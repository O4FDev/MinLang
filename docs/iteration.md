# Iteration without a collection in the middle

A sequence describes work to do when an item is needed. Creating or sharing a
sequence does not call its transforms. A traversal runs them in source order,
one item at a time, and `break` stops that work immediately.

```minyar
use "sequence" as sequence

function square(number: Integer): Integer { return number * number }
function even(number: Integer): Boolean { return number % 2 == 0 }
function add(total: Integer, number: Integer): Integer { return total + number }

let lights = sequence.range(1, 10).map(square).filter(even)
for light in lights { print(light) } // 4, 16, 36, 64
print(lights.fold(0, add))           // 120
```

`range(first, after)` is an ascending Integer range with an excluded end. Empty
and descending ranges produce no items. Both Integer limits are valid bounds;
creating or finishing a range does not subtract from its first bound or add to
its end bound.

`map(functionName)` changes an item type. `filter(functionName)` keeps an item
when the predicate returns true. `fold(initial, functionName)` visits the items
from left to right, passing the accumulator and item to the combining function.
Its result has the accumulator's type. An empty fold returns its initial value.
The source and initial value are ordinary expressions evaluated once.

Transforms in this first implementation are concrete named functions. They
compile to direct calls. Closures, callback values and generic transform
functions receive an explicit rejection. Existing user methods named `map`,
`filter` or `fold` take precedence over sequence operations.

Recipe types are inferred from their expressions. Modules using these operations
currently take the compiler's whole-graph compatibility path rather than reusing
cached module bodies; cold and warm module-state builds produce the same LLVM.

Sequences accept Lists, Text, Bytes, Maps, Sets and iterable records. Text items
are Characters, Bytes items are Integers, and Map items are keys. The original
collection's iteration behavior remains in effect: a List traversal rereads its
length, while Maps and Sets produce their existing key snapshot.

Map and filter recipes retain the original source rather than taking a copy of
its contents. A later traversal observes later mutations. Reusing a recipe
starts a new traversal; a user iterator that deliberately shares its cursor
also shares progress.

Generic functions can state the same structural contract with
`function total<Source: Iterable>(source: Source): Integer`. A record cursor
with `advance(): Boolean` and a value-returning `current()` satisfies `Iterator`.
The compiler checks the concrete method signatures and infers cursor/item types;
these bounds do not add a conformance object or dynamic dispatch.

## What the compiler emits

The consuming `for` or `fold` unwraps its recipe once and emits one loop. Map
functions and filter predicates appear as concrete calls in that loop. A false
filter branches to the loop's step block, skipping all later stages and the
body. There is no intermediate List, callback record or dynamic dispatch.

The shape for a scalar map followed by a filter is:

```llvm
for.condition:
  ; Read the next source item, or branch to for.end.
  br i1 %has.item, label %for.body, label %for.end
for.body:
  %mapped = call i64 @square(i64 %item)
  %keep = call zeroext i1 @even(i64 %mapped)
  br i1 %keep, label %sequence.keep, label %for.step
sequence.keep:
  ; The original loop body uses %mapped.
  br label %for.step
for.step:
  ; Advance the source and perform ordinary ownership cleanup.
  br label %for.condition
for.end:
```

The actual LLVM retains source locations, concrete symbol names and ownership
operations. `make check-sequences` verifies its direct calls, single loop and
absence of intermediate collection or callback operations, then runs O0/O2
programs with the ownership oracle. `make check-iteration` separately checks
the user-record protocol and its diagnostics.

The reproducible study in `experiments/iteration-study` compares a dynamic List
pipeline with a handwritten loop using the same named transforms. On Linux
x86_64 with Clang 23.1.2, both optimized loop bodies contained 31 static LLVM
instructions and the same five direct call sites: checked multiplication,
checked addition, List access fallback, List length and ownership step. Neither
loop contained an indirect call. The two dynamic inputs produced matching
results, 3104 and 3300. This measures emitted code, not execution speed or
retired instructions; hardware counters were unavailable on that box.

Run `python3 experiments/iteration-study/measure.py --build` on an idle Linux
Boat box through `bx`. It retains source, commands, raw/optimized LLVM, assembly
and a machine-readable report under `build/iteration-study`. It also reports
fixed setup separately: this two-stage pipeline creates two recipe records
outside its consuming loop.

Recipes and range values are ordinary reference records. Building a recipe
allocates one small source-holding record per stage, once; a user `iterator()`
may allocate one cursor per traversal. These fixed setup costs are not erased
by this implementation. Map/filter traversal adds no per-item allocation of
its own. A transform that returns new Text, records or Lists still pays for
those values, exactly as an ordinary call does.
