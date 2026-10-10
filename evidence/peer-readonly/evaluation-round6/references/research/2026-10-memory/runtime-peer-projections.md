# Original peer-informed ownership regressions

Four original Minyar programs add coverage using the existing
`CompilerTestCase`, `clang_command`, and generated-LLVM sanitizer helper. They
were written before execution. All were already correct; this is a coverage
addition, not a discovered runtime defect or a production change.

| Projection | Read-only source record | Minyar contract checked |
| --- | --- | --- |
| Shared Bytes and copied slice | Round 2 Z17/R4 | Helper writes affect the source and its alias; writes into `Bytes.slice` affect only the copy. The copy survives replacement of both source roots. |
| Row alias and explicit snapshot | Round 3 Z51/P6 | A plain row binding shares indexed writes; an explicit fresh scalar List preserves earlier values. Both survive outer-position replacement and dropping the original rows. |
| Unused literal effects and order | Round 3 Z39/Z43/P5 | An unused two-call literal still performs both effects. A four-call literal yields ordered values, sum 15, and an independent decimal trace 1234. |
| Effectful iterable and body lifetime | Round 4 R5/R9/R16/P4 | Nonempty and empty List/Bytes/Text producers each run once. Separate call/order counters, exact values/sums, body counts and allocated Text-length sums distinguish evaluation from output equivalence. |

Zig's writable slice views and implicit array value copies remain incompatible;
these programs deliberately assert Minyar's documented copying-slice and shared
List contracts. The decimal order and source-replacement lifetime controls are
original extensions. No upstream source code was copied, no Zig backend was run,
and assertion counts are not counted as separate peer test ports.

Run:

```sh
python3 tests/memory-research-peer-projections.py --matrix
```

The final expanded isolated matrix passes 24 generated executions: four methods, O0/O2 links,
and system/K32, fixed/K1, or sanitized system/K32 runtime configurations. The
native runtime objects use O2; the sanitized runtime object uses O1 with
ASan/UBSan. Each sanitized generated function definition is checked for the ASan
attribute. Generated UBSan instrumentation is not claimed; LSan is disabled.
There is no timing claim, and this small matrix is not a full integration gate.

Durable [results and exact source snapshots](evidence/runtime-peer-projections/run-crettoqb/results.json)
and [source-to-test provenance](evidence/runtime-peer-projections/run-crettoqb/provenance.json)
retain the read-only record hashes, selected upstream spans, excluded contracts,
compiler artifact hash, commands, helper logs, expected output, and actual mode
coverage. The isolated `--matrix` remains an opt-in research command. The default
four methods also participate in the existing shared semantic suite list for
native and sanitizer discovery; that list addition does not run the stopped
integration lane or establish a final whole-suite pass.

The earlier [three-method, 18-execution matrix](evidence/runtime-peer-projections/run-ki_43p1a/results.json)
remains separately preserved. A first expanded run correctly recorded four
methods/24 executions but retained the stale descriptive word “Three” in its
scope field. The exact final repeat above removes that word; totals are derived
from observed mode records rather than a hard-coded method count.
