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

Cache fixture/harness implemented in benchmarks/httpserver/. Pinned 548-query
corpus and original recorded body gzip are included byte-for-byte. Exact key is
first raw k + one NUL octet + first raw q, bounded exact LRU and nonblocking
fresh upstream connections; both fronts run single-owner/current-thread loops.
Pinned axum/Tokio plus Cargo.lock; no Map/compiler/runtime changes.

Linux `make -j1 check-httpserver-front` passes the actual API fixture and
independent OrderedDict byte/entry/LRU oracle plus causal held-upstream HoL.
`cargo build/test --release --locked --jobs 1` passes. Full 548-query
`compare.py --verify-only` passes raw miss/hit identity, LRU/key/byte accounting
and concurrent HoL for both fixtures (PID40275, exit0). It explicitly records
performance not qualified; all original 1.5x p50/p99 gates remain unchanged.

Preserved reds: PID36250 exit2 (independent NUL key byte accounting); subsequent
byte-level Minyar regression exit1. The reference brace Unicode escape produced
four bytes on the frozen compiler; constructing Bytes.add(0) fixes only this
fixture. PID38496 exit1: AppleDouble tests/._httpserver.py from the initial
upload was correctly rejected by the catalogue. Removed that upload artifact
only; subsequent archives disable Mac metadata. After copying the parent's
immutable bf9 workflow repair, catalogue passes 508 sources / 24 controls.
Original omission/nonpasses remain in evidence. Full correctness samples stay
in owned Linux build/httpserver-verify-r4, with concise receipts here.

Pending: independent parent review; actual macOS and Windows execution;
dedicated quiet-host <=1.5x axum p50 AND p99 gate. No performance claim yet.
