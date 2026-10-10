# Original peer-informed ownership regressions

Thirteen original Minyar programs add coverage using the existing
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
| Wide returned record | Round 7 P1 | All eight distinct fields survive a reordered effectful factory/echo; trace87654321 records initializer order, and shared mutation111 differs from saved scalar11 after container replacement and eight allocations. |
| Exact Text equality after NUL | Round 8 P1 | Sizes 0–17 and 31/32/33 cover every single changed position, unequal prefix lengths and Unicode tails after NUL; byte/scalar lengths and partial slice equality have independent expectations. |
| Scalar loop capture and mutation | Round 8 P2 | Captured 4/7/9 remain distinct from mutated shared slots 104/107/109; continue/break, loop-binding reassignment, allocation effects and untouched fourth slot have separate expected counters. |
| Euclidean remainder composition | Round 9 P1 | Zero, signs, signed boundaries and consecutive Fibonacci values have independent fixed GCD expectations; every divisor is positive and decreases. |
| Extrema scalar snapshots | Round 9 P2 | Signed endpoints, equality and operand order select exact scalar fields; saved results survive shared List writes and removal of both List roots. |

Zig's writable slice views and implicit array value copies remain incompatible;
these programs deliberately assert Minyar's documented copying-slice and shared
List contracts. The decimal order and source-replacement lifetime controls are
original extensions. No upstream source code was copied, no Zig backend was run,
and assertion counts are not counted as separate peer test ports.

Run:

```sh
python3 tests/memory-research-peer-projections.py --matrix
```

The latest complete eight-method matrix passes 48 generated executions: eight methods, O0/O2 links,
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
thirteen methods also participate in the existing shared semantic suite list for
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

The separately [targeted wide-record run](evidence/runtime-peer-projections/run-1a2ft1yr/results.json)
passes only the new method's six executions, with [source-to-test provenance](evidence/runtime-peer-projections/run-1a2ft1yr/provenance.json).
Its 17 sanitized generated definitions all have ASan attributes, and its exact
saved link argv end in O0/O2 in all three runtime configurations. The previous
48 executions were not repeated. No 54-execution complete final-source matrix
is claimed. Existing two-field effect tests and many one-field inference-budget
tests overlap parts of this case; the missing combination was all-eight-field
mapping across return, reordered effects and retained alias replacement. The
expected complete field vectors and effect trace were written before execution;
the unchanged implementation passed, so this remains a coverage addition.

To reproduce only the new case:
`python3 tests/memory-research-peer-projections.py --matrix --test-name test_wide_returned_record_preserves_fields_effect_order_and_retained_alias`.

The two round 8 methods have **separate six-execution matrices**, preserving
[Text equality results](evidence/runtime-peer-projections/run-egbfb2e0/results.json)
and [loop capture results](evidence/runtime-peer-projections/run-d29wceo4/results.json).
This adds 12 executions; it does not rerun the older nine methods or establish
one complete eleven-method matrix. The earlier eight-method/48 and ninth/six
records keep their own exact sources and scopes. Both new matrices check actual
last generated-link flags O0/O2 in all three configurations. Sanitized equality
and loop fixtures annotate 13/13 and 12/12 generated definitions respectively;
C runtime uses O1 ASan+UBSan, generated UBSan is not claimed and LSan is disabled.
All baseline outputs were already correct: these are coverage additions.

[Round 8 preregistration](runtime-peer-round8-preregister.json) and each matrix's
`provenance.json` retain source-to-test mapping and frozen read-only report/ledger
hashes. Source-review proposals remain documentary in their original peer lane;
these methods are original Minyar extensions. The equality expected output has
611 lines, derived from every changed position being different from A or NUL,
plus independent Unicode length/scalar/slice expectations. The loop has eleven
lines: captured 40,709; three visits/positions; one tail effect; rebound sum 2,703;
trace 123; allocation-derived length 9; alias values 104/107/109/13. The alias
survives source replacement, retaining Minyar shared storage semantics.

Two separate oracle calibrations run only native O0/O2:

- [C equality mutant](evidence/runtime-peer-calibrations/run-slxiueks/results.json)
  changes the isolated comparison to `strcmp` while preserving byte-length
  checks. Both executions return successfully but fail the expected Boolean
  oracle first at line 31: a size-three change at position two, after NUL at
  position one. The output says true where false is expected. Its static LLVM
  call-site inventory is preserved separately; it is not dynamic API work.
- [Minyar input-source control](evidence/runtime-peer-calibrations/run-ues9vrfd/results.json)
  changes only the capture expression to read the already-mutated source slot.
  Both executions return 1,050,809 instead of 40,709, while the remaining ten
  lines match. This is an input-source calibration, not a compiler/runtime
  mutation or corruption of saved output.

Both controls keep production sources unchanged and distinguish semantic
rejection from compilation, process or sanitizer failure. They are not counted
as new peer ports, passing production cases or another broad integration gate.

The two round 9 methods likewise have **separate six-execution matrices**:
[Euclidean composition](evidence/runtime-peer-projections/run-2a078047/results.json)
and [extrema snapshots](evidence/runtime-peer-projections/run-ts2r1bcv/results.json).
Only these twelve new executions ran. The previous eleven methods were not
repeated, and no complete thirteen-method matrix is claimed. Each record retains
actual O0/O2 generated link flags across system/K32, fixed/K1 and sanitized
system/K32. The sanitized programs have ASan attributes on 13/13 and 14/14
definitions respectively. Runtime C uses O1 ASan+UBSan; generated UBSan and LSan
are not claimed. Both baseline cases already passed, so these are coverage
additions, with no production change or speed claim.

[Round 9 preregistration](runtime-peer-round9-preregister.json) and the individual
`provenance.json` files preserve the documentary source mapping and hashes. The
Euclidean expectations were derived from zero identities, signed magnitudes,
known factors, consecutive integers and consecutive Fibonacci values; Python
arbitrary-precision GCD and the Fibonacci recurrence independently confirmed the
chosen constants before execution. `abs(INT_MIN)` is deliberately excluded,
and the guarded decreasing positive divisor avoids division overflow. The
second case compares the exact signed endpoints without arithmetic on them.
It prints the mutated shared source slots as 111/222, drops both source roots,
and checks that the saved scalar record still contains the original lower and
upper endpoints. These tests project Minyar contracts; C++ reference identity,
unsigned conversion and `constexpr` behavior are outside their scope.
