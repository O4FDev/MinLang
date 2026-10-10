# Hearth private relay adapter

`use "peerwire" as wire` implements **HPW1**, a concrete socket-independent
adapter for the Hearth peer supply contract in Tolum's
`HEARTH_PEER_SUPPLY.md` §§10.3.1–10.5. This is a private adapter contract;
it is not an HTTP/2 or native gRPC implementation. Gateway TLS connections use
the application-selected ALPN `hearth.gateway/1`. The application owns sockets,
TLS/QUIC handshakes, stream dispatch, registry refresh, revocation, timers,
target policy and concurrency admission.

## Binary envelope

Every frame has this 16-byte header followed by exactly `length` payload bytes.
Integers are unsigned big-endian; reserved bytes must be zero.

| Offset | Width | Meaning |
| --- | --- | --- |
| 0 | 4 | ASCII `HPW1` |
| 4 | 1 | Kind from the table below |
| 5 | 3 | Reserved, zero |
| 8 | 4 | Stream ID |
| 12 | 4 | Payload length |

| Kind | Value | Stream | Payload |
| --- | --- | --- | --- |
| HELLO | 1 | 0 | Strict JSON object, at most 16KiB |
| HEARTBEAT | 2 | 0 | Strict JSON object, at most 16KiB |
| OPEN | 3 | 1–4294967295 | Strict JSON object, at most 16KiB |
| STATUS | 4 | 1–4294967295 | ASCII status, at most 16 bytes |
| DATA | 5 | 1–4294967295 | Opaque bytes, at most 64KiB |
| CLOSE | 6 | 1–4294967295 | Empty |
| START | 7 | 1–4294967295 | Strict JSON object, at most 16KiB |

Only CLOSE may have an empty payload. Unknown kinds, incorrect stream classes,
nonzero reserved bytes and excessive lengths are protocol errors. DATA can
contain arbitrary bytes, including zero and malformed text.

The decoder holds at most 1MiB. Create one with `create()`, call
`feed(decoder, bytes)`, then repeatedly `take(decoder)`. Check
`frameOk` / `frameError` before the checked getters `kind`, `streamID` and
`payload`. `wouldBlockCode()` means a partial frame needs more input.
`finish(decoder)` marks EOF; complete queued frames can still be drained.
An incomplete final header or payload yields `truncatedCode()`, and an empty
finished decoder yields `closedCode()`. Invalid framing or decoder overflow is
sticky and releases the buffered input. After a fatal result discard the
decoder. `encode(kind, streamID, payload)` returns an `errors.BytesResult`.

## Metadata and authenticated routing

Strict JSON uses `json.parseUniqueBytes`: malformed UTF-8, unpaired escaped
surrogates and duplicate decoded member names, including nested duplicates,
are rejected. Metadata roots must be objects. The parser also bounds nesting,
value counts and object members as documented in [peer-auth.md](peer-auth.md).
The framing layer returns recoverable typed errors for hostile bytes; reading
success fields from rejected results is a programmer trap.

The first device control frame is HELLO with exactly
`{"device_id":"device-a","exit_id":"exit-a"}`. Its IDs must match an
actual authenticated `peerauth.Binding`, obtained after mTLS verification and
trusted registry lookup. `makeHello(binding)` constructs it;
`helloMatches(frame, binding)` checks it. `createDevice(binding)` and
`receiveDevice(device, frame)` enforce HELLO first, followed only by HEARTBEAT
on stream zero. Check `deviceReady` / `deviceError`. Repeated HELLO or a
pre-HELLO heartbeat is a protocol error. `heartbeatIntervalSeconds()` is 15;
the application schedules it and enforces freshness. `makeHeartbeat(bytes)`
and `parseHeartbeat(frame)` validate only the generic strict JSON shape and
size. Capacity, paused state, policy hash, public IP, ASN, country and optional
sticky metadata belong to the application's health policy.

Gateway OPEN has exactly these members:

```json
{"dial_grant_bytes":"<exact compact JWT>","exit_id":"exit-a","conn_id":"conn-1","deadline":1060}
```

`deadline` is a positive canonical integer Unix timestamp, not a duration.
IDs use 1–128 ASCII letters, digits, `_`, `-` or `.`. Token text is bounded to
8192 ASCII compact-JWT characters. `parseOpen(frame)` checks structure;
`openOk` / `openError` gate the getters `openGrant`, `openExitID`,
`openConnID` and `openDeadline`. `makeOpen(id, token, exit, conn, deadline)`
builds the envelope. Structure validation alone grants no authority: the edge
calls `peerauth.inspect` with its authenticated exit binding and current time
before allocating a relay or forwarding a START.

`makeStart(id, verifiedGrant)` accepts only a successful private auth result.
It forwards the exact retained JWT and emits exactly `dial_grant_bytes`,
`exit_id`, `conn_id`, `port`, `expires`, and one of `target_host` / `target_ip`.
For example:

```json
{"dial_grant_bytes":"<exact compact JWT>","exit_id":"exit-a","conn_id":"conn-1","target_host":"example.com","port":443,"expires":1060}
```

The device calls `verifyStart(frame, keys, authenticatedExitID, expectedConnID,
nowSeconds, deadlineSeconds)`. It independently verifies the gateway signature
and all auth policy, then checks every unsigned target/ID/expiry echo against
the signed claims. It returns a private `peerauth.Grant`; only its checked
destination getters authorize the actual target connection. `parseStart` is
available for generic inspection but is not an authorization helper. The
application supplies a deadline at most the verified expiry and rechecks it
when target establishment completes. It owns immutable connection IDs,
replay admission and dispatch from the physical TCP/QUIC stream to HPW1 IDs.

## Status, flow and backpressure

Each relay's first inbound frame is STATUS, with unquoted ASCII payload
`ok`, `grant_invalid`, `exit_offline` or `policy_denied`.
`makeStatus`, `parseStatus`, `statusOk`, `statusError` and `statusValue` expose
this contract. `createRelay(verifiedGrant, id)` binds private immutable exit,
connection and stream IDs. `receiveRelay(relay, frame)` accepts the first
status, then DATA or CLOSE. All subsequent frames must use that stream ID.
Duplicate status, cross-stream frames, data before status or after close are
sticky protocol failures. A rejection status is terminal. Check `relayReady`,
`relayClosed`, `relayError` and `relayStatus`; checked ID getters are
`relayExitID`, `relayConnID` and `relayStreamID`.

Incoming and outgoing queues each have an independent 1MiB maximum. This keeps
one blocked direction from consuming the opposite direction's capacity;
the application must also bound the number of concurrent relay/decoder
contexts. `receiveRelay` appends incoming DATA only when the entire frame fits.
On `wouldBlockCode()` it consumes no bytes and changes no state: retain the
frame, stop reading that stream, drain with `takeIncoming`, then retry that
same frame once space exists. Never discard it or process later stream frames
first. `enqueueRelay(relay, bytes)` queues one DATA frame, including its header
in the outgoing budget, or returns `wouldBlockCode()` without mutation.
`incomingBytes` / `outgoingBytes` expose queue occupancy.

`takeIncoming(relay, positiveMaximum)` and
`takeOutgoing(relay, positiveMaximum)` drain up to that many bytes. Outgoing
drains can split headers and payloads; the socket adapter owns any unsent
remainder after a partial write. `closeRelay` queues CLOSE when space permits
and marks the relay terminal. Already queued incoming/outgoing bytes remain
drainable. CLOSE ends both directions in this version; half-close is not
represented. The adapter must release a decoder/relay after EOF or fatal
failure and must not feed decoder control results back as protocol frames.

## Test evidence

All execution uses the existing authorised remote lab, not the developer
laptop. The tests began with a stub that rejected an independently encoded
valid status frame. A Python standard-library `struct` encoder and separate
decoder model check the exact network byte order, 65,968 complete all-prefix
controls and 500 seeded bit/truncation mutations. Header/type/ID/length limits,
EOF truncation and the exact decoder overflow boundary are checked.

The independent flow model tests 23 metadata cases, 14 status/order/identity
cases, exact JWT forwarding and independently decoded signed claims. START
verification rejects changed token, exit, connection, destination, port or
expiry echoes. Two endpoints preserve distinct binary streams through tiny
fragmented transfers; queue tests fill the exact 1MiB bound, reject without
mutation, drain, retry the held frame and check the remaining bytes exactly.
Rejected getter access is checked separately as a programmer trap.

Flow tests use an independently generated certificate solely for the
socket-independent binding policy fixture. Actual CA/EKU/expiry/possession,
TLS handshake and revocation controls run in `tests/peer-auth-device.py`;
the flow fixture does not claim to perform a live authenticated handshake.
Ed25519 fixture signing uses independent OpenSSL, with RFC 8037/8032 controls
and the same provenance documented in [peer-auth.md](peer-auth.md). The normal
and ASan/UBSan gates are `make check-peer-wire` and
`make check-peer-wire-sanitize`.
