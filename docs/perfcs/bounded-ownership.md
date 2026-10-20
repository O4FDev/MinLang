# Bounded ownership: model and runtime scheduling design

Design recorded before implementation, 2026-10-20. This changes runtime
scheduling, independently of compiler borrow, move, and escape proofs.

## Model of the existing protocol

A mortal reference count counts owning locals, expression temporaries,
container edges, and returned results. Borrowed parameters rely on an ancestor
owner. `keep` adopts an existing count; `borrow` first retains one. A local
assignment anchors its new owner before dropping its old owner; a move transfers
that count without dropping it. Nulls and immortal literals need no temporary
registration. `enter` publishes an initialized owner frame and services K queued
units. `step` detaches the current expression's temporary chunks, then services
K units. `leave` also detaches the frame's written-slot index, then services K
units. Detachment takes constant bookkeeping work and never scans owners.

Each temporary chunk holds at most eight owners. Each frame records the local
indices first written non-null, including those later cleared. A detached
chunk/frame keeps its owners until their visits. A zero-count nonleaf object
keeps its outgoing edges until its cursor visits them; it cannot be reused
before finalization. Queue metadata resides in dead objects or detached owner
storage. No recursive graph walk or queue allocation is needed.

Let F be detached frames, L their written indices, T registered mortal temporary
owners, C their chunks, E visited nonleaf fields, and O queued objects. Draining
finite acyclic debt costs exactly F + L + T + C + E + O queued units, excluding
immediate leaf destruction charged to its releasing operation. Each owner visit
may free one leaf, with at most three backing frees. A Text view's newly dead
backing root is a separate task. Traced profiles add their independently charged
collector units and retain all snapshot/mutation barriers.

Objects, frames, chunks (and an activated cycle job) have round-robin service.
The object queue alternates a captured finite old batch with recent arrivals.
In general dispatch, three continuously ready queues each get a unit within
three units; the corresponding traced bound is four. The existing object-only
batch may delay a newly requested cycle job until its bounded batch returns.
That unchanged exception is not a three/four-unit service guarantee. Captured
object predecessors are finite.
Progress requires continued service points; K bounds cleanup units, not allocator
latency, copying, page faults, OS scheduling, or elapsed operation time. See
[the complete operation table](../bounded-runtime-contract.md#the-work-budget).

The memory lane's October 20 default self-compile observation reports 11.2M
frames, 30.9M keeps, 77.7M steps, and 14.5M chunks, with 9.13B retired user
instructions. These are rounded observations on its unlanded compiler, not a
baseline for this branch. They imply approximately 2.13 temporary owners/chunk,
so roughly 46.6M owner/chunk-finalization units plus at least 11.2M frame units,
before local or object fields. Geometric chunk storage alone does not amortize
statement turnover: a nearly empty chunk can be allocated and freed per step.
The reported 31% poll, 9% keep, and 3.4% enter shares are sampling attribution,
not a proof of exact instruction costs.

## First change: single-ready-queue batching

After the ordinary scheduler chooses a frame or chunk, and only when no other
queue is ready, continue servicing that queue without repeating selection.
Every visit and finalization still consumes one unit. Publish the same next-queue
state before each unit. Stop at the budget, an empty queue, or immediately after
a drop creates object or collector work. Resume the ordinary scheduler there.
Do not batch across a competing frame, chunk, object, or cycle job. Do not change
object old/recent batching, its cursor, or its parity.

Proof: induction on performed units. Initially the selected queue matches the
reference scheduler. If it remains the only ready queue, reference selection
skips empty queues and chooses it again. Both paths perform the identical unit
with identical next-queue state. If a unit creates a competitor, batching ends
before the next selection. Thus each prefix, including zero/K1/partial-budget
polls, has identical owner counts, debt, object finalization order, queue state,
and charged work. There is no additional reclamation delay or storage cost.
Non-reentrant allocator/runtime hooks remain the existing assumption.

The loop can detect a new competitor through the pending-task count. Starting
with no object or cycle task, an owner visit cannot decrement that count:
`rc_drop` can only enqueue an object or request a cycle job. Removing a cycle
job requires `rc_cycle_unit`, which this run never calls. A task finalization
decrements the count once and drops no owner. Therefore an increase ends the
run; an unchanged count or a finalization's decrease can safely continue. This
replaces repeated object/collector readiness loads without weakening the guard.

For a run of r batched owner units within one poll, selection executes once
instead of r times. Let B count batched owner units, R owner-batch invocations
(split at poll/K boundaries), and U all other generic-dispatch units. U includes
units that become sole-object work partway through a general-dispatch poll.
Selection count changes B + U to R + U; total cleanup work remains
O(F + L + T + C + E + O). With K1, R can equal B. This is a workload-dependent
constant-factor improvement, not an asymptotic graph traversal improvement.
Each poll still performs at most min(requested,K) units.
Existing round-robin and captured-batch fairness bounds follow by equivalence.

## Validation and measurement plan

Use a retained copy of the pre-change runtime with identical generated LLVM.
Compare deterministic per-poll transcripts (zero/partial/random budgets,
K1/2/7/32/1024), live counts/bytes, shared owners, newly queued object work,
and traced-cycle phases. Keep all existing ownership, diagnostic, pool recovery,
cycle, native and sanitizer assertions. Run narrow tests first, then the official
portable landing gate and ownership/cycle/sanitizer extras through Boat.

Measure default (`--bounded-owners 32`, system heap) and eager (`--scope-owners`)
self-compilation, create-probe, safelibs and jsmn with identical program LLVM for
each control/candidate pair. Eager is a negative control for this bounded-only
change. Retain all alternating observations and require byte-identical output;
report hardware-counter availability and complete source/command identities.

## Retained screening result

The first implementation reloaded every object/collector readiness pointer
after every owner unit. Three retained same-LLVM Linux/LLVM 23.1.2 self-compile
samples found default median 15,229,435,422 instructions in the unmodified
runtime versus 15,617,632,057 with batching: a **2.55% regression**. Eager control
medians were 4,518,151,437 and 4,518,151,534. Every output matched. This version
is rejected for landing; its full observations are retained in the lane's
`build/perfcs-screen/instructions.json`, with an immutable runtime copy under
`.perfcs/batching-v1-runtime`. A pending-count guard is a separate experiment,
not an established speedup.

The pending-count version also regressed the ordinary runtime: medians
15,246,330,556 versus 15,628,302,867 (+2.505%). Its eager medians were
4,528,094,690 and 4,528,095,105. All outputs matched. Both ordinary scheduler
changes are removed.

The broader pending-count version reduced an instrumented 20-realm JS probe
from approximately 173.977M to 163.880M instructions (three retained samples,
exact output). That screen justified testing a restriction to the activated
four-queue scheduler; it is not a shipping JS speedup claim. The ordinary
runtime and the three-queue cycle instantiation retain generic dispatch.

Final shipping JS ablations find no measurable benefit from the restricted
batching path in create-probe: baseline 169,402,727; cycle-only 169,402,737;
cache-only 167,404,883; combined 167,404,976 instructions. Its 1.179% improvement
comes from chunk reuse, described in [temporary-cache.md](temporary-cache.md).

A separate public-API microstudy deliberately activates the four-queue path
by constructing, releasing and collecting a genuine traced self-cycle. On
200,000 eight-owner frames, seven retained samples plus warmup give
615,178,543→506,578,747 instructions for local owners (-17.653%) and
535,578,177→432,178,329 for temporary owners (-19.306%). Inactive controls
are unchanged. All 64 executions have identical checksums; separate
same-object instrumented links prove full ownership/backing recovery.
Shipping links disable testing accounting and share one workload object.
This supports retaining the restricted path, without inferring a product gain.

The full differential matrix compares every work/queue/owner/cycle prefix
against generic dispatch over system/fixed/lazy heaps, K1/2/7/32/1024, O0/O2,
native and ASan/UBSan. Activated ordinary object and Text-root arrivals are
included; stop/charge mutants must fail. Final application measurements and
their limitations are recorded in [results.md](results.md).
