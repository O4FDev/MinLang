# WS4 HTTP track

Base: frozen unified bf9c0e9; branch ws4/http-server. No rebase, v2 merge or push.
API/test commit: a1edb5d2fce00bd1d23ce34fb537d3853b1c2327.

Reusable server implemented in library/httpserver.min, separate from the client.
Batch requests/private tickets, shared-loop integration, strict framing/Host,
bounded Content-Length, explicit 501+close for request transfer codings, HEAD and
204/205/304 framing, pipeline ordering, fixed deadlines and bounded I/O/accepts.
No compiler/runtime/native/shared clang-driver changes or WS3 dependency.

Test-first initial cached-compiler check failed because httpserver was absent.
Local compile-only check passed with cached compiler SHA 06567c8e29c758fa6a4e14fac6e840e8b4405174706e7d041525d61b688eb618.
Local catalogue check passed (507 sources, 24 invalid controls).

Linux execution: parent-owned bx_ppv9fjr7, exclusively assigned namespace
/home/user/ws4/http-r2, copied immutable candidate baseline. Commands:

```
build/minyarc tests/httpserver.min build/httpserver-api.ll --bounded-owners 32 --library library
make -j1 check-httpserver
make -j1 check-httpserver-sanitize
```

All exit 0. Debug/release and ASan+UBSan+Linux LSan exercised the real library
through sockets: fragmented delimiters/binary bodies, bounded bodies/headers,
framing ambiguity, finite rejection, HEAD error replies, no-body statuses,
response injection, ordered keep-alive pipeline, truncated/half-close peers,
3 MiB partial writes, slow-client fairness, fixed drip/application deadlines,
connection-capacity recovery, stale/duplicate tickets, slot reuse and close.
Make wiring is mandatory in check/check-portable/check-sanitize.

Fresh candidate Linux compiler SHA f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b;
Clang 18.1.3, Python 3.12.3. Input hashes/modes and raw command results are in
ws4-http-evidence/. No host lifecycle action or paid spend by this child.
Final remote source/compiler SHA and mode verification passed. The additional
remote catalogue invocation failed because the parent baseline archive lacks
.github/workflows/ci.yml; the full local checkout catalogue passes. Its failing
command result is retained rather than counted as passing qualification.

Pending: independent parent review; actual macOS and Windows execution; cache
front using this API, Rust/axum comparator and finite 548-query byte/LRU/HoL
harness; quiet-host <=1.5x axum p50 AND p99 gate. No performance claim yet.
