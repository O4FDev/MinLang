# Campaign findings — IN PROGRESS

The campaign has produced bounded correctness repairs, measured allocation and
scan reductions, and useful counterexamples to tempting memory policies. It has
**not** established exhaustive runtime profiling, a novel general collector,
hard latency bounds, or suitability for high-frequency trading. This draft is
awaiting final-source endurance and independent joint-source/coordinator review. Both earlier two-hour cohorts and the focused combined-source gates have passed. The requested seven-hour campaign cannot finish
before **2026-10-04 06:54:29 UTC**.

## Engineering outcomes

| Accepted outcome | Evidence and practical limit |
| --- | --- |
| Unicode consuming Text joins preserve Character and slice semantics after discarding old indexes. | The original joined length could be numerically correct while access returned UTF-8 bytes as Characters. [Native/generated reds and final profiles](runtime-unicode-join.md) cover owning, alias, view, self and malformed-input controls. |
| Known-size List append reserves its unchanged final capacity when no cleanup task remains after header creation. | [Allocation and ownership controls](runtime-list-reservation.md) remove up to twelve intermediate reallocations in selected sizes; object, frame and temporary-chunk debt preserve the old growth/service schedule. This is ordinary preallocation. |
| Borrowed-copy joins preserve already-certified ASCII metadata. | [Metadata, safety and paired evidence](runtime-ascii-metadata.md) removes redundant cold scans without added allocation/service hooks. Unknown and Unicode operands remain conservative. |
| Compiler reachability and bootstrap scheduling received scoped repairs. | [Reachability/bootstrap records](profiling-reachability-bootstrap.json) and [cold-launcher validation](profiling-cold-bootstrap-final-evidence.json) retain their own source identities and checks. They are not proof of a final broad integration pass. |
| Craft repeated torch writes, mesh-slot searches and PNG error/size handling received separate repairs. | [Application provenance and controls](native-application-report.txt) and [final PNG size/cast validation](native-application-round4-report.md) separate actual application computations, native errors, allocation observations and later tiny real-graphics evidence. |

The [core patch inventory](runtime-core-patch-inventory.md) reconstructs only our
changes against the **dirty campaign-entry bytes**. Preexisting ownership,
allocator, numeric, Bytes and compiler work is not attributed to this campaign.
Native/application changes have separate entry/own-diff provenance. No commits
or resets were performed; the language gained no new memory-management syntax.

The [independent performance audit](performance-evidence-audit.md) reproduces
saved ratios and retains all adverse rows. The aggregate candidate's known
4096-byte, five-fragment system/K32/O2 workload measured a **2.4808 baseline /
candidate batch-CPU ratio**, with its stated paired interval; short ASCII also
improved. These timings use the exact pre-format d919 candidate snapshot recorded in the
audit. The reviewed patch is now applied with the same runtime source hash; the timing binary remains separately identified. Unknown/no-query point slowdowns
remain about 1.1%/0.5%, and the
no-query interval's parity conclusion depends on estimator. The accepted
borrowed-copy known workload measured 2.392; its no-query median slowdown is
about 0.96%, with a worse individual batch retained. List append ratios span
about 1.10–2.30 in the selected cases, while fixed ordinary growth remains about
1.6% slower. These are separate workloads and estimators, not an overall speedup.
Text clocks include measured-program ownership, setup and output work, without
a separately measured final drain or OS teardown; the host was loaded. None is
a full-compiler, application throughput or operation-tail latency result.

## Rejected policies and causal counterexamples

- [Unconditional List reservation](runtime-list-reservation.md) removed cleanup
  opportunities and failed finite-pool admission under queued owner debt. The
  accepted pending-task guard restores the old schedule in that case.
- [Bytes capacity-slack reuse](runtime-bytes-rounding.md) skipped a later growth
  hook after new debt arrived. The selected policy could make a follow-on request
  fail despite saving a small buffer; this does not disprove every smaller-buffer
  policy.
- [Same-credit service relocation](runtime-retirement-experiments.md#executed-equal-credit-causal-and-admission-experiments) improved a
  delayed-owner reuse case but worsened fixed/lazy admission. Moving an equal
  allowance does not preserve reclamation order, retained capacity or success.
- [Unicode slice count propagation](runtime-unicode-view-index-review.md) is
  invalid in the current representation: known count with no offsets certifies
  ASCII. This is a source-derived rejection, not a newly executed regression.
- [HUD cache controls](runtime-hud-formatting.md) distinguish user conversion
  calls, allocating conversions, intentionally permanent cache objects and the
  static pointer table. Counts alone did not justify a cache-policy change.

No speculative service, destruction-order, cache, Bytes-capacity or index-sharing
policy was deployed. Rejected candidates and setup/observer failures remain
archived with their actual dispositions.

## Conditional proof and sustained evidence

The [transformation review](runtime-transformation-review.md) and
[adversarial admission audit](runtime-admission-proof-audit.md) support a narrow
canonical fixed-buddy relation for fresh scalar List construction, with truthful
ownership, representable requests, successful common header creation, **zero
pending tasks after that common header**, and no intervening operations. [Two hand replays](runtime-list-hand-cases.md) and a separate
[adapted unsorted-list replay](runtime-list-unsorted-hand-case.md) compare
allocator decision state, ordered free-list links, initialized data and RC
state. Telemetry and uninitialized storage are excluded; high-water/allocation
counts can differ. This is not a verified whole C/LLVM runtime theorem.

The [two-owner Text/frame control](runtime-text-owner-demand.md) requires three
versus four units solely from opposite local-owner orders, including the automatic
leave poll. It illustrates a conditional cleanup-demand boundary, not an
implemented global certificate or a byte/time bound.

A [research-only Python certifier](local-cleanup-certifier-prototype.md) now has
131 passing assertion groups (20 positive/111 rejection) over 118 input hashes.
The repaired d260 checkpoint has [narrow independent approval](local-cleanup-certifier-implementation-review.md)
and unchanged independent 5/5 probes; earlier false accepts remain archived.
Its conditional archived-function result V=2, F=2, W=4 depends on explicit
caller protection and trusted runtime summaries. It changes no runtime/compiler
behavior and supplies no generated/native execution or production certification.

The [scalar List bulk-copy experiment](runtime-list-bulk.md) passed scoped native,
sanitized, pressure/error and raw-bit controls with unchanged allocation and
poll traces. The older **test-accounted** timing cohort remains qualified by its
[accounting correction](runtime-list-bulk-test-accounting-correction.json).
The separate [production-config cohort](runtime-list-bulk-production-cpu.md)
completed 204 pilots and 192 pairs with exact build guards, opaque full-value
checksums and completed child RSS. Its [independent review](runtime-scalar-production-performance-review.md)
found no unresolved performance blocker. Selected 1024/8193-word ratios are
about 2.34–2.46; fixed empty/reference controls remain roughly 1% adverse.
This primitive append-plus-checksum result does not establish an application hot
path, and old/accounted versus new/production ratios cannot be causally cancelled.

Under the coordinator's exact release, both scalar and aggregate patches are
applied. [Focused combined-source results](runtime-joint-final-results.json)
retain each native/generated/sanitizer scope, revised all-slot caller oracle,
immutable generated LLVM, three archive-only smoke boundaries and exact own
patch reconstruction. The original overwritten List sanitizer LLVM is qualified
and supplemented by seven separately labelled immutable links. Dedicated
final-source endurance remains pending; no broad integration pass is inferred.

The [fixed16MiB/K1 cohort](runtime-soak.md) passed 7,200.008299 native seconds.
The separate system/K32 cohort passed 7,200.027850 seconds, including exact final
recovery and unchanged sources. Both used the earlier c4/01ae source and
**exclude the two newly applied paths**. Requested-memory maxima are end-of-epoch
samples; RSS observations are periodic. Pacing is host-responsiveness policy,
not throughput evidence.

## Primary-source and peer evidence

[Full selected-paper reading](literature-proof-depth-round3.md), the
[claims review](literature-claims-round2.md) and original literature records
identify close precedents for bounded/deferred RC, reuse and destruction order.
Reading a complete artifact is distinct from checking every proof case, and no
broad novelty claim survives those precedents.

[Peer reconciliation](peer-evidence-reconciliation.md) separates source review
from thirteen original Minyar projection methods and 78 selected executions in
six separately scoped matrices. [Provenance integration](peer-provenance-integration.md)
repairs maintained links and raw-source availability without claiming new
execution credit. Incompatible peer copying, byte indexing and reference
identity semantics were excluded rather than imposed on Minyar.

## Remaining production and reproduction gaps

The [105-name public core ABI map](runtime-abi-evidence-map.md) records explicit
function evidence and unresolved entries. It does not infer complete profiling
from source mentions, subsystem names, or line coverage. Native/compiler APIs
have distinct scopes.
The fixed cleanup allowance bounds the specified reclamation units, not total
API latency: payload copies, UTF-8 scans, formatting, allocator/OS activity and
explicit drains retain their own size and environmental costs. No WCET or
operation-tail wall-latency proof is supplied.

The final broad integration/coverage lane stopped after service-side restrictions.
Earlier broad gates and coverage snapshots precede later edits and retain that
limitation. [Production-size terrain](native-application-round7-report.md) passed
O2, while its default-quarantine sanitizer run was resource-aborted without a
complete output or sanitizer diagnostic; it is inconclusive. Tiny real graphics
rounds [6](native-application-round6-report.md) and
[9](native-application-round9-report.md) validate selected framebuffer oracles,
not the full game or all driver paths; overlay drawing remains untested.

Selected [durable evidence](evidence/runtime/index.json) survives `make clean`.
[Archive-only reproduction](runtime-evidence-smoke.py) has a verified tiny native
scope, with installed Darwin Clang/SDK prerequisites. Other generated studies
still depend on recorded compiler/toolchain artifacts. Harness corrections and
historical incomplete runs remain visible; neither LSan nor generated LLVM UBSan
coverage is claimed.

**Current status, 2026-10-04 06:26 UTC:** the independent final-source review,
short pilots and calibrated faults have passed. The released
[joint final-source endurance](runtime-joint-endurance.md) is running; its final
long-run disposition and coordinator/closure acceptance remain pending. The
broad integration lane remains blocked.
The two fault calibrations and short native/C sanitizer pilots have now passed
in [their separate record](evidence/runtime-joint-endurance/run-77p_xuej/results.json);
no long-run result is inferred. The initial fortified-macro fixture adapter build
failure remains archived separately.

The [static final ABI source map](runtime-abi-final-source-map.json) preserves the
historical105-name registry and execution scopes while refreshing d919/3b
definitions. The [production archive patch addendum](evidence/runtime-list-bulk-production-cpu/run-x3798c1e/archive-patch-addendum.json)
adds the exact retained scalar patch and keeps the original index checkpoint
unchanged. Neither documentation correction grants new execution credit.
