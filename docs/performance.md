# Performance testing

Frontend tests measure source-to-LLVM compilation. Complete-build tests also
include Clang compilation and linking.

```sh
make check-performance
make check-scaling
make check-budget
```

`check-performance` checks compiler fixed-point output, measures self-compilation
and generated programs, and compares workloads at different sizes. Measurements
are written to `build/performance.json`. `check-scaling` covers large declaration
sets, late-bound calls, and module graphs.

The harness is `tests/performance-test.min`. For four times the input, its
limits are 5.5 times the CPU time for functions and records, and 7.0 for
statements, locals and modules. Declaration lookup uses a hash index; there
is no separate allowance for known superlinear declaration lookup.
`check-declaration-index` compares it with an independent linear oracle.

Module declaration lookup hashes the module owner, original name and declaration
kind directly. It does not allocate a qualified name for each lookup; emitted
names and declaration IDs stay unchanged. `check-module-declaration-index`
compares this index with a linear oracle and verifies cached table reloads at
O0 and O2. Generic specialization cache hits also reuse the concrete-type and
capability checks already performed for that instance.

## Local baselines

```sh
make build/tooling/tests/performance-test build/tooling/tests/compiler-behavior build/compiler-stage3.ll
./build/tooling/tests/performance-test --save-baseline
```

This saves `build/performance-baseline.json`. Later runs fail when measurements
exceed the configured tolerance. Compare runs on the same host with the same
build configuration.

## Manual benchmarks

No gate runs these targets; run them when a change touches what they measure.

- `make bench-maps`: Map operations (`tests/maps-bench.min`).
- `make bench-maps-baseline` and `make benchmark-text-basics`: compare with
  `build/minyarc-baseline`, a compiler built from the baseline control
  source. The Text benchmark writes `build/text-basics-benchmark.json` and
  `build/text-find-prefixes-benchmark.json`.
- `make bench-formats`: `bench-compression`, `bench-sha256` and `bench-tar`.
- `make bench-httpserver`: the HTTP server against axum
  (`benchmarks/httpserver/`).

## Absolute compiler budget

`check-budget` enforces 75 million retired instructions and 17 MiB peak memory,
plus matched previous/current wall and CPU comparisons over three batches of
100 alternating pairs. The paired median must be at most 1.01 and the upper
95% confidence bound at most 1.05. These limits are defined in
[`tests/performance-support.min`](../tests/performance-support.min).
Real resource qualification requires the owner macOS CI and matched inputs;
Linux can run `./build/tooling/tests/self-compile-budget --functional`.
The separate `check-performance` self-compile limits are 20 seconds wall,
2 seconds CPU and 192 MiB peak memory. The memory ceiling follows the measured
compiler: 129 MiB on Linux x86_64 on 2026-10-25, down from about 430 MiB. It
leaves room for allocators without the glibc mmap-threshold pin. Its compile-scaling phase allows 5.0x time for four times
as many functions or records; their retired instructions grow 4.0x.

`make check-budget-functional` exercises the budget controls on every platform,
including all three 100-pair batches, alternating compiler order, complete
reports and exact resource boundaries. It uses fixture measurements and does
not qualify host performance. Both `check` and `check-portable` include these
controls. On macOS, `check` also runs the real `check-budget`; an explicit
`check-budget` on another platform still rejects unsupported qualification.

The October hardening review reconstructs the starting compiler and runtime
instead of comparing against old documentation. That branch already exceeded
the instruction and memory limits. Typed source positions defer diagnostic
formatting, lexer reads reuse known characters, and direct buffer writes remove
trivial wrappers. Cold stack-bound initialization and checked LLVM success paths
reduce runtime work while retaining the error and ownership contracts.

The earlier 50-sample compiler campaign measured 72.347 million median retired
instructions and 9.281 MiB maximum RSS. On each compiler's own source, CPU falls
from 17.733 ms to 7.275 ms; identical-original-source results are recorded
separately. The independent 3×100-run budget gate also passes: 9.16 ms wall p90, 7.65 ms
CPU p90, 9.3 MiB maximum RSS, and 71.88 million instructions. Its original
ceilings and batch method are unchanged. See the
hardening report for that fixture's evidence; these are not measurements of
the current full compiler.

The budget test runs outside the development limiter because background
priority changes absolute timings. It retains all 300 paired wall and CPU
observations across three batches; shared-host load can still affect results.
Most other checks run under
`scripts/with-limits.sh`, with background priority and CPU, memory, and output
limits. Avoid parallel test jobs when comparing timings.

The public launcher's first-use bootstrap keeps those resource caps and low CPU
priority, but does not add the macOS background scheduling class. This prevents
an interactive cold build from starving behind unrelated background indexing
or backups. Bulk development checks and fuzz campaigns retain their background
policy; bootstrap invoked by an already throttled parent inherits that context.

The previous-v2 comparison retains the original and measured sources with their
hashes. When the previous source uses the removed file and argument builtins,
`prepare-compiler-budget.py` renames those calls and supplies native shims, keeping
streamed output. It leaves literals and the previous frontend rules intact. Both
compiler roles receive the identical adapted source, library arguments, runtime,
and optimization flags. The compatibility report records every renamed API;
the measured result therefore compares the previous frontend after API adaptation.

## Compiler memory

The compiler links its runtime with `MINYAR_COMPILER_ARENA`: Text, record and
small List storage come from bump arenas that are never freed. Anything the
compiler builds and drops therefore stays in its peak, so its memory is the sum
of what it ever allocated, not what is live. Two rules keep that bounded:

- A List of 2,048 or more entries owns a malloc block that grows by `realloc`,
  and `clear()` frees it. On glibc the mmap threshold is pinned so growth remaps
  pages instead of copying them.
- Token passes copy the token stream into a fresh stage. The owner of a
  superseded stage releases it: `compileTokens` marks stages through
  `SourceMap.stage` and calls `adoptTokenStage` after each pass, and a pass
  that keeps a private full copy (a prelude or a declaration prefix) releases it
  with `releaseTokens` before returning. A new pass must return a fresh
  `newSourceMap()` stage and never share its input's Lists.

Module builds create one compiler context per module, so per-module work must
not grow with the whole program: share program-wide tables (IR names) and free
module-sized ones once the module's code is joined.

To measure, compare byte-identical output and record both peak RSS and the
smallest `ulimit -v` that lets the self-compile finish (the test runner's cap is
address space, not RSS). On 2026-10-25 a normal self-compile needed 144 MiB and
a `--scope-owners` one 227 MiB, down from 700 and 810 MiB.

## Compiler time

Token passes copy most of their input unchanged. A pass advances over tokens it
keeps and calls `copyTokenRun` for the pending run before it emits a rewrite
and at its end; `copyModuleToken` is for single rewritten or synthetic tokens.
`copyTokenRun` hands a `TokenTables` record (aliases of a stage's Lists) to the
runtime helpers `compilerCopyTokens` and `compilerCopyPaths`, which append kinds,
texts, coordinates, documentation and origins in bulk and translate path indices,
adding paths to the new stage in the order its tokens first use them. The result
is the same stage a token-by-token copy builds.

Module builds compute the declaration tables' nominal types once and share that
List with every module until compiling renames a symbol. The per-module copy of
the return-type table and the symbol-node table are filled by the runtime helpers
`compilerAppendIntegers` and `compilerFillIntegers` (a `CompilerIntegers` record).

The scope-ownership lowering (`--scope-owners`) gets the piece range of every
function `compileFunction` emitted (`CompilerContext.functionPieces`) and whether
its entry calls `minyar_rc_enter`. Only those bodies are joined and split into
lines; other functions keep their pieces, and the code between functions is cut
where each definition starts and passed through unless it calls
`minyar_rc_enter`. The two borrow-coalescing rules audit every local name of a
body in one scan; `scopeNextReference` and `scopeNameEnd` are runtime helpers.
Module builds have no piece table and lower their joined module the same way.

Measured on a Linux x86_64 Boat box (LLVM 23.1.3, `perf stat -e instructions:u`,
the compiler source of b0b160445 as fixed input, byte-identical output before
and after each change): a normal self-compile fell from 2.011 G to 1.671 G
instructions with the bulk token copies, a `--scope-owners` self-compile from
2.610 G to 2.101 G with those and the per-function lowering, and a cold
incremental build of 400 modules × 21 functions without loops from 2.418 G to
2.225 G with the shared module tables (800 modules: 4.749 G to 3.982 G).

## Known release-build cost

In the September 2026 release-build fixture, the larger incremental runtime IR
raised complete release-build CPU by 16.5% because Clang optimizes and links it
with each program. Runtime artifact reuse already removed repeated C compilation;
further improvement requires separating runtime optimization from final LTO and
must be evaluated alongside application performance. This is a retained tuning
target, not a claim that the added ownership machinery is free.

## Ownership ablations

The measured 15% gap on borrowed record calls is not evidence of a missing
retain/release pair: readonly parameters already borrow their caller-owned
value and omit an ownership frame. That ablation also removes ordinary call and
stack-safety costs. Shared List replacement remains the expensive case because
the compiler cannot consume a value while another live alias exists. The new
direct Text self-replacement transfer is a deliberately narrow reuse inference;
broader borrow and last-use inference remains a measured optimization target.

## Scope ownership experiment

The direct compiler's `--scope-owners` mode removes all legacy ownership-frame
calls from the measured 721-function compiler. On Linux x86_64 with LLVM 23.1.2,
seven retained hardware-counter samples per executable measured 3,726,245,596
median eager instructions versus 4,710,602,580 for the same-source legacy
control: a 20.90% reduction. The corresponding incremental experiment fell from
8,692,398,963 to 3,436,339,021 instructions, a 60.47% reduction. Its explicit
per-cell release sequence has the different cleanup contract documented in
[runtime memory](runtime-memory.md#scope-ownership-lowering); it is not the
launcher's default bounded lowering.

Arena measured 1,188,040,017 instructions with scope lowering. A subsequent
inline eager release path reduced the same scope compiler from 3,726,245,042
to 2,873,927,153 median instructions, another 22.87%. Its matching arena measured
1,188,040,249, giving 2.4191 times arena. An unmodified runtime rebuilt through the prototype's exact path differed
from the saved eager control by only 144 instructions. All 32 follow-up outputs
matched the same frozen LLVM. The counters and runtime/header identities are in
[`frames-inline-release.json`](../experiments/memory/frames-inline-release.json).
These current-source Linux counts cannot be compared directly to earlier ARM
compiler campaigns.
All 48 executions, including warmups and legacy controls, produced exactly the
frozen original compiler's LLVM bytes. Source, LLVM, runtime and executable
hashes, every observation and the complete flags are retained in
[`frames-ownership.json`](../experiments/memory/frames-ownership.json).

Adjacent plain-borrow coalescing then reduced eager instructions from
2,873,927,000 to 2,655,982,553, a further 7.58%. Matching arena counts were
1,188,040,852 and 1,188,040,574, giving 2.2356 times arena. Both same-source
722-function scope modules have no
legacy frame calls or fallbacks. Coalescing removes 532 temporary cells,
retains and releases while preserving lasting owners and adding 15 return
polls. All 32 executions match the same frozen original LLVM, with continuous,
unscaled counters. This campaign uses one fresh output filename for all four
executables. Counts, every observation and input/runtime/executable identities
are in [`frames-borrow-coalescing.json`](../experiments/memory/frames-borrow-coalescing.json).

Removing a plain projected Text borrow used only by the next equality call
reduced eager instructions from 2,655,982,210 to 2,367,788,224, another 10.85%.
The fresh matching arena counts were 1,188,040,675 and 1,188,611,354, a 0.048%
increase. Eager now reaches 1.9921 times arena; the 1.2-times target remains
unmet. Both same-source 725-function modules have no legacy frame calls or
fallbacks. The pass removes 520 temporary cells and retains, and 869 cleanup
releases, while preserving service with 364 affected-function return polls.
All 32 executions reproduce the frozen original LLVM with continuous unscaled
counters. The new campaign output filename is shared by all four executables;
the reported reduction compares only its fresh matching controls. Complete
observations and identities are in
[`frames-compare-borrows.json`](../experiments/memory/frames-compare-borrows.json).

Extending the same lifetime proof to allocating Text join/search helpers showed
no self-compile instruction gain. Its eager median was 2,367,902,557 versus
2,367,788,397 for the fresh same-source control, a 0.00482% increase. Matching
arena medians were 1,188,611,457 and 1,188,611,839, respectively; candidate eager
is 1.9922 times arena. The pass removes 66 static cells/retains and 67 releases
and preserves service with 48 additional exit polls, but static counts do not
establish a performance improvement. Both 725-function modules have zero legacy
calls/fallbacks; all 32 outputs match the frozen original LLVM and all counters
remain continuous and unscaled. The campaign uses fresh matching controls and
one shared output filename. Complete observations and identities are in
[`frames-runtime-borrows.json`](../experiments/memory/frames-runtime-borrows.json).

Reusing temporary cells with disjoint complete CFG ranges reduced eager
instructions from 2,367,901,958 to 2,360,820,360, a further 0.2991%. Matching
arena counts were 1,188,611,561 and 1,188,646,852, a 0.00297% increase; candidate
eager reaches 1.9861 times arena. Both same-source 726-function modules have
zero legacy calls/fallbacks. Physical cells, slot GEPs and entry null stores each
fall from 4,027 to 2,594, with the largest scope falling from 153 to 96 cells.
Every logical RC call count remains identical, including retains, releases and
polls. All 32 outputs match the frozen original LLVM and all counters remain
continuous and unscaled. These fresh matching controls share one output
filename. Full observations and identities are in
[`frames-cell-reuse.json`](../experiments/memory/frames-cell-reuse.json).

Coalescing temporary borrows into their retaining record/List publishers reduced
eager instructions from 2,360,820,539 to 2,359,982,089, a further 0.03552%.
Matching arena counts were 1,188,647,852 and 1,188,647,453; candidate eager is
1.9854 times arena. Both same-source 728-function modules have zero legacy
calls/fallbacks. All actual publisher calls remain identical; 64 direct retains
and 64 temporary releases disappear, while 32 exit polls are added. Physical
cells, slot GEPs and entry null stores each fall from 2,618 to 2,613. All 32
outputs match the frozen original LLVM, with continuous unscaled counters and
one shared output filename. The 1.2 times arena target remains unmet. Full
observations and identities are in
[`frames-publish-borrows.json`](../experiments/memory/frames-publish-borrows.json).

Inlining idle public eager releases reduced instructions from 2,360,820,459
with a rebuilt control runtime to 2,357,641,733, or 0.1346%. All four profiles
link the same saved cell-reuse compiler LLVM, which predates publication-borrow
and empty-header lowering. The saved eager runtime gives 2,360,820,636;
matching arena gives 1,188,646,974, so candidate eager is 1.9835 times arena.
Both runtime variants were built through the same frozen source/header paths.
All 32 outputs match the frozen original LLVM with continuous unscaled counters.
The linked field-replacement region contains the guarded old-object decrement;
the aggregate saving is not attributed to a single region. Full observations,
source identities and the native inspection digest are in
[`frames-public-release.json`](../experiments/memory/frames-public-release.json).

[`frames-instructions.py`](../experiments/memory/frames-instructions.py) measures
Linux x86_64 user-space hardware instructions through `perf_event_open`. It
attaches to a stopped child, enables at exec, excludes the Python parent and
kernel, drops inherited sudo privileges in the compiler child, and rejects
multiplexed or unavailable counters. Permission to open hardware counters is
required; the study used `sudo -n` without changing kernel settings. One warmup
precedes retained samples and execution order alternates. Link identical legacy
and scope compiler LLVM against each runtime with the recorded ThinLTO flags,
freeze one input and library, then supply the executables as repeated
`--profile NAME=PATH` arguments. The directory must contain the measured
`compiler-stage2.ll`; `--input`, `--library` and `--report` select the artifacts.

## Modules

```sh
make check-module-performance
make check-incremental-module-performance
make build/tooling/tests/incremental-module-performance build/tooling/tests/incremental-module-memory
./build/tooling/tests/incremental-module-performance --link --sizes 400 --shapes wide
./build/tooling/tests/incremental-module-memory
```

The ordinary module benchmark measures fresh frontend processes for chains,
wide imports, and shared dependencies. It writes `build/module-performance.json`.
The incremental benchmark includes the cache driver and exercises unchanged
builds, source edits, interface edits, and cold caches. Add `--link` to include
native compilation and linking.

Memory measurements report maximum child-process RSS, rather than the sum of
simultaneous parent and child memory. See [incremental builds](incremental-builds.md)
for cache behavior and platform limits.

## Calls

On Linux and macOS a call costs what it costs in C: generated functions keep
no call-depth counter. Stack exhaustion faults in the guard region below each
language thread's stack and the runtime reports it as the usual call-depth stop
([checked failure paths](testing.md#checked-failure-paths)). Small helpers that
used to carry `minyar_stack_enter`/`minyar_stack_leave` now inline like any
other function; on box D (x86-64, cachegrind) the change retired 2-12% fewer
instructions on call-heavy programs (sortrows -11.9%, treewalk -4.4%, orders
-4.0%) and 27% fewer on a float4 fused-multiply-add kernel built from two
helper functions. Programs that use `calldepth.run`, and WebAssembly and
freestanding builds, still count calls.

## Function linkage

A whole-program build defines every function of an imported module (a package
under `--library` or a relative `use`) with internal linkage. Only the entry
module's functions and `main` stay external. Clang then drops imported
functions the program never calls, and it can inline or specialize the rest
without keeping an exported copy. Incremental builds that fall back to the full
frontend (graphs with standard-library imports, natives or constants) do the
same. Cached module bodies keep external linkage, because each body must link as
an independent object (see [incremental builds](incremental-builds.md)).

Code that binds to an imported function by symbol passes `--export-modules` to
`minyarc` or `minyar-module-build`: live images (`minyar build --hot`,
`run --watch --hot`, `minyar patch`), the REPL, and C test adapters such as
`tests/calldepth-native-adapter.c`. The option is part of the module cache key.

Measured on a Linux x86_64 Boat box with LLVM 23.1.3 (`clang -O2 -c` on the IR
of one compile, `perf stat -e instructions:u`, before and after):
`tests/regressions.min` 4.43 → 2.41 G instructions (0.61 → 0.30 s),
`tests/scope-ownership.min` 4.61 → 2.73 G, `tests/diagnostics.min`
2.77 → 2.13 G, `tests/text-literals.min` 1.57 → 1.18 G, `tools/project-cli.min`
7.42 → 7.02 G, and a ten-line program using `io`, `json` and `files`
1.11 → 0.48 G.

## Comparing generated code with C++

`experiments/memory/critical-path-study.min` checks arithmetic, indexed List work,
and record access against independent Python results and equivalent checked C++.
Use `--measure --count 5000000 --samples 31 --output results.json` for a local
comparison after correctness passes. Keep the machine idle during measurement.
One explicit warm-up pair precedes the retained samples; execution order then
alternates between languages. Setup and complete teardown are outside the
timed function and remain subject to separate correctness and allocation checks.

The report retains every measured observation, each language's median CPU time,
and the median of adjacent Minyar/C++ CPU ratios. These two ways of summarizing
ratios can differ when host conditions change, so both remain visible. Ratios
below one favor Minyar. A deterministic 95% percentile bootstrap resamples
complete pairs; its seed, sample count, full range, and method accompany the
interval. The interval assumes independent pairs and cannot account for an
unobserved workload or sustained host drift. It is evidence, not a timing gate
that can be made green by discarding inconvenient samples.

The October final default-build measurements close the earlier arithmetic,
record, and indexed-List CPU gaps on the maintained workloads. The scalar study
adds shifts, Unicode scalar conversion, Float-to-Integer and abs/clamp; the
hardening report retains ratios and confidence intervals.
System-allocation LTO List work still has a measured 1.02% CPU gap and more
retired instructions. Its disassembly identifies memory-effect/alias information
as remaining work; faster default CPU measurements do not establish lower
instruction counts. Preserve this distinction when reporting results.

## Checked collection access

A `for` loop over a List or Bytes reads the length through the same inline
helper on every iteration, so the loop header makes no runtime call. When the
body assigns only plain local names or fields and elements
(`totals[key] += amount`, `row.count = 0`), and its compiled code makes no user
call and calls only runtime operations that cannot release a List slot (Text
operations, Map lookups and stores, record construction, appends), nothing in
it can drop an element: the loop name borrows each element instead of retaining
and releasing it, and a plain variable source that the body does not reassign
needs no extra count of its own. A body that replaces a List element keeps both
counts; one that replaces a record field or Map value keeps the source's count,
because a field or Map may hold a borrowed source such as a parameter. A function whose only owners were those then
needs no ownership frame or loop service points. Summing two fields over a
1,000-element `List<Point>` 100,000 times fell from 0.29 to 0.06 seconds
(checked C with pointers to heap structs: 0.04).

Ordinary Bytes indexing, indexed replacement, length and single-byte `add`
use inline LLVM helpers even when the runtime is a separate native object. An
append takes the inline path only when the value is a byte and the storage
already has room; growth, C-layout views and invalid values call the runtime.
The typed accessors (`getInt16` through `setFloat64`) are inline too: they
check the whole two-, four- or eight-byte range and the value's range first,
then load or store explicit little-endian bytes, so unaligned C-layout views
behave the same. Float32 stores round with an ordinary conversion and Float64
keeps every bit. `make check-typed-byte-access` compares each width against
literal byte patterns at several offsets, with sentinel bytes around each store.
A Bytes method that only reads or updates its own storage, such as
`holder.bytes.add(value)` or `holder.bytes.setInt32(0, value)`, takes no
temporary count on a field or element receiver when its arguments make no
calls: nothing can replace that field before the method returns. The same
holds for `add` on a List whose element type cannot form a cycle, since an
append retains its argument and releases nothing. Removing that
count and its cleanup point lets LLVM keep the surrounding loop in registers;
on the frozen safelibs fixtures it halved zlib decode time (8.10 to 4.21 ms)
and cut PNG by 27% (13.00 to 9.51 ms). Bytes and List
helpers expose their nonnegative length and form checked element addresses
within the backing allocation. These facts do not freeze storage or imply
that two collections are disjoint. A failed check calls the runtime, which
reports the error and never returns, so the helper's slow path ends in
`unreachable`. The reporting call then lies outside every loop, and LLVM can
keep a collection's length and storage pointer in registers across
iterations; on the frozen safelibs fixtures this cut JPEG decode from 32.59 to
21.19 ms and PNG from 9.17 to 7.58 ms. Resizing and other calls retain their
ordinary memory effects; invalid accesses still use the runtime diagnostic.

The call-free Bytes and List length helpers describe their effects as
`memory(argmem: read)`, with noncapturing, non-null headers readable for sixteen
bytes. They do no allocation, synchronization or unwinding and always return.
This describes each read; aliases can still change the next observed length.
Checked accessors expose non-null backing storage only after their bounds check.
Empty Lists may have a null backing pointer, and native Bytes views imply no
backing-allocation size, alignment or disjointness. Trap branches carry source
likelihood hints, with the failing successor unlikely; ordinary append growth
does not. These contracts preserve the existing runtime checks and diagnostics.
`make check-llvm-helper-contracts` verifies the emitted contracts and mutable,
overlapping views at O0/O2 with ownership cleanup; its sanitizer variant also
instruments the compiler and generated memory accesses.

On one Linux x86_64 LLVM 23.1.2 host, seven alternating retained pairs against
the same frozen inputs measured 2,233,443,703 → 2,231,188,537 median user
instructions for arena compiler self-compilation (−0.10%). Whole-process
instructions for the frozen safelibs zlib/PNG/JPEG workers fell by
0.17%/0.47%/0.12%; the three jsmn sizes were unchanged. Compiler file size grew
from 2,040,344 to 2,041,440 bytes; codec and jsmn file sizes stayed unchanged.
Decode CPU timings were mixed, so these narrow instruction reductions do not
establish a general speedup. Compiler output matched after removing exactly
the intended helper-contract differences; decoded bytes and jsmn checksums
matched without normalization.

`make check-bytes-access check-list-access` checks the raw helpers and optimized
loops: a proven traversal removes redundant bounds and index-overflow checks
while retaining checked accumulation. The suites also exercise errors, shared
mutation and ownership at O0/O2. Their `-sanitize` counterparts instrument the
compiler and generated memory accesses.

Record field reads and scalar field writes are inline slot accesses. Every
runtime profile, including the compiler's arena, stores a record as its field
count followed by its fields. The type checker resolves each field to a constant
position below that count and records never resize, so the helpers
(`.minyar.record.get`, `.minyar.record.set.scalar`) read or write the slot with
no length test. Positions below 16 have their own accessor
(`.minyar.record.get.K`) and their own child tag under `minyar record field`, so
a store to one field position cannot force a reload of another; later positions
share the parent tag, which aliases every tagged position. A tagged position is
byte offset 8 + 8K in any record, so the separation holds without type
information. The accessors are chosen where the call is emitted: a shared
helper switching on the field would be simplified before inlining and would
merge the tags. A scalar store written directly through a method receiver
(`self.field = …`) keeps the shared parent tag: every access through one `self`
is already separated by its constant offset, and a per-position tag there let
LLVM promote a receiver counter into a loop-carried value whose register copies
cost more than the reloads it saved (an interpreter dispatch loop measured +7.5%
instructions). This is a measured codegen heuristic, not an aliasing rule.
Reference fields keep their ownership-aware runtime setters.
`make check-record-access` checks the helper IR, its inlining at O2, the absence
of a failure path and the arena layout; `check-llvm-helper-contracts` proves at
O2 that a store to field A keeps a load of field B, while a store to the same
field still reloads it.

A compound Map assignment `m[k] op= v` with an Integer, Text, Float, Boolean,
Character or payload-free choice key and a non-reference value looks the key up
once: `minyar_map_value_slot` reads like `m[k]` (an absent key stops before the
right side runs) and `minyar_map_store_slot` writes through the found slot.
When the right side can run user code, which could grow or clear the Map, the
statement still reads through the slot but stores with `minyar_map_set`. Pending recovery and a
Map read by an active hash or equality method take a scratch slot whose store
runs `minyar_map_set`, so failures and diagnostics are unchanged; Float keys
(NaN and signed-zero rules) also take the scratch slot.
`make check-map-update` runs both paths at O0/O2 and checks the emitted calls.

On the frozen safelibs fixtures (Linux x86_64, LLVM 23.1.2, separate O2 codec
and runtime objects, median of three pinned samples), inline record access
reduced decode time by 22–35%:

| Fixture | Bounded frames before → after | Scope owners before → after |
| --- | ---: | ---: |
| zlib, 1 MiB | 15.61 → 12.25 ms | 12.80 → 8.29 ms |
| PNG, 512×512 | 23.69 → 18.37 ms | 19.39 → 13.27 ms |
| JPEG, 512×512 | 56.28 → 38.93 ms | 51.43 → 35.26 ms |

The left column is the direct compiler's default ownership lowering, which
those products used; the right is `--scope-owners` with the eager runtime.
Libraries and embedders that call `build/minyarc` directly get that legacy
heap-frame lowering unless they pass the launcher's choice: `--scope-owners
--bounded-owners 32` with the default incremental runtime
(`runtime/minyar_default_runtime.c`), or `--scope-owners` with the eager
runtime. (`--bounded-owners 32` alone keeps frames, with stack frames for small
leaves, which needs a runtime that includes `minyar_stack_frames.h`.)
Both remain 18–37 times slower than the system zlib, libpng and libjpeg-turbo.

`experiments/codegen/byte-access-study.py` compares two frozen compilers with
checked C on byte sum, byte copy and Integer List sum. It retains seven
alternating samples after warmup, validates complete storage and ownership,
and reports kernel CPU/wall separately from optional whole-process `perf`
counters. Allocation, warmup, validation and teardown are outside kernel timing.
There is no timing acceptance threshold.

The October 20 Linux x86_64 campaign uses 65,536 elements and 4,096 kernel calls
per sample, LLVM 23.1.2, identical sources and a shared default-runtime object.
With separate O2 objects, median Minyar kernel CPU changes as follows:

| Kernel | Before | After | After / checked C |
| --- | ---: | ---: | ---: |
| Byte sum | 435.99 ms | 63.34 ms | 1.170 |
| Byte copy | 660.51 ms | 96.63 ms | 1.061 |
| Integer List sum | 91.21 ms | 55.37 ms | 1.029 |

With matching ThinLTO, byte sum/copy remain near their existing C controls
(after/C 1.028 and 0.956); List sum falls from 87.82 to 54.62 ms (after/C 0.973).
An initial helper-only variant regressed ThinLTO. Retained ablations identify
the missing nonnegative length fact; the final IR regression checks its effect.
[Raw observations, identities and ablations](../experiments/codegen/collection-access-first.json)
include the unfavorable intermediate measurements. Shared-host timing and these
three small kernels do not establish complete-parser or codec performance.

`experiments/codegen/safelibs-study.py` measures the maintained zlib/PNG/JPEG
fixtures through their existing checked APIs. It uses balanced same-process
baseline/candidate/native batches, retains every order and CPU/wall sample,
and verifies exact baseline/candidate output and live-object cleanup. Those
timings include the existing Python wrapper, copies, allocations and guards;
they must not be substituted for a native decoder-throughput measurement.

## Numeric text and Text search

Float printing and short JSON decimals use integer-only unrounded scaling
(`runtime/minyar_float_scale.h`; see [language](language.md) and
[JSON numbers](json-numbers.md)). On an Apple arm64 laptop, linking the same
program IR against the previous and current runtime, formatting 600,000
Floats fell from 10.33 G to 0.60 G retired instructions, and parsing a
200,000-number JSON array end to end from 1.50 G to 0.66 G, with identical
output.

`find`, `contains`, `split` and `replace` with a needle of 2 to 16 bytes test
sixteen text positions per step against the needle's first and last bytes
(SSE2 on x86-64, NEON on arm64, no CPU dispatch) and compare only the
positions that pass ([Muła](http://0x80.pl/notesen/2016-11-28-simd-strfind.html)).
Each text byte still costs at most sixteen comparisons. Other targets keep the
scalar first-byte scan. On 64 MiB of log-shaped text the search part retired
1.6–4.7 times fewer instructions (2.3–9 times fewer cycles), from frequent
`status=ok` matches to an absent `timeout`. `check-runtime-unit` compares the
search with a naive oracle on small alphabets across the 16-byte steps.

## Compiler profile guidance

On native Linux, `make compiler-pgo` builds an isolated compiler using LLVM IR
profile guidance and compares it with the same compiler built without a profile.
It leaves the ordinary compiler unchanged. The pinned LLVM installation must
include matching `llvm-profdata`, LLD and the compiler-rt profile archive.

Each invocation creates a fresh directory below `build/compiler-pgo`. It retains
the baseline, instrumented trainer, profile-use compiler, raw and merged profiles,
frozen input copies and hashes, tool hashes, exact commands, reference LLVM,
all samples and `results.json`.
The JSON summary gives the candidate path. `make check-compiler-pgo` runs the
same correctness checks with three retained pairs instead of the default 31.
These targets are explicit experiments, outside the portable gate by default.

Training uses self-compilation and three ordinary language/gallery programs.
Timing alternates baseline and candidate processes after three warmups per role.
Self-compilation is a trained workload; the separate holdouts contain 1,200
functions with a late call, 1,000 records and a 64-module import graph. Every
measured invocation must emit identical LLVM, stdout and stderr. Additional
gallery programs and three rejected inputs must agree, and generated holdouts
must execute with independently expected output at O0 and O2. Input and profile
hashes must stay unchanged throughout validation and timing.

Child CPU measurements exclude the Python harness. Wall measurements cover
subprocess startup through exit with stdout/stderr capture; this is a warm-filesystem, fresh-process
comparison on one host. The tool reports the median paired ratios and their
full range. It enforces correctness, not a speed threshold: inspect the retained
samples and holdouts before choosing a compiler. Profile generation and extra
links have a cost, and no result from this experiment changes release defaults.

## Runtime declarations and LLVM optimization

The native Text byte-length, Bytes length and List length declarations describe
leaf reads of their mutable headers: `captures(none)`, `nonnull`, a 16-byte
dereferenceable prefix, `nofree nosync nounwind willreturn`, and
`memory(argmem: read)`. Text equality has the same parameter and leaf contracts
but uses `memory(read)`: it follows backing pointers loaded from the headers.
Restricting equality to argument memory would permit incorrect reuse across a
store to a separate backing allocation. Neither header nor backing storage is
declared invariant or disjoint. Lazy Text character-length/index operations
remain outside these contracts. Explicit failure is `cold noreturn`; ordinary
exit is only `noreturn`, preserving its shutdown effects.

`make check-llvm-runtime-contracts` checks emitted declarations and matching
stage0 strings, declaration-only call merging, and the calls that must remain
across header/backing mutations. It also checks empty and Unicode Text,
equality's small-load and memcmp paths, exact failure/exit behavior, and ownership
cleanup at O0/O2. Its sanitizer counterpart instruments generated accesses and
the native runtime.

A separate Linux x86_64 LLVM 23.1.2 study built both compilers through two
generations, verified byte-identical fixed points per compiler and identical
self-compile output after only the six declaration changes were normalized.
Seven alternating retained pairs after warmup found effectively unchanged
instructions for compiler self-compilation, frozen safelibs codecs and three
jsmn sizes. Compiler file size increased by 472 bytes in that matched study;
product file sizes were unchanged. A labeled synthetic loop comparing the same
Text ten million times fell from 270,441,745 to 50,441,543 instructions after
LLVM hoisted the read. This explains an optimization opportunity and does not
establish a general application speedup.

The compiler and `--release` programs retain O2 with ThinLTO. Clang's current
default pipeline already enables loop and SLP vectorization; adding those flags
again does not remove checked-overflow dependencies. A separately controlled
O3 experiment reduced compiler self-compile instructions by 1.82% while growing
its binary by 4.62%. Codec changes ranged from effectively zero to 0.78% fewer
instructions with 5.93% more library bytes; jsmn was unchanged. These workloads
do not justify changing the default optimization level.

Runtime LLVM must keep the documented stripping of `target-cpu`,
`target-features` and `tune-cpu`, so generic generated callers remain compatible
with runtime inlining. Neither the generated IR nor the stripped runtime
names a CPU, so both compile for the CPU the LTO backend is given. Linux lld
receives Clang's `-march`/`-mcpu` choice itself; Apple's linkers receive none,
and without one the whole program would be compiled for the architecture's
generic CPU (ARMv8.0 on Apple silicon: no LSE atomics, generic scheduling). On
macOS the driver therefore passes `-Wl,-mcpu,CPU`, where CPU is what Clang picks
for C under the same flags (`apple-m1` by default). On the 22 `benchmarks/compare`
programs this cut retired instructions by 1.4% (geometric mean; matrix 25.9%). `make check-release-build` captures the actual temporary
release runtime before cleanup, checks those attributes are absent, and verifies
a generic length wrapper inlines against that captured module. That last probe
tests single-module optimization; release execution separately exercises the
actual ThinLTO link.

One standalone byte-sum prototype illustrates a sound arithmetic pattern for
future loop lowering. Starting at zero, n unsigned bytes have every prefix at
most 255*n. For n <= 16,843,009 = floor(UINT32_MAX/255), an unsigned 32-bit sum
followed by zero-extension gives the exact language Integer result; larger
inputs retain the original checked 64-bit loop. Plain wrapping LLVM addition
needs no speculative no-wrap or alias metadata. On generic x86_64 SSE2, LLVM
23.1.2 vectorized that guarded 32-bit loop at O2/O3; a guarded 64-bit version
was legal but declined by the cost model. An isolated 1 MiB byte ramp summed
128 times retired about 80.3% fewer instructions, with 145 additional function
text bytes. Real boundary and boundary+1 buffers, tails, unaligned input,
empty input and sanitizer checks passed. This prototype is not production
compiler lowering. Adoption also needs live/stable collection storage and
unchanged diagnostic, ownership and effect ordering; the arithmetic proof alone
does not permit hoisting across mutation or reassociating arbitrary signed sums.

The inline List and record helpers carry type-based alias tags in a Minyar
TBAA tree: `minyar list header` (length and values pointer), `minyar list slot`
and `minyar record field`. A List slot or record field store therefore keeps an
already loaded List length or values pointer valid, and LLVM can keep them in
registers or hoist them. The tags state only that these are different objects:
every other access, Bytes (which may be shifted native views) and the runtime's
C accesses stay outside the tree, and LLVM treats accesses from different trees
as possibly aliasing. `make check-llvm-helper-contracts` checks the tags and that
O2 reuses a List length across a field or slot store but not across a Bytes store.

A parallel function cannot resize a buffer and its caller waits for it, so in
one that contains a loop the compiler loads each List parameter's length and
values pointer once at entry and indexes through them
(`.minyar.list.get.known`/`.set.scalar.known`); a failing index still reports
through the List. An index `base + c` or `base - c` with a constant c of at
most nine digits, used by nothing else, is summed inside the bounds test
(`.known.offset`): any overflowing sum lands outside every List (lengths stay
below 2^61), and the failure path tests the overflow again, so the same error
is reported. Appending to a List of scalars stores in place while the length is
below the capacity (`.minyar.list.add.scalar`); a full List, a view and every
reference element type take the runtime append. `make check-list-access` and
`make check-llvm-helper-contracts` check the helpers, the rewrites and every
failure path at O0/O2. On one Linux x86-64 host (cachegrind Ir, outputs
identical) they cut topk by 14.0%, textindex by 4.8%, forkjoin by 4.2% and sort
by 3.3% in `benchmarks/bothmodes` at one and four threads, and grid by 5.6% and
par-forkjoin by 4.5% in `benchmarks/compare`; no program grew by more than 0.2%.
Broader tag ranges, noalias and explicit noundef contracts remain deferred.
Native scalar boundaries, nullable choice niches, shared native views and
partially initialized payloads require more precise proofs; explicit noundef
also needs matching ABI treatment at call sites for MemorySanitizer. Existing
nonnegative length ranges and successful-block backing `!nonnull` metadata
retain their narrow scope.
