# Follow-up assessment

This stage produces a runtime correction and a reproducible compiled-workload
study. It does not yet establish a novel research contribution.

## Contract correction

The K1 Text-view counterexample is fixed by queuing a newly unreachable backing
root for its own work unit. The fixed reproducer observes one destruction, one
remaining root, and complete recovery after polling. It passes natively and
under ASan/UBSan. The targeted matrix passes all 24 allocator/budget/sanitizer
configurations, checking actual object destruction as well as reported work.
The public contract and [formal notes](formal-model.md) now describe this case.

`make check-bounded check-memory-profiles check-stack-ownership` and
`make check-runtime-unit` also passed. This includes the existing graph/frame
oracles, fused-work checks, 42 focused memory-profile checks, and 40 stack/fallback
configurations. These are the relevant targeted suites; the entire `make check`
target was not run.

The fix preserves the work-unit definition. It adds a possible delayed root
destruction, rather than proving a CPU-time or retained-space bound.

## Actual scheduler fairness

With an old 8,192-field object, competing local/temporary queues, and 1,536 new
arrivals, current and fair-unit each advance the old object 256 fields. FIFO
advances it 512 fields; LIFO advances it zero. All four process 512 local owners.
Native and sanitizer runs agree and recover all storage after the arrivals stop.

This is evidence for active-head progress under competing arrivals, and an
actual-runtime starvation example for LIFO. It does not establish a fairness
advantage over FIFO, a uniform waiting bound for every object, or a space bound.

## Compiled workload

The [protocol](event-protocol.md) separates scheduler choice using identical
heap-only LLVM from the compiler's budget-dependent stack policy. Independent
oracles check every event's result and live managed memory. All 45 native and
45 sanitizer diagnostic runs passed, with matching accounting summaries.

At diagnostic width 128, K32 stack admission reduces retained heap-owner storage
at event boundaries from 288 to 96 bytes. This excludes active stack storage;
it is a small cache reduction, not a claim about whole-program peak memory.
At K8, current retains up to 7,056 dead managed bytes, versus FIFO's 5,403 in this
workload. The current scheduler therefore has no across-the-board retention win.

See [timing and retention tables](event-results.md) for the complete measurements,
including independent arrival schedules, rebuild tails and quiet-window recovery.
The study uses one synthetic application shape, three seeds and one host; it
cannot establish production latency, rare-event guarantees or general superiority.

All 180 timing runs passed their event oracles and trace checks. At 10 µs steady
arrivals, K32 heap-only current has ordinary-event response p99s of 183–196 µs,
versus FIFO's 174–182 µs and eager's 144–154 µs across the three processes. Small
ordinary service times do not prevent waiting behind snapshot rebuilds. Current
does not win this comparison. At the same arrival pattern, K8 stack admission
changes total event service by ratios of 0.964–1.075 and worsens response p99 in
all three matched seeds; stack admission is not an established latency win.

Other arrival patterns have mixed rankings and several millisecond-scale
outliers. All were retained; this campaign does not identify their causes or
support treating a large ratio from one process pair as an optimization effect.
All 720 quiet windows ended without pending tasks or overrun, under the stated
finite workload and 10 ms windows. This is not an overload or capacity guarantee.
Only 192 windows began with debt, with at most three tasks pending, so this
campaign barely exercises recovery from debt remaining at a cycle boundary.

## Research decision

The candidate remains a shared reclamation contract for heap objects, detached
local/temporary owners and compiler-selected stack frames. The
[implementation inspection](related-work.md#follow-up-implementation-inspection)
makes the comparison with CTRC more concrete, without establishing priority.

A publication claim still needs a preservation/refinement proof covering actual
lowering and optimized scheduling, a broader root-processing prior-art audit,
and an external implementation comparison or a useful guarantee that the closest
systems lack under comparable assumptions. The bug fix and finite fairness result
are useful prerequisites; neither is itself evidence of novelty.

## Local evidence

- [Historical failing Text release](../../build/reclamation-text-bound-evidence/results.json)
- [Fixed Text release](../../build/reclamation-text-bound-fixed/results.json)
- [Continual-arrival C fairness](../../build/event-load-fairness/results.json)
- [Compiled native diagnostics](../../build/event-load-diagnostic/results.json)
- [Compiled sanitizer diagnostics](../../build/event-load-sanitize/results.json)
- [Broader regression log](../../build/reclamation-regression.log)
- [Runtime unit log](../../build/reclamation-runtime-unit.log)
- [Validation and stash-preservation manifest](../../build/reclamation-validation/results.json)
- [Compiled timing manifest](../../build/event-load-timing/results.json)

The ignored `build/` evidence is local and removed by `make clean`. Preserve it
before cleaning if these measurements will be used in a paper or shared report.
