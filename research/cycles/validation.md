# Validation record

Commands run from the repository root on macOS arm64 with Apple Clang 17.
Development wrappers were disabled in comprehensive runs after a background
link timed out. Each Python harness retained its timeout and sanitizer checks.

- After the live-ring regression and scan/service optimization (`9e804c3`),
  `make -k check -o check-budget LIMITED= SANITIZER_LIMITED=` passed, including
  all 32 native/sanitizer cycle configurations, all five source fixtures,
  ordinary/module/sanitized compiler fixed points, and the final native-program
  assertions. The sole skipped gate is the unchanged absolute budget, whose
  independently reproduced baseline failure is detailed below.
- `python3 tests/cycles-profiles.py --runtime-only`: all 32 configurations
  passed again after `6b57fdd` strengthened the temporary-only-root test. That
  test explicitly triggers an epoch, then requires the unrelated cyclic garbage
  to disappear while the temporary's cycle remains intact. Runtime code did
  not change after the complete functional run.
- `make -k check-bounded check-memory-profiles LIMITED= SANITIZER_LIMITED=`:
  passed again after `9e804c3`, including allocator oracles, sanitizer matrices,
  queue equivalence, profile regressions, lazy reservations through 1 TiB, and
  injected mapping-failure recovery.
- `python3 research/cycles/live-reserve.py --runtime-revision a2fbb02 --heap-bytes 4194304`
  and `python3 research/cycles/live-reserve.py`: passed. Two million iterations
  reduced peak pool usage from 2,450,048 to 917,888 bytes; the final run uses a
  1 MiB pool. The original 1 MiB failure is committed as `a2fbb02` before its fix.
- `python3 research/cycles/measure.py --runs 5`: repeated after these tests
  completed; final raw samples are in `measurements.json` at revision `6b57fdd`.

Earlier validation, before that final optimization:

- `make -k check LIMITED= SANITIZER_LIMITED=`: completed with failures in the
  absolute self-compile budget, old immediate-retirement ownership assertions,
  malformed-budget diagnostics, and a stale equality diagnostic expectation.
  The latter three categories were corrected in separate commits and rerun
  successfully, as recorded below. The budget ceiling remains unchanged.
  The cycle target passed all 32 native/sanitizer profile configurations and
  its three compiler tests; see [cycle-matrix.txt](cycle-matrix.txt).
- `make -k check -o check-budget -o check-cycles LIMITED= SANITIZER_LIMITED=`:
  functional rerun interrupted by SIGTERM during `check-stack-ownership`, with
  no preceding failed assertion. `-o check-budget` skips the independently
  established baseline failure; `-o check-cycles` avoids rerunning the matrix
  that was executing in the first full invocation. Completed prerequisites
  passed. The remaining targets were resumed with the command below, which
  exited successfully, including the root `check` recipe's compiler fixed point
  and native-program assertions. Across the original run, successful reruns,
  and separately completed cycle/profile matrices, every functional target
  passes; only the baseline resource-budget failure remains.
- `make -k check-bounded check-memory-profiles LIMITED= SANITIZER_LIMITED=`:
  passed. Includes all bounded allocator/ownership oracles, native/sanitizer
  budgets 1/32/1024, fusion equivalence, 42 profile regression checks, and lazy
  mapping configurations through 1 TiB virtual capacity.
- `make check-runtime-unit check-ownership-mutation check-sanitize LIMITED= SANITIZER_LIMITED=`:
  passed after gray-pin accounting updates. All four deliberately injected
  ownership leaks are still detected.
- `python3 tests/ownership-policy.py`: passed after fixing pre-existing malformed
  budget diagnostics. Includes module policy/cache transitions and native output.
- `make check-binary-expressions LIMITED= SANITIZER_LIMITED=`: passed after updating
  the stale Bytes equality diagnostic expectation (five tests each, native and
  sanitized compiler).
- `./minyar tests/cycles/graphs.min -o build/cycles-launcher-default` and execution:
  passed, output `0 1 2 1 0` on separate lines.
- `./minyar --release --memory-profile fixed --heap-bytes 1048576 --cleanup-budget 1 tests/cycles/dense.min -o build/cycles-launcher-release`
  and execution: passed, output `5000`.
- `python3 research/cycles/measure.py --runs 5`: completed; raw samples and
  reproduction commands are in `measurements.json`.
- `python3 research/cycles/baseline-budget.py`: failed the unchanged resource
  ceilings, independently of the cycle implementation; exact output is in
  `baseline-budget.txt`. Compiler fixed-point output matched before measuring.

The first red commit is `e229bb8`. No changes were pushed and no other checkout
was modified.

The full run's absolute budget result was 244.11 M retired instructions,
12.7 MiB peak memory, 26.21 ms wall p90 and 21.00 ms CPU p90. The extracted
baseline produced 243.70 M, 12.6 MiB, 28.31 ms and 22.32 ms respectively.
The unchanged ceilings are 75 M, 10 MiB, 25 ms and 22 ms. Both versions fail;
the remaining gate failure is explicitly not reported as a passing `make check`.

Resume command (the additional `-o` targets had completed successfully before
the interruption):

```sh
make -k check -o check-budget -o check-cycles -o doctor \
  -o check-smoke -o check-release-build -o check-recursive-data \
  -o check-compact-ownership -o check-adversarial -o check-ownership-mutation \
  -o check-regressions -o check-memory -o check-runtime-unit -o check-modules \
  -o check-fuzz -o check-stack-overflow -o check-mutation -o check-performance \
  -o check-scaling -o check-sanitize -o check-ownership -o check-runtime-cache \
  -o check-ownership-policy LIMITED= SANITIZER_LIMITED=
```
