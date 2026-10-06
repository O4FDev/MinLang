# Read-only Swift peer source review — round 7

Five complete previously unreviewed files at **Swift `1ff1cc1170617ab23ab74aa8b741c8daca1903f6`**, **413 raw physical lines**, **38 heterogeneous comparison groups**. Dispositions: **4 adopt pending, 8 adapt pending, 26 incompatible as written, 0 exact units already covered**. All **36 selected `expectEqual` call sites and 35 `CHECK` sites** are individually attributed. Five registered Struct tests share one imported lifetime assertion source site. One narrow original regression proposal remains pending. **Zero ports, test executions, compilations, installations, timings, commits or subagents.**

This is GPT-6.1 Sol high documentary research. Only `research/2026-10-memory/peer-readonly-swift-round7.md/.json` and `evidence/peer-readonly/swift-round7/` were written. Existing dirty work, active core/native cohorts, stopped compiler/literature lanes and central manifests were left to their owners. The campaign earliest completion remains **2026-10-04 06:54:29 UTC**; this source round makes no campaign-completion claim.

## Selection and primary pinned sources

Repository README, architecture, language/ownership/testing and syntax notes, the campaign README, pins/central review ledger, and completed rounds2–6 reports/ledgers/handoffs supplied context. No file named notes/AGENTS.md was found in the repository listing; the user's supplied commit instruction applies, and no commit was made. The prior Swift exclusion set contains the initial four Interpreter files (`string_literal`, `unicode_scalar_literal`, `deinit_recursive_no_overflow`, `arrays`), all 25 recursively reviewed statement-directory files/273 grouped scenarios, and round5's `array_of_optional` and `conversions`. Exact path comparison is retained in the [selection checkpoint](../../evidence/peer-readonly/swift-round7/selection-checkpoint.json); overlap is empty. Previously selected Go/Zig round6 files also remain excluded. This selects complete bounded files, not an entire huge directory followed by an arbitrary prefix sample.

| Whole selected source | Raw extent / bytes | SHA-256 |
| --- | --- | --- |
| [test/Interpreter/structs.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift) | L1–223 / 3840 | `cb24efeb347c134c6a9673dcb0842853cf796156ea2e1a28a891b92f61ae7aee` |
| [test/Interpreter/tuples.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/tuples.swift) | L1–55 / 1034 | `1043a993ab3fae385c6e585d23be9f210c129443f3c5ef7bf8b7465e82bcff7a` |
| [test/Interpreter/bool_as_generic.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/bool_as_generic.swift) | L1–27 / 705 | `cea967c5480cdf4ec5d7f2f03dd4e494d4b5ced4e9e23d251c8e455c9370025f` |
| [test/Interpreter/functions.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift) | L1–54 / 975 | `33a23f56ddfa6b519b13f4e025f7209360a2f4b87c6cdfd3c55a111393e1a65b` |
| [test/Interpreter/slices.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/slices.swift) | L1–54 / 668 | `f080b412ffa276bcc3571927ce665e92f10bb5d9ed2fa93451efb989d2dd865d` |

Raw retrieval bytes are authoritative: the browser normalized `structs.swift` to 214 display lines; the retained raw file is 223 physical lines. Immutable sources were retrieved directly by full commit, not latest/tag resolution. Whole selected source, in-file helpers, output annotations and driver requirements were read through EOF. Constructor screening is retained separately: `constructor.swift` L1–56 has 11 class/generic/overload markers a,b,c,d,e,f,g,h,i,j,k. Despite its destructor comment, it prints only initializer selection; it is unselected and contributes no groups.

Pinned [Swift LICENSE.txt](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/LICENSE.txt) is Apache-2.0 with Runtime Library Exception, SHA-256 **`770af8291f708538d8ff885a0bbc4e045cd700531741c4f99528d435c14d7f55`**. The unchanged retained round5 bytes were rehashed against peers.json; the license and exception were read and preserved. Selected tests contain no individual copyright header; repository attribution/license and support-file copyright notices remain in evidence. Sources are documentary snapshots, not maintained ports.

## What the source establishes

- **The harness adds a lifetime oracle.** `structs.swift` does not explicitly read `l`, but `StdlibUnittest._runTest` resets `LifetimeTracked.instances` before the body and requires zero after body/teardown. `LifetimeTracked.init` increments; `deinit` checks positive serial, decrements and negates it. This check attaches to all 5 registered tests; it observes tracked objects in InitStruct/InitStructAddrOnly, while Interval/Big/Generic construct no tracked objects. It does not assert exact destructor order, peak live count, bytes, all heap leaks or Minyar's deferred cleanup service points.
- **Aggregate values and copy/lifetime are different oracles.** Eight Big fields are independently checked after a return. No selected file retains a Swift struct/tuple/array alias and mutates its source to discriminate copying from sharing. A Minyar named-record projection preserves fields while using shared records and managed pointer returns. Source values alone establish no copy or ABI parity.
- **Tuple labels matter.** `(hi:2,lo:1)` still yields lo4/hi6 after addition. A named-record projection must bind by field name, not silently swap values. Tuple/inout/custom operators remain excluded; related Minyar mutation uses shared reference semantics.
- **`!!` is a generic projection, not double negation.** The helper returns `x.boolValue`. `&&&` accepts an existential and autoclosure and calls the RHS only in its true branch; both actual calls have true LHS, and no RHS effects/false-LHS skip are observed. This is metadata coverage, not an independent short-circuit effect-order test.
- **`slices.swift` performs no slicing.** It iterates two ordinary arrays and a varargs-packed array. The generic `show_slice` is commented out. There is no slice offset, view, mutation, copy, Text or Unicode indexing assertion to import from this filename.
- **Dormant definitions remain explicit.** Both InitStruct `init(b:)` overloads and Interval's custom print helper are never called. Wrong overload bodies in functions.swift are alternatives to CHECKRight, not expected outputs. No uncalled helper is credited as a dynamic assertion or tested branch.

All 5 files have `// REQUIRES: executable_test` and `// RUN: %target-run-simple-swift`; four append `| %FileCheck %s`. They have no per-file backend skip or XFAIL annotation. The default pinned lit template empties a temporary directory, builds source with target/module-cache options and `-module-name main`, codesigns, and runs the artifact. The literal RUN directive does not select an optimization level: lit test-mode flags include empty/default, `-O`, `-Osize`, `-Ounchecked` and dynamic variants. None of these was run. CHECK text is an ordered pattern, not recorded exact whole stdout; tuple varargs CHECKs omit trailing spaces, and the empty pattern `0 ints` is weaker than the helper's `0 ints: ` output.

## Imported helpers and exact support limits

The scalar `expectEqual` overload delegates `{$0 == $1}` to `expectEqualTest`; failure sets `_anyExpectFailed` and reports context. TestSuite registers a closure without executing it; runAllTests dispatches through its parent/child or in-process harness. The parent maps failed expectations/unexpected termination to failure and aborts by the default suite callback. No source output/pass observation is inferred from this machinery.

**H1** is the single shared source assertion at StdlibUnittest.swift L1991–1993:

```swift
expectEqual(
  0, LifetimeTracked.instances, "Found leaked LifetimeTracked instances.",
  file: test.testLoc.file, line: test.testLoc.line)
```

Optional native heap tracking in the same helper is guarded by `SWIFT_RUNTIME_ENABLE_LEAK_CHECKER`; its return from `stopTrackingObjects` is discarded at this site. CMake conditionally supplies that define. The synchronous tracked-instance check itself is not conditional. Three of 5 selected named tests have no tracked object, so five attachments are not five nonvacuous lifetime experiments. Its Swift class/deinit endpoint is **incompatible as written** for Minyar incremental retirement; content-only adaptation does not cover H1.

| Pinned supporting file | SHA-256 | Actual documentary read spans |
| --- | --- | --- |
| [stdlib/private/StdlibUnittest/StdlibUnittest.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/stdlib/private/StdlibUnittest/StdlibUnittest.swift) | `3a48504ba303975595bdcb514a14366ad877a5deee2d0c2f777d296690af9e2c` | L1–50, L197–207, L327–358, L806–810, L928–947, L1361–1449, L1543–1612, L1740–1808, L1873–1912, L1953–1994, L2110–2177 |
| [test/lit.cfg](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/lit.cfg) | `fb388853482d1afbff6a5c5bcffc7264d738ec3ffec8350f04684c4dff5510eb` | L644–646, L911–980, L1438–1457, L1718–1734, L2682–2759, L2864–2879 |
| [stdlib/private/StdlibUnittest/CMakeLists.txt](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/stdlib/private/StdlibUnittest/CMakeLists.txt) | `311b454c37d0d37955dfc2a70837980cabb0b2f9a8141502f9a80fbd7e58c0d8` | L1–95 |
| [stdlib/private/StdlibUnittest/LifetimeTracked.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/stdlib/private/StdlibUnittest/LifetimeTracked.swift) | `4a11edfd41af5be2f523310493aa9065fd1c4401ec2eac558dc7d98e5630a8d2` | L1–78 |

Complete support bytes are retained, but only these helper/configuration spans receive contract review. The [source manifest](../../evidence/peer-readonly/swift-round7/source-manifest.json) records exact unread complements, including transitive OS/child-process infrastructure. Support files are not added to selected complete-test counts. A guessed `.swift.gyb` helper path returned 404 once and was not retried; the actual `.swift` path was accessible, and pinned CMake confirms its filename. No blocked directory API or restricted Rust resource was retried or bypassed. No new service/content restriction occurred; LLVM fallback was unnecessary.

## Local source and fixture coverage

All mappings bind to frozen bytes in the [local manifest](../../evidence/peer-readonly/swift-round7/local-manifest.json). They show inspected assertions and expected values, not new passing status or exhaustive repository coverage. No exact peer unit is credited already covered merely because a local related property exists.

| Coverage ID / exact source spans | Existing oracle | Exact limit |
| --- | --- | --- |
| **record-fields** — `tests/conformance/records/program.min` L1–10 | Explicit reordered record fields and nested named projections: Ada,36,language. | Three-field Person and two-field Name; no Swift tuple, initializer, by-value copy or eight-field return oracle. |
| **scalar-init** — `tests/scalar-record-initialization.py` L8–36, L45–55 | Returned scalar(37,true,z), mixed(41,mixed), nested(8,13), and effect order(x12,y11,state12); exact output and setter selection assertions. | At most three fields on these returned shapes; no eight-Integer returned record with every position independently checked. |
| **scalar-storage** — `tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191 | Reordered pair effects1110/11; managed alias/return/container escapes; swap21/12; mixed/direct projected constructors; budget64 one-field shapes plus2 fallbacks. | Budget counts many small records, not fields in one wide returned record; first escape cases observe x only; no Swift initialization delegation or ARC endpoint. |
| **scalar-mutation** — `tests/scalar-record-mutation.py` L17–44, L86–105 | Independent pair-field capture1110/11 and escaped managed pair9/4; explicit wrong-output/failure mutant oracles when invoked. | Two-field shapes only in these cases; no execution or mutant detection claimed here. |
| **scalar-production** — `tests/production-scalar-storage.py` L50–74, L76–113 | Boolean field effects/snapshots406/404; reordered Pair fields7/3/37; scalar record argument/return generations5/11/21/17. | Four scalar fields in Flags, two in Pair, one in Cell; no eight-field end-to-end return retention. |
| **parameters** — `tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146 | Scalar same-input addition7+7=14; shared List mutation2/6/6; projected Pair parameters; recursive returned Text; earlier Text argument retained during later mutation. | No exact double2/4 cases, generic/existential metadata, function values, varargs or Swift inout; later-argument control uses Text. |
| **parameter-production** — `tests/production-readonly-parameters.py` L9–41 | Distinct same-type operands259/714/rightleft/2; retained List parameter after last external owner replacement42/99. | No wide record with field permutation; shared List lifetime is not Swift value copying. |
| **loops** — `tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64 | Ordered words alpha/beta/gamma; Unicode iteration; shared Player mutationhealth15/99; nested List mutation7. | Different exact iteration values; no slicing in the selected Swift file; shared mutation is not Swift array value semantics. |
| **literal** — `tests/recursive-data.py` L148–184 | Ordered List initializer values1/2/3 and exact literal values7/seven/false/b/empty/é🙂; earlier Box retained across later replacementold!/new!/new!. | No tuple label rearrangement, eight-field return or imported metadata; initializer capture already exists, so no duplicate generic literal-effects proposal. |
| **adversarial** — `tests/adversarial.py` L16–43, L83–103, L145–211 | Borrowed parameters escape; receivers survive index/slice mutation; Boolean effect trace3/4/5/6/8; early returned Text pairs; retained shared diamond leaf!. | Existing ownership and short-circuit controls are related; none specifies Swift ARC class deinit at each test boundary or every field of an eight-Integer return. |
| **runtime-originals** — `tests/memory-research-peer-projections.py` L62–276 | Eight existing originals: Bytes copy/shared alias, row scalar snapshot, literal effects, once-only producers, NaN matrix, source underflow bits, middle Boolean literal barrier and2^53 binary64 arithmetic/bits. | Initial run-7m86apqr36 and concurrently completed run-l5_218bk48 are separate runtime-lane evidence. Frozen local source already includes eight methods; no round7 run. No8-field return or Swift operator/tuple/metadata/ARC equivalence. |
| **language-oracle** — `tests/regressions.py` L54–65 | Harness checks successful compile/link, requested O0/O2 process status and exact UTF-8 stdout when invoked. | Not invoked in this lane; environmental link flags and actual argv matter, as historical optimization correction shows. |
| **function-conformance** — `tests/conformance/programs-and-entry-points/program.min` L1–14 | Typed double via multiplication on0,1,2, checked only as total6 and top level output. | Aggregate total is weaker than independent double(2)=4 and double(4)=8 assertions; x*2 differs from selected x+x lowering. |
| **ownership-conformance** — `tests/conformance/memory-lifetime/program.min` L1–12 | Saved shared Node survives root replacement; values1,2,1. | Related existing managed retention, no implicit value copy or wide returned record field-map proof. |

Implementation reading also inspected compiler scalar-record eligibility, declared-position record construction, call operands and borrowed returns, plus the runtime's checked scalar/mixed record slots. See the JSON's hashed implementation reviews for exact spans. Whole aliases/arguments/returns keep managed records; source-order field expressions resolve to declaration positions; borrowed returns retain before frame leave. These mechanisms explain the mapping but are not executable evidence or a defect/all-clear finding. Minyar retains automatic ownership, shared mutable records/Lists/Bytes, independent Bytes.slice copies and legitimately shared immutable Text; no syntax, copy-on-write, closure, class or destructor feature is proposed.

## Complete per-unit ledger

`adopt_pending` preserves the bounded ordinary value/iteration property with existing syntax. `adapt_pending` is a weaker named-record algorithm replacing tuple/custom-operator/aggregate ABI contracts. `incompatible_as_written` preserves the actual unsupported core contract instead of forcing a field/print port. Helpers and repeated driver/lifetime attachments are not extra comparisons. The JSON preserves every selected assertion's exact source line, full helper spans and local hashes. All 38 units below are source-reviewed only.


### S1 — Interval unary negative

[test/Interpreter/structs.swift L35–39](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L35-L39). **adapt_pending**.

Primary expectation: lo=-2,hi=-1 from -Interval(1,2)

Minyar: Named Interval record with explicit fields and ordinary negate/add/subtract helpers can preserve each scalar result; no input mutation/copy assertion occurs.

Exact selected oracle sites:

- L37: `expectEqual(-2, i.lo)`
- L38: `expectEqual(-1, i.hi)`

In-file helper read spans: L9–28, L30–32.

Attached shared helper: H1 at the **Interval** boundary; no extra group or new assertion source site.

Excluded: operator overloading; Swift struct by-value argument/return ABI; TestSuite closure syntax; H1 Swift ARC endpoint check.

Local source coverage: **record-fields** (`tests/conformance/records/program.min` L1–10), **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191). Exact limits are in the local table; no execution claim.

### S2 — Interval addition

[test/Interpreter/structs.swift L40–44](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L40-L44). **adapt_pending**.

Primary expectation: lo=4,hi=6 from (1,2)+(3,4)

Minyar: Named Interval record with explicit fields and ordinary negate/add/subtract helpers can preserve each scalar result; no input mutation/copy assertion occurs.

Exact selected oracle sites:

- L42: `expectEqual(4, i.lo)`
- L43: `expectEqual(6, i.hi)`

In-file helper read spans: L9–28, L30–32.

Attached shared helper: H1 at the **Interval** boundary; no extra group or new assertion source site.

Excluded: operator overloading; Swift struct by-value argument/return ABI; TestSuite closure syntax; H1 Swift ARC endpoint check.

Local source coverage: **record-fields** (`tests/conformance/records/program.min` L1–10), **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191). Exact limits are in the local table; no execution claim.

### S3 — Interval subtraction

[test/Interpreter/structs.swift L45–49](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L45-L49). **adapt_pending**.

Primary expectation: lo=1,hi=3 from (3,4)-(1,2); lo=a.lo-b.hi,hi=a.hi-b.lo

Minyar: Named Interval record with explicit fields and ordinary negate/add/subtract helpers can preserve each scalar result; no input mutation/copy assertion occurs.

Exact selected oracle sites:

- L47: `expectEqual(1, i.lo)`
- L48: `expectEqual(3, i.hi)`

In-file helper read spans: L9–28, L30–32.

Attached shared helper: H1 at the **Interval** boundary; no extra group or new assertion source site.

Excluded: operator overloading; Swift struct by-value argument/return ABI; TestSuite closure syntax; H1 Swift ARC endpoint check.

Local source coverage: **record-fields** (`tests/conformance/records/program.min` L1–10), **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191). Exact limits are in the local table; no execution claim.

### S4 — Big returned eight-field record

[test/Interpreter/structs.swift L60–71](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L60-L71). **adapt_pending**.

Primary expectation: a,b,c,d,e,f,g,h =1,6,1,8,0,3,4,0; every named field independently asserted.

Minyar: Explicit eight-Integer record factory preserves all field values; managed Minyar return differs from Swift large aggregate value return.

Exact selected oracle sites:

- L63: `expectEqual(1, bs.a)`
- L64: `expectEqual(6, bs.b)`
- L65: `expectEqual(1, bs.c)`
- L66: `expectEqual(8, bs.d)`
- L67: `expectEqual(0, bs.e)`
- L68: `expectEqual(3, bs.f)`
- L69: `expectEqual(4, bs.g)`
- L70: `expectEqual(0, bs.h)`

In-file helper read spans: L52–58.

Attached shared helper: H1 at the **Big** boundary; no extra group or new assertion source site.

Excluded: Swift by-value aggregate ABI; H1 Swift ARC endpoint check.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **scalar-production** (`tests/production-scalar-storage.py` L50–74, L76–113). Exact limits are in the local table; no execution claim.

### S5 — Generic phantom String instantiation

[test/Interpreter/structs.swift L82–86](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L82-L86). **incompatible_as_written**.

Primary expectation: a=19,b=84; no String payload field.

Minyar: Ordinary explicit Integer fields could hold19/84 but would remove GenStruct<String> metadata/specialization.

Exact selected oracle sites:

- L84: `expectEqual(19, gs.a)`
- L85: `expectEqual(84, gs.b)`

In-file helper read spans: L73–80.

Attached shared helper: H1 at the **Generic** boundary; no extra group or new assertion source site.

Excluded: user generic struct; phantom type instantiation; H1 Swift ARC endpoint check.

Local source coverage: **record-fields** (`tests/conformance/records/program.min` L1–10). Exact limits are in the local table; no execution claim.

### S6 — InitStruct default initializer

[test/Interpreter/structs.swift L128–132](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L128-L132). **incompatible_as_written**.

Primary expectation: x=10,y=20; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L130: `expectEqual(10, s.x)`
- L131: `expectEqual(20, s.y)`

In-file helper read spans: L88–125, L93–96.

Attached shared helper: H1 at the **InitStruct** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S7 — InitStruct labeled initializer

[test/Interpreter/structs.swift L133–137](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L133-L137). **incompatible_as_written**.

Primary expectation: x=69,y=420; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L135: `expectEqual(69, s.x)`
- L136: `expectEqual(420, s.y)`

In-file helper read spans: L88–125, L98–101.

Attached shared helper: H1 at the **InitStruct** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S8 — InitStruct init then self assignment

[test/Interpreter/structs.swift L138–142](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L138-L142). **incompatible_as_written**.

Primary expectation: x=6,y=8; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L140: `expectEqual(6, s.x)`
- L141: `expectEqual(8, s.y)`

In-file helper read spans: L88–125, L111–114.

Attached shared helper: H1 at the **InitStruct** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S9 — InitStruct self assignment then init

[test/Interpreter/structs.swift L143–147](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L143-L147). **incompatible_as_written**.

Primary expectation: x=6,y=8; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L145: `expectEqual(6, s.x)`
- L146: `expectEqual(8, s.y)`

In-file helper read spans: L88–125, L116–119.

Attached shared helper: H1 at the **InitStruct** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S10 — InitStruct init then init

[test/Interpreter/structs.swift L148–152](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L148-L152). **incompatible_as_written**.

Primary expectation: x=6,y=8; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L150: `expectEqual(6, s.x)`
- L151: `expectEqual(8, s.y)`

In-file helper read spans: L88–125, L121–124.

Attached shared helper: H1 at the **InitStruct** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S11 — InitStruct address-only default initializer

[test/Interpreter/structs.swift L196–200](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L196-L200). **incompatible_as_written**.

Primary expectation: x=10,y=20; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L198: `expectEqual(10, s.x)`
- L199: `expectEqual(20, s.y)`

In-file helper read spans: L155–193, L161–164.

Attached shared helper: H1 at the **InitStructAddrOnly** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization; Any existential address-only storage.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S12 — InitStruct address-only labeled initializer

[test/Interpreter/structs.swift L201–205](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L201-L205). **incompatible_as_written**.

Primary expectation: x=69,y=420; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L203: `expectEqual(69, s.x)`
- L204: `expectEqual(420, s.y)`

In-file helper read spans: L155–193, L166–169.

Attached shared helper: H1 at the **InitStructAddrOnly** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization; Any existential address-only storage.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S13 — InitStruct address-only init then self assignment

[test/Interpreter/structs.swift L206–210](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L206-L210). **incompatible_as_written**.

Primary expectation: x=6,y=8; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L208: `expectEqual(6, s.x)`
- L209: `expectEqual(8, s.y)`

In-file helper read spans: L155–193, L179–182.

Attached shared helper: H1 at the **InitStructAddrOnly** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization; Any existential address-only storage.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S14 — InitStruct address-only self assignment then init

[test/Interpreter/structs.swift L211–215](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L211-L215). **incompatible_as_written**.

Primary expectation: x=6,y=8; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L213: `expectEqual(6, s.x)`
- L214: `expectEqual(8, s.y)`

In-file helper read spans: L155–193, L184–187.

Attached shared helper: H1 at the **InitStructAddrOnly** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization; Any existential address-only storage.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### S15 — InitStruct address-only init then init

[test/Interpreter/structs.swift L216–220](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/structs.swift#L216-L220). **incompatible_as_written**.

Primary expectation: x=6,y=8; H1 also requires no live LifetimeTracked after owning test.

Minyar: Explicit Minyar construction/reassignment has related field values but omits member defaults, self-initialization delegation and tracked class destruction. This is not ported as field-only lifetime coverage.

Exact selected oracle sites:

- L218: `expectEqual(6, s.x)`
- L219: `expectEqual(8, s.y)`

In-file helper read spans: L155–193, L189–192.

Attached shared helper: H1 at the **InitStructAddrOnly** boundary; no extra group or new assertion source site.

Excluded: member default LifetimeTracked(0); Swift class ARC/deinit endpoint; constructor overloading/delegation; self initialization; Any existential address-only storage.

Local source coverage: **scalar-init** (`tests/scalar-record-initialization.py` L8–36, L45–55), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211). Exact limits are in the local table; no execution claim.

### T1 — positional tuple addition

[test/Interpreter/tuples.swift L27–28](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/tuples.swift#L27-L28). **adapt_pending**.

Primary expectation: (lo=4, hi=6)

Minyar: Original named-record helper can preserve lo/hi values; labeled construction keeps field identity despite source order. Shared record helper mutation changes the one record; not Swift inout exclusivity/copy semantics.

Exact selected oracle sites:

- L27: `// CHECK: (lo=4, hi=6)`

In-file helper read spans: L4–25.

Excluded: tuple typealias; positional/labeled tuple coercion; custom operators.

Local source coverage: **record-fields** (`tests/conformance/records/program.min` L1–10), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64). Exact limits are in the local table; no execution claim.

### T2 — reordered labeled tuple addition

[test/Interpreter/tuples.swift L29–30](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/tuples.swift#L29-L30). **adapt_pending**.

Primary expectation: (lo=4, hi=6); first spelling hi:2,lo:1 still assigns lo1/hi2

Minyar: Original named-record helper can preserve lo/hi values; labeled construction keeps field identity despite source order. Shared record helper mutation changes the one record; not Swift inout exclusivity/copy semantics.

Exact selected oracle sites:

- L29: `// CHECK: (lo=4, hi=6)`

In-file helper read spans: L4–25.

Excluded: tuple typealias; positional/labeled tuple coercion; custom operators.

Local source coverage: **record-fields** (`tests/conformance/records/program.min` L1–10), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64). Exact limits are in the local table; no execution claim.

### T3 — tuple interval subtraction

[test/Interpreter/tuples.swift L31–32](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/tuples.swift#L31-L32). **adapt_pending**.

Primary expectation: (lo=1, hi=3)

Minyar: Original named-record helper can preserve lo/hi values; labeled construction keeps field identity despite source order. Shared record helper mutation changes the one record; not Swift inout exclusivity/copy semantics.

Exact selected oracle sites:

- L31: `// CHECK: (lo=1, hi=3)`

In-file helper read spans: L4–25.

Excluded: tuple typealias; positional/labeled tuple coercion; custom operators.

Local source coverage: **record-fields** (`tests/conformance/records/program.min` L1–10), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64). Exact limits are in the local table; no execution claim.

### T4 — inout tuple compound update

[test/Interpreter/tuples.swift L34–40](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/tuples.swift#L34-L40). **adapt_pending**.

Primary expectation: (lo=4, hi=6) after x(1,2) <+>= (3,4)

Minyar: Original named-record helper can preserve lo/hi values; labeled construction keeps field identity despite source order. Shared record helper mutation changes the one record; not Swift inout exclusivity/copy semantics.

Exact selected oracle sites:

- L37: `// CHECK: (lo=4, hi=6)`

In-file helper read spans: L4–25, L34–39.

Excluded: tuple typealias; positional/labeled tuple coercion; custom operators; inout exclusivity/value writeback.

Local source coverage: **record-fields** (`tests/conformance/records/program.min` L1–10), **scalar-storage** (`tests/scalar-record-storage.py` L59–75, L96–162, L164–182, L184–191), **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64). Exact limits are in the local table; no execution claim.

### T5 — empty varargs

[test/Interpreter/tuples.swift L50–51](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/tuples.swift#L50-L51). **incompatible_as_written**.

Primary expectation: CHECK0 ints; print helper actually emits "0 ints: " then newline

Minyar: A List<Integer> helper could print length/elements but would not exercise variadic argument packing or empty varargs.

Exact selected oracle sites:

- L50: `// CHECK: 0 ints`

In-file helper read spans: L42–48.

Excluded: varargs Int...; print terminator named argument; string interpolation.

Local source coverage: **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### T6 — one vararg

[test/Interpreter/tuples.swift L52–53](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/tuples.swift#L52-L53). **incompatible_as_written**.

Primary expectation: CHECK1 ints: 1; helper emits trailing space before newline

Minyar: A List<Integer> helper could print length/elements but would not exercise variadic argument packing or empty varargs.

Exact selected oracle sites:

- L52: `// CHECK: 1 ints: 1`

In-file helper read spans: L42–48.

Excluded: varargs Int...; print terminator named argument; string interpolation.

Local source coverage: **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### T7 — three varargs

[test/Interpreter/tuples.swift L54–55](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/tuples.swift#L54-L55). **incompatible_as_written**.

Primary expectation: CHECK3 ints: 1 2 3; helper emits trailing space before newline

Minyar: A List<Integer> helper could print length/elements but would not exercise variadic argument packing or empty varargs.

Exact selected oracle sites:

- L54: `// CHECK: 3 ints: 1 2 3`

In-file helper read spans: L42–48.

Excluded: varargs Int...; print terminator named argument; string interpolation.

Local source coverage: **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### B1 — generic Bool projection true

[test/Interpreter/bool_as_generic.swift L24–24](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/bool_as_generic.swift#L24-L24). **incompatible_as_written**.

Primary expectation: true

Minyar: !! here returns x.boolValue; it is not double negation. &&& accepts protocol existential and autoclosure. Both call-site LHS values are true; no false-LHS skipped effect/trap is asserted.

Exact selected oracle sites:

- L24: `print(!!true) // CHECK: true`

In-file helper read spans: L6–22.

Excluded: generic protocol constraint; Bool protocol extension; existential metadata; custom operator.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **runtime-originals** (`tests/memory-research-peer-projections.py` L62–276). Exact limits are in the local table; no execution claim.

### B2 — generic Bool projection false

[test/Interpreter/bool_as_generic.swift L25–25](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/bool_as_generic.swift#L25-L25). **incompatible_as_written**.

Primary expectation: false

Minyar: !! here returns x.boolValue; it is not double negation. &&& accepts protocol existential and autoclosure. Both call-site LHS values are true; no false-LHS skipped effect/trap is asserted.

Exact selected oracle sites:

- L25: `print(!!false) // CHECK: false`

In-file helper read spans: L6–22.

Excluded: generic protocol constraint; Bool protocol extension; existential metadata; custom operator.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **runtime-originals** (`tests/memory-research-peer-projections.py` L62–276). Exact limits are in the local table; no execution claim.

### B3 — existential/autoclosure RHS true

[test/Interpreter/bool_as_generic.swift L26–26](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/bool_as_generic.swift#L26-L26). **incompatible_as_written**.

Primary expectation: true

Minyar: !! here returns x.boolValue; it is not double negation. &&& accepts protocol existential and autoclosure. Both call-site LHS values are true; no false-LHS skipped effect/trap is asserted.

Exact selected oracle sites:

- L26: `print(true &&& true) // CHECK: true`

In-file helper read spans: L6–22.

Excluded: generic protocol constraint; Bool protocol extension; existential metadata; custom operator; autoclosure; conditional expression.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **runtime-originals** (`tests/memory-research-peer-projections.py` L62–276). Exact limits are in the local table; no execution claim.

### B4 — existential/autoclosure RHS false

[test/Interpreter/bool_as_generic.swift L27–27](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/bool_as_generic.swift#L27-L27). **incompatible_as_written**.

Primary expectation: false

Minyar: !! here returns x.boolValue; it is not double negation. &&& accepts protocol existential and autoclosure. Both call-site LHS values are true; no false-LHS skipped effect/trap is asserted.

Exact selected oracle sites:

- L27: `print(true &&& false) // CHECK: false`

In-file helper read spans: L6–22.

Excluded: generic protocol constraint; Bool protocol extension; existential metadata; custom operator; autoclosure; conditional expression.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **runtime-originals** (`tests/memory-research-peer-projections.py` L62–276). Exact limits are in the local table; no execution claim.

### F1 — double scalar call 1

[test/Interpreter/functions.swift L16–17](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L16-L17). **adopt_pending**.

Primary expectation: 4

Minyar: Ordinary typed Integer helper return x+x preserves the exact result; no generics/closure/lifetime contract involved in this unit.

Exact selected oracle sites:

- L16: `// CHECK: 4`

In-file helper read spans: L4–6.

Excluded: none in this ordinary scalar unit.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **function-conformance** (`tests/conformance/programs-and-entry-points/program.min` L1–14). Exact limits are in the local table; no execution claim.

### F2 — double scalar call 2

[test/Interpreter/functions.swift L18–19](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L18-L19). **adopt_pending**.

Primary expectation: 8

Minyar: Ordinary typed Integer helper return x+x preserves the exact result; no generics/closure/lifetime contract involved in this unit.

Exact selected oracle sites:

- L18: `// CHECK: 8`

In-file helper read spans: L4–6.

Excluded: none in this ordinary scalar unit.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **function-conformance** (`tests/conformance/programs-and-entry-points/program.min` L1–14). Exact limits are in the local table; no execution claim.

### F3 — curried captured subtraction

[test/Interpreter/functions.swift L21–22](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L21-L22). **incompatible_as_written**.

Primary expectation: 12

Minyar: Ordinary scalar or named-record code could reproduce printed values but would erase the tested function-value/class/tuple/existential contract. No such port proposed.

Exact selected oracle sites:

- L21: `// CHECK: 12`

In-file helper read spans: L8–10.

Excluded: returned closure; captured scalar; function-valued return.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### F4 — twice named function value

[test/Interpreter/functions.swift L24–25](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L24-L25). **incompatible_as_written**.

Primary expectation: 20

Minyar: Ordinary scalar or named-record code could reproduce printed values but would erase the tested function-value/class/tuple/existential contract. No such port proposed.

Exact selected oracle sites:

- L24: `// CHECK: 20`

In-file helper read spans: L12–14.

Excluded: function-valued parameter; indirect calls.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### F5 — twice implicit closure

[test/Interpreter/functions.swift L26–27](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L26-L27). **incompatible_as_written**.

Primary expectation: 7

Minyar: Ordinary scalar or named-record code could reproduce printed values but would erase the tested function-value/class/tuple/existential contract. No such port proposed.

Exact selected oracle sites:

- L26: `// CHECK: 7`

In-file helper read spans: L12–14.

Excluded: closure parameter; implicit $0.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### F6 — twice named closure

[test/Interpreter/functions.swift L28–29](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L28-L29). **incompatible_as_written**.

Primary expectation: 3

Minyar: Ordinary scalar or named-record code could reproduce printed values but would erase the tested function-value/class/tuple/existential contract. No such port proposed.

Exact selected oracle sites:

- L28: `// CHECK: 3`

In-file helper read spans: L12–14.

Excluded: closure parameter; closure-local parameter.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### F7 — subclass overload foo

[test/Interpreter/functions.swift L41–42](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L41-L42). **incompatible_as_written**.

Primary expectation: Right

Minyar: Ordinary scalar or named-record code could reproduce printed values but would erase the tested function-value/class/tuple/existential contract. No such port proposed.

Exact selected oracle sites:

- L41: `// CHECK: Right`

In-file helper read spans: L31–36.

Excluded: class inheritance; Any; overloads/default arguments.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### F8 — subclass overload bar

[test/Interpreter/functions.swift L43–44](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L43-L44). **incompatible_as_written**.

Primary expectation: Right

Minyar: Ordinary scalar or named-record code could reproduce printed values but would erase the tested function-value/class/tuple/existential contract. No such port proposed.

Exact selected oracle sites:

- L43: `// CHECK: Right`

In-file helper read spans: L38–39.

Excluded: class inheritance; Any varargs; overloads/default arguments.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### F9 — tuple existential return

[test/Interpreter/functions.swift L53–54](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/functions.swift#L53-L54). **incompatible_as_written**.

Primary expectation: ("1", "2", "3", 42, 7)

Minyar: Ordinary scalar or named-record code could reproduce printed values but would erase the tested function-value/class/tuple/existential contract. No such port proposed.

Exact selected oracle sites:

- L53: `// CHECK: ("1", "2", "3", 42, 7)`

In-file helper read spans: L46–51.

Excluded: tuple aggregate return; Number protocol existential; protocol extension; aggregate reflection printing.

Local source coverage: **parameters** (`tests/readonly-parameters.py` L16–25, L40–54, L101–123, L139–146), **adversarial** (`tests/adversarial.py` L16–43, L83–103, L145–211), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

### X1 — bound array iteration

[test/Interpreter/slices.swift L23–32](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/slices.swift#L23-L32). **adopt_pending**.

Primary expectation: ordered6,0,2,2,1,4

Minyar: Ordinary Integer List and for preserve all six visits/values; print(x) replaces Int.show only at the observation boundary.

Exact selected oracle sites:

- L27: `// CHECK: 6`
- L28: `// CHECK: 0`
- L29: `// CHECK: 2`
- L30: `// CHECK: 2`
- L31: `// CHECK: 1`
- L32: `// CHECK: 4`

In-file helper read spans: L4–12.

Excluded: Showable protocol method dispatch; Swift array storage/value-copy semantics not asserted.

Local source coverage: **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64), **literal** (`tests/recursive-data.py` L148–184), **runtime-originals** (`tests/memory-research-peer-projections.py` L62–276). Exact limits are in the local table; no execution claim.

### X2 — temporary array iteration

[test/Interpreter/slices.swift L34–41](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/slices.swift#L34-L41). **adopt_pending**.

Primary expectation: ordered9,8,1,0,5

Minyar: Ordinary for over Integer List literal preserves all five visits/values. No array slice, copy, offset or alias assertion exists.

Exact selected oracle sites:

- L37: `// CHECK: 9`
- L38: `// CHECK: 8`
- L39: `// CHECK: 1`
- L40: `// CHECK: 0`
- L41: `// CHECK: 5`

In-file helper read spans: L4–12.

Excluded: Showable protocol method dispatch; Swift array storage/value-copy semantics not asserted.

Local source coverage: **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64), **literal** (`tests/recursive-data.py` L148–184), **runtime-originals** (`tests/memory-research-peer-projections.py` L62–276). Exact limits are in the local table; no execution claim.

### X3 — varargs array iteration

[test/Interpreter/slices.swift L43–53](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/Interpreter/slices.swift#L43-L53). **incompatible_as_written**.

Primary expectation: ordered1,6,1,8

Minyar: An explicit List helper reproduces values but erases Int... packing; not counted as variadic coverage.

Exact selected oracle sites:

- L50: `// CHECK: 1`
- L51: `// CHECK: 6`
- L52: `// CHECK: 1`
- L53: `// CHECK: 8`

In-file helper read spans: L4–12, L43–47.

Excluded: Int... variadic packing; Showable protocol method dispatch.

Local source coverage: **loops** (`tests/conformance/loops-and-assignment/program.min` L17–24, L26–43, L53–64), **literal** (`tests/recursive-data.py` L148–184). Exact limits are in the local table; no execution claim.

## One original missing-test proposal — pending

**P1 — All fields of a wide returned record, reordered effects and retained alias.** Inspected returned-record fixtures have1–3 fields, four-field Flags is direct/scalar, and the64-proof budget fixture has66 distinct one-field objects. None of these checks all8 named positions across a returned/reordered8-field factory, ordinary echo, source-container replacement and retained alias. This is a bounded width/field-mapping combination, not a claim that all record returns lack tests.

First assert the full pinned field vector. A second original vector uses distinct11..88 so each slot permutation is observable, with noncommutative source-order trace87654321. Mutation111 versus captured scalar11 distinguishes shared record from scalar value snapshot; subsequent replacement/drop plus allocations tests reachable retained alias content. No address, destructor-time or Swift struct copy assertion.

Existing-syntax source, kept only in this report/ledger and never compiled or executed:

```minyar
record Wide { a: Integer; b: Integer; c: Integer; d: Integer; e: Integer; f: Integer; g: Integer; h: Integer }
function peerValues(): Wide {
    return Wide { a: 1; b: 6; c: 1; d: 8; e: 0; f: 3; g: 4; h: 0 }
}
function show(value: Wide) {
    print(value.a); print(value.b); print(value.c); print(value.d)
    print(value.e); print(value.f); print(value.g); print(value.h)
}
function mark(trace: List<Integer>, digit: Integer): Integer {
    trace[0] = trace[0] * 10 + digit
    return digit * 11
}
function make(trace: List<Integer>): Wide {
    return Wide {
        h: mark(trace, 8); g: mark(trace, 7); f: mark(trace, 6); e: mark(trace, 5)
        d: mark(trace, 4); c: mark(trace, 3); b: mark(trace, 2); a: mark(trace, 1)
    }
}
function echo(value: Wide): Wide { return value }
show(peerValues())
let trace = [0]
let holder = [make(trace)]
let kept = echo(holder[0])
let scalar = kept.a
show(kept)
print(trace[0])
holder[0].a = 111
print(kept.a)
print(scalar)
holder[0] = peerValues()
holder = []
for i in 0..8 { let temporary = peerValues(); print(temporary.h) }
show(kept)
```

Exact independent expected stdout (35 lines):

```text
1
6
1
8
0
3
4
0
11
22
33
44
55
66
77
88
87654321
111
11
0
0
0
0
0
0
0
0
111
22
33
44
55
66
77
88
```

The first 8 outputs preserve the complete pinned Big assertion vector. The next 8 distinct values make slot mistakes observable; trace87654321 records reverse source order rather than a commutative sum. Mutation111/previous scalar11 distinguishes reference sharing from scalar snapshot. Eight temporary records provide allocation pressure after source-container replacement, not an object-count/destruction-time guarantee. No destructor, pointer identity, Swift copy or Minyar deferred-work bound is inferred. A documentary scalar/dictionary derivation independently checks this proposed output; it is not running the proposed Minyar program.

Core owner may add this exact positive oracle through the existing candidate-aware O0/O2 harness and relevant ownership configuration. Retain a red only if one is actually observed; no defect, required change or fabricated red claimed. No surface syntax or memory policy change requested.

## Prior evidence, deduplication and handoff

Rounds2–6 contain 32+66+120+118+114=**450 heterogeneous source comparison groups across 17 deduplicated complete selected files**; array.zig's matching prefix/remainder is one file. These are bounded report totals, not whole-campaign coverage or ports. This disjoint 38-group/5-file selection yields **488 groups across 22 selected complete files** for that read-only report union only. The pre-existing Swift statement directory and initial campaign files remain separate; they are not added into this union.

The initial separate runtime record, [run-7m86apqr/results.json](evidence/runtime-peer-projections/run-7m86apqr/results.json), records 6 originals and 36 executions across systemK32, fixedK1 and generated-ASan systemK32. Saved link argv show 18 last-O0 and 18 last-O2; native runtime C objects are O2 and sanitized C objects O1. This is external execution evidence read here, not 38 peer ports or a round7 run. It covers Bytes sharing/copy, row alias/scalar snapshot, literal effects/order, once-only producers, NaN Boolean comparisons and source subnormal/signed-zero bits. Those six originals are not reproposed. The [historical correction](runtime-peer-optimization-correction.json) retains earlier 18/24/36 archives' effective sanitizer-O1 links without rewriting old ledgers. Generated UBSan/LSan/full-suite validation is not added.

During this review, the runtime lane completed round6's ordered effects before a decisive Boolean literal/helper and binary64 rounding at 2^53. The new separate [run-l5_218bk/results.json](evidence/runtime-peer-projections/run-l5_218bk/results.json) and [provenance](evidence/runtime-peer-projections/run-l5_218bk/provenance.json) record **8 methods / 48 executions**, including both new methods. Saved links have **24 last-O0 and24 last-O2** and all48 recorded executions returned0. The middle Boolean case preserves events1,2 or1,2,3 and excludes9; the arithmetic case adds exact binary64 bit controls4845873199050653696/4845873199050653697. Current fixture L226–253/L255–276 and its matching archived source were read and hashed. Six new reference snapshots are retained in [latest runtime manifest](../../evidence/peer-readonly/swift-round7/latest-runtime-manifest.json), separately from the earlier six-method references. The frozen local fixture already had eight methods at capture; its corrected reviewed span isL62–276. Old peer proposal ledgers and old36-execution archive remain unchanged. These are external originals, with zero round7 execution credit. Generic Bool CHECK values alone do not justify another ordered-effect proposal, and scalar return values do not justify repeating already-tested Text/Bytes retention.

Selection/progress evidence, retained sources/licenses, per-unit JSON, exact support complements and documentary audits are in [round7 evidence](../../evidence/peer-readonly/swift-round7/). All selected lines and 71 local-to-selected source oracle sites are reviewed; no selected helper/body is knowingly unread. All 12 adopt/adapt groups and P1 remain unimplemented/unexecuted; 26 incompatible groups are excluded. Other Interpreter files (including unselected constructor screening), other peer repositories and the unread support complements remain outside this round. No LLVM directory, entire Swift repository or whole campaign is claimed complete.

Only the two round7 reports and its evidence directory were authored. Central ledgers were not edited; unrelated changes belong to ongoing owners. Documentary checks verify retained hashes, bounded source sites, span partitions, exact prior-path overlap, original proposal arithmetic, and saved external argv/outputs; they are not tests, timings or new production validation. The [final handoff](../../evidence/peer-readonly/swift-round7/handoff.json) records independently derived totals, snapshot changes if any and the campaign boundary.


The independent documentary audit is consistent: **621 predicates**, **66 distinct retained source/license/local/reference hash records**, **7,222 selected bytes / 413 lines**, and **71 selected oracle sites**. [Document checks](../../evidence/peer-readonly/swift-round7/document-checks.json) retain every predicate and exact support partitions. These counts are documentary verification, never test executions.

Concurrent reference updates were observed in `research/2026-10-memory/README.md`, `research/2026-10-memory/runtime-peer-projections.md`. Initial frozen hashes and observed current hashes are preserved in document-checks.json and handoff.json; this lane authored neither file. Local fixture and central-ledger snapshots still match the audited bytes.
