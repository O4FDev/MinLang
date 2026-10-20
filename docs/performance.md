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

## Absolute compiler budget

`check-budget` enforces 75 million retired instructions and 17 MiB peak memory,
plus matched previous/current wall and CPU comparisons over three batches of
100 alternating pairs. The paired median must be at most 1.01 and the upper
95% confidence bound at most 1.05. These limits are defined in
[`tests/performance-support.min`](../tests/performance-support.min).
Real resource qualification requires the owner macOS CI and matched inputs;
Linux can run `./build/tooling/tests/self-compile-budget --functional`.
The separate `check-performance` self-compile limits are 20 seconds wall,
2 seconds CPU and 64 MiB. These remain regression targets, not a statement
that the current, larger compiler passes.

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
priority changes absolute timings. It takes the 90th percentile across batches;
shared-host load can still affect results. Most other checks run under
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
body makes no calls and assigns only plain local names, nothing in it can
change the collection: the loop name borrows each element instead of retaining
and releasing it, and a plain variable source that the body does not reassign
needs no extra count of its own. A function whose only owners were those then
needs no ownership frame or loop service points. Summing two fields over a
1,000-element `List<Point>` 100,000 times fell from 0.29 to 0.06 seconds
(checked C with pointers to heap structs: 0.04).

Ordinary Bytes indexing, indexed replacement, length and single-byte `add`
use inline LLVM helpers even when the runtime is a separate native object. An
append takes the inline path only when the value is a byte and the storage
already has room; growth, C-layout views and invalid values call the runtime.
`getInt32`, `getUInt32`, `setInt32` and `setUInt32` are inline too: they check
the whole four-byte range and the value's range first, then load or store four
explicit little-endian bytes, so unaligned C-layout views behave the same.
`make check-typed-byte-access` compares them against literal byte patterns at
every offset, with sentinel bytes around each store.
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

`make check-bytes-access check-list-access` checks the raw helpers and optimized
loops: a proven traversal removes redundant bounds and index-overflow checks
while retaining checked accumulation. The suites also exercise errors, shared
mutation and ownership at O0/O2. Their `-sanitize` counterparts instrument the
compiler and generated memory accesses.

Record field reads and scalar field writes use the same pattern. Every runtime
profile, including the compiler's arena, stores a record as its field count
followed by its fields, so the helper loads the count, checks the constant
field index against it and reads or writes the slot directly. A failed check
calls the runtime's diagnostic. Reference fields keep their ownership-aware
runtime setters. `make check-record-access` checks the helper IR, its inlining at
O2 and the arena layout.

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
heap-frame lowering unless they pass the launcher's choice: `--bounded-owners
32` with a runtime that includes `minyar_stack_frames.h` (as
`runtime/minyar_default_runtime.c` does), or `--scope-owners` with the eager
runtime.
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
