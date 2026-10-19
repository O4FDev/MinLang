# A light left on

A compiler error is a place to begin again. Minyar gives the name of the file, the place in the line, and the words that need attention. Where a nearby name is unambiguous, it offers that name.

These are ten small mistakes, compiled for real on 19 October 2026. Rust 1.96.0 (`--edition=2024 --emit=metadata`), Swift 6.2.4 (`-typecheck`) and TypeScript 7.0.2 (`--strict --noEmit --pretty false --lib es2020,dom`) are shown beside the current Minyar compiler. TypeScript examples use `export {};` to keep their names local to the file. This is a record of those versions and flags, not a ranking. Paths are shortened to the example filename; messages, positions and suggestions are preserved.

The Minyar examples are rejection fixtures in [`tests/diagnostics/cases`](../../tests/diagnostics/cases). Their complete text and JSON diagnostics run in `make check-diagnostics`. The other sources and captured compiler output live in [`tests/diagnostics/comparisons`](../../tests/diagnostics/comparisons). They do not add three foreign toolchains to the test prerequisites.

## A name one letter away

```minyar
let lantern = 4
print(lantren)
```

```text
error: I can't find a value named 'lantren'
  --> example.min:2:7
   |
 2 | print(lantren)
   |       ^^^^^^^
   = help: did you mean `lantern`?
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0425]: cannot find value \`lantren\` in this scope |
| Swift | error: cannot find 'lantren' in scope |
| TypeScript | error TS2552: Cannot find name 'lantren'. Did you mean 'lantern'? |

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
fn main() { let lantern = 4; println!("{}", lantren); }
```

```text
error[E0425]: cannot find value `lantren` in this scope
 --> example.rs:1:45
  |
1 | fn main() { let lantern = 4; println!("{}", lantren); }
  |                                             ^^^^^^^
  |
help: a local variable with a similar name exists
  |
1 - fn main() { let lantern = 4; println!("{}", lantren); }
1 + fn main() { let lantern = 4; println!("{}", lantern); }
  |

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0425`.
```

**Swift** · exit 1

```swift
let lantern = 4
print(lantren)
```

```text
example.swift:2:7: error: cannot find 'lantren' in scope
1 | let lantern = 4
2 | print(lantren)
  |       `- error: cannot find 'lantren' in scope
3 | 
```

**TypeScript** · exit 1

```typescript
export {};
const lantern = 4;
console.log(lantren);
```

```text
example.ts(3,13): error TS2552: Cannot find name 'lantren'. Did you mean 'lantern'?
```

</details>

## A function name with two letters swapped

```minyar
function portrait(): Integer { return 1 }
print(portriat())
```

```text
error: I can't find a function named 'portriat'
  --> example.min:2:7
   |
 2 | print(portriat())
   |       ^^^^^^^^
   = help: did you mean `portrait`?
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0425]: cannot find function \`portriat\` in this scope |
| Swift | error: cannot find 'portriat' in scope |
| TypeScript | error TS2552: Cannot find name 'portriat'. Did you mean 'portrait'? |

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
fn portrait() -> i64 { 1 }
fn main() { println!("{}", portriat()); }
```

```text
error[E0425]: cannot find function `portriat` in this scope
 --> example.rs:2:28
  |
1 | fn portrait() -> i64 { 1 }
  | -------------------- similarly named function `portrait` defined here
2 | fn main() { println!("{}", portriat()); }
  |                            ^^^^^^^^
  |
help: a function with a similar name exists
  |
2 - fn main() { println!("{}", portriat()); }
2 + fn main() { println!("{}", portrait()); }
  |

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0425`.
```

**Swift** · exit 1

```swift
func portrait() -> Int { 1 }
print(portriat())
```

```text
example.swift:2:7: error: cannot find 'portriat' in scope
1 | func portrait() -> Int { 1 }
2 | print(portriat())
  |       `- error: cannot find 'portriat' in scope
3 | 
```

**TypeScript** · exit 1

```typescript
export {};
function portrait(): number { return 1; }
console.log(portriat());
```

```text
example.ts(3,13): error TS2552: Cannot find name 'portriat'. Did you mean 'portrait'?
```

</details>

## A field name with two letters swapped

```minyar
record Window { light: Boolean }
let window = Window { light: true }
print(window.ligth)
```

```text
error: record 'Window' has no field named 'ligth'
  --> example.min:3:14
   |
 3 | print(window.ligth)
   |              ^^^^^ Window has the fields `light`
   = help: did you mean `light`?
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0609]: no field \`ligth\` on type \`Window\` |
| Swift | error: value of type 'Window' has no member 'ligth' |
| TypeScript | error TS2551: Property 'ligth' does not exist on type '{ light: boolean; }'. Did you mean 'light'? |

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
struct Window { light: bool }
fn main() { let window = Window { light: true }; println!("{}", window.ligth); }
```

```text
error[E0609]: no field `ligth` on type `Window`
 --> example.rs:2:72
  |
2 | fn main() { let window = Window { light: true }; println!("{}", window.ligth); }
  |                                                                        ^^^^^ unknown field
  |
help: a field with a similar name exists
  |
2 - fn main() { let window = Window { light: true }; println!("{}", window.ligth); }
2 + fn main() { let window = Window { light: true }; println!("{}", window.light); }
  |

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0609`.
```

**Swift** · exit 1

```swift
struct Window { let light: Bool }
let window = Window(light: true)
print(window.ligth)
```

```text
example.swift:3:14: error: value of type 'Window' has no member 'ligth'
1 | struct Window { let light: Bool }
2 | let window = Window(light: true)
3 | print(window.ligth)
  |              `- error: value of type 'Window' has no member 'ligth'
4 | 
```

**TypeScript** · exit 1

```typescript
export {};
const window = { light: true };
console.log(window.ligth);
```

```text
example.ts(3,20): error TS2551: Property 'ligth' does not exist on type '{ light: boolean; }'. Did you mean 'light'?
```

</details>

## A number used as a condition

```minyar
if 1 { print("light") }
```

```text
error: an if condition must be Boolean; expected Boolean, found Integer
  --> example.min:1:4
   |
 1 | if 1 { print("light") }
   |    ^
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0308]: mismatched types |
| Swift | error: integer literal value '1' cannot be used as a boolean; did you mean 'true'? |
| TypeScript | Accepted: numeric conditions use JavaScript truthiness. |

TypeScript accepts this program. Its condition follows JavaScript truthiness; the other three examples require a Boolean.

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
fn main() { if 1 { println!("light"); } }
```

```text
error[E0308]: mismatched types
 --> example.rs:1:16
  |
1 | fn main() { if 1 { println!("light"); } }
  |                ^ expected `bool`, found integer

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0308`.
```

**Swift** · exit 1

```swift
if 1 { print("light") }
```

```text
example.swift:1:4: error: integer literal value '1' cannot be used as a boolean; did you mean 'true'?
1 | if 1 { print("light") }
  |    `- error: integer literal value '1' cannot be used as a boolean; did you mean 'true'?
2 | 
```

**TypeScript** · exit 0

```typescript
export {};
if (1) { console.log("light"); }
```

```text
(no diagnostics)
```

</details>

## Text in an integer binding

```minyar
let light: Integer = "warm"
print(light)
```

```text
error: the value for 'light' does not match its declared type; expected Integer, found Text
  --> example.min:1:5
   |
 1 | let light: Integer = "warm"
   |     ^^^^^
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0308]: mismatched types |
| Swift | error: cannot convert value of type 'String' to specified type 'Int' |
| TypeScript | error TS2322: Type 'string' is not assignable to type 'number'. |

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
fn main() { let light: i64 = "warm"; println!("{}", light); }
```

```text
error[E0308]: mismatched types
 --> example.rs:1:30
  |
1 | fn main() { let light: i64 = "warm"; println!("{}", light); }
  |                        ---   ^^^^^^ expected `i64`, found `&str`
  |                        |
  |                        expected due to this

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0308`.
```

**Swift** · exit 1

```swift
let light: Int = "warm"
print(light)
```

```text
example.swift:1:18: error: cannot convert value of type 'String' to specified type 'Int'
1 | let light: Int = "warm"
  |                  `- error: cannot convert value of type 'String' to specified type 'Int'
2 | print(light)
3 | 
```

**TypeScript** · exit 1

```typescript
export {};
const light: number = "warm";
console.log(light);
```

```text
example.ts(2,7): error TS2322: Type 'string' is not assignable to type 'number'.
```

</details>

## Text passed to an integer parameter

```minyar
function lantern(count: Integer) { print(count) }
lantern("three")
```

```text
error: an argument passed to lantern has the wrong type; expected Integer, found Text
  --> example.min:2:9
   |
 2 | lantern("three")
   |         ^^^^^^^
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0308]: mismatched types |
| Swift | error: cannot convert value of type 'String' to expected argument type 'Int' |
| TypeScript | error TS2345: Argument of type 'string' is not assignable to parameter of type 'number'. |

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
fn lantern(count: i64) { println!("{}", count); }
fn main() { lantern("three"); }
```

```text
error[E0308]: mismatched types
 --> example.rs:2:21
  |
2 | fn main() { lantern("three"); }
  |             ------- ^^^^^^^ expected `i64`, found `&str`
  |             |
  |             arguments to this function are incorrect
  |
note: function defined here
 --> example.rs:1:4
  |
1 | fn lantern(count: i64) { println!("{}", count); }
  |    ^^^^^^^ ----------

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0308`.
```

**Swift** · exit 1

```swift
func lantern(_ count: Int) { print(count) }
lantern("three")
```

```text
example.swift:2:9: error: cannot convert value of type 'String' to expected argument type 'Int'
1 | func lantern(_ count: Int) { print(count) }
2 | lantern("three")
  |         `- error: cannot convert value of type 'String' to expected argument type 'Int'
3 | 
```

**TypeScript** · exit 1

```typescript
export {};
function lantern(count: number): void { console.log(count); }
lantern("three");
```

```text
example.ts(3,9): error TS2345: Argument of type 'string' is not assignable to parameter of type 'number'.
```

</details>

## A returned value of the wrong type

```minyar
function warmth(): Integer { return "warm" }
print(warmth())
```

```text
error: a returned value has the wrong type; expected Integer, found Text
  --> example.min:1:37
   |
 1 | function warmth(): Integer { return "warm" }
   |                                     ^^^^^^
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0308]: mismatched types |
| Swift | error: cannot convert return expression of type 'String' to return type 'Int' |
| TypeScript | error TS2322: Type 'string' is not assignable to type 'number'. |

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
fn warmth() -> i64 { "warm" }
fn main() { println!("{}", warmth()); }
```

```text
error[E0308]: mismatched types
 --> example.rs:1:22
  |
1 | fn warmth() -> i64 { "warm" }
  |                ---   ^^^^^^ expected `i64`, found `&str`
  |                |
  |                expected `i64` because of return type

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0308`.
```

**Swift** · exit 1

```swift
func warmth() -> Int { return "warm" }
print(warmth())
```

```text
example.swift:1:31: error: cannot convert return expression of type 'String' to return type 'Int'
1 | func warmth() -> Int { return "warm" }
  |                               `- error: cannot convert return expression of type 'String' to return type 'Int'
2 | print(warmth())
3 | 
```

**TypeScript** · exit 1

```typescript
export {};
function warmth(): number { return "warm"; }
console.log(warmth());
```

```text
example.ts(2,29): error TS2322: Type 'string' is not assignable to type 'number'.
```

</details>

## A match with a missing case

```minyar
choice Weather { Clear; Rain }
function warmth(weather: Weather): Integer {
    match weather { Clear { return 1 } }
}
print(warmth(Weather.Clear))
```

```text
error: match is missing cases: Rain
  --> example.min:3:5
   |
 3 |     match weather { Clear { return 1 } }
   |     ^^^^^
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0004]: non-exhaustive patterns: \`Weather::Rain\` not covered |
| Swift | error: switch must be exhaustive |
| TypeScript | error TS2366: Function lacks ending return statement and return type does not include 'undefined'. |

TypeScript reports the missing return path. Minyar, Rust and Swift name the uncovered case.

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
enum Weather { Clear, Rain }
fn warmth(weather: Weather) -> i64 { match weather { Weather::Clear => 1 } }
fn main() { println!("{}", warmth(Weather::Clear)); }
```

```text
error[E0004]: non-exhaustive patterns: `Weather::Rain` not covered
 --> example.rs:2:44
  |
2 | fn warmth(weather: Weather) -> i64 { match weather { Weather::Clear => 1 } }
  |                                            ^^^^^^^ pattern `Weather::Rain` not covered
  |
note: `Weather` defined here
 --> example.rs:1:6
  |
1 | enum Weather { Clear, Rain }
  |      ^^^^^^^          ---- not covered
  = note: the matched value is of type `Weather`
help: ensure that all possible cases are being handled by adding a match arm with a wildcard pattern or an explicit pattern as shown
  |
2 | fn warmth(weather: Weather) -> i64 { match weather { Weather::Clear => 1, Weather::Rain => todo!() } }
  |                                                                         ++++++++++++++++++++++++++

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0004`.
```

**Swift** · exit 1

```swift
enum Weather { case clear, rain }
func warmth(_ weather: Weather) -> Int {
    switch weather { case .clear: return 1 }
}
print(warmth(.clear))
```

```text
example.swift:3:5: error: switch must be exhaustive
1 | enum Weather { case clear, rain }
2 | func warmth(_ weather: Weather) -> Int {
3 |     switch weather { case .clear: return 1 }
  |     |- error: switch must be exhaustive
  |     `- note: add missing case: '.rain'
4 | }
5 | print(warmth(.clear))
```

**TypeScript** · exit 1

```typescript
export {};
type Weather = "Clear" | "Rain";
function warmth(weather: Weather): number {
    switch (weather) { case "Clear": return 1; }
}
console.log(warmth("Clear"));
```

```text
example.ts(3,36): error TS2366: Function lacks ending return statement and return type does not include 'undefined'.
```

</details>

## An unknown type name

```minyar
let light: Integre = 1
print(light)
```

```text
error: unknown type 'Integre'
  --> example.min:1:12
   |
 1 | let light: Integre = 1
   |            ^^^^^^^
   = help: did you mean `Integer`?
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0425]: cannot find type \`Integre\` in this scope |
| Swift | error: cannot find type 'Integre' in scope |
| TypeScript | error TS2304: Cannot find name 'Integre'. |

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
fn main() { let light: Integre = 1; println!("{}", light); }
```

```text
error[E0425]: cannot find type `Integre` in this scope
 --> example.rs:1:24
  |
1 | fn main() { let light: Integre = 1; println!("{}", light); }
  |                        ^^^^^^^ not found in this scope

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0425`.
```

**Swift** · exit 1

```swift
let light: Integre = 1
print(light)
```

```text
example.swift:1:12: error: cannot find type 'Integre' in scope
1 | let light: Integre = 1
  |            `- error: cannot find type 'Integre' in scope
2 | print(light)
3 | 
```

**TypeScript** · exit 1

```typescript
export {};
const light: Integre = 1;
console.log(light);
```

```text
example.ts(2,14): error TS2304: Cannot find name 'Integre'.
```

</details>

## A constant declared twice

```minyar
constant light = 1
constant light = 2
print(light)
```

```text
error: module declares 'light' more than once
  --> example.min:2:10
   |
 2 | constant light = 2
   |          ^^^^^
```

| Compiler | Its first message |
| --- | --- |
| Rust | error[E0428]: the name \`LIGHT\` is defined multiple times |
| Swift | error: invalid redeclaration of 'light' |
| TypeScript | error TS2451: Cannot redeclare block-scoped variable 'light'. |

<details>
<summary>The same source and complete output in the other three languages</summary>

**Rust** · exit 1

```rs
const LIGHT: i64 = 1;
const LIGHT: i64 = 2;
fn main() { println!("{}", LIGHT); }
```

```text
error[E0428]: the name `LIGHT` is defined multiple times
 --> example.rs:2:1
  |
1 | const LIGHT: i64 = 1;
  | --------------------- previous definition of the value `LIGHT` here
2 | const LIGHT: i64 = 2;
  | ^^^^^^^^^^^^^^^^^^^^^ `LIGHT` redefined here
  |
  = note: `LIGHT` must be defined only once in the value namespace of this module

error: aborting due to 1 previous error

For more information about this error, try `rustc --explain E0428`.
```

**Swift** · exit 1

```swift
let light = 1
let light = 2
print(light)
```

```text
example.swift:2:5: error: invalid redeclaration of 'light'
1 | let light = 1
  |     `- note: 'light' previously declared here
2 | let light = 2
  |     `- error: invalid redeclaration of 'light'
3 | print(light)
4 | 
```

**TypeScript** · exit 1

```typescript
export {};
const light = 1;
const light = 2;
console.log(light);
```

```text
example.ts(2,7): error TS2451: Cannot redeclare block-scoped variable 'light'.
example.ts(3,7): error TS2451: Cannot redeclare block-scoped variable 'light'.
```

</details>

## More than one way home

The compiler reports up to twenty independent errors. It resumes at complete function bodies and top-level statement boundaries, and suppresses uses of a binding whose initializer already failed. An unsafe lexical or declaration header error stops that pass. Every reported error has a file, line and column. JSON uses one versioned object per line on stderr; successful compilation is quiet.

Source columns count Unicode scalars. Underlines account for common terminal cells, including wide characters, combining marks and emoji sequences. A terminal's font can still choose a different width. Source-read errors retain the filename and a best-effort location; invalid UTF-8 is replaced at the first invalid byte so the diagnostic itself remains valid text.
