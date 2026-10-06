# Focused native semantic mutations

Fourteen selected semantic mutations were compiled in isolated runtime snapshots after successful unmodified fixture calibration. Twelve were detected; two survived. No production file was edited. No build failed or timed out. The [machine-readable result](literature-native-mutants.json) retains exact mutations, source hashes, commands, exit codes, diagnostics and artifact paths. This is targeted fault detection, not exhaustive mutation coverage or a proof of runtime correctness.

| Mutant | Detector / configuration | Result |
| --- | --- | --- |
| unicode_known_counts_without_index | memory-research-text-join-index.c, K1 o2 | killed |
| unicode_check_left_only | memory-research-text-join-index.c, K1 o2 | killed |
| unicode_check_right_only | memory-research-text-join-index.c, K1 o2 | killed |
| unicode_always_invalidate | memory-research-text-join-index.c, K1 o2 | survived |
| join_shared_left_reused | memory-research-text-join-index.c, K1 o2 | killed |
| join_view_reused | memory-research-text-join-index.c, K1 sanitize | killed |
| join_self_uses_stale_storage | memory-research-text-join-index.c, K1 sanitize | killed |
| poll_cap_k_plus_one | bounded-frame-retirement.c, K1 o2 | killed |
| poll_forgets_round_robin | bounded-frame-retirement.c, K1 o2 | killed |
| temporary_partial_chunk_omitted | memory-research-accounting-edges.c, K1 o2 | killed |
| release_ignores_immediate_work | text-view-budget.c, K1 o2 | killed |
| reserve_ignores_retirement_debt | memory-research-list-debt-pressure.c, K1 o2 | killed |
| reserve_ignores_active_object_debt | memory-research-list-debt-pressure.c, K1 o2 | killed |
| reserve_ignores_frame_chunk_debt | memory-research-list-debt-pressure.c, K1 o2 | survived |

The always-invalidate Unicode mutant preserves all character and slice results but forces lazy reconstruction for known ASCII operands. Its survival is expected under semantic oracles; a performance/state assertion would address a different property. The object-only reservation guard survives because the present tight-pool fixture contains object debt. A frame/chunk owner can also hold the buddy needed by final reservation, so that survivor identifies a missing admission adversary. It is not classified as equivalent.

Two debt mutants first returned the exact bounded-heap-exhaustion diagnostic, which the initial classifier did not recognize. Their raw runs remain unclassified in the first artifact. After recognizing that diagnostic, both were rerun with passing unmodified calibration and detected. Unlike the earlier invalidated model runner attempt, these original native binaries genuinely compiled and executed; the rerun supplies the reported automated status.

Existing maintained tests supplied the detectors. ASan makes stale self-join storage and interior-view storage faults observable; a native allocator can otherwise keep a resized buffer in place. The fairness fixture checks continuously ready object/frame/chunk queues and persistent queue selection. The partial-chunk fixture checks the actual 1→2→1→0 task sequence. The public Text-view fixture distinguishes immediate object destruction from queued root destruction. The reserve-pressure fixture checks admission, contents and exact pool recovery.

Malformed UTF-8 remains covered by the separate Unicode regression runner and independent review; this small mutation campaign executed valid-input fixtures only. The selected profiles and K1 budgets do not replace the completed profile/budget/sanitizer matrices recorded by engineering.

The frame/chunk obligation is now closed by a separately calibrated follow-on experiment: `tests/memory-research-list-owner-debt.c/.py`, evidence `build/memory-research-list-owner-debt/run-vkrj6rvc/results.json`. Eight builds and sixteen executions cover frame/chunk debt at K1/K32, native O2 and ASan+UBSan O1. All eight correct-runtime controls verify contents and complete pool recovery; all eight object-only-guard runs stop with the expected bounded-heap exhaustion diagnostic. The original surviving run above remains unchanged. Combining these distinct experiments detects thirteen selected mutants and leaves the conservative Unicode performance mutant alive.

Independent inspection confirms that the fixture transfers existing owned counts without inventing references: its chunk replacement removes one spacer count and transfers the scalar debt record count, and its frame local consumes the debt record count. The 2K+2 owner visits ensure header creation and the next allocation service cannot prematurely erase the intended guard-entry state. Private detach pins the kernel queue state; the subsequent append uses the public API. This is not a claim that a public leave/step reaches that same state without its automatic poll. The first mixed-record calibration failed even in the correct baseline (`run-_cz_08lm`), because delayed record scanning changed the growth migration and pool layout. Engineering corrected the fixture to a scalar leaf, preserved that failed calibration, and reran the complete control/mutant matrix.
