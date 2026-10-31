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

## Visible programs (benchmarks/compare and benchmarks/bothmodes at 1 thread, run-2 base)

Method: box M, callgrind `--dump-instr=yes` on `-g` release builds of the run-2 base (the tree behind
`base-results/`, refreshed 2026-10-31 20:46 UTC), at the ~1/10 workloads in `.prof/profile-all.sh`; every top function
below is self Ir from `callgrind_annotate`. Ratios are the full-workload cachegrind Ir from `base-results/compare.json`
and `base-results/bothmodes.json` (visible compare geomean **2.52**, Rust 2.03; bothmodes serial geomean **1.66**, Rust
1.14). Shares are percent of the program's Minyar Ir on the profiling workload. "user" is compiled program code
*including runtime helpers inlined into it* (Map probes, List/record accessors, checked arithmetic, reclamation polls),
so class shares understate the runtime: `intmap`'s map probe, for example, is 85.5% "user" and 2.9% "Map/Set".
Owner lane: esc escape/stack storage, txt non-escaping Text, brw borrow inference, drp dup/drop elision, fbip in-place
reuse, map SwissTable, cg codegen/SIMD, ccs compiler speed. No visible program compiles Minyar, so ccs has no row.

What the visible suite says, in one paragraph: the visible gap is not where the hidden gap is. Hidden was ~half
reclamation + scheduler; visible is ~2/3 codegen and Text. Fourteen of 22 compare programs and five of six bothmodes
programs are ≥60% compiled code (user ≥60%; sortrows is 95.6% in the emitted merge), and for 11 of those 14 rc+alloc is
≤13% (exprparse 25, inventory 19 and tokenizer 16 are the exceptions). Their gaps are bounds checks, per-access
element-kind tag tests, checked arithmetic and loop-invariant reloads (grid 194 Ir/cell vs the C peer's 40).
The other visible bottleneck is Text: 25-45% of config,
logstats, httpparse, textops, service, wordfreq and sorttext, where every split/slice piece is a fresh rc-managed Text
header (or a view that retains the root) and thin slices of a >4 KiB root are copied by `text_slice_bytes`
(runtime/minyar_runtime.c:1237). rc+alloc is 29-42% on json, httpparse, logstats, service and textops, but only json
(40%) and inventory (19%) have memory as their *first* cost; in the text-heavy programs the rc bill is mostly the rc
headers attached to each Text piece, so it falls out of the Text fix.

### compare (22 programs, worst first)

| program | ratio | vs Rust | top costs (% Minyar Ir) | hottest functions | owner |
|---|---:|---:|---|---|---|
| json | 6.38 (c) | 3.79 | rc 23.1, alloc 16.8, text 17.2, list 2.6, user 38.8 | parseValue 17.4%, rc_bounded_retire_small_in 13.4% | esc |
| logstats | 5.16 (c) | 2.84 | text 45, rc 19.7, alloc 15.1, libc 3.7, map 3.1, list 1.9, user 11.4 | minyar_text_split 17.1%, text_slice_bytes 15.2% | txt |
| exprparse | 5.02 (c) | 3.95 | user 64.3, rc 16, text 9.9, alloc 9.2 | Parser.peek 20.9%, Parser.unary.r 20.1% | cg |
| grid | 4.86 (c) | 3.59 | user 96.1, alloc 3 | main 95%, makeGrid 1.1% | cg |
| inventory | 4.58 (rust) | 4.58 | user 66.7, list 12.3, rc 10.4, alloc 8.4 | main 53%, sort.merge#19 10.1% | esc |
| config | 4.18 (c) | 2.77 | user 40.1, text 35.1, map 8, alloc 7.7, rc 5.2, libc 2.7 | parseConfig 12.5%, main 11.5% | txt |
| tokenizer | 3.94 (c) | 3.65 | user 63.8, alloc 13.7, text 13.6, map 2.2 | tokenize 46.2%, main 17.6% | cg |
| httpparse | 3.70 (rust) | 3.70 | text 35.4, rc 19.4, user 23.3, alloc 11.7, map 4.4, libc 3.6 | main 18.1%, rc_bounded_service 10.9% | txt |
| textops | 3.50 (cpp) | 2.07 | text 42.3, user 19.2, rc 16.8, alloc 12.5, libc 4.4 | main 19.2%, text_search_next 14.1% | txt |
| bytecode | 2.88 (c) | 1.11 | user 99.9 | main 99.9% | cg |
| service | 2.59 (cpp) | 1.67 | text 35.8, rc 27.5, user 18.6, alloc 14.4 | main 18.6%, minyar_text_split 13.9% | txt |
| wordfreq | 2.17 (c) | 1.84 | user 48.7, text 25.2, list 12, map 6.6, libc 3.9 | main 48.7%, minyar_text_split_next 23.6% | txt |
| intmap | 1.96 (rust) | 1.96 | user 85.5, alloc 4.5, libc 3.4, list 3.3, map 2.9 | main 85.5%, list_sort_integers_merge 3.3% | map |
| sortrows | 1.92 (cpp) | 1.48 | list 95.6, user 1.7, libc 1.3 | sort.merge#18 41.8%, sort.merge#23 34.8% | cg |
| orders | 1.84 (cpp) | 1.69 | user 78.6, list 11, alloc 8.6 | main 78.6%, sort.merge#18 10.4% | cg |
| par-forkjoin | 1.81 (c) | 1.81 | user 99.9 | main 85.2%, fibSerial 9.4% | cg |
| treewalk | 1.77 (c) | 1.52 | user 87.5, alloc 12.4 | Interpreter.evaluate 34.1%, Interpreter.execute.r 32.5% | cg |
| sorttext | 1.67 (rust) | 1.67 | list 59.9, text 16.1, rc 8.4, user 6.2, alloc 6, libc 3.2 | sort.merge#21 31.9%, list_sort_texts_merge 19% | txt |
| nbody | 1.30 (cpp) | 1.28 | user 99.7 | main 99.7% | cg |
| par-mandel | 1.20 (c) | 1.19 | user 99.7 | parallel#201 95.4%, main 4.3% | cg |
| matrix | 1.10 (c) | 1.07 | user 97.8, alloc 1.5 | main 97.8% | cg |
| par-reduce | 0.83 (rust) | 0.83 | user 99.7 | parallel#202 68%, parallel#371 30.1% | cg |

### bothmodes (6 programs, serial Ir at 1 thread, worst first)

| program | serial ratio | vs Rust | top costs (% Minyar Ir) | hottest functions | owner |
|---|---:|---:|---|---|---|
| textindex | 2.14 (c) | 2.11 | user 79.3, list 9.5, alloc 7.2, libc 2.3 | main 62.9%, parallel#459 16.4% | cg |
| topk | 2.04 (c) | 1.44 | user 99.6 | parallel#1041 61.5%, main 38.1% | cg |
| sort | 2.01 (c) | 1.60 | user 99.8 | parallel#793 42.3%, quicksort 41.2% | cg |
| mapreduce | 1.82 (rust) | 1.82 | user 89.1, alloc 9.8 | parallel#525 57.9%, buildRange 29% | cg |
| forkjoin | 1.30 (c) | 1.15 | user 99.7 | serial 47%, combine 42.2% | cg |
| server | 1.00 (c) | 0.22 | user 46.3, io 20.5, alloc 18.2, libc 4.9, rc 4.4 | serve 37%, request 5% | cg |

### Lane notes

- **cg (17 of 28 programs).** All pure-compute and dispatch programs: bytecode, grid, matrix, nbody, orders, sortrows,
  treewalk, exprparse, tokenizer, par-forkjoin, par-mandel, par-reduce and all six bothmodes programs. Four recurring
  shapes, all visible in the asm: (1) Text/Bytes character indexing re-tests the header (length sign, bounds,
  representation tag, `[text+0x18]`) on every access and reloads the header after each store — tokenizer spends about
  7 of its 10 instructions per character on it; (2) List element access emits an element-kind tag test (`cmp ...,0x6`)
  even where the static element type is known — inventory, grid, orders; (3) checked `Integer` adds (`jo`) stay in
  loops whose range proves them (grid's neighbour count ≤ 8); (4) hot recursive functions push and pop five callee-saved
  registers per call (treewalk `evaluate`: 26 Ir per jump-table dispatch, 11 of them prologue/epilogue).
- **txt (9 programs):** logstats, config, httpparse, textops, service, wordfreq, sorttext (and json/inventory
  secondarily). Dominant helpers: `minyar_text_split`, `minyar_text_split_next`, `text_slice_bytes`,
  `text_integer_bytes`, `text_trim_range`, `text_search_next`. Two concrete costs: every piece is an rc-managed Text
  header (`rc_heap_allocate` + retire), and a slice that is thin relative to a >4 KiB root is *copied* — logstats pays
  71 Ir per slice for the copy and 5 split calls per line, each re-polling `rc_pending_count` and reloading its SIMD
  constants. A cursor/range API over the source (no Text per field) would remove both the copies and the rc headers.
- **esc (2):** json (DOM boxes + string copies; rc+alloc 40%) and inventory (Lists of boxed records; rc+alloc 19%).
  brw/drp would remove the rc half; esc also removes the per-access tag/bounds work that dominates inventory's user 66.7%.
- **map (1):** intmap — the probe loop is inlined into `main` (`and mask; lea ×3; cmp key; jne` over 24-byte entries,
  scalar), 85.5% of the program; `map_grow`'s memset is another 2.2%.
- **brw / drp / fbip:** no visible program is primarily in these lanes (json/inventory are the closest); they remain
  driven by the hidden profile, not by the visible suite.

### The five worst visible ratios: hottest loop vs the C peer

**json, 6.38× vs C** — 10,000 records: Minyar 559.4M Ir (55.9k/record), C 87.8M (8.8k/record). The whitespace/bracket
dispatch loop is fine: `movzx/cmp/ja`, 3 instructions per byte, the same as C's `skip_space`. The cost is per value:
`parseValue` is 320 Ir/call over 304,858 values where C's `parse_value` is 148 (same input, same tree), and
`parseString` is at parity (87 vs 88 Ir/call). The extra is memory: rc_bounded_retire_small_in 74.8M +
rc_heap_allocate 39.1M + rc_system_deallocate 28.7M = 143M (26%) plus `text_slice_bytes` 30.7M — every string slice is
a new rc Text header and, being a short slice of a multi-MB root, a byte copy, where C's `parse_string` returns a
`(ptr,len)` into the input.

**logstats, 5.16× vs C** — 200,000 lines: Minyar 2,346 Ir/line, C 456. split + slice + integer formatting + retire +
heap + dealloc = 311M (66%). `minyar_text_split` runs 5× per line (line + 4 field separators); the function is 180
instructions, reloads its SIMD constants per call and polls `rc_pending_count` on the back edge. `text_slice_bytes`
averages 71 Ir/piece because thin slices of the 2 MB root are copied. C is one `memchr` per line plus in-place field
pointers and a hand-written `parse_int`, with no allocation at all.

**exprparse, 5.02× vs C** — 50,000 lines: Minyar 14,936 Ir/line, C 2,970. `Parser.peek` is 2.94M calls (59 per line) at
53 Ir/call: reload `text` pointer, signed-length test, bounds test, representation-tag test, byte load,
overflow-checked `position += 1`, store, then a second bounds+tag pair for the returned Character. C's `peek` is a
static function that `-O3` inlines into `unary`/`term`, keeping `position`/`length` in registers: a few instructions
per space with no header reloads. Separately, 25% of the program is rc+alloc for the Expr choice objects (one heap object per Number/Negate/Binary
vs C's 24-byte bump-allocated arena entry), and 6.4% is `text_integer_bytes` result formatting where C uses `printf`.

**grid, 4.86× vs C** — 632² cells × 12 generations (4.79M cell updates, plus BFS/components in both): Minyar ~194
Ir/cell, C 40. In the inlined `liveNeighbours`/`countAlive` loops every list element access carries a bounds check, an
element-kind tag test and a header reload (`mov rdi,[rdi+r15*8]` per level), the add itself is a checked 64-bit `add`
with `jo` even though the value is ≤8, and every loop back edge loads `rc_pending_count` for the reclamation poll.
The C peer's IR is a software-pipelined sliding window: three row pointers hoisted, 8 `load i8` + `zext` + `add nuw
nsw i32`, a 2-way switch on the count, no bounds/overflow checks and no allocation. clang does not vectorise it either
(no `<16 x i8>` in the IR), so this gap is per-element instruction count, not SIMD width.

**inventory, 4.58× vs Rust (2.42× vs C)** — 300,000 operations: Minyar 594 Ir/op, C 246; Rust's `Vec<Item>` is 1.27×
faster than C, so 4.58×. Minyar `main` is 315 Ir/op: each List access tests the element-kind tag (`cmp ...,0x6`),
bounds-checks, and the loop polls the reclamation scheduler (rc_bounded_service alone is 14.5M, 8.1%); `Warehouse.take`
and `Catalog.newItem` are out-of-line calls (13.0M + 11.5M) where C inlines them. C `main` is 119 Ir/op indexing arrays
of 40-byte Items by value with inline history Lists, then libc `qsort` (7.7M). This is the esc case: inline record
storage and stack temporaries remove the box, the tag test and most of the rc traffic at once.

### Top 10 functions per program (self Ir share, ≥0.1%)

```
compare
bytecode   main 99.9%
config     parseConfig 12.5%; main 11.5%; text_slice_bytes 11%; text_trim_range 10%; map_text_hash 6.9%; Config.integer.r 6.8%; parseValue.r 6.6%; rc_heap_allocate 4.2%; minyar_text_split_next 3.7%; rc_bounded_release 3.1%
exprparse  Parser.peek 20.9%; Parser.unary.r 20.1%; rc_bounded_retire_small_in 10%; Parser.term.r 8.2%; text_integer_bytes 6.4%; rc_heap_allocate 5.6%; evaluate.r 5.2%; Parser.sum.r 4.2%; rc_system_deallocate 3.5%; rc_bounded_service 3%
grid       main 95%; makeGrid 1.1%; _int_malloc 0.8%; __memcpy_avx_unaligned_erms 0.8%; list_grow 0.8%; realloc 0.2%; _int_realloc 0.2%; _int_free_merge_chunk 0.2%; rc_system_deallocate 0.2%; unlink_chunk.isra.0 0.2%
httpparse  main 18.1%; rc_bounded_service 10.9%; text_slice_bytes 9.6%; rc_heap_allocate 6.2%; text_search_next 5.4%; rc_bounded_retire_small_in 4.9%; rc_system_deallocate 4.7%; minyar_text_split 4%; unicode_case 3.7%; rc_bounded_release 3.4%
intmap     main 85.5%; list_sort_integers_merge 3.3%; map_grow 2.5%; __memset_avx2_unaligned_erms 2.2%; rc_reallocate_data_in 2%; list_grow 1.1%; __memcpy_avx_unaligned_erms 1.1%; rc_system_deallocate 0.5%; rc_heap_allocate 0.5%; minyar_map_keys 0.4%
inventory  main 53%; sort.merge#19 10.1%; rc_bounded_service 8.1%; Warehouse.take 7.3%; Catalog.newItem 6.5%; rc_heap_allocate 2.8%; rc_bounded_retire_small_in 2.2%; __memcpy_avx_unaligned_erms 1.9%; rc_system_deallocate 1.9%; minyar_list_set_owned 1.6%
json       parseValue 17.4%; rc_bounded_retire_small_in 13.4%; minyar_runtime_jsonStringEnd 7%; rc_heap_allocate 7%; leaf 5.9%; text_slice_bytes 5.5%; rc_bounded_service 5.2%; rc_system_deallocate 5.1%; parseString 4.9%; Value.get 3.8%
logstats   minyar_text_split 17.1%; text_slice_bytes 15.2%; rc_bounded_retire_small_in 12.7%; main 11.4%; rc_heap_allocate 8.7%; text_integer_bytes 7.4%; rc_system_deallocate 5.4%; rc_bounded_service 4.6%; minyar_text_split_next 4.2%; __memchr_avx2 3.7%
matrix     main 97.8%; list_grow 0.5%; _int_malloc 0.4%; __memcpy_avx_unaligned_erms 0.3%; realloc 0.1%; _int_realloc 0.1%; rc_system_deallocate 0.1%; __vfscanf_internal 0.1%; _int_free_merge_chunk 0.1%
nbody      main 99.7%; __vfscanf_internal 0.1%
orders     main 78.6%; sort.merge#18 10.4%; rc_heap_allocate 7.2%; _int_malloc 0.8%; list_sort_by 0.7%; __memcpy_avx_unaligned_erms 0.5%; __vfscanf_internal 0.3%; malloc 0.3%; rc_system_new_page 0.2%; ____strtoul_l_internal 0.2%
par-forkjoin main 85.2%; fibSerial 9.4%; total 5.3%
par-mandel parallel#201 95.4%; main 4.3%; __vfscanf_internal 0.1%
par-reduce parallel#202 68%; parallel#371 30.1%; main 1.7%; __vfscanf_internal 0.1%
service    main 18.6%; minyar_text_split 13.9%; text_slice_bytes 10.9%; rc_bounded_service 10.4%; rc_bounded_retire_small_in 8.6%; rc_bounded_release 8.3%; rc_system_deallocate 7.3%; rc_heap_allocate 5.8%; text_integer_bytes 5.1%; minyar_text_builder 3.3%
sortrows   sort.merge#18 41.8%; sort.merge#23 34.8%; sort.merge#28 13.9%; list_sort_by 5.2%; main 1.7%; __memcpy_avx_unaligned_erms 1.1%; rc_heap_allocate 0.6%; minyar_record_set_reference 0.4%; __memcmp_avx2_movbe 0.1%; __vfscanf_internal 0.1%
sorttext   sort.merge#21 31.9%; list_sort_texts_merge 19%; main 6.2%; list_sort_integers_merge 6.2%; minyar_text_split 5.7%; text_integer_bytes 3.7%; text_slice_bytes 3.7%; rc_heap_allocate 3.6%; rc_bounded_retire_small_in 3.4%; rc_bounded_service 2.9%
textops    main 19.2%; text_search_next 14.1%; minyar_text_split_next 12.1%; text_slice_bytes 7%; rc_bounded_retire_small_in 6.3%; rc_bounded_release 6%; minyar_text_split 5.3%; rc_heap_allocate 4.7%; rc_system_deallocate 4.7%; rc_bounded_service 4.4%
tokenizer  tokenize 46.2%; main 17.6%; text_slice_bytes 11.2%; rc_heap_allocate 11.1%; append_in_place 2.7%; map_text_hash 2.2%; text_integer_bytes 1.9%; minyar_record_set_reference 1.8%; _int_malloc 1%; minyar_join_text_take_left 0.9%
treewalk   Interpreter.evaluate 34.1%; Interpreter.execute.r 32.5%; Interpreter.call 20.9%; list_grow 5.6%; rc_system_deallocate 4%; rc_heap_allocate 2.8%
wordfreq   main 48.7%; minyar_text_split_next 23.6%; sort.merge#32 11.6%; map_text_hash 5.5%; __memchr_avx2 2.2%; rc_bounded_release 1.5%; __memset_avx2_unaligned_erms 1.3%; utf8_scan 1.1%; rc_heap_allocate 0.7%; text_compact_kept_piece 0.6%

bothmodes (1 thread)
forkjoin   serial 47%; combine 42.2%; build 10.5%; __memcpy_avx_unaligned_erms 0.1%; evaluate 0.1%
mapreduce  parallel#525 57.9%; buildRange 29%; rc_heap_allocate 8.3%; main 2.1%; _int_malloc 0.9%; __memset_avx2_unaligned_erms 0.7%; malloc 0.3%; rc_system_new_page 0.2%; __memcpy_avx_unaligned_erms 0.2%; __vfscanf_internal 0.1%
server     serve 37%; request 5%; minyar_bytes_new 4.8%; _int_free 4.5%; sendAll 4.2%; rc_bounded_release 4%; net_loop_wait_fill 4%; minyar_net_readInto 4%; rc_system_deallocate 3.8%; malloc 3.8%
sort       parallel#793 42.3%; quicksort 41.2%; main 16.3%
textindex  main 62.9%; parallel#459 16.4%; sort.merge#52 9.2%; rc_reallocate_data_in 2.9%; list_grow 1.4%; rc_heap_allocate 1.2%; __memcpy_avx_unaligned_erms 1.2%; __memset_avx2_unaligned_erms 1.1%; rc_system_deallocate 1.1%; utf8_scan 0.4%
topk       parallel#1041 61.5%; main 38.1%; __memcpy_avx_unaligned_erms 0.1%; __vfscanf_internal 0.1%
```

Reproduce: `.prof/profile-all.sh` (callgrind all 28 at 1/10), `.prof/classify.py build/prof/compare` and
`build/prof/bothmodes` (class shares + top functions), `.prof/cgref.sh NAME N` (callgrind of the C peer, same workload)
and `.prof/refasm.sh NAME` (the `-O3 -march=x86-64-v3 -emit-llvm` C IR). Raw callgrind files, `hotasm.txt` (per
instruction Ir), `files.txt` and `self.txt` are under `/home/agent/swarm/prof/build/prof/` on box M; the execution log
is `~/prof-all.log`.

### Lane delta profiles (keep updated as lanes land)

Same callgrind setup, profiled against the run-2 base with `.prof/prof-commit.sh REF [programs...]`; full-workload
points re-measured with `.prof/fullir.sh` (which reproduces `base-results` exactly: intmap 1,554,954,638 and httpparse
5,397,662,659 on the base).

| lane commit | programs | Ir delta vs base | reading |
|---|---|---|---|
| map `e96c61f1e` (packed Map control bytes) | intmap, httpparse, config, wordfreq, tokenizer, json, sorttext | intmap **+1.46%** (full: 1,554.95M → 1,577.62M), httpparse **+2.04%** (full: 5,397.66M → 5,507.84M), config **+0.74%** (full: 2,765.3M → 2,785.8M); at 1/10: wordfreq +1.1%, tokenizer +0.7%, json +0.04%, sorttext 0.0% | slower on every visible Map user: the packed probe is not paying for its extra per-bucket work. Flagged to the map lane; not a candidate for landing as-is. |
| map `1f69bd2eb` (second commit, "hand the probe its table pieces") | intmap, httpparse, config, wordfreq, tokenizer, json, sorttext | intmap **+1.41%** (full: 1,554.95M → 1,576.91M), httpparse **+1.88%** (full: 5,397.66M → 5,498.98M); at 1/10: config +1.0%, wordfreq +1.1%, tokenizer +0.8%, json +0.03%, sorttext 0.0% | the second commit trims ~0.1 pp of the regression but it is still slower on every visible Map user. |
| map `0b39e9c8a` (revert of both probe commits) | — | back to base code; no delta measured needed | the lane reverted after the two delta reports above. |
| cg `31389b788` (`-mllvm -unroll-threshold=600` in the release driver) | all 22 compare + 6 bothmodes | **grid −25.05%** (full: 9,295.4M → 6,967.30M → ratio 4.86 → 3.64); all 27 others within ±0.1% at full (topk +0.080% = 12,126.2M → 12,135.94M; inventory +0.055% = 4,927.5M → 4,930.20M; matrix −0.15%, intmap −0.25%); no class-share move ≥1 pp | the only big visible win so far, and it does not slow any program at full workload. Note the 1/10 profiles overstate small deltas (topk showed +0.52% there, +0.080% at full), so landing decisions should use the full-workload points. |
| res `31b438748` / head `79b1fd422` as committed | all 28 | **0.00% on every program** | the READY commit and the branch head contain no runtime change: `31b438748` and `79b1fd422` touch only `reports/research.md`, and the branch's only non-doc commit is the determinism audit. |
| res worktree change (uncommitted `M runtime/minyar_bounded_rc.h`, +38 lines) | all 28 | service **−6.68%** (full: 1,967.30M → 1,835.94M), logstats **−5.33%** (full: 4,690.10M → 4,440.15M), sorttext −3.28%, textops −3.18%, httpparse −2.34% (rc/reclaim −1.9 pp), exprparse −1.12%, config −0.48%, server −0.23%, wordfreq −0.10%, json −0.03%; every other program 0.00% (max +0.01% sortrows) | the change is real and matches the lane's numbers, but it is **not in the READY commit** — the gate would land documentation only. Needs a commit in `wt/r2-res` before gating; then the numbers above are the expected visible delta. |
| res `87d9cd16f` (same change, now committed with `tests/eager-retirement.c` and its check target) | service, logstats (runtime hunk is byte-identical to the profiled diff) | the numbers above apply; the added test/check files do not change program IR | re-verified the `runtime/minyar_bounded_rc.h` hunk is identical to the diff that was profiled. |
| txt `b102ace81` (split pieces read by position, no List) | all 28 (full workload for service, logstats, sorttext, config, httpparse, wordfreq, textops, json, tokenizer) | service **−44.73%** (full: 1,967.30M → 1,087.31M → ratio 2.59 → 1.43), logstats **−34.55%** (full: 4,690.10M → 3,069.51M → ratio 5.16 → 3.38), sorttext **−8.18%** (full: 1,717.2M → 1,576.80M → ratio 1.67 → 1.54); config, httpparse, wordfreq, textops, json and tokenizer are byte-identical at full; every other program 0.00% ±0.02% at 1/10 | the largest visible win so far and no program slower. The 1/10 profile understated it (logstats −17.8% there) because at the full size the pieces are thin slices of a >4 KiB root, so the positional reader also avoids the copies. |
| txt `b102ace81` + res `87d9cd16f` together (cherry-pick on a temp tree) | service, logstats, sorttext, textops, httpparse, config, wordfreq, json, tokenizer | full workload: service **1,080.94M** (−0.6% vs txt alone, −45.05% vs base), logstats **3,057.51M** (−0.4% vs txt alone, −34.81% vs base), sorttext **1,574.40M** (−0.15% vs txt alone, −8.32% vs base); textops −3.18%, httpparse −2.34%, config −0.48%, wordfreq −0.10% | the two changes are additive and do not interfere: land both. Most of res's own win is subsumed by txt on service/logstats, but it still removes the leftover per-piece retirement and helps textops/httpparse/config/exprparse where txt does not apply. |
| txt head `1a28fa982` (index split ranges once per binding) | service, logstats, sorttext, textops, httpparse, config, wordfreq, tokenizer, json | full workload identical to `b102ace81` (logstats 3,069.51M, service 1,087.31M, sorttext 1,576.80M); at 1/10 logstats improves further (385.5M → 306.7M) and sorttext is 1.5% higher (136.4M → 138.5M) | neutral at the sizes that matter for the gate; the extra indexing helps small inputs only. |
