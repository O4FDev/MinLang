# Automatic ownership in the native runtime

Native programs use non-atomic reference counting with compiler-inserted ownership
operations. Launcher builds use system-backed incremental cleanup with a default
budget of 32 work units per service batch. Total reclamation work grows with the
graph, but the default runtime spreads graph traversal across service points.
The explicit eager profile can perform the entire traversal during a release.
See [the cleanup contract](bounded-runtime-contract.md) for the work accounting
and operations outside that budget; it is not a wall-clock deadline.

## Recursive data and cycle prevention

Recursive record types are supported, including recursion through nested Lists
and mutually recursive records. Trees, persistent chains and shared acyclic
structures can be built with record constructors and List literals; see
[`examples/recursive-tree.min`](../examples/recursive-tree.min).

The conservative restriction applies to mutation, not declarations. For a
mutation of `List<T>`, the compiler asks whether `T` can reach that exact
`List<T>` type by following record fields and List element types. If so, both
`.add` and indexed replacement are rejected with:

```text
this List mutation could create a reference cycle; construct a new List instead
```

For `record Node { children: List<Node> }`, `List<Node>` therefore supports
construction, indexing, iteration and sharing, but not `.add` or indexed
replacement. Even a particular append of a fresh leaf is rejected: proving
individual mutations safe would require additional ownership analysis. A
mutable `List<Integer>` payload remains supported. An external `List<Wrapper>`
where `Wrapper` contains a Node also remains mutable if Node cannot reach
Wrapper. The check uses exact nested List types: a `List<List<Node>>` worklist
is mutable when Node only contains `List<Node>` and has no path back to that
outer List type.

Lists keep their shared reference semantics; nothing is implicitly copied,
frozen or made weak. A function that performs a forbidden mutation is rejected
even if a caller would pass an apparently safe argument. Module aliases,
returned references and helper functions cannot evade the check because every
mutation is checked using its resolved static type. The iterative traversal
visits each reachable record once, and proven-safe List types are cached for
that compilation. Scalar and Text element types need no graph traversal.

The acyclicity argument uses the first possible cycle. A new record or List
literal is unavailable to the source program until its construction finishes;
each field or element is retained or transferred before evaluating subsequent
initializers. Construction therefore cannot introduce the first cycle. That
cycle must instead result from inserting a mutable edge from some List object
of type `List<T>` to a value of type `T`. The existing return path in the heap
would imply a type path from `T` back to `List<T>`, which the checker rejects.
This argument includes transitive record fields, nested Lists and aliases.

The non-mutating `list.appended(value)` operation copies into a fresh List and
is permitted for recursive element types. Because the result does not exist
while its inputs are evaluated, none of them can already point back to it; the
first-cycle proof therefore still holds. This supports dynamic bottom-up tree
construction, at linear cost per append, without weakening the mutation rule.

Arbitrary cyclic graphs remain unsupported. Integer identifiers in a List of
records remain an option; see [`examples/graph.min`](../examples/graph.min).
Inferred lifetime regions and permissive mutation analysis are not implemented.
Dynamic types, closures, foreign pointers, mutable record fields or changes to
the type encoding must revisit this proof before being added.

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
  for the caller.
  `minyar_rc_leave` retires that function's expression and local owners; the
  incremental profiles can complete their reclamation at later service points.
- Functions using only scalars and borrowed parameters can omit ownership frames. Local stack slots are
  allocated once at entry. Eligible leaf functions use compiler-provided storage
  for up to `min(8, K−1)` owner slots when bounded ownership lowering is enabled.
  Their stack storage never enters a deferred queue or cache. Other ownership
  frames use pooled heap storage; K1 keeps that ordinary representation.

## Scalar record replacement

The compiler can eliminate a directly constructed local record whose fields
are all Integer, Boolean or Character values. Its conservative lexical proof
requires every later use of that binding in its scope to be a direct field
projection. Whole-object aliases, arguments, returns, reassignment and container
insertion keep the managed representation. Later same-name declarations also
prevent replacement, even when a more precise analysis could prove them safe.
Records with reference fields and immediately projected constructor expressions
currently keep the managed representation.

Each initializer is evaluated once in source order. The generated field reads
use the captured scalar values, so a replaced object needs no allocation,
reference count or cleanup. Unused records still evaluate their initializers.
The proof relies on immutable fields and a binding that cannot escape or be
reassigned: its initializer definitions dominate every permitted use, including
uses within nested branches or the current loop iteration. Capturing a value
does not reread a mutable initializer input later. Any future feature that
allows whole-object access through another route must revisit this proof.

The analysis charges each attempt before lookahead: eight bytes per field and
at least eight per record, with a 512-byte cap per compiled function or top-level
body. Rejected candidates consume this budget too. At most 64 attempts can scan
the body's tokens, making this additional lookahead work linear in body size
with a fixed factor. The cap also limits captured fields; it is not a physical
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

A native heap object has an eight-byte private prefix: three kind bits and a
reference count. A zero count denotes an immortal object. Compiler-generated
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

See [runtime profiles](bounded-runtime-contract.md) for incremental cleanup and
finite-heap configuration.
