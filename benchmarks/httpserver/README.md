# Reusable HTTP server cache-front qualification

`front.min` uses library/httpserver.min through batch `advance`, private request
tickets, `respond`, and the shared event loop. Upstream misses use numeric
nonblocking connects and fresh TCP sockets; hits run while misses wait. No
serving-project source is modified. `cache.min` is the fixture-only index/hash
LRU adapted from its read-only front_ev.min, without a Map dependency.

The axum comparator uses axum 0.8.6 and Tokio 1.47.1 with a current-thread
runtime, fresh asynchronous upstream sockets, TCP_NODELAY on both directions,
the same 5 s upstream deadline and 4 MiB body/16 KiB header bounds. Cargo.lock
pins transitive crates. It uses a hash index and linked LRU entries, preserving
exact recency, entry/key+body byte limits, replacement accounting, and oversize
rejection. Neither fixture decodes raw query values for its cache key. The key
is the first raw `k` value, **one NUL octet**, and the first raw `q` value.
Minyar constructs that octet using Bytes.add(0): the frozen baseline's Text
parser does not implement brace Unicode escapes used by the old reference.

Both fixtures accept `PORT UPSTREAM_IP UPSTREAM_PORT [ENTRIES] [BYTES]`, print
the actual port once, expose identical GET /api/search and /stats behavior,
cache only successful 200 bodies, and report hits, misses, entries, bytes,
evictions and upstream_connects. Defaults are 100,000 entries / 256 MiB. Client
keep-alive works, but the reference workload intentionally opens a fresh
client TCP connection and sends Connection: close for every measured request.

The identical workload domain is valid body-free HTTP/1.1 GET requests, bounded
cache responses and two concurrent actors. Axum's general request parser,
listener limits and informational/transfer-coding features are not being
claimed equivalent to the stricter Minyar server outside that domain.

Inputs are exact read-only copies of brief-serving's 548-query dev_all.tsv and
raw/runs/direct_r1.bodies.jsonl.gz, retaining all body bytes including timing
fields. SHA256:

```
queries.tsv       74f31164ecbcb19c8911870510fd7fb56f58d79930d39fc0c3aebd9c1e1fb6f6
bodies.jsonl.gz   6233b7f0e13c9c5563d65d892d750d1ab6357ddddc5d39cc91dd530d35d660bb
```

The deterministic replay upstream injects each recorded response's total_us
compute delay, unchanged for either front, before serving its exact bytes. This
models the recorded search workload plus the replay host's socket/HTTP overhead;
it does not claim to execute a live search engine or reproduce its wall latency.

Build on an admitted Boat host, in the assigned child namespace only:

```
./minyar --release benchmarks/httpserver/front.min -o build/httpserver-front
CARGO_HOME="$PWD/build/cargo-home" CARGO_TARGET_DIR="$PWD/build/axum-target" cargo build --release --locked --jobs 1 --manifest-path benchmarks/httpserver/axum/Cargo.toml
CARGO_HOME="$PWD/build/cargo-home" CARGO_TARGET_DIR="$PWD/build/axum-target" cargo test --release --locked --jobs 1 --manifest-path benchmarks/httpserver/axum/Cargo.toml
```

`make check-httpserver-front` is mandatory in check/check-portable. It compiles
the actual API fixture, checks its Minyar LRU directly, compares wire accounting
against an independent Python OrderedDict, and causally proves a cache hit can
finish while an upstream miss is deliberately held. It requires no Rust build
or external input/download and is suitable for Linux/macOS/Windows qualification.

The full **acceptance** harness requires a quiet, dedicated admitted benchmark
host. No other child builds/test jobs may overlap performance timing:

```
python3 benchmarks/httpserver/compare.py \
  --minyar build/httpserver-front \
  --axum build/axum-target/release/minyar-httpserver-axum-front \
  --queries benchmarks/httpserver/inputs/queries.tsv \
  --replay benchmarks/httpserver/inputs/bodies.jsonl.gz \
  --output build/httpserver-acceptance
```

Output must be empty. Runs are finite (600 s total deadline, bounded request
timeouts and request counts, terminated/joined subprocesses). Three paired
rounds alternate process order and start fresh empty caches. Each sequential
round measures 548 misses, 548 hits and 548 stats replies. HoL warms query zero,
then measures 547 other misses concurrently with 548 hits of that cached query,
checking that they overlap. Raw bodies must equal every recorded byte, on both
miss and hit paths. Counter/entry/byte values, raw key distinctions, LRU order,
byte evictions, oversize bypass and causal HoL are correctness gates.

All five cohorts must have Minyar p50 **and p99 <=1.5x axum**. Percentiles use
nearest rank and the gate compares the median of the three complete per-round
percentiles. There is no fallback baseline, threshold option, subset selector,
timing/score normalization, retry selection or ignored failing cohort. A failed
gate exits nonzero and records failure in results.json. Samples/body hashes,
binary/input hashes, exact front commands and upstream request targets remain
available for review. Record source/compiler/native/runtime/tool identities
alongside this output in the parent qualification record.

`--verify-only` runs one complete identity/LRU/HoL round on a shared correctness
host and reports **performance not qualified**. It is never an acceptance run.
`--self-test` checks that the fixed gate rejects missing samples and a p99-only
regression while accepting the exact 1.5 boundary. The optional Make target
`bench-httpserver` accepts HTTP_FRONT_MINYAR, HTTP_FRONT_AXUM, HTTP_FRONT_RESULTS
and runs full acceptance. Do not infer speed from a correctness-only run.

The 2026-10-12 dedicated Linux run passed every unchanged p50/p99 gate (worst
ratio 1.304x), with raw corpus identity and exact LRU/HoL checks. Source, tool,
command, samples and platform qualification receipts are recorded in
../../docs/progress/ws4-http.md and its adjacent ws4-http-evidence directory.
Windows execution and independent integration review remain separate gates.
