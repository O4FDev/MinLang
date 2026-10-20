# Differential compiler fuzzing

`make check-differential-fuzz` first replays the checked-in regression corpus,
then generates eight reproducible, valid programs. Each combines random checked
and wrapping Integer expressions, bounded loop control and short circuits,
shared records and Lists, Map and Set key snapshots with aliased managed values,
Bytes, captured callbacks, and choices whose reference payloads outlive their
input slot. The collection cases mutate record keys after insertion and keep
List values across replacement, removal and clear operations. A Python model
computes every observation without invoking Minyar. Each program checks those
values itself, and the runner independently checks its complete output.

Each program runs in eight configurations: the stage2 and stage3 compilers,
eager reference counting and the process-lifetime arena, and Clang O0 and O2.
The runtime is also built at the selected optimization level. Eager runs use
the existing test-only ownership contract to check cleanup on normal return;
arena runs intentionally retain their allocations. The compiler executables
themselves use the standard compiler arena in both stages.

The target is separate from `check-portable` so ordinary gates retain their
existing cost. Include it explicitly when changing lowering or memory ownership:

```sh
make check-differential-fuzz FUZZ_SEED=0xC0DE FUZZ_PROGRAMS=100 FUZZ_SIZE=24
```

For the moonshot worktrees, run that command through `bx fuzz`; builds and
campaigns belong on the remote box. Every child process has a deadline, and a
timeout kills its process group and fails the campaign. Captured stdout and
stderr share a 16 MiB limit, preventing a noisy compiler or program from
exhausting the runner before its deadline.

Evidence is retained under `build/differential-fuzz/campaign-*`: generated
source, independent expected output, generator specifications, LLVM, runtime
source and objects, executable variants, and exact commands with captured raw
stdout/stderr, status and timing. `results.json` records compiler hashes and
the actual outcome. A nonzero program status, unexpected diagnostics, a wrong
transcript, rejection of generated source, or a timeout is a failure.

The first failing configuration is reduced by deleting independent functions
and shrinking generator sizes, preserving its phase, configuration and exact
failing check. Stable family, seed and check labels keep two failures in the
same matrix cell from being confused during reduction. The bounded reduction is
a starting point for a regression, not a claim of globally minimal source. The
original case always remains available. Replay either
`program-NNNN/spec.json` or `minimized/spec.json` with:

```sh
python3 tests/differential-fuzz.py --clang clang-23 \
    --replay build/differential-fuzz/campaign-EXAMPLE/minimized/spec.json
```

`--replay` is repeatable. After confirming a compiler fix, copy the minimized
specification to `tests/differential-fuzz-regressions/NNNN-description.json`.
`make check-differential-fuzz-regressions` replays every specification in that
versioned corpus across all eight configurations. The initial matrix baseline
also proves the replay path before the first discovered miscompilation is added.

Use `--timeout` to change the per-command deadline and `--shrink-attempts 0`
to retain an unreduced failure immediately. The seed and generator specification
are replay inputs; use the original compiler/runtime revision for exact replay.
Finite seeded coverage does not establish the absence of miscompilations.
