# Pinned peer-test semantic review

Pinned source entries: **13**. Peers: **1**.

Complete immediate tests/ui/expr directory at the pinned Rust1.90.0 commit:12Rust sources and1diagnostic companion. Every body was read and each selected test/function unit has a disposition. This is not recursive or repository-wide Rust coverage;4files also appear in the original32-file selection and must not be double-counted.

`peers-inventory.json` retains additional
directory-discovered pending paths, including explicitly capped LLVM/Lean
listings. Source retrieval, reading, semantic disposition and validation
are recorded separately. Upstream sources and licenses are cached only in
`build/peer-research/sources`; new Minyar tests are original adaptations.

Reproduce retrieval with `python3 scripts/peer-research-sources.py --manifest research/2026-10-memory/peer-rust-expression-directory.json --fetch`.
Verify caches and regenerate this table with `python3 scripts/peer-research-sources.py --manifest research/2026-10-memory/peer-rust-expression-directory.json`.
Run adaptations with `python3 tests/peer-research-semantics.py` (O0 and O2).

## Rust: 1.90.0

Pinned commit `1159e78c4747b02ef996e55082b704c09b970588`. [License](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/LICENSE-MIT): MIT license selected from dual MIT/Apache licensing.

### [tests/ui/expr/block-fn.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/block-fn.rs)

SHA256 `f34a3cc0fb3fac435085f6ce10e639d75992ec15342c865fe02b8d23e33cff5e`; 9 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| test_fn | incompatible | Nested function declaration is bound as a first-class function item and then called; Minyar supports neither nested function declarations nor function-valued bindings. |

### [tests/ui/expr/block-generic.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/block-generic.rs)

SHA256 `ca61362009dce3ca8bd1de2a773cfa2ecd7ca78c58dbdd30fb6c7a2ef1129d8a`; 27 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| test_generic | incompatible | Generic Clone bound, higher-order FnOnce equality callback and standalone block expression; these language typing contracts have no Minyar equivalent. |
| test_bool | incompatible | Instantiates generic higher-order/block-expression probe for Bool; the central generic/callback contract is unsupported, even though scalar equality itself is supported. |
| test_rec | incompatible | Derive(Clone), generic callback and record value-copy behavior; Minyar managed record aliases do not imply this copy contract. |

### [tests/ui/expr/block.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/block.rs)

SHA256 `20e971da119e7ff5ec96ae0adcd115d1e56d541c7d23d99bdd8367f85312745d`; 18 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| test_basic | incompatible | Standalone block yields a Boolean expression for a binding; Minyar braces describe statements/record construction, not general block values. |
| test_rec | incompatible | Standalone block yields a record expression; replacing it with direct record construction would remove the expression-block contract being tested. |
| test_filled_with_stuff | incompatible | Block expression has local mutable loop state and yields its trailing binding; unsupported block values and implicit tail expressions. |

### [tests/ui/expr/copy.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/copy.rs)

SHA256 `f772e9a80cf4d0f3f665b167db148b2dcab9b92473008c6208b36468d691d929`; 18 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| main/f | incompatible | Rust Copy struct creates independent value storage. Minyar managed record aliases share mutation; matching expected independence would change semantics. |

### [tests/ui/expr/early-return-in-binop.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/early-return-in-binop.rs)

SHA256 `ecbe9331e93473b60cd912d7623f7a26096da7642eacba90c6522e1e65ae16ed`; 19 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| add_with_early_return | incompatible | Rust return is an expression and generic Add/Copy traits are used. Minyar return is a statement; do not introduce syntax to port it. |

### [tests/ui/expr/if-bot.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/if-bot.rs)

SHA256 `2e00a4ea409885a1a70bf0b2ce5e7aac084ff4eadd919f5f0788be266aedbca8`; 6 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| main | incompatible | If is a value expression whose panicking arm has bottom type and other arm supplies5; Minyar if is a statement and does not expose this expression type unification. |

### [tests/ui/expr/if-generic.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/if-generic.rs)

SHA256 `47dd8284c5c25449c1d1a5f4ac322042fa4249b8bcd652ff82ebf92298cdc995`; 29 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| test_generic | incompatible | Generic Clone/callback plus if expression yielding expected clone or alternate value; unsupported generics, function values and expression-valued if. |
| test_bool | incompatible | Generic Bool callback instantiation is central; ordinary Boolean equality is only a related scalar property. |
| test_rec | incompatible | Generic cloned record/alternate record passed through FnOnce comparison; Minyar managed alias/value-copy semantics differ. |

### [tests/ui/expr/if-panic-all.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/if-panic-all.rs)

SHA256 `46df9d474f9827e5cd477e0c38f4e0098905b16d9ac76e164a7b906458272f26`; 11 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| main | incompatible | Nested if expressions infer bottom type when both branches panic; unused outer else arm has no runtime effect. Minyar statement if does not implement this expression typing probe. |

### [tests/ui/expr/issue-22933-1.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/issue-22933-1.rs)

SHA256 `b1913d2172e26230cce492f222a5f1da0ddeb534080c45567a81a8baed1e43eb`; 23 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| CNFParser.is_whitespace | port_candidate | Character equality against space/newline is compatible as a standalone function; class impl/static method scope is excluded. |
| CNFParser.consume_whitespace | incompatible | Mutable self method passes an address of function item to dynamic Fn trait predicate; method/trait/function-value contracts are unsupported. |
| CNFParser.consume_while | incompatible | Borrowed dynamic predicate is called in while condition through mutable self; no Minyar callable trait object or method receiver equivalent. |

### [tests/ui/expr/issue-22933-2.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/issue-22933-2.rs)

SHA256 `7cd21557a755f001c18644afd2673c64bc1a09665fca32fa5225d49d11831e40`; 8 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| Delicious.ApplePie | incompatible | Negative enum-associated-item lookup distinguishes PIE from Pie and offers variant suggestion; Minyar has no enum/associated variant syntax. |

### [tests/ui/expr/issue-22933-2.stderr](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/issue-22933-2.stderr)

SHA256 `622e972638651ee138197dd74d967287bd1cfc584dd0b6f265caf57dae6563d8`; 18 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| expected E0599 diagnostic | incompatible | Exact Rust enum-associated-item error code/source highlighting/similar variant suggestion correspond to unsupported enum syntax. No Minyar diagnostic snapshot is claimed equivalent. |

### [tests/ui/expr/scope.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/scope.rs)

SHA256 `0c27f612f4111c391cb5528adcb09997716e7bfb07209511dc60163d4385c532`; 7 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| f/main | compatible_adaptation | A void call can finish a void function. Absolute :: scope is replaced by ordinary module-local resolution and the executable entry is separate. Test: `test_rust_scope_void_call_can_finish_a_void_function`; passed native O0 and O2, 2026-10-04 initial round. |

### [tests/ui/expr/weird-exprs.rs](https://github.com/rust-lang/rust/blob/1159e78c4747b02ef996e55082b704c09b970588/tests/ui/expr/weird-exprs.rs)

SHA256 `ea26f38c567eba8aee02a370ff8d4fef9729d4595de407f7a9cc6412a36e3e31`; 303 lines. Status: source_read_and_semantically_reviewed.

| Individual upstream unit | Disposition | Semantic mapping and evidence |
| --- | --- | --- |
| strange | incompatible | return expression in binding initializer |
| funny | incompatible | return expression in call argument |
| what | incompatible | closure and interior-mutability Cell plus loop expression |
| zombiejesus | incompatible | return expressions in loop/if/match conditions |
| notsure | incompatible | assignment expressions, unit comparison and mutable borrowing |
| canttouchthis | incompatible | unit expression comparison and return expression |
| angrydome | incompatible | break/continue as expressions and match |
| evil_lincoln | incompatible | unit-valued printing stored in a binding |
| dots | incompatible | range expressions and debug formatting |
| u8 | incompatible | macros, nested modules, lifetime generics and pattern destructuring |
| fishy | incompatible | generic empty argument lists and iterator collect |
| union | incompatible | Rust union and lifetime parameter |
| special_characters | incompatible | closures, tuple patterns, unit/range expressions |
| punch_card | incompatible | nested range expressions |
| match | incompatible | raw identifier and nested match expressions |
| i_yield | incompatible | coroutine and yield expressions |
| match_nested_if | incompatible | match guard and expression-valued nested if |
| monkey_barrel | incompatible | unit assignment expressions |
| continue | incompatible | Unicode identifiers, loop expressions and break values |
| function | incompatible | Deref trait and callable value chaining |
| bathroom_stall | incompatible | matches macro with assignment expression guard |
| closure_matching | incompatible | closure patterns and match |
| semisemisemisemisemi | incompatible | redundant semicolon parsing (Minyar statement separators differ; needs independent parser review) |
| useful_syntax | incompatible | nested brace import syntax |
| infcx | incompatible | recursive module re-exports |
| return_already | incompatible | return/break expressions and inferred Debug trait |
| fake_macros | incompatible | keyword macro delimiters and loop values |
| fish_fight | incompatible | traits, generics, qualified paths and higher-order functions |
| main | incompatible | invokes the incompatible expression/syntax probes; not a separate portable oracle |

