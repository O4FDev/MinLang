# WS2 G15 implementation handoff — 2026-10-12

Branch: `ws2/checked-arithmetic`, based on
`bf9c0e9bb6ced1f40d8d7c51bedca769b05909c0`.
Implementation: `5e77925394807d2531c2a52330b2d436890286c8`.
Catalogue/Linux wiring: `e90edfd487b682a65b7dbdbda1696af58ab6bddd`.
No push, merge, owning-project edits, or claim of a closed/merged gap.
Fresh independent review belongs to the parent; no children were created.

## Implemented behavior

`errors.checkedAdd`, `errors.checkedSubtract`, and `errors.checkedMultiply`
return the existing `errors.IntegerResult` through errors-owned factories.
Overflow uses new code 13, native code 0, and an operation-specific message.
Parent approved this namespace/code and G14 was notified to reserve code 14.
Private scalar `native "integer_overflow"` helpers validate two Integer
parameters and a Boolean return, then extract the signed LLVM overflow flag.
Compiler lowering does not construct another module's private records.
Ordinary trapping arithmetic, wrapping helpers, and failed extraction semantics
remain covered by execution tests.

The exact neo-db `g15_overflow_untrappable.min` is retained as
`tests/fixtures/g15-overflow-trap.min` (SHA-256
`94178c0a80620f254e56bc644f7d2eb6126b77020c87e32c98805e95562c1f04`).
The adapted recovery fixture returns success for scale(18), failure for
scale(19), then executes scale(2) and prints `still alive`.

## Test-first and executed validation

The recovery test failed on unchanged bf9c0e9 before implementation:
`module 'errors' has no function named 'checkedMultiply'`.
The first candidate run exposed an incorrect new test diagnostic expectation;
the actual existing wrong-type diagnostic was preserved and the assertion
corrected. Both failure workspaces and outputs are retained.

Boat Linux x86_64, Ubuntu Clang 18.1.3:

- 9 checked-result tests, including 891 operations over 297 boundary/random
  pairs against Python unbounded integers, operand evaluation order, private
  fields/types, failed extraction, native signatures, IR and wrapping behavior.
- 3 current frontend integration tests: module Result return, callback capture
  retaining a Result, typed Result match/try propagation. Callback/Result tests
  execute the existing exact ownership/cleanup harness.
- 6 existing checked-arithmetic and 8 existing error-value tests.
- All native execution cases run at O0 and O2. The 9+3+6 arithmetic/frontend
  tests also pass with ASan/UBSan compilers and linked programs.
- Core, module, callback and Result stage2/stage3 LLVM fixed points match.
  Sanitized core self-compilation also matches the ordinary fixed point.
- All four ordinary frontends and the 26 native tests were rebuilt/repeated
  under default ThinLTO after the initial non-LTO baseline/candidate controls.
- LLVM `opt -passes=verify` accepted the emitted G15 IR.

Exact commands and outputs are in the retained logs. Principal Make targets:

```sh
make LIMITED='bash scripts/with-limits.sh' SANITIZER_LIMITED='bash scripts/with-sanitizer-limits.sh' \
  build/compiler-stage3.ll build/module-compiler-stage3.ll \
  build/closure-compiler-stage3.ll build/errors-compiler-stage3.ll \
  check-checked-results check-checked-results-frontends \
  check-checked-arithmetic check-errors-values
make LIMITED='bash scripts/with-limits.sh' SANITIZER_LIMITED='bash scripts/with-sanitizer-limits.sh' COMPILER_LTO_FLAGS= \
  check-checked-results-sanitize check-checked-results-frontends-sanitize \
  check-checked-arithmetic-sanitize check-sanitized-fixed-point
```

Small native macOS arm64 control: the three actual emitted flag helper bodies
(symbols renamed only) passed 507 endpoint comparisons against C `__int128`
at O0, O2 and ASan/UBSan with Apple Clang 17. This does not qualify the full
macOS Result/compiler frontend stack. Windows execution remains outstanding.

Local wiring checks passed after adding both suite catalogue rows:
`python3 tests/suite-catalogue.py` (508 sources, 24 negative controls),
`python3 scripts/check-linux.py --dry-run`, and Make database assertions.
Portable reaches both native targets, sanitizer reaches both sanitizer
targets, and the Linux runner explicitly lists all four. The full Linux/portable
runner was not executed by these static wiring checks.

## Evidence and sandbox lifecycle

Own default sandbox `bx_3k28w84c`, `--no-env --ttl 5400`, multiplier 1,
distinct source checkout `/home/user/ws2-checked-arithmetic`.
Pre-creation limits: subscription remaining 359803 seconds, purchased 0,
canStart true. No purchases, add-ons, upgrades, or other hosts operated.
Final usage: 851 included seconds. Stop `stop_7b11865697fbdafe` completed
at `2026-10-12T14:18:49.966Z`; sandbox is stopped.

Jobs: red `cmd_zb1jxdd6pryr`/18514 (expected exit 1), first candidate
`cmd_futsqahewmbu`/20242 (test diagnostic failure), corrected native
`cmd_u18jkvid5umb`/20991 (exit 0), sanitizer `cmd_dxpslw4bjbxe`/21550
(exit 0), default ThinLTO/performance `cmd_xcfsqdx4ifil`/23969 (exit 0).

Local evidence root: `build/ws2-evidence/` in this worktree.
`boat-evidence.tar.gz` SHA-256:
`36ef90e725737a012b57b656c234952cfab483810547c3dc8226d0f228f18be3`.
Unpacked under `build/ws2-evidence/boat/`. It includes exact source archives,
binary/input snapshots, successful and failed manifests, logs, LLVM/assembly,
and raw paired timing samples. All retained test-file hashes verified locally.
Lifecycle, catalogue, Linux plan, Make wiring and macOS control evidence are
beside the archive.

Default ThinLTO compiler SHA-256:
`535a766eb3ffa8a4cd3d88503a76ea169d243f439e1bcdf4200ee0ebec836f9d`.
Baseline ThinLTO compiler:
`f4f589328d1b53b8cf92c9aa8b0da1f5168bca1b4e8cf9198ff1b542cc59212b`.
Sanitized core compiler:
`7828d0105d9d29fb948a86d32e4ab26da6c81d40b730d72a83532ab181ac1923`.
All other artifact identities are in `*-artifacts.sha256` and test manifests.

## Remaining review and qualification

Parent owns the pinned foundation baseline dependency stack
`193c8af` + `47a1159` + `39a8e72`, with fresh review pending at handoff.
It was not cherry-picked before parent release. Integration must apply the
reviewed stack before this arithmetic change: current-core reconstruction of
the frozen comparator would otherwise drift. The exact frozen digest remains
`a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf`;
this branch does not alter the builder or silently redefine that comparator.

Optimized x86_64 checkedMultiply shares one `imulq` between overflow detection
and the success value. Retained AArch64 cross-assembly emits `mul`/`smulh` for
the flag and repeats `mul` on success. This limitation is accepted for correctness
review, subject to the original performance gates; no universal commoning claim.

100 alternating, warmed self-compile pairs on one pinned CPU used the same
current source and byte-identical output. Median CPU candidate/baseline 0.98525;
paired geometric mean 0.98249, approximate 95% interval [0.96601, 0.99926].
Wall median ratio 0.99535, but paired interval [0.95062, 1.09236]. All adverse
samples are retained. This diagnostic does not prove the public <=1% gate.
Compiler/Minyarcraft/Atacama/JSON/neo-db statement benchmarks, Windows/full
platform qualification, independent review, Phase1 integration and actual
merge confirmation remain required. G13 >=2x and other WS2 goals are unproved.

The parent held-state report and unresolved G14 cleanup/propagation, G13
default-profile/collector, syscall/thread-pointer and WS1 TLS findings were read
and preserved. Owner release revoked the implementation/Boat hold only; it did
not waive those findings or qualification thresholds. This implementation edits
arithmetic APIs/codegen plus the requested catalogue/CI wiring, with no call-depth,
RC, syscall or other-worktree edits.
