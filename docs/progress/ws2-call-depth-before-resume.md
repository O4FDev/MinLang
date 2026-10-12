# WS2 call-depth implementation — 2026-10-12

Owner release admits development and owned Boat testing from `bf9c0e9`;
only integration into `v2` waits for Phase 1. This branch has no merged gap.
The original independent R1 findings are preserved verbatim in
`ws2-g14-design-review.md` and remain implementation/verification requirements.

Candidate code is a dedicated frontend assembled after closure/Result
adapters, with no ordinary core or frozen-comparator changes. It checks pending
failure immediately after named/indirect language calls, keeps temporary
registrations, roots partial Lists, retains logical guards, tracks checkpoint
predecessors, and disables recovery integer-dispatch replacement. Typed entry
rejection has no leaves; accepted unwind has paired ownership/depth leaves.
Stack v1 conversion rewrites its exact entry and matching leave pieces without
editing callback domain/header metadata. `calldepth.run` validates domain,
counts the root callback as one, caps nested scopes, restores parent state,
and constructs existing errors results with logical counting suspended.
Nonpositive limits fail without executing the callback; `remaining()` is
advisory and returns -1 outside a scope. Failure code 14 is reserved with WS2
parent; code 13 belongs to checked arithmetic.

## Evidence so far

Owned default/no-env Boat `bx_8pvzt8f7`, checkout
`/home/user/ws2-call-depth`, archived source from exact `bf9c0e9` plus task
archives. Included-credit balance before creation: 359845 subscription seconds,
zero purchased seconds, `canStart=true`. No paid add-ons or account changes.
Stopped with operation `stop_4826f12b6a737da7` when runtime linking awaited the
selector dependency. No integrator host was accessed.

Baseline owning G14 program prints `1000`, then exits 1 with maximum-depth
stderr. New C API test initially fails undeclared scope/query API; recovery
fixture initially fails missing calldepth package. Stage1 candidate emits
verified LLVM for G14, limits, nested restoration, ownership/partial
construction, short-circuit/parallel edges, native reserve and imported
Result/try fixtures. Stage2 self-compilation first exposed an unconsumed local
move metadata token after transfer disabling; adapter now disables production
too, and the rebuilt Stage2 LLVM verifies. These are frontend facts, not
runtime correctness passes. Exact logs/IR/native objects are in
`evidence/ws2-call-depth/prelink-evidence.tar.gz`; later final tests must retain
commands, stdout/stderr, input/tool/artifact hashes.

## Required work before review/merge offer

- Import only independently reviewed standalone WS1 selector (701cecd under
  review), then commit/test four depth/bounds/readiness/limit TLS annotations
  separately. Include after math.h is selector-owned. Recovery state uses that
  same macro. No c38057c ancestry is accepted.
- Execute recovered million recursion followed by success, exact limits,
  zero/negative, repeated/nested restoration, all ownership fixtures and
  callback domain rejection. Run O0/O2/LTO, ASan/UBSan with fake stacks,
  small stacks, native/fallback bounds, and actual pthread scope isolation.
- Verify generic and stack v1 exits with the exact RC/debt oracle at
  K1/K32/K1024 and heap policies; check callback wrapper with indirect calls
  cannot be considered stack-leaf. Verify frontend fixed point and launcher
  feature selection including incremental requests forced to full compilation.
- Fresh independent parent-owned review is required before any merge request.
  Windows/macOS/platform and <=1% full single-thread benchmark qualification
  remain required; narrow tests cannot establish them or the parent's G13 >=2x.

Native reserve status can recover before logical exhaustion. Actual guard-page
overflow in large generated/native prologues remains a known limitation, not a
proved recovery guarantee. Native code itself must cooperate to unwind; this
is not recovery from arbitrary runtime faults. Already completed side effects
survive. Raw machine.callEntry is rejected in this recovery frontend; ordinary
frontend behavior remains unchanged. Importing that raw-entry package therefore
requires a compatible safe interface before using recovery.
