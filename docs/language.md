# The Minyar language

The LLVM compiler and runtime define this language contract. Minyar targets
share its types, reference semantics and failure behavior. The separate
`--experimental-swift` and `--experimental-swift-source` dialects explore Swift
interoperability. Their value types and additional syntax are outside this
contract. An alternative compiler must pass the same language conformance
tests before it can become a Minyar backend.

Ordinary Minyar also runs inside a native mobile application. The
[mobile guide](mobile.md) describes UIKit over the shared `ui.View` model,
iOS device and Simulator targets, and Android NDK embedding with a shared-view
Activity renderer. These use ordinary functions, records and native calls;
no separate mobile dialect is needed.

## Tests beside the code

A module can keep named tests beside its declarations. Tests can use private
functions and fields in their own module:

```minyar
function double(value: Integer): Integer { return value * 2 }

test "two small numbers make something whole" {
    expect(double(21) == 42)
}
```

`minyar test` discovers tests in every `src` directory in the resolved project
and its dependencies, including nested modules. Each test runs in a separate
process; a failed test does not prevent the remaining tests from running.
Existing `tests/*.min` programs run too. A substring filter matches module
paths, test names and integration-test filenames.

Two module tests can run at once. `MINYAR_TEST_JOBS=1 minyar test` runs them
serially; the setting accepts 1–64 workers. Each case's captured output is
reported together, in discovery order. All module test binaries are built
before their cases begin running.

`expect(condition)` requires a Boolean. A failed expectation includes its
source expression and file:line:column. A direct comparison also shows the
right and left values, evaluated once from left to right. Scalars and finite
records render their values; collection fields show their type. Compound
Boolean conditions keep ordinary short-circuit evaluation.

Discovery reads source without running module initializers or linking modules
which contain no tests. The low-level `--list-tests` option prints each case
index followed by a tab and its JSON-quoted name.

Tests are omitted from ordinary builds, including their literals and runtime
features. Their bodies are checked when testing. Module initializers run in
each test process; the application entry point and executable top-level
statements do not. `test` and `expect` remain ordinary identifiers outside
their test syntax. The low-level `--test-mode` compiler/launcher option builds
a module's test executable; run it with `--list`, a zero-based case index, or
no argument to run its cases in order.

## Documentation beside the code

Write `///` immediately above a declaration to describe it. Consecutive lines
form one comment; an empty `///` line begins a new paragraph. A blank source
line separates the comment from the declaration. Fields and choice cases can
have their own comments too:

```minyar
/// A named light beside the water.
public record Lantern {
    /// The place someone will look for.
    name: Text
    /// The light we have to give.
    light: Integer
}
```

`minyar --doc-json FILE.min` prints versioned JSON containing public
declarations, original signatures, comments, members and file:line:column
spans. Private declarations and private fields are excluded. Generic
parameters, constraints, choices, methods and type aliases keep their source
spelling. This reads syntax; use `minyar check` to check a project's types.
Documentation emits no runtime code or literals.

`minyar doc` builds an offline API reference at `target/doc/index.html`, with
original signatures, rendered comments and local search. Every fenced
`minyar` example is compiled and run before publication; a following `output`
fence gives its exact standard output. The documented module is imported as
`api`. Examples can contain `test` blocks and run with `minyar test` too.
A failed example preserves the previous documentation. A source directory
without a manifest can use `minyar doc --path library`.
See [documentation beside the code](documentation.md) for the full format.

## Bindings and scope

`let` introduces a local value. A name exists from its declaration to the end
of its lexical block. Assignment changes its value without changing its type.

Inside a block, `constant` creates an immutable binding. Its initializer may
be any expression and its type can be inferred:

```minyar
function example(): Integer {
    constant answer = 20 + 22
    constant values = [answer]
    values.add(1)             // the referenced List remains mutable
    return values[0]
}
```

Immutability applies to the binding; it does not freeze a referenced object.

```minyar
let attempts = 3
attempts = attempts - 1
attempts -= 1
```

Compound assignment (`+=`, `-=`, `*=`, `/=`, `%=`) applies the operator to the
current value and stores the result. It works for locals, record fields and
List positions, with the same type rules as the operator itself.

## Numbers and comparisons

`Integer` ranges from -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807.
Arithmetic overflow and division by zero stop the program with an error.
Integer literals outside this range are rejected.
The minimum value is spelled `-9223372036854775808`. Hexadecimal literals such
as `0xFF` and octal literals such as `0o755` are also Integers. Decimal Integer
literals cannot have a leading zero: `0755` is a compile error, so file modes
cannot silently become decimal. Use `0o755` (493) or plain decimal `493`.

`Float` is an IEEE 754 double-precision number. A Float literal has digits on
both sides of its point, with an optional exponent: `1.0`, `0.25`, `6.02e23`.
Float arithmetic follows IEEE 754, so dividing by zero gives an infinity rather
than stopping. Printing a Float always shows a point or exponent, using the
shortest digits that read back as the same value:

```minyar
print(0.1 + 0.2)       // 0.30000000000000004
print(Float(7) / 2.0)  // 3.5
print(Integer(-7.9))   // -7
```

Exact integral Floats strictly inside ±2^53 format directly as decimal digits
followed by `.0`, without calling the C formatting or parsing libraries.
Zero retains its sign. Other finite values keep the shortest-roundtrip rule.

Integer and Float never mix implicitly; convert with `Float(integer)` or
`Integer(float)`. `Integer` truncates toward zero and stops if the Float is NaN
or outside the Integer range. `Integer(character)` gives a code point and
`Character(integer)` accepts any Unicode scalar value.

Import `use "math" as math` for Float mathematics: `math.sqrt`, `math.sin`,
`math.cos`, `math.tan`, `math.asin`, `math.acos`, `math.atan`, `math.atan2(y, x)`,
`math.exp`, `math.log`, `math.pow(base, exponent)`, `math.floor`, `math.ceil`
and `math.round` (halves round away from zero). Core `abs`, `min`, `max` and
`clamp(value, low, high)` accept Integers or Floats of one type.

Integers also support bitwise `&`, `|`, `^`, `~` and the shifts `<<` and `>>`
(arithmetic). A shift count outside 0 to 63 stops the program. For hashing and
random number generators, `wrappingAdd`, `wrappingSubtract` and
`wrappingMultiply` wrap around instead of stopping on overflow.

For recoverable signed Integer overflow, import `errors` and use
`errors.checkedAdd(left, right)`, `errors.checkedSubtract(left, right)` or
`errors.checkedMultiply(left, right)`. Each returns `errors.IntegerResult`.
Check `errors.integerOk(result)` before reading `errors.integerValue(result)`;
reading a failed result still stops the program. Overflow carries
`errors.overflowCode()` (13), native code 0, and an operation-specific message.

```minyar
use "errors" as errors
let result = errors.checkedMultiply(9223372036854775807, 10)
if errors.integerOk(result) {
    print(errors.integerValue(result))
} else {
    print(errors.message(errors.integerError(result)))
}
print("still alive")
```

Operators bind in this order, tightest first: `*`, `/`, `%`; then `+`, `-`;
then `<<`, `>>`; then `&`; then `^`; then `|`; then `<`, `>`, `<=`, `>=`;
then `==`, `!=`; then `&&`; and finally `||`. Operators at the same level
associate left to right. Thus `1 << 2 + 1` is `1 << (2 + 1)` and
`value & 1 == 0` tests the lowest bit.

There is one equality operator: `==`. It never converts either side. Both sides
must have the same type, and values compare by meaning—`Text` compares its
contents. `!=` is its direct opposite. Ordered comparisons accept `Integer`,
`Float`, `Character`, `Boolean`, `Text` or Ordered records. Boolean orders
`false` before `true`; Text uses the lexicographic order of natural List sorting.
Arithmetic accepts `Integer` or `Float`
operands; `+` also joins two `Text` values. These operators never coerce
Boolean values into numbers. A NaN Float is unequal to everything, itself
included.

## Constants

Function declarations cannot use a [reserved built-in name](#reserved-function-names).
The compiler identifies the colliding name and suggests a rename.

At module scope, `constant` declares a compile-time value that every function in the module
can use. It is a declaration, like a function or record, and `public` exports
it from a module:

```minyar
constant CHUNK_SIZE = 16
constant GRAVITY: Float = -9.81
constant TITLE = "Minyarcraft"
```

A literal value may omit its type annotation: an Integer, Float, Text,
Character or Boolean, optionally negated. Integer constants also accept
arithmetic, parentheses, bitwise operators and other Integer constants,
including forward references and public constants from imported modules:

```minyar
constant PAGE_BYTES = 1 << 12
constant HEADER_BYTES = 14 + 20 + 8
constant PAYLOAD_BYTES = PAGE_BYTES - HEADER_BYTES
```

These expressions run in the compiler. Their results become ordinary literals;
they allocate nothing and need no startup code. Arithmetic has the same checked
64-bit limits as an ordinary Integer expression. Invalid shifts, division by
zero, overflow, recursive dependencies and expressions deeper than the compiler's
128-level limit are compile errors. A native record's `Bytes[expression]` field
length can use the same expressions and constants. Functions, mutable globals
and allocation are not available during constant evaluation.

### Immutable Integer tables

At module scope, a bracket initializer declares an immutable table of Integers.
Every element is evaluated by the compiler, with the same arithmetic and overflow
rules as scalar constants:

```minyar
constant PORTS = [80, 443, 8000 + 80]
constant COUNT = PORTS.length
constant HTTPS = PORTS[1]

function port(index: Integer): Integer { return PORTS[index] }
```

Tables support indexing and `.length`. They cannot be changed, passed as values,
returned or assigned to another binding. A table declaration has no type annotation.
Use a local List or an explicitly typed `global` when you need a mutable collection.
The same bracket syntax inside a function still creates an ordinary List.

Table data occupies eight bytes per element in read-only static storage, with no
allocation, initialization code, ownership root or getter. Each dynamic access
evaluates its index once, checks its bounds and loads an Integer. Optimization may
remove a proven bounds check. An indexed module also contains one shared
bounds-failure helper and message. `.length` is a literal with no runtime work; a table
used only for compile-time values needs no runtime data. Empty tables have length
zero, and every index into them fails. A bad index during constant evaluation is
a compile error; a bad runtime index stops the program with a source stack trace.

Scalar expressions and table elements can refer to table lengths and constant
indexes, including declarations written later. Cyclic value dependencies reject.
Lengths are determined by the source structure, so `constant T = [T.length]` is
well defined. Dependencies between elements of the same table still count as a
table value cycle. Existing compiler evaluation-depth limits apply.

### Runtime globals

A module constant cannot execute initialization code. Use an explicit immutable `global` binding for runtime
initialization. A nonliteral global initializer requires a type annotation:

```minyar
global MODES: List<Integer> = [0o644, 0o755]
global CRC_TABLE: List<Integer> = makeTable()
```

Global initializers run once before `main()` or the entry module's
top-level statements, including declarations in imported modules. Repeated and
diamond imports share the same module table. An initializer may depend on another
global; recursive initialization stops with a clear error. Literal module
constants are substituted directly and cannot cause initialization side effects.

The binding cannot be reassigned. A List, Bytes or record value retains its usual
mutable alias semantics; initialize lookup tables once and share them within the
owning domain. Normal return from the executable entry releases the module roots.

## Contracts

A function can describe the conditions it needs and the promises it makes:

```minyar
function share(light: Integer, people: Integer): Integer
    requires(light >= 0)
    requires(people > 0)
    ensures(result >= 0 && result <= light) {
    return light / people
}
```

`requires(condition)` checks entry, before the body runs. `ensures(condition)`
checks every normal return, including an error returned by `try`. In an ensures
clause, `result` is the returned value. A function returning Nothing can make
promises about its parameters without naming a result. Conditions must be Boolean.
Clauses can repeat and span lines. Functions and record methods can both use
them, including generic functions.

`invariant(condition)` checks both entry and normal return. On a method, it can
describe the state that an operation must preserve:

```minyar
record Lantern { light: Integer }

function Lantern.share(amount: Integer)
    requires(amount >= 0 && amount <= self.light)
    invariant(self.light >= 0) {
    self.light -= amount
}
```

These are function boundary invariants; they do not watch individual field
assignments or loop iterations. Entry clauses run in header order, omitting
ensures; exit clauses run in header order, omitting requires. Scalar parameters
in exit conditions retain their entry values. Reference parameters and `self`
observe the body's changes. A body runs once and its return value is evaluated
once. A failed check stops with its clause, source expression and file:line:column.
An abort, `fail` or process exit does not run exit contracts.

Default and debug builds check contracts. Tests check them even with `--release`.
Ordinary release builds remove the clauses before name resolution and code
generation, including their calls, literals and wrapper functions. A release
contract therefore has no runtime cost. An enabled contract costs its predicate
computations and branches, plus an ordinary wrapper call and the usual ownership
work for its arguments and result, with static failure messages; LLVM may inline
the calls. Predicates may call
ordinary functions, so write them without side effects that the program needs.
They are debug checks, not validation for untrusted input.

The words `requires`, `ensures` and `invariant` are contextual in function headers;
existing functions, fields and local variables with those names keep working.
Put entry-point checks on a function called by `main`. Native functions need an
ordinary Minyar wrapper to add contracts.

## Loops

`while condition { ... }` repeats while a Boolean holds. `for` visits a range
of Integers, the elements of a List, or the Characters of a Text:

```minyar
for position in 0..3 {
    print(position)    // 0, 1, 2: the end is excluded
}
for word in ["Min", "yar"] {
    print(word)
}
```

A range's bounds and a loop's collection are evaluated once. The loop variable
is a fresh binding for each iteration, so assigning to it does not change which
value comes next. A List loop rereads the List's length on every iteration.
`break` leaves the innermost loop and `continue` starts its next iteration.

A record can be iterable too. Its `iterator()` method returns a record cursor.
The cursor's `advance(): Boolean` moves to the next item and says whether one
exists; `current()` returns that item. All three methods take no arguments:

```minyar
record Countdown { start: Integer }
record CountdownCursor { remaining: Integer }

function Countdown.iterator(): CountdownCursor {
    return CountdownCursor { remaining: self.start }
}
function CountdownCursor.advance(): Boolean {
    if self.remaining <= 0 { return false }
    self.remaining -= 1
    return true
}
function CountdownCursor.current(): Integer { return self.remaining }

for number in Countdown { start: 3 } { print(number) } // 2, 1, 0
```

The loop evaluates its source and calls `iterator()` once. Before each turn,
it calls `advance()` and, only when that returns true, `current()`. An empty
cursor never calls `current()`. Assigning the loop variable does not change
the cursor. A fresh cursor makes nested and repeated traversals independent;
a method that returns `self` deliberately shares progress with its aliases.
Methods used outside their module must be public.

Iteration checks this method shape structurally. It uses ordinary direct calls
and a branch loop, with no dispatch table, intermediate List or per-item wrapper.
The source and cursor keep their ordinary record allocation and ownership costs;
allocations inside user methods remain their own costs. `current()` can return
any value type, including a record or a List, but cannot return `Nothing`.
`parallel for` continues to require an Integer range.

Import `sequence` for lazy `sequence.range(first, after)` values. Iterable values
also support `.map(functionName)`, `.filter(functionName)` and
`.fold(initial, functionName)` with named functions. Generic transforms infer
concrete type arguments from the items and fold seed, retaining direct calls and
ordinary generic constraints. Stored recipes do no transform work until
traversed. Map/filter chains fuse into one loop with direct calls, and fold
combines items from left to right. Eligible named chains used directly as an
ordinary `for` source remove their recipe setup. Stored recipes and chains passed
to `fold` keep one small record per stage; declined source forms retain the same
setup. Traversal has no intermediate Lists or per-item protocol wrappers.
Source records and cursors keep their own costs. See [lazy iteration](iteration.md)
for examples, setup limits and the generated LLVM shape.

Conditions accept only `Boolean`.

## Types and built-in operations

The value types are:

- `Integer`: a signed 64-bit whole number.
- `Float`: an IEEE 754 double-precision number.
- `Bytes`: a growable sequence of bytes.
- `Text`: Unicode text, encoded as UTF-8.
- `Character`: one Unicode scalar value, including non-ASCII literals.
  Printing a Character encodes it as UTF-8.
- `Boolean`: either `true` or `false`.
- `Nothing`: the absence of a returned value.

Text preserves embedded zero bytes. Its `length` counts Unicode scalar values
(not grapheme clusters), and indexing produces a `Character`:

```minyar
let language = "Min" + "yar"
print(language.length) // 6
print(language[0])     // M
print(language.slice(0, 3)) // Min
print(Text(42))        // 42
```

`text.slice(start, end)` returns the characters from `start` up to, but not
including, `end`. Positions count Unicode characters rather than UTF-8 bytes,
and an invalid range stops with a descriptive bounds error.

Import `use "process" as process` for `process.argumentCount()` and
`process.argument(position)`, excluding the executable name. Import
`use "io" as io` for `io.readTextFile(path)` and `io.writeTextFile(path, text)`.
`io.writeTextParts(path, pieces)` streams a `List<Text>` without allocating its
concatenation. A program that produces large output in small pieces, such as
the compiler, avoids holding the whole file twice.

Every Text contains valid UTF-8, including values returned by files and native
libraries. Invalid input is rejected at the conversion boundary.
`text.byteLength` counts encoded bytes, including embedded zero bytes.
Keep arbitrary file contents in Bytes. Import `text` and call
`text.decode(bytes): Result<Text, errors.Error>` for recoverable decoding;
invalid UTF-8 produces `errors.invalidDataCode()`. Character-offset caches
remain lazy.

Import `unicode` when a character should mean a whole visible cluster:

```minyar
use "unicode" as unicode
print("é".length)                       // 2 scalar values
print(unicode.graphemeCount("é"))          // 1 grapheme cluster
for piece in unicode.graphemes("👩🏽‍🚀🌙") { print(piece) }
print(unicode.canonicallyEqual("é", "é"))  // true
print(unicode.caselessEqual("Straße", "STRASSE")) // true
```

`unicode.graphemeBoundaries(value)` returns scalar offsets, including zero and
the end, suitable for `value.slice`. Empty Text has the single boundary `[0]`
and no graphemes. Segmentation follows Unicode 18.0.0 extended grapheme
clusters, including combining marks, joined emoji, flag pairs, Indic conjuncts
and CRLF. `unicode.unicodeVersion()` reports the pinned Unicode data version.
A grapheme cluster is a text boundary, not a promise about a font's display width.

`unicode.normalized(value)` returns canonical composition (NFC).
`unicode.canonicallyEqual(left, right)` compares these canonical spellings.
`unicode.caseFold(value)` creates a canonical, locale-independent comparison key
using full default case folding; `unicode.caselessEqual` compares those keys.
Folding handles expansions such as `ß` to `ss` and preserves accents.
It decomposes before folding and composes afterward, so canonically equivalent
spellings keep the same key. It is not a display-oriented lowercase operation.
These operations preserve embedded zero bytes and control characters; they do
not strip marks or apply compatibility normalization. Ordinary `==`, ordering,
hashing, `length` and indexing retain their exact-content and scalar contracts.

`unicode.uppercased(value)` and `unicode.lowercased(value)` apply full default
Unicode casing for display, including multi-character expansions (`ß` to `SS`)
and Greek final sigma. They use the original input for context and preserve
its scalar order. They do not implicitly normalize. Default casing is
locale-independent; Turkish, Azerbaijani and Lithuanian tailoring is not applied.
Use `caseFold` when making comparison keys rather than comparing lowercase text.

The Unicode provider is linked when the `unicode` module is imported.
Counting scans once and allocates no boundary storage. Boundary lists scan
twice and allocate one temporary byte per scalar plus their Integer List;
splitting also creates Text slices and may build the scalar-offset cache.
Normalization, folding and display casing allocate native temporary buffers and copy their
output into managed Text. Folding first allocates a decomposed intermediate.
Casing uses two linear passes with a checked, exactly sized output buffer.
Native scratch storage uses the system allocator rather than the selected
Minyar heap profile. Unicode tables add read-only program data when linked.

Normalization and folding take linear time in the input size for the pinned
Unicode tables. Canonical reordering uses stable counting sort for disordered
runs longer than 16 combining marks, with four scratch bytes per scalar in the
largest such run. Shorter runs use bounded insertion sort; they and already
ordered input need no sorting buffer. Recursive decomposition uses four bytes
per resulting scalar before in-place UTF-8 encoding and an optional buffer
shrink. Normalize complete keys after concatenating their parts.

`joinText(parts)` joins a `List<Text>` into one Text value.

Text literals can include expressions inside `\(` and `)`:

```minyar
let name = "Ada"
print("Hello, \(name)! You have \(20 + 22) messages.")
print("The answer is \(true), and the star is \('★').")
```

An expression may produce Integer, Float, Boolean, Character or Text. Calls,
parentheses and nested text literals work inside an interpolation. Expressions
run once, from left to right. For records, Lists and Bytes, choose a Text
representation explicitly before inserting it. `\\(` writes a literal `\(`.
Other text escapes keep their usual meaning.

One interpolation uses one `joinText` over its literal and converted parts,
with one exactly sized output byte buffer. The parts List, the Text header,
and conversions of scalar values have their own allocations; this does not
promise one allocation for the entire expression.

Multi-line Text uses three quotes. Its opening delimiter is followed by a
newline, and its closing delimiter sits on its own line:

```minyar
let invitation = """
    Dear \(name),
        There is a light in the harbour.
    Come home when you are ready.
    """
```

The newline after the opening delimiter and the newline before the closing
delimiter are omitted. Each content line loses as many leading spaces or tabs
as precede the closing delimiter; each space or tab counts as one column.
A nonblank line needs at least that much indentation. Short blank lines are
allowed, and additional indentation is preserved. CRLF line endings become LF.
To retain a final newline, leave an empty line before the closing delimiter.
Escapes and interpolation work as in ordinary Text. A backslash followed by a
physical newline continues a line without including that newline; the next
line still loses the closing delimiter's indentation.

Raw Text surrounds its quotes with `#`. Backslashes, quotes and interpolation
markers are literal characters; only the matching quote-and-`#` delimiter ends
the value:

```minyar
let path = #"C:\Users\Ada\notes.txt"#
let program = #"""
    print("Hello, \(name)!")
    """#
```

Raw multi-line Text follows the same indentation and newline rules. It does
not interpret escapes, interpolation or line continuation.

`List<T>` holds values of type `T`:

```minyar
let tokens: List<Text> = []
tokens.add("function")
print(tokens[0])
print(tokens.length)
```

Lists can also be constructed directly from values of one element type:

```minyar
let words = ["Min", "yar"]
let nested: List<List<Integer>> = [[], [1, 2], []]
print(joinText(words)) // Minyar
```

Nonempty literals infer their element type. Empty literals use the type of an
annotated binding, record field, function parameter or return, assignment, or
surrounding typed List literal. An empty List with no such context still needs
an annotation. Literal elements are evaluated from left to right; a comma
separates elements, and a trailing comma is allowed.

In a Result-returning function, a temporary owner protects a List's partially
built contents when `try` returns an error. Successful construction adds one
retain/release pair, including for an interpolation's parts List.

A List is a reference value: aliases observe the same additions and indexed
replacements, including those performed by functions. Mutations that could
create a record/List ownership cycle activate traced allocation, as described
below. Reading or writing
outside a List's bounds stops with a clear error.

`list.sort()` stably orders its elements in place and returns `Nothing`;
aliases observe the same List. `list.sorted()` returns a fresh shallow copy.
Natural order supports Integer, Character (code point), Boolean (`false`
before `true`), Float, and Text (lexicographic unsigned UTF8 bytes). Float
NaNs come last and compare equal to one another; signed zeros compare equal.
Equal elements keep their original order. Text sorting does not build its
lazy character-offset cache.

`list.sortBy(compare)` and `list.sortedBy(compare)` take a
`(T, T) -> Integer`. Its signed three-way result is negative when the
first element comes earlier, zero when equal, and positive when later:

```minyar
let values = [3, 1, 2]
values.sortBy(function(a: Integer, b: Integer): Integer { return a - b })
```

The callback sees the original slot order throughout comparison. Changes to
separate captured state and element record fields are allowed. If the List's
length or slots differ from their original snapshot after comparison, the
program stops with `the List was mutated during its sort comparator.` before
publishing any sorted slots. Callback side effects are retained. A transient
mutation restored exactly before that check is not reported. Rebinding a
variable or field holding the receiver or comparator keeps the selected
objects alive for the sort.

All four methods use O(n log n) comparisons and O(n) extra space. Natural
sorting needs at most ceil(n/2) scratch slots; comparator sorting retains n
original slots and uses n indices plus ceil(n/2) scratch indices. A copied
result adds its own List storage. Comparator results should define a
consistent ordering; subtraction can overflow for distant Integer values,
so comparisons returning -1, 0, or 1 are safer for general Integers.

`Bytes` holds packed binary data, such as file contents, compact tables or
vertex data. `Bytes(length)` makes zero-filled Bytes and `Bytes()` makes empty
ones. Like a List, Bytes is a shared reference value:

```minyar
let pixels = Bytes(4)
pixels[0] = 255          // each position holds an Integer from 0 to 255
pixels.add(128)          // append one byte
pixels.addFloat32(1.5)   // append a 32-bit Float
print(pixels.length)     // 9
print(pixels.getFloat32(5))
```

Multi-byte values use little-endian order at any byte offset. For each of
`Int16`, `UInt16`, `Int32`, `UInt32`, `Int64`, `Float32` and `Float64` there is
an `addKind(value)` that appends, a `getKind(offset)` and a
`setKind(offset, value)`. Integer values outside the kind's range stop the
program; `Float32` rounds to the nearest 32-bit Float. `addBytes(other)`
appends other Bytes, `slice(start, end)` copies a range, `resize(length)`
truncates or zero-extends, and `clear()` empties the Bytes while keeping its
storage. Clearing and shrinking take constant time; growing initializes only the
newly exposed range, plus any allocation/copy needed for capacity growth.
Discarded storage is not a secure erase; it remains private and is initialized
before a later resize or native extension exposes it. `io.readBytesFile(path)` and `io.writeBytesFile(path, bytes)` transfer files
unchanged. `for byte in bytes` visits each byte as an Integer.

Byte indexing, indexed replacement and `.length` use checked inline helpers,
including when the runtime is linked as a separate native object. Invalid
positions and byte values keep the runtime's bounds and range errors. Aliases
and C-layout views retain their shared storage semantics; a mutating call can
change the length or storage before the access completes.

`Bytes(text)` is a Text's UTF-8 encoding. `Text(bytes)` validates and copies
UTF-8 immediately; invalid UTF-8 stops at that conversion. Use
`text.decode(bytes)` for untrusted input that needs recoverable failure:

```minyar
let wire = Bytes("héllo")   // 6 bytes
print(Text(wire).length)     // 5
```

Import `use "random" as random`; `random.bytes(count)` returns Bytes from the platform's cryptographically secure
generator: `arc4random_buf` on macOS and the BSDs, `getrandom` on Linux,
`BCryptGenRandom` on Windows and the processor's `RDRAND` instruction in
freestanding programs.

For reproducible system tests, import `simulation`. Its explicit I/O boundary
provides seeded completion ordering, virtual time, disk and network faults,
durable file/name models and replayable decisions. It performs no host I/O.
See [deterministic simulation](simulation.md) for its contracts and costs.

Import `pages` for fixed-size byte images, bounded named regions and typed
little-endian fields. Invalid ranges return Results, and copied input/output
buffers keep page bounds stable across aliases. See [checked pages](pages.md)
for the runtime checks and allocation costs.

Import `completionio` for bounded Linux io_uring file reads, writes and syncs.
Its typed queue reports submission and completion failures separately, copies
buffers and retains file descriptors until completion. Queues require explicit
draining and closing. See [completion I/O](completion-io.md) for platform
support, ownership and durability requirements.

## Memory lifetime

Text, List, and record values are reclaimed automatically. Acyclic components
use reference counting; cycle-capable record and List components use traced
allocation selected by the compiler and launcher. No extra build option or
memory-management syntax is required. Expression temporaries are released
between statements; locals retain their values until reassignment or scope exit.
Returning a local can transfer its existing ownership to the caller. This
does not copy the value or change what other aliases observe.
Aliases keep shared values alive.

A local record with only scalar fields can stay in registers or stack storage
when its fields are the only way it is used. This includes direct field updates.

When returning `words + suffix` or `values.appended(item)`, the compiler can
transfer a local's ownership after evaluating the other operand. The runtime
reuses storage when that value has no other owner; shared values keep the
copying behavior. Parentheses do not change this rule.
The same applies when replacing the local itself, such as
`values = (values).appended(values[0])`: the index is read before storage reuse.

Reconstructing a scalar record into its local can also reuse uniquely owned
storage. Every field initializer runs before any old field is replaced, so
`point = Point { x: point.y; y: point.x }` still swaps the two values. Other
aliases keep observing the previous record.

Recursive records support construction, sharing and mutation:

```minyar
record Node { value: Integer; children: List<Node> }
let leaf = Node { value: 1; children: [] }
let root = Node { value: 2; children: [leaf, leaf] }
print(root.children[0].value) // 1
root.children.add(root)      // a cycle; the runtime can reclaim it
```

The compiler follows reference fields, List elements and callback captures to
identify components whose mutation could create cycles. Those components have
additional tracing metadata and collection work; unrelated acyclic components
retain ordinary reference counting. All aliases still observe mutation.

`list.appended(value)` is an alternative when a separate List is wanted. It
preserves the original List's contents and shares references to its elements:

```minyar
let children: List<Node> = []
children = children.appended(leaf)
let root = Node { value: 2; children: children }
```

Copying an aliased List is linear in its length; repeated copying can be
quadratic. The compiler can reuse storage in eligible consuming assignments.
Use `.add` when shared mutation is intended and List literals when all elements
are already known.

Cycle support is not universal: Map mutations that could form reference cycles
are still rejected. Integer identifiers remain useful for explicit graph models;
see the [graph example](../examples/graph.min). The [recursive tree
example](../examples/recursive-tree.min) demonstrates recursive construction
and traversal. The [runtime memory contract](runtime-memory.md) explains
traced components, ownership and execution domains.

Freeing a large graph can take time proportional to its size. See
[runtime profiles](bounded-runtime-contract.md) for incremental cleanup and
finite-heap options.

## Records

A record groups related values under one named, compiler-checked shape:

```minyar
record Person {
    name: Text
    age: Integer
}

let ada = Person {
    name: "Ada"
    age: 36
}

print(ada.name)
```

Every field is required exactly once and must have its declared type. Fields
may be provided in any order, and commas are optional. Records may contain
other records and lists, and records may be list elements:

```minyar
let people: List<Person> = []
people.add(ada)
print(people[0].name)
```

A record is a reference value, like a List. Assigning a field changes the one
shared record, so every alias observes it:

```minyar
let player = Person { name: "Ada"; age: 36 }
let same = player
same.age += 1
print(player.age) // 37
```

Assignments can reach through fields and List positions, as in
`world.chunks[0].blocks[5] = 1`. Scalar fields can always be assigned. Reference
field mutation that can create a record/List cycle activates traced allocation;
Map-related cycles remain restricted. See the
[runtime memory contract](runtime-memory.md).
The receiver, index and assigned value are evaluated once, in that order.

`Equatable`, `Ordered` and `Hashable` name capabilities of a type. Integer,
Text, Character, Boolean and Float have these capabilities. A record derives
them when every field has them and its shape is finite. Lists, Bytes, callbacks,
native-layout records and recursive record shapes have no derived capability.
Unsupported operations report the missing capability at compile time.

Record `==` compares fields by meaning, including private fields and nested
records; `!=` is its opposite. Separately allocated records can be equal.
Aliasing and mutation retain their reference semantics. Equality does not test
reference identity, and has no identity shortcut: a record containing NaN is
unequal even to itself. Derived equality cannot recurse through a cycle.
Map and Set fields are Equatable when their collection equality is defined.
These mutable collection fields do not make a record Ordered or Hashable.

Record order is lexicographic in field declaration order. `list.sort()` and
`list.sorted()` accept Ordered records, as do `<`, `>`, `<=` and `>=`.
Primitive field order follows natural List sorting, including NaNs last and
signed zeros equal. Sorting is stable; a sorted copy still shares its records.
Choices derive these capabilities when all their payload types qualify. Equality
compares the case and its active payloads; order follows case declaration order,
then payload declaration order. Hashing and key snapshots also visit only the
active payloads. Choices can declare instance methods in their own module.
Derived comparisons examine the finite field shape without allocation or
dynamic dispatch. Natural record sorting uses the comparator sorting workspace
described above.

A field marked `private` can be read, assigned and initialized only by code in
the module that declares the record. Other modules can still name the record
type, pass it around and use its other fields, but they cannot create one with
a record literal; they get one from the declaring module's functions instead:

```minyar
public record Account {
    owner: Text
    private balance: Integer
}

public function open(owner: Text): Account {
    return Account { owner: owner; balance: 0 }
}

public function balance(account: Account): Integer {
    return account.balance
}
```

Elsewhere, `account.owner` works but `account.balance` and
`Account { ... }` are compile errors. A field may itself be named `private`.

A method names its record before the function name. Inside it, `self` is the
receiver, with the same shared mutation semantics as any record argument:

```minyar
function Account.deposit(amount: Integer) {
    self.balance += amount
}

account.deposit(10)
```

Methods belong to the module that declares their record. Mark a method
`public` to call it from another module; otherwise it is private to its module.
The receiver and arguments are evaluated once, from left to right, and the
receiver stays alive throughout the call. Methods compile to direct function
calls with an implicit first argument, without dynamic dispatch or vtables.
`value.name` reads a field; `value.name(...)` calls a declared method when
one has that name. Otherwise it calls the field's callable value. A method and
a field may share a name, which lets a public method check access to a private
stored value without exposing the field itself.

Construction uses record literals or ordinary named functions, such as
`bank.open("Ada")`. A dotted declaration always takes a receiver; there is no
separate type-level method form. This keeps construction explicit and gives
factory functions the same module visibility rules as other functions.
## Choices and matching

Declare choices at module scope. The word `choice` remains an ordinary name
elsewhere, including fields, parameters and loop bindings.

A choice describes the different forms one value can take. Cases start with a
capital letter and may carry named, typed payloads:

```minyar
choice Shape {
    Circle(radius: Float)
    Rectangle(width: Float, height: Float)
    Empty
}

let shape = Shape.Circle(2.0)
match shape {
    Circle(radius) { print(3.14159 * radius * radius) }
    Rectangle(width, height) { print(width * height) }
    Empty { print(0.0) }
}
```

A constructor may omit its choice name when the case is unambiguous, or when
an annotation, parameter or return type supplies the choice. Payload-free cases
are written `Empty` or `Shape.Empty`; empty parentheses are also accepted.
Use `public choice` to export a choice and its cases. In another module,
`geometry.Shape.Circle(2.0)` constructs an exported case.

A match evaluates its input once and tries its arms in order. It must cover
every possible value, or end with `else { ... }` to handle the rest. A missing-case
diagnostic shows an example value that still needs handling. Payload names in
an arm are local bindings; `_` ignores a value. Arms may return, break or continue
just like other blocks. An `_` in a diagnostic example stands for any value of
that payload type.

Patterns can nest choice and Result cases, and match Integer, Float, Boolean,
Character and Text literals. A binding or `_` matches any value of its expected
type. Case names resolve from the value being matched, including nested payloads.
Add `where` and a Boolean expression to accept a pattern only when its guard is
true:

```minyar
function describe(value: Maybe<Maybe<Integer>>): Text {
    return match value {
        Some(Some(0)) { "nothing yet" }
        Some(Some(number)) where number > 0 { "a little light" }
        Some(Some(_)) { "below the horizon" }
        Some(None) { "an empty lantern" }
        None { "no lantern" }
    }
}
```

A guard runs only after its pattern matches. It can use the arm's bindings;
if it returns false, matching continues with the next arm. Guarded arms do not
prove coverage, even when the guard is `true`. Without an `else` or wildcard,
Boolean patterns must cover both `true` and `false`; numeric and text literals
need a binding or wildcard for the remaining values. Scalar values can also be
matched directly: `match count { 0 { "none" } _ { "some" } }`.

An Integer range pattern includes its first bound and excludes its end, like a
`for` range. `1..9` matches 1 through 8. Both bounds are Integer literals; a
range must increase. Ranges can appear inside any other pattern:

```minyar
match first([7]) {
    Some(1..9) { print("a single digit") }
    Some(number) { print(number) }
    None { print("nothing yet") }
}
```

Overlapping ranges keep arm order. Exhaustiveness checks account for their
unions and for relationships between nested fields. A range ending at the
maximum Integer still excludes that value; add its literal or a fallback when
needed. Text patterns use exact content, including zero bytes; composed and
decomposed Unicode spellings remain distinct, as with ordinary `==`.

Nested bindings have the same ownership as ordinary arm bindings. They remain
alive if a guard or arm replaces the original input, and can be returned or
captured by a closure. Names are scoped to one arm and cannot repeat within its
pattern. `where` remains an ordinary identifier outside the guard position.

For one case, write `if value is Pattern` or `while value is Pattern`:

```minyar
if shape is Circle(radius) {
    print(3.14159 * radius * radius)
}

while letters.next() is Some(letter) {
    print(letter)
}
```

Each check evaluates its input once. A loop checks again before every iteration.
Bindings belong to the successful body; an `else` branch cannot use them.
They keep their values alive if the body replaces the original input. `is`
remains an ordinary name elsewhere, including `if is { ... }` for a Boolean
binding named `is`.

Record patterns list fields in declaration order. Use a `let` pattern when it
must always succeed:

```minyar
record Pair { first: Integer; second: Text }
let pair = Pair { first: 42; second: "days" }
let Pair(number, unit) = pair
print(number)
print(unit)
```

Patterns can nest records, choices and literals. A `let` evaluates its right
side before introducing its names. It rejects patterns that can fail, such as
`let Some(value) = optional`, and shows an example value they miss. Use `if ... is`
or `match` for those cases. A single-case choice can be destructured with `let`
when its payload patterns also cover every value. Private record fields keep
their ordinary access rules; `_` can ignore them. Native C-layout records do
not yet support record patterns.

A match can also produce a value. Each arm then contains one expression, and
all arms must have the same type. This works for choices and `Result`:

```minyar
let area = match shape {
    Circle(radius) { 3.14159 * radius * radius }
    Rectangle(width, height) { width * height }
    Empty { 0.0 }
}
```

`Maybe<T>` carries either `Some(value)` or `None`. A payload can supply `T`,
as in `Some("moon")`; an annotation, parameter or return type can supply it
for `None`. Explicit constructors such as `Some<Text>("moon")`, `None<Text>()`
and `Maybe<Text>.None` also work:

```minyar
function first(words: List<Text>): Maybe<Text> {
    if words.length == 0 { return None }
    return Some(words[0])
}
let greeting = match first(["hello"]) {
    Some(word) { word }
    None { "silence" }
}
print(greeting)
```

Choices can have type parameters. Construction infers them from payloads or
context, or accepts explicit types:

```minyar
choice Tree<Item> {
    Leaf(value: Item)
    Branch(children: List<Tree<Item>>)
    Empty
}
let tree: Tree<Text> = Branch([Leaf("moon"), Empty])
let number = Tree<Integer>.Leaf(42)
```

Each concrete choice type is compiled separately, using the same
monomorphisation as generic functions. `Maybe` is an ordinary generic choice
declared in `library/maybe.min`; its source declaration is available without an
import. Local declarations retain their names, including a local case named
`Some` or a function named `Some`. Qualify a constructor or provide its expected
type when case names overlap.

The library also exposes choices through existing APIs. For example,
`peerwire.parseStatus(frame)` returns `peerwire.StatusResult`, with
`AcceptedStatus(text)` and `RejectedStatus(error)` cases. Existing `statusOk`,
`statusValue` and `statusError` helpers remain available; matching lets a caller
handle both outcomes directly.

A choice whose cases all have no payloads stores its case as one eight-byte
integer. Constructing, passing, returning and matching these values allocate
nothing and need no reference counting. They remain distinct named types:
an Integer or a different choice cannot stand in for one. Methods, generic
constraints and derived equality, ordering and hashing work as usual. Lists,
records, callbacks, Maps and Sets store these cases directly as scalar values.

A two-case choice with exactly one Boolean, Character or payload-free choice
payload also stores one eight-byte integer, without a wrapper or reference
counting. This includes `Maybe<Boolean>`, `Maybe<Character>` and `Maybe<Signal>`
when every Signal case has no payload. Case order is preserved. With the payload
case first, present values keep their scalar code and the empty case uses the
next code; with the empty case first, empty uses zero and present codes increase
by one. Boolean codes are false = 0 and true = 1. Character codes are Unicode
scalar values, retaining the existing rejection of surrogates and out-of-range
values. Enum payload codes retain declaration order.

Native parameters and results for these choices use i64, including callback
signatures and C-layout fields. A native producer of `Maybe<Boolean>` must
return an encoded i64 (Some(false) = 0, Some(true) = 1, None = 2), rather than
a managed wrapper pointer; a pointer to such a value points to i64 storage.
Native producers must maintain the encoded domain and the existing Character
validity contract. Nested wrappers such as `Maybe<Maybe<Boolean>>` retain a
tagged outer wrapper, so `Some(None)` remains distinct from `None`.
Integer and Float payloads retain tagged storage.

Tagged choices share record ownership and automatic memory management.
A value stores a tag and a union large enough for its largest case: different
cases share the same payload slots. Only the active case's reference payloads
are retained and traced. A payload occupies one eight-byte slot, with reference
tracking stored separately. Payloads can hold choices, records, Lists and
callbacks, with the same ownership and cycle analysis as records. Cases and
payload fields are accessed through constructors and matching. Patterns inspect only the active case and its payloads.

A two-case choice with one Text, Bytes, List, Set or ordinary record payload uses
a nullable pointer.
For example, `Maybe<Reading>` stores the `Reading` pointer for `Some(reading)`
and null for `None`, with no wrapper allocation. The record keeps its usual
shared ownership. `Maybe<Text>` likewise stores Text directly; even an empty
Text has a non-null header, so `Some("")` remains distinct from `None`.
Text equality, ordering and hashing use contents, and key snapshots retain
the immutable Text. This also applies to a user-declared choice with the same
shape, preserving its case order. Nested payload-bearing choices, callbacks
and C-layout payloads keep the tagged union, so values such as `Some(None)` remain distinct from
`None`. Native functions returning an ordinary managed record must return a
valid, non-null record. Native functions returning an eligible choice return
the nullable payload pointer, rather than a tagged wrapper; a present Text
must have a valid, non-null Text header. `Maybe<Bytes>` stores its Bytes header
the same way: `Some(Bytes())` is present even when its backing buffer is empty.
Unwrapping shares the mutable Bytes value, including retained C-layout views.
This representation does not add equality, ordering, hashing or Map-key/Set
support for Bytes. Native functions returning such a choice must return the
Bytes header or null, rather than an old choice wrapper or an interior address.
`Maybe<List<Item>>` likewise stores the List header or null, including for an
empty List. Unwrapping keeps the same mutable List and its element ownership.
Reference-element Lists retain their usual cycle tracing; even a choice/List
cycle that becomes a physical List self-edge is collected as a List. Lists
gain no implicit equality, ordering, hashing or Map-key/Set support. Native
functions returning these choices must return the List header or null.
`Maybe<Set<Item>>` stores the Set header or null too, so `Some(Set<Item>())`
remains distinct from `None`. Unwrapping shares the same mutable Set. Equality
compares present Sets by their contents; these choices have no implicit ordering
or hashing and cannot be Map keys or Set elements. Native producers must return
one owned Set header for a present value or null for an absent one.

## Maps and Sets

`Map<Key, Value>` accepts Hashable record keys as well as scalar keys. A
lookup uses structural equality. Insertion stores a snapshot of a record key;
changing the original record afterwards leaves the stored key intact. Iteration
also returns snapshots, so changing an iterated record cannot change a Map key.
Snapshotting copies record fields recursively and shares immutable Text. It
costs time and space proportional to the record fields copied; internal record
sharing is not preserved. Scalar keys keep their existing storage and are not copied.
Float keys, including Float fields in record keys, reject NaN and treat signed
zeros as the same key.

`Set<Item>` holds distinct Hashable values:

```minyar
let names: Set<Text> = Set()
names.add("Ada")
names.add("Ada")
print(names.length)          // 1
print(names.contains("Ada")) // true
for name in names { print(name) }
print(names.remove("Ada"))   // true; false when absent
names.clear()
```

`add` returns Nothing. A Set is a shared reference value; aliases observe
additions and removals. `==` and `!=` compare membership. Iteration visits a
snapshot in unspecified order, and record elements use the same snapshot rules
as Map keys. Set storage is a hash table; expected lookup, addition and removal
take constant time apart from hashing, comparing and copying an element.
Float elements and Float fields follow the same NaN and signed-zero rules as
Map keys.

## Generic functions and records

A function can name the types it works with, using angle brackets after its
name. The same type parameter always means the same concrete type in one call:

```minyar
function firstOr<Item>(values: List<Item>, fallback: Item): Item {
    if values.length == 0 { return fallback }
    return values[0]
}

print(firstOr([20, 22], 0))     // 20
print(firstOr([], "quiet"))    // quiet
print(firstOr<Integer>([], 7)) // 7
```

Arguments normally supply the type parameters. An annotated result can also
supply them, as in `let values: List<Text> = empty()` for a generic function
returning `List<Item>`. When neither gives enough information, write the types
explicitly. Inconsistent arguments are rejected; generics never convert one
type into another.

The expected result type applies to the call's value. In
`let count: Integer = identity(record).count`, the argument determines the
record type; the Integer annotation describes the field. Method calls,
indexing and calls through returned callbacks follow the same rule.

Generic functions can call one another or themselves and can be exported from
modules. The compiler creates one ordinary function for each distinct set of
concrete types used anywhere in the program. Values keep their usual native
representation and ownership rules, with no boxing or runtime type dispatch.
An unused generic body produces no executable code. The compiler checks a body
with its concrete types when it is used. Builds using generics currently compile
the whole reachable module graph, including in incremental mode.

A record can also name its field types:

```minyar
record Pair<First, Second> {
    first: First
    second: Second
}

let tide = Pair { first: "dawn"; second: 1.2 }
let readings: List<Pair<Text, Float>> = [tide]
print(readings[0].first) // dawn
```

A literal infers its type arguments from its fields and any surrounding type.
Explicit construction, such as `Pair<Text, Float> { first: "noon"; second: 2.7 }`,
works too. Fields, nested records and Lists keep their concrete types. A repeated
type parameter requires matching field types.

A literal used as the receiver of a field access infers its own record type
from its fields. The surrounding expected type describes the selected field.

Each instantiation has ordinary record reference semantics. Its concrete field
types determine ownership and cycle analysis. When mutation can create a cycle,
that instantiation uses traced allocation. Type parameters belong to their
own declaration, even when a module has a record with the same name.

A type alias gives an existing concrete type a familiar name:

```minyar
type Tide = Pair<Text, Float>
type TideTable = List<Tide>

let readings: TideTable = [Tide { first: "dawn"; second: 1.2 }]
```

Aliases are transparent: `Tide` and `Pair<Text, Float>` are the same type, with
the same fields, ownership and layout. They can name primitive, record, collection,
callable and Result types, refer to later aliases, and be exported with `public`.
A recursive chain is rejected. An alias is a type name; construction uses the
usual record literal or the original type's functions. Type parameters still
belong to their own declaration and can shadow an alias.

A method declared through a concrete record alias belongs to its underlying
record, and must be declared in that record's module. Equivalent aliases share
methods; they cannot declare the same method twice. Generic C-layout records
retain fixed-width fields and fixed Bytes arrays, and their concrete layouts
work with `sizeOf`, `alignOf`, `offsetOf`, `cView` and `cAt`.

A capability constraint describes which concrete types a parameter accepts:

```minyar
function largest<Item: Ordered>(values: List<Item>, fallback: Item): Item {
    if values.length == 0 { return fallback }
    let ordered = values.sorted()
    return ordered[ordered.length - 1]
}

print(largest([1.2, 2.7, 1.4], 0.0)) // 2.7
```

A capability describes the methods a type promises to provide:

```minyar
capability Named {
    function name(): Text
    function greeting(): Text { return "Hello, " + self.name() }
}

record Visitor { name: Text }
function Visitor.name(): Text { return self.name }
conform Visitor to Named

function greet<Guest: Named>(guest: Guest): Text {
    return guest.greeting()
}
print(greet(Visitor { name: "Ada" })) // Hello, Ada
```

A conformance belongs to the module that declares the record. It checks every
method's parameter and result types, even when no generic function uses it.
A matching method overrides its default; a missing method uses its default or
reports an error. Method parameter names may differ. `Self` in an annotation
means the conforming record, including inside a collection or callable type.
Aliases retain their underlying record's conformance. A concrete generic record
can conform through an alias or a type such as `Box<Integer>`.

User-defined capability names share the type namespace. Export one with `public capability`
and refer to an imported one with its module alias, such as `labels.Named`.
Implement an imported capability's required methods with `public function` so
its defaults can call them. Defaults retain access to helpers in their original
module. `capability`, `conform` and `to` remain ordinary identifiers elsewhere.
This first form supports concrete record conformances and ordinary method
signatures; capability inheritance and generic capability methods are not supported.

A type opts into a user-defined capability explicitly; matching method names
alone do not establish conformance. The compiler specializes defaults as ordinary
record methods and generic functions as ordinary concrete functions. There is no
boxing, witness table or runtime method dispatch.

The three built-in capabilities use ordinary declarations in
`compiler/builtin-capabilities.min`:

| Capability | Required methods | Default |
| --- | --- | --- |
| `Equatable` | `equal(other: Self): Boolean` | none |
| `Ordered` | `compare(other: Self): Integer` | `equal` tests whether `compare` returns zero |
| `Hashable` | `equal(other: Self): Boolean`, `hash(): Integer` | none |

A record can opt into them with the same `conform` declaration. `==` and `!=`
use its `equal` method; ordering and natural sorting use the sign of `compare`.
`Ordered` and `Hashable` also satisfy `Equatable`. Custom operations compose
through nested records, choices, generic bounds and record collection keys.
An explicit record method overrides the default equality supplied by `Ordered`.

Equal keys must return equal hashes and keep their meaning while stored. After
a custom equality or order is declared, the compiler requires an explicit
`Hashable` conformance instead of deriving an incompatible field-wise hash.
Custom equality also requires an explicit `Ordered` conformance for ordering.
Map and Set record keys still need a finite snapshot shape: Lists, Bytes,
callbacks, native records and recursive fields cannot be copied as keys, even
when the record supplies custom hashing. A generic Hashable bound by itself
does not require a key snapshot.

Record collection keys use the existing hash/equality callback path. The runtime
checks mutation during those callbacks; changing the same Map from its hash or
equality method stops with a clear error. Sorting stages its permutation before
committing it. Cooperative call-depth failure stops custom comparisons and
lookups before committing collection changes. Capability calls themselves
remain direct calls with concrete arguments and no runtime trait representation.

The built-in names keep their capability meaning in an unqualified bound.
Existing ordinary record and alias names such as `Ordered` continue to work in
type annotations, constructors and explicit type arguments.

`Iterable` and `Iterator` are also built-in, structural capability names; a
user capability cannot reuse any built-in name.

Implicit scalar and structural conformances remain available.
Integer, Float, Text, Character and Boolean satisfy the three comparison
capabilities. Finite records
whose fields support a capability inherit it. Maps and Sets support Equatable
where their ordinary equality is defined, including as record fields; they do not
derive Ordered or Hashable. Comparison of Lists, Bytes, callbacks, recursive
record shapes and native record layouts needs an explicit operation. A record
can constrain its type parameters in the same way as a function. The compiler
checks each concrete argument before emitting its instantiation; constraints
add no runtime dispatch.

`Iterable` accepts the built-in collections, lazy recipes and records with the
iteration method shape described above. `Iterator` accepts a record cursor with
`advance(): Boolean` and a value-returning `current()`. Their concrete cursor and
item types are inferred; no conformance declaration or runtime dispatch is needed.
For example, `function total<Source: Iterable>(source: Source): Integer` can sum
the Integer items of a List, a lazy range or a user sequence with one body.

The errors library also shares one value/error record across its checked APIs.
`errors.ValueResult<Item>` stores a value with an `errors.Error`. Create one with
`errors.success(value)` or `errors.failure(fallback, error)`, and use `errors.ok`,
`errors.value` and `errors.error` to inspect it. Reading a failed value stops the
program; the fallback fills its storage and is not a recovery value.

`errors.IntegerResult` and `errors.BooleanResult` are transparent aliases for
`ValueResult<Integer>` and `ValueResult<Boolean>`. Their established factories,
accessors and failure messages remain available. They keep the same two-field
native layout. `BytesResult` retains its separate EOF, truncation and would-block
statuses.

## Recoverable failures

`Result<T, E>` contains either a successful `T` or an error `E`. `Ok(value)`
and `Err(error)` infer their types from an annotated binding, field,
function parameter or return type:

```minyar
function firstByte(packet: Bytes): Result<Integer, Text> {
    if packet.length == 0 { return Err("empty packet") }
    return Ok(packet[0])
}

function increment(packet: Bytes): Result<Integer, Text> {
    return Ok(try firstByte(packet) + 1)
}

match increment(Bytes("A")) {
    Ok(value) { print(value) }
    Err(error) { print(error) }
}
```

`try expression` unwraps success and immediately returns an error from the
enclosing Result-returning function, whose error type must match exactly.
It works inside expressions, arguments, assignments and returns, and may
stand alone for a no-value operation. Propagation preserves evaluation order
and releases the current function's owned locals and temporaries. Programmer
failures such as bounds errors remain fatal.

Add context with `try operation() else "reading the configuration"`. The
context is evaluated only when the operation fails, then passed to the error's
public `withContext(Text)` method, which must return the same error type.
An `errors.Error` provides this method. The original error and its aliases
stay unchanged, including its code, native code and `message()`. `contexts()`
returns a fresh List from the outermost operation to the innermost;
`describe()` prints those layers followed by the original message, indented
two spaces at each layer. Adding context copies its stored context Text;
its cost grows with the total context length. Plain `try` adds no context.

```minyar
function port(source: Text): Result<Integer, errors.Error> {
    return Ok(try readPort(source) else "reading the port")
}
```

Both the operation and context use unary-expression precedence. Parenthesize
a compound context, such as `else ("reading " + path)`. The surrounding
expression continues to use the successful value. Ordinary `if ... else`
and existing identifiers keep their meaning.

Use `Result<Nothing, E>` for an operation with no success payload. Construct
success with `Ok()` and match it with `Ok() { ... }`. `Nothing` cannot be
stored or bound as a payload, or used as an error type. A match must handle
both variants exactly once. An unannotated standalone constructor still
needs explicit arguments, for example `Ok<Integer, Text>(42)`.

Generic Result is the public error-handling model. The `results` package
adapts existing low-level networking status records while retaining EOF,
would-block and truncated-prefix information. Concrete `errors` status
records remain compatibility and native-ABI interfaces.

Result and Maybe have methods for the small decisions around a match:

```minyar
let count: Result<Integer, Text> = Ok(21)
print(count.map(function(value) { return Text(value * 2) }).unwrapOr("unknown"))
let name: Maybe<Text> = None
print(name.unwrapOr("traveller"))
```

`isOk()` and `isErr()` inspect a Result; `isSome()` and `isNone()` inspect a
Maybe. `unwrapOr(fallback)` returns the successful value or the already
evaluated fallback. `unwrapOrElse(callback)` computes a fallback only on
failure, passing a Result's error; its Maybe callback takes no arguments.
`map(callback)` changes a success value, `mapError(callback)` changes a
Result error, and `andThen(callback)` chains an operation returning the same
container. A chained Result preserves the error type. `orElse(callback)`
recovers on failure; a Result passes its error and may change the error type,
while a Maybe calls its no-argument callback. Success skips these recovery
callbacks. `Maybe.filter(predicate)` keeps a value only when the predicate
holds; `okOr(error)` and `okOrElse(callback)` turn absence into a Result error.
The same methods work when Maybe is explicitly imported as `maybe.Maybe<T>`;
maps and recovery preserve that choice type's module identity.

Callbacks infer parameter and return types from the value and their bodies.
They are evaluated once as ordinary arguments and called only for their
matching case. Receiver and argument lifetimes follow ordinary function calls.
The compiler specializes small Minyar match functions for these methods;
there is no dynamic dispatch. Mapping constructs a new Result or Maybe, with
the storage cost described above. Inspecting or unwrapping does not
allocate a new container. Captured callbacks may allocate their environment.

`unwrap()` returns success and stops on failure; `expect(message)` uses the
supplied failure message. Prefer a match or fallback for recoverable input.
For `Result<Nothing, E>`, `map` and `andThen` take a no-argument success
callback. Mapping to Nothing calls the callback and returns `Ok()`;
`unwrapOrElse` takes an `(E) -> Nothing`. Maybe payloads must be values.

The standard library offers typed operations alongside deprecated compatibility
names. An empty success remains a success; failures carry an `errors.Error`.

| Module | Typed operations | Compatibility APIs |
| --- | --- | --- |
| `text` | `integer`, `integerBytes` return Result; `find`, `characterAt`, `slice` return Maybe | `parseInteger`, `parseIntegerBytes`, and Text's original methods |
| `io` | `readText`, `readBytes`, bounded `readTextWithin`/`readBytesWithin`, `writeText`, `writeBytes`, `writeParts`, `flush` | `readTextFile`, `readBytesFile`, `writeTextFile`, `writeBytesFile`, `writeTextParts`, `sync` |
| `files` | `openFile`, `closeFile`, `readBytes`, `readBytesAt`, `writeBytes`, `writeBytesAt`, `entries`, `fileSize`, `sizeOfPath`, `resize`, `reserve`, `move`, `deleteFile`, `createDirectory`, `deleteDirectory`, `flush`, `flushData`, `flushDirectory` | Original native Integer/Bytes/lastError functions |
| `process` | `argumentAt` returns Maybe; `sleep` returns Result | `argument`, `sleepNanoseconds` |
| `json` | `decode`, `decodeBytes`, unique/budgeted decoding, `Value.get`, `findMember`, `element`, `asText`, `asBoolean`, `asInteger`, `asNumber`, `asArray` | `parse`, `lookup`, `require*`, `member`, `string` and their methods |
| `http` | `fetch`, `fetchBounded`, `fetchWithin`, `postText`, `send` return `Result<Reply, errors.Error>`; `Reply.text`, `Reply.json` decode the body | `get`, `getBounded`, `getBoundedWithin`, `post`, `request`, `Response` |
| `net` | `openConnection`, `beginConnection`, `finishConnection`, `listenOn`, `acceptConnection`, `openDatagram`, `portOf`, `waitReady`, `closeConnection`, `readBytes`, `writeBytes`, `receivePackets`; `addressFamily` returns Maybe | Original native handles, sentinel counts and status records |
| `workers` | `start`, `startSelf`, `currentMode`, `readRequest`, `replyMessage`; `Worker.send`, `receive`, `close` | `spawn`, `spawnSelf`, `mode`, `readMessage`, `reply`, `send`, `receive`, `close` |
| `tls` | `open`, `openWithTrust`, `openWithIdentity`, `openWithProtocol`, `openQUIC`; `Session.receive`, `send`, `read`, `finishInput`, `close`, `failure`, `cipherSuites` | Original factories, state-machine functions and Session fields |

File and process errors preserve a positive native error code. File reads and
directory listings capture the native status before another operation can
replace it. `io` keeps the status in a private native snapshot, without a shared
last-error channel. An empty file yields `Ok` with empty contents. Bounded reads
accept a nonnegative byte limit; exceeding it returns an error, including when
an oversized file begins with a readable prefix. Invalid UTF-8 is an error for
Text and remains available through Bytes. `writeParts` streams its pieces
without joining them. Failed writes may have changed the file; use `files`
and its explicit sync/rename operations when durability is required.
The read limit counts content bytes; the Bytes buffer may have spare geometric
capacity. A typed Text read holds its Bytes while validation and conversion
create the Text copy. Typed operations also allocate their Result and native
snapshot records. The compatibility functions keep their original allocation
paths. Importing these generic module declarations currently selects the
whole-graph compilation fallback described above, including for compatibility
calls; caching individual generic module bodies remains future work.

`files` also exposes `startSyncer`, `syncerSocket`, `requestSync`, `syncedOffset`,
`drainSyncer`, `waitForSync`, `switchSyncer`, `stopSyncer` and the corresponding
`startPreparation`, `preparationSocket`, `preparationDone`, `drainPreparation`,
`waitForPreparation`, `stopPreparation` operations as Results. Their native
handle lifetime, completion-socket borrowing and durability contracts stay
the same. A preparation still in progress is `Ok(false)`.

JSON getters never coerce types. `findMember` returns `Result<Maybe<Value>,
errors.Error>`: a non-object is an error, an absent member is `Ok(None)`, and
an explicit JSON null is `Ok(Some(value))` with `value.kind == json.NULL`.
`get` reports missing members, and `element` reports invalid array positions.
`asInteger` parses the original signed decimal integer spelling exactly;
fractional and exponent spellings use `asNumber`, which checks the finite
Float range. Ordinary typed decoding uses the first duplicate member;
`decodeUnique` and its bounded Bytes forms reject duplicates and retain their
documented metadata budgets. The old APIs keep their previous sentinel,
coercion and Unicode-replacement behavior.

An HTTP Reply is complete: status 404 is an `Ok` reply, while transport,
protocol, timeout and body-limit failures are `Err`. The portable and native
macOS modules expose the same typed API. `Reply.text()` validates UTF-8;
`Reply.json()` decodes with a 128 MiB byte limit. These conveniences retain
the existing whole-response buffering and request limits. Reply shares its
headers and Bytes with the underlying response; decoding may allocate a Text
copy or a JSON tree. The compatibility Response keeps its five-field native
layout, including status zero and error text on failure.

`net.readBytes` returns `Ok(Some(bytes))` for stream data and `Ok(None)` for
EOF. Would-block is an error with `errors.wouldBlockCode()`. A datagram uses
`receiveDatagramBytes`: an empty datagram is `Ok(Bytes())`. A truncated read
returns a `ReadFailure`, whose `error()` and `prefix()` preserve both the
diagnostic and readable bytes. `receivePackets` and `DatagramOffload.receive`
use `BatchFailure` to retain packets received before an error. Both failure
types support `withContext` and `describe`, including contextual `try`.
`Datagram.data()` checks each packet's status. The offload handle also has
typed `port`, `ready`, `watch`, `sendTo` and `close` methods.

Socket adapters preserve handle ownership, partial write counts and the
native API's serialization requirements. Handle/status operations capture
the legacy last-error channel immediately; concurrent calls sharing that
channel still require the same external coordination. `waitReady` returns
`Ok(false)` on a timeout. `readBytesInto` appends to the supplied buffer and
requires a positive limit. The original operations retain their contracts.

Worker messages distinguish `Some(Bytes())` from EOF `None`; a timeout is a
would-block error. `currentMode` returns None outside a worker, and
`readRequest`/`replyMessage` return an error there. TLS methods operate on the
existing caller-driven state machine and never open sockets. `Session.read`
drains authenticated plaintext before reporting a later sticky failure;
closed input yields None, and pending input is a would-block error. Managed
Result/Maybe wrappers allocate containers and share their reference payloads.
The runnable `examples/gallery/replies.min` reads a weather station's reply
without a network dependency.

## Callbacks

`(ArgumentTypes...) -> ReturnType` describes a callable value; `() -> T`
has no parameters. An anonymous function supplies its implementation.
Context supplies omitted parameter and return types:

```minyar
record Handler { apply: (Integer) -> Integer }
let offset = 2
let handler = Handler {
    apply: function(value) { return value + offset }
}
print(handler.apply(40)) // 42
let callbacks = [handler.apply]
print(callbacks[0](10))  // 12
```

Without a contextual callable type, anonymous parameters need annotations and
an omitted return type means `Nothing`. The earlier
`Callback<ArgumentTypes..., ReturnType>` spelling remains accepted for source
compatibility and compiler bootstrapping.

Callback-valued fields, List elements, constants and returned expressions can
be called directly. The callee is evaluated once before its arguments and kept
alive throughout the call, even if argument evaluation replaces its original
field or List slot.

Scalar captures are snapshots; reference captures retain shared objects.
Captured bindings cannot be rebound, including with compound assignment such
as `+=`. To maintain captured state, mutate a field of a captured record.
Callbacks belong to their creator's execution domain; they do not transfer
managed objects between threads.

## Structured tasks

`tasks.together(timeoutMs, body)` owns a scope of one-shot worker processes.
The ordinary callback starts typed tasks with `tasks.start` and reads replies
with `tasks.response`. Returning waits for unobserved replies; errors,
cancellation and deadlines close and reap every child before the scope returns.
The callback may return a typed value, delivered after all children finish;
Lists, records and Bytes keep their ordinary ownership outside the scope.
Task and Scope aliases cannot be used after the callback ends. Managed values
stay on their creating domain, and workers receive copied messages in separate
heaps. There is no function colouring or shared managed mutation.

`tasks.channel` pairs request and reply codecs, with built-in codecs for Bytes,
Text and Integer. The event loop services all outstanding workers while waiting
for a reply. Each worker uses `tasks.serve` to handle one request and send a
terminal Result. A terminal reply ends task work; process exit status is not a
separate result. Deadlines are cooperative at task operations and after user
callbacks. This first slice supports macOS and Linux; task workers cannot create
descendant task scopes. See [Tasks that come home together](tasks.md) for the
complete contract, costs and a runnable example.

## Parallel ranges

`parallel for` gives each iteration its own slot in an existing `Bytes` or a
List of Integers, Floats, Booleans or Characters:

```minyar
let squares = [0, 0, 0, 0]
parallel for index in 0..squares.length {
    squares[index] = index * index
}
```

Bounds are evaluated once. Empty and descending ranges do no work. The index
cannot be changed, and every shared write must use that index directly. Scalar
locals belong to one iteration; outer scalar bindings cannot be reassigned.
An output buffer may be read at the same index or through `.length`. Other
scalar buffers may be read at any checked index. When an input could alias an
output, the compiler inserts a check before dispatch; an alias stops with a
clear error asking for a separate input buffer. Empty ranges do no work and
need no alias check.
Bytes views from C-layout records are checked by backing range, including
pairs of outputs. Views starting at the same byte may share direct-index
access; shifted overlapping views need separate storage or a copy. Disjoint
views of one owner can still run together.
Buffers keep their existing length, bounds checks and shared reference semantics.
Managed values cannot be created, passed to functions, resized or returned by an
iteration. Calls must be to pure `parallel function`s, including their callees;
raw machine operations and native effects are rejected. `continue` skips one
iteration; `break` is allowed only inside a nested ordinary loop.

On macOS and Linux, a persistent thread pool distributes fixed chunks of 128
indices. Idle workers steal chunks from other workers; the calling thread also
works, and returns only after every worker has finished. Set
`MINYAR_PARALLEL_THREADS` to 1–64 to choose the total number of participating
threads; the default is the online processor count, capped at 64. Freestanding
OS builds use the processor-entry scheduler after the processors are started.
Other targets and recoverable execution use the sequential backend. Each loop can
capture at most 64 values. Scalar captures are snapshots; the caller keeps buffer
owners alive, and worker code performs no ownership operations.
Parallel builds currently check the whole module graph,
including when module caching is requested. The [parallel gallery](../examples/gallery/parallel.min)
draws a Julia garden into separate slots, with a woven Unicode preview or a PNG.

Add `reduce name` to sum into one mutable Integer or Float binding:

```minyar
let total = 0
parallel for index in 0..values.length reduce total {
    total += values[index]
}
```

Each chunk starts a private accumulator at zero. The body may update it with
`+=`, but cannot otherwise read it or reassign it. Contributions may be
conditional, and ordinary disjoint output writes can accompany them. After
the workers finish, partial sums are combined in chunk order with the original
binding. Integer additions remain checked. Float grouping is fixed at 128
iterations per chunk, independent of the number of threads; it can differ from
a sequential left-to-right sum. An empty range preserves the original value.
Partial storage costs one word per chunk and uses the configured allocator.
Reductions are not yet available in recoverable execution.

`pixels.blendBytes` and `pixels.maskBytes` work on owned BGR0 byte buffers:
blue, green, red and an unused zero byte for each pixel. Both use checked
parallel slots. Mask bytes are immutable during the job and need separate
storage. `pixels.coverageBytes` accepts a List of signed Float areas; its
running sum stays sequential because each value depends on its predecessor.
The address-based pixel routines remain available for device memory.

## Parallel functions

A `parallel function` may run on several processors at once. The runtime's
ownership tracking is single-threaded, so a parallel function stays outside it:
its parameters, locals and results are `Integer`, `Float`, `Boolean` or
`Character`, and it calls only other parallel functions, `machine` intrinsics
and scalar functions declared `parallel`, including those in `math`. The compiler checks this and
compiles the function with no call-depth or ownership frame.

```minyar
use "machine" as machine

parallel function square(index: Integer, results: Integer) {
    machine.store64(results + index * 8, index * index)
}

let results = Bytes(64)
let entry = parallelEntry(square)
for index in 0..8 {
    machine.callEntry(entry, index, machine.address(results))
}
```

`parallelEntry(name)` is the address of a parallel function, which a scheduler
can start on other processors; `machine.callEntry(entry, first, second)` calls a
parallel function taking two Integers through that address, and
`machine.atomicAdd` coordinates processors through shared memory. Ordinary
functions can call parallel functions directly. Minyar OS uses them to spread
per-pixel work over every processor; see freestanding programs.

## Hardware register fields

Use a native register layout when bit positions are known at compile time:

```minyar
record Control native "register32" {
    enabled: Integer at(1, 1)
    threshold: Integer at(4, 8)
    distance: Integer at(12, 10)
}
let control = encodeField(Control, "enabled", 1) |
    encodeField(Control, "threshold", 15)
print(extractField(Control, "threshold", control)) // 15
let changed = replaceField(Control, "distance", control, 64)
print(fieldFits(Control, "distance", 1024)) // false
```

The native tags `register8`, `register16`, `register32` and `register64`
select the word width. Each Integer field declares its first bit and width
with contextual `at(first, width)`. Coordinates are compile-time Integer
constants; fields must fit the word and cannot overlap. Private fields follow
ordinary module visibility. A layout is a declaration operand for these four
operations; it cannot be constructed, stored or passed as a runtime value.
Its name must be distinct from runtime records, module constants and globals.
Field names must be literal text. The operations emit scalar shifts and masks
directly, including at O0, without allocating a descriptor or a field-name string.

`encodeField` produces a zero-filled payload; `extractField` reads a field
from an Integer; `replaceField` preserves every other bit. Narrow words and
field values must fit their unsigned widths. A full-width 64-bit field accepts
every Integer bit pattern. Invalid literal or scalar-constant operands reject
at compile time; other invalid values stop through the ordinary Integer range
failure. `fieldFits` returns false for an invalid field value. These are pure
operations: use explicit volatile device reads/writes and required barriers.

The `device` module gives memory-mapped registers distinct widths. A
`Field8`, `Field16`, `Field32` or `Field64` describes a field within a register
of that width. Its first argument is the least-significant bit; the second
is the number of bits. Both the field range and its values are checked:

```minyar
use "device" as device
let distance = device.field32(12, 10)
let control = device.encode32(distance, 64)
print(device.extract32(distance, control)) // 64
let changed = device.replace32(distance, control, 96)
```

`encode32` creates the field's bits with all other bits zero. `extract32`
reads a field from an Integer; `replace32` preserves the other bits. The
same operations exist for 8, 16 and 64 bits. Words narrower than 64 bits
must be nonnegative and fit their width. A full-width `Field64` accepts every
Integer bit pattern, including negative values. A field cannot be built by a
record literal or passed to a register operation of a different width.

`device.readField32(register, field)` performs one volatile read.
`device.updateField32(register, field, value)` checks the value, reads once
and writes once. It is a non-atomic read-modify-write for ordinary read/write
registers. For write-only or write-one-to-clear registers, use
`device.write32(register, device.encode32(field, value))`; this performs no
read. These operations add no hardware memory barrier. Use `machine.fence()`
where the device and architecture require one.

A field descriptor is an ordinary managed record, allocated when constructed;
keep it for repeated access. Its operations use Integer masks and shifts with
range checks and the usual record ownership cost. They add no dynamic dispatch.
Native `record ... native "c_packed"` layouts can describe DMA storage; the
e1000 driver uses `sizeOf` and `offsetOf` on its 16-byte descriptors, so strides
and offsets come from the declared layout. Those queries are compile-time values;
they do not create a record. Packed layouts describe storage and do not make
ordinary record field accesses into volatile MMIO operations.
See [kernel development](os-development.md) for hosted driver tests, bounded
QEMU tests, GDB and symbolized panic addresses.

## Interrupt contexts and DMA ownership

A contextual handler declaration binds a scalar function to one interrupt vector:

```minyar
interrupt function clockTick(vector: Integer) handles(32) {
    signalInterrupt(0)
}
```

Compile this context with `--freestanding --kernel-target x86_64` or `arm64`.
PIC vectors 32..47 and GIC IDs 16..1019 are accepted respectively. A handler
takes one Integer and returns Nothing. Its complete direct call graph must use
scalar, acyclic code: allocation, managed values, Float, blocking, locks,
native calls, indirect calls, recursion and loops reject. Ordinary functions
keep their ordinary behavior. This context proof is separate from hardware
entry, register preservation and a physical stack bound.

`signalInterrupt(slot)` stores a coalescing flag; ordinary code consumes it with
`takeInterrupt(slot)`. Slots are literal or module-constant Integers in 0..255.
These operations use release/acquire ordering. A flag carries no event count,
payload access or DMA completion permission. Existing user callables with these
names retain normal lookup precedence.

The `dma` module separates CPU access from a device-owned pending request:

```minyar
use "dma" as dma
use "dma_model" as model

let queue = model.modelQueue()
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 7)
let pending = dma.submit(queue, cpu, 16)
let delivered = model.modelDeliver(queue, Bytes("hello"))
let completed = dma.reclaim(pending, 0)
print(dma.load8(completed, 0)) // 104
dma.dispose(completed)
```

Moving a Cpu or Pending binding makes its previous binding unavailable.
`load8`, `store8` and `copyOut` borrow Cpu; `ready` borrows Pending.
`submit`, `reclaim`, `dispose` and `retire` consume their capability. Ordinary
helpers consume affine arguments; only compiler-owned native primitives have
the borrowing rules above. `copyOut` returns independent Bytes. A reclaimed Cpu
exposes only the completed prefix, including zero bytes for an empty completion.

The first flow subset supports straight-line code, if/else, concrete direct
helpers and normal returns. Continuing branches must agree on ownership; every
normal exit must transfer, dispose or retire each live capability. Cpu/Pending
cannot escape through records, containers, choices, Results, callbacks or globals.
Queue aliases may be passed directly, but Queue also cannot enter these aggregate
or captured forms. Opaque handles have no automatic record equality or hashing.
Loops, match and recoverable control flow with these capabilities reject.
Use this registry from one serialized boot CPU, outside interrupt context.

These opaque handles allocate ordinary managed records. A separately rooted
runtime registry owns backing storage and checks capability epochs. Readiness
validates the actual private queue completion before reclaim can return Cpu;
a caller's Boolean or interrupt flag cannot authorize it. Bounded reclaim stops
on timeout and quarantines storage. Retirement also pins storage; it does not
cancel DMA or provide safe reset. The deterministic model tests this protocol.
Hardware adapters additionally require coherent identity mappings and an actual
retained queue owner. Raw native/machine escapes, IOMMU isolation, noncoherent
cache maintenance and safe device reset are outside this guarantee.

## Programs and entry points

Executable statements may be written directly at the top level. They run from
top to bottom, while records and functions are declarations and may appear
anywhere in the file:

```minyar
function double(value: Integer): Integer {
    return value * 2
}

let answer = double(21)

if answer == 42 {
    print("Everything is working")
} else {
    print("Something went wrong")
}
```

Module declarations are indexed before function bodies are checked. A function
can name a record or call another function declared later in the file. Module
constants and globals are also visible throughout their module. Local bindings
still become visible where they are declared.

The compiler retains resolved types and source spans for checked declarations,
statements and expressions. See the [compiler syntax tree](compiler-syntax.md).

Compiler diagnostics identify the source file, line and column. Source-read failures, including invalid UTF-8, use the same text or JSON format. Common syntax,
type and field errors also show the source line and underline the relevant
token. Columns count Unicode scalar values, starting at one. Type mismatches
show the expected and actual types where those are known:

```text
error: the value for 'stars' does not match its declared type; expected Integer, found Text
  --> sky.min:1:5
   |
 1 | let stars: Integer = "many"
   |     ^^^^^
   = help: change this value to the expected type, or change the declaration if it should accept the found type
   = explain: minyar explain E0401
```

Each error includes a repair note and an error code. Run `minyar explain E0401`
for a longer explanation with a valid example, or `minyar explain --list` to
browse the error families. Explanations work outside a project and need no
network access. Codes describe the problem rather than the particular name or
type in the message, so they remain useful when the wording changes.

When a spelling is close, the compiler suggests a name available at that point.
This includes values, functions, record fields and methods, types, choice cases
and public module members. Equally close alternatives get no suggestion.
Private names from other modules and bindings outside the current scope are
not candidates.
Missing match arms name the cases that still need handling. The
[lantern](../examples/gallery/weather-lantern.min) gallery combines the corrected names
with choices, methods and interpolation.

The compiler can report several independent errors in one run, up to 20.
It resumes with the next function or top-level statement when the boundary
is clear. A failed binding does not produce further unknown-value messages
from its uses. Fixing the reported errors may expose further errors inside
the same function or a malformed declaration.

Tools can request `--error-format json` from the compiler or standalone
launcher. It emits one versioned JSON object per error, with the same message,
source, range, label and help. See the [diagnostic schema](compiler-syntax.md#json-diagnostics).

Runtime stops keep their message and add a short Minyar stack trace:

```text
Minyar stopped: The harbour has no light.
Minyar stack trace:
  at darkWindow (harbour.min:1:10)
    | function darkWindow(): Integer {
  at evening (harbour.min:4:10)
    | function evening(): Integer {
  at top level (harbour.min:7:1)
    | print(evening())
```

A frame names the function's declaration, or the first top-level statement.
Its source line is saved when the program is compiled, so it remains readable
after the original file is moved or removed. Lines are limited to 160 characters,
with an ellipsis when clipped; tabs expand to spaces and terminal controls are
replaced. A source line is omitted if it was unavailable during compilation.
Optimized code may inline or merge functions and remove tail calls; the trace
shows the frames that remain. A trace has at most twelve Minyar frames.
Stripped images and hosts without readable unwind information retain the
entry location. macOS ARM64 and hosted Linux have full symbol readers; Windows
and freestanding builds currently use the entry fallback. The error-format
option describes compiler diagnostics; it does not change a program's arguments.

Trace names and source locations are static data. There is no call/return
instrumentation, thread-local trace stack or normal-path allocation. Metadata
increases binary size, and unwind tables remain available in optimized builds.
On macOS ARM64 the cold reader adds no loader bindings. Hosted Linux uses the system unwinder and adds a `libgcc_s` dependency, with library-loading work at startup. Whole-process retired
instruction samples vary with startup and allocation; the measured LLVM
function bodies contain zero additional normal-path instructions.

`if` chains may continue with `else if`:

```minyar
if score >= 90 {
    print("A")
} else if score >= 80 {
    print("B")
} else {
    print("C")
}
```

`exit(status)` ends the program with an `Integer` process status; reaching the
end uses zero.
An explicit `function main()` is also supported. It accepts no declared
parameters and has an `Integer` return type; use `process.argument()` from the `process` module to read process
arguments. A file cannot mix this form with executable top-level statements
because that would create two entry points. The executable entry `main` cannot
be called from language code; put shared work in a separate function. An imported
module function named `main` is an ordinary function and remains callable.
Reaching the end of the executable entry `main` returns process status zero;
an explicit `return` can choose another Integer status.

Other functions with a value return type must return a value on every reachable path.
A path ending in `fail(...)`, `exit(...)`, or a literal `while true` loop without
a reachable `break` is also terminal. Literal `true` and `false` conditions
select the reachable branch for return analysis, though unreachable source is
still type-checked. For example, `if true { return 1 }` needs no `else`.
Functions returning
`Nothing` can use a bare `return`. `Nothing` is a return type, not a value that
can be stored in bindings, fields, Lists, or parameters.

Built-in operations validate their argument count and types, just like user
functions. Extra arguments are errors.

User function names occupy a separate linker namespace from the runtime and
system libraries. Names such as `malloc` or `minyar_list_new` are ordinary user
function names; they cannot replace the runtime implementation.

Local modules use an explicit namespace and expose declarations with `public`:

```minyar
use "./geometry.min" as geometry

let point: geometry.Point = geometry.Point { x: 20, y: 22 }
print(geometry.answer(point))
```

Imported modules cannot contain executable top-level statements. Imports are
resolved relative to the importing file, declarations are private unless
marked `public`, and cycles are rejected. See [modules](modules.md).

C headers can supply ordinary modules through the
[C header importer](c-interop.md). Select the functions, fixed-layout structs,
enums and integer constants you need. Clang checks their declarations and
layouts; generated wrappers check narrow integer conversions and use the
existing native calling convention. Pointer ownership needs an explicit C
facade. No additional language syntax is required.

A statement ends at the end of its line, using LF or CRLF. A bare CR is whitespace,
not a line boundary. The end of the source file also ends
the final complete statement, without requiring a trailing newline. A line ends a statement when its last
token could end one: a name, a literal, `)`, `]`, or `}`. A line that ends with
an operator, a comma, or an opening bracket continues onto the next line, so
long expressions can be wrapped after the operator:

```minyar
let total = first +
    second
let joined = add(
    20,
    22,
)
```

Inside parentheses and square brackets, newlines are whitespace. A wrapped
call or List can therefore close on its own line without a trailing comma.
`else` and `else if` may begin on the following line, including after comments.
A semicolon ends a statement early when two statements share a line; it is
never required.

```minyar
let values = [
    20,
    22
]
print(
    values[0] + values[1]
)
if values.length == 0 {
    print("empty")
}
else {
    print("ready")
}
```

<!-- reserved-names: generated by tools/reserved-names.py -->
## Reserved function names

These names belong to the language's built-in functions and constructors.
A user function cannot declare one of them, including inside an imported
module. Choose a different function name, such as `joinTextLocal` or `joinWith`.
Record fields and methods use their receiver's namespace; this list reserves
function declarations, not field names or arbitrary prefixes.

Names are case-sensitive. Standard-library functions belong to their module
alias and do not reserve every module's function namespace.

| Reserved function name |
| --- |
| `Bytes` |
| `Character` |
| `Float` |
| `Integer` |
| `Map` |
| `Set` |
| `Text` |
| `abs` |
| `clamp` |
| `exit` |
| `fail` |
| `joinText` |
| `max` |
| `min` |
| `parallelEntry` |
| `print` |
| `wrappingAdd` |
| `wrappingMultiply` |
| `wrappingSubtract` |

Generated from the compiler by `tools/reserved-names.min`;
`make check-reserved-names` verifies this list.
<!-- reserved-names: end -->

The [error gallery](../examples/gallery/errors.md) places ten real Minyar
errors beside the same mistakes in Rust, Swift and TypeScript. Underlines
account for wide characters, combining marks and common joined emoji; source
coordinates remain Unicode scalars. Terminal fonts may choose different widths.

## Describing native views

The `ui` module describes views with ordinary functions: `column` and `row`
compose headings, labels, keyed buttons, text inputs and checkboxes. The pure
description owns no native UI objects. `ui-macos` displays it through AppKit
and updates text and values while keeping the same native controls. Application
state stays in ordinary Minyar records. See [native desktop applications](desktop.md)
for a complete example, update rules and `minyar app` bundling and signing.

## Formatting source

`minyar fmt` lays out source with four-space blocks and consistent spacing.
Comments and literal spelling stay intact. Use `minyar fmt --check` to check
the style without writing files, or `--stdout FILE.min` to preview one file.
See [Minyar style](style.md) for examples and the preservation checks.

`minyar lsp --stdio` provides live compiler diagnostics, hover documentation,
definitions, references, rename, completion, literal type hints, quick fixes,
symbols and formatting to an editor. See
[editor tooling](editor.md) for setup and the current navigation capabilities.

`minyar run --watch` rebuilds a project after source edits. Add `--hot` to replace
function implementations while the process and its values stay alive. Keep state
in ordinary records, Lists and globals; pass it to the functions you are editing.
The [lanterns gallery](../examples/gallery/lanterns.min) follows this shape.
Changes to types, declarations or initialization require a fresh run. See
[live programming](cli.md#live-programming) for the reload boundary and its
development-time costs.
