# 7. When something is missing or fails

[Previous](06-records.md) · [Contents](README.md) · [Next](08-garden.md)

An empty List is ordinary information. Reading its first position anyway is
a mistake. A function can describe the possibility of absence in its type:

```minyar
function firstName(names: List<Text>): Maybe<Text> {
    if names.length == 0 { return None }
    return Some(names[0])
}

for names in [["Ada", "Jo"], []] {
    match firstName(names) {
        Some(name) { print("Welcome, \(name).") }
        None { print("No one has signed up yet.") }
    }
}
```
```output
Welcome, Ada.
No one has signed up yet.
```

`Maybe<Text>` holds either `Some` text or `None`. It is a choice: one value
with one of several possible forms. `match` handles those forms. The name
inside `Some(name)` becomes available only in that arm's block.
Minyar checks that the match covers both forms, so absence is not forgotten.

## Explain a failure

A `Result<Integer, Text>` holds either `Ok` with an Integer or `Err` with
an explanation in Text. The two type arguments name the success and error
types, in that order:

```minyar
function shareSeeds(seeds: Integer, people: Integer): Result<Integer, Text> {
    if people <= 0 { return Err("We need at least one person.") }
    if seeds < 0 { return Err("The seed count cannot be negative.") }
    return Ok(seeds / people)
}

for people in [3, 0] {
    match shareSeeds(12, people) {
        Ok(count) { print("Seeds per person: \(count)") }
        Err(message) { print(message) }
    }
}
```
```output
Seeds per person: 4
We need at least one person.
```

The function checks the divisor before dividing. Returning an error lets
the caller choose what to do; it does not stop the whole program.
The type does not make every function automatically safe: we still write
the checks appropriate to its inputs.

Try it: change the seed count from `12` to `-1`. With three people you should
get the seed-count explanation. With zero people you still get the first
explanation, because the checks run in order.

## Pass a failure back to your caller

Inside another Result-returning function, `try` extracts success or returns
the error immediately. The two functions must use the same error type:

```minyar
function availableSeeds(count: Integer): Result<Integer, Text> {
    if count < 0 { return Err("Count the seeds again.") }
    return Ok(count)
}

function plan(count: Integer): Result<Text, Text> {
    let seeds = try availableSeeds(count)
    return Ok("Ready with \(seeds) seeds.")
}

for count in [12, -1] {
    match plan(count) {
        Ok(message) { print(message) }
        Err(message) { print(message) }
    }
}
```
```output
Ready with 12 seeds.
Count the seeds again.
```

On failure, `plan` never reaches its second line. `try` propagates a Result;
it does not catch out-of-bounds access, Integer overflow or other runtime
stops. Use `match` where your program can make a decision about a failure.
