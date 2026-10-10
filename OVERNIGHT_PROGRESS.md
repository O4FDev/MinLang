# Overnight progress (2026-10-10)

Brief: ~/overnight/briefs/minyar-lang.md. Status beacon: ~/overnight/status/minyar-lang.log.
Suite logs: /tmp/v2logs (final/ = the run on the merged v2). Scratch: /tmp/mlperf.

Worktrees:
- ~/Projects/Minyar-Lang-v2: branch `v2`. Pushed at 465c8fa (08:05, all suites green).
  Local 5b27714 adds the second session's work and both subagents' branches; final suites running.
- ~/Projects/Minyar-Lang-list: `perf/macos-list` (my Phase 2 commits)
- ~/Projects/Minyar-Lang-craft: `perf/craft-frames` (subagent, merged)
- ~/Projects/Minyar-Lang-stream: `perf/text-stream` (subagent, merged)
- ~/Projects/Minyar-Lang-astra: `port/astra-cycles` (NOT merged; decision for the user)
- /tmp/mlperf/v2base: detached v2 465c8fa, the clean baseline for before/after numbers
- ~/Projects/Atacama-desktop-app: git repo, branches `v2-list`, `v2-stream` (current; needs v2 >= 5b27714)

## Done (second session, from 06:51)
- docs/v2-performance.md 11-17 (budget, appended, draw state, guard, call trees, ThinLTO, Atacama streaming)
- Bugs: Text/List in-place growth on parameters and re-read locals (pre-existing for Text), guard cap, tree pass
- Atacama builds against v2 5b27714; make test and make check pass. Minyar-OS boots (568 ms).
- MORNING draft: /tmp/v2logs/MORNING2.md; summary page: /tmp/v2logs/summary.html

## In flight
- /tmp/v2logs/final.sh on v2 5b27714 (summary in /tmp/v2logs/final/summary.log)

## Next
1. When final suites are green: push v2, then commit MORNING.md and push again
2. html_render the summary page (fill SUITES_STATUS)
3. If a suite fails: fix on v2, rerun that suite only
