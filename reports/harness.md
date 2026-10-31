HARNESS V2 READY (19:35 UTC): compiler and runtime changes are selected by the functions they change.
Index: /home/agent/swarm/harness/build/dev-check/index.json (= index-v4.json: file trace + per-check function coverage,
337 checks; base = goal/2026-10-30-harness at ae948c628..1d936135f, i.e. cake-base + dev-check). Needs the tool at branch tip
1d936135f or later (older tools read the same index but ignore the function data). Command unchanged: `./minyar dev check`.
Proof: mutation full gate (runtime minyar_map_remove + compiler constantOverflow message; 10 mutation-caused failures):
dev-check selected all 10, missed none. Compiler-stage function edit alone: 78/337 checks, RED in 700 s on exactly the
failing check (check-compile-time-constants). Runtime-header function edit (minyar_map_get_or, run by 1 check): 90/337.
Batch B4 (recorded red check-last-use-sinks) is fully function-attributable: its 13 changed compiler functions are executed
by 215 checks including check-last-use-sinks.

HARNESS READY: `./minyar dev check` (= `make dev-check` = `python3 tools/dev-check.py run`; `--plan`, `--only PATH`,
`--bench --bench-base FILE`, `--include-base-red`). Branch goal/2026-10-30-harness, tip de678b88b.
Index (box H): /home/agent/swarm/harness/build/dev-check/index.json, replaced 16:23 UTC by the re-parsed v2 (nested-Make goals,
fixed retry statuses; same base). The 253b28805 copy is at /home/agent/swarm/harness-val/index-253b28805.json.
Agents on 253b28805 should cherry-pick up to de678b88b: the content cutoff (496cac274) and file-rule-by-recipe (e210ead6d)
are what keep a .mk / new-file change from selecting everything.

## Agreement: harness vs recorded full gate
| batch (tip) | change | gate | dev-check | agree |
| --- | --- | --- | --- | --- |
| B2 153ad7ee5 | compiler (text lowering) + tests | red: check-language-contracts | compiler sources → build/minyarc stale → all 337 selected, i.e. it runs the gate's check set; not rerun (Luke: no gate reruns) | yes by construction |
| B4 978516b86 | compiler (codegen) + docs | red: check-last-use-sinks | same: all 337 | yes by construction |
| B5 2d2a3804b | benchmarks.mk rule, new tests/ablation/*, minyar, run.py, reports | red: suite-catalogue → build-wiring, peer-manifest, peer-regressions* | RAN (replayed on the indexed tree): 115 selected, RED: suite-catalogue, build-wiring, peer-manifest, peer-regressions-rust-go-zig | yes |
| B3 bb87f78f4 | compiler + runtime | green 335/335 | all 337 (plan) | consistent |
| B6 908aec3ab | runtime + compiler | green 338/338 | all 337 (plan) | consistent |
| B7 1ddea7b87 / runtime-only fd83e1930+1ddea7b87 | runtime | green 339/339 | all 337 (plan; runtime headers feed runtime.o and the compiler runtime) | consistent |
| base cake-base 9aa49c5f1 | — | (no record) | index run: 6 checks red at base (see FINDING) | confirmed by orchestrator's batch-9 gate (same 6 + 3 new) |
| docs edit (synthetic) | docs/language.md | — | 4 selected, GREEN 166 s | — |
| test edit (synthetic) | tests/http.min | — | no Linux gate check reads it; GREEN 24 s | — |
Not done in the time box: replays of glib (c26af6a9d), gnative (e1fc31110), gtest (bd48818de), gmk (8810e3f0b), gdocs, and a
narrow library edit (tar) — gnative was running when the box got saturated; first attempt selected 271 checks because
file rules were compared by prerequisite list (fixed in e210ead6d, not yet re-measured).

## Turnaround (box H, 8 vCPU shared with ~10 agents, --jobs 4)
| change | rebuild | checks | wall |
| --- | --- | --- | --- |
| docs edit | cutoff build 10 s, 0 changed | 4 | 166 s |
| test edit not in the Linux gate | 6 s | 0 (+1 untraceable) | 24 s |
| .mk rule + new test files (B5) | cutoff 206 s (338 outputs rebuilt, 0 bytes changed) | 115 | 1,310 s (RED) |
| library module used by the runner (json) | 151 s, 220 changed | 337 | = gate (aborted) |
| compiler pass edit | build/minyarc 52 s (stage1+stage2, thin-LTO cache; stage0 only for bootstrap/) | 337 | = gate |
| runtime header edit | runtime.o + compiler runtime | 337 | = gate |
| full gate | — | 336-339 | 22-24 min at CHECK_JOBS=8 (orchestrator); traced index gate 57 min at 4 jobs on the shared box |

## What remains
- Precision: new files are seen by every check that lists their directory (`tests`, `.`, `tools`); 30+ checks list
  tests/. Next: record which listed entries a process then opens and match by name pattern, or find the shared lister.
- Compiler/runtime-core changes are honest (= gate). Real narrowing needs per-check coverage of compiler functions
  (IR-level PGO instrumentation of minyarc) — not started.
- `rebase` after reverting core sources rebuilds everything (282-449 s); fine for validation, irrelevant for agents.
- macOS-only checks are not covered (Linux index).

INDEX READY (14:33 UTC; base = goal/2026-10-30-harness 253b28805 = cake-base + dev-check). Copy it to
<tree>/build/dev-check/index.json. check-debugger-values (ptrace) cannot be traced and runs every time; since 8beeca6e0
base reds are listed, not rerun. A seed whose build is partial gets one wider first run while Make builds the missing outputs.

# Lane harness: `minyar dev check`

FINDING for the orchestrator: goal/cake-base 9aa49c5f1 is RED on box H, untraced: check-last-use-sinks
("propagated: local owner moves" at tests/last-use-sinks.min:43), check-determinism-runtime, check-record-reconstruction-reuse,
check-structured-tasks, check-quic-official-adapter (+ check-quic-rfc which depends on it). dev-check reports these as BASE-RED. The orchestrator is bisecting this catch (box H dirs bis-goal = aa151eb22 without
batch 8, bis-int8 = 6a19fe3e2 = batch 8 without per-field TBAA; results in logs/bisect-*-H.log); conclusion to be added by
the orchestrator.
Second real catch (orchestrator, 14:30): the full batch-9 gate on box H (goal/integrate-9 = cake-base + ownership5) failed
10/339 = the six base reds above + check-choice, check-choice-set-niche, check-ownership-name-proofs (new in batch 9).


## Design (12:40-13:00 UTC)
- Existing `check-changed`/`tools/check-selection.min` treats every compiler/runtime path as "bounded" (core checks only)
  and maps library modules by a hand table: not safe against a false green. Kept it; added a separate tool.
- `tools/dev-check.py`: dependency index from one strace'd gate on the base tree (per check: paths opened/stat'ed/exec'd,
  directories listed; Make parse excluded), content-hash change detection with content-true mtimes (rsync'd trees cannot
  look up to date), Make's own `-n --debug=b` for stale outputs, Make rule/variable diff, always-run for new / untraced /
  base-red checks. Runs the selection through check-in-parallel.
- Compiler / runtime-core change => almost every check reads build/minyarc or links minyar-runtime.o => close to the
  gate; reported as such (no pretend narrowing).

## Log
- 12:46 traced index gate started on box H (/home/agent/swarm/harness, cp -a of base, CHECK_JOBS=4).
  strace -f --seccomp-bpf -e trace=%file,%process; one strace process ~50% CPU; trace ~100 MB/min.
- Make dry-run finding: build/.toolchain.json depends on FORCE, so `make -n` calls *everything* stale. Fix: run FORCE
  targets for real first (stamp/Cargo rewrite only on change), count them stale only if their mtime moved, `-o` them in
  the dry run. Selection on a clean warm tree: db 0.3 s + stale 0.8 s.
- Compiler edit (comment in compiler/stages/ownership.min) rebuild of build/minyarc on box H: 52 s (stage0 → stage1 →
  stage2, thin-LTO cache); stage0 recompiles only when bootstrap/ changes. Everything downstream is then stale.
- Narrow checks for the harness itself (box H, harness-dev): check-dev-check, check-suite-catalogue, check-build-wiring,
  check-peer-manifest, check-documentation: all passed.
- Under strace, LeakSanitizer (ptrace stop-the-world) fails: check-generated-llvm-sanitizer; quic-official-adapter also
  failed traced. Index retries failures traced with detect_leaks=0, then untraced; anything still untraced is always run.
- 13:44 traced gate finished: 3431 s wall at CHECK_JOBS=4 on a box shared with the int9 gate; trace 3.4 GB;
  24 of 336 failed under the tracer: LeakSanitizer aborts under ptrace (cycle-*-sanitize, generated-llvm-sanitizer,
  update-launch-native, ...), plus quic-official-adapter, debug-info/debugger-values (ptrace), last-use-sinks,
  determinism-runtime, net, osdev-*, managed-graphs-*, record-reconstruction-reuse, structured-tasks.
  Fix: preload a 1-line `__lsan_is_turned_off` hook while tracing (verified: ASan program under strace exits 0 with it),
  retry failures traced, then untraced to separate base reds from tracer-only failures.
- Mistake caught: the retry list included `check-portable` itself (it has its own recipe) → reran the whole gate;
  killed after ~4 min. Aggregate goals are now selected statically from their prerequisites and recipe paths.
- 14:00-14:20 lost to two process-control slips: `pkill -f` patterns matched my own ssh command (exit 255), and a
  killed driver's python kept running so two reindexes interleaved one log. Rerunning one clean reindex (retry only).
- Base results: the runner's results.json lists failures only; per-check pass/time must come from times.tsv (fixed).

## Orchestrator: what the BASE-RED catch was (bisect on box H, 14:35 UTC)
Ran the six base-red checks on box H at two trees (logs/bisect-bis-goal-H.log, logs/bisect-bis-int8-H.log):
- aa151eb22 (goal/2026-10-30 tip, full gate green on box B): only check-determinism-runtime fails on box H → box-H
  environment, not a regression.
- 6a19fe3e2 (goal + ownership4 Result-in-registers, no per-field TBAA): check-last-use-sinks,
  check-record-reconstruction-reuse, check-structured-tasks, check-quic-official-adapter (+ dependent check-quic-rfc)
  FAIL → real regressions from ownership4, which had only been narrow-checked. The batch-8 full gate on box B had not
  finished after 4 h; the harness found them first. The batch-9 gate (box H) additionally failed check-choice,
  check-choice-set-niche, check-ownership-name-proofs (new in ownership5's lowering).
→ Two real catches for the validation table. goal/2026-10-30 stays at the box-B-green tip; ownership4/5 fixes in progress
on goal/integrate-9.
- 14:54 first B5 simulation selected all 337 checks: `build/minyar-runtime.o: ... $(BUILD_RULES)` makes every object
  depend on every .mk file, so Make's graph calls everything stale for any .mk edit (B5 edits benchmarks.mk); and every
  check that runs `./minyar` or a nested `make` read all makefiles. Two fixes, both general:
  1. content cutoff: build the stale outputs first (through check-in-parallel's parallel shared-prerequisite builder,
     via MAKEFILES=build/dev-check/cutoff.mk) and select only by outputs whose bytes changed. Builds are deterministic
     (runtime.o, cycle-runtime.o, a harness binary rebuilt after touching a .mk: byte-identical).
  2. nested building Makes (no -p/-n/-q/-d/-f/-C elsewhere) are treated like the check's own Make: their parse and stats
     are excluded and their goals' rule closures join the check's rule comparison and stale set. Database-printing Makes
     (build-wiring style introspection) keep every makefile read.
- Follow-up (15:20 UTC): the ownership4 regressions behind check-structured-tasks and check-quic-official-adapter /
  check-quic-rfc were a REAL use-after-free: the Result-in-registers lowering dropped a retain when a payload store was
  `minyar_record_set_reference_traced` (library/tasks.min `launch` returning `Ok(operation)` freed `Operation` early).
  Fixed in 589051151 on goal/integrate-9; last-use-sinks / record-reconstruction-reuse were tests reading the boxing
  wrapper instead of `NAME.r` (6d1b98202). Without the harness this would have reached goal/2026-10-30 behind a gate
  that had run 4 h on box B without finishing.
- 15:40 B5 (known red, batch 5 = f51a4f9e0..2d2a3804b replayed on the indexed tree: revert batch+fix, rebase, apply batch):
  cutoff built 338 stale outputs in 206 s, 0 changed bytes; 115/337 checks selected (new files under tests/ and tools/
  are observed by every check that lists those directories; minyar launcher readers); RED in 1310 s on the loaded box:
  check-suite-catalogue, check-build-wiring, check-peer-manifest, check-peer-regressions-rust-go-zig (+ 2 base reds whose
  partial traces were hit). Gate (box G): 9 failures from the same uncatalogued script. AGREES.

## Harness v2: compiler and runtime changes by executed function (16:50 UTC onwards)
- Instrumented gate (box H, /home/agent/swarm/harness-cov): clang wrapper (`build/dev-check/cov/bin/clang`) compiles runtime
  C and compiler IR to objects with `-fprofile-generate -mllvm -pgo-function-entry-coverage -mllvm -runtime-counter-relocation
  -mllvm -disable-preinline`; every link gets the profile runtime and a weak `__llvm_profile_counter_bias`; continuous mode
  (`%c`) keeps counts of aborting programs (verified: an `abort()`ing program's functions are recorded); a `make` shim on PATH
  sets LLVM_PROFILE_FILE=<data>/<check>/%c%p.profraw for each `make -j1 check-x`. minyarc: 1,752 instrumented functions,
  140 KB per profile. Compiler IR names `.minyar.fn.minyar_module_<hash>_<name>` map 1:1 to compiler source functions
  (the compiler is one concatenated module).
- Pitfalls met: llvm-nm shows no `__profc_` in the LTO'd minyarc although it is instrumented (check with llvm-readelf/a run);
  `%4m` online merging + continuous mode gave counter-mismatch/truncated files (use per-pid files); continuous mode prints
  "Neither __llvm_profile_counter_bias ..." on stderr in programs without instrumented code (fixed by the weak symbol);
  deleting build outputs to force rebuilds broke checks that use undeclared artefacts (rebuilt via the runner, restart).
- Function snapshots: compiler 1,259 functions, runtime 2,084 functions; comments/whitespace ignored; anything outside
  function bodies, a signature change, or an added/removed file widens to file-level selection.
- Recorded batches by function (git parent→tip): B4 (978516b86, red check-last-use-sinks) is fully attributable: 13 compiler
  function bodies, nothing else in compiler/ or runtime/. B2, B3, B6, B7, runtime-only and batch 8 all widen (signature or
  struct/macro changes, a new runtime header) — real batches mostly change declarations too.
- 18:05 LLVM 23 findings: `-pgo-function-entry-coverage` makes every runtime-linked program's profile unreadable
  ("number of counters 1 is greater than the maximum number of counters 0"), and continuous mode (`%c`) truncates them; only
  minyarc's profiles were readable (293 checks would have had incomplete coverage). Switched to full IR counters with
  `-pgo-instrument-entry` (executed ⇔ entry counter > 0), plain per-pid files, and `tools/dev-check-coverage/covexit.c`
  (linked into every program: writes the profile on `_exit`/`_Exit`/`abort` via `--wrap` and on fatal signals; verified an
  aborting program keeps its counts). Third instrumented gate started 18:10.
- Mutation full gate (the one allowed rerun; tree = base + M1 + M2, box H, 4 jobs, 4,321 s): M1 = runtime/minyar_maps.h
  `minyar_map_remove` returns 0 for keyed maps; M2 = compiler/constant-evaluation.min `constantOverflow` diagnostic text.
  Failed (beyond the 6 base reds and the aggregate): check-choice-enums, check-choice-layout, check-choice-runtime-profiles,
  check-choice-scalar-niche, check-choice-set-niche, check-compile-time-constants, check-empty-map-traversal, check-maps,
  check-record-capabilities, check-record-collections. dev-check v2 must select all ten.
- 19:00-19:45 v2 validation on the warm harness tree (each mutation measured after `dev-check rebase` to a clean base build;
  a first attempt without rebase measured against the previous mutation's build and selected everything — fixed by procedure):
  | change | rebuilt / bytes changed | selected | verdict | wall |
  | --- | --- | --- | --- | --- |
  | M2 compiler: constantOverflow message (compiler/constant-evaluation.min) | 674 / 22 (121 s) | 78 | RED: check-compile-time-constants (+ base reds hit) | 700 s |
  | N1 runtime header: minyar_map_get_or returns the fallback (runtime/minyar_maps.h) | 684 / 350 (217 s) | 90 | RED: check-stdlib-everyday (the only check that runs it) | 1,022 s |
  | M1 runtime: minyar_map_remove (used by the compiler itself, so compiler output changes) | 684 / 337 | 306 | (stopped; ≈ gate) | — |
  | mutation full gate M1+M2 (4 jobs, shared box) | — | 336 | 10 mutation-caused failures, all selected by dev-check | 4,321 s |
  Most of the 78/90 come from "inspects": checks whose processes read build/minyarc, minyarc-modules, runtime.o or the
  changed source as data (mostly sha256sum for cache keys, cp, the launcher). Kept conservative: hashes can be asserted
  (fixed-point checks compare stage outputs). 26 checks lack complete coverage and are always selected for core changes
  (6 base reds, 5 that fail when instrumented, 4 with an unreadable profile, 11 that emit runtime IR as text).
- Green replays finished on the v2 index (replayed on the warm tree, rebase first; box H toolchain environment required —
  a first attempt without it saw Makefile variables CC/LLVM_CC differ and selected everything):
  | batch | recorded gate | dev-check | wall |
  | --- | --- | --- | --- |
  | gdocs 8968863a6^..aa151eb22 (reports + livepatch bench script) | green (box B 336/336 at 81044253f) | 24 selected (new reports/ files are seen by checks that list `.`), BASE-RED only: check-quic-official-adapter (box H base red) | 277 s |

## Sharded full gate (orchestrator, 2026-10-31 19:43–19:54 UTC)
Final swarm batch (goal + c7 + c8 + c4 + c6 + o5fix), check-portable leaf checks bin-packed longest-first from int14's
times.tsv (9,187 s CPU sum, slowest check-quic-rfc 262 s) into 3 shards on boxes M/K/J, each a clean synced tree built
from scratch: **10.5 min wall end-to-end** (build ~3 min + checks ~7 min), green except the box-environment
check-determinism-runtime. Single-box gate of the same tree on L: ~25 min. Tools: ~/Projects/minyar-goal-20261030/shard/
(plan.py, run-shard.sh, shard-gate.sh, shard-collect.sh).
