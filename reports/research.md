# Research log — run 2, agent `res`

Goal (Luke 20:40): broadly faster than today's Minyar, aiming at optimised C. This lane invents past the known
techniques and measures what it can. Base: `bbee03178` (run-2 base, compare geomean 2.52 vs fastest reference,
2.03 vs Rust). Everything below is measured on box H unless stated; Ir = cachegrind instructions.

Known techniques already taken or in flight by other lanes: escape analysis / stack storage (`esc`), Perceus
borrow+drop inference (`brw`, `drp`), in-place reuse (`fbip`), SwissTable Maps (`map`), Text views without headers
(`txt`), codegen/SIMD (`cg`), profiling (`prof`). This log deliberately does not repeat those.

## Idea queue (design → why it could pass the known limits → status)

| # | idea | why it is new here | status |
|---|---|---|---|
| R1 | Text hash memoised in the header, interned short Texts | Map-heavy programs re-hash the same Text 2–3× per source op (wordfreq: hash 14%, memcmp 8%); text values are immutable, so a cached hash and a canonical copy are sound | measuring |
| R2 | Interned Text = pointer-equal keys (bounded, per-thread table) | turns Map key compare into a pointer compare for repeated keys and removes allocation for repeats | design |
| R3 | Lazy `for x in text.split(sep)` (split-list sinking) | the List of views exists only to be iterated: logstats split+slice+teardown ≈ 70% | design |
| R4 | Allocation-site "escape on demand": bump-allocate objects in a per-call region, promote on an escaping store | static escape rejects 96–98% of functions; a runtime store barrier is 2–3 compares per store vs 40–70 Ir per object for alloc+free+scheduler | design |
| R5 | Frame-limited reuse in the other direction: a short-lived *region* per loop iteration for aggregates the compiler proves die at the backedge | frame-limited reuse paper bounds the space; Minyar frees per object today | design |
| R6 | Checked-overflow facts from induction variables (loop versioning on a range proof) | pure-compute programs are 99% user code and overflow tests block vectorisation and reassociation (U11) | design |
| R7 | Pure-compute: hoist Text header loads out of call-free scan loops with a "text bytes are immutable" alias fact | U4/U7 | design |

## Measurement protocol

- `python3 benchmarks/compare/run.py --only NAME` (Ir, deterministic) on box H; compare against
  `/home/agent/swarm/base-results/compare.json`; a change is kept only if every measured program is within +0.1%
  and at least one is better.
- Wall only for the few programs that matter, n=3 interleaved under `flock /home/agent/bench.lock`.
- Correctness: compare `--check` (O0 + release, C-identical output) and the narrowest `make check-*`.

## Log

(pending base seed)
