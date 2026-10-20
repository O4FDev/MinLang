# 4. Working with lists

[Previous](03-decisions.md) · [Contents](README.md) · [Next](05-functions.md)

A List keeps several values in order. Square brackets make a List; commas
separate its elements. A `for` loop visits each element:

```minyar
let packets = [4, 7, 3]
let total = 0
for seeds in packets {
    total += seeds
}
print("Seeds altogether: \(total)")
```
```output
Seeds altogether: 14
```

Each time around, `seeds` names the next element. It exists only inside the
loop's block. `total` was introduced outside that block, so we can update it
inside and read it afterwards.

Try it: add `6` to the List. The total should become `20`.

## Positions start at zero

`List<Text>` means a List whose elements are Text. All elements of a List
have the same type. An empty List needs enough context to know that type:

```minyar
let names: List<Text> = []
names.add("Ada")
names.add("Sam")
print(names.length)
print(names[0])
names[1] = "Jo"
for name in names {
    print(name)
}
```
```output
2
Ada
Ada
Jo
```

`.add(...)` appends an element. `.length` gives the number of elements.
`names[0]` reads the first; `names[1]` reads the second. An empty List has
length zero and no valid position. Reading or writing outside its bounds
stops the program. Use a `for` loop when you just need to visit everything.

## A range of numbers

Sometimes the positions themselves are useful. `0..3` visits `0`, `1` and `2`:
the start is included and the end is excluded.

```minyar
let tasks = ["Sow", "Water", "Rest"]
for position in 0..tasks.length {
    print("\(position + 1). \(tasks[position])")
}
```
```output
1. Sow
2. Water
3. Rest
```

The position used for indexing still starts at zero. Adding one changes only
the number displayed for the reader. Lists are shared objects: assigning one
to another name does not copy its contents. The next chapters show how that
affects functions and records.
