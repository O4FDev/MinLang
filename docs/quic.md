# QUIC development status

`library/quic.min` implements a socket-independent QUIC v1 client and server in
Minyar. It uses our `tls.min` / `tlsserver.min` TLS 1.3 handshake over ordered
CRYPTO frames. It does not wrap an upstream QUIC or TLS transport. The native
providers supply AES, X25519, ChaCha20/Poly1305, certificate trust, and
asymmetric signatures. X25519 and ChaCha/Poly1305 use the same pinned,
unmodified Monocypher 4.0.3 source as the updater; see `vendor/README.md`.
TLS Finished and ticket binder comparisons use its fixed-size constant-time
comparisons. Low-order X25519 inputs fail before key derivation. The upstream
2020 audit assessed an earlier version, and is not a security audit of Minyar.

This is still an experimental transport. The complete requested QUIC standard,
deployment interoperability matrix and production capacity measurements have
not yet been completed. TCP fallback is implemented through our TLS/yamux
transport; it requires the caller to open the replacement socket.

## Implemented behavior

- AES-128-GCM Initial packets, AES and ChaCha20-Poly1305 negotiated traffic,
  header protection, packet number reconstruction, and Retry integrity.
- Separate Initial, Handshake, and application packet number spaces; key
  discard, authenticated transport parameters, TLS client/server certificate
  verification, and required client certificates when configured.
- Ordered bidirectional/unidirectional streams, bounded offset reassembly,
  duplicate handling, conflicting buffered-byte detection, final-size checks,
  stream and connection flow control, and recoverable backpressure.
- ACK ranges, RTT estimation, packet/time loss deadlines, retransmission under
  fresh packet numbers, PTO probes, CUBIC congestion window calculations, and
  token-bucket pacing with two-MTU confirmed bursts and recovery buffer credit.
- Application key updates with handshake/ACK gating, unchanged header
  protection keys, phase wrap, bounded retention of old read keys, precomputed
  next read keys, and per-key AES confidentiality usage limits.
- Authenticated client path migration with unpredictable exact-path challenges,
  per-path amplification budgets, bounded candidate paths, path recovery timers,
  and preserved streams. Native socket/address mapping remains caller-owned.
- Server anti-amplification before address validation, protocol and application
  connection-close frames, bounded packet/parser queues, and idle timers.
- Client Retry processing and stateless server Retry tokens bound to the exact
  peer address, connection IDs, version and a bounded validity interval.
- TLS PSK-DHE resumption, authenticated encrypted tickets, current trust and
  certificate-expiry revalidation, and opt-in replay-safe QUIC 0-RTT.
- A bounded yamux v0 multiplexer over authenticated TLS/TCP, automatic QUIC
  timeout/outage detection, and connection generations that reject retired
  stream handles instead of implicitly replaying application writes.

The TCP TLS server also shares this handshake state machine. OS roots are the
default; explicit roots are an exclusive trust store. Client-auth and
server-auth certificate purposes are checked separately. RSA-PSS and ECDSA
CertificateVerify signatures are bound to the verified leaf and transcript.

## API

```minyar
use "quic" as quic
use "errors" as errors

let connection = quic.client("localhost", randomBytes(80), "peer-edge", roots, identity, key)
// Feed datagrams with a monotonic millisecond clock.
quic.receive(connection, receivedPacket, now)
// Send each returned datagram once, preserving datagram boundaries.
for packet in quic.poll(connection, now) { /* send packet */ }
// Wait on socket readiness until quic.nextTimer(connection).
let opened = quic.openStream(connection, false)
if errors.integerOk(opened) {
    let id = errors.integerValue(opened)
    let written = quic.writeStream(connection, id, Bytes("request"), true)
    // A would-block result leaves the entire application write unconsumed.
}
```

`server` takes the original destination connection ID from the first Initial,
its certificate chain, PKCS8 or supported opaque identity key, trust roots, and
whether a client certificate is mandatory. `readStream` distinguishes data,
EOF, would-block, and failure. `updateKeys` returns would-block until the
handshake, current-phase ACK, and reordering conditions permit an update.

`quicretry.store` takes a fresh random 16-byte server key and a token lifetime
of at most two minutes. `reply` creates a Retry without allocating connection
state; `validateInitial` authenticates a returned Initial token against exact
address bytes and connection IDs. Only its private, validated result can be
passed to `quic.serverAfterRetry`. Route that connection using
`initialDestination`, because the original destination ID remains bound in
transport parameters while Initial protection uses the Retry source ID.
Rotate the token key before its bounded issuance budget is exhausted.

The caller owns socket readiness, datagram source addresses, scheduling, and
per-peer dispatch. Connection instances have one owner; sharing a mutable
connection across threads is not supported. Entropy must come from
`randomBytes`; test-only deterministic entropy must never be deployed.

`quicwire.destinationId(packet, 8)` reads bounded, unprotected routing metadata
without decrypting or parsing frames. This result does not authenticate a peer.
New connection allocation still needs Initial bounds, amplification limits,
and a separately bounded dispatcher.

`quicdispatch` supplies a bounded SipHash-2-4 CID table and indexed timer heap.
Use a fresh 16-byte random table key, stable connection slot IDs, and
`lookup`/`insert`/`remove` plus `schedule`/`cancel`/`takeDue`/`nextDeadline`.
Removal reuses slots; repeated timer updates retain one node per connection.
The remote soak fixture uses these structures and only polls peers with input
or due timers. `quic.release` clears retained state after closing completes;
it rejects live connections. Idle expiry silently closes, per RFC 9000.

`transport.client` / `serverQUIC` / `serverTCP` expose `receiveUDP`, `pollUDP`,
`receiveTCP`, `pollTCP`, `tick`, and `nextTimer`. On `TCP_NEEDED`, open a fresh
TCP socket and call `startTCP` with fresh entropy. TCP negotiates the configured
ALPN plus `.yamux/1`, and verifies certificates again. `peerCertificate` returns
checked leaf DER only in `QUIC_READY` or `TCP_READY`, including revalidated
resumed identities. Hash this public certificate to bind an application device
registry. Mandatory mTLS is selected by the server constructor.

Fallback increments `generation`. Previous stream handles fail with code 1002
(`retryRequiredCode`); the caller decides which operations to retry on freshly
opened streams. QUIC early-data rejection similarly retires those early stream
IDs with code 1001. Application data is never copied to replacement streams.

Tickets use wall-clock time; transport recovery uses monotonic milliseconds.
Early data is disabled by default. `tlstickets.allowEarlyData` and
`quic.clientEarly` explicitly enable replay-safe operations. Ticket acceptance
rechecks cached certificate chains against current roots, purpose and time;
server identity, SNI and ALPN are bound inside authenticated tickets. The server
also bounds ticket expiry by the earliest server/device certificate expiry and
checks its own configured identity's current time bounds before resuming.
A delayed, previously valid PSK ClientHello cannot resume an expired identity.
The native `currentCertificateExpiry` helper extracts strict RFC 5280 time
bounds only; it does not establish trust and never replaces `chain` or
`clientChain`. Its UTC-century, generalized-year, leap/calendar and truncation
tests use an independent datetime oracle and
[OpenSSL's ASN.1 time test approach](https://github.com/openssl/openssl/blob/master/test/asn1_time_test.c).
The server
also rejects early data when remembered limits decrease. The single-use cache
holds at most 4096 unexpired ticket fingerprints: saturation rejects early data
while ordinary resumption remains possible. Early-data acceptance is bound to
one random server-instance ID; another instance or a restart sharing the same
ticket encryption key rejects early data. A fleet-wide replay cache is not
implemented, and relay/arbitrary requests must keep early data disabled.

## Remaining constraints

`receivePath` and `pollDatagrams` use stable numeric path IDs mapped by the
caller to local sockets and exact peer addresses. `probePath` initiates client
validation; a second unvalidated candidate is refused. Server-initiated active
migration and preferred-address migration are not implemented. Version 2 crypto/parser vectors pass, while live constructors
currently use version 1. The server can emit stateless version negotiation for
unsupported versions. The v1-only client follows RFC 9000 section 6.2: it
abandons an eligible version-negotiation response containing no v1, allowing
TCP fallback, and ignores responses after Retry/authentication, with wrong
connection IDs, or listing v1. Live v2 and compatible version negotiation are
not implemented. Retry preserves packet numbers and the exact ClientHello,
accepts only one correctly authenticated Retry, and verifies the server's
authenticated Retry-source transport parameter. Resumption and opt-in 0-RTT
are experimental and have independent
peer tests, but their sustained fault-soak evidence is still outstanding.

`resetStream` and `stopSending` cancel one stream direction without terminating
the connection. A failed read/write has `streamResetCode()` (1003), with the
peer's application error in `errors.nativeCode`, including error zero.
RESET final size still consumes flow credit and must match any received FIN.
Opening a higher peer ID implicitly creates the lower IDs of its type.
Streams are reclaimed at `poll` after both directions finish: sending needs
all data plus FIN acknowledged, or RESET acknowledged; receiving needs final
size plus the application observing EOF/reset. Call `readStream` to observe
completion even after receiving the last data bytes. Closed IDs are retained
as at most 256 ranges; old frames cannot reopen them. Once reclaimed, reads
return EOF and writes return closed. Final-size checking for already reclaimed
streams is omitted as permitted by RFC 9000 section 4.5. At most 128 active stream
records remain, and MAX_STREAMS credit is replenished on peer-stream closure.
The sanitizer churn test completes 2000 mixed bidirectional/unidirectional
streams with at most two retained records. This is a bounded functional test,
not hours-long churn or a memory benchmark. Locally issued connection-ID
retirement remains unsupported. Yamux still retains at most 128 stream records
and bounds connection buffers to 1 MiB; its stream reclamation is outstanding.
Persistent congestion uses bounded send-order history across all packet-number
spaces. It collapses CUBIC to two datagrams only after an uninterrupted loss
interval longer than three base PTOs, with an RTT sample predating those sends;
an intervening ACK breaks the interval. Metadata shares the existing sent
record, and acknowledged/lost records release their retained payloads. The
RFC9002 example and its two false-positive adversaries pass sanitizers. CUBIC's
epoch excludes application idle time; a paced sending backlog is still active.
RTT sampling uses the largest newly acknowledged packet's send time even when
that packet was ACK-only, provided the ACK also acknowledges new eliciting
data. ACK-only send timestamps are capped at 4096; an ACK older than retained
metadata cannot contribute a sample. Duplicate ACKs do not sample again.
ECN remains outstanding. BBR is exploratory: Google's BBRv3 and QUIC BBRv2
implementations require delivery-rate and minimum-RTT models, app-limited
sampling and probe states, rather than a different CUBIC window formula.
The [IETF BBR draft](https://datatracker.ietf.org/doc/draft-ietf-ccwg-bbr/)
targets Experimental status. BBR implementation and comparative remote loss,
fairness and bottleneck tests remain future work; CUBIC is the current policy.
Local close/error enters a three-PTO closing
period; authenticated packets can trigger close responses with exponential
backoff. A received close enters a three-PTO draining period, which sends no
packets. Public state becomes CLOSED/FAILED immediately, but socket adapters
must keep routing the CID and calling `poll`/`nextTimer` while `closing` or
`draining` is true. `release` refuses both periods. Idle expiry remains silent
and can release immediately. The closing test drops the first close, rejects
forged triggers, recovers on a real peer packet, and verifies deferred release.

The macOS AES provider uses CommonCrypto's CPU-dispatched AES block primitive
and our scalar GHASH. Linux uses OpenSSL EVP and Windows uses BCrypt GCM/ECB;
these providers select available CPU acceleration. No performance claim about
AES-NI, ARM crypto, idle cost, or per-connection memory is inferred from their
presence. Freestanding builds have fail-closed host-provider stubs.

## TDD and interoperability evidence

The crypto, parser, TLS-server, stream/recovery, transport, and key-update tests
were introduced before their implementations. Missing modules/APIs failed
first; the original TLS client accepted an untrusted self-signed certificate.
The tests now reject that connection and the other adversarial fixtures.

Short deterministic checks:

```sh
python3 tests/quic-crypto.py --sanitize
python3 tests/quic-wire.py --sanitize
python3 tests/tls-server.py --sanitize
python3 tests/quic-transport.py --sanitize
python3 tests/quic-transport.py --key-update --sanitize
python3 tests/quic-transport.py --migration --sanitize
python3 tests/quic-transport.py --server-protocol --sanitize
python3 tests/quic-transport.py --quic-resumption --sanitize
python3 tests/quic-transport.py --early --sanitize
python3 tests/quic-transport.py --fallback --sanitize
python3 tests/quic-transport.py --retry --sanitize
python3 tests/quic-transport.py --rtt --sanitize
python3 tests/tls-resumption-expiry.py --sanitize
python3 tests/transport-go.py --sanitize
python3 tests/quic-quinn.py
MINYAR_QUINN_KEY_UPDATE=1 python3 tests/quic-quinn.py
python3 tests/quic-quinn.py --migration
python3 tests/quic-quinn.py --resumption
python3 tests/quic-quinn.py --early
```

Static RFC 9001 and RFC 9369 Appendix A oracles verify the complete published
client/server packets, secrets, keys, ChaCha packet, and Retry integrity,
including every byte tamper and every proper prefix. Parser tests use an
independent Python varint encoder, all frame/header prefixes, bounds/role
checks, and 30,000 seeded mutations. Virtual-clock transport tests cover lost
Initial/server flight/data, duplication, reordering, certificate-authenticated
streams, and random unauthenticated datagrams. The TLS server is exercised by
independent Python/OpenSSL clients, including unknown, expired, future,
wrong-purpose and absent client certificates.

Quinn 0.11.12 / quinn-proto 0.11.19 with rustls 0.23.45 is a test-only pinned
independent peer. Both client and server roles exchange a stream over actual
UDP with mutual TLS, including a peer-initiated key update. Both roles also
pass an actual UDP-port change: Quinn rebinding
and a Minyar client switching between two native sockets.
Both roles pass TLS resumption and accepted replay-safe 0-RTT. Deterministic
tests reject reused tickets and tickets from a new server instance, and real
short-lived certificates expire between initial and resumed handshakes.
HashiCorp yamux v0.1.2 with Go's independent TLS 1.3 exchanges sixteen concurrent
32 KiB half-closed streams in both roles, including required client certificates.
Quinn is not linked
into Minyar. On 2026-10-10, the remote official runner's handshake and transfer
cases passed with quiche and MsQuic in both client/server directions. The
ngtcp2 wolfSSL image failed in both directions with `ERR_CRYPTO` at the TLS
ClientHello/ServerHello boundary; this remains unresolved. The runner's
`--must-include` filtered square matrix also hit an upstream JSON-export
`KeyError`, after producing its individual checks and logs. Rectangular matrices
avoid that reporting issue. These results do not establish full RFC compliance;
retry, loss/corruption, migration, key-update, resumption and 0-RTT runner cases
still need their independent matrix. See the accompanying evidence manifest.

## Remote fault soak

Sustained load and performance runs must run on remote Linux hosts. The
`tests/quic-soak.py` guard requires `MINYAR_REMOTE_LOAD=1`. The fixture can
route 64 long-lived independently authenticated Quinn peers on one UDP socket,
with 15-second heartbeats, seeded packet loss/reordering, and per-process
Linux `/proc` RSS/CPU samples. `--server-only --front-address ADDRESS
--fixtures DIRECTORY` supports a peer on another remote host. The report
records the executable/source hashes, versions, raw samples, faults, and exit
statuses; an external process deadline is still recommended.

The fixture accepts up to 16,384 peers, with a setup allowance separated from
the full duration after all peers authenticate. `tests/quic-peer-soak.py`
records the independent peer's own CPU/RSS and binary hash, with file-backed
output and an independent deadline. A separate `--idle-seconds` run negotiates
180-second idle timeouts, disables Quinn keepalives, waits for one authenticated
echo from every peer and a second barrier, then pauses for at most 120 seconds.
Server `RETAINED` records expose active/authenticated counts, CID routes and
timer entries. Proxy counters in each sample distinguish zero-ingress connected
idle from a heartbeat/loss workload. Teardown is staggered after the quiet
window; final live connections, routes and timers must all be zero. Such a
measurement also requires a coordinated quiet host window without other
builds or interoperability traffic. The fixture itself establishes no
production capacity, idle-cost or flat-memory claim.

Functional soak success, flat memory, and near-zero idle CPU must be reported
from completed artifacts. A startup-only idle sample, a bounded parser fuzz
run, and a loopback echo do not establish those results.

## Primary design and test sources

- [RFC 9000 transport](https://www.rfc-editor.org/rfc/rfc9000.html),
  [RFC 9001 TLS and packet vectors](https://www.rfc-editor.org/rfc/rfc9001.html),
  [RFC 9002 loss recovery](https://www.rfc-editor.org/rfc/rfc9002.html),
  [RFC 9369 version 2 vectors](https://www.rfc-editor.org/rfc/rfc9369.html), and
  [RFC 9438 CUBIC](https://www.rfc-editor.org/rfc/rfc9438.html).
- [ngtcp2 packet tests](https://github.com/ngtcp2/ngtcp2/blob/main/tests/ngtcp2_pkt_test.c)
  informed systematic truncation and malformed-length coverage.
- [Quinn virtual-clock tests](https://github.com/quinn-rs/quinn/blob/main/quinn-proto/src/tests/mod.rs)
  informed loss, duplication, and reordering tests.
- [quiche packet implementation/tests](https://github.com/cloudflare/quiche/blob/master/quiche/src/packet.rs)
  and [MsQuic handshake tests](https://github.com/microsoft/msquic/blob/main/src/test/lib/HandshakeTest.cpp)
  informed packet-number/protection and authentication boundaries.
- [Quinn force-key-update test API](https://docs.rs/quinn/0.11.12/quinn/struct.Connection.html#method.force_key_update)
  drives the independent key-update check.
- [QUIC interop runner](https://github.com/quic-interop/quic-interop-runner)
  defines the remaining deployment matrix.
- [RFC 8446 resumption and early data](https://www.rfc-editor.org/rfc/rfc8446.html)
  and [RFC 8448 handshake traces](https://www.rfc-editor.org/rfc/rfc8448.html)
  provide the independent binder oracle.
- [HashiCorp yamux protocol](https://github.com/hashicorp/yamux/blob/master/spec.md)
  and [its session tests](https://github.com/hashicorp/yamux/blob/master/session_test.go)
  inform wire flags, flow control and half-close behavior.
