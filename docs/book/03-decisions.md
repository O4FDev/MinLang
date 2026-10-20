# 3. Making decisions

[Previous](02-names.md) · [Contents](README.md) · [Next](04-lists.md)

Programs become useful when the instructions depend on the information.
An `if` chooses a block by checking a condition:

```minyar
let water = 3
if water >= 2 {
    print("We can water the garden.")
} else {
    print("Bring another can of water.")
}
```
```output
We can water the garden.
```

`>=` asks whether the left number is greater than or equal to the right.
The answer is a Boolean. When the answer is true, the first block runs;
otherwise the `else` block runs. Only one of them runs.

Try it: change `water` to `1`. The other message should appear.

Use `==` to ask whether values are equal and `!=` to ask whether they differ.
`<`, `>`, `<=` and `>=` compare sizes. Both sides must have the same type.
`&&` means both conditions must hold, `||` means at least one must hold,
and `!` reverses a Boolean:

```minyar
let raining = false
let cans = 2
let needsWater = !raining && cans > 0
print(needsWater)
print(cans == 2)
print("seed" == "Seed")
```
```output
true
true
false
```

Text equality compares its contents, including letter case. A condition must
be Boolean; a number alone does not stand for true or false.

## Repeat while something holds

`while` checks its condition before each repetition. If it is false at the
first check, the body does not run at all.

```minyar
let cans = 3
while cans > 0 {
    print("Watering with can \(cans)")
    cans -= 1
}
print("Finished.")
```
```output
Watering with can 3
Watering with can 2
Watering with can 1
Finished.
```

`cans -= 1` means the same as `cans = cans - 1`. Updating it matters: if the
condition never becomes false, the program keeps repeating. You can normally
stop a running terminal program with Control-C.

Try it: start with zero cans. The only line printed should be `Finished.`.
