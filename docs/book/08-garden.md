# 8. A small program of your own

[Previous](07-results.md) · [Contents](README.md)

We have a garden plan: several beds, a seed budget and a question about
whether the plan fits. Here is the whole program. Replace `src/main.min`
with it; nothing from an earlier example needs to remain.

```minyar
record Bed {
    name: Text
    seeds: Integer
}

function totalSeeds(beds: List<Bed>): Integer {
    let total = 0
    for bed in beds {
        total += bed.seeds
    }
    return total
}

test "an empty garden needs no seeds" {
    expect(totalSeeds([]) == 0)
}

test "every bed contributes to the total" {
    let beds = [
        Bed { name: "Peas"; seeds: 8 },
        Bed { name: "Herbs"; seeds: 6 }
    ]
    expect(totalSeeds(beds) == 14)
}

let beds = [
    Bed { name: "Peas"; seeds: 8 },
    Bed { name: "Herbs"; seeds: 6 },
    Bed { name: "Flowers"; seeds: 10 }
]
let budget = 30
for bed in beds {
    print("\(bed.name): \(bed.seeds) seeds")
}
let needed = totalSeeds(beds)
print("Total: \(needed) seeds")
if needed <= budget {
    print("Seeds left: \(budget - needed)")
} else {
    print("Extra seeds needed: \(needed - budget)")
}
```
```output
Peas: 8 seeds
Herbs: 6 seeds
Flowers: 10 seeds
Total: 24 seeds
Seeds left: 6
```

Read the declarations first: `Bed` describes our information and `totalSeeds`
describes a task. The tests check two examples of that task. Then the
top-level instructions create the plan, print each bed and compare the total
with the budget. We chose nonnegative, small seed counts; this version does
not validate arbitrary input.

Run these commands inside the project directory:

```sh
minyar check
minyar run
minyar test
minyar build --release
"./target/release/hello"
```

The last path assumes you called the project `hello` in chapter 1. Substitute
your project name if you chose another. `check` checks types without producing
an executable. `test` runs the test cases. `build --release` creates an
optimized executable you can run directly.

## Make it yours

Try these changes one at a time. Save, predict the result, run the program,
and run the tests after changing a function.

1. Change the budget to `20`. You should need four extra seeds.
2. Restore `30` and add a bed needing five seeds. The total becomes `29` and
   one seed remains. Add a test for your new combination.
3. Put the printing loop in a function taking `List<Bed>`, then call it.
   The output should stay the same.
4. Add a function returning `Result<Integer, Text>` that rejects a bed with
   a negative seed count. Handle success and failure with `match`, as in
   chapter 7. Test a negative count as well as an ordinary plan.

There is a [complete worked answer to the validation exercise](answers.md)
when you are ready to compare approaches. Its program and tests are checked
alongside every other example in this book.

You now have the pieces to write small tools: data, decisions, repetition,
functions, tests and explicit failures. For bigger programs, learn
[modules](../modules.md), which let files share public declarations, and
[the project CLI](../cli.md), which manages builds and dependencies.
The [language guide](../language.md) describes the rest of Minyar. This
[garden program is also a runnable gallery file](../../examples/gallery/community-garden.min);
the checker keeps it identical to the program on this page. The
[gallery](../../examples/gallery/) offers more complete programs to explore.
