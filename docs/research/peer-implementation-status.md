# Peer testing implementation status

The reviewed implementation queue has been integrated. **The exhaustive source
audit is still in progress.** The live inventories, decisions, resolutions and
completion contract are under [exhaustive](exhaustive/README.md). Inventory files,
upstream mapping keys and executable local methods are different measures.

## Round-four implementation checkpoint: 2026-10-05

The catalogue contains 541 methods across four executable peer suites:

| Suite | Methods | Selected ownership methods |
| --- | ---: | ---: |
| Common peer regressions | 88 | 29 |
| C++, Java and JavaScript | 349 | 13 |
| Rust, Go and Zig | 50 | 35 |
| Python, Swift, Ruby and Lua | 54 | 16 |

All 5,882 previously outstanding implementation decisions were resolved, bringing
`implementations.jsonl` to 20,922 exact upstream keys in round three. The next
408 reviewed and validated mappings bring the round-four total to 21,330. Some keys describe finite
domain cells or equivalent source assertions; they do not imply 21,330 new test
methods. Further source review can add accepted cases after this checkpoint.
The older C++/Java/JavaScript handoff received an independent review of all 4,779
keys. Review reconciled 35 stale rationale fields without changing source keys,
hashes or spans, and strengthened 13 newline-boundary rejection oracles.
All 1,085 new round-three mappings and all 408 round-four mappings also received
independent source and implementation reviews. These strengthened three helper
return oracles, a pre-failure trace, the 5,000-field compile-and-link case, and
the exact Lua modulo-zero input; the corrected selections passed their gates.

The accepted tests exposed and now exercise these compiler/runtime corrections:

- Complete final statements are accepted at EOF; incomplete expressions still fail.
- Declaration names and duplicate function parameters are checked explicitly;
  binary-operator and unknown-function diagnostics identify their source locations.
  The following deferred-case review found and fixed doubled punctuation tokens
  using their second column; eight new golden cases assert the first column.
- Indexed assignment through a record's List field preserves receiver/index/value
  evaluation order and ownership. Literal brackets cannot confuse its lookahead.
- Runtime List growth checks its size bound before signed multiplication.
- The sanitized compiler is built from self-hosted LLVM containing call-depth
  guards. Deep valid unary input must either return a controlled depth error or
  compile and execute correctly; an ASan crash does not pass.

## Maintained checks and evidence

All four suites participate in native O0/O2, extended O0/O2/O3/Os and ASan/UBSan
O0/O2 Make gates. Compile-only cases declare frontend coverage. Explicit campaign
configuration decorators distinguish O2 allocation campaigns and harness-only
controls. The manifest checks every executable method and matches the ownership
Make selection exactly. It rejects eight controlled invalid catalogues. The host
source catalogue covers 117 files and rejects eleven invalid controls.

Peer invocations persist outcome, tool/source hashes, observed configurations,
selected output references, skipped cases, omitted methods and partial domains
under `build/peer-results/`. A passing selection does not imply full suite or
platform coverage. Failure workspaces retain strict stdout/stderr/status evidence,
timeout information and guarded replay, including explicit environment additions
and removals. Thirteen evidence-harness controls validate this reporting.

Additional adopted methodologies include:

- Allocation/resize ordinal and byte-budget fault campaigns, forced-moving resize,
  exact baseline trace prefixes, and independent boundary controls.
- Five generated LLVM verifier/FileCheck fixtures at O0/O2, with five negative
  controls including three distinct malformed SSA dominance patterns.
- Same/distinct List aliases across branch orders, loops and module boundaries,
  linked as O0/O2 objects and O2 full-program LTO.
- Integer and Text List growth with retained aliases across five allocator
  profiles, checking every prior element after each of 257 appends. Bounded/lazy
  16KiB runs produced the same exact 127-element successful prefix before controlled
  exhaustion under native and ASan/UBSan execution.
- Expected-output variant selection with explicit endian/size/system precedence,
  chosen path/hash evidence and wrong-variant/missing-oracle negative controls.
- Stateful List models, original Unicode/scalar vectors, argument permutations,
  strict UTF-8 ingress, module cycles, and bounded reproducer reduction.

The individual round-three implementation batches passed their declared focused
native and sanitizer checks. Selected normal-exit workloads also passed exact
ownership accounting. Compiler diagnostic goldens, core regressions, conformance,
self-hosted fixed points, native/sanitized depth checks and incremental-module
integration passed. Source/handoff records identify each batch's evidence; this is
not a claim that every older log used an identical final compiler binary.

A fresh isolated Linux aarch64 snapshot using clang 18 passed all 19 Unicode
filename vectors and the buffered/large `/dev/full` failure cases at O0/O2/O3/Os
and self-hosted compiler/runtime ASan/UBSan O0/O2, with no exclusions in those
selections. The nine original non-Apple guards remain on macOS; the matching keys
are resolved by actual Linux evidence. Snapshot hashes, image identity and reports
are retained under `build/peer-linux-round3/`. The [Linux checkpoint receipt](exhaustive/linux-round3-validation.json) now records
passing coverage for all 530 optimizer declarations, 529 sanitizer declarations
(the separate LTO pilot is optimizer-only), and all 84 ownership declarations.
This combines complete suite runs with focused corrections, preserving the initial
failures. A clean build exposed missing public/module driver prerequisites, now
included in every peer gate; the Linux write-failure C fixture also needed its GNU
feature macro before system headers. The [round-four Linux receipt](exhaustive/linux-round4-validation.json) extends
this to all 541 optimizer, 540 sanitizer and 93 ownership declarations, including
the subsequent source additions and oracle corrections. Retained C++/Java/JavaScript
methods were compared by AST; all three changed methods were executed again.
The later tokenizer correction independently passed all 27 diagnostic goldens,
23 core regressions, seven conformance programs and the compiler fixed point on
macOS and Linux, including sanitized diagnostics. Round-five additions remain
outside this frozen checkpoint.

CI has separate per-suite optimization and sanitizer jobs, plus an ownership,
allocation and LLVM contract lane. The isolated Linux correctness runner now
copies the audit documents required by the maintained peer gates. No remote CI
run or Windows execution is claimed here.

## Remaining work and limits

At this checkpoint 571,545 inventoried candidate files remain pending, including
support/data/production files that have not yet been classified. Nine languages
have unfinished source discovery and case enumeration. Lua's recorded source
review is complete, but 42 Lua applicability decisions remain deferred. Across
all languages, 3,963 deferred decisions are still open. The checker now blocks
completion for every deferred decision, even if its implementation flag is false,
and for generated cohorts lacking individual ledger references. Acquiring or
hashing a file never counts as reading its tests.
The comprehensive completion gate must still fail; implementation queue completion
alone is insufficient. Subsequent batches must update the live ledgers and gates.

The broader `make check` previously stopped at the self-compilation instruction
ceiling on this macOS host: approximately 166 million versus a 75 million limit.
The unchanged HEAD compiler also exceeded that limit with the same flags and
runtime; this does not support attributing the failure to the EOF correction.
The threshold remains unchanged. Evidence is in `build/peer-budget-comparison.json`
and `build/peer-full-check.log`; relevant integration targets passed separately.
A successful local test does not certify every upstream configuration or absolute
correctness. Generated-domain judgments distinguish a read generator and finite
checked-in cases from all possible runtime executions.
