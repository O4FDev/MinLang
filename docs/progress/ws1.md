# WS1: concurrency

Base: `bf9c0e9`, branch `ws1/concurrency`. Phase 1 completion has not
been signalled; rebase onto `v2` when the integrator publishes it.

## Done

- Read the shared workstream rules and current runtime/compiler contracts.
- Coordinated the RC, collection and call-guard boundaries with WS2/WS3.
- Reserved `MINYAR_THREADED` and `MINYAR_THREAD_LOCAL` for the opt-in
  runtime; ordinary builds retain their storage/layout.
- Recorded the primary-source decision in `docs/concurrency-design.md` and
  the executor sharding proposal in `docs/concurrency-neodb.md` (`f957639`).
- Completed read-only compiler/runtime feasibility audit. Shared Unicode
  literal state, caller address escapes and warm-cache effects need checks.
- Recorded the full release gates in
  `docs/research/concurrency-qualification.md` (`cfa5629`, revised after review).
- Independent R2 approved the design/proposal/gates at `3265fa7` as documents
  only. Selector and implementation approval remain withheld. Follow-ups
  clarify owning literal storage and protocol versus execution portal state.

## In flight

- Final docs review, including the G14 stack-frame cleanup requirement and
  R2 follow-ups; no source implementation admission is requested.
- Thread, Send-boundary and collector implementation plan (research only).

## Merge requests

None yet. Every change requires an independent review before submission.
Only the integrator merges and pushes `v2`.
Preparatory review R1 requested changes; selector `c38057c` is not approved.

## Blockers and qualification

- Integrator confirmed at timeline position 812 that Phase 1 is open and
  implementation/Boat jobs are held until `PHASE1_DONE`. Preserving the
  preparatory selector commit `c38057c`; no further implementation starts
  before the release signal. Requested one 8-vCPU Boat sandbox admission;
  no new compute allocation or spending has been initiated.
- Laptop worktree materialization is resource-constrained. Research children
  may read the parent source and retain drafts outside unfinished checkouts;
  they must not bypass the resource guard or launch duplicate worktrees.
- TSan, 8-vCPU scaling and the unchanged ±1% single-thread benchmark gates
  remain unrun. Shared managed threading is not implemented by this record.
- Selector fixes deferred under the implementation hold: numeric `0`/`1`
  semantics and rejecting bounded RC's implicit pool without a system heap.
