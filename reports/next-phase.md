# Next phase: structural memory and codegen work to get the hidden suite close to 1×

Luke (2026-10-31 20:15): hidden 4.67× (now 4.83× after the c8 revert; 3.24× vs Rust) is far from 1×. Next session's
priority is structural memory work, not small tuning. Ablation: reclamation + scheduler ≈ half the hidden gap; even with
every guarantee off Minyar was 3.25× → most of the gap is implementation debt.

## The five worst hidden programs (numbers only; orchestrator callgrind on goal 84e2e01a3, box M, 2026-10-31 20:28 UTC)
Share of Minyar instructions by cost class. "user" = compiled program code including runtime helpers inlined into it
(Map probes, record/List accessors, checked arithmetic).

| program | ratio vs fastest | vs Rust | rc/reclaim | alloc/free | Text runtime | Map/Set | user | dominant cost |
|---|---|---|---|---|---|---|---|---|
| h08 | 12.94 | 9.51 | 10.7 | 2.2 | 4.7 | **23.3** | **50.6** | Map operations + inlined probe/user code |
| h12 | 8.99 | 1.18 | 0.0 | 0.1 | 1.8 | 0.0 | **98.0** | pure compiled code; C reference ~7.6× ahead of Rust → vectorisation / codegen |
| h06 | 8.21 | 7.78 | 17.8 | 12.5 | **39.2** | 0.4 | 26.6 | Text runtime (slice/split/join/search) + RC/alloc of short-lived Texts |
| h01 | 7.51 | 5.06 | **35.9** | 13.3 | 4.1 | 0.1 | 44.6 | reclamation + allocation of short-lived records/Lists (≈ 49%) |
| h13 | 7.09 | 4.67 | 21.4 | 13.0 | **30.7** | 3.3 | 26.1 | Text runtime + RC/alloc |
Next: h16 6.58 (99.9% user code, vs Rust 2.87), h05 5.64, h15 5.00 (rc 22%), h11 4.76, h10 4.39 (Text 46.5%; vs Rust 1.00).

Whole-suite top runtime symbols: rc_bounded_service 5.2%, rc_bounded_retire_small_in 4.4%, rc_heap_allocate 4.0%,
rc_system_deallocate 3.2%, text_slice_bytes 3.7%, minyar_text_split(+next) 3.6%, minyar_join_texts 2.0%,
text_search_next 1.7%, rc_bounded_release 1.5%, map_text_hash 1.3%.

## Structural plan (Opus designs and reviews; Wafer agents implement under SWARM-PLAYBOOK.md)
Rules unchanged: no program slower in either mode, guarantees kept, hidden re-score after every batch, sharded/fast gate.

a. **Escape analysis + stack / inline storage (U6)** for records, Lists and Text that don't escape — attacks the
   rc/reclaim + alloc/free share (≈ 49% of h01, ≈ 30% of h06/h13/h11/h15) and Text slices/split pieces. Start with
   function-local aggregates and loop-iteration temporaries, then inline record fields of record type, then
   non-escaping Text views (no header allocation). Papers: partial-escape-analysis-2014.pdf, region-retrospective-2004.pdf.
b. **Ownership / borrow inference that removes RC at compile time** (Perceus drop/dup insertion with borrowed parameters,
   Lean 4 "Counting Immutable Beans"): papers/perceus-2021.pdf, counting-immutable-beans-2019.pdf,
   lobster-memory-management.html, swift-arc-optimization.md.
c. **In-place reuse (FBIP)** of dying same-shape objects — FIRST fix the latent double-release c1 found in List-header
   recycling (treewalk −9.3% but SIGSEGV; memcheck shows a release on a header the code no longer owns;
   reports/cake/c1.md). Papers: fbip-fp2-2023.pdf, frame-limited-reuse-2022.pdf.
d. **c8 re-land**: Text loop versioning with unique names for nested versioned regions (b07 duplicate LLVM value
   `value.N.fastA.fastB`); a Wafer task is already on it (branch goal/c8fix).
e. **(new, from the profile) codegen for pure compute** — h12/h16 are ~99% compiled code at 9.0×/6.6× vs C but 1.2×/2.9×
   vs Rust: compare the hot loops' IR/asm against the C reference build (`-O3 -march=x86-64-v3`) for vectorisation,
   strength reduction, overflow-check placement and alias facts; this is where SIMD (phase 2 PAR-6) pays off for phase 1.
f. **Map at hashbrown speed for h08-like workloads**: SwissTable-style control bytes with SIMD group probing, integer-key
   fast hash, entry storage inline (Map/Set ≈ 23% + inlined probes in user code).

Decision for Luke (top of goal-status.md): the opt-in `region { … }` block — not part of this plan unless he approves it.
