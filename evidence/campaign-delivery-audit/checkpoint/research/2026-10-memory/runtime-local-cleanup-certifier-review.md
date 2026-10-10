# Independent design review: local cleanup certifier

**Conditional approval for a standalone research prototype, with no runtime or
compiler changes.** The proposed local four-unit inference is sound under its
explicit successful-execution, ownership, profile, protection and full-service
premises. I found no runtime-cost contradiction in the inspected rules. This
review does not validate an implementation: the typed parser, interprocedural
requirements and actual loop analysis are still proof/test gates. A prototype
that cannot establish them must reject the archived function.

Reviewed the complete [design](local-cleanup-certifier-design.md), its runtime
summary catalog, expected derivation and 29 proposed control records. The
[review record](runtime-local-cleanup-certifier-review.json) pins those artifacts,
relevant saved LLVM/source bytes, and current matching runtime fragments. I
inspected all thirteen definitions of the stated direct call closure and the
actual RC construction, keep, frame/chunk retirement and scalar destruction
paths. No checker, test, runtime execution, compilation, timing, installation or
production modification occurred. All 29 controls remain proposed.

## Runtime correspondence

A successful `list_new` initializes a fresh RC_LIST header with ownership word
10, length/capacity zero and a single producer owner. Scalar appends change only
raw storage and scalar contents; their allocation/resize hooks can service
outside debt without decrementing this producer. Freshness and absence of an
exported pointer prevent an old valid queue task from owning the new generation.
The first keep can service before chunk allocation while that producer still
protects the argument, then installs it in the active chunk before its second
service hook. These are meaningful hidden polls, not assumed idle calls.

`rc_keep` allocates a new chunk **before an incoming owner** only when no tail
exists or the old tail already contains eight slots. It does not detach a chunk
when the eighth owner is published. The ninth owner therefore produces active
occupancies `[8,1]`; existing active chunks are not reclamation-queue tasks.
`rc_step` detaches the entire active chunk chain once, and leave independently
detaches any remaining chain before retiring the current frame. This supports
both the actual `[2]` case and the distinct eight/nine controls.

At the actual proposed boundary, the two sealed scalar Lists each have one token
in one active chunk; the current frame activation has no written locals.
A chunk unit visits one owner and cocharges unique scalar List header/backing
destruction. An empty chunk later consumes a distinct finalizer unit. A
zero-written frame activation consumes one finalizer whether cached or freed.
Thus the source-derived local obligations are two visits, one chunk finalizer
and one frame finalizer: **W = 4**. Eight owners require **10** units, and nine
owners require **12**. List element counts and raw backing bytes do not add
managed-edge visits. Cached physical frame reuse is a new activation, while
retained cache storage after finalization is not unconsumed work.

This is the total attributed to the selected component after full service.
Outside queues may consume both automatic budgets, so neither completion at
return, an exact remaining-at-return value, process poll count, allocation
admission nor a wall deadline follows. The design correctly excludes those
fields and does not subtract a whole poll return from four.

## Borrower and loop gates

The actual `pick` loop stores zero in its private counter and a List length in a
separate immutable limit cell; its header compares the counter with that limit,
its only latch stores `counter+1`, and its other exits return a scalar after
balancing the call-depth guard. There is no managed construction, ownership hook,
Bytes write or opaque call in the cycle. With inferred nonnegative limit and the
proposed representability bound, the invariant/rank proof is adequate. For the
actual fresh limits List the instantiated bound is two. A scalar return type
alone would not prove this; mutations of a callee body must invalidate its summary.

The raw getter establishes an unsigned `position < length` guard before loading
its backing and slot. Its bad path calls the checked runtime getter; normal
invalid access terminates rather than returning an arbitrary word. This supports
safe reads only with the same valid ScalarList generation, immutable length and
backing, and guard provenance. An opaque `ptr` or layout resemblance is not a
ScalarList certificate. Requirements must be substituted through callers and
checked against fresh scalar construction or retained as explicit external
requirements. No reference List may acquire scalar status from its getter alone.

The external Bytes parameter is forwarded through `paint` and `put`, which
perform scalar byte writes and balanced call-depth guards. `bytes_set` checks
bounds/value then writes payload without owner transfer, managed allocation or
poll. The caller must protect the valid Bytes object continuously, including
prefix hidden polls. The archived caller's registered local is a hand witness;
it is **not** automatically discharged by analysing these thirteen definitions.
Normal successful invocation also excludes arithmetic, byte-bound and stack
failures. The checker must report that caller requirement as unfulfilled unless
another independently justified context analysis supplies it.

## Proposal controls and implementation limits

The 29 records are a useful preregistration, not 29 executed tests. Their renamed
application/SSA/block variants, changed owner numbers and eight/nine packing
controls challenge artifact matching and a canned answer. The missing/duplicate
keep, unknown zero-argument call, early step, pointer laundering, poisoned
backedge, invalid getter and escaping-return controls challenge distinct proof
premises. Compound records contain multiple alternatives; later reports must
count actual generated fixtures/assertions separately rather than treating every
alternative as already tested.

Before an accepted prototype result, retain the proposed separate gates:

1. Complete typed subset parsing, symbol resolution, dominance and CFG checking.
   Missing instructions, duplicate declarations, alternate runtime definitions,
   hidden global effects and invalid trailing operands must reject.
2. Body-derived borrower effects and role/bound requirements across the complete
   call closure. No trusted application function-name or hash whitelist.
3. An independently reviewed loop witness covering every continuing path and
   backedge, including zero/two-step and illicit cell/limit mutation controls.
4. Producer-to-active-chunk token conservation and the exact terminal retirement
   suffix. Earlier local service, missing registration or later pointer use
   cannot silently move the certificate boundary.
5. The proposed independent checker mutations, especially omitted structural
   finalizers, ignored callee effects and original-name bypass. A passing
   serialization test would not establish inference soundness.

Keep the catalog tied to its frozen 64-bit system/K32 source/profile, with exact
prototypes and named trust obligations. A later unrelated production Text edit
must not silently make a catalog appear checked against new bytes: the prototype
can continue analysing the original archived artifact/catalog, or explicitly
review and repin affected identities. Runtime summaries, C/LLVM translation,
linking and valid external state remain conditional premises, not parser results.

The useful proposed result is automatic inspection of one existing compiler hook
sequence with explicit protection requirements, rather than a hand-entered work
constant. General cleanup inference, safe allocator admission, analysis cost,
corpus applicability, production benefit and novelty remain unproved. No
production integration, broad model lane or native execution is needed to test
this design.
