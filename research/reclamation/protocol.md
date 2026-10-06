# Scheduler comparison protocol, pilot version 1

Written before the comparative timing runs in this directory. The initial small
diagnostic run checked that the new harness builds and drains correctly. This
protocol makes no acceptance threshold or production-latency claim.

## Questions

1. How do object traversal order and batching affect release latency, poll
   latency, complete-drain time, and post-release retained managed bytes?
2. Does integrating frame/temporary retirement retain the same queued-work
   contract across K=1, ordinary budgets, and large budgets?
3. What claims survive adversarial cases rather than only chains and warm graphs?

## Experimental arms

| Arm | Object policy | Other behavior |
| --- | --- | --- |
| current | Production captured-batch/recent policy with shortcuts | Unmodified runtime snapshot |
| fair-unit | Same policy, including unary-parent ordering exception | Generic one-unit dispatch; no batching/fusion shortcuts |
| fifo | Oldest retired object finishes before later objects | Generic dispatch |
| lifo | Newest retired object advances first; new children can preempt | Generic dispatch |
| eager | Existing immediate iterative destruction | Different eager owner representation; total-profile baseline |

All arms use system allocation and identical source fixtures, C compiler,
optimization level, inputs, and diagnostics mode. The four incremental arms
share the same outer object/frame/chunk rotation and K. They are built from
frozen copies; `variants.py` fails when expected transformation sites differ.
There are no production runtime modifications or configurable experimental
policies in shipped code. Eager is not a scheduler-only ablation.

## Initial workloads

- Chain: unary records ending in a retained scalar sentinel.
- Wide: a List of records owning 136-byte scalar payloads and a shared sentinel.
- DAG: those records additionally reference earlier records; root order is
  shuffled deterministically from the seed.
- Frames: a detached activation with N local owners and one borrowed temporary
  every four owners. This exercises all three retirement queues.

All content checks and graph construction precede retirement. The sentinel
remains live through complete draining and its sole remaining owner is checked
in diagnostic builds. It is then released; managed bytes/objects return to zero,
and cached owner storage is explicitly freed. Native system diagnostic builds
also check the backing allocation counter. Sanitizer builds add ASan/UBSan;
LSan is disabled for platform consistency, so do not call this an LSan pass.

These are finite, synthetic direct-runtime fixtures. In particular, the frames
case does not exercise compiler-selected stack frames. No fixed-rate input
stream, sustained arrival, application response deadline, or cold-cache guarantee
is represented by the pilot.

## Measurement separation

Run correctness (`--mode diagnostic`) separately from `sampled` and `batch`.
Diagnostic builds record per-step pending tasks and requested managed bytes and
do not produce timing measurements. Timing builds omit RC testing counters.

Sampled mode records one initial retirement and each subsequent poll. Quantiles
use nearest rank, per process; retain all samples and the maximum. Polls within
one graph drain are dependent observations, not independent repetitions. One
process supplies exactly one root/frame retirement. Small poll counts cannot
support rare-tail claims. No subtraction of clock overhead or eager percentiles.

Batch mode surrounds initial retirement and complete draining with two clock
reads. It keeps the same touched trace-buffer footprint but has no sample writes
or per-poll clocks in the measured interval. Loop bookkeeping and runtime work
remain included. Do not compare sampled drain time as if it were pure runtime
CPU overhead. Report clock minimum positive empty-pair difference as a diagnostic,
not as a calibrated correction or a hardware timestamp-resolution guarantee.

Requested managed bytes exclude frame/chunk allocations, frame caches, libc
overhead, and RSS. The dead-byte metric subtracts the final live sentinel bytes.
This pilot reports post-retirement retained bytes, not full peak process memory.

Run processes serially in a recorded seeded permutation. Use three fresh
processes per configuration/size/shape for an initial timing pilot. Chain/wide/
frames seeds repeat the same structure; DAG seeds vary topology and order.
Retain source and transformed-header hashes, compiler version, commands, binary
hashes, raw CSVs, failed runs, stderr, git revision/status/diff, and limitations.
A timing result has evidential value only for the frozen snapshot it identifies.

## Initial matrices

- Small harness validation: N=64, K=1/32, one seed, all five arms/four shapes.
- Native and sanitizer correctness: N=2048, K=1/32/128, three seeds, all arms/shapes.
- Timing pilot: N=16384, K=1/32/128, three seeds, all arms/shapes, sampled and batch.
- Separate historical counterexample: final Text-view release at K=1 returned
  nonzero on the original runtime. On the fixed research branch it must return
  zero with one unit and a deferred backing root; preserve the original evidence.

## Follow-up work required for a paper

1. Add continuously arriving retirement while old object, frame, and temporary
   queues compete; measure oldest-task progress and backlog by cycle position.
2. Add declared quiet recovery windows and finite-pool capacity/fragmentation,
   preserving the previously written HFT methodology where applicable.
3. Add compiler-generated ownership workloads: event-state replacement, parsing
   with shared text, and persistent DAG updates; preserve an independent oracle.
4. Hold compiler lowering fixed when varying K, then separately compare heap-only
   ownership, fixed stack admission, and K-dependent admission.
5. Compare to external implementations only after matching data representation,
   workload semantics, complete lifecycle work, and allocator assumptions.
6. Repeat on controlled native hosts, report per-process variation, and use an
   appropriate dependence model before statistical or deadline claims.

## Clock amendment before the second campaign

The first complete timing pilot used `clock_gettime(CLOCK_MONOTONIC)` on macOS.
Its recorded minimum positive calibration difference was 1,000 ns, and many
per-poll timings were consequently quantized to zero or one microsecond. This is
too coarse for useful comparison of the short polls. The whole initial campaign
is retained under `build/reclamation-*`; no individual outliers were removed.

Before rerunning, the fixture switches macOS timing to `mach_absolute_time` with
the reported timebase conversion (128-bit intermediate arithmetic). Other hosts
continue to use `clock_gettime`. All four matrices are rerun under fresh `-v2`
output directories so accounting and timing identify the same revised fixture.
The regenerated pilot table uses that second campaign. This is an explicit
measurement correction; it is not independent confirmation of initial timings.
No workload, acceptance threshold, seed, or exclusion rule changes.

The pilot may reject a hypothesis or find a correctness issue. It cannot by
itself establish novelty, practical workload benefit, or a hard real-time bound.
