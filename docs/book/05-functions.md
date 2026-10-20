# 5. Writing functions

[Previous](04-lists.md) · [Contents](README.md) · [Next](06-records.md)

A function gives a task a name. Its parameters are named inputs; `return`
provides an output to the caller and ends that call.

```minyar
function seedsNeeded(beds: Integer, seedsPerBed: Integer): Integer {
    return beds * seedsPerBed
}

print(seedsNeeded(3, 4))
print(seedsNeeded(5, 2))
```
```output
12
10
```

The parentheses in the declaration describe the inputs and their types.
`: Integer` after the closing parenthesis describes the returned value.
In `seedsNeeded(3, 4)`, arguments fill the parameters in order: `beds` gets
`3`, and `seedsPerBed` gets `4`. Each call has its own local bindings.

A function returning a value must provide one on every reachable path.
A function that only performs actions, such as printing, may omit its return
type; that means it returns `Nothing`. Call it to perform its actions instead
of trying to store its nonexistent result.

Passing a List or record shares the same object with the function. Changing
that object inside the function is visible to its caller. Plain numbers are
values: assigning a number parameter again does not change the caller's binding.

Try it: add a call for seven beds with three seeds per bed. It should print `21`.

## Keep a check beside the task

A test records something that should always be true. It helps you find a
mistake after changing a function:

```minyar
function seedsNeeded(beds: Integer, seedsPerBed: Integer): Integer {
    return beds * seedsPerBed
}

test "three beds need twelve seeds" {
    expect(seedsNeeded(3, 4) == 12)
}

test "no beds need no seeds" {
    expect(seedsNeeded(0, 4) == 0)
}

print("The plan needs \(seedsNeeded(3, 4)) seeds.")
```
```output
The plan needs 12 seeds.
```

Save this in `src/main.min`. `minyar run` prints the plan; `minyar test` runs
the named tests. Test blocks are excluded from ordinary builds. `expect`
checks a Boolean, and a false expectation reports the expression and its
location. Test names explain the intended behavior.

Try it: change the multiplication to addition. Run the tests and read which
expectations fail. Restore the multiplication afterwards. A passing test
checks its particular examples; it does not prove every possible input works.
