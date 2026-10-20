# 6. Keeping related things together

[Previous](05-functions.md) · [Contents](README.md) · [Next](07-results.md)

A record describes related fields under one type name. It lets the compiler
check that a garden bed has a name and a seed count:

```minyar
record Bed {
    name: Text
    seeds: Integer
}

let herbBed = Bed { name: "Herbs"; seeds: 6 }
let sameBed = herbBed
sameBed.seeds += 2
print("\(herbBed.name): \(herbBed.seeds)")
```
```output
Herbs: 8
```

The declaration describes the fields; `Bed { ... }` creates one record.
Every field must be supplied exactly once, with the right type. A dot reads
a field, and assignment changes it.

Notice the output: assigning `herbBed` to `sameBed` gives the same record
another name. It does not make a second bed. Both names observe the change.
Lists work the same way. If you need an independent record, create a new one
and supply its fields; nested Lists or records would still need their own
copying decisions.

Minyar keeps shared records alive automatically while they are needed. You do
not write instructions to free them. Sharing still matters when you decide
which part of your program may change an object.

## Give a record an action

A method is a function called through a value. Put the type name before the
method name in its declaration; inside the method, `self` means that value:

```minyar
record Bed {
    name: Text
    seeds: Integer
}

function Bed.plant(extra: Integer) {
    self.seeds += extra
}

function showBed() {
    constant bed = Bed { name: "Peas"; seeds: 4 }
    bed.plant(3)
    print("\(bed.name): \(bed.seeds)")
}

showBed()
```
```output
Peas: 7
```

`constant bed` keeps the binding fixed. The referenced bed can still change,
which is why `plant` works. Declare methods in the same module as their type.
For now each example is one module: one source file.

Try it: create two separate beds, plant in the first and print both. Only
the first should change. Then assign the first to another name and repeat;
that second name should observe the change too.
