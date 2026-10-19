# The Minyar language

The LLVM compiler and runtime define this language contract. Minyar targets
share its types, reference semantics and failure behavior. The separate
`--experimental-swift` and `--experimental-swift-source` dialects explore Swift
interoperability. Their value types and additional syntax are outside this
contract. An alternative compiler must pass the same language conformance
tests before it can become a Minyar backend.

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

At module scope, `constant` declares a literal value that every function in the module
can use. It is a declaration, like a function or record, and `public` exports
it from a module:

```minyar
constant CHUNK_SIZE = 16
constant GRAVITY: Float = -9.81
constant TITLE = "Minyarcraft"
```

A literal value may omit its type annotation: an Integer, Float, Text,
Character or Boolean, optionally negated. A module constant cannot execute
initialization code. Use an explicit immutable `global` binding for runtime
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

## Memory lifetime

Text, List, and record values are reclaimed automatically. Acyclic components
use reference counting; cycle-capable record and List components use traced
allocation selected by the compiler and launcher. No extra build option or
memory-management syntax is required. Expression temporaries are released
between statements; locals retain their values until reassignment or scope exit.
Aliases keep shared values alive.

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

A match evaluates its input once. It must cover every case exactly once, or end
with `else { ... }` to handle the remaining cases. A missing-case diagnostic
names the cases still needed. Payload names in an arm are local bindings; `_`
ignores a payload. Arms may return, break or continue just like other blocks.

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

Choices currently share the record representation and automatic memory
management. Each value allocates a tag and slots for all declared payloads;
inactive slots are empty. This includes choices with no payloads. Payloads can
hold choices, records, Lists and callbacks, with the same ownership and cycle
analysis as records. Cases and payload fields are accessed through constructors
and matching. Nested or literal patterns are not yet supported.

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

`Equatable`, `Ordered` and `Hashable` are the supported capability names.
Integer, Float, Text, Character and Boolean satisfy all three. Finite records
whose fields support a capability inherit it. Lists, Bytes, callbacks, recursive
record shapes and native record layouts need an explicit operation. A record
can constrain its type parameters in the same way as a function. The compiler
checks each concrete argument before emitting its instantiation; constraints
add no runtime dispatch.

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

Use `Result<Nothing, E>` for an operation with no success payload. Construct
success with `Ok()` and match it with `Ok() { ... }`. `Nothing` cannot be
stored or bound as a payload, or used as an error type. A match must handle
both variants exactly once. An unannotated standalone constructor still
needs explicit arguments, for example `Ok<Integer, Text>(42)`.

Generic Result is the public error-handling model. The `results` package
adapts existing low-level networking status records while retaining EOF,
would-block and truncated-prefix information. Concrete `errors` status
records remain compatibility and native-ABI interfaces.

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

Functions with a value return type must return a value on every reachable path.
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
