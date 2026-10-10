# Overnight progress (2026-10-10)

Brief: ~/overnight/briefs/minyar-lang.md. Status beacon: ~/overnight/status/minyar-lang.log.
Suite logs: /tmp/v2logs (summary.log; roundN/ hold earlier runs). MORNING.md is the report.

Worktrees:
- ~/Projects/Minyar-Lang-v2: branch `v2` (pushed at b8e0ca1; perf work merged locally, final run in progress)
- ~/Projects/Minyar-Lang-list: branch `perf/macos-list` (Phase 2 work; merged into v2)
- ~/Projects/Minyar-Lang-astra: branch `port/astra-cycles` (NOT merged; decision for the user)
- ~/Projects/Atacama-desktop-app: git repo (new); branch `v2-list`; builds against ../Minyar-Lang-v2
- /tmp/v2-base: detached checkout of b8e0ca1 for before/after measurements

## Done
- Phase 1: snapshots, reconciliation doc, v2 green and pushed
- Phase 2: changes 1-10 in docs/v2-performance.md, code review, simplify, an 8-agent review
  workflow (found a use-after-free, fixed), adversarial attack workflow running

## Next
1. Final v2 suite run green -> push v2 (git push origin v2)
2. Minyar-OS boot comparison base vs final (/tmp/bench/os-compare.sh)
3. Refresh MORNING.md numbers, copy to ~/Projects/Minyar-Lang/MORNING.md, html_render
4. Stop the stub server on port 47391; remove /tmp worktrees (atacama-before, atacama-astra, v2-base)
