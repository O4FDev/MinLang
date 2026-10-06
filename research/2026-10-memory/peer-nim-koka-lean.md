# Dedicated Nim, Koka and Lean ownership review

The selected source review identifies ten useful original Minyar adaptations and several boundaries where a direct port would change semantics. All ten adaptations subsequently passed together at O0/O2 in the integrated focused gate; three followups also passed at both levels. No Minyar production change was needed for these coverage additions. No upstream peer suite was executed by this lane.

The [JSON manifest](peer-nim-koka-lean.json) records source URLs, immutable commits, SHA256, reading status, individual unit dispositions and completed validation. The [unit tables](peer-nim-koka-lean-units.md) render every disposition. The [discovery inventory](peer-nim-koka-lean-inventory.json) records listed but unreviewed candidates separately. Source retrieval is reproducible from the raw GitHub URL formed with each manifest repository, commit and path; source bytes are cached only under `build/peer-research/sources/<language>/<path>`. Three license hashes and all 106 cached file hashes were checked against the manifest. Maintained tests are original adaptations, not vendored upstream code.

## Selection and coverage

These older immutable versions are baseline snapshots. They are not described as the latest releases. Current-version documentation and source observations are separately recorded in [literature-peers.md](literature-peers.md).

| Peer snapshot | Selection read | Individual recorded units | Outside this selection |
| --- | --- | ---: | --- |
| Nim 2.2.4, `f7145dd26efeeeb6eeae6fff649db244d81b212d` | 18 named files in `tests/arc`: aliasing, moves, cursors, control flow and ORC cycles; 2917 lines | 94 | Directory lists 109 files; 91 unreviewed. ORC tests are inside `tests/arc`; `tests/orc` does not exist at this commit |
| Koka 3.2.2, `39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3` | Entire immediate `test/parc` directory: 38 programs, 23 companion core goldens and config; 1620 total lines | 93 | No recursive language-wide suite review. Companion output review concerns relevant ownership core, not import boilerplate; config excludes parc19 |
| Lean 4.23.0, `50aaf682e9b74ab92880292a25c68baa1cc81c87` | All 26 candidates of declared basename filter: 12 initial compiler/IR/runtime files and 14 additional theorem/interpreter/playground sources; 931 lines | 234 | Complete recursive repository tree was available without truncation; all declared filter candidates reviewed. This filename filter is not exhaustive memory-test discovery |

There are 421 recorded units, including helpers, branch contracts, line-identified assertions/theorems, harness directives and companion goldens. They are not 421 executed test cases. Several units intentionally map to one adaptation. Some source files are suites of distinct historical regressions, so file-level success alone would not establish their coverage.

| Disposition | Nim | Koka | Lean |
| --- | ---: | ---: | ---: |
| Ported semantic subset | 10 | 5 | 5 |
| Covered by identified existing contract/test | 10 | 17 | 4 |
| Reviewed, adaptation still pending | 11 | 11 | 18 |
| Incompatible direct contract | 63 | 34 | 204 |
| Exact compiler IR incompatible | 0 | 23 | 0 |
| Harness-only / excluded upstream | 0 | 3 | 3 |

“Incompatible direct contract” means that copying the test as written would require an unavailable feature, a different representation or a changed ownership/observability guarantee. It does not mean no related program can be written. A manually implemented substitute needs an explicit semantic mapping and often stops exercising the original optimization or memory bug.

## Completed adaptations

New test file: [peer-memory-nim-koka-lean.py](../../tests/peer-memory-nim-koka-lean.py). It uses the maintained compiler test helper, which checks execution at O0 and O2. The ten tests cover:

1. Nim constructor fields sharing one local: an earlier projected Text stays valid while a later constructor argument mutates its container. The mutation is an explicit strengthening of the source's later read.
2. Nim conditional projection retained across loop iterations: replacing temporary rows must not invalidate a previously saved Text.
3. Nim pop shape: a result is protected before its source slot is overwritten, including an assignment from that same slot. The actual Nim pop/resize API is not claimed.
4. Nim part-to-whole assignment: a child survives root replacement with one dynamic index evaluation; an old-root alias remains valid.
5. Nim two effectful assignment indices: destination index runs before source index, and a separately saved overwritten Item remains valid. Custom value-copy/destructor hooks are not mapped.
6. Nim old-scope protection: save current scope, replace the context's owner with its parent, then consume saved symbols. An acyclic `List<Scope>` encodes termination without cursor syntax.
7. Koka nested selection: both-nonempty, left-only, right-only and both-empty cases preserve selected managed child/whole-input results.
8. Koka boxed pair rotation shape: fresh List construction preserves output values and input aliases. Exact generic Cons/boxing allocation reuse is not claimed.
9. Lean join-point ownership shape: a managed Payload replaces Nat to expose lifetimes through a returned duplicate pair and short-circuit calls. This does not reproduce Lean's Nat tagging or exact RC trace.
10. Lean reuse regression: explicit tag records encode the tested Expr constructors, preserving shared recursive operands and output. It does not establish identical ADT layout or record reuse.

Initial eight-test evidence is `build/peer-memory-6nvnqdfp/results.json` with `native.log`, tool/artifact hashes and limitations. The two later tests have a completed execution transcript and supplemental manifest record; their raw output was not separately saved. The [integrated focused gate](profiling-integrated-focused.json) subsequently completed the full ten-test file and all three followups at O0/O2, with stable compiler/runtime hashes and [raw log](profiling-integrated-focused.log). Sanitizer profile, alternate compiler, exact heap accounting and peer-native execution remain separate pending obligations.

The initial extended Lean reassociation input failed with call-depth exhaustion at both optimization levels. Examination showed that `add(Val 1, Add(Val 3,x))` makes the copied partial algorithm repeatedly swap the two Val heads. This was an adapter/input error, not a Minyar memory defect. The extra case was changed to a terminating multiply-headed left operand; the original upstream main input was retained. The failed attempt is recorded in `port_trial_notes`. Initially passing semantic tests are described as coverage, not as fabricated red-green production fixes.

## Concrete hazards and rejected shortcuts

Nim's linked-node rewrite in `topt_cursor2` saves the next node before replacing an edge that can remove its last owner. Its `topt_refcursors` source includes an explicit unsoundness comment, while the executed source only traverses nil. These are evidence of delicate inference and weak test input, not proof of a current Nim defect. A Minyar borrow optimization must preserve saved owners across mutation and effects; a nil-only traversal is an inadequate adversary.

Nim part-to-whole assignment cannot move a child by accessing its parent storage after the parent is replaced. The dynamic-index adaptation specifically exercises this ordering. Conditional saved values across iterations and saved old scopes similarly need an owning local when the old container can disappear.

Koka's `.kk.out` files here are compiler core goldens because config requests `--showfcore`; they are not expected stdout. `parc21` tests evaluation order despite a borrowed argument. `parc19` is excluded by the pinned config and its historical golden uses older core names. Treating every cached golden as an executing passing program would overstate evidence.

Koka's closure capture, algebraic effects, multi-shot handlers, constructor-specialized reuse and arbitrary-precision integer RC cannot be certified by a scalar or loop-shaped Minyar result. Several small patterns can be adapted, but their exact memory oracle is lost. The 100-million counter and twelve-queens handler benchmark were read and classified, not executed.

Lean's arrays use persistent/value behavior: branching pop/push results can remain independent, while Minyar Lists share mutation. A direct alias plus `.add` port would change the result. Many array guard assertions also depend on higher-order APIs, proof-indexed access, Option, persistent arrays or interpreter commands. Explicit loops might reproduce selected values, but cannot stand in for the original ownership/layout test without qualification.

The additional fourteen Lean files were retrieved from the same immutable commit and fully read, adding545lines/119individual units. Many are theorem simplification, dependent literal matching or proof-indexed set/equality regressions, so treating their filenames as runtime memory tests would overstate coverage. `Array.get!`/default accesses may return a default out of bounds, unlike Minyar's termination contract; Subarray take/drop clamp range lengths and retain persistent backing, unlike a hypothetical copied List substitute. Historical playground sources were not asserted to execute in the pinned modern harness. The unsafe `array_map` playground saves a projected element, clears its array slot, then calls a mapper: the related owner-preservation obligation is covered by existing managed projection/overwrite adaptations, while exact generic unsafe representation and higher-order reuse remain incompatible. The remaining scalar early-return/break and fresh-map value subsets are explicitly pending, not counted as new memory fixes.

All cyclic ORC examples remain incompatible with Minyar's acyclic mutation contract. Replacing them with trees would remove the collector requirement. User finalizer prints, exception unwinding, threads and unowned pointer/cursor edges also need their own interfaces; the current port does not introduce new syntax to accommodate them.

## Next focused work

The ten-test file and three followups have completed integrated native validation. Next reserve sanitizer modes and a small eager/K1/K32 matrix with exact end-of-program ownership accounting. Preserve generated source and LLVM in evidence if making stronger preservation claims. Run upstream selected programs only where the pinned toolchain and suite harness are available; compiler goldens must use their actual harness.

The first three followups cover early return after duplicate insertion into two owner Lists, projected child plus transferred whole parent and Text separator joining under deferred owners. Remaining useful adaptations include generic pair/unzip already assigned to the peer lane and faithful persistent-array value construction where useful. The manifest marks these pending instead of implying completion. Do not expand the suite merely to inflate test counts; use a concrete missing ownership obligation or found defect to choose each addition.

The first three are now validated separately in [peer-memory-nim-koka-followups.py](../../tests/peer-memory-nim-koka-followups.py), with [validation status](peer-nim-koka-followups.json). They map four already reviewed upstream units, now marked as ported semantic subsets. All three passed O0/O2 through the integrated maintained gate. These tests preserve the original tested ten and are included in portable CI integration. They claim managed ownership shapes and value results, with explicit differences from Nim move IR, Koka Cons reuse and closure capture.
