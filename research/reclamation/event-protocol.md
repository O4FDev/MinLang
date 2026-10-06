# Continuing-load experiment, version 1

Specified before timing the compiled workload on the research branch. Goal:
decide whether scheduler choice and budget-dependent stack ownership improve
event processing beyond finite graph-drain microbenchmarks. A negative result
is useful; no paper-worthy benefit is assumed.

## Workload and comparison axes

`event_workload.min` compiles with the ordinary Minyar compiler. It maintains
four rolling snapshots of records with text and numeric histories. Every 256th
event rebuilds one snapshot, sharing one quarter of its previous rows. Other
events update a 257-element numeric table and access a snapshot row. Each event
also calls two leaf functions holding five/eight text owners, one with a slice.
The retained LLVM must demonstrate heap-only versus actual stack admission.
The C harness supplies arrivals/timing and roots; event logic is generated LLVM.
An independent Python implementation produces every expected event result.

1. Scheduler axis: eager, FIFO, LIFO, fair-unit, current; identical **heap-only
   LLVM** for all policies. Incremental budgets K1/K8/K32. Eager differs in owner
   representation and is a total-profile baseline, not a scheduler-only ablation.
2. Ownership axis: current scheduler at K8/K32, comparing that same heap-only
   LLVM with compiler `--bounded-owners K` output. Expect five-owner admission at
   both budgets and eight-owner admission only at K32. No compiler patch.

All use the system allocator, disabled integer-text cache, the same C compiler
and `-O2`, without LTO. This intentionally holds cross-language inlining constant;
results must not be described as release/LTO performance. An LTO study is follow-up.

## Arrivals and recovery

Timing: 8,192 events in four cycles, width 1,024, three seeds (271828, 314159,
161803), fixed mean spacings 10 µs and 50 µs, steady or 16-event simultaneous
bursts. Arrival times are prescribed independently of completion. Response is
completion minus scheduled arrival, including all waiting. Keep slow samples.
Analyze rebuild events and ordinary events separately as well as overall.

Each cycle has a predeclared 10 ms quiet window after its scheduled final event
interval. The harness polls during the remaining quiet window, then waits for
the next predetermined arrival. If processing overruns that window, it is not
silently extended. Record pending tasks before/after, time to empty when possible,
and event lateness at the window end. Complete remaining debt after the last
cycle and include it in lifecycle wall time. A finite successful drain is not a
proof of infinite backlog stability. Three process replicates cannot certify
rare deadline-miss probabilities.

Diagnostic campaigns omit pacing and timing. They execute the same workload
and use a preallocated, independent traversal of source roots at each event
boundary to distinguish live requested managed bytes from retained dead managed
bytes. Retained heap-owner frames/chunks/caches are measured separately; these
boundary measurements do not include active stack-frame storage. Sanitizer runs stay
separate. Diagnostic quiet windows use complete drains, so they establish
accounting/correctness and event-to-event debt, not timed-window recovery.
Small smoke validation uses 512 events/width 32. The diagnostic matrix uses
2,048 events/width 128; it does not establish memory behavior at timing sizes.

## Evidence and decision

Retain frozen runtime/compiler/fixture inputs, compiler binary, LLVM for each
ownership policy, generated-code admission checks, exact commands, hashes,
all expected/actual results, raw event/recovery traces, host/compiler metadata,
and failure logs. Randomize serialized timing processes with a recorded seed.
Use per-process nearest-rank percentiles; do not pool samples across seeds.
Diagnostic instrumentation must not appear in timing binaries.

Report latency, completed workload/lifecycle time, event debt trajectories,
quiet-window recovery, and owner-storage costs. No subtraction of unrelated
percentiles. A smaller median alone is insufficient: examine ordinary-event
tails, rebuild tails, total work and memory together. Without a consistent
benefit or a new defensible guarantee, keep this as an engineering study rather
than declaring a novel research result.

This is an application-shaped synthetic workload, not production traffic,
networking, an exchange simulator, or proof of suitability for trading.
