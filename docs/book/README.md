# Minyar for people who have never programmed

A program is a set of instructions you can save, change and run again. This
short book starts with one instruction and ends with a program that plans a
community garden. You need no programming vocabulary before you begin.

```minyar
print("There is room for you here.")
```
```output
There is room for you here.
```

The first box is a program. The second is what it prints. You type the first
box into a file; the second lets you check what happened. Through chapter 8,
each Minyar box is a complete, independent program: replace the entire file
with the next box, without keeping code from an earlier page. Project chapters
label their files with a `// file:` comment; keep all the files shown on that
page together.

Read in order:

1. [Your first program](01-first-program.md): save instructions and run them.
2. [Giving things names](02-names.md): keep values and do arithmetic.
3. [Making decisions](03-decisions.md): choose and repeat instructions.
4. [Working with lists](04-lists.md): do useful work on a collection.
5. [Writing functions](05-functions.md): name a task and check it with tests.
6. [Keeping related things together](06-records.md): describe something real.
7. [When something is missing or fails](07-results.md): handle both outcomes.
8. [A small program of your own](08-garden.md): bring the pieces together.
9. [More than one file](09-modules.md): share a module and test its private code.

After trying chapter 8's validation exercise, compare it with a
[worked answer that checks the garden plan](answers.md).

Take breaks. Run each example, change one thing and predict what will happen.
Understanding a small program is more useful than rushing through a large one.
The exercises have answers you can check by running your changed program.

Already a programmer? Start with [Minyar for Rust programmers](../from-rust.md),
[C++ programmers](../from-cpp.md) or [Swift programmers](../from-swift.md).
The [language guide](../language.md) is the detailed reference.

## How the examples stay honest

`make check-book` reads these pages and the three transition guides directly.
It compiles every Minyar box and checks successful completion, exact printed
output and empty standard error at O0 and O2. It also builds and runs embedded
tests. Each example has its own temporary directory. No handwritten duplicate
of a book program stands in for the page you read.
For project pages, the checker assembles the labeled files before compiling
each one, so imports and private module tests are checked too.

Every program box must have an explicit `output` box, including an empty one
for a program that prints nothing. The checker rejects missing, orphaned and
unclosed fences. Shell boxes describe commands to enter in a terminal; the
[first-program walkthrough](01-first-program.md) explains their prerequisites.
`make check-book-cli` follows those project commands through the public
launcher and runs the final garden executable in the release profile.
It also creates the multi-file harvest project directly from chapter 9,
checks its imported function and tests, and runs its release executable.
