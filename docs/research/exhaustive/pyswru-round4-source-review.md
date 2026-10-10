# Python, Swift and Ruby source review, round 4

This bounded batch closes ten previously pending file bodies: one Python file,
four Swift files and five Ruby files. Two already-reviewed Ruby shared helpers
were also re-read to trace wrapper dispatch. All twelve snapshots were acquired
from their official pinned repositories and verified against inventory SHA-256
values. The per-case record is `pyswru-round4-decisions.jsonl`; identical decisions
were added to the owned language ledgers. No repository discovery or exhaustive
completion is claimed.

The batch adds 207 decisions: Python 108, Swift 15 and Ruby 84. Twelve accepted
keys map to three original Minyar methods. `pyswru-implementation-round4.jsonl`
contains only these validated keys. The source snapshot manifest is
`pyswru-round4-source-review.jsonl`.

- Python `Lib/test/test_call.py`: read all 1,187 lines, all test methods, helper
  functions, decorators, call tables, C descriptor subclasses and checkers.
  Adopted exactly the three generated arities 10, 500 and 1,000. The test preserves
  each middle-argument result and additionally prints every parameter as a local
  transport/order control. CPython vectorcall, NULL argument arrays, C ABI flags,
  dynamic descriptor binding, keyword suggestions and recursion-limit policies
  are separately rejected for their concrete absent mechanisms. The five
  inherited calling-convention configurations are explicitly scoped in each
  shared method decision; imports do not establish dependency-body review.
- Swift `statements.swift`: preserve the inclusive parity-filter trace and the
  two ordered optional-payload filtering traces. The ten optional positions are
  represented by explicit Boolean/payload records; absent positions carry poison
  values. This adaptation makes no claim to test Swift optional-pattern syntax.
  `subscripting.swift`, `mandatory_inlining.swift` and `return_from_main.swift`
  were fully read. Custom accessor/generic witness dispatch, closure lifetime
  transformation, property-wrapper partial apply and interpreter uncaught-throw
  crash handling have no equivalent Minyar mechanism. Plain indexing, a named
  helper or `fail` would remove their actual regression triggers.
- Ruby `bootstraptest/test_flow.rb`: read all 601 lines, each direct assertion,
  and every cell of the four Enumerable fixture by four operation domain.
  The asserted nonlocal block/class transfers, exception/ensure replacement and
  dynamic implicit bindings cannot be established by reproducing their traces
  in straight-line Minyar. Every direct assertion and all sixteen generated
  cells have an exact decision.
- Ruby string wrappers: followed `each_char` to both existing shared bodies and
  `end_with` to its shared body and class fixtures. The wrapper selects `to_s`;
  `to_sym` is outside the adopted Text domain. Six suffix cases preserve all
  eight exact source input/output examples through a typed List<Text> helper
  built from scalar length, slice and equality. Literal Boolean oracles are
  cross-checked independently with host `str.endswith`. Eight local controls
  include overlong, absent, supplementary-scalar and embedded-NUL suffixes.
  Coercion hooks, lazy conversion side effects, encoding tags and malformed
  encoding predicates are separately excluded. The wrappers' spec-helper
  dependencies remain explicitly deferred, not implicitly read.

Focused checks passed for all three new methods at native O0/O2/O3/Os and
ASan/UBSan O0/O2, with no selected skips or exclusions. An additional ownership
runtime run checks their normal exits. Evidence paths and per-method metadata
are in `build/peer-pyswru-round4-validation.json` and
`build/peer-pyswru-round4-method-metadata.json`. These focused runs do not claim
completion of the entire maintained suite; manifest integration belongs to the
parent task.

The reviewed `scripts/check-linux.py` snapshot now includes exhaustive docs so
peer ownership's audit/manifest dependencies exist inside the isolated tree.
The dry run passed. Existing snapshots without the required implementation
ledger cannot resume; current source docs add approximately 266 MB to snapshot
content. The script's target list still does not directly run the complete
peer regression/optimization/sanitizer gates; adding source files alone does
not widen those targets.
