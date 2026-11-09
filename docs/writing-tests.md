# Writing Minyar tests

Read this before adding or changing a check. `docs/testing.md` explains how to
run the suites; this page says what a test should and should not assert.

## A test asserts a property of the product

The product is the language, the compiler, the runtime and the library. A good
test fails when a user-visible guarantee breaks and passes after any correct
refactor. Assert:

- **Program behaviour**: the output, exit status and side effects of a compiled
  program, at O0 and at O2 (the two must agree).
- **Rejections**: invalid programs fail to compile with status 1, leave no
  LLVM output, and name the problem and the source line and column. Match the
  stable part of the message (the phrase and the location), not the whole text.
- **Ownership and memory safety**: no use after free, no double release, no
  leak of reclaimable objects at exit, bounded reclamation. Prefer running the
  program under ASan/UBSan or the ownership runtime over inspecting IR.
- **Checked failures**: overflow, bounds, division by zero and similar traps
  happen at the right operation, before later effects.
- **Documented library behaviour**, including errors and edge cases.

## A test does not assert incidental details

Do not assert any of these unless the detail is itself the documented
contract (a file format, a wire protocol, an ABI):

- exact byte sizes, instruction counts, line counts or symbol names in
  generated LLVM or object code;
- the exact wording of output that is not the subject of the test (harness
  summaries, help text, another tool's messages);
- the text, layout or command count of Makefiles, scripts or source files
  (assert that a check runs and what it checks, not how a recipe is spelled);
- the number of rows in a fixture or corpus, unless the fixture is generated
  from a seed and the count checks the generator;
- the current behaviour of something the language does not define. If you
  must pin it, name the test `..._current_...` and record the open question.

## Time, load and the network

- No wall-clock upper bound tighter than the alternative it rules out. To
  show a deadline holds, make the failure mode unbounded (keep interrupting,
  keep the peer silent) and assert only that the call returns at all, with a
  generous limit scaled by `test.scaledSeconds`.
- Performance belongs in benchmarks and in `check-budget` (retired
  instructions on the owner's macOS runner), not in correctness checks.
- No test may need the internet. Use local peers, mirrors and fixtures.

## One property, one place

- Before adding a check, look for one that already covers the property. Do
  not run the same command with the same inputs from two gate targets; give
  a shared step its own target and depend on it.
- A budget or profile matrix (cleanup budgets 1/32/1024, heap profiles,
  sanitize/native) earns each cell by exercising a different code path. Say in
  the target's comment which path each cell reaches.
- Tests of the test harness are fine when the harness decides pass or fail
  (the check runner, timeouts, the fuzz minimiser). Keep them small.
- Records of past review or agent runs (ledgers, reports, evidence logs) are
  not tests. Keep them out of the per-commit gate.

## A test must be able to fail

Before landing a new test, break the code it protects (or use a mutant, as the
memory and wiring checks do) and see it fail with a message that says what
broke. A test that is skipped on every gate host protects nothing: either run
it somewhere or delete it.
