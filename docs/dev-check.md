# dev-check: affected gate checks in seconds to minutes

`minyar dev check` (or `make dev-check`, or `python3 tools/dev-check.py`) runs
exactly the `check-portable` checks that a change can affect, on a warm
prebuilt tree, through `make check-in-parallel`. It prints the changed sources,
the stale build outputs, every selected check with the reason it was selected,
and one verdict line:

```
GREEN: 4 affected check(s) passed in 41 s. Run the full gate (make check-in-parallel CHECKS=check-portable) before merging.
RED: 1 of 9 failed: check-suite-catalogue
```

`--plan` prints the selection without running it. `--only PATH...` limits the
claim to some changed paths or directories; the verdict then names how many
other changed paths it did not cover. `--jobs N` (default 4) is passed to the
check runner. The command exits 0 for green, 1 for red, 2 when it cannot
decide (no index) and 3 (`BASE-RED`) when only checks that already failed at the
indexed base failed. `--bench` also runs the affected `benchmarks/compare`
programs under cachegrind and prints their Minyar Ir against
`--bench-base` (a `compare.json` of the base), failing if an output differs.

It is feedback, not a landing gate: always run the full gate before merging.
dev-check is the default pre-gate step for all Minyar work: run it after every
change, fix what it reports, and only then queue the full gate.

## How a check is selected

Selection comes from recorded dependencies, not from a list of areas:

1. `make dev-check-index` runs the whole gate once on the base tree under
   `strace -f --seccomp-bpf -e trace=%file,%process` and records, for every
   check, each path its processes opened, stat'ed or executed (failed lookups
   included, since a file created there changes behaviour), and each directory
   they listed. Processes are attributed to the check whose `make -j1 check-x`
   started them. The check's own Make parse (Makefile, `.mk`, `.d` includes and
   `$(shell ...)` run while parsing) is excluded; step 4 compares Make itself.
   The index also keeps the base tree's content hashes, every Make rule and
   every Makefile variable, and which checks passed. `build/dev-check/index.json`
   is about 20 MB; the trace itself is not needed afterwards.
2. `run` hashes the source tree and compares it with the base. Content decides
   what changed, not timestamps: files whose content matches what was last
   built get that build's mtime back, and every other file is stamped now, so a
   copied or synced tree can never look up to date when it is not.
3. `make -n --debug=b` over every check's file prerequisites lists the build
   outputs the change makes stale. This is Make's real graph, including the
   `.ll.d` files that record which library modules each harness imports, so a
   library change reaches exactly the harnesses that import it, and a compiler
   or runtime change reaches everything built with `build/minyarc` or linked
   with `build/minyar-runtime.o`.
   Make's graph is coarse (every object lists every makefile), so `run` then
   builds the stale outputs through the check runner's parallel builder and
   keeps only those whose bytes changed (builds are deterministic); an output
   left stale or unbuilt counts as changed. `--no-cutoff` skips this.
4. A check is selected when it read a changed source or a changed output, listed
   a directory that gained or lost a file, or its Make rules (with all
   prerequisites) or the Makefile variables they use changed. File targets are
   compared by recipe; their prerequisite lists act through step 3. A `make`
   that a check runs to build goals is treated like the check's own Make (its
   goals join the comparison); one that prints or queries the database
   (`-p`, `-n`, `-q`) keeps every makefile it reads as a dependency. A check that is
   new or has no trace is always selected. A check that failed at the indexed base is
   run only when its (partial) trace is hit, and listed as red at base otherwise:
   the gate is red there whatever the change does (`--include-base-red` runs them). If the check
   runner itself is stale, every check runs.

So a docs or report edit runs only the checks that read that file, a test
file edit runs its own check, a library module edit runs the checks whose
harnesses or fixtures use that module (directly or through imports), and a new
test file runs the checks that enumerate its directory, such as
`check-suite-catalogue`.

## Compiler and runtime changes: selection by function

A second index records which compiler and runtime functions each check
executes. `tools/dev-check.py coverage` folds it in from one instrumented gate
run (`sh tools/dev-check-coverage/run.sh`): a clang wrapper compiles runtime C
and the compiler's LLVM IR with entry-instrumented IR profile counters
(`-fprofile-generate -mllvm -pgo-instrument-entry`), every link gets the
profile runtime plus a small object that also writes the profile on `_exit`,
`abort` and fatal signals, and a `make` shim on `PATH` sends the profiles of
each `make -j1 check-x` to that check's directory. A process killed with
SIGKILL loses its counts; LLVM 23's function-entry-only and continuous modes
produced unreadable profiles for runtime-linked programs and are not used. The index also keeps a function
snapshot of `compiler/**/*.min` and `runtime/**/*.{c,h}`.

For a change to those files, dev-check compares each file with the snapshot.
When only function bodies changed (comments and whitespace are ignored), it
selects the checks that executed one of those functions at base, plus:

- checks without complete coverage (they failed in the instrumented run, wrote
  an unreadable profile, or compiled runtime or compiler code to IR or assembly
  that they read as text rather than run);
- checks that open a changed compiler or runtime file, or a rebuilt compiler or
  runtime artefact, as data (anything but a compiler or linker reading it);
- checks selected the usual way by every other changed file or output. Build
  outputs whose only change is compiler or runtime code (the compilers, runtime
  objects, and programs linked from them) are explained by the coverage; a
  Minyar-compiled `.ll` whose bytes changed is a codegen change and selects the
  checks that use it.

It falls back to file-level selection (close to the full gate) when code
outside function bodies changed (types, structs, macros, constants, top-level
declarations), a signature changed, a file was added or removed, a changed
function has no coverage counter at base, or the check runner or a process
whose check is unknown executed a changed function. Line numbers that shift
inside unchanged functions are not treated as changes.

Compiler and runtime-core changes without a coverage index are honest rather than fast: almost every
check compiles or links Minyar code, so the selection is close to the full
gate. dev-check says so, and Make rebuilds `build/minyarc` through its normal
self-host stages (stage0 only when `bootstrap/` changed).

## Using it on a build box

The build box keeps a prebuilt base tree with its index. Seed your own copy
once (`cp -a` of the base, which includes `build/dev-check/index.json`), then
sync your worktree over it and run, for example:

```
BB_HOST=agent@HOST BB_ROOT=/home/agent/swarm bb <lane> './minyar dev check'
```

`bb` copies files but does not delete; dev-check removes base files missing
from the synced `.bb-files` list so deletions count. `make dev-check-rebase`
builds the current tree and measures later changes against it instead of the
indexed base. Rebuild the index (`make dev-check-index`, about one gate of
time) when the base moves far; until then a moved base only widens selection.

## Limits

- The index is per platform; it covers the Linux `check-portable` gate on the
  box where it was recorded. macOS-only checks are not covered.
- Reads through a directory descriptor the trace never saw opened, and
  `fchdir`, are not resolved. Checks that cannot run under `strace` (for
  example ones that use `ptrace`) fail at index time and are always selected.
- Benchmark selection is by imports: the programs under `benchmarks/compare`
  and `benchmarks/bothmodes` that import a changed module (directly or through
  library imports), or all of them for a compiler or runtime change.
  `--bench` measures only the compare programs; bothmodes ones are listed.

## Measured on the 8-vCPU build box (shared with ten agents, `--jobs 4`)

| change | selected | result |
| --- | --- | --- |
| docs/language.md edit | 4 of 337 checks | green in 166 s |
| tests/http.min edit (no Linux gate check reads it) | 0 (+1 untraceable) | green in 24 s |
| new test script + benchmarks.mk rule (batch 5) | 115 | red in 1,310 s, same root check as the gate |
| library/json.min edit (the check runner imports json) | all | equals the gate |
| compiler pass or runtime header edit, file-level index only | all | equals the gate (`build/minyarc` rebuild 52 s) |
| compiler function body edit, function index (constant-overflow diagnostic) | 78 | red in 700 s on the one failing check |
| runtime header function body edit, function index (`minyar_map_get_or`) | 90 | red in 1,022 s on the one failing check |

The full gate takes 22 to 24 minutes on the same box with `CHECK_JOBS=8`.

With the function index, most of the remaining selection for a compiler or
runtime change comes from checks that read the compiler binary, a runtime
object or the changed source as data (`sha256sum` for cache keys, copies, the
launcher). They stay selected: a check may compare such hashes.
