# Indexed Unicode Text after consuming join

Selected raw results, source diffs and hashes survive `make clean` in the
[durable runtime index](evidence/runtime/index.json); original acquisition paths
remain recorded there.

4 October 2026. A semantic regression was reproduced before any production
edit, independently reviewed, fixed with a representation-invariant check and
validated on generated Minyar as well as direct runtime calls. This is a
correctness repair, not a new memory-management algorithm or a performance claim.

## Defect and invariant

An owning Text can have a known character count and a non-null UTF-8 index after
`.length`, character access or slicing builds its lazy index. The consuming join
reuses a uniquely owned left header, discards that old index and previously kept
the sum when both operands had known counts. Subsequent character access saw a
known count with no index and followed the ASCII byte path.

The first red case builds `é🙂`, indexes it, consumes it into `é🙂xy`, and reads
character zero. Expected U+00E9; actual U+00C3. The joined bytes and summed
character length are numerically correct, so checking only equality or length
does not detect this defect. A slice can also use wrong byte boundaries before
any later indexing repairs the state.

The runtime representation invariant is: a known character count with no offset
index certifies ASCII. Unknown text uses the negative count sentinel until lazy
UTF-8 validation/index construction. The fix preserves a known count only when
both original character counts equal their saved original byte lengths. Those
operands are ASCII; the result count is the joined byte length. Otherwise it
sets the negative sentinel, so Unicode gets a fresh lazy index when needed.
Saved byte lengths also make the condition correct for a self RHS after the
left header's byte length has changed. The uniqueness condition and allocation
policy are unchanged.

## Red evidence and review

- Direct original runtime: [run-8o4rlalr/results.json](evidence/runtime/results/unicode-native-red.json).
  System/K32/O2 compiled successfully, then aborted with expected U+00E9 versus
  observed U+00C3. Exact original runtime, fixture hashes and commands are saved.
- Generated original/candidate differential:
  [run-o44vcd_o/results.json](evidence/runtime/results/unicode-generated-red-green.json).
  Ordinary Minyar syntax emits eight consuming calls. The original program
  exits successfully with incorrect output; the isolated candidate produces the
  exact expected output. Raw output hex preserves malformed output bytes without
  a capture decoder hiding the failure.
- Independent reviewer:
  `build/peer-memory-unicode-independent-tv6xn_4n/results.json`.
  System/K1/O2 original fails an independent slice-first oracle; candidate
  passes orientation/alias/view/self/ASCII, identity, 127/128/130 breadcrumb and
  final object/byte/allocation checks. Unknown malformed UTF-8 traps identically
  before/after. An initial fixture helper-name collision is recorded separately
  from the runtime red result.

The production source remained frozen during the broad integration gate.
External snapshot checks preceded the source edit. The repaired
`runtime/minyar_runtime.c` SHA256 is
`db41660ae11fca6957654f150213dd39ec801570629a633a1bcb09f9670ff7db`.

## Permanent focused regression and final result

The original `tests/memory-research-text-join-index.c` matrix has seventeen semantic cases: Unicode
left/right/both, known empty RHS, self join, exact-capacity realloc and spare
capacity, unknown-count controls, ASCII, live alias, flattened view, borrowed
join, slice before length, and 130/260-character accented/non-BMP breadcrumb
boundaries. It checks every expected scalar and byte, slicing, exact header
reuse/fallback, alias/root preservation and complete object/data recovery.
`--invalid-utf8` checks that unknown malformed bytes still fail when indexed.

The generated fixture and independent `.stdout` oracle cover the same ordinary
language transitions without ownership syntax. The full command is:

```sh
python3 tests/memory-research-text-join-index.py --language
```

Final evidence: [run-9mfrbcfx/results.json](evidence/runtime/results/unicode-repair-matrix.json).
All 107 recorded commands/checks pass: eager K32 and system/fixed/lazy K1/K32,
each at O0/O2 and ASan+UBSan, giving 21 configurations. Each runs seventeen C
semantic cases, one expected malformed-UTF-8 trap and the generated program.
The runner copies and hashes its compiler artifact and runtime, preserves
failures/timeouts, and annotates generated LLVM definitions with
`sanitize_address` using the existing test helper. UBSan instruments the C
runtime; this does not imply every generated arithmetic operation has UBSan
checks. LeakSanitizer is disabled (`detect_leaks=0`), matching the platform's
existing sanitizer setup; explicit recovery checks complement that exclusion.

The bounded-RC top comment was corrected after this final matrix snapshot;
the report retains its old raw hash. Independent token fingerprint review
confirms that subsequent change is comment-only. No functional bounded-RC
change is inferred from that provenance difference.

After the separately measured ASCII copy-path change, the maintained fixture
adds an eighteenth borrowed-known-ASCII case and asserts the certificate before
queries. The final formatted runtime passed the exact `--language` matrix at
[run-zxq8d1m_/results.json](evidence/runtime/results/final-text-matrix.json): 107 checks,
21 C configurations, 21 generated executions and 21 expected UTF-8 traps. The
runner derives this summary from observed coverage and asserts the requested
matrix. The preceding `run-_gj9t242` has 64 C-only checks because its invocation
omitted `--language`; an initial progress claim was corrected after reading that
saved JSON. The separate ASCII report retains that correction and timing controls.

## Limits and maintenance

No claim is made about every Unicode string, foreign-created invalid Text, a
mechanized C proof or whole-program leak freedom. The independent UTF-8 values,
stride boundaries, alias controls and malformed-byte trap test the repaired
invariant rather than only its implementation condition. ASCII keeps its known
count path; Unicode must rebuild indexes after mutation. Timings have not been
collected for the repair under current host load.

A small portable default regression can use the system O2 C fixture and the
generated source at O0/O2. The wider profile/sanitizer matrix remains an explicit
research runner. The integration gate completed before this production repair;
its otherwise passing runtime assertions did not cover this sequence. Parent
orchestration records that gate's unrelated cold-bootstrap timeout separately.
