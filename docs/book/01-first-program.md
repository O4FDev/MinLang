# 1. Your first program

[Contents](README.md) · [Next: giving things names](02-names.md)

A computer follows instructions very literally. Writing a program means
making those instructions precise. You can start with a single line:

```minyar
print("Hello, world!")
```
```output
Hello, world!
```

`print` writes something on the screen and starts a new line. The parentheses
contain what to print. The quotation marks say that `Hello, world!` is text;
the marks themselves do not appear in the output.

## Make a place to work

First follow the [installation guide](../cli.md) and check that the `minyar`
command is available. Minyar is under development: the installation guide
distinguishes source builds and local release candidates; there is no public
release host yet. A source installation needs its native toolchain too.

Open a terminal, the application where you enter commands. Enter these lines
one at a time, in a directory where you keep your projects:

```sh
minyar new "hello"
cd "hello"
```

The first command creates a directory called `hello`. The second moves into
it. If that directory already exists, choose a new name instead.

Open `src/main.min` inside `hello` in a plain-text code editor. Replace its whole
contents with the first program above and save it. The `.min` ending tells
you this file contains Minyar source: instructions written for people to read.
Back in the terminal, still inside the `hello` directory, run:

```sh
minyar run
```

Minyar checks the source, compiles it into a native executable and runs it.
The first build can take longer while tools are prepared. Look for
`Hello, world!` in the output. Save the file after every change before running
again. If the terminal says it cannot find `minyar`, return to the installation
guide; that is a setup problem, not a problem with your program.

## Text and arithmetic

Instructions run from top to bottom. Replace the entire file with this:

```minyar
print("A little arithmetic")
print(20 + 22)
print("20 + 22") // Quotation marks make this text.
```
```output
A little arithmetic
42
20 + 22
```

Without quotes, `20 + 22` asks for addition. With quotes, it is just some text.
`//` begins a comment: an explanation for the reader, ignored by the program
until the end of the line. Put each instruction on its own line.

Try it: change `+` to `*` in the second line. Predict the result, then run it.
It should print `440`. The last line still prints the original text.

If you make a typing mistake, Minyar reports an error with a filename, line
and column, often showing the source and an underline. Start with the first
error, check the marked text, save a correction and run again. An error is
information about an instruction the computer could not accept.
