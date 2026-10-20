# Minyar for C++ programmers

Minyar compiles typed source to native code through LLVM. This page describes
its ordinary language, with complete programs tested at O0/O2 by
`make check-book`. The [book](book/README.md) teaches the syntax from scratch;
the [language guide](language.md) is the detailed reference.

## Records are shared references

A Minyar record groups named, typed fields. Assignment of a record shares
that record. Passing it to a function shares it too:

```minyar
record Account {
    owner: Text
    balance: Integer
}

function Account.deposit(amount: Integer) {
    self.balance += amount
}

let account = Account { owner: "Ada"; balance: 20 }
let alias = account
alias.deposit(22)
print("\(account.owner): \(account.balance)")
```
```output
Ada: 42
```

Record assignment has shared object semantics rather than memberwise value
copying. A List or Bytes also shares storage on assignment. You do not pair
allocations with `delete`: automatic reference counting manages acyclic
objects, and cycle-capable record/List components use traced allocation.
Map cycles remain restricted. These choices have runtime costs; see
[runtime memory](runtime-memory.md).

Inside a block, `constant` fixes a binding, while `let` allows reassignment.
A constant binding does not make its referenced object's fields immutable.
A derived record `==` compares supported fields by meaning, even for two
separately allocated records.

Methods are declared in the record's module and take implicit `self`.
They use direct calls without vtables. Ordinary Minyar has no class hierarchy
in this model; compose records through fields. Fields marked `private` and
declarations without `public` are restricted to their module.

## Numeric conversions are explicit

`Integer` is signed 64-bit and `Float` is IEEE 754 double precision. Arithmetic
does not implicitly mix them. Integer overflow, invalid shifts, bounds errors
and Integer division by zero produce runtime stops instead of continuing
with an unchecked result. Float arithmetic follows IEEE 754:

```minyar
let whole: Integer = 7
print(whole / 2)
print(Float(whole) / 2.0)
print(Integer(-3.9))
```
```output
3
3.5
-3
```

`Integer(float)` truncates toward zero and rejects NaN or out-of-range values.
Use the explicit wrapping operations for modular Integer arithmetic, or
`errors.checkedAdd` and related functions for recoverable overflow. `Bytes`
offers checked byte and little-endian numeric access; it is not an unchecked
pointer into a record's native layout. See [the language guide](language.md).

## Failures are values when recovery is intended

A Result carries success or error with checked types. A match handles both;
`try` returns a failed Result from the enclosing function, whose error type
must match. It does not catch runtime stops:

```minyar
function divide(total: Integer, parts: Integer): Result<Integer, Text> {
    if parts <= 0 { return Err("The number of parts must be positive.") }
    return Ok(total / parts)
}

for parts in [3, 0] {
    match divide(12, parts) {
        Ok(value) { print(value) }
        Err(message) { print(message) }
    }
}
```
```output
4
The number of parts must be positive.
```

Use `Maybe<T>` for absence without an error explanation. User-defined `choice`
types and exhaustive `match` describe more domain-specific alternatives.

Generic functions and records use angle brackets and monomorphisation. Concrete
instances keep their normal ownership semantics. A generic body is checked
with its concrete types when instantiated; an unused body emits no executable
code. There is no runtime type dispatch from generic specialization itself.

## Choose one entry point

Examples above use executable top-level statements. Alternatively, declare
a parameterless Integer-returning `main`, with no executable top-level
statements. Falling through this entry function returns process status zero:

```minyar
function main(): Integer {
    print("Ready.")
}
```
```output
Ready.
```

Ordinary functions with a value return type must return on every reachable
path; the implicit zero is specific to the executable entry point.

Imports use a module alias, such as `use "io" as io`, with public declarations
accessed through it. No textual header inclusion is needed for Minyar modules.
Start with `minyar new`, then `minyar run`, `minyar test` and
`minyar build --release`; the [CLI guide](cli.md) covers native build setup.
The [module guide](modules.md) covers splitting a project across files.
