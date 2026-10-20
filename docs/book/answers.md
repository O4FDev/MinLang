# A worked answer: checking the garden plan

[Contents](README.md) · [The garden exercise](08-garden.md#make-it-yours)

Try the last exercise before reading this answer. There are several reasonable
ways to arrange it. This version keeps the calculation separate from printing,
so tests can check the answer without reading messages from the screen.

```minyar
record Bed {
    name: Text
    seeds: Integer
}

function checkedTotal(beds: List<Bed>): Result<Integer, Text> {
    let total = 0
    for bed in beds {
        if bed.seeds < 0 {
            return Err("Count the seeds for \(bed.name) again.")
        }
        total += bed.seeds
    }
    return Ok(total)
}

function showPlan(beds: List<Bed>) {
    match checkedTotal(beds) {
        Ok(total) { print("Total: \(total) seeds") }
        Err(message) { print(message) }
    }
}

test "a valid plan adds the beds" {
    let beds = [Bed { name: "Peas"; seeds: 8 }, Bed { name: "Herbs"; seeds: 6 }]
    match checkedTotal(beds) {
        Ok(total) { expect(total == 14) }
        Err(message) { expect(false) }
    }
}

test "a negative count is an error" {
    match checkedTotal([Bed { name: "Peas"; seeds: -1 }]) {
        Ok(total) { expect(false) }
        Err(message) { expect(message == "Count the seeds for Peas again.") }
    }
}

test "an empty plan has a zero total" {
    match checkedTotal([]) {
        Ok(total) { expect(total == 0) }
        Err(message) { expect(false) }
    }
}

showPlan([Bed { name: "Peas"; seeds: 8 }, Bed { name: "Herbs"; seeds: 6 }])
showPlan([Bed { name: "Peas"; seeds: -1 }])
```
```output
Total: 14 seeds
Count the seeds for Peas again.
```

`checkedTotal` returns as soon as it finds a negative count. It checks a bed
before adding its seeds, so no misleading total is returned for that plan.
`showPlan` decides what to print for either result. The tests make the same
decision: `expect(false)` marks a branch that should not happen in that case.

The empty List needs no explicit type here because the function's parameter
supplies `List<Bed>`. Its loop runs zero times and the total stays zero.

Save the whole program as `src/main.min` and use `minyar run` and `minyar test`.
This solution still assumes totals fit in an Integer. Checking negative values
does not prevent overflow if enormous positive counts are added. Handling that
separate problem would use the recoverable checked arithmetic described in
the [language guide](../language.md#numbers-and-comparisons).
