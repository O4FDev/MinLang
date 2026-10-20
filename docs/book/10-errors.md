# 10. Reading an error and making one repair

[Previous](09-modules.md) · [Contents](README.md) · [Next](11-files.md)

A compiler error gives you a place to begin. It tells you which instruction
Minyar could not accept and where to look. Make one small correction, save,
and check again.

The first program in each pair below deliberately contains a mistake. Its
message is a compiler error, not something printed by the program. The second
program is a complete repair, followed by what it prints when run. Each pair
starts fresh; keep no source from the previous pair.

You can try the sources in your project's `src/main.min` and use `minyar check`
to check them. The messages below shorten the filename to `program.min`; your
message will name the file you actually checked. Run the corrected program
with `minyar run` after its check succeeds.

## Give a name the kind of value it expects

```minyar-reject
let light: Integer = "warm"
print(light)
```
```diagnostic
error: the value for 'light' does not match its declared type; expected Integer, found Text
  --> program.min:1:5
   |
 1 | let light: Integer = "warm"
   |     ^^^^^
   = help: change this value to the expected type, or change the declaration if it should accept the found type
   = explain: minyar explain E0401
```

Read the first line first: `light` was declared as Integer, but its value is
Text. `program.min:1:5` points to line 1, column 5. Line and column counting
start at one. The source line is repeated below; the `^` marks underline the
binding that needs attention. The underline identifies a relevant part of the
instruction, so read it together with the message.

The help line suggests a repair. The explain line gives a command for a
longer explanation: `minyar explain E0401`.

Suppose we meant a count of four lights. Keep the Integer type and change
`"warm"` to `4`:

```minyar
let light: Integer = 4
print(light)
```
```output
4
```

Predict the output before running the repaired source. If we had wanted the
word instead, that would call for a Text binding; choose the type that matches
what the value means in your program.

## Ask a question that has a Boolean answer

```minyar-reject
if 1 { print("light") }
```
```diagnostic
error: an if condition must be Boolean; expected Boolean, found Integer
  --> program.min:1:4
   |
 1 | if 1 { print("light") }
   |    ^
   = help: write a comparison such as count > 0, or use a Boolean value such as true or false
   = explain: minyar explain E0402
```

An `if` needs `true` or `false`. The number `1` alone is an Integer, so the
message points directly at it. Suppose the intended question was whether the
number is positive. Write that comparison:

```minyar
if 1 > 0 { print("light") }
```
```output
light
```

`1 > 0` produces a Boolean. Its answer is true, so the block runs. Try changing
`1` to `0`; the repaired program should then print nothing.
[Check the worked answer](answers.md#chapter-10-when-the-condition-is-false).

## Check the spelling before declaring another name

```minyar-reject
let lantern = 4
print(lantren)
```
```diagnostic
error: I can't find a value named 'lantren'
  --> program.min:2:7
   |
 2 | print(lantren)
   |       ^^^^^^^
   = help: did you mean `lantern`?
   = explain: minyar explain E0301
```

The first line says which name could not be found. The location points to its
use in `print`, and the help line offers the nearby name `lantern`. Compare
that with the name we introduced on line 1. Here, two letters were swapped.
Change only the spelling in the call:

```minyar
let lantern = 4
print(lantern)
```
```output
4
```

A suggestion is something to check against your intention. In this program,
the existing `lantern` is exactly the value we wanted to print.

## Give every choice a path

A choice declaration lists the forms a value can take. Here `Weather` can
be `Clear` or `Rain`. The semicolon separates cases written on one line.

```minyar-reject
choice Weather { Clear; Rain }
function warmth(weather: Weather): Integer {
    match weather { Clear { return 1 } }
}
print(warmth(Weather.Clear))
```
```diagnostic
error: match is missing cases: Rain; for example: Rain
  --> program.min:3:5
   |
 3 |     match weather { Clear { return 1 } }
   |     ^^^^^
   = help: add an arm for each missing case, or an else arm to handle all remaining cases
   = explain: minyar explain E0601
```

`Weather` has two cases, but the match handles only `Clear`. The message names
the missing case, `Rain`. Minyar checks the whole function even though the
last line currently passes `Weather.Clear`.

Add a Rain arm. Keep the meaning simple: Clear gives one unit of warmth and
Rain gives zero.

```minyar
choice Weather { Clear; Rain }
function warmth(weather: Weather): Integer {
    match weather { Clear { return 1 } Rain { return 0 } }
}
print(warmth(Weather.Clear))
```
```output
1
```

Now both possible inputs have an answer. Change `Weather.Clear` on the final
line to `Weather.Rain` and predict `0` before running again.
`Weather.Rain` constructs the Rain form of the choice.
[Check the worked answer](answers.md#chapter-10-taking-the-rain-path).

When a check reports several errors, start with its first message. Read the
file location, find the underlined source, and make one repair that matches
your intention. Check again before making another change. A successful source
check means Minyar accepted the program's types and structure; tests and
careful inputs still help you check whether it does the task you intended.
