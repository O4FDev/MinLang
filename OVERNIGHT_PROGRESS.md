# Overnight progress (2026-10-10)

Brief: ~/overnight/briefs/minyar-lang.md. Status beacon: ~/overnight/status/minyar-lang.log.

Worktrees:
- ~/Projects/Minyar-Lang-v2: branch `v2` (the reconciliation; suites run here, logs in /tmp/v2logs)
- ~/Projects/Minyar-Lang-list: branch `perf/macos-list` (Phase 2 work, to merge into v2)
- ~/Projects/Minyar-Lang-astra: branch `port/astra-cycles` (Astra port; NOT merged, user decision)
- ~/Projects/Atacama-desktop-app: now a git repo; branch `v2-list` uses mac.list; tests/profile/ has the stub server and driver

## Done
- All dirty worktrees snapshotted; docs/v2-reconciliation.md
- v2 = 0be01e7 + appkit + minyar-os; check-portable and check-modules green on v2
- perf/macos-list: macos.list (Atacama history 10.2x), 60 Hz wake throttle (streaming 4.3x),
  leaf functions skip the call-depth guard (Minyarcraft -20%, compiler -10%), unified http
- docs/v2-performance.md (ranked, with numbers)
- Minyar-OS boots in QEMU (desktop ready 632 ms); Minyarcraft builds

## In flight
- v2 suites: check-http, check-tls, check-macos, check-ownership, check-peer-semantics, check-peer-sanitize

## Next
1. When v2 suites are green: push v2
2. Merge perf/macos-list into v2; rerun check-portable, check-macos, check-http, stack overflow; push
3. Point Atacama's Makefile at ../Minyar-Lang-v2
4. MORNING.md + html_render summary (by 10:45)
5. More profiling if time: Astra overhead, OS kernel compile cost
