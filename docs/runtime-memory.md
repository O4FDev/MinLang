# Automatic ownership in the native runtime

Native programs use non-atomic reference counting with compiler-inserted ownership
operations. Launcher builds use system-backed incremental cleanup with a default
budget of 32 work units per service batch. Total reclamation work grows with the
graph, but the default runtime spreads graph traversal across service points.
The explicit eager profile can perform the entire traversal during a release.
See [the cleanup contract](bounded-runtime-contract.md) for the work accounting
and operations outside that budget; it is not a wall-clock deadline.

Native implementations for the `io`, `process`, `random`, and `math` modules
live in `runtime/minyar_library.h`, separately from core Text, Bytes, and
numeric operations. They share the runtime compilation unit to preserve each
ownership profile and the bootstrap/native C ABI; the compiler resolves their
public APIs through ordinary module declarations.

## Recursive data and cycle prevention

The compiler supports cycle-capable record/List mutation and typed closures.
It marks the affected type components for traced allocation, and the launcher
links the required runtime automatically. No separate frontend selection is
needed. Activated components include exact hidden capture edges; they do not
use the no-cycles proof below. Programs that require no such feature retain
ordinary LLVM and runtime allocation representations.

Recursive record types are supported, including recursion through nested Lists
and mutually recursive records. Trees, persistent chains and shared acyclic
structures can be built with record constructors and List literals; see
[`examples/recursive-tree.min`](../examples/recursive-tree.min).

For a mutation of `List<T>`, the compiler asks whether `T` can reach that exact
`List<T>` type through its reference edges. If it can, mutation activates the
relevant traced component rather than inserting an untracked cyclic edge.
For `record Node { children: List<Node> }`, construction, indexing, iteration,
`.add` and indexed replacement are all supported, including self-reference.
A mutable `List<Integer>` payload remains untraced. Exact nested types matter:
a `List<List<Node>>` worklist need not itself become cyclic when Node only
contains `List<Node>` and cannot reach that outer List type.

Lists keep shared reference semantics; nothing is implicitly copied, frozen
or made weak. Analysis uses resolved static types across module aliases,
returned references and helper functions. Scalar and Text element types need
no recursive ownership-graph traversal.

The acyclicity argument uses the first possible cycle. A new record or List
literal is unavailable to the source program until its construction finishes;
each field or element is retained or transferred before evaluating subsequent
initializers. Construction therefore cannot introduce the first cycle. That
cycle must instead result from inserting a mutable edge: from some List object
of type `List<T>` to a value of type `T`, or from a record of type `R` to a
value of a reference field type `F`. The existing return path in the heap would
imply a type path from `T` back to `List<T>`, or from `F` back to `R`, and the
compiler therefore keeps those edges out of ordinary untraced components by
activating traced allocation and its mutation barriers. A reference field
whose type can reach its own record is handled by the same analysis.

Scalar field assignment adds no heap edge and is always permitted. This
argument includes transitive record fields, nested Lists and aliases.

The non-mutating `list.appended(value)` operation preserves the input List's
contents and is also permitted for recursive element types. A fresh result
cannot already be referenced by its inputs. Eligible consuming assignments
can reuse uniquely owned storage; an aliased input requires copying.

Map mutations that could create reference cycles remain rejected. Integer
identifiers are an alternative for explicitly managed graph relationships;
see [`examples/graph.min`](../examples/graph.min). Inferred lifetime regions
are not implemented. The no-cycles proof does not cover raw foreign-pointer
mutation; closure capture edges instead participate in the traced component
analysis below. New dynamic types or changes to the type encoding must
establish their own ownership argument.

## Closures, cycles and execution domains

Typed callbacks use `(ArgumentTypes...) -> ReturnType` and anonymous
`function(...)[: ReturnType] { ... }` values. Their environments own exact
capture fields: scalar captures are snapshots and reference captures preserve
aliases. Captured bindings cannot be rebound; a captured record can hold
mutable state. Callback calls use the ordinary owned/borrowed convention.

The compiler includes environment and callback edges in its type
analysis. Cycle-capable mutation activates the relevant strongly connected
type component, with traced allocations, owning-slot barriers and a bounded
snapshot collector. Unrelated acyclic components remain untraced. A traced
allocation adds 32 metadata bytes before the ordinary RC header, plus allocator
rounding. Cycles have real storage and collection costs; ordinary programs do
not acquire atomic counts or dormant collector checks.

Managed heaps remain single-owner. A callback carries its creator's execution
domain and rejects foreign-domain entry before touching ownership or stack
state. Atomic allocation of domain identities does not make a heap shareable.
`workers` provides concurrency through subprocesses and bounded copied Bytes
messages, with a separate heap, caches and ownership frames in each process.
It does not transfer managed pointers or implement shared managed threads.
The scalar-only parallel ABI also excludes managed arguments and results.

`parallel for` borrows scalar buffer storage for one synchronous job. The
compiler proves that each iteration writes only its unchanged index, prohibits
resizing and reference escape, and checks callees transitively for raw/native
effects. Buffer headers stay fixed; worker code reads their lengths and accesses
scalar slots without retaining, releasing, allocating or entering ownership
frames. The owner thread evaluates bounds and snapshots scalar captures once,
then keeps its existing owners alive until every worker acknowledges completion.
Same-index aliases are safe. Arbitrary indexed reads require a buffer that no
iteration writes. The compiler compares potentially aliased input/output roots
before dispatch. Lists compare object identity. Bytes compare backing ranges,
including C-layout views with different headers: shifted overlapping views
cannot be written together or read while another view writes. Direct-index
aliases with the same backing start remain safe. Adjacent disjoint views are
allowed. Guards are needed only for matching buffer types and a nonempty
range. Each buffer pair is checked once, on the owner thread.

Hosted jobs use a persistent pthread pool with one queue per worker and chunk
stealing. Storage is bounded by 64 workers plus each thread's native stack and
the caller's capture words; the pool allocates no managed objects. Pool creation
is lazy. A terminal worker failure exits the process directly after reporting
the checked error, because unwinding through pool shutdown would wait on the
failing job. Normal exits stop and join the pool. Windows executes the same
checked chunks sequentially. Freestanding builds use the installed processor-entry
scheduler, or run sequentially before it is installed. The native scheduler
must join before returning so no worker outlives its borrowed environment.
Reduction scratch storage is allocated and freed by the owner, with one scalar
word per chunk; workers write unique words and the owner merges after joining.

`eventcallbacks.dispatch(dispatcher, timeoutMs, maximum)` runs callbacks on
that owner thread. Its private wait policy first services exactly the selected
cleanup budget. Ordinary retirement debt requests an immediate readiness poll.
When only cycle work remains, including a partially scanned cohort, the wait
is capped at 10 ms; a shorter requested wait stays shorter. With no debt, the
requested wait passes through unchanged. Pending work and cursors stay queued.
This allows idle reactors to yield while collection continues, at the cost of
reclamation latency. For a fixed 4,096-node test graph, budget 32 required 470
batches with at most 4.7 seconds of summed wake deadlines; budget 1 required
18,332 batches with at most 183.31 seconds. These are deterministic deadline
sums, not measured wall times or bounds for growing application graphs. See
the progress tests and tradeoff.
This wait policy belongs to `eventcallbacks.dispatch`. The separate AppKit
`macos.nextEvent` hook services one batch and pumps input without sleeping while
debt remains; see the AppKit cleanup contract.

Current registration barriers distinguish fresh or newly exposed owning edges
from an already proven snapshot cohort. Irreversibly dead private owners are
unregistered before their edges are retired; removing those excluded edges
must not invalidate an unrelated live-path proof. Late-registration, exposure
and private-retirement gates exercise phase interleavings, ownership transfers
and exact cleanup. These checks bound recorded work units; they do not certify
idle CPU or a wall-clock collection deadline. The retained Result-cycle failure
from frozen `907804b` passed a focused replay with the repaired runtime at O0/O2,
native and ASan/UBSan/LSan, with exact `42/41` output and empty stderr.

Typed `Result<T,E>` values use owned records with only the active payload slot
initialized and owning. `Result<Nothing, E>` has a tag-only success with no
initialized payload. Match and expression-level early propagation preserve payload lifetimes
and run scope cleanup; cycles through either payload follow the same
graph analysis. See the Result language contract
and the independent review.

Choices share their payload slots across cases and track only the active
reference fields. A two-case choice with one Text or ordinary managed record
payload uses that payload pointer directly, reserving null for the empty case.
This includes `Maybe<Text>` and `Maybe<Record>` and adds no wrapper object or
reference-count edge. Empty Text headers are non-null. Text key snapshots
retain the immutable payload and return one owned result; record payloads
keep their existing deep snapshot copy.
The compiler keeps the full logical field graph for cycle analysis and projects
nullable aliases to their payload type when choosing traced ownership calls.
Choice, callback and C-layout payloads retain an explicit tag; in particular,
an optional containing another optional must preserve `Some(None)`.
Physical layout kind 3 denotes this nullable payload contract, with zero
choice-owned storage slots. Its niche type may be Text (type 2) or an ordinary
managed record; consumers must classify the payload before reading its layout.

## Compiler/runtime ownership contract

- Managed constructors and ordinary functions returning references produce one owned
  reference. Text literals and bounded runtime caches are explicitly immortal.
  List literals create ordinary managed objects.
- An owned producer carries a compiler-only token identifying its temporary
  registration. A local, return, record field, List append, or List replacement can consume that
  token: registration and the matching retain/drop are omitted. Borrowed values
  never carry this token, and the optimization does not imply heap uniqueness.
- `minyar_rc_keep` adopts other produced references into the current expression.
- `minyar_rc_borrow` retains a borrowed field/element as an expression owner
  when its lifetime may extend across a later call or mutation.
- A chain of field reads borrows intermediate receivers without count changes.
  Indexed expressions and method arguments can run user code, so their
  receivers remain protected. This optimization does not assume pure functions.
- `minyar_rc_local` retains a new local value before releasing the previous
  value, making aliases and self-assignment safe. Synchronous calls borrow
  parameters protected by caller or ancestor owners; incoming parameter ownership
  slots start null. Assignment establishes a new local owner. `minyar_rc_local_take` transfers an already-owned reference
  into the slot and releases its previous value. Lexical scope exit clears locals.
- `minyar_rc_step` releases completed expression owners. It does not scan the
  heap. Nested function calls have separate expression storage.
- A reference return transfers its owned result, or retains a borrowed result
  for the caller. A checked return of a local name, optionally parenthesized,
  moves that local's ownership count to the caller: returning ends the binding's
  lifetime on that path. Other aliases retain their counts. Readonly borrowed
  parameters, fields and indexed values keep the borrowed-return rule; a mutable
  parameter without an established local owner receives a retained count instead.
  Recoverable compiler jobs keep the existing retain-and-cleanup path.
  A complete return expression using Text `+` or List `appended` can consume a
  named local left operand or receiver after argument evaluation. Only the
  complete root is eligible: an inner consumer cannot invalidate a later read
  in the same return expression. Existing consuming runtime operations check
  dynamic uniqueness and copy when aliases remain; traced Lists keep their
  edge bookkeeping. No runtime ABI or reference semantics change.
  Direct reassignment can use the same proof when the named receiver is the
  target binding, including grouped receivers and RHS reads of that binding.
  The old owner ends after all RHS evaluation and before the consuming call;
  assignment roots the new result in its place.
  `minyar_rc_leave` retires that function's expression and local owners; the
  incremental profiles can complete their reclamation at later service points.
- Functions using only scalars and borrowed parameters can omit ownership frames. Local stack slots are
  allocated once at entry. Eligible leaf functions use compiler-provided storage
  for up to `min(8, K−1)` owner slots when bounded ownership lowering is enabled.
  Their stack storage never enters a deferred queue or cache. Other ownership
  frames use pooled heap storage; K1 keeps that ordinary representation.

## Scope ownership lowering

The launcher selects scope ownership for `--memory-profile eager`, including
incremental module builds and release builds. The direct compiler exposes the
same lowering as `--scope-owners`. It replaces local-frame lookups with explicit
retain, store and release operations. Each remaining expression producer receives an initialized-null stack
cell. A control-flow walk places its release at the first statement cleanup or
return on every reachable path, including both sides of a conditional and loop
exits. Cleanup visits only cells that can be live there. A producer that could
repeat before cleanup, or a function needing more than 256 cells, keeps the
ordinary frame representation.

A plain temporary borrow immediately retained into a local or returned value
shares that lasting owner's count. This requires adjacent emitted operations;
intervening calls, branches and traced borrows keep their temporary owners.
Local cleanup polls remain, and a coalesced return explicitly services pending
work before unlinking its scope.

A projected Text used only by the immediately following text equality call
needs no temporary count. This requires a plain borrow from the generated
record or checked List getter. The lowering audits every use of both the
pointer and its raw field value; another use, an intervening call or an
unsupported local identifier keeps the owner. Traced borrows keep their
barriers. Statement and return service points remain present.

The same lifetime proof covers ordinary text joins and text search: their
allocation and lazy index work preserve the argument's existing parent owner
and invoke no user callbacks. A consuming text join qualifies only for its
borrowed right operand; its left input still needs the transferred owner.

A 24-byte stack header links the cells for compiler diagnostics. Diagnostics
release these roots before jumping back to their native recovery boundary;
normal returns clear cells explicitly and unlink the header. Neither the header
nor its cells enter a heap queue or cache. Traced retains and cycle service points
remain present, and the final cycle drain waits for both kinds of ownership root.
Reference arguments still borrow their callers; consuming an unowned parameter
first creates the consumer's count.

Eager scope releases inline the count decrement for shared untraced values
when no destruction or collector work is pending; immortal values return
without a write. Last owners, traced values and pending work use the ordinary
release path. Incremental profiles keep their ordinary release and service
accounting. Null cells do not request an unlimited cycle drain.

The direct compiler rejects combining this mode with `--bounded-owners`. The
system, fixed and lazy launcher profiles retain ordinary bounded lowering.
Linking scope output against an incremental runtime preserves ownership but performs a separately budgeted
release for each live cell, followed by a service batch. The ordinary frame's
single K-total limit for statement cleanup or frame exit therefore does not apply
to this experimental sequence. It is not a replacement for that bounded contract.

## Scalar record replacement

The compiler can eliminate a directly constructed local record whose fields
are all Integer, Float, Boolean or Character values. Its conservative lexical proof
requires every later use of that binding in its scope to be a direct field
read or write. Whole-object aliases, arguments, returns, reassignment and container
insertion keep the managed representation. Later same-name declarations also
prevent replacement, even when a more precise analysis could prove them safe.
Records with reference fields and immediately projected constructor expressions
currently keep the managed representation.

The binding's local ID is reserved before checking its initializer, without
adding the name to scope early. A match expression can allocate its own locals
without changing which binding owns the captured field metadata.
Each initializer is evaluated once in source order. Readonly fields use the
captured scalar values. A record with direct field updates instead uses private
i64 field slots allocated once at function entry; field reads load the current
value, and assignments store it. Loop-local construction initializes those slots
again on each iteration. Compound assignment captures the old field before
evaluating its right operand, matching managed records. LLVM can promote these
slots to registers and branch/loop values at O2.

Neither representation allocates a managed record or needs reference counting
or cleanup. Unused records still evaluate their initializers. The binding must
not escape or be reassigned, so no outside alias can observe private storage.
Readonly candidates keep their previous LLVM at O0. Any future feature that
allows whole-object access through another route must revisit this proof.

The analysis charges each attempt before lookahead: eight bytes per field and
at least eight per record, with a 512-byte cap per compiled function or top-level
body. Rejected candidates consume this budget too. At most 64 attempts can scan
the body's tokens, making this additional lookahead work linear in body size
with a fixed factor. The cap also limits captured and addressable fields; it is not a physical
stack-size guarantee. LLVM handles remaining locals and register spills.

## Readonly parameter bindings

A parameter that is never reassigned can use its incoming LLVM SSA value
directly, without a local load/store slot. This changes storage for the binding,
not the value's ownership: managed arguments remain borrowed under the caller's
existing protection. List element writes and `add` keep their shared mutation
semantics and do not themselves reassign the parameter. Returned borrows and
protection during later argument evaluation follow the existing rules.

The compiler scans each eligible function body once, matching assignment names
against at most 64 parameters. Nested scopes and branches are included; string
contents do not affect brace depth. Any same-name assignment conservatively
keeps the original local slot, including assignments to shadowing bindings.
Functions with more than 64 parameters keep all original slots without this
body scan. Thus this analysis has a fixed-factor linear work bound, separate
from the scalar-record proof-attempt budget.

The proof is that every accepted binding retains its original incoming value
throughout its scope. Immutable argument-operand output pieces identify those
values; mutable bindings preserve their original LLVM local identifiers.
Readonly identifiers cannot enter scalar-record or ownership-slot metadata.

## Representation and destruction

An ordinary native heap object has an eight-byte private prefix: three kind
bits and a reference count. Traced allocations additionally carry the metadata
described above. A zero count denotes an immortal object. Compiler-generated
Text globals include the same prefix and expose the payload using an LLVM
constant offset expression. Native calls must never pass an unprefixed object
to ownership operations.

Text owns its bytes and Unicode index. Lists are marked as containing references
or scalar values. Records store a field count followed by inline fields; a
two-Integer record requests 32 bytes including the ownership prefix. Generated
LLVM accesses managed records through runtime calls, while scalar-replaced
records use captured values.

Records with reference fields have a byte per field identifying owned references.
Scalar-only records omit that map. Cleanup releases only initialized reference
fields, so integer bits are never mistaken for pointers. Container insertion
retains a borrowed reference or takes an owned one. Replacement either retains
the borrowed new element or consumes a compiler-proven owned result, then
releases the old element.

In incremental profiles, reference-bearing aggregates reaching zero count and
detached heap ownership storage become queued work. Leaf values can be freed
immediately without graph traversal. The runtime visits fields and retires tasks in budgeted
batches, using the dead objects' own storage for queue links and cursors. It
does not scan the live heap. Total reclamation work remains proportional to
what is destroyed, and queued storage can remain resident between service
points. Allocator calls and copying have separate costs outside that budget.

The eager profile frees leaves directly and processes reference containers with
an iterative queue, avoiding recursive C-stack destruction while still allowing
a graph-sized release. Its queue/frame buffers can retain their high-water
capacity. Incremental profiles bound cached ownership-frame bytes separately.
The integer-to-Text cache has at most 32,768 entries; Text literals and ASCII
Character texts live for the process lifetime.

Text values are immutable. A full-range slice retains the same Text, and most
partial slices use a view that retains the source's owning root. Nested slices
are flattened to that root, keeping destruction depth constant. A slice below
one eighth of a source larger than 4 KiB is copied instead, preventing a tiny
token from retaining a large file or argument. Unicode indexes belong to each
Text header and are built lazily. They store one byte-position breadcrumb per
64 characters, using 32-bit entries below 4 GiB; an indexed operation decodes
at most 63 characters from the nearest breadcrumb. Two words at the end of the
lazy index remember the most recent character position and byte offset.
Sequential indexing resumes from that cursor and decodes each character once;
backward and random access falls back to the nearest breadcrumb. Keeping the
cursor in the index allocation avoids increasing the header cost of ASCII Text.

In incremental profiles, destroying a view consumes one work unit. A backing
root made unreachable by that destruction is queued for a separate work unit;
it can remain allocated after the release when its poll budget is exhausted.

Binary Text joins normally borrow both operands. A fresh owned left result, or
the left local in a direct `text = text + piece` replacement, supplies an
ownership token to the consuming join:
the runtime reuses a unique owning Text and grows its byte allocation
geometrically, while shared values and slice views take the immutable copying
fallback. Thus a direct `a + b + c + ...` expression performs linear aggregate
copying without changing the value observed through aliases. `joinText` remains
the preferred single-allocation operation for a dynamically accumulated List.
For self-replacement, the compiler clears the local owner only after evaluating
the right operand, so `text = text + text` remains valid. Shared locals still
take the copying fallback, so aliases continue to observe the original
immutable value.

Ownership-using functions place a cleanup service point on every loop backedge,
so a long scalar phase after releasing a graph cannot starve pending retirement.
The compiler removes these calls from functions that never acquire managed
owners. This guarantees progress per completed loop iteration, not a wall-clock
deadline for code that reaches no further runtime or loop service point.

Compiler-arena builds retain storage until process exit and compile away ownership
hooks. Their short-slice cache can evict an entry without invalidating aliases
because the underlying arena storage remains alive.

## Checks

| Target | Coverage |
| --- | --- |
| `make check-ownership-policy` | Compiler budget selection, nonleaf fallback, module policy identity and edited delta replay |
| `make check-stack-ownership` | Independent graph/debt accounting, stack lifetime, native/sanitizer and fallback profiles |
| `make check-runtime-cache` | Standard runtime reuse, dependency invalidation and custom settings isolation |
| `make check-ownership` | Native and sanitized reference lifetimes with exact cleanup accounting |
| `make check-runtime-unit` | Object/byte counts, deep cleanup, alias mutation, Unicode, slice-view roots, retention guard, and geometric Text growth |
| `make check-memory` | Discarded-text RSS and nested/returned aliases |
| `make check-adversarial` | Evaluation order, transfers, and control flow |
| `make check-ownership-mutation` | Detection of injected ownership leaks |
| `make check-ownership-stress` | Generated type graphs and alias programs |
| `make check-recursive-data` | Construction, traversal, sharing, and mutation rejection |
| `make check-scalar-record-storage` | Initializer order, escape analysis, shadowing, and analysis limits |
| `make check-readonly-parameters` | Mutable fallback, alias lifetimes, and parameter boundaries |
| `make check-compiler-slice-cache` | Collisions, eviction, Unicode, and surviving aliases |
| `make check-cycle-registration-exposure` / `-sanitize` | Standalone exposure/late-registration schedules and both Result payload-cycle cleanup oracles |
| `make check-cycle-registry-growth` / `-sanitize` | Registered-graph growth with exact reachability, cleanup and work assertions |
| `make check-cycle-private-retirement` / `-sanitize` | Operation-aware retirement, phase/reuse controls and private locality bounds |
| `make check-cycle-progress` / `-sanitize` | Live-cohort progress, exact reclamation and the separate strict idle CPU assertion |

The graph and callback checks additionally include
`tests/managed-graphs.min`, `tests/managed-graphs-profiles.min`,
`tests/callbacks.min`, `tests/callback-domains.min` and `tests/cycle-progress.min`.
Their exact reachability, object/debt and work-budget assertions complement
application soaks; short collector tests do not establish a server's idle CPU
or large-connection behavior. Windows supports system, fixed and eager heaps;
its lazy heap requires the absent POSIX mmap backend and explicit lazy requests
fail rather than being counted as passing cases. At frozen `a154153`, actual
Windows native progress passed all 21 cases, but sanitizer progress failed the
unchanged 2% idle assertion at `system-k1024/n2048`. That timed failure remains
unresolved, independently of passing registration and locality controls.

See [runtime profiles](bounded-runtime-contract.md) for incremental cleanup and
finite-heap configuration, and the v2 verification map
for source-specific evidence and remaining platform checks.
