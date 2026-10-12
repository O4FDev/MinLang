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

Benchmark fixture/test commit: 283a5ad8c7a3b3d9a4f7ff86687450f971a0c625.

Quiet performance acceptance **passed** on parent-admitted exclusive
bx_8b8ercp7:/home/user/ws4/http-bench. PID33738/cmd_bi3qixj4jzoc, exit0,
2026-10-12 15:07:07..15:08:04 UTC. Exact command:

```
python3 benchmarks/httpserver/compare.py --minyar build/httpserver-front --axum build/axum-target/release/minyar-httpserver-axum-front --queries benchmarks/httpserver/inputs/queries.tsv --replay benchmarks/httpserver/inputs/bodies.jsonl.gz --output build/httpserver-acceptance-r1
```

Three alternating paired rounds, all five cohorts, unchanged <=1.5x p50 AND
p99 threshold. Ratios (Minyar/axum p50, p99): miss 1.005/0.980; hit 0.844/0.769;
stats 1.190/1.247; HoL miss 1.069/1.011; HoL hit 0.981/1.304. Worst 1.304.
Pinned corpus/replay, raw miss/hit byte identity, exact LRU/raw keys/accounting,
held-miss causal HoL and concurrent overlap all passed. Recorded total_us
compute-delay replay is a deterministic fixture, not a live-engine claim.
Samples and binary/input hashes are retained in acceptance-samples.tar.gz and
acceptance-results.json; commands/tool/source receipts are adjacent.

To prevent launcher Make rebuilds changing compiler artifact identity, quiet
Minyar build directly invoked copied immutable baseline compiler f4f589...
with --bounded-owners 32 --library library, then clang-driver release link with
copied baseline runtime IR SHA4119757fe8eecb06ac096a90a989bd9982d5609e6b5f8d088dba038b4cec75a2.
Post-run source/compiler/runtime/binary SHA checks passed. The shared correctness
run's later Make rebuild produced compiler0b8bd2..., despite unchanged source;
that actual artifact hash is retained separately, not asserted equal to f4f589.

macOS native wire and actual cache-front smoke passed using authorized cached
compiler06567c... and freshly compiled O0 candidate runtime/net sources. Commands
and hashes are in macos-native.json/macos-front.json; no bootstrap, privilege or
laptop security operation occurred. This covers actual kqueue execution.

Pending: independent parent review; actual Windows execution on its admitted
verified relay; root integration/full programme performance regression gates.
No rebase/v2 merge/push by this child, no downstream edits, no paid spend. All
owned remote jobs are exited; parent controls host lifecycle and slot release.

## R1 correction and requalification

Independent R1 requested one P2 fix: FIN plus backpressured writes could keep
HUP ready and spin. Corrected in1751f1e: unwatch immediately on writing HUP,
retain unsent bytes, bounded10ms would-block probes through shared wait clamping,
unchanged fixed deadline and I/O fairness budget. Mandatory combined regression
detects spin and proves exact4MiB resumed-FIN replies, timer/other-client
progress and cleanup. The initial red530995 waits/530965 closed-only, plus an
intermediate unchanged-bound nonpass, are preserved.

The first corrected default benchmark failed hit p99=1.6303; entire failed
run retained. Performance change f6d9dfb packs responses<=64KiB with headers;
large bodies remain borrowed. After source-bound full correctness/SAN tests,
all original default three-round/five-cohort p50 ANDp99 gates passed on the
exclusive quiet host (PID33933, exit0; worst1.103x). No gate, corpus, delay,
cohort or sample selection was changed. Original283a/bd43 evidence is intact.

Test-only64bb2e9 adds empty/65535/65536/65537 exact binary pipeline/CL boundaries.
Final source-bound baseline f4 compiler debug/release/ASan+UBSan+LSan plus all
protocol/HUP/front controls pass (PID79356), as do bounded Mac native checks.
All jobs exited. Complete original finding, reply, red/failure/passing runs,
runner commands, source/mode/tool/object identities and samples are in
ws4-http-r1-response.md and ws4-http-evidence/r1/. Fresh independent R2 and
actual Windows execution remain pending, alongside root integration gates.
