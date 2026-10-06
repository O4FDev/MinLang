# Draft claims and proof obligations

Status: a mathematical model and proof sketches, not a mechanized proof or a
verification of the compiler and C runtime. `check_model.py` checks finite
scheduling cases; the existing `experiments/memory/production-contract-model.py`
checks finite type-graph cases. Neither establishes a universal theorem by testing.

## Scope and state

Assume one mutator, finite objects and owner tables, non-reentrant allocator/runtime
hooks, no finalizers or weak references, and no source-level access to retired
storage. Exclude count overflow by the runtime's checked failure. Safety claims
concern successful operations; process exit and out-of-memory termination need
separate semantics. Allocation failure cannot be ruled out by these claims.

Let H be allocated objects. Each has a finite sequence of scalar/reference slots,
a live reference count or a retired tag, and (when retired) a cursor. Let R be
active source roots, F detached local-owner frames, and T detached temporary chunks.
References in unprocessed retired object slots, F, and T still count as owners.
Consumed slots may physically retain stale bits; those bits are no longer edges.

The basic accounting invariant for each nonretired mortal object v is:

    rc(v) = active root owners + active heap-slot owners
            + unprocessed retired-slot/frame/chunk owners of v.

Borrowed parameters are protected by caller owners, not counted twice. Immortal
objects are outside the mortal accounting equation. Ownership transfers preserve
the equation; retaining a replacement precedes dropping its former value.
During fused non-reentrant transitions, include transient ownership held in the
poll's C locals. Invariants at public boundaries alone are insufficient to justify
all intermediate loads and frees.

## Acyclicity lemma

Let G_T contain an edge A -> B for every reference slot of declared type B in
type A, including List element edges. The constructor rule allows references only
to already completed values. The mutation rule for List<T> permits an insertion
only if T cannot reach List<T> in G_T (reflexive reachability). The current
record-field rule permits inserting R -> F only if F cannot reach R. Scalar
field writes add no owning heap edge.

Proof sketch by the first cycle: constructing an unpublished object cannot add
an edge from an existing object back to itself. If an insertion L -> x introduces
the first heap cycle, an existing path x ->* L must precede it. Type preservation
maps that path to T ->* List<T>, contradicting the List mutation guard. Similarly,
a field insertion r -> x in a record of type R would require a preceding path
x ->* r, giving a type path F ->* R and contradicting the field mutation guard.
Removing or replacing an old edge cannot invalidate this argument. List copying
constructs a fresh unpublished container. Aliases do not alter the type path.

Remaining compiler obligations: resolved type encodings faithfully represent
nested Lists and records; every List and reference-field mutation site invokes
its guard; constructors protect earlier initializer results across later evaluation.
Dynamic types, closures and foreign references would require new rules. The field
guard is now implemented by checkFieldMutation; this proof sketch does not verify
every code-generation call site or module build.

## Safety lemma for deferred owners

Under the accounting invariant, moving an active owner table to F or T neither
releases its objects nor loses ownership. Processing one slot removes exactly
one owning edge. A newly zero-count object cannot be reached from an active
source root, and becomes a retirement task while its outgoing slots remain
owners. Its storage is freed only after all slots have been processed.

Induction on these transitions gives absence of early reclamation in this model.
It does not prove source-to-LLVM lowering correct, C pointer tagging correct,
allocator correctness, or optimized cursor storage safe. Existing independent
heap/frame oracles and sanitizer runs provide evidence for those obligations.

## Work accounting and a discovered exception

A queued work unit visits one object slot or detached owner, or finalizes a task.
Leaf destruction invoked by a visit has bounded structural depth, but allocation
and free latency are excluded. Do not equate a work unit with a fixed CPU duration.

For poll(b), the unit scheduler performs at most min(b, K) queued units. A batched
path must refine an ordered sequence of these units and charge every unit. The
production optimization requires a separate refinement argument; equal final
heaps alone do not prove the same fairness or work behavior.

For a stack owner frame with s written slots, s <= min(8, K-1) implies:

    leave_work = s + poll(K-s) <= K, with K-s >= 1.

This counts owner visits, not all frees that a visit can induce. Stack storage
must never enter F/T or a cache. Heap-frame and temporary-chain detachment is
constant bookkeeping before their bounded poll. Frame entry still initializes
storage proportionally to capacity and is not a bound on all work in a call.

**The original runtime violated the public-release bound at K=1.**
`text_view_bound.c` constructs an owning Text and a partial view, releases the
root's external owner, then releases the view. Before the fix, `rc_drop` freed both view and root
and returned 2. `minyar_rc_release` reported 2 work units despite K=1. A local
native and ASan/UBSan reproduction returned `{budget: 1, reported_work: 2}` with no
objects or bytes remaining. The [retained evidence](../../build/reclamation-text-bound-evidence/results.json)
contains source/binary hashes and commands. This is a counterexample to that work
contract, not a leak.

On `research/bounded-reclamation`, view destruction decrements the owning root
and queues it as a fieldless Text task if it becomes unreachable. Each object's
destruction now consumes a separate unit. Text views are flattened to an owning
root, so this introduces no recursively queued view chain. The reproducer now
expects one reported unit and one surviving queued root after the K1 release,
then complete reclamation after polling.
The [fixed native and sanitizer evidence](../../build/reclamation-text-bound-fixed/results.json)
records one remaining root after release and zero final bytes after polling.

`tests/text-view-budget.py` checks actual destruction counts independently of
reported work for release, aliases, local/List replacement, detached owners,
stack owners, and both object queues. All 24 combinations of K1/K2/K32/K1024,
system/fixed/lazy allocation, and native/ASan+UBSan passed. This closes the
specific counterexample, not a proof of every public path or allocator bound.

The model must include the view's owning edge to its backing root. Releasing
that edge during view destruction performs one additional constant-size count
update, but no second destruction. Only an owning Text can be queued by this
path: it has no managed outgoing references, its cursor is always zero, and
either object-service path finalizes it in one unit. Owning Text finalization
can free its byte allocation, Unicode index, and header (at most three backing
allocations); a view has no separate byte allocation. This case argument relies
on flattened views and non-reentrant hooks, not merely the reported work counter.

## Fairness and eventual reclamation

Across objects, F, and T, rotating selection gives each continuously ready queue
one unit within three executed queued units, including across K=1 polls. The
claim is about executed work, not wall time or number of source expressions.

Within object service, alternate recent-stack work and a captured older batch.
New arrivals never enter that batch. Every batch member has finitely many
predecessors, each with finitely many remaining units. Thus its active head
advances within six global queued units when all competitors stay ready. This
six-unit statement applies to the active head, not every object in the batch.
The unary-parent exception and optimized pairs require checking that old service
is not delayed and that new competing tasks restore ordinary scheduling.

A captured batch eventually finishes under continued nonzero polling. An object
remaining in recent work either finishes there or enters a later captured batch.
Assume finitely many arrivals between service steps; no infinite work happens
between successive polls. These facts give eventual service for every queued task.

For a finite, permanently unreachable acyclic subgraph, fair service of detached
owners and predecessor objects eventually removes every incoming dead edge.
Induction in a topological order then gives reclamation of each object. Shared
descendants still reachable from live roots are excluded from the conclusion.

This does not imply a uniform wait bound for all objects, bounded backlog under
arbitrary arrivals, or any fixed bound on retained bytes. A pure recent/LIFO
policy admits starvation when a new task arrives before each service step;
`check_model.py` includes that counterexample. FIFO has progress but its locality
and retained-memory costs need measurement, not an assumed disadvantage.

`check_fairness.py` also checks the C schedulers under 1,536 new arrivals with
all three queues continuously ready. Current/fair-unit advanced the captured
old object 256 fields, FIFO 512, and LIFO zero; all advanced 512 detached local
owners. Native and ASan/UBSan runs passed. This supports the active-head service
claim and distinguishes LIFO, but does not establish an advantage over FIFO or
replace a universal refinement proof.

## Requirements before publication

1. Extend the Text-view regression into an audit of every public service path.
2. Give a compiler preservation argument for actual ownership lowering and
   construction order, including module builds and optimizer assumptions.
3. Formalize and prove the optimized scheduler's refinement of the unit model.
4. Extend the finite continual-arrival C checks to a scheduler refinement proof.
5. Derive capacity/recovery claims only under explicit arrival, object-size,
   service-frequency, and allocation assumptions; no universal space theorem.
