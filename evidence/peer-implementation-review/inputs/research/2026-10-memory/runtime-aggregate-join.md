# Aggregate Text join: compiler call-pattern projection

The unchanged runtime gives a fresh aggregate `joinText` result unknown character metadata, even when every fragment is already certified ASCII. In the original escaped-literal assembly projection, this causes one cold scan of the 15-byte ASCII result; the warm query needs no scan. This is a count-based opportunity, not a demonstrated compiler speedup or production policy change.

The projection follows the fragment-building pattern in `compiler/compiler.min:280–338`, preserving source ownership and an alias while allocating fragments. It does not execute the full compiler, lexer diagnostics, source mapping, or generated-code assembly. The program's independent Python oracle decodes escapes and checks exact output, UTF-8 byte length, scalar length/sum and the surviving source alias after a consuming append.

The final baseline [raw results](evidence/runtime-aggregate/run-norhhoed/results.json) passed 18 generated executions: six controls in ordinary system/K32 O2, compiler-arena O2, and system/K32 with C ASan+UBSan and generated ASan O1. All 13 generated definitions carry ASan attributes. Leak detection is disabled; generated UBSan instrumentation is not claimed. [Verified source archive](evidence/runtime-aggregate/run-norhhoed/archive-index.json) retains pristine and instrumented sources, local instrumentation patches, compiler hash and exact argv; reproduction still requires the matching compiler and installed toolchain.

| Control | Fragments | UTF-8 result bytes | Uncertified fragments, ordinary / arena | Cold index builds | Warm builds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Known ASCII | 5 | 15 | 0 / 0 | 1 | 0 |
| Unicode, accent and nonBMP | 5 | 12 | 3 / 4 | 1 | 0 |
| Unknown ASCII read from a file | 6 | 19 | 1 / 1 | 1 | 0 |
| ASCII without querying characters | 5 | 15 | 0 / 0 | 0 | 0 |
| Empty | 0 | 0 | 0 / 0 | 1, zero-byte input | 0 |
| Single ASCII fragment | 1 | 3 | 0 / 0 | 1 | 0 |

Each outer aggregate join makes one object payload request and one data request of result byte length plus one, visits every fragment once for sizing and once for copying, and copies exactly the result's UTF-8 bytes. Its ordinary statement phase includes three cleanup hooks offering 96 queued-work units and doing zero actual queued work. Arena ownership hooks are absent. Unicode's cold query additionally requests a lazy index allocation; ASCII's cold scan allocates no index. These phase counts include compiler ownership operations and are not isolated public-function costs.

The arena leaves the ASCII tail sliced from an indexed Unicode source conservatively uncertified; the ordinary path knows that slice's scalar count. A proposed propagation rule must preserve that proof-state difference. Unknown ASCII is read from a file before the measured phases, so a prospective optimization of an inner join cannot accidentally certify the negative control. Empty certified inputs permit a vacuous ASCII certificate; malformed unknown input must still be validated lazily.

Every ordinary run recovered exact object count, requested bytes and tracked heap allocations to zero after the explicit final drain and frame-cache disposal. Arena process-lifetime used bytes are reported separately (218–642 bytes in these controls), without a managed-recovery claim. Payload request sizes exclude reference-count headers and allocator rounding. Index input sizes are scanner inputs, not instructions, CPU time or latency.

Two retained intermediate failures are harness calibration, not runtime defects: [run-98uj_4mm](evidence/runtime-aggregate/run-98uj_4mm/results.json) expected a removed inner aggregate call; [run-hryz8782](evidence/runtime-aggregate/run-hryz8782/results.json) assumed the ordinary Unicode slice certificate count also applied to arena slices. The final assertions distinguish both behaviors. Earlier exploratory controls used an inner aggregate result as the unknown child; they are superseded by the persistent file-input control and are not the final baseline record.

Reproduce the final baseline with `python3 tests/memory-research-aggregate-join.py`. Source propagation, if tested, remains an isolated snapshot experiment: check the already available certificate during the existing sizing pass, preserve byte copying/allocation/service order, and invalidate metadata whenever any fragment remains uncertified. No-query inputs would pay one added certificate predicate per fragment without receiving a scan benefit; count evidence alone cannot establish their CPU cost.

## Isolated propagation result

The [explicit count requirement](evidence/runtime-aggregate/run-0e5yjkpm/results.json) failed on the unchanged baseline after its output oracle passed: a certified ASCII aggregate still performs one cold scan. This is an avoidable-work regression criterion, not a preexisting semantic bug. The [complete instrumented baseline](evidence/runtime-aggregate/run-soga_9x2/results.json) and [isolated candidate](evidence/runtime-aggregate/run-i0thmm8l/results.json) each passed 18 generated controls plus six successful native debt controls and two expected malformed-input traps. Production sources remain unchanged. The [candidate patch](evidence/runtime-aggregate/run-i0thmm8l/candidate.patch) adds only an automatic boolean in the sizing loop and a conditional character-count initializer.

Known ASCII, empty and single-fragment cold queries now build no index; Unicode and persistent unknown ASCII still build once. Warm and no-query paths remain at zero builds. These older paired phases have identical ordered object/data requests, byte-copy and helper-mediated cleanup events, payload request sizes, hook offerings and helper-mediated work counts. The all-poll refinement below separately records direct public polls. The known five-piece ASCII case replaces a 15-byte cold scan with five certificate predicates; the six-piece unknown control adds six predicates and still scans 19 bytes. The no-query case adds five predicates without avoiding work later. This count-only stage did not establish a CPU effect; the subsequent paired observations retain both benefits and small slowdowns. The candidate remains isolated rather than an accepted production change.

Native controls call the public aggregate join after a deterministic private retirement boundary creates object, frame or temporary-chunk debt. The result has exact `aa` bytes/scalars and the expected metadata, and recovers all ordinary heap/object state. Both variants preserve the two K32 allocation hooks, offering and executing 64 queued-work units. Object/frame pending task counts stay 1 across those hooks; chunk task counts follow 13→10→6. This cardinality is not remaining work or retained bytes. The tests do not infer global service/admission equivalence from only the empty-queue generated traces.

Malformed `0xff` input stays uncertified and traps only when queried, with exit 1 and the original invalid-UTF8 diagnostic in both native and sanitizer runs. Expected process termination excludes quiescent recovery for those trap cases. Two additional intermediate failures are retained: [run-750f9ssl](evidence/runtime-aggregate/run-750f9ssl/results.json) used a nonexistent fixture helper name, and [run-ywn3kjkv](evidence/runtime-aggregate/run-ywn3kjkv/results.json) incorrectly applied normal-exit recovery assertions from its destructor to an expected error exit. Neither was a runtime defect; the corrected fixture preserves the diagnostic and reports recovery only for successful calls.

Reproduce with the baseline command above, followed by `python3 tests/memory-research-aggregate-join.py --candidate --require-certified --compare-baseline PATH_TO_BASELINE_RESULTS`. The archive preserves exact pristine sources, local candidate/instrumentation patches and final instrumented sources. Compiler hash and toolchain are external prerequisites; no whole-compiler timing, final full-suite pass, novelty or hard-latency claim follows from this small experiment.

## Paired CPU observations, candidate still test-only

The [preregistered job](runtime-aggregate-timing-preregister.json) and
[durable result](evidence/runtime-aggregate-timing/run-rrkuiyad/results.json)
preserve all 60 CPU/wall pairs from 12 seeded randomized blocks, five baseline
calibration runs and ten warmups. Counters and sanitizers are disabled. A single
O2 generated program links with pristine versus candidate system/K32 runtime
snapshots; before/after binary, compiler and source hashes match. The independent
oracle checks the final joined bytes, scalar or byte totals and an alias value
equality line. The separate semantic/count fixture checks source bytes and
consuming-alias safety; timing equality alone does not establish those properties. This repeated-join workload builds immutable lexer-like fragments
before the loop, so its loop costs are not full lexing or compiler performance.
Clocks run from a C constructor to its reporting destructor: program setup,
loop, output and compiler-inserted cleanup hooks are included, while dynamic
loader startup, OS process teardown and a separate quiescent drain are not.
The correctness/count fixtures establish quiescent recovery separately.

The [ratio figure](runtime-aggregate-timing.svg), with PDF/PNG exports and
[plot provenance](runtime-aggregate-figure.json), shows every retained CPU pair
and the interval, including an enlarged view of all controls.

| Mode | Loops per execution | Baseline/candidate CPU ratio | 95% paired bootstrap interval |
| --- | ---: | ---: | ---: |
| Certified ASCII, 4,096-byte result queried | 590,627 | 2.4808 | 2.4644–2.4982 |
| Certified short ASCII, 15-byte result queried | 1,000,000 | 1.0865 | 1.0811–1.0919 |
| Persistent unknown ASCII, 4,096-byte result queried | 576,495 | 0.9893 | 0.9822–0.9960 |
| Mixed accent/nonBMP Unicode, 4,096-byte result queried | 24,453 | 1.0021 | 0.9994–1.0049 |
| Certified ASCII, 4,096-byte result without character query | 1,000,000 | 0.9953 | 0.9895–0.9994 |

Ratios above one favor the candidate. The unknown-input slowdown is about 1.1%
and the no-query slowdown about 0.5%; both are retained. Their intervals stay
below the respective preregistered 5% and 3% slowdown-rejection thresholds.
Unicode's interval includes parity. The known-large positive threshold (>3%
benefit with the interval excluding no effect) is met. These limited observations
support the declared workload tradeoff; they do not prove a universal benefit.
Independent review and both sustained frozen-source cohorts remain adoption
prerequisites; no production change is authorized by this report.

The loop-count pilot targets 0.15–0.30 CPU seconds. Short and no-query modes hit
the preregistered one-million-loop cap, yielding mean baseline CPU times about
0.071 and 0.123 seconds, respectively. Their shorter observations have less
timing resolution than planned; no rows were excluded or repeated to obtain
the desired result. The other baseline means are approximately 0.178–0.193 CPU
seconds. Intervals resample the 12 paired log ratios 10,000 times with a fixed
seed; their narrowness does not establish robustness across hosts, workloads,
compilers or sample sizes.

The paced core soak remained active and external host load was high (load1
approximately 10.0 at start and 9.3 at finish). Native/application jobs were
deliberately idle for these pairs. CPU is the primary observation; wall ratios
and user/system CPU are retained separately. This is not a quiet-host experiment
or an operation wall-latency bound. The
[archive index](evidence/runtime-aggregate-timing/run-rrkuiyad/archive-index.json)
preserves exact inputs, code, raw rows and resource enforcement clarification:
the outer wrapper imposed CPU240s/output256MiB/taskpolicy768MiB/nice15 and the
runner enforced a 30-second subprocess timeout. The preregistration's separate
60-second child CPU limit was not installed; all children completed far below
30 seconds. That enforcement-description error is preserved separately from
the unchanged performance thresholds and passing observations.

## Poll-observer coverage correction

The original event observer recorded `rc_service_pending` helper calls and their
nested poll work. It did not record direct public `minyar_rc_poll` calls, such as
those from `rc_step`. Consequently older fields named `actual_queued_units`
mean helper-mediated queued work, not total queued work in every generated
phase. The raw older records remain unchanged. The two native allocation-hook
controls still execute exactly 64 units; this correction does not weaken their
isolated comparison or change the timing data.

The [refined baseline](evidence/runtime-aggregate/run-ltiaucr9/results.json) and
[refined candidate](evidence/runtime-aggregate/run-z4ozpuwj/results.json) rerun
only the same 18 generated and eight native controls each. Both pass. Their
new [all-poll observer patch](evidence/runtime-aggregate/run-z4ozpuwj/poll-instrumentation.patch)
records every actual public poll's clamped budget, pre/post task count and returned
work as event kind5, separately from helper event kind4. All complete event
arrays and helper/poll count fields match between variants. Nested poll work
is never added twice: `all_poll_work` is the sum of public poll returns, while
the older helper field is a subset, not an additional quantity.

In ordinary system/K32 known-ASCII fragment construction, nine helper calls
offer 288 units and do zero work, but 17 public polls offer 544 units and perform
two units. The outer join statement has three idle helper calls offering 96
units and invokes no public polls. Its cold/warm iteration phases each call 15
public polls offering 480 units and doing zero work. Alias/drop cleanup performs
six helper-mediated/public-poll units. Arena ownership hooks and polls remain
absent. These are lexical phase observations, including caller cleanup, and
are not isolated function costs or a sum of compound operation allowances.
The direct-work gap illustrates why zero helper work cannot be promoted to zero
total reclamation work. No production source or timing binary changed.

## Independent performance reanalysis

The [completed audit](performance-evidence-audit.md) reproduces all saved paired
estimates without new measurements and finds no performance acceptance blocker.
The primary Text CPU value is the process clock, rather than the exact sum of
separately sampled user/system fields or a pure loop cost. Its known-ASCII
benefit remains strong under alternative estimators. The no-query geometric
point slowdown remains about 0.5%, while its median interval crosses parity;
the worst retained pair costs about 3.1% more candidate CPU. Pointwise intervals
from one loaded host session do not establish a tail or population guarantee.
The source-frozen system cohort and focused final-source checks are still
required before adoption; this documentation reconciliation changes no source.
