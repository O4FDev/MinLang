# A portable HTTP server

Import `httpserver` for a bounded HTTP/1.1 server over Minyar's portable event
loop. One owner polls the server and responds to the returned requests; there
are no handler callbacks or worker threads inside this module. The complete
[Tideboard example](../examples/gallery/tideboard/README.md) serves a browser
interface and a JSON API on loopback.

```minyar
use "httpserver" as http
use "errors" as errors

let server = http.listen("127.0.0.1", 8080, http.defaults())
if !http.ok(server) { fail(errors.message(http.serverError(server))) }
while true {
    let batch = http.poll(server, -1)
    if errors.isError(http.batchError(batch)) {
        http.close(server)
        fail(errors.message(http.batchError(batch)))
    }
    for request in http.requests(batch) {
        let response = http.response(200, "text/plain; charset=utf-8", Bytes("Hello, sea.\n"))
        if !http.respond(server, request, response) { http.abandon(server, request) }
    }
}
```

`listen(host, port, limits)` returns a Server. Check `ok(server)` and inspect
`serverError(server)` if it fails. Port zero asks the operating system to choose
an available port; `port(server)` reports it. `close(server)` releases the
listener, all connections and the event loop. Close it when ending an ordinary
server loop.

`poll(server, milliseconds)` waits for network events and advances connection
state. Use -1 to wait until work or a deadline. A Batch contains `requests(batch)`
and `batchError(batch)`. Each Request has `method`, `target`, `headers`, `body`
(Bytes), and `keepAlive`. `header(request, name)` looks up a header without
case sensitivity and returns empty Text when absent. Target parsing, routing,
body decoding and application data validation belong to the application.

Construct a Response with `response(status, contentType, body)` and append
`Header { name: ...; value: ... }` values to its `headers` List when needed.
`respond(server, request, response)` queues a response for that request's private
ticket and returns Boolean. A false result can mean an expired/consumed request
or an invalid response. `requestActive` checks a ticket and `abandon` closes its
connection without replying. Do not reuse consumed tickets. Poll again to flush
queued output and make progress on other connections.

The server writes Content-Length and connection framing itself. Applications
cannot supply Content-Length, Transfer-Encoding, Connection, Trailer or Upgrade
response headers. Response status must be 200–599, header names must be HTTP
tokens, and header values must be ASCII without controls other than tab. Bodies
and headers must fit the configured limits. HEAD responses omit body bytes.
A `Transfer-Encoding: chunked` request body is decoded into `body` under the
same `maxBodyBytes` limit and body deadline; chunk extensions and trailer fields
are discarded. Any other transfer coding gets 501, and a request that carries
both Content-Length and Transfer-Encoding gets 400; both close the connection.

`defaults()` supplies finite connection, header, body and response limits,
per-turn accept/I/O/event budgets, a request limit per connection, deadlines
for idle, header, body, application and write phases, and `streamBufferBytes`,
the unsent bytes one streamed response may queue (64 KiB). The server copies Limits
at listen time. Set application-specific values before listening: Tideboard
uses 32 connections and 512-byte bodies. This bounds server buffers; an
application must also bound its own collections and response construction.

## Streamed responses

`stream(server, request, response)` starts a chunked response instead of
`respond`: it sends the status and headers with `transfer-encoding: chunked`,
and a non-empty `response.body` as the first piece. The request stays the
stream's handle. `send(server, request, piece)` writes one piece as a chunk as
soon as the socket accepts it, and `finishStream(server, request)` writes the
last chunk; the connection then serves its next request. 204, 205 and 304
cannot stream, and a HEAD request gets the head while its pieces are dropped.

```minyar
let events: List<http.Request> = []
// For each GET /events request:
let head = http.response(200, "text/event-stream", Bytes("data: hello\n\n"))
if http.stream(server, request, head) { events.add(request) }
// Later, after any poll:
for open in events { http.send(server, open, Bytes("data: tick\n\n")) }
```

`send` returns false when the stream has ended or when its unsent bytes would
pass `streamBufferBytes`; `streamActive(server, request)` tells the two apart,
and a full stream accepts pieces again once a later poll has written some. A
stream waiting on a reader that takes nothing for `writeMilliseconds` is
closed; an idle stream has no deadline, so send keep-alive pieces if
intermediaries need them. A streaming connection keeps reading: when the client
closes it, the next poll releases the stream, and `endedStreams(batch)` lists
the `requestId` of every stream the server released (by disconnect, stall or
close) since the previous Batch. `abandon` closes an active request or stream.

## Without sockets

`session(limits, nowMillis)` returns a Session: one HTTP/1.1 connection with
the same parser, framing and limits, driven by bytes and a caller's millisecond
clock instead of a socket. It reads no clock and performs no I/O, so a
`deterministic` function can drive it with the `simulation` module.
`session.receive(bytes, now)` returns a Batch whose `accepted(batch)` counts
the bytes taken (offer the rest after answering), `session.takeOutgoing(max)`
returns bytes for the peer, `session.finishInput(now)` reports the peer's end of
input, and `session.tick(now)` applies deadlines and dispatches a pipelined
request once a response has been taken. `respond`, `stream`, `send`,
`finishStream`, `requestActive`, `streamActive` and `abandon` are Session
methods with the Server functions' meaning. `closed()` turns true when the
session has ended the connection.

## HTTPS on the same listener

Import `httpstls` and call `listenTLS(host, port, limits, identity, privateKey)`.
It returns the same `httpserver.Server` with the same poll/respond API and
limits; only the bytes on the socket differ. Keeping TLS in its own module
means a plain `http.listen` program never imports, links or starts the
TLS/crypto natives.
`identity` is a List of DER certificates (leaf first) and `privateKey` is a
PKCS#8 DER key. Each accepted connection runs a TLS 1.3 session
(`tlsserver`, ALPN "http/1.1", no client authentication), so request and
response buffers stay plaintext and bounded by the same Limits. A failed
handshake, a truncated record or a peer that disappears mid-handshake closes
that connection only; polling continues. TLS connections end with an
authenticated close_notify when the response closes them.

```minyar
use "httpserver" as http
use "httpstls" as httpstls
use "errors" as errors
use "io" as io

let identity: List<Bytes> = [io.readBytesFile("leaf.der")]
let server = httpstls.listenTLS("127.0.0.1", 8443, http.defaults(), identity, io.readBytesFile("leaf.pk8"))
if !http.ok(server) { fail(errors.message(http.serverError(server))) }
while true {
    let batch = http.poll(server, -1)
    for request in http.requests(batch) {
        let response = http.response(200, "text/plain; charset=utf-8", Bytes("Hello over TLS.\n"))
        if !http.respond(server, request, response) { http.abandon(server, request) }
    }
}
```

An invalid identity or key is reported by `httpstls.listenTLS` before any connection is
accepted: check `ok(server)` as for plain HTTP. Server name selection (SNI),
client certificates and HTTP/2 remain application or separate-module concerns.

For a shared event loop, `loopHandle(server)`, `waitMilliseconds(server, timeout)`
and `advance(server, eventBatch)` expose the same state machine. Keep one owner
and include the server's earliest deadline when choosing a wait.

`make check-httpserver` (including `check-httpserver-tls`) and
`make check-httpserver-front` qualify the transport.
`make check-showcase-tideboard` compiles the real example at O0/O2 and exercises
its API through loopback HTTP requests. Client authentication, durable
application storage and deployment policy are separate concerns.
