# The Minyar language

## Bindings and scope

`let` introduces a local value. A name exists from its declaration to the end
of its lexical block. Assignment changes its value without changing its type.

```minyar
let attempts = 3
attempts = attempts - 1
```

## Numbers and comparisons

`Integer` ranges from -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807.
Arithmetic overflow and division by zero stop the program with an error.
Integer literals outside this range are rejected.
The minimum value is spelled `-9223372036854775808`.

There is one equality operator: `==`. It never converts either side. Both sides
must have the same type, and values compare by meaning—`Text` compares its
contents. `!=` is its direct opposite. Ordered comparisons accept `Integer` or
`Character` operands. Arithmetic accepts `Integer` operands; `+` also joins two
`Text` values. These operators never coerce Boolean values into numbers.

Conditions accept only `Boolean`.

## Types and built-in operations

The value types are:

- `Integer`: a signed 64-bit whole number.
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

Record fields are immutable after construction. Record equality is not supported.

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
