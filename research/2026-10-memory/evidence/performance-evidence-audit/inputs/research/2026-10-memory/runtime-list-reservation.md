# Known-length List reservation experiment

Selected raw results, source diffs and hashes survive `make clean` in the
[durable runtime index](evidence/runtime/index.json); original acquisition paths
remain recorded there.

## Question and scope

Does planning an appended List's existing geometric capacity before allocating
storage reduce allocator activity without changing contents, aliases, ownership,
capacity policy or cleanup bounds? This is ordinary preallocation, not a claim of
a new memory-management algorithm. The existing compiler and language syntax
remain unchanged. The workspace already contained substantial uncommitted work;
the original runtime was snapshotted before this experiment and no commits or
resets were performed.

`minyar_list_appended` formerly grew an empty destination repeatedly, then copied
the source elements. `runtime/minyar_collections.h` now computes the same final
capacity and reserves one backing buffer when no retirement is pending after
creating the result header. If debt remains, it keeps the original intermediate
growth and cleanup schedule. Ordinary append growth computes one next capacity
and uses the shared resize body directly.

## Red, change and controls

The first regression failed at source length 2: one header allocation, one backing
allocation and one unnecessary realloc. The snapshot replay also fails there:

```sh
python3 tests/memory-research-list-reserve.py \
  --runtime-dir build/memory-research-runtime-baseline/minyar-memory-profiles-1msa1ju5/originals/runtime \
  --mode native --output-dir build/memory-research-list-reserve-red-evidence
```

Retained red evidence:
[run-vb29a14s/results.json](evidence/runtime/results/allocation-red.json).
This is an expected assertion failure, not a successful correctness run.

The fixture counts actual libc malloc/realloc calls independently of runtime
work counters. It checks 11 scalar lengths, a separately written capacity model,
every copied scalar, the unchanged source, 257 shared reference members, retained
and transferred appended owners, and exact post-drain object/byte recovery.
The arena fixture measures actual bump-arena retained bytes. Overflow and injected
first/second allocation failures retain existing diagnostics. Fixed/lazy pool OOM
cases reserve beyond the finite capacity and fail through the ordinary path.

| Source length | Original realloc calls | Changed realloc calls |
| --- | ---: | ---: |
| 0, 1 | 0 | 0 |
| 2, 3 | 1 | 0 |
| 15 | 3 | 0 |
| 31 | 4 | 0 |
| 1023 | 9 | 0 |
| 1024 | 10 | 0 |
| 4095 | 11 | 0 |
| 4096, 8193 | 12 | 0 |

Both versions perform two malloc calls for an appended scalar List: header and
initial/final buffer. The original incremental allocator has one cleanup-service
opportunity per reallocation in addition to the two allocation opportunities;
the changed version has only those two allocation opportunities. These idle
counting cases have no pending debt and execute **zero actual cleanup units**.
Fewer opportunities must not be described as a measured reduction in cleanup
work. Reference copying still uses the existing reference-appending service.

For an arena source of 1024 entries, retained List-storage bytes per append fall
from 24,576 to 16,384. Original tiny growth extends storage in place; crossing from
the small List arena into the large List arena strands the old 8,192-byte buffer.
One reservation avoids that buffer. This excludes object headers and arena block
reservation overhead.

Original count evidence (bounds deliberately disabled, semantics still checked):
[run-ruw3uli7/results.json](evidence/runtime/results/original-counts.json).

## Correctness checks

```sh
python3 tests/memory-research-list-reserve.py --mode all
```

Unconditional candidate evidence (superseded by the debt guard below):
[run-lml85q04/results.json](evidence/runtime/results/historical-list-matrix.json):
24 C configuration runs, 21 generated-language executable runs and 17 expected
overflow/OOM diagnostic checks pass. Profiles: eager, system, fixed, lazy and
compiler arena; O0, O2 and ASan+UBSan; incremental budgets 1 and 32. Pool size is
8 MiB to keep fixed startup modest. Each run snapshots all runtime fragments,
fixtures and generated LLVM, with source SHA-256 values and exact commands.

`tests/memory-research-list-reserve.min` builds and shares a 1024-entry scalar List,
repeatedly returns fresh appended Lists through a borrowed parameter, and checks
that the original alias retains its length and contents. It also appends a fresh
Quote to a 257-entry record-reference List, clears the source local and verifies
both surviving aliases. Its sums and outputs are independently calculated.
The compiler executable's SHA-256 is recorded; compiler sources were not changed
by this lane.

Existing checks also pass:

```sh
clang -std=c11 -O2 -Wall -Wextra -Werror tests/runtime-unit.c -o build/memory-research-runtime-unit
build/memory-research-runtime-unit
clang -std=c11 -O1 -g -fsanitize=address,undefined tests/runtime-unit.c -o build/memory-research-runtime-unit-sanitize
ASAN_OPTIONS=detect_leaks=0:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 build/memory-research-runtime-unit-sanitize
clang -std=c11 -O2 -DMINYAR_SYSTEM_HEAP=1 -c runtime/minyar_runtime.c -o build/memory-research-runtime-system.o
MINYAR_TEST_RUNTIME=build/memory-research-runtime-system.o python3 tests/recursive-data.py
```

The last command runs 16 existing recursive-data tests, including fresh appended
recursive children, at O0 and O2. LeakSanitizer is disabled following the existing
repository sanitizer configuration; ASan and UBSan are enabled. Exact C ownership
accounting complements that exclusion, but it does not establish whole-program
leak freedom. This is a focused campaign, not a claim that all tests passed.

Initial unchanged-runtime fairness/service baseline: 9 native K32 checks across
system/fixed/lazy for recent-cursors, recent-fairness and idle-service.
Evidence: [minyar-memory-profiles-1msa1ju5/results.json](evidence/runtime/results/baseline.json).

## Paired performance and rejected first design

Host: Apple M1 Pro, 16 GiB, macOS. Exact platform and compiler version are in the
JSON artifacts. These C fixtures include the runtime in one translation unit.
Timings measure the loop with process CPU and monotonic clocks, excluding startup
and source preparation. Copying is included. Two warmups precede 12 adjacent
pairs per case, with deterministic randomized order. All observations are retained.
Intervals use 10,000 deterministic bootstrap resamples of paired-ratio medians
and assume independent observed pairs; they do not model OS jitter or unseen
workloads. The baseline is the pre-change snapshot, not git HEAD.

```sh
python3 tests/memory-research-list-reserve-bench.py \
  --before-runtime build/memory-research-runtime-baseline/minyar-memory-profiles-1msa1ju5/originals/runtime \
  --pairs 12
```

| Case | System CPU original/changed (95% interval) | Fixed CPU original/changed (95% interval) |
| --- | ---: | ---: |
| Append length 31 | 2.293 (2.271–2.350) | 1.497 (1.471–1.519) |
| Append length 1024 | 1.334 (1.318–1.348) | 1.141 (1.135–1.152) |
| Append length 8193 | 1.100 (1.092–1.112) | 1.191 (1.156–1.205) |
| Ordinary growth length 31 | 1.001 (0.958–1.029) | 0.984 (0.974–0.993) |

Ratios above one favor the changed implementation. Ordinary fixed growth has a
residual measured ~1.6% slowdown in this experiment. Its optimized LLVM growth
body differs only by equivalent comparison operand reversal and attribute IDs;
the measurement cannot identify a cause, and is not evidence of zero regression.
Code layout and single-TU compiler decisions remain candidate explanations.
Separate generated-language timing and further controls are needed.

Unconditional candidate paired evidence: [run-131w4uv4/results.json](evidence/runtime/results/unconditional-list-timing.json).
The final debt guard adds one pending-count branch. Its matched revalidation
appears below; the earlier table remains the unconditional design's evidence.
The first design routed ordinary growth through the capacity-planning loop too;
its growth controls regressed ~4.6% system/~5.6% fixed. That unsuccessful design
was corrected before acceptance. Its snapshots and observations remain in
[run-orc9795b/results.json](evidence/runtime/results/rejected-growth-design.json).

Final guarded paired evidence:
[run-9t0lgm8s/results.json](evidence/runtime/results/final-list-timing.json).
The same command ran with an exclusive project timing reservation, normal QoS,
CPU/output/memory limits and nice 15. External host activity remained possible.
All twelve pairs per case and both warmups are preserved, with runtime hashes;
the measured collection fragment is SHA256
`01ae1e88dbcd98a9f8815a7a8e0508247a19f7f0b912d938544db129191eb4c0`.

| Case | System CPU original/guarded (95% interval) | Fixed CPU original/guarded (95% interval) |
| --- | ---: | ---: |
| Append length 31 | 2.297 (2.268–2.335) | 1.517 (1.509–1.529) |
| Append length 1024 | 1.332 (1.323–1.344) | 1.131 (1.118–1.148) |
| Append length 8193 | 1.105 (1.094–1.112) | 1.183 (1.167–1.187) |
| Ordinary growth length 31 | 1.007 (0.987–1.030) | 0.984 (0.972–0.999) |

Measured baseline process CPU per batch ranged roughly 20–67 ms. The no-debt
append improvement persists with the guard, while ordinary fixed growth again
shows about 1.6% higher CPU. This is a workload tradeoff, not a claim that every
List operation became faster. Requested capacities and allocation-count evidence
are separate from these C loop timings. Generated List programs have correctness
coverage; they have not yet established the same timing ratios. Pending-debt
append uses the original growth schedule and is outside the fast-path speed claim.

![Guarded List timing ratios including ordinary growth controls](runtime-list-timing.svg)

The SVG has PDF and high-resolution PNG exports. `runtime-timing-figures.json`
records the source evidence and export hashes; all pair ratios are displayed.

## Review-discovered allocation admission regression and correction

Independent review proposed a decisive adversary: intermediate growth services
debt before requesting the final block. Removing that work can make a tight pool
fail even when the original append succeeds. This was reproduced before adding
the correction, at both K1 and K32.

`tests/memory-research-list-debt-pressure.c` fills a 64 KiB pool with 32-byte
blocks, then leaves one separate result-header slot and an output-sized region.
The region's lower portion is free; a queued reference-map record occupies an
upper buddy. Its fields are null, so it needs field visits plus finalization to
release that buddy. The old result's small backing can grow in the lower region
while its realloc calls retire the blocking record.

| Budget | Queued fields | Initial pool bytes | Final block | Original | Unconditional reserve |
| --- | ---: | ---: | ---: | --- | --- |
| 1 | 2 | 63,520 | 2,048 | Success/recovery | OOM |
| 32 | 64 | 58,336 | 8,192 | Success/recovery | OOM |

The corrected implementation tests `rc_pending_count` **after** result-header
allocation and its service. Nonzero chooses the unchanged original growth loop.
Zero chooses one reservation: the capacity planner creates no new debt, so every
omitted allocation service would have been idle. The pending count includes the
active/captured/recent object queues, detached frames and temporary chunks.
This argument assumes the existing single-mutator runtime with no user finalizers;
it is not a concurrency claim. Eager and compiler-arena profiles keep reservation.

The independent review reproduced the same boundary and the guard's recovery:
`build/run-bddgj2v4/literature-reserve-debt-review.json`.
The complete fixed/lazy native+ASan/UBSan before/unconditional/guarded matrix is
tracked by `tests/memory-research-list-debt-pressure.py`; expected OOM cases are
retained as negative evidence. The focused List fixture also checks that pending
system-heap debt keeps the old four realloc calls, rather than only testing pools.

The optimization's allocation reduction is therefore scoped to the no-debt path.
This correction is required for acceptance; unconditional reservation is rejected
despite its favorable idle timing measurements.

Guarded validation under the repository background limiter overlapped the full
integration suite and hit 60-second wall timeouts: `run-044tzqz2` stopped while
compiling system O2, and debt `run-19ym4579` stopped on the original K32 sanitizer
binary. Completed prefix checks passed; there was no recorded assertion or
sanitizer failure. These incomplete runs establish no final matrix conclusion.
They remain preserved under their respective `build/memory-research-*` parents.
Parent orchestration requested exclusive compilation for the integration suite;
the deferred experiment alone was interrupted and further compilation paused.
At that checkpoint, complete matrices and matched benchmarks awaited the next
exclusive window. Evidence writes now replace JSON atomically, and future
generated tests copy the compiler artifact to avoid concurrent build replacement.

The final guarded focused matrix subsequently passed in the temporary exclusive
correctness gap with normal QoS, retaining CPU/output/memory limits and nice 15.
Evidence: [run-9ekj44fd/results.json](evidence/runtime/results/historical-guarded-matrix.json) (109 checks:
24 C configurations, 21 generated executable runs, 17 expected diagnostics plus
their builds and compiler-version checks). Approximate duration from evidence
directory creation to final JSON: 29.24 seconds. The additional ownership controls
cover empty reference Lists, all-immortal/null members and an appended tail that
aliases an existing source member, for both retain and transfer forms. Incremental
system-heap debt verifies the old four realloc service opportunities remain.
The compiler executable is copied and retained in this artifact directory.
The earlier timeout results remain historical failed attempts.

After the integration suite released its reservation, the complete fixed/lazy
K1/K32 native+ASan/UBSan debt differential passed all 24 variant executions:
[run-mmxhx7t9/results.json](evidence/runtime/results/list-object-debt.json).
Original and guarded variants succeed and reclaim the entire pool; the rejected
unconditional variant fails with the expected OOM in all eight pressure cases.

The focused List matrix then passed again on the final runtime after the separate
Unicode correctness repair:
[run-tja7d6bv/results.json](evidence/runtime/results/list-sanitizer-matrix.json) (109 checks,
24 C configurations, 21 generated executions, 17 expected diagnostics).
This rerun corrects a sanitizer harness gap: earlier generated ASan links
instrumented the C runtime but did not add `sanitize_address` to generated LLVM
function definitions. The current runner copies and annotates generated IR with
the existing `llvm_sanitizer` helper. Native IR is unchanged. Earlier C fixture
sanitizer coverage remains valid, but earlier artifacts do not establish
instrumented generated-function coverage. UBSan covers C runtime operations,
not every generated arithmetic instruction. LeakSanitizer remains disabled.
The deferred-owner matrices also completed; their distinct positive isolated
and negative generated findings are in `runtime-deferred-reuse.md`.

## Frame and temporary-owner debt regression

Independent mutation review found a coverage gap: replacing the guard with an
object-queue-only test survived the original blocking-record fixture. That test
contained object debt, so it could not distinguish the full pending count from
active/recent/captured object queues alone. This was a surviving mutant, not a
detected production defect.

`tests/memory-research-list-owner-debt.c` adds separate frame and temporary-chunk
controls. Each has `2K+2` pending owner slots, with the last visited slot owning a
scalar record that blocks an upper buddy of the final output region. No object
task is queued at entry or after the result-header and next-allocation service
windows. Private detach helpers pin this state without the automatic leave/step
poll; ordinary append construction then supplies its normal service calls. The
full guard keeps geometric growth, visits the blocking owner before its large
resize, and recovers the entire pool. The object-only guard attempts direct final
reservation and fails with the expected OOM.

The final differential passed 24 checks: eight builds and sixteen frame/chunk
executions across K1/K32 and native/ASan+UBSan:
[run-vkrj6rvc/results.json](evidence/runtime/results/list-owner-debt.json).
Both correct executions succeed in every configuration; both mutant executions
fail as specified. Ownership-transfer counts and calibration received independent
static review. The first fixture attempt, `run-_cz_08lm`, is retained: its mixed
record required extra scan work and even the correct guard failed. That invalid
positive control prompted the scalar-record calibration; it is not evidence of a
runtime regression. Peer CI integration adds a small K1/O2 frame/chunk smoke;
the full mutant/profile matrix remains a research opt-in.

## Limits and next questions

Copying remains linear in List length. Reference member retain operations remain
linear too. Ordinary finite-pool allocation can fail through fragmentation and
pending debt. The optimization provides no wall-clock latency bound, reservation
guarantee or HFT suitability claim. No-debt reservation removes idle cleanup
opportunities; pending-debt construction retains the original schedule. Existing
per-call cleanup caps and explicit service-point liveness remain the contract.
The object, frame and temporary-chunk pressure controls cover distinct pending
task kinds. The guard preserves cleanup-service opportunities under debt; it does
not prove identical allocator placement or universal later admission on the
queue-empty path. A [separate bounded buddy-placement differential](runtime-list-fragmentation.md)
found no difference in 15,653 admitted appends from 16,384 source-hashed histories,
with its tested classes and follow-on requests stated explicitly. Other
fragmentation and cache histories remain additional hypotheses.

The next separate hypothesis is whether logically retired frame/container owners
keep a Text's physical count above one long enough to defeat safe consuming-join
reuse. Test eager versus K1/K8/K32, live-alias and self-join controls, pending/live
bytes and budget progress before proposing a mechanism. Prior deferred reference
counting and frame-limited reuse prevent broad novelty claims for that idea.
