# First registration and canceled local marking

This document preserves the initial conservative two-fix checkpoint and its real performance red. The tested selective follow-up is described in [registration-exposure.md](registration-exposure.md).

This is a correctness repair for the optional single-owner cycle runtime. It does not change the ordinary compiler or runtime. Native callers must use all owning-edge barriers and may only publish values through legal live owners; the repair does not permit resurrection of an active white object.

## Two independently reproduced defects

A certified record can own an empty traced List or record that remains unregistered. Its earlier field scan skips the unregistered child. On the child's first reference insertion, preserving the old certificate can omit that certified parent from a local cohort. A temporary receiver borrow does not establish an independent persistent root. The local collector can consequently clear a live List. The maintained Result callback case reproduces this in both optimization modes, through both payload slots.

The conservative guard captures whether the source was registered before registration. Additive preservation now requires either prior registration or no existing traced incoming owner. An internally owned first registration rejoins the old certified parents. It does not classify a transient reference count as a root.

Canceling a local cohort exposes a second defect. Its MARK phase can finish scanning an old known parent outside the captured local sweep cohort. That parent keeps completed mark 2. The following joined full job can choose another anchor and ordinary shading skips the marked parent, incorrectly omitting its new descendants. Full ROOTS now resets completed mark 2 before its existing namespace and generation normalization.

No current MARK scan can complete during full ROOTS: execution is serialized, the gray queue is only consumed in MARK, and completed mark 2 is assigned only by MARK completion. Queued mark 1 is retained, including gray links and pins. The reset adds constant work to the existing ROOTS unit and does not enlarge a cohort or poll budget.

## Tests and evidence

The direct C test covers 96 combinations: empty List or record; certified, independently held uncertified, or fresh external receiver; copied or transferred publication; borrowed or unborrowed receiver; and IDLE/local ROOTS/MARK/SWEEP. Oracles use exact owned fields, List lengths, callback captures, object counts, and zero final objects/bytes. Phase schedules publish through legal owned application pointers, with the same retain, incoming-count, store, and commit ordering as public helpers. They do not attempt active-white resurrection.

An additional queued-root adversary publishes a current mark 1 before that root's full ROOTS unit, checking that the queue retains one entry and its link remains intact.

Evidence is isolated under /home/user/minyar-overnight/ci/memory-registration-review on existing Boat bx_w8xs3uwb. Original d9 direct O0/O2 runs abort at the live-object oracle; original retained Result O0/O2 binaries fail with an empty List diagnostic. The registration guard alone retains an additional local-ROOTS red. Both fixes pass the 96 schedules across 20 native and ASan/UBSan profiles: system, fixed, and lazy budgets 1/32/1024, plus eager budget 32. The unchanged retained Result LLVM passes O0/O2 natively and with ASan/UBSan. Exact source, tool, binary, argument and raw-log hashes are retained per phase.

The additional queue adversary passes O0/O2 and ASan/UBSan; a mutant clearing all nonzero marks fails its exact queue-link assertion. Verification of all remaining mandatory suites is still pending. Aggregate-RAM pauses and missing reused-artifact setup runs are retained as non-passes rather than counted as collector greens.

## Performance scope

The incoming-owner guard is intentionally conservative. Constructor graphs with incoming owners may trigger additional full scans. The unchanged captured-growth gate is a retained true red: system budget 1, 32 callbacks needs 35,747 units / 64 epochs against the existing 4,608-unit bound. This repair cannot be treated as a final integrated candidate until a separately proved follow-up passes the existing limits. No selective provenance or unrelated-retirement optimization is included here. Windows idle accounting and the separate unknown self-cycle quadratic limitation remain unresolved and outside this repair.
