# Minyar for Swift programmers

This page covers ordinary Minyar, compiled through its LLVM compiler.
The explicitly selected experimental Swift dialects use a separate compiler
path and language contract. In particular, their Swift value semantics do
not describe ordinary Minyar records or Lists. See the [language guide](language.md).
Every program below is independently checked by `make check-book`.

## Familiar spelling, different binding rules

Minyar's `let` allows reassignment. Inside a block, `constant` prevents it.
Records, Lists and Bytes are shared references, including through a constant
binding. They do not acquire value semantics from their declaration syntax:

```minyar
record Note { title: Text }

function demonstrate() {
    constant note = Note { title: "First draft" }
    let alias = note
    alias.title = "Ready"
    let copies = 1
    copies += 1
    print(note.title)
    print(copies)
}

demonstrate()
```
```output
Ready
2
```

Construct an independent record explicitly when you need one. Copying a List
with `.sorted()` or `.appended(value)` creates separate List storage but
still shares referenced elements. `.sort()` and `.add(value)` mutate the
existing List, visible through aliases. Automatic memory management uses
reference counting for acyclic objects and tracing for cycle-capable record/List
components; Map cycles remain restricted. See [runtime memory](runtime-memory.md).

## Functions and choices

Write `function`, use `: Type` after the parameter list for a return type,
and pass arguments positionally. Methods use `function Type.method(...)`
in the declaring module, with implicit `self`. A choice uses capitalized cases
and `match`, rather than assuming Swift's enum or switch syntax:

```minyar
choice Weather {
    Sunny
    Rainy(minutes: Integer)
}

function describe(weather: Weather): Text {
    return match weather {
        Sunny { "Bring a hat." }
        Rainy(minutes) { "Rain for \(minutes) minutes." }
    }
}

print(describe(Weather.Sunny))
print(describe(Weather.Rainy(20)))
```
```output
Bring a hat.
Rain for 20 minutes.
```

Each match must cover the cases or end with an `else` arm. A match expression
has one expression of the same result type in each arm. `Maybe<T>` has `Some`
and `None`; there is no implicit optional unwrapping in these examples.

## Result propagation and text

`Result<T, E>` uses `Ok` and `Err`. Inside a Result-returning function, `try`
extracts success or returns the error immediately. It is not a `throws` marker
and does not catch runtime stops. The error types must match:

```minyar
function checkedName(name: Text): Result<Text, Text> {
    if name.length == 0 { return Err("Please enter a name.") }
    return Ok(name)
}

function greeting(name: Text): Result<Text, Text> {
    let checked = try checkedName(name)
    return Ok("Hello, \(checked)!")
}

for name in ["Ada", ""] {
    match greeting(name) {
        Ok(message) { print(message) }
        Err(message) { print(message) }
    }
}
```
```output
Hello, Ada!
Please enter a name.
```

Text interpolation uses `\(...)`. `Text` stores valid UTF-8; the core
`.length`, indexing and slicing described in the [language guide](language.md)
count Unicode scalar values, not user-perceived grapheme clusters. Do not
assume a displayed emoji or accented letter always occupies one such position.
`Character` means a Unicode scalar in ordinary Minyar. `Bytes(text)` gives
its UTF-8 encoding; `text.byteLength` counts bytes.

Executable instructions can appear at the top level, as above, or in a
parameterless Integer-returning `main`. Do not combine both entry forms in
one file. Declarations are private to their module unless `public`, and
imports use `use "./module.min" as module`. Named tests use `test` and
`expect`; [chapter 5](book/05-functions.md) shows them beside a function.

The [project CLI](cli.md) provides `new`, `run`, `check`, `test`, `fmt`, `doc`
and `build --release`. Start with the [book](book/README.md) if you want a
guided project using the ordinary language.
