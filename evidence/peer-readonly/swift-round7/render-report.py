"""Render the saved documentary ledger as a standalone report; no test execution."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'evidence/peer-readonly/swift-round7'
R=ROOT/'research/2026-10-memory'
d=json.loads((R/'peer-readonly-swift-round7.json').read_text())
sources=json.loads((E/'source-manifest.json').read_text())

def spans(items):
    return ', '.join(f'L{a}–{b}' if a!=b else f'L{a}' for a,b in items)

out=['''# Read-only Swift peer source review — round 7

Five complete previously unreviewed files at **Swift `1ff1cc1170617ab23ab74aa8b741c8daca1903f6`**, **413 raw physical lines**, **38 heterogeneous comparison groups**. Dispositions: **4 adopt pending, 8 adapt pending, 26 incompatible as written, 0 exact units already covered**. All **36 selected `expectEqual` call sites and 35 `CHECK` sites** are individually attributed. Five registered Struct tests share one imported lifetime assertion source site. One narrow original regression proposal remains pending. **Zero ports, test executions, compilations, installations, timings, commits or subagents.**

This is GPT-6.1 Sol high documentary research. Only `research/2026-10-memory/peer-readonly-swift-round7.md/.json` and `evidence/peer-readonly/swift-round7/` were written. Existing dirty work, active core/native cohorts, stopped compiler/literature lanes and central manifests were left to their owners. The campaign earliest completion remains **2026-10-04 06:54:29 UTC**; this source round makes no campaign-completion claim.

## Selection and primary pinned sources

Repository README, architecture, language/ownership/testing and syntax notes, the campaign README, pins/central review ledger, and completed rounds2–6 reports/ledgers/handoffs supplied context. No file named notes/AGENTS.md was found in the repository listing; the user's supplied commit instruction applies, and no commit was made. The prior Swift exclusion set contains the initial four Interpreter files (`string_literal`, `unicode_scalar_literal`, `deinit_recursive_no_overflow`, `arrays`), all25 recursively reviewed statement-directory files/273 grouped scenarios, and round5's `array_of_optional` and `conversions`. Exact path comparison is retained in the [selection checkpoint](../../evidence/peer-readonly/swift-round7/selection-checkpoint.json); overlap is empty. Previously selected Go/Zig round6 files also remain excluded. This selects complete bounded files, not an entire huge directory followed by an arbitrary prefix sample.

| Whole selected source | Raw extent / bytes | SHA-256 |
| --- | --- | --- |''']
for f in d['scope']['selected']:
    out.append(f"| [{f['path']}]({f['url']}) | L1–{f['physical_lines']} / {f['bytes']} | `{f['sha256']}` |")
out.append('''
Raw retrieval bytes are authoritative: the browser normalized `structs.swift` to214 display lines; the retained raw file is223 physical lines. Immutable sources were retrieved directly by full commit, not latest/tag resolution. Whole selected source, in-file helpers, output annotations and driver requirements were read through EOF. Constructor screening is retained separately: `constructor.swift` L1–56 has11 class/generic/overload markers a,b,c,d,e,f,g,h,i,j,k. Despite its destructor comment, it prints only initializer selection; it is unselected and contributes no groups.

Pinned [Swift LICENSE.txt](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/LICENSE.txt) is Apache-2.0 with Runtime Library Exception, SHA-256 **`770af8291f708538d8ff885a0bbc4e045cd700531741c4f99528d435c14d7f55`**. The unchanged retained round5 bytes were rehashed against peers.json; the license and exception were read and preserved. Selected tests contain no individual copyright header; repository attribution/license and support-file copyright notices remain in evidence. Sources are documentary snapshots, not maintained ports.

## What the source establishes

- **The harness adds a lifetime oracle.** `structs.swift` does not explicitly read `l`, but `StdlibUnittest._runTest` resets `LifetimeTracked.instances` before the body and requires zero after body/teardown. `LifetimeTracked.init` increments; `deinit` checks positive serial, decrements and negates it. This check attaches to all5 registered tests; it observes tracked objects in InitStruct/InitStructAddrOnly, while Interval/Big/Generic construct no tracked objects. It does not assert exact destructor order, peak live count, bytes, all heap leaks or Minyar's deferred cleanup service points.
- **Aggregate values and copy/lifetime are different oracles.** Eight Big fields are independently checked after a return. No selected file retains a Swift struct/tuple/array alias and mutates its source to discriminate copying from sharing. A Minyar named-record projection preserves fields while using shared records and managed pointer returns. Source values alone establish no copy or ABI parity.
- **Tuple labels matter.** `(hi:2,lo:1)` still yields lo4/hi6 after addition. A named-record projection must bind by field name, not silently swap values. Tuple/inout/custom operators remain excluded; related Minyar mutation uses shared reference semantics.
- **`!!` is a generic projection, not double negation.** The helper returns `x.boolValue`. `&&&` accepts an existential and autoclosure and calls the RHS only in its true branch; both actual calls have true LHS, and no RHS effects/false-LHS skip are observed. This is metadata coverage, not an independent short-circuit effect-order test.
- **`slices.swift` performs no slicing.** It iterates two ordinary arrays and a varargs-packed array. The generic `show_slice` is commented out. There is no slice offset, view, mutation, copy, Text or Unicode indexing assertion to import from this filename.
- **Dormant definitions remain explicit.** Both InitStruct `init(b:)` overloads and Interval's custom print helper are never called. Wrong overload bodies in functions.swift are alternatives to CHECKRight, not expected outputs. No uncalled helper is credited as a dynamic assertion or tested branch.

All5 files have `// REQUIRES: executable_test` and `// RUN: %target-run-simple-swift`; four append `| %FileCheck %s`. They have no per-file backend skip or XFAIL annotation. The default pinned lit template empties a temporary directory, builds source with target/module-cache options and `-module-name main`, codesigns, and runs the artifact. The literal RUN directive does not select an optimization level: lit test-mode flags include empty/default, `-O`, `-Osize`, `-Ounchecked` and dynamic variants. None of these was run. CHECK text is an ordered pattern, not recorded exact whole stdout; tuple varargs CHECKs omit trailing spaces, and the empty pattern `0 ints` is weaker than the helper's `0 ints: ` output.

## Imported helpers and exact support limits

The scalar `expectEqual` overload delegates `{$0 == $1}` to `expectEqualTest`; failure sets `_anyExpectFailed` and reports context. TestSuite registers a closure without executing it; runAllTests dispatches through its parent/child or in-process harness. The parent maps failed expectations/unexpected termination to failure and aborts by the default suite callback. No source output/pass observation is inferred from this machinery.

**H1** is the single shared source assertion at StdlibUnittest.swift L1991–1993:

```swift
expectEqual(
  0, LifetimeTracked.instances, "Found leaked LifetimeTracked instances.",
  file: test.testLoc.file, line: test.testLoc.line)
```

Optional native heap tracking in the same helper is guarded by `SWIFT_RUNTIME_ENABLE_LEAK_CHECKER`; its return from `stopTrackingObjects` is discarded at this site. CMake conditionally supplies that define. The synchronous tracked-instance check itself is not conditional. Three of5 selected named tests have no tracked object, so five attachments are not five nonvacuous lifetime experiments. Its Swift class/deinit endpoint is **incompatible as written** for Minyar incremental retirement; content-only adaptation does not cover H1.

| Pinned supporting file | SHA-256 | Actual documentary read spans |
| --- | --- | --- |''')
for f in sources['support']:
    if 'snapshot' in f:
        out.append(f"| [{f['path']}]({f['url']}) | `{f['sha256']}` | {spans(f['reviewed_spans'])} |")
out.append('''
Complete support bytes are retained, but only these helper/configuration spans receive contract review. The [source manifest](../../evidence/peer-readonly/swift-round7/source-manifest.json) records exact unread complements, including transitive OS/child-process infrastructure. Support files are not added to selected complete-test counts. A guessed `.swift.gyb` helper path returned404 once and was not retried; the actual `.swift` path was accessible, and pinned CMake confirms its filename. No blocked directory API or restricted Rust resource was retried or bypassed. No new service/content restriction occurred; LLVM fallback was unnecessary.

## Local source and fixture coverage

All mappings bind to frozen bytes in the [local manifest](../../evidence/peer-readonly/swift-round7/local-manifest.json). They show inspected assertions and expected values, not new passing status or exhaustive repository coverage. No exact peer unit is credited already covered merely because a local related property exists.

| Coverage ID / exact source spans | Existing oracle | Exact limit |
| --- | --- | --- |''')
for key,c in d['local_coverage_references'].items():
    out.append(f"| **{key}** — `{c['path']}` {spans(c['lines'])} | {c['proves']} | {c['limit']} |")
out.append('''
Implementation reading also inspected compiler scalar-record eligibility, declared-position record construction, call operands and borrowed returns, plus the runtime's checked scalar/mixed record slots. See the JSON's hashed implementation reviews for exact spans. Whole aliases/arguments/returns keep managed records; source-order field expressions resolve to declaration positions; borrowed returns retain before frame leave. These mechanisms explain the mapping but are not executable evidence or a defect/all-clear finding. Minyar retains automatic ownership, shared mutable records/Lists/Bytes, independent Bytes.slice copies and legitimately shared immutable Text; no syntax, copy-on-write, closure, class or destructor feature is proposed.

## Complete per-unit ledger

`adopt_pending` preserves the bounded ordinary value/iteration property with existing syntax. `adapt_pending` is a weaker named-record algorithm replacing tuple/custom-operator/aggregate ABI contracts. `incompatible_as_written` preserves the actual unsupported core contract instead of forcing a field/print port. Helpers and repeated driver/lifetime attachments are not extra comparisons. The JSON preserves every selected assertion's exact source line, full helper spans and local hashes. All38 units below are source-reviewed only.
''')
for u in d['comparison_groups']:
    out.append(f"\n### {u['id']} — {u['name']}\n\n[{u['path']} L{u['lines'][0]}–{u['lines'][1]}]({u['url']}). **{u['disposition']}**.\n\nPrimary expectation: {u['upstream_expected']}\n\nMinyar: {u['minyar_mapping']}")
    out.append('\nExact selected oracle sites:\n\n'+'\n'.join(f"- L{s['line']}: `{s['source'].strip()}`" for s in u['source_assertion_sites']))
    out.append('\nIn-file helper read spans: '+(spans(u['in_file_helper_spans']) or 'none')+'.')
    if 'shared_harness_oracle' in u:
        out.append(f"\nAttached shared helper: H1 at the **{u['harness_registered_test']}** boundary; no extra group or new assertion source site.")
    out.append('\nExcluded: '+('; '.join(u['excluded_contracts']) or 'none in this ordinary scalar unit')+'.')
    out.append('\nLocal source coverage: '+', '.join(f"**{key}** (`{d['local_coverage_references'][key]['path']}` {spans(d['local_coverage_references'][key]['lines'])})" for key in u['local_coverage_ids'])+'. Exact limits are in the local table; no execution claim.')

p=d['proposed_original_regressions'][0]
out.append(f'''\n## One original missing-test proposal — pending

**P1 — {p['name']}.** {p['demonstrated_gap']}

{p['rationale']}

Existing-syntax source, kept only in this report/ledger and never compiled or executed:

```minyar
{p['proposed_minyar_source']}```

Exact independent expected stdout (35 lines):

```text
{p['independent_expected_stdout']}```

The first8 outputs preserve the complete pinned Big assertion vector. The next8 distinct values make slot mistakes observable; trace87654321 records reverse source order rather than a commutative sum. Mutation111/previous scalar11 distinguishes reference sharing from scalar snapshot. Eight temporary records provide allocation pressure after source-container replacement, not an object-count/destruction-time guarantee. No destructor, pointer identity, Swift copy or Minyar deferred-work bound is inferred. A documentary scalar/dictionary derivation independently checks this proposed output; it is not running the proposed Minyar program.

{p['tdd_handoff']}

## Prior evidence, deduplication and handoff

Rounds2–6 contain32+66+120+118+114=**450 heterogeneous source comparison groups across17 deduplicated complete selected files**; array.zig's matching prefix/remainder is one file. These are bounded report totals, not whole-campaign coverage or ports. This disjoint38-group/5-file selection yields **488 groups across22 selected complete files** for that read-only report union only. The pre-existing Swift statement directory and initial campaign files remain separate; they are not added into this union.

The initial separate runtime record, [run-7m86apqr/results.json](evidence/runtime-peer-projections/run-7m86apqr/results.json), records6 originals and36 executions across systemK32, fixedK1 and generated-ASan systemK32. Saved link argv show18 last-O0 and18 last-O2; native runtime C objects areO2 and sanitized C objectsO1. This is external execution evidence read here, not38 peer ports or a round7 run. It covers Bytes sharing/copy, row alias/scalar snapshot, literal effects/order, once-only producers, NaN Boolean comparisons and source subnormal/signed-zero bits. Those six originals are not reproposed. The [historical correction](runtime-peer-optimization-correction.json) retains earlier18/24/36 archives' effective sanitizer-O1 links without rewriting old ledgers. Generated UBSan/LSan/full-suite validation is not added.

During this review, the runtime lane completed round6's ordered effects before a decisive Boolean literal/helper and binary64 rounding at2^53. The new separate [run-l5_218bk/results.json](evidence/runtime-peer-projections/run-l5_218bk/results.json) and [provenance](evidence/runtime-peer-projections/run-l5_218bk/provenance.json) record **8 methods / 48 executions**, including both new methods. Saved links have **24 last-O0 and24 last-O2** and all48 recorded executions returned0. The middle Boolean case preserves events1,2 or1,2,3 and excludes9; the arithmetic case adds exact binary64 bit controls4845873199050653696/4845873199050653697. Current fixture L226–253/L255–276 and its matching archived source were read and hashed. Six new reference snapshots are retained in [latest runtime manifest](../../evidence/peer-readonly/swift-round7/latest-runtime-manifest.json), separately from the earlier six-method references. The frozen local fixture already had eight methods at capture; its corrected reviewed span isL62–276. Old peer proposal ledgers and old36-execution archive remain unchanged. These are external originals, with zero round7 execution credit. Generic Bool CHECK values alone do not justify another ordered-effect proposal, and scalar return values do not justify repeating already-tested Text/Bytes retention.

Selection/progress evidence, retained sources/licenses, per-unit JSON, exact support complements and documentary audits are in [round7 evidence](../../evidence/peer-readonly/swift-round7/). All selected lines and71 local-to-selected source oracle sites are reviewed; no selected helper/body is knowingly unread. All12 adopt/adapt groups and P1 remain unimplemented/unexecuted;26 incompatible groups are excluded. Other Interpreter files (including unselected constructor screening), other peer repositories and the unread support complements remain outside this round. No LLVM directory, entire Swift repository or whole campaign is claimed complete.

Only the two round7 reports and its evidence directory were authored. Central ledgers were not edited; unrelated changes belong to ongoing owners. Documentary checks verify retained hashes, bounded source sites, span partitions, exact prior-path overlap, original proposal arithmetic, and saved external argv/outputs; they are not tests, timings or new production validation. The [final handoff](../../evidence/peer-readonly/swift-round7/handoff.json) records independently derived totals, snapshot changes if any and the campaign boundary.
''')
audit=json.loads((E/'document-checks.json').read_text())
out.append(f"\nThe independent documentary audit is consistent: **{audit['summary']['documentary_predicate_count']} predicates**, **{audit['summary']['distinct_retained_hash_records']} distinct retained source/license/local/reference hash records**, **7,222 selected bytes / 413 lines**, and **71 selected oracle sites**. [Document checks](../../evidence/peer-readonly/swift-round7/document-checks.json) retain every predicate and exact support partitions. These counts are documentary verification, never test executions.")
if audit['concurrent_reference_changes']:
    out.append('\nConcurrent reference updates were observed in '+', '.join('`'+c['path']+'`' for c in audit['concurrent_reference_changes'])+'. Initial frozen hashes and observed current hashes are preserved in document-checks.json and handoff.json; this lane authored neither file. Local fixture and central-ledger snapshots still match the audited bytes.')
report='\n'.join(out)+'\n'
for before,after in [('all25','all 25'),('all5','all 5'),('All5','All 5'),('All38','All 38'),('all38','all 38'),('of5','of 5'),('has11','has 11'),('to214','to 214'),('is223','is 223'),('returned404','returned 404'),('first8','first 8'),('next8','next 8'),('All12','All 12'),('and71','and 71'),('across17','across 17'),('across22','across 22'),('disjoint38','disjoint 38'),('not38','not 38'),('records6','records 6'),('and36','and 36'),('show18','show 18'),('and18','and 18'),('areO2','are O2'),('objectsO1','objects O1'),('earlier18','earlier 18'),('at2^53','at 2^53'),('contain32','contain 32'),(';26','; 26')]:
    report=report.replace(before,after)
(R/'peer-readonly-swift-round7.md').write_text(report)
print('Rendered standalone round7 report from manually authored ledger.')
