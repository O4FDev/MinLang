# Breadth continuation — executable scope

Continue toward a simple, fast, reliable native language with automatic memory,
unchanged syntax, and useful applications. This checkpoint defines work; it runs
no builds or experiments. Preserve the dirty tree and historical evidence. All
code/research work uses Sol/high, TDD and the architecture's existing boundaries.
The old campaign is paused and unfinished; creating its replacement goal failed.
This plan does not mark it complete or imply that the goal UI resumed.

## First milestone and campaign acceptance

The first milestone is **25 new independent semantic regression cases across at
least four categories**, plus **one profiled real compile/application pipeline
with a ranked source bottleneck list**. Each case needs a distinct contract,
independent expected result/diagnostic, peer mapping and observed execution.
O0/O2, memory profiles, repeated samples and assertion counts are validation
dimensions, never additional cases. A baseline-green addition is coverage; only
an observed failing contract is a defect red. Do not subdivide one scenario or
change constants to meet the count.

Campaign targets: **100 such new cases informed by at least four peers across
at least six semantic categories**; a measured workload map spanning lexing,
parsing, semantic analysis, LLVM emission, runtime/library, build tooling and
real applications; **three profiled optimization attempts in distinct non-Text/
List subsystems**, with complete-build/application effects; **three materially
different compiler automatic-memory hypotheses**, followed by the best bounded
experiment; one integrated regression/reproduction entrypoint; and a concise
original-requirement → delivery → limitation ledger. Rejected candidates count
as experiments only with an actual falsification or cost result. No speedup is
promised. Targets remain unmet if compatible new contracts or allowed execution
are insufficient; record the shortfall instead of weakening the counting rule.

## First three work packets

| Packet / exclusive owner | Concrete files and work | Tests, workloads and exit evidence |
| --- | --- | --- |
| 1. Semantic expansion / semantic author | Add `tests/peer-breadth-semantics.py` using `tests/regressions.py`; amend `build-support/research.mk` only after focused execution. Start with retained Go/Zig round-three P1, P3, P5–P8; Swift round-seven wide-returned-record P1; values round-nine GCD/extrema proposals. Inspect cited local fixtures to exclude duplicates. Expand distinct branches, lifetime transitions and effect contexts rather than value variants. | At least 25 new cases across control flow/scope, evaluation effects, record layout/return, and alias/lifetime or numeric composition. Use the existing `CompilerTestCase` O0/O2 oracles. Any production fix is handed to its exclusive subsystem owner after a real red. Record compatible subset versus original Minyar control honestly. |
| 2. Workload map and first bottleneck / profiling author | Own new `tests/breadth-profile.py` and its result schema. Read `compiler/compiler.min` (`tokenize`, declaration discovery/index lookup, `parseExpression`, `compileStatement`, `compileTokens`), `compiler/module-compiler.min`, `tools/module-build.c`, `minyar`, and existing performance harnesses. If phase instrumentation is justified, compiler owner alone edits the monolithic compiler and adapter. | First profile the real `examples/craft/main.min` source-to-LLVM and complete native-build pipeline; separate frontend, cache driver, Clang/LTO/link and execution costs. Follow with self-compilation and cold/unchanged/body/interface-edited module graphs using `tests/module-performance.py` and `tests/incremental-module-performance.py`. Produce raw samples and ranked source attribution; mark phases inseparable where attribution is unavailable. First milestone needs one observed pipeline, not all workloads. |
| 3. Compiler automatic-memory decision / compiler owner | Own `compiler/compiler.min`, `compiler/module-compiler-adapter.patch` and any necessary generated-adapter coordination. Compare the three hypotheses below against existing borrow/ownership lowering and the retained `textures.snow` closure case. Implement only the cheapest valuable, falsifiable choice after packet 2 identifies a relevant cost. | Use `tests/readonly-parameters.py`, `tests/production-readonly-parameters.py`, `tests/scalar-record-storage.py`, `tests/recursive-data.py` and new focused branch/escape cases. Check output, alias lifetime, generated IR ownership effects, relevant profiles and stage-two/stage-three fixed point when lowering changes. A rejected experiment needs a concrete counterexample or measured adverse cost. |

These are work roles, not authorization to spawn agents. One writer owns each
file; shared harness/build-rule edits transfer explicitly. The compiler is one
stateful source unit, so compiler edits and adapter changes are serialized.
On the 16 GiB host the coordinator grants one CPU measurement/build window at
a time. Correctness jobs pause during timing; no concurrent soaks or benchmarks.

## Breadth after the first milestone

Use the already reviewed pending ledgers before new acquisition:
`peer-readonly-go-zig-round3.json` records 25 pending runtime subsets and eight
proposals; `peer-readonly-swift-round7.json` and
`peer-readonly-values-round9.json` identify concrete unimplemented combinations.
Use `peers-review-ledger.json` and `peers.json` for the remaining fourth-peer
contracts (Rust/Nim/Koka or LLVM where compatible). The Rust expression directory
contains many unsupported features, so it cannot be treated as a ready batch.
Six categories must include control flow/scope, effect order, type/diagnostic
contracts, record construction/return, ownership/alias lifetime, and numeric or
Bytes boundary behavior. A count target does not justify new syntax or importing
unsupported copy, pointer, generic, constexpr or concurrency semantics.

Profile-driven non-Text/List attempts should cover (1) compiler declaration/type
lookup or phase bookkeeping, (2) incremental cache/build and runtime LTO cost,
and (3) Bytes/binary I/O or native mesh/image transfer. Source anchors are
`compiler/compiler.min`, `tools/module-build.c`, `runtime/minyar_bytes.h`,
`runtime/native/graphics.c`, and `examples/craft/{save,terrain,meshing}.min`.
Use exact binary round trips, terrain/mesh fingerprints and independent image
oracles alongside real end-to-end costs. Existing numeric and Bytes fixtures
support focused safety checks. Retained release-build CPU growth of 16.5% in
`docs/performance.md` is an old tuning lead, not the current baseline. Terrain's
resource-aborted sanitizer cohort and untested graphics overlay remain gaps.

The automatic-memory hypotheses are: **last-use ownership transfer** across
branches/calls (reduce bookkeeping without consuming live aliases);
**escape-informed scalar-record storage** beyond existing narrow scalarization
(reduce allocation, with identity/mutation preserved); and **local-component
cleanup summaries** for proven nonescaping call components (predict structural
work without asserting caller/whole-process closure). Compare applicability,
analysis/runtime cost and falsifiers before choosing. The `textures.snow` proof
is conditional W=4 for one local component; its escaping Bytes caller and the
research-only certifier's old runtime catalog prevent general certification.

## Execution, integration and evidence discipline

Allocate at least 70% effort to implementation, profiling and test execution;
at most 15% to documentation/duplicate review; the remainder to targeted design
and literature. One independent review per meaningful production patch; repeat
only for new risk, failure or material changes. No resumed Text/List micro-work
unless it blocks these goals. No long soak or paired timing before substantial
new paths justify it. Review does not substitute for implementing pending cases.

Normal authorized focused local TDD continues. Previously stopped broad final
integration/coverage, optional AFL and restricted native/model agent actions
stay stopped: no retry, alternate route, renamed wrapper or rejected-resource
retrieval. `campaign-final-closure-review.md` records this service boundary but
does not give an exact rejected invocation, so that action's boundary remains
unresolved; it is not a blanket prohibition on compiler work. Independent
read-only source/IR analysis is available if a specific action is blocked.

Add `tests/breadth-check.py` as the single focused entrypoint for new semantic
cases, chosen correctness/reproduction fixtures and opt-in profiles. It must
report skipped/blocked lanes explicitly and cannot wrap the stopped broad gate.
Finish with a short ledger linking requirements to new observed cases/results,
source identities and gaps. Two historical two-hour soaks apply to older runtime
sources; the later joint 30-minute run was interrupted around 15 minutes without
a final drain. Neither certifies this continuation or closes final integration.
