# HTTP/1.1 server

`use "httpserver" as http` imports the hosted Linux/macOS/Windows server.
The existing `http` client is independent. The server uses `eventloop` and
`net.readInto` / `net.writeRange`; it adds no native package.

```minyar
use "httpserver" as http
use "errors" as errors

let server = http.listen("127.0.0.1", 8080, http.defaults())
if !http.ok(server) { fail(errors.message(http.serverError(server))) }
while true {
    let batch = http.poll(server, -1)
    if errors.isError(http.batchError(batch)) { break }
    for request in http.requests(batch) {
        http.respond(server, request, http.response(200, "text/plain", Bytes("hello")))
    }
}
http.close(server)
```

`Request` contains method, raw target, lowercase header names, binary body and
keepAlive. `header(request, name)` returns the first matching value, or empty
Text. `requestId` identifies an application request. Owner, slot and ticket are
private: `respond` rejects foreign, expired, duplicate and reused tickets.
It returns false for an invalid response without consuming a live ticket.
`requestActive` tests whether work can still be answered; `abandon` closes it.
Modifying public request fields does not modify its stored framing decision.

For asynchronous upstream work, use `loopHandle(server)` and reserve negative
event tokens <= -2 for application watches (the listener uses -1, clients >=0).
Call `loop.wait(handle, http.waitMilliseconds(server, timeout), maxEvents)`,
then `http.advance(server, batch)` and handle application events from the same
batch. Keep checking `requestActive` to cancel expired upstream work. Remove
application watches before closing their sockets and before `http.close`,
which closes the shared loop. Application requests have no client watch while
dispatched, preventing close/HUP notifications from spinning a paused socket.
Rewatching happens when a response starts. `poll` is the simple owned-loop helper.

Only HTTP/1.1 origin-form targets and OPTIONS `*` are accepted. Syntax requires
CRLF, ASCII header values, token field names, exactly one nonempty Host, and a
DNS-style host or bracketed numeric IPv6 with an optional port in 1..65535.
Whitespace before a colon, folding, bare LF, controls and non-ASCII header
octets are rejected before conversion to Text. CONNECT and upgrades are not
supported. This is a deliberately strict server subset; it is not an HTTP
proxy or a general streaming body decoder.

Bodies use one decimal Content-Length, bounded before arithmetic or allocation.
Duplicate Content-Length (even equal), comma lists, duplicate Transfer-Encoding
and TE+CL return 400 and close. An otherwise framed request with any
Transfer-Encoding, including chunked, receives a finite 501 and closes; its
connection is never reused and its body is not dispatched. Expect receives
417 and closes without waiting for a body. Oversized bodies return 413;
oversized headers or too many fields return 431. Framing follows the security
boundaries in [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3),
with the deliberate transfer-coding restriction above.

Responses accept statuses 200..599 and validated ASCII headers. The server
owns Content-Length, Transfer-Encoding, Connection, Trailer and Upgrade;
application attempts to set them are rejected. HEAD sends the hypothetical
body length and no body. 204 omits Content-Length and sends no body; 205 sends
Content-Length: 0; 304 may send the supplied representation length and no body.
There is no informational response, protocol switching, streaming response or
automatic Date header. Response body storage is retained without concatenating
or copying; callers must treat supplied Bytes as immutable while the server
may send them (immutable cache entries work well).

Limits are snapshotted at listen. Defaults bound 1024 live connections, 16 KiB
headers, 64 fields, 1 MiB request bodies, 16 MiB response bodies, 1000 requests
per connection, 32 accepts and 64 KiB I/O per readiness turn. Connection slots
are reused and bounded by maxConnections. Input storage is bounded by
maxHeaderBytes + maxBodyBytes; only one request per connection can be in the
application phase, preserving pipeline order. Excess pipeline bytes stay in
the kernel once that bounded buffer fills. Each buffered request is dispatched
on a later advance turn, so a hot pipeline cannot monopolize a batch.

Idle (30 s), headers (5 s), body (10 s), application (30 s), and writes (10 s)
use fixed monotonic deadlines; byte progress never extends a phase deadline.
Idle/app/write expiry closes directly. A partially read request expires with
one finite 408, followed by the write deadline and close. Deadlines run while
advance/poll is driven; blocking application work cannot be preempted. Accepted
sockets are nonblocking. EOF before a complete body returns 400; full requests
and half-closed peers may still receive their response. Watches are removed
before socket close, and `close` is idempotent.

Run `make check-httpserver` for real socket tests at debug/release. The portable
gate includes it. Windows and sanitizer qualification are recorded separately;
source portability alone is not execution evidence.
