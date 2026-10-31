INDEX READY (14:33 UTC): /home/agent/swarm/harness/build/dev-check/index.json (337 checks of check-portable, base =
goal/2026-10-30-harness 253b28805 = cake-base + dev-check). Copy it to <tree>/build/dev-check/index.json. 7 base reds and
check-debugger-values (ptrace, untraceable) run on every invocation (~1 min); a seed whose build is partial gets one
wider first run while Make builds the missing outputs.

# Lane harness: `minyar dev check`

FINDING for the orchestrator: goal/cake-base 9aa49c5f1 is RED on box H, untraced: check-last-use-sinks
("propagated: local owner moves" at tests/last-use-sinks.min:43), check-determinism-runtime, check-record-reconstruction-reuse,
check-structured-tasks, check-quic-official-adapter (+ check-quic-rfc which depends on it). dev-check reports these as BASE-RED. The orchestrator is bisecting this catch (box H dirs bis-goal = aa151eb22 without
batch 8, bis-int8 = 6a19fe3e2 = batch 8 without per-field TBAA; results in logs/bisect-*-H.log); conclusion to be added by
the orchestrator.
Second real catch (orchestrator, 14:30): the full batch-9 gate on box H (goal/integrate-9 = cake-base + ownership5) failed
10/339 = the six base reds above + check-choice, check-choice-set-niche, check-ownership-name-proofs (new in batch 9).

STATUS 14:22 UTC: not ready yet. Traced base index on box H is at 300/336 checks (box shared with the int9 gate);
validation (B5 red run, greens, compiler/runtime plans) follows immediately; expected ~14:15 UTC.
Branch goal/2026-10-30-harness has the tool (tools/dev-check.py, `./minyar dev check`, docs/dev-check.md).

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
