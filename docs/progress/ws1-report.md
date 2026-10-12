# WS1 concurrency: held-state report

## Landed in v2

None. The integrator has not published `PHASE1_DONE`; implementation and
Boat qualification are held. No concurrency gap is marked fixed.

## Prepared on ws1/concurrency

- `c38057c`: opt-in selector/header and include. Independent R1 review
  requested changes; this source commit is not approved for integration.
- `67e9515`: recorded the Phase 1 hold.
- `cfa5629`: full release qualification plan.
- `f957639`: cited ownership/thread decision and neo-db executor proposal.
- `3265fa7`: exact warm-cache effect-loss regressions, local/non-atomic versus
  shared/atomic evidence, channel mutex gates and selector review disposition.

Read-only research and feasibility tasks completed. Independent docs/design
review R2 approved its exact `3265fa7` scope as documents only; B1/B2 selector
source approval remains withheld. Final review covers the later G14 cleanup
requirement and literal-provenance/portal-state clarifications. No product
implementation or qualification result is implied by these documents.

## Decision and implementation work remaining

The required release shares FrozenBytes backing concurrently through checked
managed handles with atomic native lifetimes. Ordinary mutable values and
collector state remain domain local and non-atomic. Bounded channels provide
the public synchronization primitive. Explicit Bytes detachment transfers an
exclusive backing allocation without copying and empties every sender alias
to its local shell; it is not general affine graph transfer.

After release from the hold, fix selector `0`/`1` semantics and reject bounded
RC's implicit pool without a system heap. Then implement domain initialization
and teardown, Unicode literal localization, per-thread collector state,
checked named entries and transitive call effects, opaque control lifetimes,
bounded channels, exact-accounted transfer and shared FrozenBytes. Preserve
checks through module/interface caches and optional frontend routes. Coordinate
stack/recovery and syscall boundaries with WS2, collection contracts with WS3
and platform qualification with WS7.
WS2's terminal G14 audit adds a shared emitter constraint: indirect callback
nonleaf tracking and structured entry slots must preserve domain validation,
and every stack-backed ownership frame needs its exact paired leave. The
qualification plan records the unexecuted Bytes-owning callback regression.

No repro or stress test has passed for these capabilities. The remaining
release evidence is the original objective: integrator merge/CI receipts,
kernel-blocking VMM-2 test, compiler Send rejections/acceptances, concurrent
shared lifetime and zero-copy tests, per-thread collector/exit cleanup,
TSan-clean generated/runtime/native stress, all five single-thread benchmark
families within ±1%, and near-linear shared-input scaling on eight Boat vCPUs.
The [qualification plan](../research/concurrency-qualification.md) specifies
the observations and failure cases; existing loose gates are not substitutes.

## Decisions needed from the integrator

- Publish the qualified, pushed `v2` SHA and green CI URL in `PHASE1_DONE`.
- Admit one quiet eight-vCPU Boat sandbox and the platform verification route
  under the shared programme budget. No allocation or spending has started.
- Freeze the parallel workload, estimators, samples/stress bounds and proposed
  scaling interpretation before measurements. The proposed 7.2x median and
  6.4x interval lower bound are not yet approved thresholds.

Preserve the stopped research checkout and do not bypass the laptop resource
guard. Lightweight review worktrees use no checkout/materialization.
