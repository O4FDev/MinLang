# Overnight progress (2026-10-10)

Brief: ~/overnight/briefs/minyar-lang.md. Work happens in the `v2` worktree at
~/Projects/Minyar-Lang-v2. Status beacon: ~/overnight/status/minyar-lang.log.

## Done
- Snapshotted all dirty worktrees (see docs/v2-reconciliation.md)
- v2 = 0be01e7 + merge appkit + merge minyar-os (http split into http / http1)
- docs/v2-reconciliation.md

## In flight
- make check-portable on v2 (log /tmp/v2logs/portable.log)
- Astra cycle port in ~/Projects/Minyar-Lang-astra (branch port/astra-cycles), by a subagent

## Next
1. Fix check-portable failures, then peer-semantics, peer-sanitize, ownership, macOS/HTTP/module suites
2. Atacama app build + tests against v2; Minyar-OS QEMU boot; Minyarcraft build
3. Push v2
4. Merge Astra port once green
5. Phase 2 profiling: NSTableView path, streaming throttle, unified http, compile times
