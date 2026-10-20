# Networking for a reverse proxy

The portable `httpserver` module owns HTTP/1.1 parsing and downstream socket
lifetimes. Use `loopHandle(server)` to share its readiness loop with upstream
sockets. Its listener uses token -1 and downstream slots use nonnegative
tokens; caller watches use other negative tokens. Feed each readiness batch
to `advance(server, batch)` and your own dispatcher. Clamp the wait with
`waitMilliseconds(server, requested)` and your own transaction deadlines.
Remove a socket's event registration before closing the socket.

`drain(server)` stops listening and closes idle or incomplete request readers.
Already dispatched requests retain their private tickets and deadlines. They
may still receive a response; the server closes after sending it. Already
queued responses finish their partial writes before closing. Buffered pipeline
requests are not dispatched during drain. Continue advancing the loop until
`connectionCount(server)` reaches zero, then call `close(server)` to release
the loop. Repeated drain/close calls are safe. A drained server has no port.

Check `requestActive(server, request)` before dispatching a late upstream reply;
`respond` checks the ticket too. A request that has expired must not deliver a
reply into a reused connection slot. `abandon` closes an active dispatched
request when no valid response can be generated.

The server accepts complete bounded request bodies. It rejects transfer-coded
requests, upgrades, CONNECT tunnels and expectations; its response API generates
Content-Length and Connection. Proxy callers must remove hop headers and every
field nominated by Connection before passing response headers. Keep arbitrary
body data in Bytes and validate untrusted header bytes before constructing Text.

TLS1.3 server sessions are separate socket-independent state machines. Their
ClientHello SNI bytes are now checked as bounded ASCII DNS names before Text
construction. Empty/overlong labels, edge hyphens, trailing dots, addresses and
non-ASCII bytes reject the session. SNI may be absent. Internationalized names
use ASCII A-labels. This follows the host_name contract in
[RFC6066 section3](https://www.rfc-editor.org/rfc/rfc6066.html#section-3);
an invalid peer field must not turn into a process-wide UTF8 conversion stop.

These APIs support a bounded proxy implementation; they do not establish its
HTTP/2 or HTTP/3 interoperability, throughput, or memory qualification. The
dedicated drain and SNI checks are listed in [testing](testing.md).
