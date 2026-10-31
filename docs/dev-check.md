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
4. A check is selected when it read a changed source or a stale output, listed
   a directory that gained or lost a file, or its Make rules (with all
   prerequisites) or the Makefile variables they use changed. A check that is
   new or has no trace is always selected. A check that failed at the indexed base is
   run only when its (partial) trace is hit, and listed as red at base otherwise:
   the gate is red there whatever the change does (`--include-base-red` runs them). If the check
   runner itself is stale, every check runs.

So a docs or report edit runs only the checks that read that file, a test
file edit runs its own check, a library module edit runs the checks whose
harnesses or fixtures use that module (directly or through imports), and a new
test file runs the checks that enumerate its directory, such as
`check-suite-catalogue`.

Compiler and runtime-core changes are honest rather than fast: almost every
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
