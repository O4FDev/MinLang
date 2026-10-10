# Overnight progress (2026-10-10)

Brief: ~/overnight/briefs/minyar-lang.md. Status beacon: ~/overnight/status/minyar-lang.log.
Suite logs: /tmp/v2logs (summary.log; round*/ hold earlier runs). Scratch: /tmp/mlperf (scripts, variants, logs).

Worktrees:
- ~/Projects/Minyar-Lang-v2: branch `v2` (pushed at b8e0ca1; 465c8fa = merged perf work, suites green, push pending)
- ~/Projects/Minyar-Lang-list: branch `perf/macos-list` (Phase 2 work; second session's commits b515b60..c68ac2a)
- ~/Projects/Minyar-Lang-stream: `perf/text-stream` (subagent: Atacama streaming text cost, report due 09:15)
- ~/Projects/Minyar-Lang-craft: `perf/craft-frames` (subagent: Minyarcraft steady-state frames, report due 09:15)
- ~/Projects/Minyar-Lang-astra: `port/astra-cycles` (NOT merged; decision for the user)
- /tmp/mlperf/v2base: detached v2 465c8fa, clean baseline build for before/after numbers
- ~/Projects/Atacama-desktop-app: git repo, branch `v2-list` (stream agent may add `v2-stream`)

## Done (second session, from 06:51)
- v2 suites on 465c8fa: portable, modules, driver options, regressions, http, tls, macos, graphics-render,
  codegen, incremental-modules, stack-overflow-sanitize, ownership, peer-semantics green; peer-sanitize running
- docs/v2-performance.md 11: check-budget passes (inline Text equality, writeTextFile(path, List<Text>),
  shorter call-depth guard): self-compile 80.40M -> 72.18M, 10.81 -> 9.23 MiB; Minyarcraft 16.44G -> 15.74G
- docs/v2-performance.md 12: x = x.appended(e) appends in place when unique; json history 4.0x at 5,000 runs
- Review of 11 found a fallback-cap bug (stack-limits test) -> fixed 7276d07

## In flight
- v2 peer-sanitize, then extra.sh (native-graphics, toolchain-portability), then push v2
- Review agent on 7aa535f (appended soundness)

## Next
1. Push v2 when green
2. check-portable + ownership + peer suites on perf/macos-list (validates 11 and 12)
3. Merge agent branches (text-stream, craft-frames) after review; merge perf into v2; full suites; push
4. MORNING.md + html_render summary (start 10:45); draft in /tmp/v2logs/MORNING.draft.md
5. Astra decision text stays as in the draft
