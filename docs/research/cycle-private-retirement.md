# Private zero-count retirement

The opt-in bounded collector no longer invalidates a held primary proof merely because a fresh unrelated registered owner reaches real reference count zero. This is a narrow retirement path. Live owning-edge replacement, generic unregister, the eager collector and ordinary runtime sources retain their existing behavior.

## Eligibility and lifetime argument

The decision runs after the ordinary outside-collector decrement reaches zero and before the bounded queue repurposes the ownership word. The ownership word must equal RC_TRACED, incoming must be zero, and the owner must still be registered, fresh marked3, unpinned and uncleared. Its gray_next may contain only the unregistered exposure bit4: any certificate, generation or link bits reject eligibility. Primary, temporary and retry anchors are excluded.

The collector must be outside its body, in IDLE with no pending/request/rescan/local request, a valid non-building primary proof and an independently held unpinned primary anchor. A marked3 owner has not participated in a captured traversal. With real count zero and incoming zero it cannot supply any live anchor-to-child path.

The owner is unlinked and receives the exact unregistered sentinel gray_next==8. This is a state-scoped sentinel, not a globally reserved pointer bit: registered gray links still use pointer mask ~7 and may naturally contain bit3. Interpretation requires registered==0 and exact equality. No metadata layout or pointer mask changes.

Each queued field independently rechecks the current primary eligibility and dead-owner metadata. Eligible cleanup decrements the child's incoming count and then performs the unchanged ordinary child drop. Both counts change together, so surviving external ownership is unchanged. Unknown surviving children still execute after_drop scheduling; unknown cycles are not certified or parked as known. Temporary proof invalidation remains active. If phase, anchor, proof or request state changed between fields, generic edge removal runs.

The sentinel survives recent/captured queue transitions because those queues reuse object ownership, record map bytes or List capacity, rather than gray_next. The cleanup cursor advances before child release exactly as before. Allocation zeroes cycle metadata, and registration clears gray_next before exposing a new registered lifetime.

This relies on the existing serialized single-owner, non-reentrant collector and complete owning-edge barriers. It does not permit native untracked pointer mutation or resurrection of an object whose real ownership already reached zero.

## Tests and retained evidence

The independent ledger separates borrowed held references, unregistered fieldless cleanup, fresh registered unary cleanup, real replay-like List replacement, and removal of a live owning edge. Sizes32/256/2048 preserve exact payload, object/byte and pending-work oracles.

With the final test source7556b547, original v5 at system/k1 compiled successfully and failed the proposed private-churn bound: eight lifetimes consumed1136 units and8 epochs at n32, against unchanged192 units. The candidate consumed8 units and0 epochs at all three sizes. This is a deterministic work bound, not an actual edge CPU measurement. Live owning replacement remains invalidating.

Tests also cover new descendants, shared held children, independently rooted cohorts, unknown self-cycles, root transfer/loss, primary/opposite certificate fault injection and active local/full ROOTS/MARK/SWEEP. Queued controls retire a four-field owner, service the first field, then change phase, transfer/drop the anchor or invalidate and rebuild its proof before servicing the remaining fields. Recent and captured queue paths both preserve liveness and exact cleanup. Local/full MARK and SWEEP cases explicitly retain a valid primary at the phase boundary, so validity alone cannot authorize the remaining field.

Allocation checks inspect128 fresh lifetimes and track every prior address. System native observed126 prior reuses with0 consecutive reuses; system ASan observed no reuse and proves initialization only. Supported fixed-heap native and ASan runs observed127 prior/consecutive reuses and checked reset metadata on every lifetime. Sanitizer quarantine was not changed.

On Boat bx_w8xs3uwb, frozen a15415377320bfe69d8fb628c2f4dd10a59e02b8 plus two candidate headers and the test produced:
- 344 focused native/diagnostic/sanitized process outcomes, all expected;
- 700 candidate compile/control records across20 allocator/budget native/sanitized configurations, all0;
- the unchanged exposure fixture across20 profiles and original Result42/41 program at O0/O2/native/sanitized;
- six full profiles of Result26 and independent review23;
- progress21+21, witness14+14, additive30+30 and registered-growth30+30;
- all11 exposure and3 retirement mutants killed by runtime assertions after successful compilation;
- ordinary default/program-system/compiler-arena objects byte-identical to7f4d0b5 with the same LLVM23 flags.

All11557 source hashes and7 reused compiler/IR/runtime artifact hashes were unchanged. Aggregate host maxima were39.8734% CPU and9.7308% RAM;75% abort and one builder remained active. These are host resource observations, not workload performance certification. The isolated checkout's initial missing build/minyarc setup failure is retained separately; a hashed symlink to the existing compiler supplied that hardcoded baseline dependency for the fresh passing run.

Proof root: /home/user/minyar-overnight/ci/memory-idle-broad-v1. Focused ledger root: /home/user/minyar-overnight/ci/memory-idle-ledger-candidate-v2. Diagnostic headers only add scalar cause counters and are kept separate from production measurements. Existing fixed binary hashes are additionally bound without altering the original focused manifest.


## Mandatory CI entry contract

CI owns the driver, Make targets and catalogue. This delivery supplies only the C fixture, two opt-in headers and this report.

The fixture includes cycle-additive.c with its main renamed; that fixture includes ../build/managed-graphs-engine.c. Generate this existing engine through tools/cycle_runtime.py: import engine_source, pass the absolute repository Path, and write its returned source to build/managed-graphs-engine.c. Retain the generated engine and compiler/tool/input hashes. No maintained ordinary runtime source needs editing.

Compile tests/cycle-idle-invalidation.c with -std=c11 -Wall -Wextra -Werror, -iquote <ROOT>/runtime and -lm. Author native profiles used LLVM23 -O2; sanitizer profiles used -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer with detect_leaks=1:halt_on_error=1 and UBSAN halt_on_error on Linux. The separate focused ledger used system/k1 -O2 with both native and sanitizer builds. Its diagnostic variant defines MINYAR_IDLE_LEDGER and uses the separately retained scalar-counter header; it is not a production requirement.

Supported profile flags:

- system: MINYAR_SYSTEM_HEAP=1;
- fixed: MINYAR_BOUNDED_HEAP=1;
- lazy: fixed plus MINYAR_LAZY_HEAP=1, subject to the existing POSIX backend capability;
- eager: no bounded/system flags; unchanged generic cleanup.
Bounded profiles use poll budgets1/32/1024; eager uses32. New fixture evidence used4MiB for pool profiles, stated explicitly; existing additive1MiB and all other suite budgets remain unchanged. Follow existing platform sanitizer and lazy-capability conventions rather than claiming unsupported Windows lazy or LSan support.

The command is BINARY N OPERATION [ARGS]. N must be1..4096; authored focused sizes were32/256/2048 and broad allocator/budget controls used32. Valid operations:

- borrow, fieldless, private, replacement, remove-live;
- new-child, anchor-transfer, shared-child, cross-component, unknown-cycle;
- active-local PHASE or active-full PHASE, where PHASE is1(ROOTS),2(MARK),3(SWEEP);
- bounded-only queued MODE RECENT, RECENT0(captured) or1(recent), MODE phase(fullROOTS), local-mark, local-sweep, full-mark, full-sweep, transfer, drop, rebuild;
- bounded-only certificate GENERATION,0(current primary) or1(opposite tag): deliberate guard fault injection, not a valid anchor certificate;
- bounded-only reuse, unknown-after-drop.

Successful commands return0 with empty stdout and intentional stderr ledger lines. Their independent payload/count assertions finish with rc_object_count==0, rc_bytes==0 and no pending work. Fixed/lazy allocation mode requires observed prior-address reuse as well as reset metadata. System/ASan reuse counters report observations without demanding libc/quarantine behavior.

The mandatory private locality command is BINARY32 private assert-local under bounded system/k1: it enforces the192-unit bound for eight retirements and exact cleanup first. A retained original-v5 build with the final same C source is the failure control: compilation0, runtimeSIGABRT(-6),1136units/8epochs and the exact work-bound assertion. It is not an accepted positive run. The full retained operation matrix and per-profile command lines are in the author-used run-ledger.py and run-ledger-profiles.py; CI can extend its existing fixture choices without copying diagnostic instrumentation into production.

## Scope and next verification

The previous actual current-v5 2048-connection smoke passed. Its actual20,000-connection baseline failed2.8431915% idle versus2% and required forced teardown; software idle sampling attributed98.24% of284 userspace samples to collector functions but did not identify every invalidation trigger. Neither that run nor the sample certifies this candidate.

A source-matched actual edge rerun and the unresolved Windows sanitized1s idle gate remain required. The documented unknown residual-cycle quadratic limitation is unchanged. No current edge CPU/RSS/normal-cleanup, Windows, general concurrency or production-readiness claim follows from the deterministic ledger.
