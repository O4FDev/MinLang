# Pinned peer-test semantic review

Pinned source entries: **25**. Peers: **1**.

All 25 files in the complete recursive pinned Swift test/stmt directory (including its two child directories) were actually read and given individual function/scenario dispositions. No overlap with initial four Interpreter selections. This is not the Swift repository, nor a claim that grouped diagnostic assertions are individually executable Minyar tests.

`peers-inventory.json` retains additional
directory-discovered pending paths, including explicitly capped LLVM/Lean
listings. Source retrieval, reading, semantic disposition and validation
are recorded separately. Upstream sources and licenses are cached only in
`build/peer-research/sources`; new Minyar tests are original adaptations.

Reproduce retrieval with `python3 scripts/peer-research-sources.py --manifest research/2026-10-memory/peer-swift-statement-directory.json --fetch`.
Verify caches and regenerate this table with `python3 scripts/peer-research-sources.py --manifest research/2026-10-memory/peer-swift-statement-directory.json`.
Run adaptations with `python3 tests/peer-research-semantics.py` (O0 and O2).

## Swift: swift-6.2-RELEASE

Pinned commit `1ff1cc1170617ab23ab74aa8b741c8daca1903f6`. [License](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/LICENSE.txt): Apache-2.0 with Runtime Library Exception.

### [test/stmt/async.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/async.swift)

SHA256 `c78646d8048ae427d51bd3e8bccbf492efe85cab9aa61f9c98d4b182543ad4fa`; 14 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [omnom / f](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/async.swift#L5) | upstream_helper_or_harness | External SIL binding and async helper declarations supply the invalid synchronous context. |
| [syncContext](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/async.swift#L10) | incompatible_feature | await and async-let checking requires concurrency, which Minyar does not implement. |

### [test/stmt/c_style_for.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift)

SHA256 `d844a4aa7559323e259a21575bf0c3636f5e4ba3452564b66890c53c22718078`; 40 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [ascending-exclusive-increment](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L3) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [ascending-exclusive-add](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L6) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [ascending-inclusive-increment](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L9) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [ascending-inclusive-add](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L12) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [descending-exclusive-decrement](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L15) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [descending-exclusive-subtract](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L18) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [descending-inclusive-decrement](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L21) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [descending-inclusive-subtract](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L24) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [omitted-initializer](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L31) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [parenthesized-number](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L34) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |
| [parenthesized-mutated-counter](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/c_style_for.swift#L38) | incompatible_feature | Swift removal diagnostic for C-style loop syntax; Minyar supports range/List/Text iteration, and Swift fix-it wording is not its contract. |

### [test/stmt/defer.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift)

SHA256 `5834a160f7b719a795d478ce300c2aa3894621b7a9115c94757326e12991a4d3`; 163 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [voidReturn1 / breakContinue](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L3) | upstream_helper_or_harness | Empty and non-void helpers support defer diagnostics; they are not standalone passing runtime cases. |
| [testDefer](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L6) | incompatible_feature | Deferred bodies may not transfer control out of their scope; Minyar has no defer statement. |
| [SomeTestClass.method](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L24) | incompatible_feature | Implicit self mutation and immediately executed defer warning require class/defer semantics. |
| [DeferThrowError](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L30) | upstream_helper_or_harness | Error enum provides exception values for the following defer cases. |
| [throwInDefer](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L34) | incompatible_feature | Exception escaping defer is rejected; neither exception nor defer syntax exists in Minyar. |
| [throwInDeferOK1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L39) | incompatible_feature | Nested do/catch catches an exception inside defer. |
| [throwInDeferOK2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L48) | incompatible_feature | Throwing outer function does not change nested caught defer behavior. |
| [throwingFuncInDefer1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L57) | incompatible_feature | Marked throwing call still escapes defer. |
| [throwingFuncInDefer1a](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L62) | incompatible_feature | Nested catch handles marked throwing call inside defer. |
| [throwingFuncInDefer2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L71) | incompatible_feature | Unmarked throwing call produces defer escape diagnostic. |
| [throwingFuncInDefer2a](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L76) | incompatible_feature | Nested catch does not waive missing-try diagnostic. |
| [throwingFuncInDefer3](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L89) | incompatible_feature | Nonthrowing parent rejects throwing defer escape. |
| [throwingFuncInDefer3a](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L94) | incompatible_feature | Nonthrowing parent accepts locally caught marked throw. |
| [throwingFuncInDefer4](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L103) | incompatible_feature | Nonthrowing parent and unmarked throwing defer call are invalid. |
| [throwingFuncInDefer4a](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L108) | incompatible_feature | Locally caught call still requires try spelling. |
| [throwingFunctionCalledInDefer](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L121) | incompatible_feature | Helper explicitly throws the error enum. |
| [SomeDerivedClass.init](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L125) | incompatible_feature | Superclass initializer chaining cannot be nested in defer. |
| [badForwardReference](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/defer.swift#L134) | incompatible_feature | Deferred capture cannot forward-reference nested locals; no defer/capture syntax. |

### [test/stmt/errors.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift)

SHA256 `7b80de9e66e0a8b493c0d3f89660a48c432309ec32dc1312dd3a12f098af2909`; 272 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [MSV](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L2) | upstream_helper_or_harness | Error enum and domain/code helper members. |
| [a / b / c / d / e / thrower / opaque_error](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L9) | upstream_helper_or_harness | No-op and throwing/existential helper declarations support catch tests. |
| [one](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L18) | incompatible_feature | Nonthrowing function directly throws an enum. |
| [two](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L22) | incompatible_feature | Nonthrowing function throws existential Error. |
| [three](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L26) | incompatible_feature | Typed catch is not exhaustive for existential Error. |
| [four](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L34) | incompatible_feature | Catch-all variable binding handles Error. |
| [five](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L42) | incompatible_feature | Typed catch plus wildcard is exhaustive. |
| [six](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L51) | incompatible_feature | Outer wildcard handles a nested partial catch. |
| [seven_helper](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L62) | incompatible_feature | Throwing Integer helper for accessor cases. |
| [seven.x/y/z](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L64) | incompatible_feature | Getter catches, force-tries, or optional-tries exception. |
| [eight.x/y/z](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L82) | incompatible_feature | Lazy closure getters exercise the same three error forms. |
| [multiPattern](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L100) | incompatible_feature | Multiple catch patterns include wildcard. |
| [ThrowingProto / testExistential / testGeneric](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L108) | incompatible_feature | Protocol existential and generic throwing calls. |
| [nine_helper / nine](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L123) | incompatible_feature | Missing positional argument should not trigger unrelated useless-try warning. |
| [ten_helper overloads / ten](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L127) | incompatible_feature | Overload resolution with missing argument should not add useless-try warning. |
| [eleven_helper / eleven_one](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L134) | incompatible_feature | Catch Error is always true within nonthrowing closure. |
| [eleven_two](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L144) | incompatible_feature | Partial catch makes closure throwing and invalid for nonthrowing parameter. |
| [Twelve / twelve_helper / twelve](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L153) | incompatible_feature | Enum-range catch pattern does not conform to Error and closure remains throwing. |
| [Thirteen / equality / thirteen_helper / thirteen](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L164) | incompatible_feature | Error existential equality pattern and closure conversion diagnostics. |
| [ClassProto / unrelated-struct-catch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L179) | incompatible_feature | Unrelated struct cast warning differs from Error-conforming struct catch. |
| [class-catch-and-error-composition](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L198) | incompatible_feature | Nonfinal classes can gain Error conformance; existential cast rules. |
| [generic conditional Error cast](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L219) | incompatible_feature | Type parameter can be a valid runtime Error cast target. |
| [P / superclass-and-final-existential-cast](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L225) | incompatible_feature | Open superclass cast is accepted but final unrelated class warns. |
| [invalid_interpolation](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L240) | incompatible_feature | Throwing interpolation must be marked/handled by enclosing function. |
| [valid_interpolation](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L247) | incompatible_feature | Throwing parent handles both outer-try and interpolated-try forms. |
| [takesClosure / passesClosure](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L254) | incompatible_feature | Throwing trailing-closure call requires error handling. |
| [S.packTest / S.test](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors.swift#L261) | incompatible_feature | Typed parameter packs do not waive throwing call handling. |

### [test/stmt/errors_async.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_async.swift)

SHA256 `97abc1bab0961280e43c3cf83bba17eb689e5cd9bcb0f4a12fd4612941b0aea6`; 15 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [MyError](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_async.swift#L5) | upstream_helper_or_harness | Error enum supplies a thrown continuation result. |
| [shouldThrow](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_async.swift#L10) | incompatible_feature | Unsafe throwing continuations, async and catch exhaustiveness are unsupported. |

### [test/stmt/errors_nonobjc.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_nonobjc.swift)

SHA256 `30d47bad92e16967afa73ee6af07ec439da22b5a5b3ffbc656f121c12edbe534`; 17 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [Foundation module harness](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_nonobjc.swift#L1) | upstream_helper_or_harness | Builds a synthetic Foundation input module on non-ObjC platforms; input directory remains pending. |
| [bar](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_nonobjc.swift#L10) | upstream_helper_or_harness | Throwing helper declaration. |
| [foo](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_nonobjc.swift#L12) | incompatible_feature | NSError bridging and catch exhaustiveness on non-ObjC platforms have no Minyar ABI equivalent. |

### [test/stmt/errors_objc.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_objc.swift)

SHA256 `1f8501074868815de28d246e17eff6172287bc3cadb221f638fcdf6f7b6649f1`; 14 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [mock SDK / Foundation harness](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_objc.swift#L1) | upstream_helper_or_harness | Requires Objective-C interoperability and mock SDK. |
| [bar](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_objc.swift#L7) | upstream_helper_or_harness | Throwing helper declaration. |
| [foo](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/errors_objc.swift#L9) | incompatible_feature | NSError exhaustive catch is an ObjC bridging rule, not Minyar ownership behavior. |

### [test/stmt/foreach.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift)

SHA256 `c0a828dd05da1936cb01c6d6ded22fb3a93e8c5ac972304f61ed78600c643c31`; 366 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [BadContainer1 / bad_containers_1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L4) | semantic_subset_candidate | Nominal nonsequence record rejection can map to invalid Minyar for input; Swift protocol-conformance wording excluded. |
| [BadContainer2 / bad_containers_2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L11) | incompatible_feature | Invalid Sequence conformance because generate field is not iterator. |
| [BadContainer3 / bad_containers_3](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L19) | incompatible_feature | Void makeIterator cannot infer nominal IteratorProtocol type. |
| [BadIterator1 / BadContainer4 / bad_containers_4](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L27) | incompatible_feature | Declared iterator does not conform to IteratorProtocol. |
| [GoodRange / GoodTupleIterator / ElementProtocol](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L40) | upstream_helper_or_harness | Custom generic and tuple sequence helpers are unsupported fixtures. |
| [patterns scalar element inference](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L58) | semantic_subset_candidate | Homogeneous Integer iteration/addition is compatible subset; typed patterns and protocols excluded. |
| [patterns tuple destructuring](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L66) | incompatible_feature | Tuple iterator binding and element conversion diagnoses require tuple patterns. |
| [slices](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L81) | compatible_port_candidate | Nested array iteration and running sum map to nested Lists; no Swift copy-on-write mutation inference. Test: `test_nested_integer_iterations_preserve_running_sum`; drafted_not_executed; ordinary stated semantic subset only. |
| [discard_binding](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L92) | compatible_port_candidate | Discarded for binding can map to unused ordinary Minyar identifier; underscore exact syntax to be checked. |
| [X / Gen / Seq / sequence helper overloads](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L96) | upstream_helper_or_harness | Generic, optional and overloaded sequence producers supply inference tests. |
| [testForEachInference](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L120) | incompatible_feature | Contextual iterator generic/overload/optional/range-integer-width inference differs from Minyar. |
| [testMatchingPatterns](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L154) | incompatible_feature | Optional case and subclass type patterns in for-in require pattern matching/class hierarchy. |
| [testOptionalSequence](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L172) | incompatible_feature | Optional container unwrapping diagnostic requires Optional. |
| [testExistentialSequence](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L178) | incompatible_feature | Existential Sequence dynamic dispatch unsupported. |
| [testForEachWithAnyCollection](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L185) | incompatible_feature | Implicit existential opening for Collection unsupported. |
| [P / RepeatedSequence / RepeatedIterator / conditional extensions](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L192) | upstream_helper_or_harness | Protocol-constrained conditional generic iterator fixture. |
| [testRepeated](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L226) | semantic_subset_candidate | Repeated values could map to explicit List; conditional-conformance checking is excluded. |
| [tuple-pattern-element-mismatch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L232) | incompatible_feature | Tuple destructuring diagnostic for scalar/wrong-arity elements. |
| [testForEachWhereWithClosure](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L244) | incompatible_feature | Where clause captures loop variable in generic closures and nested contains closure. |
| [test_no_ambiguity_with_prefix_iterator](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L254) | incompatible_feature | Generic Collection prefix overload ambiguity is absent in Minyar. |
| [nonsequence-tuple-input](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L261) | incompatible_feature | Tuple iteration rejection has no tuple syntax equivalence. |
| [empty-array-tuple-pattern](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L267) | incompatible_feature | Any inference plus three-element tuple pattern rejection. |
| [String-array-tuple-pattern](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L272) | incompatible_feature | Tuple mismatch diagnostic must retain String element type. |
| [Base / Child / Range / filtered Set loop](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L277) | incompatible_feature | Class inheritance, Set and where-filtered type inference unsupported. |
| [Optional data filtered loop function/closure](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L300) | incompatible_feature | Optional coalescing and closure/where inferred binding must not become Optional. |
| [variadic pack where rejection](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L321) | incompatible_feature | Repeat-each pack iteration deliberately forbids where. |
| [nested pack iteration binding](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L334) | incompatible_feature | Generic packs need independent nested environments. |
| [enumerated range-slice tuple binding](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L346) | incompatible_feature | Range slice and enumerated tuple pattern annotations are Swift-specific. |
| [testInvalidPreamble](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/foreach.swift#L356) | semantic_subset_candidate | Malformed iterator source must not crash; Swift continues multiple diagnoses in one file, while Minyar stops at first error. |

### [test/stmt/if_unexpected_else.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_unexpected_else.swift)

SHA256 `100fd3d184a758cef101f6cc2c4caadc74dc68c061258d95e2dd27962a9ac369`; 5 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [else immediately after condition](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_unexpected_else.swift#L3) | compatible_port_candidate | Malformed ordinary if can map to a Minyar syntax diagnostic; exact Swift repair/fix-it is excluded. Test: `test_missing_if_else_while_braces_reject_without_output`; drafted_not_executed; ordinary stated semantic subset only. |

### [test/stmt/if_while_var.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift)

SHA256 `ec5b5963c670402f0095207face71f1471f14acf62067a9b61d1ec2fbd52243c`; 309 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [NonOptionalStruct / Enum / binding helpers](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L3) | upstream_helper_or_harness | Optional and inout helpers supply conditional-binding diagnostics. |
| [let optional binding immutable](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L12) | incompatible_feature | Swift let immutability and inout checking differ from Minyar mutable let. |
| [binding-outside-scope](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L17) | semantic_subset_candidate | Ordinary block-local scope rejection compatible; Optional binding syntax excluded. |
| [var optional binding mutable](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L19) | incompatible_feature | Optional conditional unwrap and var declaration unavailable. |
| [missing-shorthand-bindings](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L24) | incompatible_feature | If-let/var shorthand name lookup unsupported. |
| [nonoptional conditional-bindings](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L34) | incompatible_feature | Optional-only binding initializer rule including guard shorthand. |
| [property-shorthand invalid identifier](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L45) | incompatible_feature | Conditional unwrapping requires identifier and Optional value. |
| [discard-pattern-nonoptional-binding](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L53) | incompatible_feature | Optional binding underscore rule unsupported. |
| [if-case missing initializer / nonoptional patterns](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L56) | incompatible_feature | Optional enum case patterns and initializer requirements unsupported. |
| [typed shorthand unwrap](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L64) | incompatible_feature | Optional wrapped String vs Integer type checks require Optional. |
| [B / D / malformed binding recovery](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L70) | incompatible_feature | Closure-valued malformed if-let and class typo recovery. |
| [binding-else-scope](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L82) | semantic_subset_candidate | Branch-local binding must not leak to sibling/else; adapt ordinary block binding only. Test: `test_branch_binding_does_not_leak_to_siblings`; drafted_not_executed; ordinary stated semantic subset only. |
| [shorthand let versus var mutation](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L99) | incompatible_feature | Swift let immutable vs var mutable unwrap; Minyar let is mutable. |
| [unused optional binding warning](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L111) | incompatible_feature | Swift warning/fix-it suggests Boolean nil check; no corresponding warning contract. |
| [nonoptional Integer unwrap](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L114) | incompatible_feature | Optional-only conditional binding and pattern unwrap rules. |
| [multiple conditional clauses](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L119) | incompatible_feature | Comma-separated optional binding clauses unsupported. |
| [leading Boolean and missing-let clause](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L124) | incompatible_feature | Multi-clause syntax and fix-it require optional binding. |
| [typed pattern additional Optional level](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L131) | incompatible_feature | Explicit Optional annotation changes unwrap depth. |
| [error-recovery Boolean clauses](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L140) | semantic_subset_candidate | Malformed plain conditions may become no-crash seeds; comma/closure condition semantics excluded. |
| [malformed nested conditional preamble](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L148) | semantic_subset_candidate | Invalid nested if and undefined names can map to targeted Minyar no-crash/rejection seeds. |
| [testIfCase](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L154) | incompatible_feature | Optional patterns and case-let spelling/warnings unsupported. |
| [testTypeAnnotations](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L173) | incompatible_feature | Optional construction and typed wildcard pattern diagnostics. |
| [testShadowing](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L180) | incompatible_feature | Guard/if optional shadowing and ternary initializer dependencies unsupported. |
| [testShadowingWithShorthand](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L189) | incompatible_feature | Shorthand Optional guard/if shadowing unsupported. |
| [testWhileScoping](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L200) | semantic_subset_candidate | Loop-local scope cannot leak; use ordinary body-local binding, exclude while-let. Test: `test_loop_body_binding_does_not_escape_its_scope`; drafted_not_executed; ordinary stated semantic subset only. |
| [testWhileShorthand](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L205) | incompatible_feature | While optional shorthand unwrap is not Minyar syntax. |
| [SomeParseResult.error/error2/error3](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L210) | incompatible_feature | Generic enum associated-value labeled pattern matching unsupported. |
| [SomeParseResult.repeated/repeated2/repeated3/repeated4/repeated5](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L230) | incompatible_feature | Tuple enum payload labels and mismatch diagnostics unsupported. |
| [matchImplicitTupling](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L266) | incompatible_feature | Deprecated implicit enum payload tuple binding unsupported. |
| [CaseStaticAmbiguity](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L274) | incompatible_feature | Enum case wins over same-named static overload during pattern resolution. |
| [HasPayload / UsesPayload.deinit](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L286) | incompatible_feature | Optional enum pattern in class destructor and static-case overload ambiguity unsupported. |
| [coalesced nonoptional initializer](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/if_while_var.swift#L305) | incompatible_feature | Nil-coalescing can turn Optional into nonoptional and invalidate unwrap. |

### [test/stmt/nonexhaustive_switch_stmt_editor.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/nonexhaustive_switch_stmt_editor.swift)

SHA256 `152a56a15635f3ca57fa4dcfd87e0f8e0e3f7a95fac8d73bb67b45b8edbe5a38`; 44 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [NonExhaustive](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/nonexhaustive_switch_stmt_editor.swift#L3) | upstream_helper_or_harness | Public resilient enum supplies cases. |
| [missing-known-case](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/nonexhaustive_switch_stmt_editor.swift#L11) | incompatible_feature | Switch must cover enum case b. |
| [known-cases-without-unknown-default](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/nonexhaustive_switch_stmt_editor.swift#L20) | incompatible_feature | Library evolution requires a future-case default outside the module. |
| [empty-switch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/nonexhaustive_switch_stmt_editor.swift#L25) | incompatible_feature | Editor diagnostics and individual fix-its for known/future cases. |
| [plain-default](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/nonexhaustive_switch_stmt_editor.swift#L33) | incompatible_feature | Default covers future enum cases. |
| [unknown-case-wildcard](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/nonexhaustive_switch_stmt_editor.swift#L39) | incompatible_feature | Unknown case wildcard covers future cases. Minyar has no switch or resilient enums. |

### [test/stmt/pack_iteration.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/pack_iteration.swift)

SHA256 `9ad4803e2ce576d473609a18917ad020907b1b79665bc050de2de284b0f34db6`; 11 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [variadic nested closure binding](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/pack_iteration.swift#L5) | incompatible_feature | Generic parameter packs, repeat-each iteration and nested function environments are unsupported. |

### [test/stmt/rdar40400251.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/rdar40400251.swift)

SHA256 `62ea76738ffd136a302539be19e15a8c2307422a00bc8939b17c563ea50bc825`; 38 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [E1 / E2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/rdar40400251.swift#L3) | upstream_helper_or_harness | Recursive enum and tuple-associated case create large exhaustiveness space. |
| [foo](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/rdar40400251.swift#L19) | incompatible_feature | Large tuple enum switch must still diagnose missing bar case. |
| [bar](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/rdar40400251.swift#L29) | incompatible_feature | Tuple wildcard case does not cover bar/baz; no Minyar pattern switch. |

### [test/stmt/statements.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift)

SHA256 `663a6d70e6e6299d8a8d50420c2006557bcb74cff6ec0db94f6e5cd84c2a6a88`; 633 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [nested comment / helper declarations](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L3) | semantic_subset_candidate | Nested comment and ordinary call parsing compatible; generic markUsed helper excluded. |
| [invalid_semi](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L12) | semantic_subset_candidate | Swift bans standalone empty semicolon; Minyar contract must be checked before adopting that diagnostic. |
| [nested1/nested2 capture](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L16) | incompatible_feature | Nested function captures outer local and parameter; unsupported closures/nested function declaration. |
| [funcdecl5 while/if spacing](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L27) | compatible_port_candidate | Ordinary nested Boolean conditions and while/if spacing map; unused-literal warnings excluded. |
| [funcdecl5 assignment targets](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L39) | semantic_subset_candidate | Mutable variable assignment and rejection of literal targets compatible; tuple targets and Swift let immutability excluded. |
| [funcdecl5 Boolean-only conditions](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L55) | compatible_port_candidate | Integer condition must not act as Boolean; already represented in reachability negative controls for while, if port pending. Test: `test_ordinary_if_requires_boolean`; drafted_not_executed; ordinary stated semantic subset only. |
| [infloopbool / infloopbooltest](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L96) | semantic_subset_candidate | Nominal record condition rejection compatible; self-returning class/property conversion rules excluded. |
| [Int / SomeGeneric builder chains](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L106) | incompatible_feature | Extensions, generic self and static chained builder members unsupported. |
| [top-level break and continue](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L128) | compatible_port_candidate | Loop jumps outside loops must reject; exact Swift allowance for switch/if/do excluded. Test: `test_jumps_outside_loops_reject_even_in_ordinary_if`; drafted_not_executed; ordinary stated semantic subset only. |
| [function inside loop cannot jump outward](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L130) | incompatible_feature | Nested functions form control boundary, but Minyar does not allow their declaration. |
| [labeled if inside loop](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L136) | incompatible_feature | Labeled if break/continue rules absent in Minyar. |
| [labeled outer if](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L145) | incompatible_feature | Unlabeled jump rules depend on labeled Swift if. |
| [bare do break](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L153) | incompatible_feature | Do-scope jump is unsupported syntax. |
| [tuple_assign](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L157) | incompatible_feature | Tuple assignment and nested tuple destructuring unsupported. |
| [missing_semicolons](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L165) | semantic_subset_candidate | Adjacent ordinary calls/assignments can yield rejection seeds; local classes/functions and Swift fix-its excluded. |
| [top-level value/void return](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L178) | semantic_subset_candidate | Need existing Minyar top-level contract before port; Swift function-only return rule cannot be presumed. |
| [NonVoidReturn1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L182) | compatible_port_candidate | Value-returning function needs return value; Minyar matching diagnosis can be tested. Test: `test_value_return_requires_a_value`; drafted_not_executed; ordinary stated semantic subset only. |
| [NonVoidReturn2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L187) | compatible_port_candidate | Malformed unary expression after return should reject without crash; exact recovery excluded. |
| [VoidReturn1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L192) | compatible_port_candidate | Early void return and semicolon after return compatible. Test: `test_void_return_call_preserves_effect_order`; drafted_not_executed; ordinary stated semantic subset only. |
| [VoidReturn2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L198) | incompatible_feature | Explicit Unit tuple value is Swift-specific; Minyar Void has no unit literal. |
| [VoidReturn3](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L202) | compatible_port_candidate | Returning a Void call maps to existing Rust-derived void-call regression. Test: `test_void_return_call_preserves_effect_order`; drafted_not_executed; ordinary stated semantic subset only. |
| [IfStmt1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L208) | compatible_port_candidate | Missing if body opening brace rejection. Test: `test_missing_if_else_while_braces_reject_without_output`; drafted_not_executed; ordinary stated semantic subset only. |
| [IfStmt2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L213) | compatible_port_candidate | Else must have a body or if; rejection without Swift fix-it. Test: `test_missing_if_else_while_braces_reject_without_output`; drafted_not_executed; ordinary stated semantic subset only. |
| [IfStmt3](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L218) | compatible_port_candidate | Else followed by condition without if rejects; no syntax change needed. Test: `test_missing_if_else_while_braces_reject_without_output`; drafted_not_executed; ordinary stated semantic subset only. |
| [WhileStmt1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L228) | compatible_port_candidate | Missing while opening brace rejects. Test: `test_missing_if_else_while_braces_reject_without_output`; drafted_not_executed; ordinary stated semantic subset only. |
| [DoStmt](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L234) | incompatible_feature | Swift do statement unsupported. |
| [DoWhileStmt1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L241) | incompatible_feature | Removed do-while spelling diagnosis is not Minyar statement syntax. |
| [DoWhileStmt2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L248) | incompatible_feature | Separate do then while supported only by Swift do statement. |
| [LabeledDoStmt](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L257) | incompatible_feature | Labeled block requires do in Swift; no labels in Minyar. |
| [RepeatWhileStmt1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L264) | incompatible_feature | Repeat-while loops and control targets unsupported. |
| [RepeatWhileStmt2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L273) | incompatible_feature | Malformed repeat statement recovery unsupported syntax. |
| [RepeatWhileStmt4](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L277) | incompatible_feature | Malformed repeat condition is Swift-specific. |
| [brokenSwitch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L283) | incompatible_feature | Nonexistent enum-style case for Integer and switch exhaustiveness unsupported. |
| [switchWithVarsNotMatchingTypes](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L290) | incompatible_feature | Shared pattern-bound variable types must match tuple switch arms. |
| [breakContinue labeled loops/switch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L300) | incompatible_feature | Labels, switch jump behavior and label shadowing differ from ordinary Minyar loop targets. |
| [breakContinue unreachable statement after break](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L324) | semantic_subset_candidate | Ordinary Minyar while break followed by named call can check parser and lexical dead context; switch excluded. Test: `test_dead_call_after_break_remains_a_statement`; drafted_not_executed; ordinary stated semantic subset only. |
| [breakContinue Optional switch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L334) | incompatible_feature | Some42 and nil cannot exhaust every Optional Integer. |
| [MyEnumWithCaseLabels / testMyEnumWithCaseLabels](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L347) | incompatible_feature | Associated enum payload labels and reordering diagnostics. |
| [test_guard](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L362) | incompatible_feature | Guard Optional patterns, scoped unwrap and multi-clause conditions unsupported. |
| [test_is_as_patterns](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L395) | incompatible_feature | Type-test switch pattern warnings unsupported. |
| [matching_pattern_recursion](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L405) | incompatible_feature | Closure expression inside switch pattern plus unknown loop input crash recovery. |
| [r18776073](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L422) | incompatible_feature | Switch nil arm needs executable statement; no pattern switches. |
| [testThrowNil](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L430) | incompatible_feature | Thrown nil cannot infer Error; no exceptions or nil. |
| [r23684220](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L438) | incompatible_feature | Invalid Any coalescing Optional binding must retain AST; no matching feature. |
| [f21080671](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L445) | incompatible_feature | Try/catch typo repair requires exception regions. |
| [f availability / multi-clause condition](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L459) | incompatible_feature | Swift availability and conditional binding need comma instead of &&. |
| [Type / r25178926](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L471) | incompatible_feature | Where applies only to final multi-case pattern and affects exhaustiveness. |
| [testAmbiguousWhereInCatch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L507) | incompatible_feature | Multiple catch patterns have same where ambiguity; no exceptions/patterns. |
| [top-level guard break](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L535) | incompatible_feature | Guard/do unlabeled-break allowance unsupported. |
| [fn(a) guard break](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L541) | incompatible_feature | Guard statement absent; cannot port outer jump rule unchanged. |
| [fn(x) nested guard break](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L547) | incompatible_feature | Nested guard scopes and labeled if allowance unsupported. |
| [bad_if](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L558) | semantic_subset_candidate | Integer cannot be Boolean is compatible; tuple/nil expressions excluded. Test: `test_ordinary_if_requires_boolean`; drafted_not_executed; ordinary stated semantic subset only. |
| [unknown loop labels / typo corrections](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L565) | incompatible_feature | For/while/repeat labeled-jump diagnostics and edit distance fix-its unsupported. |
| [ambiguous nested label corrections](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L598) | incompatible_feature | Nested label candidates in three loop kinds unsupported. |
| [class / case EOF parser recovery](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/statements.swift#L629) | incompatible_feature | Enum case declaration outside enum and incomplete class recovery unsupported syntax. |

### [test/stmt/switch_nil.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_nil.swift)

SHA256 `7372cc7b5a08b4e7fc19201f1c5abcf382c259627fc8bc8d5c9dcf5cb1f7b06c`; 30 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [test](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_nil.swift#L7) | incompatible_feature | Nonoptional enum cannot match nil; Minyar has no nil pattern/switch. |
| [Nilable](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_nil.swift#L16) | upstream_helper_or_harness | ExpressibleByNilLiteral helper defines a nominal nil conversion. |
| [testNil](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_nil.swift#L20) | incompatible_feature | Subject conversion to Optional during pattern match is Swift-specific. |

### [test/stmt/switch_stmt1.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt1.swift)

SHA256 `3f52e8b3028a301e683a6bda78e3dfb37989b77e3db219019f394dd124f6abe5`; 14 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [E](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt1.swift#L3) | upstream_helper_or_harness | Two-case enum fixture. |
| [foo1-enum-empty-switch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt1.swift#L8) | incompatible_feature | Enum exhaustiveness diagnostic requires switch. |
| [foo1-integer-empty-switch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt1.swift#L13) | incompatible_feature | Integer switch requires case/default; no switch statement in Minyar. |

### [test/stmt/switch_stmt2.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift)

SHA256 `48fefea6f5dbc8975931f037c33bdae64cb442228e2fca6d7d0d5168ef817106`; 154 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [E](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L3) | upstream_helper_or_harness | Two-case enum fixture. |
| [foo1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L8) | incompatible_feature | Missing enum case is diagnosed despite a return arm. |
| [foo2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L15) | incompatible_feature | Single integer case cannot exhaust all integers. |
| [testSwitchEnumOptionalNil](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L25) | incompatible_feature | some plus nil exhaust an Optional enum. |
| [testSwitchEnumBool](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L36) | semantic_subset_candidate | Boolean two-way total control can map to if/else; switch diagnostics remain incompatible. |
| [testSwitchOptionalBool](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L67) | incompatible_feature | Optional Boolean includes none plus two wrapped cases. |
| [testSwitchEnumBoolTuple](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L91) | incompatible_feature | Tuple Boolean exhaustiveness and partial-pattern diagnostics require tuple matching. |
| [non_fully_covered_switch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L130) | incompatible_feature | Integer switch missing default is Swift syntax/analysis. |
| [fallthrough_not_last](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/switch_stmt2.swift#L143) | incompatible_feature | Dead nested switch after fallthrough must not crash; Minyar has no switch/fallthrough. |

### [test/stmt/then_stmt.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift)

SHA256 `ff5bb4cfa9d1351836e911653457f6fbc80b39d18c65f5bcffcad421950413b4`; 218 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [then helper](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L7) | upstream_helper_or_harness | Ordinary default-argument/closure function shares contextual spelling. |
| [testThenStmt invalid positions and values](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L9) | incompatible_feature | Experimental then is valid only at final statement of if/switch/do expressions. |
| [testThenStmt producing conditional values](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L29) | incompatible_feature | Then evaluates expression branches; Minyar if is a statement. |
| [testThenStmt labeled then](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L38) | incompatible_feature | Then statement cannot receive label; labels unsupported. |
| [testThenFunctionCalls](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L46) | semantic_subset_candidate | Ordinary then function name could map; Swift trailing closures/default arguments excluded. |
| [testThenLabel](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L55) | incompatible_feature | Labeled loop named then and binding with same spelling require labels. |
| [S declarations](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L62) | upstream_helper_or_harness | Contextual property/method/subscript fixture. |
| [testThenAsMember invalid bare statement](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L68) | incompatible_feature | Statement then newline/semicolon parsing recovery is experimental Swift syntax. |
| [testThenAsMember ordinary expressions](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L88) | semantic_subset_candidate | Ordinary variable named then can be used in arithmetic, assignments and fields; casts/optional/regex excluded. Test: `test_contextual_swift_spellings_remain_ordinary_names`; drafted_not_executed; ordinary stated semantic subset only. |
| [testThenSubscript](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L123) | semantic_subset_candidate | Ordinary local named then can be indexed in Minyar List; Swift custom subscript excluded. Test: `test_contextual_swift_spellings_remain_ordinary_names`; drafted_not_executed; ordinary stated semantic subset only. |
| [testOutOfPlace](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L129) | incompatible_feature | Nested if/guard may not produce then except expression-tail contexts. |
| [testNested1](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L146) | incompatible_feature | Nested if/switch expressions implicitly forward then value. |
| [testNested2](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L163) | incompatible_feature | Then explicit nested conditional expression result. |
| [testNested3](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L180) | incompatible_feature | Effects before nested then expression maintain expression-tail rule. |
| [throwingFn](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L200) | upstream_helper_or_harness | Throwing helper for try placement. |
| [testTryOnThen](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L202) | incompatible_feature | Try belongs on produced expression, not experimental then statement. |
| [testReturnTryThen](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt.swift#L216) | semantic_subset_candidate | Returning parameter spelled then compatible subset; useless-try warning excluded. |

### [test/stmt/then_stmt_disabled.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt_disabled.swift)

SHA256 `5b05cf032c902f9640b93f26596e5dfcac6bca8cc39b0c6d5f4d5d03cf328298`; 11 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [disabled experimental then](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt_disabled.swift#L4) | incompatible_feature | Disabled ThenStatements expression keyword diagnostics require an experimental Swift feature. |

### [test/stmt/then_stmt_exec.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt_exec.swift)

SHA256 `e91eba54738a448eea327de0164d249e9d9107f92b52dde5b8c896ceed9c25f3`; 76 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [testDeferIf](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt_exec.swift#L9) | incompatible_feature | Then expression exits run nested defer before enclosing statements. |
| [testDeferSwitch](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt_exec.swift#L32) | incompatible_feature | Switch fallthrough runs each case defer and outer defer in specified order. |
| [testFallthrough](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/then_stmt_exec.swift#L61) | incompatible_feature | Assignment state across switch fallthrough and then expression yields six; no matching Minyar features. |

### [test/stmt/typed_throws.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift)

SHA256 `d9cf91a07750d0d6a313ecb2a812c2d0c6d852e2005716aebd635be8120b3390`; 420 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [MyError / HomeworkError / error helpers](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L5) | upstream_helper_or_harness | Typed error enum fixtures and throwing calls. |
| [testDoCatchErrorTyped](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L20) | incompatible_feature | Catch variable inferred from thrown type, heterogeneous errors erase to any Error, partial catch rethrows. |
| [testDoCatchMultiErrorType](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L80) | incompatible_feature | Multiple error types erase enum member context to existential Error. |
| [testDoCatchRethrowsUntyped](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L92) | incompatible_feature | Partial typed catch can convert remainder to untyped error propagation. |
| [testDoCatchRethrowsTyped](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L99) | incompatible_feature | Typed parent must not propagate MyError or erased any Error as HomeworkError. |
| [testTryIncompatibleTyped](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L126) | incompatible_feature | Try sites and Never catch checked against explicit parent error type. |
| [doSomethingWithoutThrowing / testDoCatchWithoutThrowing](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L143) | incompatible_feature | Nonthrowing call warns useless try and unreachable catches. |
| [rethrowsLike / fromRethrows](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L155) | incompatible_feature | FullTypedThrows removes legacy rethrow-like generic compatibility. |
| [testDoCatchExplicitTyped](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L162) | incompatible_feature | Explicit do throws clause determines catch type and requires catch. |
| [tryBangQuestionMismatchingContext](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L185) | incompatible_feature | Forced/optional try consume errors while ordinary try propagates mismatched type. |
| [apply / testDoCatchErrorTypedInClosure](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L191) | incompatible_feature | Generic typed-throwing closure plus explicit typed do/catch inference. |
| [ThrowingMembers](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L206) | incompatible_feature | Typed throwing subscript and property getters. |
| [ThrowingStaticSubscript / globalIntOrThrows](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L216) | incompatible_feature | Static/global throwing getters and subscripts. |
| [testDoCatchInClosure call sites](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L230) | incompatible_feature | Closure error inference from call, direct throw, heterogeneous conditional, nested partial catch. |
| [testDoCatchInClosure getter sites](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L272) | incompatible_feature | Throwing instance/static subscript and property sites inform error type. |
| [throwing/nonthrowing autoclosure helpers](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L315) | upstream_helper_or_harness | Autoclosures plus generic Error/Never setup. |
| [throwingAutoclosures](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L322) | incompatible_feature | Implicit argument closure cannot convert erased Error to MyError or Never. |
| [noThrow](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L330) | incompatible_feature | Throws Never forbids both direct throw and throwing calls. |
| [LowerThanAssignment / ~~~](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L343) | upstream_helper_or_harness | Custom low-precedence operator supplies try scope checks. |
| [testSequenceExpr binary and assignment try scope](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L349) | incompatible_feature | Try/force-try spans AST expression sequence and assignment; async unsafe order warnings unsupported. |
| [testSequenceExpr conditional try scope](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L372) | incompatible_feature | Try on condition covers both ternary arms; try on one arm leaves other throw sites. |
| [testSequenceExpr unassignable/custom operator](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L380) | incompatible_feature | Try scope checked despite invalid mutability and lower-than-assignment operator folding. |
| [testSequenceExpr RHS try restrictions](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L387) | incompatible_feature | Try to right of nonassignment and folded AST region diagnostics. |
| [testSequenceExpr low precedence RHS try](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L404) | incompatible_feature | Low precedence operator truncates forced-try coverage, with three-way notes. |
| [testSequenceExpr conditional low precedence RHS try](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws.swift#L412) | incompatible_feature | Conditional operator boundary interacts with low-precedence throwing RHS. |

### [test/stmt/typed_throws_ast.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws_ast.swift)

SHA256 `65991d02d6942b11ef80b7749ba8dc5b8c0e94188928090a76675f1d0c81bf0b`; 51 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [MyError / HomeworkError](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws_ast.swift#L3) | upstream_helper_or_harness | Error enum declarations supply typed-throws AST payloads. |
| [homework](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws_ast.swift#L13) | incompatible_feature | Throwing getter accessor AST. |
| [printOrFail](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws_ast.swift#L19) | upstream_helper_or_harness | Typed throwing helper. |
| [throwsAnything](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws_ast.swift#L23) | incompatible_feature | AST checks distinguish typed-to-any conversion, forced try and optional try. |
| [doesNotThrow](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws_ast.swift#L41) | upstream_helper_or_harness | Nonthrowing helper. |
| [throwsNothing](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/typed_throws_ast.swift#L43) | incompatible_feature | AST records Never as thrown type of try! and try? for nonthrowing call. |

### [test/stmt/yield.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift)

SHA256 `60d267905c1226c18587df1938ed632ed19dc54b58702d338d8c2840b414a05b`; 107 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [YieldRValue.property](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L3) | incompatible_feature | Read accessor coroutine yield is not a Minyar feature. |
| [YieldVariables.property](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L12) | incompatible_feature | Read and inout modify accessor yields require coroutine storage semantics. |
| [YieldVariables.wrongTypes](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L22) | incompatible_feature | Read and modify yield values must match String type. |
| [YieldVariables.rvalue](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L32) | incompatible_feature | Cannot yield mutable reference to literal. |
| [YieldVariables.missingAmp](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L39) | incompatible_feature | Modify yield requires explicit address ampersand. |
| [HasProperty](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L48) | upstream_helper_or_harness | Associated-type protocol specifies getter/setter requirements. |
| [GenericTypeWithYields.property](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L53) | incompatible_feature | Generic Optional unwrap plus read/modify coroutine yield. |
| [GenericTypeWithYields.subscript](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L65) | incompatible_feature | Generic tuple coroutine temporary reference lifetime. |
| [yield / call_yield](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L77) | compatible_port_candidate | Ordinary function name yield remains callable; candidate for reserved/contextual-name coverage without accessor syntax. Test: `test_contextual_swift_spellings_remain_ordinary_names`; drafted_not_executed; ordinary stated semantic subset only. |
| [YieldInDefer](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L82) | incompatible_feature | Parser recovery for yield nested within defer. |
| [InvalidYieldParsing](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/yield.swift#L97) | incompatible_feature | Labeled and multiple coroutine yield argument diagnostics. |

### [test/stmt/Inputs/Foundation-with-NSError.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/Inputs/Foundation-with-NSError.swift)

SHA256 `630e080d9c27ee1467f27f1630bc96ed7e8c2065af8c0b2f9125b86aa1171434`; 1 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [synthetic Foundation NSError class](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/Inputs/Foundation-with-NSError.swift#L1) | upstream_helper_or_harness | Minimal Error-conforming class supports non-ObjC catch bridging fixture. Not an independent runtime ownership or Minyar class test. |

### [test/stmt/print/then_stmt.swift](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/print/then_stmt.swift)

SHA256 `07dde06c68c3836dc0ed4a4546bebeef9b72abfac8ac6ad797cd8fe427bd09ed`; 17 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| [foo explicit then versus implicit AST production](https://github.com/swiftlang/swift/blob/1ff1cc1170617ab23ab74aa8b741c8daca1903f6/test/stmt/print/then_stmt.swift#L5) | incompatible_feature | Experimental ThenStatements AST printing must preserve explicitly written then while omitting synthesized then in the else expression. Minyar has no expression-valued if/then or corresponding Swift AST print API. |

