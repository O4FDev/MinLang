# 11. Saving a garden note

[Previous](10-errors.md) · [Contents](README.md)

A program can keep a note in a file and read it back later. Writing or reading
can fail, so both operations return a `Result`, like the functions in
[chapter 7](07-results.md). This time the explanation has the type
`errors.Error`, which can describe both the failure and what we were trying
to do.

Create a fresh project for this example:

```sh
minyar new "garden-notes"
cd "garden-notes"
```

Replace `src/main.min` with this whole program:

```minyar
use "io" as io
use "errors" as errors

function saveAndRead(path: Text, note: Text, maximumBytes: Integer): Result<Text, errors.Error> {
    try io.writeText(path, note) else "saving the garden note"
    let saved = try io.readTextWithin(path, maximumBytes) else "reading the garden note"
    return Ok(saved)
}

let path = "garden-note.tmp"
let note = "Peas: 8; herbs: 6"
for maximumBytes in [64, 8] {
    print("Read limit: \(maximumBytes) bytes")
    match saveAndRead(path, note, maximumBytes) {
        Ok(saved) { print("Saved and read: \(saved)") }
        Err(error) { print(error.describe()) }
    }
}
```
```output
Read limit: 64 bytes
Saved and read: Peas: 8; herbs: 6
Read limit: 8 bytes
reading the garden note
  could not read file: garden-note.tmp
```

Save the file, then enter:

```sh
minyar check
minyar run
```

The program prints the lines above. Unlike the compiler errors in
[chapter 10](10-errors.md), this read failure happens while an accepted
program is running. Our `Err` arm chooses to print an explanation and
continue. `error.describe()` turns the error and its operation descriptions
into Text for `print`.

## Save, then read

`io.writeText(path, note)` creates the file if it is missing and replaces its
contents if it already exists. Both trips through the loop write the same
note. Use the disposable filename in this fresh project; changing it to the
name of an existing file would replace that file's contents.

When launched with `minyar run`, the program starts in the project directory.
Here, `garden-note.tmp` is beside `Minyar.toml`, rather than inside `src`.
It remains there after the program ends so you can open it and inspect the
note. The `.tmp` ending is just part of its name; it does not make the file
disappear automatically.

The first `try` continues when writing succeeds, or returns the error from
`saveAndRead` when writing fails. A successful write has no value to store;
we can go straight on to reading. `else "saving the garden note"` adds what
we were doing to that error. It does not run a replacement operation.
The next line does the same for reading. Once both operations succeed,
`Ok(saved)` passes the text back to the caller.

## Choose how much text to accept

`readTextWithin` accepts a whole file only when its contents fit within the
given byte limit. It returns an error if the file is larger; it does not
silently return just the beginning.

Our note uses 17 bytes, so the 64-byte read succeeds. The 8-byte read is
deliberately too small. The explanation names the failed read, with our
operation description above it. Other problems can also make a read fail;
this message alone does not identify which one occurred.

The limit counts stored UTF-8 bytes, rather than visible letters. The plain
letters, digits, spaces and punctuation in this note each use one byte.
Other characters can use more than one.

Try it: change the note to `""`, leaving both limits unchanged. An empty
file is valid text. Both reads should succeed, and both success messages
should have nothing after `Saved and read: `. Restore the original note
afterwards, or write a short note of your own and choose a limit that fits.
