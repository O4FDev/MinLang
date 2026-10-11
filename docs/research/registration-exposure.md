# Captured owning paths and first registration

This follow-up repairs live-object reclamation in the optional, single-owner cycle runtime while preserving the existing registered-growth work bounds. Ordinary compiler and runtime sources are unchanged. Native callers still need every owning-edge barrier, serialized nonreentrant service, and legal live owners. Neither this patch nor the tests permit resurrection of an active white object.

## Why a reference count is insufficient

A certified record can already own an empty traced List or record. That empty child is unregistered and skipped by an earlier field scan. Its first outgoing store must rejoin the old owning parent before a local cohort can reclaim the child. The maintained Result callback regression exercises two such Lists through both payload slots. Its temporary receiver borrow makes the total count larger than the incoming count, so an apparent external count cannot establish that the previously scanned path remains covered.

Conversely, a fresh, never-captured parent may own an empty child while both remain in the finite unknown cohort. Treating all such incoming owners as previously scanned forces repeated full scans. The conservative checkpoint fixed the first correctness case but needed 35,747 units for 32 callbacks against the unchanged 4,608-unit bound.

## State and lifetime rules

The existing bit 2 in gray_next has two disjoint meanings. On a registered node it remains the snapshot namespace. On an unregistered node it records sticky exposure through a captured incoming path. MARK sets exposure when it skips an unregistered traced child. An owning publication from a previously registered, already exposed source sets it too, including an append beyond an active List scan limit. Incoming-edge removal never clears this exposure; one of several owners disappearing does not erase another owner's prior scan. Registration reads it before assigning the registered namespace. Zero-owner retirement clears metadata before allocator reuse.

Registered mark 3 means the new registry node has not yet been exposed by a captured traversal. It does not mean gray, and a direct primary tag alone does not move it into the known registry. Captured ROOTS and actual non-new shading normalize it before tracing. ROOTS must normalize even an internally owned fresh cycle with no external shading call; otherwise the nonzero state alone can retain garbage through its first finite cohort. Existing gray mark 1, queue links, pins, and captured lengths remain intact.

First-registration additive preservation requires prior registration, no traced incoming owner, or no captured exposure. All existing phase, held-anchor, pin, self-insertion, and after-incoming anchor checks remain. No decision uses a temporary borrow as persistent provenance.

A primary tag witnesses the object's anchor path. Promotion to the known registry additionally requires every current owning edge to be accounted for by the captured traversal, a sound direct child tag whose unknown cohort still receives mandatory descendant work, or sticky exposure on a skipped empty child that forces rejoin at first registration.

Two publication boundaries enforce that distinction. When proven MARK encounters a freshly registered snapshot-new child outside the captured cohort, it cancels the proof and schedules a joined finite scan before the parent can promote. When an active List receives its first primary tag but its current length exceeds its captured scan limit, the tag is withheld and a joined scan is scheduled. Restarting the index cannot cover an unvisited appended suffix. This source-coverage check applies regardless of whether the appended child is unregistered, fresh registered, or an already captured temporary root. Completed mark 2 requeues with a fresh length; a fixed-length record can restart its index within that fixed length.

## Canceled cohorts and root loss

A canceled local MARK may finish a known parent outside that job's captured sweep cohort. Its completed mark 2 then belongs to the old snapshot. Full ROOTS clears that state before namespace and generation normalization. Current MARK cannot complete during serialized full ROOTS, so clearing 2 does not discard current gray work.

A take/drop barrier can run before that root's own full ROOTS visit. Actual shading therefore performs the same stale-2 normalization during full ROOTS. It also normalizes a fresh mark 3 that is not snapshot-new. These checks leave gray mark 1, its queue entry, and collector pins untouched. The internal completed-parent control separately checks a node with no external ROOTS shading call, ensuring the collector-side reset is necessary too.

## Tests and retained evidence

The original late-registration C source preserves 96 schedules across List/record, certified/independently rooted/fresh external receivers, copied/taken publication, temporary borrows, and IDLE/local ROOTS/MARK/SWEEP. The new exposure source adds fresh versus captured incoming paths; direct tags before and after ROOTS; captured publication; append limits with all three target ages; real public-API appends under budget 1; shared-owner removal across namespace flips; allocator reuse; queued gray roots; stale and fresh roots moved before their ROOTS visit; internal completed parents; and fresh internal cycles.

Tests assert actual fields, List lengths, live object counts, incoming/owner conservation, queue identity, exact final zero objects/bytes, and existing unit budgets. Split-service cases use public retain, incoming, store, commit ordering and stop service only to inspect a legal phase. The long-List case reaches the same append boundary through real public calls and ordinary budget-1 polling.

All evidence is retained on existing Boat bx_w8xs3uwb under /home/user/minyar-overnight/ci/memory-registration-review. The original d9 C and maintained Result O0/O2 failures, guard-only local-ROOTS failure, conservative work-bound failure, delayed direct-child failure, stale-root failure, registered/captured append failures, fixture setup non-passes, resource-paused non-passes, and survived initial mutations remain separate.

The final runtime pair passes the maintained Result 26-test suite and independent 23-method review across native, ASan/UBSan, 1MiB bounded budgets 1/32/1024, and bounded sanitizer budget 1, with O0/O2 output and exact cleanup oracles. Existing progress 21+21, witness 14+14, original additive 30+30, and registered growth 30+30 profiles pass unchanged. Registered growth still uses its author's 4MiB profile; original additive remains 1MiB. The raw system-budget-1 callback case now uses 1,504 units / 64 epochs under the same 4,608-unit bound; streaming uses 1,075 units / 6 epochs.

The final expanded C source passes 20 native/sanitizer profiles, including fixed/lazy 1MiB heaps, plus O0. The retained original Result LLVM passes O0/O2 against the final native and sanitized runtime. Eleven deliberate guard removals compile and then fail exact runtime assertions; the initially survived fresh-ROOTS and full-ROOTS mutations are retained separately and now caught by the fresh internal-cycle and internal completed-parent controls. Ordinary default, system program, and compiler-arena runtime objects are byte-identical to original 7f4d0b5 with LLVM 23 and identical relative-path compile commands.

Final evidence stages are extended-v7, green-exposure-final-v2, mutants-final-v3, exposure-o0-final, and ordinary-final. Runtime source hashes are 43d0e0c2084d490951b7423eea74454f6c7111c58a1d4cf271468fda77910368 (minyar_cycles.h) and 8f0a89de20ecae298e54b030cea789840c513521771ba35517643a5212fd9b61 (minyar_cycles_collect.h). The final exposure test hash is fef056f92b62fa658f29131f7e3b78dde5bd76dd6299c466ff4029d7fb54cdce. Final input/argv/binary/raw-log hashes are indexed by the delivery handoff. These are Linux proofs; they do not certify new Windows or macOS runs. The separate Windows 1-second idle CPU accounting failure remains unresolved and is not bypassed by this patch.

## Limits

There is no arbitrary native mutation guarantee, concurrent collector, or general linear cycle-collection claim. Unknown self-cycle churn retains the documented quadratic limitation. The proposed unrelated-retirement optimization has not been implemented or executed; unregister and outgoing-edge retirement both need their own proof and tests. Metadata stays 32 bytes and no barrier or tracing step allocates. Every scan unit and poll budget keeps its existing definition.
