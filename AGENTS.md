# Working on Minyar

- Read `docs/language.md`, `docs/compiler-syntax.md` and `docs/testing.md` for
  the area you change. The compiler is Minyar, bootstrapped by `bootstrap/stage0.c`.
  New syntax used inside the compiler must also work through stage0.
- Start with the smallest existing `check-*` target in `build-support/*.mk`.
  `make check-changed-plan` explains the working-tree selection;
  `make check-changed` runs core plus affected library checks. Set
  `CHECK_CHANGED_BASE` to include commits since a branch point. Unknown paths
  fall back to `check-portable`. See `docs/testing.md` for build-box inputs.
- Keep a warm build directory. Use the existing check runner for concurrent
  targets; separate raw Make processes must use separate build directories.
  `make -j8` alone does not parallelize this repository (`.NOTPARALLEL`).
- A timeout is a failure. Isolate it, retain its log, and compare CPU with wall
  time before changing limits. `MINYAR_TEST_TIMEOUT_SCALE=2` widens harness hang
  detection on loaded hosts without changing correctness assertions.
- Run the narrow check first, then the required portable/platform gate. Keep
  O0/O2 execution, rejection diagnostics and ownership assertions for language
  changes. Never substitute a smoke pass for the required landing gate.
- Follow the active run's coordination charter for build hosts, status and
  landing. During the 2026-10-20 moonshot, all builds/suites run through `bx`
  (macOS-only lanes have an explicit exception); use `gate.sh` then `land.sh`.
- Use one-line Conventional Commits: `type(scope): short plain message`, with
  no body or trailers. Do not push unless the user explicitly authorizes it.
