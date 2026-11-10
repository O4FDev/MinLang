# Working on Minyar

- Read `docs/language.md`, `docs/compiler-syntax.md` and `docs/testing.md` for
  the area you change. Read `docs/writing-tests.md` before adding or changing
  a test: assert product behaviour, not incidental detail. The compiler is Minyar, bootstrapped by `bootstrap/stage0.c`.
  New syntax used inside the compiler must also work through stage0.
- Start with the smallest existing `check-*` target in `build-support/*.mk`.
  `make check-changed-plan` explains the working-tree selection;
  `make check-changed` runs core plus affected library checks. Set
  `CHECK_CHANGED_BASE` to include commits since a branch point. Unknown paths
  fall back to `check-portable`. See `docs/testing.md` for build-box inputs.
- Keep a warm build directory. Use the existing check runner for concurrent
  targets; separate raw Make processes must use separate build directories.
  `make -j8` alone does not parallelize this repository (`.NOTPARALLEL`).
- Narrow deterministic fuzzing with `check-fuzz-expressions`, `check-fuzz-hostile`
  or the other documented stage targets. Use `check-regressions-case` with
  `CHECK_REGRESSION_CASE=Regressions.test_name` for one existing regression.
- A timeout is a failure. Isolate it, retain its log, and compare CPU with wall
  time before changing limits. `MINYAR_TEST_TIMEOUT_SCALE=2` widens harness hang
  detection on loaded hosts without changing correctness assertions.
- Run the narrow check first, then the required portable/platform gate. Keep
  O0/O2 execution, rejection diagnostics and ownership assertions for language
  changes. Never substitute a smoke pass for the required landing gate.
- Follow the active run's coordination charter for build hosts, status and
  landing. The inherited pre-commit hook builds locally. When a charter keeps
  builds off this machine, commit with `git -c core.hooksPath=/dev/null commit`
  after its checks; the override still requires the charter's landing gate.
- Use one-line Conventional Commits: `type(scope): short plain message`, with
  no body or trailers. Do not push unless the user explicitly authorizes it.

## Leave the repository better than you found it

- Run `make garden` (see `docs/garden.md`) before you finish. Do not raise any
  count on its summary line. Fix any drift your change causes.
- If a doc, example or check misled you, fix it in the same change. A wrong
  example misleads the next agent too.
- Keep run artefacts out of the tree: logs, notes, scratch programs, saves and
  per-agent reports go in the run's own folder. A record worth keeping goes in
  `docs/records/YYYY-MM-DD-topic/`. Living docs describe the current tree.
- Delete what you can prove dead with `git grep`, such as unused scripts,
  targets and files. Git history keeps them. Removing a check needs a test
  review.
- Give every TODO a date, as `TODO(YYYY-MM-DD)`. Write placeholders in docs as
  `check-NAME` or `<name>`.
