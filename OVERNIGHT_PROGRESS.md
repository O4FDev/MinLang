# Overnight progress (2026-10-10)

Brief: ~/overnight/briefs/minyar-lang.md. Status beacon: ~/overnight/status/minyar-lang.log.
Suite logs: /tmp/v2logs (summary.log; round1/round2 hold earlier runs).

Worktrees:
- ~/Projects/Minyar-Lang-v2: branch `v2` (pushed at b8e0ca1; perf work merged locally since)
- ~/Projects/Minyar-Lang-list: branch `perf/macos-list` (Phase 2 work; merged into v2)
- ~/Projects/Minyar-Lang-astra: branch `port/astra-cycles` (NOT merged; decision for the user)
- ~/Projects/Atacama-desktop-app: git repo (new); branch `v2-list`; builds against ../Minyar-Lang-v2

## Done
- Snapshots of all dirty worktrees; docs/v2-reconciliation.md; v2 green on all suites and pushed (b8e0ca1)
- Phase 2 (docs/v2-performance.md): macos.list, 60 Hz wake throttle, leaf frames, indexed-store
  borrow, Text field append, symbol ordering, unified http, review and simplify passes
- Bug from the simplify pass (state slot 14 vs ownership map) found by check-modules and fixed,
  with a deterministic regression test

## In flight
- Full suites on merged v2 (summary in /tmp/v2logs/summary.log), then push v2 again
- Astra agent: inlining traced fast paths (port/astra-cycles)

## Next
1. Push v2 when green
2. Atacama on v2: make, make test, driver numbers, screenshots
3. Minyar-OS on v2: boot in QEMU and compare frame profiler against b8e0ca1
4. MORNING.md + html_render summary (by 10:45)
5. Decide what to say about Astra (merge recommendation)
