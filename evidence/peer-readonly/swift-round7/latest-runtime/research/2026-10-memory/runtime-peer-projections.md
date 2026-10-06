# Original peer-informed ownership regressions

Eight original Minyar programs add coverage using the existing
`CompilerTestCase`, `clang_command`, and generated-LLVM sanitizer helper. They
were written before execution. All were already correct; this is a coverage
addition, not a discovered runtime defect or a production change.

| Projection | Read-only source record | Minyar contract checked |
| --- | --- | --- |
| Shared Bytes and copied slice | Round 2 Z17/R4 | Helper writes affect the source and its alias; writes into `Bytes.slice` affect only the copy. The copy survives replacement of both source roots. |
| Row alias and explicit snapshot | Round 3 Z51/P6 | A plain row binding shares indexed writes; an explicit fresh scalar List preserves earlier values. Both survive outer-position replacement and dropping the original rows. |
| Unused literal effects and order | Round 3 Z39/Z43/P5 | An unused two-call literal still performs both effects. A four-call literal yields ordered values, sum 15, and an independent decimal trace 1234. |
| Effectful iterable and body lifetime | Round 4 R5/R9/R16/P4 | Nonempty and empty List/Bytes/Text producers each run once. Separate call/order counters, exact values/sums, body counts and allocated Text-length sums distinguish evaluation from output equivalence. |
| NaN ordered comparisons and negation | Round 5 P1, N1–N54 | Three NaN operand orientations, all six comparisons, direct/helper Boolean returns, negation and double negation; finite controls and effect order are independent. |
| Source underflow and signed zero | Round 5 P2, L1–L45 | Independently proved decimal neighbors of half the minimum subnormal, both signs, zero exponent spellings and helper returns have exact binary64 bits. |
| Middle-literal effect barrier | Round 6 P1 | Two mandatory prior operands remain ordered before a decisive literal; allocating-helper controls execute event3, while forbidden trailing event9 stays absent. |
| Binary64 halfway arithmetic | Round 6 P2 | At 2^53, +1 rounds to the even endpoint and +2 reaches the next representable value; direct/helper values and exact bits agree with explicit expectations. |

Zig's writable slice views and implicit array value copies remain incompatible;
these programs deliberately assert Minyar's documented copying-slice and shared
List contracts. The decimal order and source-replacement lifetime controls are
original extensions. No upstream source code was copied, no Zig backend was run,
and assertion counts are not counted as separate peer test ports.

Run:

```sh
python3 tests/memory-research-peer-projections.py --matrix
```

The final isolated matrix passes 48 generated executions: eight methods, O0/O2 links,
and system/K32, fixed/K1, or sanitized system/K32 runtime configurations. The
native runtime objects use O2; the sanitized runtime object uses O1 with
ASan/UBSan. Each sanitized generated function definition is checked for the ASan
attribute. Generated UBSan instrumentation is not claimed; LSan is disabled.
There is no timing claim, and this small matrix is not a full integration gate.

Durable [results and exact source snapshots](evidence/runtime-peer-projections/run-l5_218bk/results.json)
and [source-to-test provenance](evidence/runtime-peer-projections/run-l5_218bk/provenance.json)
retain the read-only record hashes, selected upstream spans, excluded contracts,
compiler artifact hash, commands, helper logs, expected output, and actual mode
coverage. The isolated `--matrix` remains an opt-in research command. The default
eight methods also participate in the existing shared semantic suite list for
native and sanitizer discovery; that list addition does not run the stopped
integration lane or establish a final whole-suite pass.

The earlier [three-method, 18-execution matrix](evidence/runtime-peer-projections/run-ki_43p1a/results.json)
and [four-method, 24-execution matrix](evidence/runtime-peer-projections/run-crettoqb/results.json)
remain preserved. Their native configurations linked at O0/O2, but their sanitizer
configuration effectively linked at O1 twice: the isolated runner appended the
runtime sanitizer flags after the helper's requested flags. The prior description
of O0/O2 sanitizer coverage was wrong. The corrected final runner records every
actual link argv, checks the last optimization flag, and requires O0/O2 in all
three configurations. The sanitized runtime C object itself still uses O1.

The [correction record](runtime-peer-optimization-correction.json) also identifies
the immutable round 5 documentary cross-reference to the older 24-execution run;
that source-review ledger remains unchanged. The [bounded runner audit](runtime-optimization-coverage-audit.json)
finds the HUD, final List/Text, ASCII, deferred and API-count generated links
unaffected: their saved argv supply exactly one optimization flag. HUD sanitizer
links intentionally use O1 and are labeled separately. No unaffected matrix was
repeated because of this harness defect.

Existing scalar tests already cover NaN equality, formatting, conversion traps,
random Float normalization, negative zero and overflow. They do not cover this
ordered-comparison/Boolean-negation matrix or the selected half-minimum source
literal neighbors. These are original narrow coverage additions. The 108 NaN
Boolean expectations and 12 signed-bit outputs are assertions within two tests;
they are not 120 peer ports or evidence that every reviewed unit was executed.

The [corrected six-method, 36-execution matrix](evidence/runtime-peer-projections/run-7m86apqr/results.json)
remains unchanged. The current eight-method matrix adds round 6 P1/P2 after a
source comparison against existing short-circuit, scalar and near-2^53 formatting
fixtures. The new cases were authored with independent expectations before their
baseline executions, which already passed. All 120 definitions across the eight
sanitized generated programs have ASan attributes; those same programs link at
both actual O0 and O2. This definition total is not a port or assertion count.
