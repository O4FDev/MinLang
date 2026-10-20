# 2. Giving things names

[Previous](01-first-program.md) · [Contents](README.md) · [Next](03-decisions.md)

A value is a piece of information, such as a number or some text. A binding
gives a value a name. `let` introduces a binding you can assign again:

```minyar
let name = "Ada"
let seeds = 12
seeds = seeds - 3
print("Hello, \(name).")
print("Seeds left: \(seeds)")
```
```output
Hello, Ada.
Seeds left: 9
```

`=` stores the value on its right under the name on its left. It does not
ask whether two things are equal. After the third line, `seeds` holds `9`.
Inside text, `\(seeds)` inserts the value of `seeds`. This is interpolation.
The parentheses show where that expression ends.

Try it: start with `20` seeds instead. You should have `17` left.

## Types describe the kind of value

`Integer` means a whole number, `Float` means a number that can have a fractional part,
`Text` means text, and `Boolean` means `true` or `false`. Minyar usually works
out a binding's type from its first value. You can also write it after `:`.
Once a binding has a type, assigning again cannot change its type.

```minyar
let seeds: Integer = 7
let beds: Integer = 2
print(seeds / beds)
print(Float(seeds) / Float(beds))
```
```output
3
3.5
```

Integer division discards the fractional part, toward zero. Convert explicitly
with `Float(...)` when you want fractional arithmetic. Minyar does not mix
Integer and Float automatically. Division by zero with Integers stops the
program, so check a divisor when it comes from outside your program.

To see a type error, change the first line to assign `"seven"` while keeping
`: Integer`. Read the error, then restore `7`. Text and numbers are different
kinds of information even when their spelling looks similar.

## A name that stays put

Inside a function or another block, `constant` introduces a binding that
cannot be assigned again. Braces mark a block of instructions belonging
together. Functions will get a full explanation in [chapter 5](05-functions.md).

```minyar
function showPlan() {
    constant beds = 3
    let seedsPerBed = 4
    seedsPerBed = 5
    print(beds * seedsPerBed)
}

showPlan()
```
```output
15
```

Here the number of beds stays fixed while the plan for each bed changes.
A constant name does not freeze a List or record it refers to; we will meet
those shared objects in [chapter 6](06-records.md). Names introduced inside a
block are available only from their declaration to the end of that block.
