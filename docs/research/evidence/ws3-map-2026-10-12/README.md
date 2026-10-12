# WS3 Map implementation evidence

All heavy work ran only on WS3-owned Boat `bx_ez43hrrp`, in
`/home/user/ws3/map`, under `/home/user/ws3/build.lock`. No paid provisioning,
root host, local heavy build, privileged security operation, or Windows VM was
used. Native macOS and Windows qualification are pending parent coordination.
Checked-in failure-log copies trim trailing whitespace; original Boat logs remain
unchanged at their recorded build paths.

The dependency is WS2's approved frozen-baseline stack
`193c8af`, `47a1159`, `39a8e72`, cherry-picked as `1b2f1d9`, `8f63bd7`,
`ca7ac33`. The baseline source SHA-256 remains
`a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf`.
No baseline branch, hash, provenance, or gate was relaxed.

The generic cache fix is the separate dependency
`a9d76fd0c93602c23c4d8a6cc3307f81c02c824a`, with no Map typing/runtime changes.
It deduplicates complete declaration lines across cached module bodies and
handles both combined blocks and individual declarations. Detection rejects
ordinary `@` globals and definitions before scanning a first line. Cached
bodies retain their requirements; only assembled output is deduplicated.

## Verification

- `map-matrix.log`: 14 Map tests across four frontends and ten owned runtime
  configurations: 560 test cases, each executing at O0/O2 where applicable.
  Eleven native profiles include the process-lifetime compiler arena. Coverage
  includes the independent Python dictionary and dense-array models, wrapped
  collision clusters, growth/backshift, UTF-8 equal keys, managed aliases,
  right-side clear, compound assignment, imported types, exact fatal errors,
  generic overflow, and Map-cycle rejection.
- `map-sanitize.log`: the same matrix with four sanitized compilers and
  ASan/UBSan runtime/generated-code instrumentation, plus seven callable/Result
  cases. Normal owned exits enforce exact live-object recovery. Arena retains
  process-lifetime allocations, so only that native arena case disables LSan.
- `map-final-build.log`: clang22 serial thinLTO builds with the unchanged
  768MiB compiler limit; core stage2/stage3 LLVM equality.
- `map-graphs-final.log`: 12 managed-graph regressions, including byte-for-byte
  ordinary IR comparisons against the frozen compiler. Map declarations are
  emitted only when a Map operation needs them.
- `map-frontends-final.log` and `map-frontends-sanitize-final.log`: seven Map
  callback/Result cases on the final graph adapter, native and ASan/UBSan.
  Captures and callable signature parsing preserve negative Map types. A
  deferred guard rejects callback edges that would cycle through a Map while
  accepting unrelated cyclic values owned by a Map.
- `map-regressions-initial.log`: compiler hardening 33, ordinary regressions 29,
  List literals 6, ownership 11, recursive data 16, managed graphs 12,
  callbacks 20, and Result language 26 tests passed. The incremental launcher
  then failed because a nested build selected default Clang/linker settings.
  `map-incremental-final.log` records the passing rerun with the exported
  clang22 serial-link environment.
- `map-module-cache.log`: cold/warm Map output equality and invalidation of an
  importer when a private record field behind Map/List return wrappers changes.
- `map-module-cache-initial.log`: preserved failing duplicate-declaration repro
  before the generic cache fix. `feature-declarations.log` adds independent
  combined-four/individual-ten declaration controls, Unicode comments, and
  ordinary-global/body preservation at O0/O2.
- `map-catalogue.log`: all new test sources have registered runners.

`map-post-dedup.log` repeats the complete native and sanitizer matrices on the
generic declaration fix, and confirms the compiler fixed point.
`map-graphs-post-dedup.log` and `map-incremental-post-dedup.log` repeat the
ordinary-IR and module regressions after that change.
`map-module-cache-signed.log` additionally proves actual warm type-table/body
reuse for a nested signed Map type whose magnitude exceeds 32 bits. Type slots
now have a checked signed 64-bit reader; lengths/counts keep their natural
reader. This prevents the cache driver's ordinary frontend fallback from
hiding an unsupported negative type table. `map-incremental-signed.log` keeps
the general module suite green on that final reader.
`map-callable-values-final.log` and `map-callable-values-sanitize-final.log`
extend the callable/Result cases to nine, including a saved owned callback
remaining callable after Map clear, at O0/O2 with exact recovery.

The native snapshot insertion regression also fails when `map_store` is
mutated to call the ordinary List setter, and passes with the traced setter.
It inserts into an empty bucket during ROOTS while another root precedes the
child, preventing replacement's release barrier from hiding a missing retain
barrier. This small C check does not constitute native platform qualification.

## Reproduce on the assigned Boat

Export these settings inside the serial lock before invoking Make or launchers:

```sh
export CC=clang-22 LLVM_CC=clang-22 MINYAR_CLANG=clang-22 MINYAR_TEST_CLANG=clang-22
export COMPILER_LTO_FLAGS='-flto=thin -fuse-ld=lld-22 -Wl,--thinlto-jobs=1 -Wl,--threads=1'
export SWIFTC=/home/user/.local/share/swiftly/bin/swiftc
make check-maps check-maps-sanitize
make build/minyarc-baseline build/compiler-stage3.ll
cmp build/compiler-stage2.ll build/compiler-stage3.ll
python3 tests/managed-graphs.py
python3 tests/incremental-modules.py
```

The exact job wrapper is `flock /home/user/ws3/build.lock bash -c '...'`, with
its working directory `/home/user/ws3/map`. Retain stdout/stderr logs. For peer
timing, first confirm no other WS3 compiler/test/benchmark process is active;
hold the lock for compilation and the complete benchmark, not only each sample.

## Peer measurements

`peer-results.json` retains all seven rotated repetitions, source hashes,
versions, CPU affinity, checksums, medians, and ratios. The benchmark is
end-to-end Minyar lowering, with runtime LLVM linked at O2 and serial thinLTO.
Peers are standard Rust `HashMap` (`rustc -O`) and Swift `Dictionary`
(`swiftc -O`). Toolchains: clang22.1.8, Rust1.97.1, Swift6.4.0, Linux x86-64;
all processes pinned to CPU0.

Key construction is excluded from insert/lookup/mixed/remove timings. There
are no reserve hints. Each language builds independent equal query keys and
uses the same permutation and value checksum. Rust Text keys borrow the
fixture strings to avoid an additional per-insert allocation. Text equality
and standard hash policies remain each language's shipped behavior.

For 2,000,000 Integer keys, median times in insert/lookup/mixed/remove order
were Minyar **154/99/230/137ms**, Rust **98/193/401/191ms**, and Swift
**197/207/458/308ms**. Minyar beat Swift in every phase; Rust inserted faster,
while Minyar looked up, mixed, and removed faster.

For 200,000 Unicode path Text keys, the same order was Minyar
**19/48/44/59ms**, Rust **20/34/59/44ms**, and Swift **148/85/145/105ms**.
Minyar beat Swift in every phase; Rust lookup/removal were faster. These
results do not claim superiority in every operation or equivalent hash costs.

Reproduce with `MINYAR_TEST_CLANG=clang-22 SWIFTC=... python3 tests/maps-bench.py`
inside the exclusive lock. Fixtures are in `benchmarks/maps`; emitted source,
LLVM, executables, and JSON are retained under `build/maps-bench` on Boat.

## Performance gate and remaining integration

`compiler-diagnostic.json` preserves a **failed pre-dedup** fixed-input diagnostic:
31 alternating CPU samples, pinned identical foundation input/output, median
baseline 7.139ms and candidate 7.301ms, ratio **1.022692**, limit **1.01**.
This short compiler diagnostic is not the complete acceptance gate; it is
retained as an unresolved regression signal, not dismissed or relabeled pass.
Its JSON identifies the measured compiler binaries. The final declaration and
signed-table changes have not been requalified by the full performance gate.

The parent owns the integrated selfcompile/Minyarcraft/Atacama/JSON/neo-db
gate at <=1% regression, independent review, central Map builtin reservation,
generated docs, platform qualification, and merges. Map-contained ownership
cycles remain conservatively rejected. No v2 merge/push has been performed.
