# Cycles without an unbounded cleanup batch

This branch supports arbitrary owning cycles through List addition/replacement
and reference-field assignment, in all runtime profiles. It adds an incremental
snapshot tracer alongside reference counting. There is no collector thread,
user-visible collection operation, weak annotation, or exit-only solution.

The intended guarantee is a bound on **work per service batch**, not a
wall-clock deadline, a universal bound on retained bytes, or a bound on an entire
source expression. The distinction matters for finite pools and high mutation
rates. The proof below is an informal proof sketch, backed by tests, not a
mechanized verification of the C implementation.

## Why this algorithm

A localized trial-deletion collector can reduce visits to unrelated live data.
However, simply spreading trial deletion over service points and aborting when
the graph changes can starve garbage indefinitely. Restarting a whole trial also
hides unbounded work unless every reset is incremental. I chose a finite cohort,
monotone marking, and barriers instead. No mutator operation restarts an epoch.
This is simpler to reason about with the existing compiler's precise counts,
but requires metadata and sometimes scans live aggregates.

Related work consulted:

- Taiichi Yuasa, [Real-time garbage collection on general-purpose machines](https://doi.org/10.1016/0164-1212(90)90084-Y), 1990: the snapshot/deletion-barrier approach. This implementation additionally shades incoming roots and edge transfers, and handles reference-count retirement explicitly.
- David F. Bacon and V. T. Rajan, [Concurrent Cycle Collection in Reference Counted Systems](https://doi.org/10.1007/3-540-45337-7_12), ECOOP 2001: localized cycle collection and the difficulty of mutation during collection. This branch does not implement their concurrent algorithm or claim their performance properties.
- The repository's [existing cleanup contract](../../docs/bounded-runtime-contract.md), ownership lowering, and pending-task scheduler. `research/reclamation/`, mentioned in the task, was absent from this checkout.

## Representation and operations

The eight-byte word immediately before a payload still stores its kind and
ordinary ownership count. Text and scalar records retain their old layout.
Lists and mixed records reserve a further 48 bytes on this 64-bit ABI:
registry links, gray-queue links, an incoming-edge count, and generation/color,
pin, registration, and cleared flags. Scalar Lists currently pay this space cost
too, because their reference kind can be established after allocation.

Every aggregate slot insertion increments its target's incoming count; removing
that slot decrements it. The ordinary count still includes that edge. Consequently
`ordinary - incoming` counts external owners, including locals, returned values,
expression temporaries, native owners, and detached frames/chunks (plus explicitly recorded collector pins). Compiler
transfers change the classification of an owner, even when they do not change
its ordinary count. Text and scalar objects cannot be part of a cycle; their
ownership remains entirely count-driven.

A container enters the intrusive registry on its first edge to another aggregate.
Reference-only leaves need no tracing. The registry persists until the container
reaches zero or cycle sweeping clears all its edges. Dead objects' queued edges
continue to contribute incoming counts until ordinary cleanup visits them.

Generated entry points select a compiler-hinted policy before creating objects.
The former type reachability analysis enables tracing at a mutation whose type
can close a cycle; it no longer rejects that mutation. Both entry-point forms,
nested Lists, aliases, and module-resolved types use the policy. Construction
cannot create the first cycle because its new object is not yet accessible.
Thus no cyclic garbage exists while this policy keeps tracing dormant. Raw C
clients default to conservative tracing. Counts and registry metadata are kept
up to date even while tracing is dormant, so enabling does no catch-up scan.
Once enabled, tracing stays enabled. In incremental profiles each hint call
also services one bounded batch before the mutation, while receiver/argument
owners protect the pending store. This supplies collection work at cyclic
mutations without adding calls to constructor-only acyclic programs.

A nonzero count drop that removes an aggregate's last external owner requests
an epoch. A take-store can also request one when the target loses its last
external owner and the receiver has no external owner. A rooted receiver would
itself keep the transferred target reachable. Events during an epoch record a
request for another pass. Collector-internal sweep bookkeeping does not request
redundant passes.

## The state machine

1. **Capture.** Flip a generation bit, capture the registry's head, and clear the
   current request. This is constant work. New registrations prepend with the
   new generation and cannot enter the captured suffix.
2. **Roots.** Visit one cohort entry per unit. Shade entries whose ordinary count
   exceeds their incoming count. Root insertion, owner deletion, and edge
   insertion/removal barriers also shade old-generation targets.
3. **Mark.** Pop one gray object, capture its current field count, visit one slot
   per unit, then finish it. Setup and completion accompany its first and last
   slot; an empty scan takes one unit. A unit never starts a second object.
   Each object is enqueued at most once per epoch.
   Reads fetch the current List backing pointer; no cursor survives a resize as
   an interior pointer. The saved length cannot grow with later appends.
4. **Sweep.** Visit cohort entries individually. Marked entries survive and
   reset their generation/color. An unmarked entry gets a temporary collector
   pin; one outgoing slot is cleared per unit and its child is dropped normally.
   Setup accompanies the first slot; completion accompanies the last. On
   completion it leaves the registry and records that its slots are cleared,
   avoiding a second traversal on subsequent reference-count retirement.
5. **Finish.** A constant-time transition starts another requested epoch or
   removes the cycle job. Generation bits are reusable because every surviving
   cohort entry was reset in a charged sweep unit; there is no wrapping counter
   or global color-reset pass.

Registry and gray links are doubly linked, so deletion repairs saved cursors in
constant time. A gray object whose *real* count reaches zero gets a collector
pin until its scan finishes. Removing it from the gray queue immediately would
lose all of its snapshot edges; scanning those edges immediately would violate
K. The pin solves both problems. At scan completion it becomes black before the
pin is dropped, preventing repeated pinning.

Sweeping likewise pins only its active object. It never frees an entire white
set in one operation and never decrements references to already freed white
objects: each unprocessed incoming edge still owns its target. Clearing a
self-edge cannot destroy the active object before the pin is released. There
are no finalizers that can expose a white object to the mutator.

## Invariants and proof sketch

Assumptions: single-threaded, non-reentrant runtime/allocator hooks; well-typed
compiler output; all managed edges use the owning-slot APIs; external owners
obey the existing retain/transfer contract. Foreign raw-pointer mutation and
forged pointers are outside that contract.

**Counts.** At service boundaries, ordinary counts equal external plus internal
owners plus any collector pin. Incoming counts equal actual still-owned
aggregate slots, including slots awaiting retirement. A mutation anchors the
new edge before releasing the old one, and all count/barrier updates precede
its service call. Immortal Text and scalar bits cannot become traced pointers.
This invariant is inductive over all borrowed and taking stores and removals.

**Cohort and queue lifetime.** At capture the registered objects form a finite
suffix. New arrivals precede it; removing entries repairs the cohort, root, and
sweep cursors. Every gray entry remains allocated, either through ordinary
owners or its gray pin. A completed scan releases its pin only after marking its
children. Every sweep-active entry retains its own pin. Hence no collector
cursor or queue link outlives its allocation.

**Snapshot safety.** A root present at capture either remains external until its
root visit, or its removal/transfer shades the object first. For each snapshot
edge from a marked object, either the scan sees it, or the deletion barrier
shades its old target. The gray pin retains edges whose source's ordinary
owners disappear before that scan. New root acquisition is also shaded; new
edges to cohort objects are shaded even when their source is outside the cohort.
All shading is monotone and restricted to the captured generation. Thus the
marker reaches every cohort object needed by the snapshot or subsequently
acquired by the mutator. At mark termination an unmarked cohort object is not
reachable from the program. Mutator operations cannot acquire an unreachable
white object without already having a reachable path to it. It is therefore
safe to sever its edges incrementally, even during mutation elsewhere.

**Acyclic retirement.** Zero-count objects outside gray pinning use the existing
iterative retirement queues. Gray pinning delays, but cannot lose, that
retirement: each pinned object has a finite marked scan and drops its pin exactly
once. Clearing cyclic edges eventually produces ordinary zero counts. A cleared
object still held by another garbage edge remains allocated until that owner
is processed. Counts and registry removal prevent a double free.

**Eventual reclamation.** Consider a finite component that becomes unreachable.
The last external owner of its remaining registered graph either drops or moves
into an unrooted receiver; that requests collection, unless a pending ordinary
zero-count cascade is already sufficient. Deferred owner storage and ordinary
edge retirement are serviced fairly. Once that retirement and any active
snapshot's conservative marking have passed, a subsequent cohort contains the
component without roots or mutator access. It cannot acquire new marks from
mutator barriers. Sweeping severs all its remaining edges, and fair ordinary
retirement frees its leaves. An active snapshot may preserve floating garbage
for a later epoch; exact completion in one epoch is not claimed. Unrelated
mutation cannot add cohort members, re-enqueue black objects, or restart work.
This establishes eventual reclamation given continued service, not a fixed
number of milliseconds or a universal live-bytes/heap ratio.

**Per-batch work.** A cycle unit performs one root test, survivor visit, field
visit (including constant-size scan setup/completion), empty scan, or phase
change. It never visits a second field or starts a second container.
Each has a fixed number of pointer/count updates,
and can enqueue but never recursively traverse other aggregates. A field visit
may release a leaf, including a Text view and its single flattened backing root
(at most five backing frees). A final sweep field may also finish its cleared
container (at most two further backing frees), for a maximum of seven frees.
Pool bookkeeping per free is bounded by its fixed
buddy-tree depth; system allocator latency is not bounded. Barriers only shade
one target per ownership update, never visit its outgoing slots; their constant
bookkeeping is included in a containing service unit or mutator ownership
operation. The scheduler charges each cycle unit alongside ordinary units and
stops at `min(requested, K)`. It selects among four queues in at most four tests.
No cohort scan, queue drain, or reset occurs outside those units. Stack-frame
retirement reserves its written-slot units before polling, as before.
The pre-mutation hint's service call is another explicit K-bounded batch, not
an uncharged scan. As before, a source expression can contain several batches.

**Termination under mutation.** Each captured object is root-tested once,
marked at most once, scanned up to one saved finite length, and sweep-tested
once unless ordinary retirement removes it first. Barriers cannot add new
allocations to this finite set or increase an active List's limit. A cycle job
requested inside an object-only batch may wait for that batch to finish, at
most K units. Following polls use the general scheduler, where the cycle job
gets a unit within four scheduler units, including K1. Thus an epoch
finishes even if mutation continues. This is a finiteness argument; the number
of fields at a scan's start can exceed the number at epoch capture, so a strict
bound using only the initial heap's edge count is not asserted.

## Tests and reproduction

The first commit (`e229bb8`) is intentionally red: the source fixture fails the
old cycle diagnostic, and the native self-loop test fails exact reclamation.
Subsequent commits add the collector and deliberately convert incompatible
rejection tests to acceptance tests. Type-graph model tests now check whether
the compiler emits an enabling hint, rather than whether it rejects the source.
A missing-hint compiler mutant must fail the exact-accounting cycle fixture.

```sh
make check-cycles
make check-bounded check-memory-profiles check-ownership
make check
python3 research/cycles/measure.py --runs 5
```

`tests/cycles-runtime.c` exercises self-loops, a 1,000-node ring, a growing List,
List self-reference through the native API, take transfers, temporary-only
roots, and repeated root/edge changes during collection. Its independent graph
oracle computes reachability in an integer adjacency model before reading
actual live nodes; it does not infer liveness from collector colors/counts.
Every direct poll asserts its limit, including an independent cycle-unit delta.
Exact object/byte counters must return to zero after a test-only drain.

`tests/cycles-profiles.py` compiles native and ASan/UBSan variants for system,
fixed, and lazy profiles at K1, K2, K7, K32, K1024, plus eager. Generated LLVM
functions receive `sanitize_address`, as in the existing sanitizer harness.
Source tests cover mutual record types, List replacement, field replacement,
receiver aliases, temporary protection across mutation, 100,000 small cycles,
and 5,000 dense 24-node cyclic graphs. A further fixture churns 100,000 cycles
beside a persistent 1,000-node live ring. These workloads must fit a 1 MiB pool
before their test-only exit drain. This is evidence of bounded memory for these
workloads, not a universal space theorem for all allocation/service schedules.

## Measurements and findings

Measurements below are medians of five runs on macOS arm64, baseline revision
`c2c9eff1343ad80d78ad5a32801fb135a530f3fb`. The raw observations, commands,
source hash, date, and measured revision are in [measurements.json](measurements.json).
The source-to-LLVM runs omit Clang link time. The system-runtime compiler is a
separate useful stress case; the shipping compiler uses the arena.

| Workload | Baseline retired instructions | This branch | Change |
| --- | ---: | ---: | ---: |
| Compiler arena, same baseline source | 244.06 M | 244.36 M | +0.1% |
| Compiler arena, each version's own source | 244.06 M | 244.36 M | +0.1% |
| Compiler using system runtime, same source | 638.65 M | 669.97 M | +4.9% |
| Existing runtime benchmark, scale 2 | 340.45 M | 348.10 M | +2.2% |
| 20 constructor-only chains of 5,000 nodes | 219.32 M | 261.31 M | +19.1% |

The 0.1% arena difference is within observed variation; arena self-compilation
is effectively unchanged. The chain's remaining overhead and metadata cost are real.
Its median peak RSS rose from about 1.89 to 2.38 MiB. The general benchmark's
RSS stayed about 12.8 MiB; the system-runtime compiler variants were roughly
13 MiB. Shared-host load makes wall time unreliable, and the
centisecond `/usr/bin/time` values do not support latency claims.

For 100,000 cyclic allocations in a fixed 1 MiB pool:

| Budget | Retired instructions | Median peak RSS | Reported wall time |
| --- | ---: | ---: | ---: |
| 1 | 273.81 M | 2.33 MiB | 0.01 s |
| 32 | 355.76 M | 2.31 MiB | 0.02 s |
| 1024 | 356.36 M | 2.33 MiB | 0.02 s |

These are complete executable runs, including startup. Smaller batches coalesce
candidate requests over more mutation and can perform less total cycle work;
K therefore need not improve aggregate throughput monotonically. Pool capacity
is 1 MiB regardless of cumulative allocation. The runtime oracle's peak rounded
pool usage was 155,776 bytes in the tested fixed/lazy configurations, dominated
by the growing-List test. Every instrumented batch stayed within its configured
limit; exact final object and owned-byte counts were zero. No wall-clock pause
bound is inferred from those assertions.
The complete configuration counters are preserved in [cycle-matrix.txt](cycle-matrix.txt).
The persistent-live-ring reserve comparison is in [live-reserve.txt](live-reserve.txt):

```sh
python3 research/cycles/live-reserve.py --runtime-revision a2fbb02 --heap-bytes 4194304
python3 research/cycles/live-reserve.py
```

Each command executes two million iterations at K1. The reported remaining
objects precede exit cleanup and include deferred garbage; these counts are
not claimed to be leaks or the minimum live set. Exact recovery is checked
separately by the profile matrix's exit harness.

### Port onto v2 (3bd7f74)

The port moved the List/record barriers into `runtime/minyar_collections.h`
and kept v2's deferred Text-root retirement. Medians of five
`/usr/bin/time -l` runs on macOS arm64 under background priority, against a
clean 3bd7f74 build. Both compilers emit identical LLVM for these non-cyclic
inputs apart from the two new declarations and the `minyar_rc_cycle_policy`
call in `main`.

| Workload | v2 retired instructions | Port | Change | Peak RSS |
| --- | ---: | ---: | ---: | --- |
| Compiler arena, compiling v2's compiler.min | 87.87 M (min) | 88.07 M (min) | +0.2% | unchanged |
| Compiler using system runtime | 361.5 M | 397.6 M | +10.0% | ~12.3 MiB both |
| `tests/performance/runtime.min 2` (system heap, -O2) | 208.9 M | 213.0 M | +2.0% | 13.4 MiB both |
| `acyclic.min`, `--release` | 193.3 M | 227.1 M | +17.5% | 1.9 → 2.3 MiB |
| 100,000-record chain, `--release` | 168.3 M | 201.6 M | +19.8% | 12.1 → 21.3 MiB |
| 100,000 `List<Point>.add`, `--release` | 46.6 M | 57.3 M | +23.1% | 7.3 → 11.9 MiB |

A non-cyclic program whose mutation types could close a cycle (100,000
`root.children.add(Tree {...})`) enables tracing and costs about 37,000
instructions per add (3.74 G in total, linear in the add count). v2 rejected
that program, so it has no baseline.

### Validation status

Final command outcomes are recorded in [validation.md](validation.md). The
absolute self-compile budget gate is not green on this machine. The unchanged
baseline independently fails it too: 243.70 M retired instructions and 12.6 MiB
against 75 M and 10 MiB ceilings. See [baseline-budget.txt](baseline-budget.txt)
and reproduce with `python3 research/cycles/baseline-budget.py` after the
measurement build. The limits have not been relaxed to hide this failure.

The ordinary full run was first attempted through the repository's development
wrapper; a native link exceeded its 30-second test timeout under background
priority. Validation then used `LIMITED= SANITIZER_LIMITED=` to remove that
wrapper, while retaining the tests' own timeouts. This changed execution
priority, not the cases or assertions.
`measure.py` extracts the baseline revision into this worktree's build directory;
it never changes another checkout. It compares five `/usr/bin/time -l` samples,
records all samples in `measurements.json`, and reports medians. Self-compilation
includes a common baseline source input and the current compiler's own source.
The production compiler links its process-lifetime arena; its runtime ownership
hooks, including cycle hooks, compile away. Native workloads use the ordinary
system runtime; cyclic pool workloads use a fixed 1 MiB pool.

Development findings that affected the final design:

- The initial collector used ~11.7x baseline instructions on the constructor-only
  acyclic chain. Repeated conservative candidates kept the tracer busy. Compiler
  mutation hints now keep tracing dormant for this workload. This failed design
  is not presented as the final overhead measurement.
- The first dense K1 workload exhausted its 1 MiB pool because sweep clearing was
  followed by a second traversal of null slots. Recording cleared objects
  removed that duplicate work; the same workload then completed.
- A late live-ring stress test exposed a larger reserve requirement: at K1,
  100,000 cycles beside a persistent 1,000-node ring exhausted both 1 and 2 MiB
  pools. Two million iterations stabilized at 2,450,048 pool bytes in a 4 MiB
  pool, so this was bounded debt, not a cumulative leak. The additional red
  commit `a2fbb02` preserves the 1 MiB case. Combining constant-size scan setup
  and completion with field units reduced the reserve to 1,081,312 bytes;
  servicing one bounded batch at each existing mutation hint reduced it to
  917,888 bytes and passed the same two-million-iteration run in 1 MiB. The
  revised unit still visits at most one field, but its worst-case backing-free
  bound is explicitly seven rather than five. The change adds service at
  potentially cyclic mutations; it is not a faster allocator or a relaxed K.
- Full eager tracing on every candidate made chain construction quadratic.
  Normal eager releases and statement/loop service now advance at most 32 cycle units; ordinary eager
  destruction remains unbounded, and outermost frame exit finishes cycle work.
- A 100,000-node unary mixed-record runtime test needed its pool increased from
  8 to 16 MiB: each node's rounded allocation increased from 32 to 128 bytes.
  This is a real metadata cost, not a reduction in the tested graph size.
- The existing native ownership oracle now reconstructs collector pins as
  physical owners, and uses the replacement API rather than reusing an
  initialization setter. The unary free-order oracle observes the enlarged
  allocation base. Eager exact-leak checks finish outstanding gray-pin debt
  before asserting zero objects; they still detect all four injected leaks.
- Two unrelated pre-existing CLI diagnostic failures (empty and negative
  ownership budgets) were fixed after the full suite exposed them. A stale
  equality diagnostic assertion was aligned with the baseline's existing Bytes
  wording. These changes are separate commits, not hidden cycle semantics.
- The old direct Text-view release counted two immediate units at K1. Its
  constant-depth backing release now belongs to the same leaf-owner unit,
  matching the unit already used for a field pointing to a view. The documented
  maximum number of backing frees per such unit is five.

## Limitations and open work

- This is a global cohort tracer over registered aggregates, not a localized
  candidate collector. After the first potentially cyclic mutation, acyclic
  traffic can still trigger expensive live-graph scans. Type hints avoid that
  cost only before enabling. Finer eligibility metadata and localized cohorts
  would be useful follow-up work.
- The 48-byte prefix and pool rounding are substantial for small aggregates.
  Text and scalar records are unaffected; scalar Lists still reserve metadata.
- Fairness and finite epochs prove eventual reclamation. They do not prove that
  every producer rate fits every fixed heap. Capacity must cover live objects,
  snapshots, deferred edges, cached ownership frames, allocator rounding and
  fragmentation, and resize buffers. There is deliberately no unbounded
  allocation-pressure drain. Tested steady workloads fit small pools, but a
  general amortized space bound remains open.
- K limits logical cleanup units, not arbitrary allocator calls, record
  initialization, data copying, page faults, I/O, or OS scheduling. No hard
  wall-clock pause guarantee is claimed. Large scalar operations can still take
  time proportional to their size.
- The compiler arena intentionally remains process-lifetime storage. Normal
  incremental programs do not acquire an exit-only collector; test-only drains
  distinguish remaining debt from leaks.
- New language features such as foreign pointers, user finalizers, closure
  environments, hidden mutable slots, or multithreading require revisiting both
  the compiler hint proof and collector barriers.
- Runtime proof sketches and randomized interleavings are not exhaustive proofs
  of the C code. The new implementation is validated on macOS arm64 here; other
  platforms retain the repository's existing coverage but were not newly run
  for this work.
