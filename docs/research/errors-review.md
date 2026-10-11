# Independent typed Result review, 2026-10-11

Reviewed base: `74eec16a3f9bc4a442d224de4ce42abf843ed258`, in a separate
Boat worktree on `overnight/errors-review`. The original errors worktree was
not edited. Every build and test ran remotely, with sequential compiler links.

## Findings and fixes

1. **P2: generic punctuation lost its lexical kind.** In the reviewed base,
   `compiler/errors-compiler.min:87` recognized a quoted `"<"` as a constructor
   delimiter, line 23 consumed a quoted `">>"`, and line 63 consumed string or
   Character commas inside nested Callback types. Invalid programs compiled,
   including `Ok"<"Integer, Text>(1)` and
   `Result<Callback<Integer "," Integer>, Text>`. The frontend now checks
   punctuation kinds, uses the existing checked token predicate for commas,
   and requires balanced constructor headers. Tests cover both quotes and
   nested annotation positions: bindings, Lists and record fields.

2. **P2: generic-looking value comparisons were rewritten as types.** The same
   recognition rule rejected valid ordinary expressions such as
   `let Result = 1; print(Result < 2)`. Type-position and constructor-header
   recognition now preserve ordinary Result/Ok/Err variable comparisons.
   Their LLVM is byte-identical to the ordinary frontend.

3. **P2: unused managed parallel parameters escaped the scalar ABI check.**
   The maintained core checks parallel body usage at
   `compiler/compiler.min:4833`, but an unused
   `Result<Integer, Text>` parameter did not mark that body as using references.
   Even `parallelEntry` accepted the declaration. The guarded Result adapter
   now checks parameter and return types separately from body liveness.
   Negative controls cover Result, List, Callback, Text, Bytes and records,
   with and without parallelEntry; native Result arguments remain rejected.
   The ordinary core is unchanged. Its pre-existing unused-managed-parameter
   gap remains outside this opt-in review patch.

No Result ownership or networking-library defect was reproduced by the
independent runtime adversaries. This is bounded evidence, not a claim that
every combination has been proved correct.

## Independent tests and provenance

`tests/errors-review.py` contains 22 independent test methods. Runtime cases
execute at both O0 and O2 with the existing exact frame/object/debt oracle.
They cover nested matches, shadowing, mixed returns, loop jumps, single input
evaluation, propagated reference payloads after container replacement, nested
callbacks, equal imported aliases, distinct modules with the same type name,
cyclic callbacks through both slots, and recovery followed by further work.

Real loopback UDP tests distinguish would-block, truncated prefix preservation,
empty successful packets and recovery. Real TCP tests distinguish short data
reads from EOF. A per-iteration live-object check drains bounded debt and
verifies that cyclic locals have been reclaimed after both success and early
error returns, before subsequent work.

The inactive-slot test adds a test-only assertion call before each match's tag
read and retains the unmodified LLVM separately. It checks both slot directions:
the active reference owns a non-null payload; the inactive slot is null with
its ownership flag clear. A mutation marking the inactive Ok error slot as
owning is rejected by this oracle at O0 and O2. This instrumentation is recorded
in evidence and does not ship in the compiler or runtime.

Primary strategies were inspected from
[Rust's Result tests](https://github.com/rust-lang/rust/blob/9377e0af5267119df43e9d6221a6d839743fa581/library/coretests/tests/result.rs)
and [Gleam's Result tests](https://github.com/gleam-lang/stdlib/blob/cd425d4cdfc9e2d8874920fa09cff0735bb7d246/test/gleam/result_test.gleam).
The fatal-callback-after-error adversary adapts Rust's collect short-circuit
strategy; type-changing propagation and recovery follow Gleam's try cases.
Only scenarios were adapted; peer test implementations were not copied.

## Verification and limits

The final original 26 tests plus 22 independent tests run sequentially in:
native; ASan/UBSan; 1 MiB bounded heap with budgets 1, 32 and 1024; and
ASan/UBSan with the same bounded heap and budget 1. LeakSanitizer follows the
repository policy and is disabled; exact object/frame/debt assertions remain
enabled. Evidence retains individual sources, LLVM, executable/runtime hashes,
tool hashes, input snapshots, subprocess outputs and outcomes.

The final frontend self-hosts with byte-identical stage 2/3 LLVM. Eight additional
ordinary sources (five existing codegen fixtures, feature-name comparisons,
scalar parallel calls and parallelEntry), plus the original suite's three
ordinary sources, have byte-identical core/optional LLVM. Five targeted cleanup
cases also run with compiler stack-owner selection and the production
stack-frame header at budgets 1, 32 and 1024; larger budgets exercise emitted
stack owners, while budget 1 exercises the supported fallback.

Only the Result helper, its guarded build adapter, independent tests and this
report change. No closure/domain checks, ordinary core/runtime, global build,
catalogue, harness or launcher files change. New CI catalogue/launcher wiring,
CI parser changes, Windows, hosted coverage and performance gates, actual
serialized worker transport, and long network soaks remain with their owners.
No full-project, cross-platform or overall overnight completion is claimed.

Remote evidence: `/home/user/minyar-overnight/errors-review`; the final six-profile
matrix is under its `final/` directory. The handoff index records final source
and binary hashes and a source-only bundle excluding the reviewed base.

