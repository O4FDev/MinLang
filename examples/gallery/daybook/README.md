# Daybook

A native command line tool for adding up time across plain text daybooks. Keep
the files in Git, combine several weeks, or pipe the JSON report into another
tool. No dependencies, clock, account or network connection are needed.

From the repository root:

```sh
./minyar --debug "examples/gallery/daybook/src/main.min" -o "build/daybook"
./build/daybook "examples/gallery/daybook/week.tsv"
./build/daybook --json "examples/gallery/daybook/week.tsv"
```

From this directory, an installed Minyar also supports `minyar run -- week.tsv`
and `minyar test`. Use `--release` when building for regular use.

Each row is a project name, a tab, and nonnegative whole minutes. Names are
case sensitive and keep their Unicode spelling. Spaces around fields are
trimmed; blank lines and lines beginning with `#` are ignored. LF, CRLF and
a last line without a newline all work. There is no header row. Quotes have
no special meaning. `--` ends options for filenames beginning with a dash.

The example prints:

```text
DAYBOOK
project	minutes
Café	20
Garden	60
Writing	30
total	110
4 entries · 3 projects
```

JSON contains `entries`, `totalMinutes` and `projects` (an array of `name` and
`minutes`). Both reports sort project names by Minyar's Text ordering. Minutes
remain exact 64-bit integers, including in JSON; consumers using floating point
numbers should account for their own precision limit.

Bad data reports the filename, line and reason to standard error, exits 1, and
prints no partial report. Bad options exit 2. `--help` exits 0. Each input is at
most 4 MiB, with at most 64 files, 50,000 entries and 4,096 projects in a run.
Names have at most 80 Unicode scalar values and contain no control characters.
Totals are checked for overflow before changing the ledger.

Choices describe rows and commands; record methods collect and render the
ledger; `Result` and contextual `try` keep input errors recoverable. Text
interpolation and `joinText` build reports without repeated concatenation of
the growing output. Project lookup uses a Map and sorting costs O(p log p)
for p distinct projects. Inputs are read one bounded file at a time.
