# Minyar for Rust programmers

This page describes ordinary Minyar, the native LLVM language. Start with
the [book](book/README.md) for a slower introduction, or the
[language guide](language.md) for the full contract. Each program below is
independent and its following output is checked by `make check-book`.

## Bindings and shared objects

Minyar's `let` can be reassigned without a `mut` marker. Inside a block,
`constant` prevents rebinding. Neither form freezes a referenced record,
List or Bytes. Assignment and function arguments share those objects:

```minyar
record Counter { value: Integer }

function demonstrate() {
    constant counter = Counter { value: 1 }
    let alias = counter
    alias.value += 1
    let count = 10
    count += 2
    print(counter.value)
    print(count)
}

demonstrate()
```
```output
2
12
```

Do not read record assignment as a move or an independent value copy. There
are no Rust-style borrow annotations in this code. Automatic ownership
management keeps aliases alive. Acyclic objects use reference counting;
cycle-capable record/List components use traced allocation. These mechanisms
have runtime costs; see [runtime memory](runtime-memory.md). Map mutations
that could create reference cycles remain restricted.

`list.sorted()` makes a fresh List with shared element references;
`list.sort()` mutates the existing List. A record's derived `==` compares
its fields when their types support equality, rather than testing identity.

## Choices, Result and propagation

Use `choice` for a sum type, capitalized cases for constructors, and braces
around each match arm. Arms bind their payloads locally. `Result<T, E>` and
`Maybe<T>` are available without imports. `try` propagates a Result error
from a function with the same error type:

```minyar
function positive(value: Integer): Result<Integer, Text> {
    if value <= 0 { return Err("Use a positive number.") }
    return Ok(value)
}

function doubled(value: Integer): Result<Integer, Text> {
    let checked = try positive(value)
    return Ok(checked * 2)
}

for value in [21, 0] {
    match doubled(value) {
        Ok(answer) { print(answer) }
        Err(message) { print(message) }
    }
}
```
```output
42
Use a positive number.
```

`try` does not convert error types implicitly or catch a runtime stop.
Integer overflow and bounds errors stop the program; recoverable operations
return typed Results. A function call is an ordinary call: `try` is needed
when you choose propagation, rather than being mandatory just to obtain a Result.

## Generics compile to concrete functions

Angle brackets introduce type parameters; constraints name capabilities.
The compiler specializes each used set of concrete types. There is no boxing
or dynamic dispatch from a generic call itself:

```minyar
function larger<Item: Ordered>(left: Item, right: Item): Item {
    if left > right { return left }
    return right
}

print(larger(20, 22))
print(larger("ash", "oak"))
```
```output
22
oak
```

Built-in `Equatable`, `Ordered` and `Hashable` capabilities derive for eligible
finite record shapes. The [language guide](language.md#records) gives the
limits; do not assume a mutable collection is Ordered or Hashable. Generic
bodies are checked with their concrete types when used. Specialization does
not remove the ordinary allocation or ownership costs of those types.

Write `function Type.method(...)` in the type's module; `self` is implicit.
Methods are private unless `public` and compile to direct calls. Factories
are ordinary functions or record literals, not a separate static-method form.

Use `use "./module.min" as module` and qualify exported declarations through
the alias. Declarations are private by default. `minyar new`, `run`, `check`,
`test`, `fmt`, `doc` and `build --release` are the usual project entry points;
see the [CLI](cli.md). Named `test` blocks stay beside declarations and use
`expect`, as shown in the [testing chapter](book/05-functions.md).
