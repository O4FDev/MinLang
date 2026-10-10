# October memory and compiler campaign

Started UTC **2026-10-03 23:54:29**. The user requested at least seven hours of
active work; the earliest completion is **2026-10-04 06:54:29 UTC**. All engineering
agents use GPT-6.1 Sol with high reasoning. Elapsed time alone is not evidence of
coverage or an achieved optimization.

## Start here

The [current findings](campaign-findings.md) and [machine-readable states](campaign-findings.json)
separate completed outcomes from pending endurance/closure. [Focused joint results](runtime-joint-final-results.json)
link the exact final source and distinct native/generated gates; the [final static ABI map](runtime-abi-final-source-map.json)
preserves per-function evidence boundaries. The [additive scalar patch archive record](evidence/runtime-list-bulk-production-cpu/run-x3798c1e/archive-patch-addendum.json)
corrects a small omitted patch while retaining the original index. The
[paper methods and claims brief](paper-methods-and-claims.md) is a separate
source/evidence synthesis, not another execution result. Independent
[joint source/pilot review](runtime-joint-final-source-review.md) is complete;
the [documentary closure checkpoint](campaign-final-closure-review.md) accepts
current evidence and links, with the long final outcome still pending.

## Ownership

| Area | Owner | Working boundary |
| --- | --- | --- |
| Coordination, campaign acceptance | Root | Schedules measurements; protects existing work. |
| Runtime allocation and memory engineering | `memory_engineering` | Runtime C/private fragments, focused memory tests. |
| Primary literature and claims | `literature` | Paper review and source-grounded assessment. |
| Compiler profiling and peer tests | `peer_profiling` | `profiling*`, `peers*`, peer research tools/tests; compiler changes require an agreed file boundary. |

No commits are authorized in this campaign. Existing changes are preserved.
The initial tracked binary diff and source-file hash manifest are retained at
`/var/folders/kp/v_5qvc9n6vb8gb8htz3yqwzm0000gn/T/minyar-october-baseline-s7giml8w`.
This snapshot includes untracked file hashes, not their contents; it is a
comparison aid rather than a complete backup.

## Evidence index

| Record | Meaning |
| --- | --- |
| `profiling-initial.log` | Exact initial gate command, build output, times and exit status. |
| `profiling.md` | Subsystem map, baseline, reproducible measurements and acceptance criteria. |
| `peers-expanded-pending-inventory.json` | Complete immediate Git tree inventories for 1,560 LLVM InstCombine and 1,996 Lean run entries; source review remains explicitly pending per path. |
| `peers-review-ledger.json` | Deduplicated paths with exact review extent and cross-references; scenario counts remain per-manifest and bounded pending paths stay explicit. |
| `peers.json` / `peers.md` | Pinned bounded inventories and explicit semantic dispositions. |
| `peer-nim-koka-lean.json` | Separate additional ownership-oriented per-unit review and original adaptations. |
| `profiling-coverage.md` | Measured/unmeasured subsystem ledger, limitations and next experiments. |
| `profiling-full-gate.log` / `profiling-full-gate-sources.json` | Interrupted background gate and explicit mixed-version provenance. |
| `profiling-normal-qos.json` | Temporary scheduling wrapper retaining resource safety limits. |
| `profiling-full-gate-normal.json` / `.log` / `-disposition.json` | Source-frozen normal-QoS full gate: one cold-bootstrap timeout; exact command history and known Unicode gap. |
| `profiling-reachability-expanded-final-red.json` / `profiling-reachability-bootstrap.json` | Red-first literal-true reachability repair, independent review, and matching bootstrap fixed points. |
| `profiling-bootstrap-policy-red.json` / `profiling-cold-bootstrap-final-evidence.json` | Scoped public-bootstrap scheduling repair, retained limits, and actual default cold-launcher validation. |
| `profiling-integrated-focused.json` / `.log` | Maintained peer, runtime-memory and launcher-policy gate integration; focused snapshots and exact commands. |
| `profiling-coverage-run.json` / `profiling-coverage-final.json` / `profiling-coverage-matched.json` | Preserved coverage infrastructure failures and the matching-toolchain restart; no denominator or threshold exclusions. |
| `profiling-coverage-toolchain.md` / `profiling-coverage-result.json` | Actual LLVM22 pipeline portability repair, exact denominators and explicit eager/configuration scope. |
| `peer-swift-statement-directory.json` / `.md` | Complete recursive statement directory: 25 files source-read with 273 authored function/scenario groups; grouped assertions are not counted as ports. |
| `profiling-afl-tooling.json` | Official AFL++ v5.03c source pinned by full commit and archive checksum; isolated build and actual fuzz campaign remain pending. |
| `profiling-reachability-mutations-plan.json` | Six exact source-anchor CFG mutations; execution status remains separate from planning. |
| `peer-rust-expression-directory.json` / `.md` | Complete immediate pinned Rust expression directory, individual dispositions and explicit overlap with the initial inventory. |
| `runtime-list-reservation.md` | Production guarded reservation optimization; initial allocation red, rejected unconditional admission variant, exact final focused snapshots and paired measurements. |
| `runtime-unicode-join.md` | Production correctness repair for indexed consuming Text joins; original native/generated red and independently reviewed final profile checks. |
| `runtime-deferred-reuse.md` | Discovered deferred-owner reuse cost; early-service variants remain isolated experiments, with live aliases and retained capacity as controls. |
| `runtime-bytes-rounding.md` | Rejected isolated capacity-slack candidate; late cleanup debt changed allocation admission, so production Bytes policy remains unchanged. |
| `runtime-profiling-map.md` | Runtime subsystem evidence and explicit unmeasured paths; measured samples do not imply exhaustive coverage. |
| `runtime-retirement-experiments.md` | Proposed/test-only accounting and retirement work; each experiment retains its own scope and tested snapshot, without a broad all-clear. |
| [Read-only Go/Zig round 2](peer-readonly-go-zig-round2.md) / [ledger](peer-readonly-go-zig-round2.json) | 32 authored comparison groups; proposals remain separately scoped from execution. |
| [Read-only Go/Zig round 3](peer-readonly-go-zig-round3.md) / [ledger](peer-readonly-go-zig-round3.json) | 66 additional groups, with the Zig array remainder completed and prefix overlap excluded. |
| [Read-only strings round 4](peer-readonly-strings-round4.md) / [ledger](peer-readonly-strings-round4.json) | 120 authored groups in five complete selected files; runtime projections remain pending in that ledger. |
| [Read-only values round 5](peer-readonly-values-round5.md) / [ledger](peer-readonly-values-round5.json) | 118 comparisons in five selected Swift/Go/Zig files; source review only. Separate original P1/P2 coverage and the historical optimization correction are linked below. |
| [Read-only evaluation round 6](peer-readonly-evaluation-round6.md) / [ledger](peer-readonly-evaluation-round6.json) | 114 groups in two complete selected Go/Zig files; documentary checks and pending proposals remain distinct from original runtime test execution. |
| [Original runtime peer projections](runtime-peer-projections.md) | Thirteen original methods: the earlier eight-method/48 matrix, then five separate six-execution matrices from rounds 7–9. Actual O0/O2 argv and historical sanitizer-O1 correction are retained; no complete thirteen-method run is claimed. |
| [Queue-empty List fragmentation probe](runtime-list-fragmentation.md) | Source-hashed bounded histories found no observed placement/admission difference; cleanup-hook preservation and universal allocator equivalence remain separate claims. |
| [Native/application round 2](native-application-round2-report.md) / [results](native-application-round2-results.json) / [index](native-application-round2-index.json) | Separate staging-allocation/error and application oracles; both 900-second O2 and sanitizer sustained cohorts passed. |
| [HUD Integer formatting baseline](runtime-hud-formatting.md) | Real generated application call mix; public conversion counts, allocating conversions, intentional cache objects and static table storage remain separate. |
| [Function-level public runtime ABI map](runtime-abi-evidence-map.md) / [JSON](runtime-abi-evidence-map.json) | 105 source-defined core names; direct correctness, count and workload-timing evidence remain separate, with explicit unmapped and outside-scope entries. |
| [Public Float Text baseline](runtime-float-text.md) | Ten fixed native/sanitized spelling, alias and recovery cases; managed allocation/helper-service counts and omitted-event red remain separate from formatter algorithm work and application performance. |
| [Unicode view index review](runtime-unicode-view-index-review.md) / [JSON](runtime-unicode-view-index-review.json) | Single-field count propagation rejected from the current ASCII/index invariant; hand counterexample only, with no candidate or production edit. |
| [Aggregate adoption preregistration](runtime-aggregate-adoption-preregister.md) / [JSON](runtime-aggregate-adoption-preregister.json) | Document only: exact reviewed patch, both-cohort entry condition, focused final-source modes, durable replay and blocked full-integration boundary. |
| [Archive-only native reproduction](evidence/runtime-reproduction/run-fczgzr4c/results.json) / [runner](runtime-evidence-smoke.py) | Fresh temporary directory, archived sources only: 18 Unicode cases and one trap; installed C toolchain/SDK remain external prerequisites. |
| [Independent PNG proposal review](runtime-native-round3-review.md) | Five-line bounded repair reviewed against saved reds and arithmetic; no huge framebuffer/GPU execution inferred. |
| [Accepted PNG repair, native round 4](native-application-round4-report.md) / [results](native-application-round4-results.json) | Final-source 75 checks with separately scoped chunk, preflight, PNG decode, zero/retry, allocation, I/O, mesh and loader controls. |
| [Read-only values round 9](peer-readonly-values-round9.md) / [ledger](peer-readonly-values-round9.json) | Source-only comparison groups stay documentary; two original Minyar boundary methods have separate six-execution records in the runtime projection report. |
| [Compiler local closure case](runtime-compiler-closure-case.md) / [JSON](runtime-compiler-closure-case.json) | Source/IR derivation only: conditional four-unit texture-local closure, with the whole-universe claim excluded by caller Bytes lifetime and escape. |
| [Full-paper proof-depth review](literature-proof-depth-round3.md) / [record](literature-proof-depth-round3.json) | Complete selected CTRC and Yue Niu–Jan Hoffmann author artifacts read; unfinished proof verification and transfer limits remain explicit. No new executions. |
| [Peer evidence reconciliation](peer-evidence-reconciliation.md) / [record](peer-evidence-reconciliation.json) | Documentary reconciliation of thirteen methods and 78 selected executions in six separate scopes; no whole-suite replay. |
| [Peer provenance integration](peer-provenance-integration.md) / [record](peer-provenance-integration.json) | Maintained stale links corrected and 197 raw-source entries verified; frozen histories and execution scopes are unchanged. |
| [Independent performance audit](performance-evidence-audit.md) / [record](performance-evidence-audit.json) | Saved-pair reanalysis found no aggregate performance blocker; small slowdowns, timing boundaries, estimator sensitivity and host/provenance limits remain part of acceptance. |
| [Campaign findings draft](campaign-findings.md) / [JSON](campaign-findings.json) | IN PROGRESS: outcomes, rejected policies, conditional results and explicit pending/gap fields for coordinator review. |
| [Historical cleanup certifier design review](runtime-local-cleanup-certifier-review.md) / [record](runtime-local-cleanup-certifier-review.json) | Historical conditional feasibility and 29 then-unexecuted proposed records; superseded implementation results are separate below. |
| [Research cleanup certifier prototype](local-cleanup-certifier-prototype.md) / [implementation review](local-cleanup-certifier-implementation-review.md) / [current handoff](evidence/local-cleanup-certifier-prototype/source-stability-handoff-current.json) | Repaired d260 research-only checkpoint: 131 assertion groups (20 positive/111 reject), 118 input hashes, unchanged independent 5/5 probes; prior false accepts preserved. Conditional local W=4, not production/compiler certification. |
| [Isolated scalar List bulk copy](runtime-list-bulk.md) / [basic results](runtime-list-bulk-results.json) / [follow-ups](runtime-list-bulk-followup-results.json) / [CPU rows](runtime-list-bulk-cpu-results.json) | Test-accounted primitive criteria pass with adverse empty control retained; source/count/pressure/error/raw-bit controls pass. [Accounting correction](runtime-list-bulk-test-accounting-correction.json), production-config evidence and joint final-source/adoption gates remain explicit. |

Inventory discovery, source retrieval, semantic reading, executable adaptation,
and passing validation are different stages. Counts in this campaign distinguish
them. Peer tests outside the selected inventory remain unreviewed.

Measurements run serially on this 16 GiB host. Agents reserve expensive builds
and timing windows with the coordinator; native micro-fixtures may run together
only when they do not contaminate measurements. Correctness precedes performance
comparisons. A change must retain independent expected values, exact relevant
diagnostics, ownership contracts, optimization-level checks and bootstrap
fixed-point behavior.

## Runtime engineering update

The accepted [ASCII metadata change](runtime-ascii-metadata.md) preserves certified
counts through borrowed Text copies. The generated known-ASCII workload has a
CPU baseline/candidate ratio of 2.392; the byte-length-only control is about 0.9%
slower. [Guarded List reservation](runtime-list-reservation.md) retains its append
benefit and a roughly 1.6% fixed-pool ordinary-growth slowdown. These are workload
tradeoffs, not general latency guarantees.

[ASCII paired-ratio figure](runtime-ascii-timing.svg) and
[List paired-ratio figure](runtime-list-timing.svg) show every observed pair and
bootstrap intervals; PDF/PNG exports accompany them. The
[durable runtime bundle](evidence/runtime/README.md) and
[source/result index](evidence/runtime/index.json) preserve 45 selected result
files plus source versions after `make clean`, including rejected candidates,
counterexamples, incomplete host-starved attempts and the corrected 64-check
C-only reporting mistake. The exact final Text `--language` matrix separately
passed 107 recorded check entries: 21 C configurations, 21 generated executions and
21 expected UTF-8 traps. Whole campaign validation remains independently scoped.


## Execution history and durable evidence

The historical c4/01ae checkpoint froze core sources at its then-final Text
matrix and ran the two-hour cohorts. Later root-released joint patches are now
applied at d919/3b; the current released1800-second endurance is described in
the opening links. Historical results below retain their original source scopes. The approved two-hour fixed/K1 payload soak passed
7,200.008299 native monotonic seconds with exact final recovery. Its
[preregistered limits and oracle](runtime-soak.md) and
[durable completed results](evidence/runtime-soak/run-h2hs4wqq/results.json) keep
pilot/red calibration separate from the long cohort. The
[equal-credit experiment](runtime-retirement-experiments.md) is rejected as a
default policy after a finite-pool admission counterexample, despite measured
reuse and allocation-count benefits. No production cleanup schedule changed.

The compiler/peer integration lane stopped after repeated service-side
restrictions. The literature execution lane also stopped after preserving its
completed cohorts. Optional follow-on tooling and shapes are unexecuted. The
[native ownership-model report](literature-native-model-completed.md),
[root-level native-model index](../../evidence/native-model/index.json) and
[root-level literature archive](../../evidence/literature/README.md) preserve
completed sources, seeds, journals and limitations. The completed model cohorts
contain 1,206,002 configuration-weighted public-operation executions and 214,660
constructed/destroyed generations; these are bounded C ABI observations.

The distinct native/application lane's
[report](native-application-report.txt),
[evidence index](native-application-index.json) and
[independent static review](runtime-native-independent-review.md) cover its
terrain and headless renderer changes. The final expanded snapshot records 504
contracts in 12 configurations. That scope includes successful PNG staging,
all nine write-error sites and close-error checks, not PNG malloc-failure
injection or actual GPU/display execution; subsequent work has its own result.

Earlier coverage and the broad full gate retain their recorded source snapshots.
Coverage preceded the final ASCII metadata change. The earlier full gate also
preceded later production changes and had a cold-bootstrap timeout, separately
repaired in focused checks. Neither record establishes complete full-suite or
coverage validation of all final production sources. The blocked final
integration lane is reported as unavailable; focused final runtime matrices,
completed ownership cohorts and application gates retain their exact independent
scope rather than being promoted to a whole-repository all-clear.


[Additional baseline API counts](runtime-api-count-probes.md) measure view
threshold/fan-out retention and Boolean formatting; ten actual generated token
workloads complement native controls. These observations make no policy change
or timing claim. Reproducibility corrections remain explicit in
[the runtime checklist](runtime-reproducibility.md).


The [accepted core patch inventory](runtime-core-patch-inventory.md) separates
this campaign's own changes from the initial dirty runtime and reconstructs its
exact final hashes. A [native size-guard audit](runtime-guard-order.md) fills a
managed failure-order gap under pending debt, with no production change.

The [aggregate Text join baseline](runtime-aggregate-join.md) preserves 18
generated compiler call-pattern projections, including persistent unknown ASCII,
Unicode, empty, single-fragment, no-query and source-alias controls. Its
[durable exact sources and results](evidence/runtime-aggregate/run-norhhoed/archive-index.json)
remain a count-based opportunity, without a full compiler speedup claim. The
[isolated certificate experiment](runtime-aggregate-join.md#isolated-propagation-result)
preserves ordered allocation/service events in its controls and avoids known
ASCII cold scans; unknown/Unicode and no-query costs remain explicit, and no
production policy change or CPU benefit is claimed. The
[paired CPU result and all-control figure](runtime-aggregate-join.md#paired-cpu-observations-candidate-still-test-only)
subsequently recorded known-ASCII benefit with small retained unknown/no-query
slowdowns under shared host load; the candidate remains isolated. The
[Swift round 7 source review](peer-readonly-swift-round7.md) is a separate
read-only ledger; its wide-record adaptation remains a proposal, not an executed
runtime test in that peer lane. The separate [original runtime projection](runtime-peer-projections.md)
now has a six-execution targeted wide-record result, preserving field order,
effects and Minyar shared aliases without claiming Swift value-copy semantics.

The [two canonical allocator hand cases](runtime-list-hand-cases.md) replay the
reviewer's one- and two-move constructions with complete map/free-link,
initialized-content and reclamation-state comparisons. Their deliberately
unequal telemetry and lack of a surviving same-class tail remain explicit.
The separately authorized [adapted three-move case](runtime-list-unsorted-hand-case.md)
tests restoration before surviving tails in unsorted lists, preserving the
literal-layout setup failure and the allocator-rule derivation of its actual
public prefix. Neither cohort proves universal admission equivalence.
The [aggregate all-poll correction](runtime-aggregate-join.md#poll-observer-coverage-correction)
separates helper-mediated work from direct public polls and retains both older
and refined traces; it does not change production or the paired timing binaries.


The [fixed-heap sustained cohort](runtime-soak.md) completed 7,200.008299 native
monotonic seconds with a successful final drain and unchanged sources. Its
end-of-epoch memory and periodic RSS observations remain sampled scopes.
The separately preregistered default system/K32 cohort also passed; its exact final record is linked below. Both cohorts retain their earlier c4/01ae source scope.

Later application rounds retain separate evidence:

- [Round 5: save/load and physics](native-application-round5-index.json) exercises
  actual modules with bounded state and file/alias controls.
- [Round 6: tiny actual graphics](native-application-round6-index.json) uses one
  hidden 64×64 context/FBO and an independent color-path oracle calibration;
  it does not establish full-game graphics or general driver coverage.
- [Round 7: production-size terrain](native-application-round7-index.json)
  preserves the O2 pass separately from the default-quarantine sanitizer
  resource abort, which has no complete output or sanitizer defect conclusion.
- [Round 8: textures and atmosphere](native-application-round8-index.json)
  records CPU computations and captured geometry. Cloud occupancy is inferred
  from output, so coherent whole-cell omission/addition remains a gap; this
  cohort does not execute real graphics.
- [Round 9: tiny graphics composition](native-application-round9-report.md) /
  [evidence index](native-application-round9-index.json) records four groups and
  six readbacks, plus two separate oracle mutants. Overlay drawing remains
  untested; no production repair or sanitizer/timing result is implied.

The [independent transformation review](runtime-transformation-review.md),
[adversarial admission audit](runtime-admission-proof-audit.md) and
[literature/claims review](literature-claims-round2.md) separate static arguments,
prior-art overlap and proof limits from executed results. The aggregate candidate
remained unapplied through both source-frozen cohorts and is now applied under the exact joint release; focused final validation and endurance retain separate scopes. Earlier full-gate and
coverage snapshots remain historical rather than final-source complete checks.

The [two-owner Text/frame control](runtime-text-owner-demand.md) executes the
[read-only cleanup-demand proposal](runtime-demand-certificate.md): opposite
slot orders need three versus four units after including the automatic leave
poll. Its observer calibration, exact recovery and separately disposed frame
cache are explicit; this is not an implemented global demand certificate.

[Read-only Text/loop round 8](peer-readonly-text-loops-round8.md) keeps its
unexecuted peer ledger separate from the [two new original runtime projections](runtime-peer-projections.md),
each with six targeted executions and its own semantic oracle calibration.
The earlier eleven-method snapshot and current thirteen-method discovery remain
separate from the selected execution scopes; no full final thirteen-method
matrix is claimed. The
[independent cleanup-demand audit](runtime-demand-certificate-audit.md) clarifies
uniform-universe, Text/Bytes and direct-release/temporary-detachment boundaries;
the tiny Text-only replay does not implement or discharge a global ledger.

The scalar [independent timing audit](runtime-scalar-bulk-performance-audit.md) conditionally approves the test-accounted cohort only. [Production-configuration validation](runtime-list-bulk-production-validation.md) records distinct configuration and same-binary RSS scopes; new CPU acquisition and independent production review have completed. The [joint final-source plan](runtime-joint-adoption-preregister.md) passed its focused gates. Historical [partial baseline caller controls](evidence/runtime-list-bulk-caller/run-o5v7uh03/results.json) remain separate from the later revised55-line all-slot baseline/final oracle.

The [default system/K32 sustained cohort](runtime-soak.md) now passed 7,200.027850 native seconds and final verified recovery on unchanged c4/01ae source. [Final results](evidence/runtime-soak/run-s9b7q1ep/results.json) distinguish exact quiescent recovery from completed-epoch requested and periodic RSS samples. Both long cohorts exclude the pending candidate patches.

The [separate production-config scalar observation](runtime-list-bulk-production-cpu.md) completed 204 pilots/192 pairs with exact build guards and child RSS. Its adverse fixed empty/reference controls remain visible; independent production review and combined final-source checks have passed; exact joint application is complete, with dedicated endurance/terminal acceptance pending. This does not reclassify the earlier accounted cohort or either frozen-source soak.

The [exact joint application and focused gates](runtime-joint-final-results.json)
now pass on d919 runtime/3b collections: the revised caller oracle checks every
promised source/result slot, both selected projections archive each linked LLVM,
and seven separately labelled generated-ASan List supplements qualify the
original shared LLVM record. [Fresh archive-only reproduction](evidence/runtime-joint-final/run-xc_5g2zj/archive-only-results.json)
executes three native boundaries from retained sources/helpers and installed
Darwin Clang/SDK; [own patch reconstruction](evidence/runtime-joint-final/run-xc_5g2zj/own-production/index.json)
reproduces all three core files from the initial dirty bytes. Original adapter
failures remain preserved. The [independent production scalar review](runtime-scalar-production-performance-review.md)
found no unresolved performance blocker; adverse controls remain explicit.
[Final-source endurance pilots](evidence/runtime-joint-endurance/run-77p_xuej/results.json)
and both oracle calibrations passed. Its explicitly released1800-second run is now active, with a separate final disposition pending. These checks do not restart
or replace the blocked broad integration lane.

The [final static ABI source map](runtime-abi-final-source-map.json) updates
locations/hashes without upgrading historical evidence scopes or the unchanged
105-name inventory. The [production patch archive addendum](evidence/runtime-list-bulk-production-cpu/run-x3798c1e/archive-patch-addendum.json)
adds the exact aca554 patch and preserves the original archive-index checkpoint.
[Independent joint-source review](runtime-joint-final-source-review.md) accepts
focused gates, archive replay and calibrated pilots; only the released
[endurance final outcome](runtime-joint-endurance.md) and terminal closure remain
pending.
