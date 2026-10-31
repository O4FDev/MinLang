# "Have our cake and eat it too" swarm — results (2026-10-31)

Question (Luke): can we get the speed without the cost — no documented-behaviour change, no API break, no lost guarantee?
13 Wafer Code agents (DeepSeek V4.1 Flash), ~160 measured attempts, Opus coordinating. Per-agent attempts tables:
`~/Projects/minyar-goal-20261030/reports/cake/c1.md … c13.md`. Ir = cachegrind instructions on box H/I–L (AMD), all
outputs byte-identical to C/C++/Rust. "Merged" = on `goal/2026-10-30` after a full gate (single-box or sharded).

## Results
| id | target | approach that worked | Ir delta (main programs) | wall | guarantee kept | API unchanged | merged |
|---|---|---|---|---|---|---|---|
| c1 | empty Lists (json leaves) | lazy empty List blocked by reference semantics (aliases must see adds); kept: first List growth = 4 slots | json −1.1%, textops −1.6%, intmap −1.0% | json −3.1% | yes | yes | **yes** |
| c2 | json debt, API unchanged | integral numbers / `asInteger` via a byte-scan fast path (no decimal round trip) | json −13.4% | json −6% | yes (708 number oracles + 60k differential) | yes | **yes** |
| c3 | scheduler unit (T4b) | 8 fields per unit; alone still +0.6–0.95% on 5 programs; the "−3.4%" proposal leaked fields | — | — | yes | yes | superseded by c4 (its first commit is in c4) |
| c4 | eager speed, bounded pauses (T4) | **one unit retires a bounded small subtree** (≤8 slots, ≤8 aggregates, constant work) | exprparse −10.8%, json −10.5%, service −4.8%, logstats −2.8% | json **−25%**, service −16%, exprparse −5.6% | yes (K-unit bound per service point kept; contract text updated) | yes | **yes** |
| c5 | region freeing (T5) | static inference rejects 96–98% of functions; opt-in mechanism built (env flag, not merged) | 0 to +0.4% on accepted set | — | — | — | no (see decision D2) |
| c6 | allocator fast path | one static page per small-heap size class for single-object churn | alloc+free pair 518 → ~110 Ir; transient-List micro −59%; exprparse −0.7% | — | yes | yes | **yes** |
| c7 | bounds checks proved away (T2) | one window test before a versioned loop, unchecked reads inside, same error message outside | topk **−9.3%** (1 and 4 threads) | topk −19% @1 | yes (checks stay; messages identical) | yes | **yes** |
| c8 | Unicode at ASCII speed (T3) | Text scanning loops versioned on one counted-ASCII test (capped at 2000 pieces) | exprparse −4.0%, tokenizer −5.1% | — | yes (`t[i]` semantics unchanged) | yes | merged, then **reverted** (84e2e01a3): a hidden program's nested loops make the versioning emit a duplicate LLVM value (`value.N.fast8.fast4`) — compile failure; passed every visible check |
| c9 | parallel tasks that allocate (T7) | `parallel for` bodies own worker-local Text/records/Lists, drained per chunk | 0 on all serial programs | demo 1.7× @4 | yes (race freedom; no escape) | yes (additive) | **yes** |
| c10 | collection teardown / per-unit cost | word+ctz next-owner scan, inlined slot frees (built on c3) | exprparse −1.3%, logstats −1.3%, json −1.1% | — | yes | yes | no — being re-based on c4 (next session) |
| c11 | shared frozen input | `frozen.decode(frozenBytes, start, end)` zero-copy Text views | shared-input join 3.7× fewer Ir | 2.5× @4 | yes (TSan) | yes (additive) | **yes** |
| c12 | Map single probe | inlined Map entry points, `has`/`getOr` miss remembers the slot for the next insert, unzeroed grow | intmap −14.4%, wordfreq −7.2%, tokenizer −3.1% | intmap −9% | yes (iteration order pinned) | yes | **yes** |
| c13 | Text chains + sort compares | every Text `+` chain as one sized write; one three-way compare per (a,b); per-site merge for record sorts | sortrows **−27%**, sorttext −15% | sortrows CPU −7.6% | yes | yes | **yes** |
| o5fix | hidden regression in ownership5's lowering | inline boxing in wrappers, inline take for stored values | treewalk −6% more; probe shapes back to ≤ base (one at +4%) | — | yes | yes | **yes** |

Visible compare suite (22 programs, vs fastest of C/C++/Rust): **2.69 → 2.52** after the c8 revert (vs Rust 2.17 → 2.03; 2.51/2.02 with c8) across the swarm
merges; json 8.51 → 6.38, exprparse 5.74 → 4.74, treewalk 1.89 → 1.77, sortrows 2.64 → 1.92. Hidden: see goal-status.md.

## Harness turnaround (`minyar dev check`, reports/harness.md)
- Docs edit 166 s, untouched test 24 s, `.mk` + new tests 22 min (correctly RED), compiler/runtime change = all checks.
- Full gate: ~19–25 min on one 8-vCPU box; **sharded 3 ways (M/K/J, clean builds included): 10.5 min wall**.
- Real catches: a use-after-free in the Result-in-registers lowering (BASE-RED finding), the loop-versioning compile
  OOM (c8 uncapped), and three fixtures pinning old unit counts (c4).

## Decisions still for Luke (each with the consequence in code)
- **D1 — c10's recent-first-with-minimum-share cleanup order** (exprparse −2.8%, json −1.2% measured for pure
  recent-first; the bounded variant with ≥1-in-8 old-batch share and the sustained-load retention test were not finished).
  User code: no observable difference (no finalizers; deterministic either way); only `docs/bounded-runtime-contract.md`
  wording about alternation changes.
- **D2 — opt-in `region { … }` block** (c5; ceiling −29% to −76% Ir on parse-then-drop programs):
  ```
  before:  let tree = parse(line); total += eval(tree)          // per-object teardown
  after:   region { let tree = parse(line); total += eval(tree) } // one bulk free at exit; escaping `tree` = compile error
  ```
  New syntax, so held per Luke's "no new arena syntax for now".
- **D3 — json member lookup index** (c2): needs a private field on `json.Value`, which breaks `json.Value { … }` record
  literals (6 repo tests); only wins from ~32 members.
  ```
  before:  let v = json.Value { kind: json.OBJECT, keys: k, items: i, … }   // compiles today
  after:   same literal fails: missing private field `index` (needs a constructor function instead)
  ```

## Not merged, worth having (next session's first batch)
- **c8 Text loop versioning** (`goal/cake-c8` 821bca9bb; exprparse −4%, tokenizer −5%): fix nested versioning so a loop copy inside an already-versioned region gets unique value names (repro shape: a Text scanning loop nested inside another versioned loop → `multiple definition of local value named 'value.N.fastA.fastB'`), add that shape to tests, re-gate, re-score hidden.
- c10 re-based on c4 (branch `goal/cake-c10-on-c4` if the agent finished; else `goal/cake-c10` 257edb3b4 on c3's d0f9d338a).
- c5 region mechanism (`goal/cake-c5` 663771786, a7e041b0d) — opt-in, only if D2 is approved.
- c1's header-recycling attempt (treewalk −9.3%) — blocked by a latent double-release in borrow bookkeeping (fix first).

## Spend
Wafer Code for the swarm (14:20 UTC on): see the final line in goal-status.md. Boxes: H, I–L, M–O within Luke's $10.
