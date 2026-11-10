# Minyar overnight run @RUN_NAME@: charter for every lane

Goal for the night: @GOAL@ The run ends at @END@. Your brief names your lane and its scope.
`C=@RUN_DIR@`.

## Rules
- Work in your own git worktree on your own branch. Never edit the main checkout `@REPO@` or commit on
  `@BRANCH@`. Stay inside your lane; a finding for another lane is one line in `$C/reports/cross-lane.md`.
- Read `AGENTS.md`, then the docs it names for the area you change. Commits: one-line Conventional Commits, made
  with `git -c core.hooksPath=/dev/null commit ...` (the inherited hook builds locally).
- The machine is shared by every lane. Builds, check targets, benchmarks and fuzz runs go through
  `$C/heavy <command>` (first come, first served slots). Anything under 90 s on one core (one compile,
  `minyar --check`, one small program, one narrow check) goes through `$C/light <command>` (its own queue, killed
  at 120 s). Never run two heavy commands at once yourself. No `make -j` above 4. Keep one warm `build/`; no extra
  worktrees or build trees. Remove scratch output when done; never commit `target/` or `build/` output.
- Free services only. Do not start sub-agents unless your brief says so.
- Fixes are general and principled. Never special-case a benchmark, never weaken, delete or loosen a test or an
  expected output to get green, never trade away a language guarantee: write it under "Decisions for Luke".
  Say plainly which changes are workarounds.
- Performance claims need retired-instruction counts or n >= 3 interleaved timings with spread, plus
  byte-identical output.
- Nothing is pushed except by the train. Never force-push, never rewrite `@BRANCH@` history.

## Landing
Work in small units. For each: the narrowest `check-*` target, then `$C/heavy ./minyar dev check` (or
`make check-changed`), then from your worktree `$C/land.sh <lane>` in the background. The train stacks every
queued lane on `@BRANCH@`, runs one gate in the gate VM, and fast-forwards and pushes on green. On red it reruns
only the failing checks per lane to find the culprit. `LAND-RED` lists checks that fail on your branch but pass on
base (`$C/base.fail`): fix them, or show with evidence that a check is flaky on base and retry once. After
`LAND-GREEN`, `git rebase @BRANCH@`. Land at least once by @FIRST_LAND@; last attempt by @LAST_LAND@.

## Report
Keep `$C/reports/<lane>.md` current: first line `STATUS: <one sentence, with time>`, then findings with
commands and numbers, what landed (SHAs), "Decisions for Luke" and what remains.
