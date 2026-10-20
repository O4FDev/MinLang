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
Request transfer codings are rejected with 501 and connection close.

`defaults()` supplies finite connection, header, body and response limits,
per-turn accept/I/O/event budgets, a request limit per connection, and deadlines
for idle, header, body, application and write phases. The server copies Limits
at listen time. Set application-specific values before listening: Tideboard
uses 32 connections and 512-byte bodies. This bounds server buffers; an
application must also bound its own collections and response construction.

For a shared event loop, `loopHandle(server)`, `waitMilliseconds(server, timeout)`
and `advance(server, eventBatch)` expose the same state machine. Keep one owner
and include the server's earliest deadline when choosing a wait.

`make check-httpserver` and `make check-httpserver-front` qualify the transport.
`make check-showcase-tideboard` compiles the real example at O0/O2 and exercises
its API through loopback HTTP requests. HTTPS termination, authentication,
durable application storage and deployment policy are separate concerns.
