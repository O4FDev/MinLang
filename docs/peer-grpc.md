# Native Hearth gateway gRPC transport

`http2` and `peergrpc` are native Minyar protocol modules for the private
Hearth gateway contract. Their production code imports only Minyar modules;
Python h2, HPACK, protobuf and grpcio are pinned independent **test peers**.
The gateway connection uses actual TLS with ALPN `h2`; the caller performs
mTLS and control-plane identity authorization before supplying plaintext
bytes. The device connection continues to use [HPW1](peer-wire.md).

This mapping uses standard HTTP/2, HPACK, uncompressed gRPC message envelopes,
protobuf and gRPC status trailers. Its private service schema is
[peer.proto](../tests/interop/peergrpc/peer.proto). This document does not claim
interoperability with an existing Tolum gateway service whose schema has not
been supplied; that service must use this explicitly agreed mapping.

## Service and first messages

The bidi method is `/hearth.peer.v1.PeerGateway/Dial`. A request's first
protobuf message is `DialRequest.open` with exact compact JWT bytes,
`exit_id`, `conn_id`, and `deadline` in Unix seconds. Subsequent requests carry
`DialRequest.data` opaque bytes. The first successful response is
`DialResponse.status`, followed by `DialResponse.data`. Enum values are
`OK=1`, `GRANT_INVALID=2`, `EXIT_OFFLINE=3`, `POLICY_DENIED=4`;
`UNSPECIFIED=0` grants no authority. A rejection status ends the response with
`grpc-status: 0`: the RPC carried a typed admission result successfully.
Protocol failures instead use a gRPC error status, generally INTERNAL (13).
Deadline expiry uses DEADLINE_EXCEEDED (4).

Each protobuf message has the standard five-byte gRPC prefix: compression byte
zero and unsigned big-endian 32-bit serialized length. OPEN is at most 16KiB;
data bytes are at most 64KiB, allowing up to 65540 protobuf bytes and 65545
envelope bytes. Compression is deliberately unsupported: request
`grpc-encoding` is absent or `identity`, and nonzero message compression flags
are rejected. `application/grpc` and `application/grpc+proto` content types,
POST, the exact method path and `te: trailers` are required. Unknown/repeated
protobuf routing fields or oneof variants are rejected rather than allowing
last-field routing changes; the private schema has no extension fields.

Parsing an OPEN supplies no authority. The caller calls `peerauth.inspect`
with the actual certificate/registry exit binding, exact JWT, immutable
request IDs, current Unix seconds and `openDeadlineSeconds`. Only the private
verified grant supplies the destination. It binds the selected device mux,
then forwards `peerwire.makeStart` so the device independently verifies the
same original JWT. No grant signing, target dialing, Redis state, registry
network lookup or public service listener is performed by these modules.

## Application API

```minyar
use "peergrpc" as grpc
use "errors" as errors
let server = grpc.create()
grpc.transportTick(server, monotonicMilliseconds)
let accepted = grpc.receive(server, plaintextBytes)
let opened = grpc.requests(server, unixMilliseconds)
if grpc.openOk(opened) {
    let id = grpc.openStreamID(opened)
    // Verify openGrantBytes/openExitID/openConnID/openDeadlineSeconds.
    // Retain openDeadlineMilliseconds/openMonotonicDeadlineMillis unchanged.
    grpc.sendStatus(server, id, "ok")
}
```

All calls return typed errors for hostile input. Check `openOk` / `openError`
before the private result getters `openStreamID`, `openGrantBytes`,
`openExitID`, `openConnID`, `openDeadlineSeconds`,
`openDeadlineMilliseconds` and `openMonotonicDeadlineMillis`. The token getter
returns a copy. Reading a rejected result is a programmer trap.

Call `requests` promptly after every `receive`, until it reports would-block.
It accepts new HTTP/2 headers, drains bounded message fragments, and returns
each valid OPEN once. A malformed RPC is terminated independently; the
connection can continue with other streams. `read(server,id,positiveMaximum)`
returns opaque request data, would-block, typed error or EOF. `write` queues
one data message atomically. `sendStatus` must precede application data writes
and reads; known rejection statuses close the response. `closeStream(server,
id,grpcStatus,message)` sends final status trailers after previously queued
responses, with standard percent-encoding of `grpc-message`.

`takeOutgoing(server,positiveMaximum)` drains serialized HTTP/2 bytes. Socket
ownership and partial writes remain with the caller: retain the unsent suffix
after any partial transport write. `finish` reports truncated transport input;
after EOF discard the connection and its pending RPC contexts. Inspect
`connectionError` to distinguish connection failure from an individual RPC.

## Clocks and deadlines

`requests`, `tick` and `nextDeadlineMillis` use **Unix wall-clock
milliseconds**. `openDeadlineSeconds` preserves the original request deadline
for the auth verifier. The effective millisecond deadline is the earlier of
that absolute deadline and the request header's `grpc-timeout`, measured from
header acceptance. The standard H/M/S/m/u/n timeout units and at most eight
digits are supported. Submillisecond durations round up to the available
millisecond timer precision; 500m remains exactly 500 milliseconds.

Call `transportTick(server,monotonicMillis)` immediately before
`receive`/`requests` and on timer events. Each RPC also freezes an independent
monotonic deadline using the original remaining duration. Neither deadline is
recomputed on later samples. A backward wall-clock change cannot extend the
relative timeout. `openMonotonicDeadlineMillis` is zero only if the caller
omitted the initial monotonic sample; the gateway caller must supply it.
`nextTransportDeadlineMillis` returns the earliest RPC monotonic deadline or
HTTP/2 SETTINGS ACK deadline. Map wall-clock waits to monotonic waits using
the current difference, and enforce both immutable bounds at establishment.

The HTTP/2 module itself exposes monotonic `tick` / `nextDeadlineMillis` and
requires SETTINGS acknowledgment within ten seconds of the initial tick.
Time-related failures are recoverable values. Positive read/drain maxima and
checked-result use are programmer obligations.

## HTTP/2 engine and bounds

The socket-independent engine exposes `create`, `receive`, `finish`,
`takeOutgoing`, `requests`, `read`, `respond`, `write`, `closeStream`,
`resetStream`, `connectionError`, `bufferedInput`, `bufferedOutput`, `tick`
and `nextDeadlineMillis`. A request result has checked `streamID`, `headers`
and `endStream` getters; use `requestOk` / `requestError` first. Headers are
`Header { name: Text; value: Text }`; `headerValue` retrieves a field.

It checks the client preface and initial SETTINGS, sends server SETTINGS and
ACK, handles PING ACK, RST_STREAM and GOAWAY, and assembles noninterleaved
HEADERS/CONTINUATION blocks. Client IDs are odd, positive and monotonically
allocated. Request pseudo-fields precede regular fields and are unique;
connection-specific headers, invalid lowercase names, control values,
misplaced trailers and inconsistent content lengths fail the stream.
This server is scoped to the POST gRPC mapping; CONNECT, extended CONNECT,
server push, HTTP/1 upgrades and general HTTP routing are not offered.
Legacy priority frames are validated but scheduling does not use priority.
Unknown extension frame types, undefined flags and reserved stream-ID bits
are ignored as required by HTTP/2.

HPACK supports static and dynamic indexed fields, all literal forms, table
size updates, bounded integer/string decoding and the complete RFC 7541
Huffman alphabet. EOS symbols, overlong/non-EOS padding and invalid references
fail the connection. Dynamic entries retain original opaque bytes so rejected
metadata cannot corrupt later indexing or trigger a UTF-8 conversion trap.
Private gateway header values use visible ASCII and HTAB only; non-ASCII
values are rejected at the stream boundary. Outgoing headers use never-indexed
literals without Huffman coding, which is standard HPACK and avoids shared
secret-dependent dynamic state.

Advertised limits are 64 concurrent streams, a 4KiB decoder dynamic table,
16KiB encoded/decoded header blocks, 128 fields, 16KiB HTTP/2 frames, and
initial connection/stream flow windows of 65535 bytes. Closed drained contexts
are removed before new streams are admitted. Inbound and outbound connection
byte queues each cap at 1MiB. The outbound cap includes all pending stream DATA
and serialized frames; ordinary writes reserve 4KiB for control output.
gRPC fragment/application queues share a separate 1MiB cap across calls.
Metadata and table bounds are additional fixed caps; the caller bounds total
connection count.

Application reads release connection and stream receive-window credit.
Padding is accounted for in flow control and immediately credited after
validation. Writes stall in bounded queues when either send window is zero,
and WINDOW_UPDATE resumes them. Backpressure consumes no supplied application
bytes: retain and retry the same write after draining output. Oversized input
feeds return would-block without accepting a prefix; retry in smaller chunks.
Fatal connection errors generate GOAWAY; stream errors generate RST_STREAM or
typed gRPC trailers while other streams remain usable.

## Evidence and provenance

The independent stub controls first rejected valid HTTP/2 and protobuf OPEN
fixtures. Tests then use separately implemented Python h2/HPACK encoders and
an actual grpcio network client, rather than Minyar encoder/decoder roundtrips.
Pinned versions are in [requirements.txt](../tests/interop/peergrpc/requirements.txt)
and apply only to isolated test venvs. Normal and ASan/UBSan gates are
`make check-peer-grpc` and `make check-peer-grpc-sanitize`; all development
execution was on the existing authorised remote lab.

The campaign covers every prefix of a request and maximum-size HTTP/2 DATA
frame, 315 protobuf message prefixes, all 256 Huffman octet symbols and the
fixed RFC 7541 C.4.1 vector, dynamic references/resizing, continuation ordering,
24 framing/compression errors, ten header controls, 250 seeded HTTP/2
mutations and 150 protobuf mutations. Exact queue limits and a zero-window
stall verify that rejection preserves bytes and drain/retry makes progress.
Three simultaneous grpcio bidi streams each cross the initial flow window
with a 64KiB message and preserve distinct binary payloads. First status,
rejection enum values, uncompressed message boundaries, percent-encoded
trailers, getter traps and exact 500ms deadlines under backward wall time are
checked independently.

The standalone network fixture is explicitly plaintext loopback and tests
protocol behavior; the product adapter supplies actual mTLS/ALPN h2. Actual
certificate/registry controls are separately tested in the auth gate. This
slice does not claim the standalone fixture itself authenticates a gateway.

Primary protocol sources are [RFC 9113](https://www.rfc-editor.org/rfc/rfc9113.html),
[RFC 7541](https://www.rfc-editor.org/rfc/rfc7541.html), the
[gRPC HTTP/2 protocol definition](https://github.com/grpc/grpc/blob/816d41355f831fdaec27e3d4cb4e5d3fe0d55637/doc/PROTOCOL-HTTP2.md),
and [protobuf encoding](https://protobuf.dev/programming-guides/encoding/).
The Huffman numeric constants were extracted directly from RFC 7541 Appendix B;
their Revised BSD notice is retained in `library/http2.min`. Independent peers
are [python-hyper/h2](https://github.com/python-hyper/h2),
[python-hyper/hpack](https://github.com/python-hyper/hpack),
[grpc/grpc](https://github.com/grpc/grpc) and
[protocolbuffers/protobuf](https://github.com/protocolbuffers/protobuf).
