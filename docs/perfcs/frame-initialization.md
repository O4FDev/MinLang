# Retired heap-frame slots remain initialized

Design recorded before a private prototype, October 20, 2026. Baseline:
`7b36666d800fa02619a360327faec220e1dfab8d`. This is independent of the chunk
cache and cycle scheduler batching. The first candidate remains frozen in a
separate checkout while this follow-up is qualified. Measurements and gate
status belong in [results.md](results.md).

The pre-change bounded runtime clears every requested local slot at every
heap-frame entry. Its written-slot index already identifies every local slot
that must be visited at retirement, including slots subsequently moved or
cleared. The proposed invariant is that **all local-capacity value slots in a
fully retired cached heap frame are NULL**, including slots above a later
activation's requested local count.

## Protocol

For bounded heap frames only:

1. After allocating or enlarging a locals buffer, clear its entire new value
   region once: `count * sizeof(void *)`. The written-index region does not
   need initialization; its valid prefix starts empty.
2. A reused frame whose requested count fits its existing capacity skips the
   entry clear. Reset its ordinary activation metadata as before.
3. Each existing pending-frame owner unit decrements the pending index count,
   loads that index, saves the untagged owner in a C local, writes NULL to that
   value slot, then calls the same `rc_drop(saved_owner)`.
4. Frame finalization, cache admission/eviction, queue turns, pending-task
   counts and polling stay unchanged. Clearing does not add a work unit or
   remove an existing null-owner visit.

Eager frames, compiler-provided stack frames, scope cells, temporary chunks and
generated code remain unchanged. No frame layout, runtime ABI or option changes.

## Invariant proof

For a newly allocated zeroed frame header, capacity is zero. A first positive
entry allocates storage and clears the full value region before publication;
a zero-slot frame has no value storage. A successful growth also clears the
full new value region, regardless of its allocator path.

During an active bounded frame, each non-NULL assignment to a slot with a
clear low-bit tag appends its index exactly once and sets the tag. A previously
written slot keeps its tag through assignment, move or clear. A never-written
slot receiving NULL stays NULL. Thus every non-NULL value or tag has exactly
one index, and all other capacity slots remain NULL. Operations only access
valid current activation slots; slots between local count and capacity remain
NULL by induction from the previous retirement.

At leave, the written index is detached with the frame. The next owner unit
removes exactly its last pending index, saves the owner with the tag masked,
clears that slot, and drops the saved owner. Remaining indexed slots and owners
are untouched. A moved slot containing only the tag still consumes its usual
visit and is cleared. A never-written slot needs no visit. Once every indexed
slot was visited, every value slot up to capacity is NULL. Only the following
separate finalization unit can place this frame in the reusable cache. Reuse
therefore starts from exactly the value state previously established by the
entry memset. The stale index array is ignored until overwritten by new
first-write registrations.

The owner must be captured and untagged **before** the NULL store. Looking it
up after the store loses a release; passing the tagged pointer to `rc_drop`
corrupts the object address. The existing index-decrement/reverse visit order
is retained. Clearing a slot after it leaves the valid pending prefix does
not affect the independent graph oracle's owner accounting.

## Growth, recovery and boundaries

The value array and index array share one allocation, with the index base at
`locals + local_capacity`. System `realloc` can leave old index words inside
the enlarged value region; pool `resize_discard` intentionally preserves no
contents and can move to a lower buddy without copying. Therefore clearing
only the newly added suffix is **incorrect**. Clear all new capacity value
slots after every successful growth. The existing size/overflow checks and
fatal allocation failure behavior remain unchanged.

Heap diagnostic unwind calls ordinary `minyar_rc_leave`, so it follows the
same pending visits and cannot cache partially cleared storage. The caller
frame captured by a recovery boundary remains active and unchanged. Pending
frames may outlive a diagnostic longjmp but cannot be reused before finalizing.
Scope unwind owns separate cells. The diagnostic branch for a stack-resident
frame drops bounded stack slots immediately and never caches the header or
buffer; its clearing policy stays unchanged.

The explicit stack API still clears its supplied storage on every admission.
K1, large-slot and otherwise rejected stack requests fall back to ordinary
heap entry and inherit this invariant. Eager/arena fallback behavior is
unchanged. Raw native code that bypasses ownership APIs to mutate internal
`RcFrame.locals` or the written index is outside this proof, as it already is
outside the written-owner protocol.

Cycle counts and snapshot barriers use the saved owner and the unchanged
`rc_drop` path. Collector roots derive from counts/incoming edges rather than
scanning retired frame cells. No owned reference disappears before its count
drop; the C local preserves the address across clearing. Existing non-reentrant
runtime/allocator hooks remain a prerequisite. Frame eviction frees the same
allocation in the same finalization unit. The chunk cache and shared cache
byte allowance are unchanged.

## Work and cost

Let E be the sum of requested local counts over bounded heap-frame entries,
G the sum of new capacities over successful allocations/growth events, and W
the total number of indexed local visits over retirement. The previous value
initialization writes E pointer slots. The candidate writes G slots during
growth and W slots during the already existing owner visits. It retains all
W index/value loads and drops and adds one scalar NULL store per visit.

G is a sum over growth events, not just each frame's maximum capacity: every
growth clears the whole new value region. A warm repeatedly reused frame with
capacity N and w written slots per call changes repeated initialization from
N stores to w stores, after its initial/growth clear. Sparse reuse can make
w much smaller than N. A densely written frame has w approximately N; it has
no promised gain and may lose vectorized memset throughput. Cold frames,
frequent growth, cache eviction or a zero cache allowance can add W stores
without eliminating any entry clear. Each heap-frame owner unit remains one
indexed visit/drop plus O(1) bookkeeping; each finalization remains one unit.
K-total cleanup ceilings and queue fairness are unchanged. This is a volume
argument, not an instruction, pause, RSS or universal speedup claim.

## Qualification before any production change

Add a physical cached-slot oracle that examines **all capacity slots** after
complete retirement, before reuse and after shrinking activations; include
never-written slots, moved and tag-only slots, repeated null assignment,
clear/reassign, aliases and immutable values. At K1, check one visited slot
becomes NULL and cannot release twice while unvisited slots keep their owners.
Require the same release order, work returned, pending debt, recent parity and
next-queue state against the retained baseline. Cached payload bytes are an
intentional stronger invariant, not a required byte-identical stale payload.

Exercise system realloc, fixed/lazy lower-buddy and replacement growth, and
growth within one rounded pool block. Preserve `tests/dead-frame-growth.c`'s
new-capacity NULL and exact layout/recovery assertions. Strengthen existing
sparse frame and stack oracles instead of treating stale cached words as
owners. Cover mixed scoped/heap/stack diagnostic unwind and retained boundary
roots at O0/O2 with ASan/UBSan; include genuine active cycle phases, default
K1/2/7/32/1024, eager controls and stack admission/fallback.

Start with existing bounded/frame models and `check-stack-ownership`, then
`check-bounded`, `check-memory-profiles`, scope/diagnostic/cycle/ownership
checks and the complete required portable gate. Parent runs everything through
bx. Measure same-LLVM default/eager self-compilation and frozen product pairs,
separating sparse reuse, dense reuse and cold/growing frames. Reject regressions
or retain an explicitly narrower policy; do not infer a speedup from fewer
memset calls alone.
