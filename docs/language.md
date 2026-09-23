# The Minyar language

## Bindings and scope

`let` introduces a local value. A name exists from its declaration to the end
of its lexical block. Assignment changes its value without changing its type.

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
as `0xFF` are also Integers.

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

Math functions take Floats: `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`,
`atan`, `atan2(y, x)`, `exp`, `log`, `pow(base, exponent)`, `floor`, `ceil`
and `round` (halves round away from zero). `abs`, `min`, `max` and
`clamp(value, low, high)` accept Integers or Floats of one type.

Integers also support bitwise `&`, `|`, `^`, `~` and the shifts `<<` and `>>`
(arithmetic). A shift count outside 0 to 63 stops the program. For hashing and
random number generators, `wrappingAdd`, `wrappingSubtract` and
`wrappingMultiply` wrap around instead of stopping on overflow.

Operators bind in this order, tightest first: `*`, `/`, `%`, `<<`, `>>`, `&`;
then `+`, `-`, `|`, `^`; then `<`, `>`, `<=`, `>=`; then `==`, `!=`; then `&&`
and finally `||`. So `value & 1 == 0` tests the lowest bit.

There is one equality operator: `==`. It never converts either side. Both sides
must have the same type, and values compare by meaning—`Text` compares its
contents. `!=` is its direct opposite. Ordered comparisons accept `Integer`,
`Float` or `Character` operands. Arithmetic accepts `Integer` or `Float`
operands; `+` also joins two `Text` values. These operators never coerce
Boolean values into numbers. A NaN Float is unequal to everything, itself
included.

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

Use `argumentCount()` and `argument(position)` for command-line arguments,
and `readTextFile(path)` and `writeTextFile(path, contents)` for text files.

`joinText(parts)` joins a `List<Text>` into one Text value.

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

A List is a reference value: aliases observe the same additions and indexed
replacements, including those performed by functions. Mutations that could
create an ownership cycle are rejected, as described below. Reading or writing
outside a List's bounds stops with a clear error.

## Memory lifetime

Text, List, and record values are reclaimed automatically through reference
counting. Expression temporaries are released between statements; locals retain
their values until reassignment or scope exit. Aliases keep shared values alive.

Recursive records and acyclic recursive values are supported. Their structural
Lists are built with literals rather than later mutation:

```minyar
record Node { value: Integer; children: List<Node> }
let leaf = Node { value: 1; children: [] }
let root = Node { value: 2; children: [leaf, leaf] }
print(root.children[0].value) // 1
```

For a mutation of `List<T>`, the compiler rejects `.add` and indexed replacement
if `T` can lead back to that same `List<T>` type through fields or nested Lists.
This prevents cycles even through aliases and helper functions. In the example,
mutating any `List<Node>` is rejected, including an append that would happen to
be safe. `list.appended(value)` returns a fresh List with the additional value,
so recursive children can be accumulated safely by reassigning a local:

```minyar
let children: List<Node> = []
children = children.appended(leaf)
let root = Node { value: 2; children: children }
```

The operation copies the existing elements and is therefore linear in the List
length; repeated use is quadratic. List literals remain preferable when all
children are already known. Constructing a new List and reassigning a local
cannot introduce the first cycle because that new List did not exist while its
elements were evaluated.
Unrelated mutable Lists, such as an Integer payload or an external worklist of
wrappers that Node cannot reach, retain their usual shared behaviour.

Arbitrary cyclic graphs require another representation, such as Integer identifiers;
see the [graph example](../examples/graph.min). The [recursive tree
example](../examples/recursive-tree.min) demonstrates recursive construction
and traversal. The [runtime memory contract](runtime-memory.md) explains the
mutation rule and its acyclicity argument.

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
`world.chunks[0].blocks[5] = 1`. Scalar fields can always be assigned. A field
holding a Text, List or record cannot be assigned if its type could lead back
to the record's own type, because that could create a reference cycle; see the
[runtime memory contract](runtime-memory.md). Record equality is not supported.

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

`exit(status)` ends the program with an `Integer` process status; reaching the
end uses zero.
An explicit `function main()` is also supported. It accepts no declared
parameters and has an `Integer` return type; use `argument()` to read process
arguments. A file cannot mix this form with executable top-level statements
because that would create two entry points.

Functions with a value return type must return a value on every reachable path.
A path ending in `fail(...)` or `exit(...)` is also terminal. Functions returning
`Nothing` can use a bare `return`. `Nothing` is a return type, not a value that
can be stored in bindings, fields, Lists, or parameters.

Built-in operations validate their argument count and types, just like user
functions. Extra arguments are errors.

Local modules use an explicit namespace and expose declarations with `public`:

```minyar
use "./geometry.min" as geometry

let point: geometry.Point = geometry.Point { x: 20, y: 22 }
print(geometry.answer(point))
```

Imported modules cannot contain executable top-level statements. Imports are
resolved relative to the importing file, declarations are private unless
marked `public`, and cycles are rejected. See [modules](modules.md).

A statement ends at the end of its line. A line ends a statement when its last
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

The closing `)` of a wrapped call needs a trailing comma before it, and `else`
belongs on the same line as the `}` that precedes it. A semicolon ends a
statement early when two statements share a line; it is never required.
