# Language conformance index

This tree is the executable index for `docs/language.md`. Every program has an
exact `expected.stdout` and runs at both O0 and O2 through `make
check-conformance`. Rejection wording is indexed separately by
`tests/diagnostics.py`, which checks complete stderr byte for byte.

| Specification requirement | Primary conformance evidence | Negative and boundary evidence |
| --- | --- | --- |
| Bindings, lexical blocks, assignment, and shadowing | `bindings-and-scope/program.min` | `tests/adversarial.py`, `tests/readonly-parameters.py` |
| 64-bit arithmetic, comparisons, Boolean-only conditions, and evaluation | `numbers-and-comparisons/program.min` | `tests/errors/integer-too-large.min`, `tests/runtime/integer-overflow.min`, `tests/runtime/divide-by-zero.min`, `tests/adversarial.py` |
| Unicode Text, Character, indexing, slicing, conversions, and joining | `text-and-lists/program.min` | `tests/regressions.py`, `tests/runtime/text-slice-out-of-bounds.min`, `tests/integer-text-cache.py` |
| List literals, inference, aliases, append, replacement, and bounds | `text-and-lists/program.min` | `tests/runtime/lists.min`, `tests/runtime/list-out-of-bounds.min`, `tests/ownership.py` |
| Automatic lifetime, aliases, recursive acyclic values, fresh-List recursive construction, and cycle rejection | `memory-lifetime/program.min` | `tests/recursive-data.py`, `tests/production-memory.py`, `tests/ownership-mutation.py` |
| Required typed immutable record fields and nested records | `records/program.min` | `tests/errors/record-*.min`, `tests/scalar-record-storage.py` |
| Top-level order, functions, returns, branches, loops, and explicit main | `programs-and-entry-points/program.min`, `explicit-main/program.min` | `tests/errors/top-level-*.min`, `tests/errors/mixed-entry-points.min`, `tests/regressions.py` |
| Arguments, file reads/writes, invalid UTF-8, and I/O failures | `explicit-main/program.min` | `tests/regressions.py` |
| Modules, visibility, identity, paths, packages, and import cycles | `tests/modules/` | `tests/run-module-tests.sh`, `tests/incremental-modules.py` |
| Statement termination, continuations, comments, and literal lexing | `programs-and-entry-points/program.min` | `tests/errors/statements-on-one-line.min`, `tests/fuzz-regressions/`, `tests/diagnostics.py` |

When the language specification gains a requirement, update this table and add
or identify its executable evidence in the same change.
