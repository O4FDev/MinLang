# Gardening

Most changes here are written by agents. They copy what they find: a stale
doc, a dead script, or a log someone committed becomes the next agent's
example. Gardening is the upkeep that stops this. Remove weeds while they are
small. When something misleads an agent, fix the thing that misled it, not
only the one mistake. Add cheap checks that show the next agent what matters.

## Run it

```sh
make garden                       # or ./minyar dev garden
make garden GARDEN_FLAGS=--online # also compare pinned versions with upstream tags
python3 tools/garden.py docs unused --limit 0
make check-garden                 # exit 1 if docs drift or tracked leftovers exist
```

`tools/garden.py` reads the tree and needs no build. It takes a few seconds.
Each finding is `where: what`, and the last line is a summary such as
`garden summary: docs=0 unused=35 ...`. Compare that line before and after
your change. `--json` prints the findings as JSON. `--root DIR` inspects
another checkout.

## Sections and what to do

- `docs`: a living doc names a Make target, a repository path, a link
  target or a launcher flag that does not exist. Fix the doc, or the code if
  the doc describes the intended behaviour. Write placeholders in upper case
  or in angle brackets (`check-NAME`, `check-<name>`) so they are not read as
  real names. Drift in `docs/records/`, `docs/research/` and `tests/` is not
  reported.
- `unused`: files in `tools/`, `scripts/`, `install/` and `build-support/`
  that nothing mentions, or that only docs mention, and Make targets that no
  rule, recipe, doc, script or workflow runs. Delete a file or target only
  when `git grep` confirms nothing uses it. Git history keeps the file. An
  orphan `check-*` target is a test that never runs: wire it into a gate
  aggregate, or delete it after a test review.
- `size`: tracked files over 2 MiB and source files over 8,000 lines.
  Generate large data instead of tracking it, or fetch and pin it. Split long
  sources when they change.
- `leftovers`: tracked logs, backups and scratch files, and dated Markdown
  outside `docs/records/`. Delete them, or move the record to
  `docs/records/YYYY-MM-DD-topic/`.
- `local`: ignored files in this checkout outside `build/`, such as old
  notes, saves and packaged extensions. They are not in the repository, but
  they mislead tools and agents that list the directory. Move them out.
- `todos`: markers in sources and docs written as `TODO:`, `FIXME:`,
  `XXX:` or `HACK:`. Undated markers are reported. Dated markers, written
  `TODO(YYYY-MM-DD): ...`, are reported once their date has passed. Fix the
  item or give it a date.
- `checks`: the slowest checks from `build/tooling/check-durations`. Pass
  `--check-log FILE` (repeatable) with check-runner or gate logs to also list
  checks that timed out, and checks that both passed and failed. A check that
  does both on the same tree is flaky. A slow check slows every agent that
  runs the gate, so make it faster or run it less often.
- `deps`: the pinned LLVM, vendored libraries and the Swift toolchain, with
  how long ago each pin changed. `--online` runs `git ls-remote` against each
  upstream repository and names newer releases. Update a pin and its
  fingerprints together, as `vendor/README.md` describes.

`tools/garden-allow.txt` lists deliberate exceptions, each with its reason.
Prefer fixing the finding. Add a line only when a doc names a file in another
repository or in a generated project.

## Where it runs

- On your machine: `make garden` before you finish a change. Leave the
  summary no worse than you found it.
- Nightly CI: the `garden` job in `.github/workflows/fuzz-nightly.yml` runs
  `make check-garden`. It fails on docs drift or tracked leftovers and writes
  the full report, with `--online` pin checks, to the job summary.

## Layout

- `compiler/`: the Minyar compiler, written in Minyar.
- `bootstrap/stage0.c`: the C compiler that builds the first compiler.
- `runtime/`: the C runtime.
- `library/`: the standard library.
- `tests/`: tests, fixtures and data.
- `build-support/*.mk`: the Make rules, one file per area.
- `tools/`: developer tools.
- `scripts/`: platform and release scripts.
- `docs/`: living documentation.
- `docs/records/`: dated records. These are not maintained, so do not
  follow them as current instructions.
- `experiments/`: measurement studies. `experiments/memory/` also holds
  fixtures that maintained tests use.
- `benchmarks/`, `examples/`, `os/`, `playground/`, `proofs/`, `editors/`,
  `install/`, `toolchains/` and `vendor/` are named for what they hold.
