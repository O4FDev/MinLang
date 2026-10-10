# Individual pinned source-unit dispositions

Authoritative data: [peer-nim-koka-lean.json](peer-nim-koka-lean.json). Source cache hashes and three licenses verified; retrieval never supplied a review status. Selected review only, not upstream-suite execution or exhaustive language coverage. Every selected unit identifies a scenario, helper, assertion, theorem, golden or harness. Completed semantic subsets are linked in the authoritative manifest; unrelated adaptations remain pending.

## Nim v2.2.4

Commit `f7145dd26efeeeb6eeae6fff649db244d81b212d`. [Upstream license](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/copying.txt): MIT.

18 named ARC/ORC alias, move, cursor, control-flow and cycle regressions; excludes thread/async/custom-finalizer suites

### [tests/arc/taliased_reassign.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/taliased_reassign.nim)

SHA256 `b50daff25df0ae134ce7cd07414844bc6ac3c5ad60182a082f5bb6749bf97911`; 41 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| Dual D/+ and Tensor helpers | incompatible_direct_contract | Generic value-semantic Dual/Tensor and operator overloads absent; shared Minyar records differ. |
| loss aliased reassignment | reviewed_adaptation_pending | Fresh output element-wise sum can reproduce values; expected113 does not test custom generic move issue, pending semantic subset only. |

### [tests/arc/tarc_orc.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tarc_orc.nim)

SHA256 `5dca78271719ba9a8e5833578f9607f2e806e17c57036614bb2a04bb211a987b`; 188 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| initKeyPair pointer field initialization | incompatible_direct_contract | Raw pointers/fixed uint8 arrays and FFI addresses absent. |
| bug20303 projected index result | covered_existing_contract | Indexed managed result protection covered by ownership/regressions; template index syntax absent. |
| main empty seq branches static/runtime | covered_existing_contract | Empty List-return paths covered; compile-time execution unavailable. |
| bug tuple embedded seq mutation | reviewed_adaptation_pending | Can map tuple to record and sequence to shared List; fresh construction nested indexed mutation requires separate adaptation. |
| 21974 push/pop returned first alias | ported_semantic_subset | Preserve returned managed Item before overwriting the source slot, including same-slot control; capacity resizing/pop API not claimed. |
| 21987 custom EmbeddedImage/Image copy-sink hooks | incompatible_direct_contract | Custom destroy/dup/sink, distinct wrappers and value-copy semantics absent. |
| TestObj/TestSubObj destructor inheritance | incompatible_direct_contract | No class inheritance or user finalizers. |
| 23858 discarded cdecl result effect | reviewed_adaptation_pending | Discarded call side effect is meaningful, but calling convention hook absent; scalar peer-profiling effect test covers generic requirement. |
| 24147 inherited custom copy | incompatible_direct_contract | Inheritance and explicit custom copy hook absent. |

### [tests/arc/tcontrolflow.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tcontrolflow.nim)

SHA256 `159d8426089ea0c8e6ef28a4e13b893a502115241509c5ddcab3c94892c20e00`; 118 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| elifIsEasy constructor/destructor timing | incompatible_direct_contract | User destructor prints have no Minyar counterpart; early-drop timing intentionally incremental. |
| orIsHard false/true | covered_existing_contract | Short-circuit side-effect suppression covered by binary-expression-ownership.py; destructor output not mapped. |
| run MouseEvent protects data | covered_existing_contract | Stored shared reference and caller borrow covered by ownership nested records. |
| sysFatal/ifexpr expression-valued conditional | incompatible_direct_contract | Runtime compilerproc and expression-if syntax absent; Minyar bounds diagnostics independently tested. |
| escapeCheck template toSeq block result | incompatible_direct_contract | Expression-valued block/template unavailable; managed returned List protected by existing tests. |
| seqsEqual expression-local declarations | incompatible_direct_contract | Let declarations inside expression and Nim string equality code generation absent; scalar Text equality independently tested. |

### [tests/arc/tcursor_field_obj_constr.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tcursor_field_obj_constr.nim)

SHA256 `6c52c49772ff483ac79435fd86a42c105196eeb5dafa1b4d82f934c2c36a0aa4`; 44 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| NodeObj destroy output | incompatible_direct_contract | User destructors unavailable; order a,b,c cannot be an incremental reclamation oracle. |
| addNode/addEdge/main cursor graph | incompatible_direct_contract | Explicit unowned cursor edges require external owner graph; Minyar owns managed edges and forbids potentially cyclic recursive mutation. Cannot silently change edge ownership. |

### [tests/arc/tcursor_on_localvar.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tcursor_on_localvar.nim)

SHA256 `5940104f8f695027fb64b740f12e1a592a35d76468b59ea1a2afd87aa37b7b71`; 163 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| Config new/add/sections/params/loadString | incompatible_direct_contract | Ordered tables, table iterators and string split/strip parsing APIs absent; cursor inference on these library operations not represented. |
| extract substring bounds | reviewed_adaptation_pending | Text slice/search subset possible but this is a parser helper; no direct ownership improvement inferred. |
| testMe/main conditional projected ref | covered_existing_contract | Protected managed local projection is covered by ownership.py; nil branch/destructor prints unavailable. |
| testMe2/main2 assignment projected ref | covered_existing_contract | Same ownership projection via later assignment covered by current ownership-mutation tests; nil and finalizer timing excluded. |

### [tests/arc/tcursorloop.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tcursorloop.nim)

SHA256 `3f143b019a8efaa08e85c8ac61bc9b7280b9516e0f4e3637cb86dc7c42b31749`; 45 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| traverse owning loop it | reviewed_adaptation_pending | Can map null termination to empty children List; existing recursive-data chain traversal covers constant-index shape. |
| traverse cursor jt / expandArc | incompatible_direct_contract | Exact compiler cursor lowering and nil-only execution do not prove general traversal safety; no cursor syntax port. |

### [tests/arc/tdestroy_in_loopcond.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tdestroy_in_loopcond.nim)

SHA256 `c207ecff3d31fc8f2959d5a334513f717c3a104cb94e085cd0fa33976c00c407`; 75 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| HeapQueue helpers | incompatible_direct_contract | pop/clear/setLen API absent; simple replacement can test subset but not exact container. |
| newFuture cyclic closure | incompatible_direct_contract | Closure captures own Future, requiring cycle collector; unsupported in Minyar. |
| sleep/processTimers/main and occupied-memory400 oracle | incompatible_direct_contract | Deferred callback, cycles and full collection required. A manually acyclic queue would weaken source test. |

### [tests/arc/tmove_regression.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tmove_regression.nim)

SHA256 `e28b4dbc22be494c71695557408bc1b45d7a4de32bb3f9b52144f1010d16565a`; 23 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| finOp2/main path/file exception loop | incompatible_direct_contract | Path parent APIs, tuple result, caught exceptions and file handles unavailable. Printed path sequence alone would remove the move regression. |

### [tests/arc/tmovebug.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tmovebug.nim)

SHA256 `5ebbbbc05966f513e904bac91c84337ee0c340bd94cae7f78db8cbc208613bec`; 843 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| TMyObj custom hooks/moveBug/moveBug2/main | incompatible_direct_contract | Raw allocated pointer, variant object and custom copy/sink/destructor counts absent; value-semantic assignment differs. |
| tbug13314 escaping closure | incompatible_direct_contract | Closure captures mutable ref; no first-class closures. |
| procStat projected split columns | reviewed_adaptation_pending | SplitWhitespace API absent; managed column lifetime shape possible with explicit Lists. |
| tokenize/parse managed constructor fields | ported_semantic_subset | Adapt local Box projection into two Snapshot fields; extend later helper with mutation to test lifetime protection. |
| tokenizeA/parseA pointer variant | incompatible_direct_contract | Raw pointer address unavailable. |
| tokenizeD/parseD alloc0 variant | incompatible_direct_contract | Manual allocated pointer/deref unavailable. |
| tokenizeOD/parseOD owning ref variant | ported_semantic_subset | Owned managed-local form maps to same constructor-projection adaptation; no exact tokenization API claim. |
| whenfalse tokenizeOHD/parseOHD | incompatible_direct_contract | Disabled experimental implicit-deref source; not an executing test. |
| combinations/main2 exception iterator paths | incompatible_direct_contract | Iterator yields, caught UndefEx and labeled break absent. |
| ME custom hooks/shouldSink/shouldNotSink | incompatible_direct_contract | Exact distinction custom copy vs sink hooks unavailable; all-path ownership principle relevant, no copied output. |
| O2 update custom sink | incompatible_direct_contract | Hook prints and global seq semantics absent; standard fresh List assignment tests do not certify hook behavior. |
| initFoo/initFoo2..7 expression blocks and exceptions | incompatible_direct_contract | Six variants of expression-valued scoped constructors/case/try unsupported. Plain managed record construction already covered. |
| zip/leak live occupied memory | incompatible_direct_contract | Iterator yielded tuple and exact nonincreasing getOccupiedMem oracle unavailable. |
| weirdScopes expression statements/tuple assignments/try/case | incompatible_direct_contract | Expression blocks, tuple lvalues and exception scope unavailable; retaining king only would weaken program. |
| getScope/getScope2/getScope3 mixed return/expression/try | incompatible_direct_contract | Branch expression returns and exceptions differ. Minyar explicit-return branch contract already tested. |
| newWrapper/newWrapper2 both allocation arms | covered_existing_contract | Managed constructors and branch returned owner protected by ownership.py; ref-empty wrapper can use scalar record but exact prints differ. |
| caseSym/caseDotExpr/caseBracketExpr/caseBracketExprCopy | covered_existing_contract | Self assignment retains before release, covered in ownership-mutation/runtime fixtures; custom destructor output not mapped. |
| caseDotExprAddr/caseBracketExprAddr | incompatible_direct_contract | Raw addresses/dereference unavailable. |
| caseNotAConstant two effectful indices | ported_semantic_subset | Preserve destination-before-source index evaluation, overwritten managed Item and independently retained old alias; custom hooks/value-copy storage differ. |
| potentialSelfAssign runtime neighbor index | reviewed_adaptation_pending | Must retain source when destination index runtime-derived; existing index assignment tests partially cover, dedicated case pending. |
| partToWholeSeq/partToWholeSeqRTIndex | ported_semantic_subset | Preserve selected child before root replacement; one dynamic index evaluation and oldRoot alias control. |
| partToWholeUnownedRef | incompatible_direct_contract | Unowned ref dereference and custom value sink unavailable; owned managed child test not the same permission. |
| OOO initO/initC/pair destructor initialization | incompatible_direct_contract | User destructor asserts initialized, tuple return and firstWrite internal metadata unavailable; zero/uninitialized memory separately tested. |
| noConsume/main3 expression block | incompatible_direct_contract | nosinks pragma and block expression absent; ordinary borrowed call covered. |
| smoltest return in while | covered_existing_contract | Explicit return in while supported and already covered by regressions. |
| genAddrOf/atomicClosureOp case and block | incompatible_direct_contract | Enum case and expression block absent; borrowed parameter nonnull managed records covered separately. |
| assertEq/convoluted declaration scope | incompatible_direct_contract | Template block variables escaping expression scope absent; Minyar lexical rules differ. |

### [tests/arc/tmovebugcopy.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/tmovebugcopy.nim)

SHA256 `faf38b704443e903b2221f9cf167b5bf84a6be639ed49e50b63bfb3663cfb1c4`; 526 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| TMyObj custom hooks/moveBug/moveBug2/main | incompatible_direct_contract | Raw allocated pointer, variant object and custom copy/sink/destructor counts absent; value-semantic assignment differs. |
| tbug13314 escaping closure | incompatible_direct_contract | Closure captures mutable ref; no first-class closures. |
| procStat projected split columns | reviewed_adaptation_pending | SplitWhitespace API absent; managed column lifetime shape possible with explicit Lists. |
| tokenize/parse managed constructor fields | ported_semantic_subset | Adapt local Box projection into two Snapshot fields; extend later helper with mutation to test lifetime protection. |
| tokenizeA/parseA pointer variant | incompatible_direct_contract | Raw pointer address unavailable. |
| tokenizeD/parseD alloc0 variant | incompatible_direct_contract | Manual allocated pointer/deref unavailable. |
| tokenizeOD/parseOD owning ref variant | ported_semantic_subset | Owned managed-local form maps to same constructor-projection adaptation; no exact tokenization API claim. |
| whenfalse tokenizeOHD/parseOHD | incompatible_direct_contract | Disabled experimental implicit-deref source; not an executing test. |
| combinations/main2 exception iterator paths | incompatible_direct_contract | Iterator yields, caught UndefEx and labeled break absent. |
| ME custom hooks/shouldSink/shouldNotSink | incompatible_direct_contract | Exact distinction custom copy vs sink hooks unavailable; all-path ownership principle relevant, no copied output. |
| O2 update custom sink | incompatible_direct_contract | Hook prints and global seq semantics absent; standard fresh List assignment tests do not certify hook behavior. |
| initFoo/initFoo2..7 expression blocks and exceptions | incompatible_direct_contract | Six variants of expression-valued scoped constructors/case/try unsupported. Plain managed record construction already covered. |
| zip/leak live occupied memory | incompatible_direct_contract | Iterator yielded tuple and exact nonincreasing getOccupiedMem oracle unavailable. |
| weirdScopes expression statements/tuple assignments/try/case | incompatible_direct_contract | Expression blocks, tuple lvalues and exception scope unavailable; retaining king only would weaken program. |
| getScope/getScope2/getScope3 mixed return/expression/try | incompatible_direct_contract | Branch expression returns and exceptions differ. Minyar explicit-return branch contract already tested. |

### [tests/arc/topt_cursor.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/topt_cursor.nim)

SHA256 `240e57d60666a4cb5c7a68494234f7e1d9b02cd237ef4d61ea2ab14d7c154c8c`; 58 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| main cursor tuple assignment / expandArc | incompatible_direct_contract | Tuple value-copy and exact cursor elision unavailable; semantic branch reassignment already covered broadly. |
| sio file lines borrowed buffer | incompatible_direct_contract | File line iterator/lent buffer interface absent; dead iffalse branch not counted as executed validation. |

### [tests/arc/topt_cursor2.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/topt_cursor2.nim)

SHA256 `809acabeb587b0eff6b4e61c51ce335a84669b4a6fb9007f0348d09dcca93f94`; 77 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| Token/Paragraph printing and linked cursor rewrite | incompatible_direct_contract | Inheritance, double linked container and recursive rewiring unavailable; comments show nxt must own while edge rewrite removes owner. Relevant correctness hazard, no claim current Nim bug. |
| inner custom destructor/main holder | incompatible_direct_contract | Custom finalizer output absent; fresh nested managed holder lifetime covered elsewhere. |

### [tests/arc/topt_no_cursor.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/topt_no_cursor.nim)

SHA256 `d69433d01d46217e431edf9e7a1716167da2bacf18cfb57537357bfb2e775ee3`; 379 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| newTarget splitDrive tuple | incompatible_direct_contract | OS path parser and tuple result absent. |
| delete/main cyclic tree rewrite | incompatible_direct_contract | Parent back-pointers and recursive field rewrites are forbidden; copying sibling/saved is the relevant retained-owner hazard, not a portable graph. |
| p1/tissue15130 moved sequence result | reviewed_adaptation_pending | Tuple destructure/move builtin absent; returned managed List protection covered broadly, exact explicit-move contract not ported. |
| tt/encodedQuery retained projected pair | covered_existing_contract | Nested shared Lists in returned record covered in ownership.py; tuple/seq value semantics excluded. |
| s/charmatch/plus destructure and cursors | incompatible_direct_contract | Tuple results and split parser combinators absent; Text slice roots have independent tests. |
| substrEq/splitCommon/split/accResult | incompatible_direct_contract | String splitting custom iterator/template implementation absent; helper comparisons not an ownership oracle. |
| extractConfig conditional saved row value | ported_semantic_subset | Adapt prebuilt managed Rows and repeated replacement; checks saved projection across iterations and after temporary row retirement. |
| rawCloseScope/addInterfaceDecl/mergeShadowScope | ported_semantic_subset | Encode acyclic parent with List<Scope>; keep saved old scope after context.current replaced, then transfer its Text symbols. No cursor syntax or cyclic mutable graph introduced. |
| Foo/getSubDirs/check dynamic method | incompatible_direct_contract | Methods/inheritance and filesystem path helpers absent; property reassignment alone not exact contract. |

### [tests/arc/topt_refcursors.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/topt_refcursors.nim)

SHA256 `90e58b5c34c9daa1939cb433ad85ddb6370033dde20c473ab0b6e9c09828b148`; 54 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| traverse it cursor vs jt owner compiler golden | incompatible_direct_contract | Pinned source explicitly labels optimization unsound; nil-only executable cannot exercise risky graph. No assertion of a present Minyar/Nim runtime defect. |
| kept next owner while traversing | reviewed_adaptation_pending | Generic safety shape maps to owner-held child traversal; recursive-data.py has owner-return chain test; effectful graph rewrite requires own adversary. |

### [tests/arc/topt_wasmoved_destroy_pairs.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/topt_wasmoved_destroy_pairs.nim)

SHA256 `7dd242c4f7efdc68b288a9133e72e6ba9854143e448ba652ef237aa91af6402b`; 94 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| main all paths move x to one of two Lists | reviewed_adaptation_pending | Transfer shape compatible; exact wasMoved/destroy IR is Nim-specific. Existing managed branch/Lists coverage; distinct branch-transfer port pending. |
| tfor early return before final branch transfer | ported_semantic_subset | Original semantic ownership subset passed O0/O2 in profiling-integrated-focused.json; exact peer layout/IR and accounting not claimed. |

### [tests/arc/torc_basic_test.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/torc_basic_test.nim)

SHA256 `d5ea4288873a2c9383452a62741412f47730443a627e560d95c3a833b59520e9`; 138 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| edge/createNode/main SCC graph | incompatible_direct_contract | Creates several cycles including self-cycle; Minyar intentionally rejects these mutations. |
| buildComplexGraph/main2 multiple SCCs | incompatible_direct_contract | Complex graph and back edges require cycle collector; must remain unsupported disposition. |
| GC_fullCollect MEM0 oracle | incompatible_direct_contract | Global full collection and occupied-memory API unavailable; deferred drain in C is a different interface. |

### [tests/arc/torc_selfcycles.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/torc_selfcycles.nim)

SHA256 `08ec74c6b4766099739b2ced3c29b0764011552453e70deeb64857985e4043cf`; 33 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| newColumnNode self right/column | incompatible_direct_contract | Two explicit self cycles rejected by Minyar; no fake acyclic replacement. |
| createDLXList/stress main | incompatible_direct_contract | Cycles and custom ORC stress/malloc leak harness absent; leak result cannot transfer. |

### [tests/arc/twrong_sinkinference.nim](https://github.com/nim-lang/Nim/blob/f7145dd26efeeeb6eeae6fff649db244d81b212d/tests/arc/twrong_sinkinference.nim)

SHA256 `9561b80cecbee7a3e7e7d4763e0e4eeb101f142fec9f69af2f409f1e1b223154`; 18 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| Foo/take/willSink rejected callback | incompatible_direct_contract | First-class proc type with inferred sink convention mismatch absent; plain direct calls remove the issue. |

## Koka v3.2.2

Commit `39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3`. [Upstream license](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/LICENSE): Apache-2.0.

Entire immediate test/parc directory at pinned commit, including outputs and config; 62 entries, no recursive subdirectories

### [test/parc/beans.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/beans.kk)

SHA256 `f6c4b8023816725e357cacf883fda9e3d02bf9bdd91e66f566d10d275f471c1e`; 67 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| id | covered_existing_contract | Identity/borrow return existing ownership coverage. |
| mkPairOf | reviewed_adaptation_pending | Managed child stored in two record fields; existing nested shared Pair test covers shape, generic pair constructor differs. |
| fst | covered_existing_contract | Returned first/unused second owned value coverage in ownership choose/identity. |
| isNil Nil / Cons | covered_existing_contract | List empty/nonempty checks exist; pattern optimization not claimed. |
| hasNothing Nil / Nothing / recursive tail | incompatible_direct_contract | Maybe type and nested constructor pattern absent. |
| map Nil / Cons | incompatible_direct_contract | Higher-order generic callback and immutable Cons reconstruction absent. |
| goForward empty-first / nonempty-first | reviewed_adaptation_pending | Record of two Lists can reproduce value behavior via fresh copies; no direct deque transfer/reuse port yet. |
| swap empty / singleton / two-head | reviewed_adaptation_pending | Fresh list-copy adaptation possible; native Cons reuse not available; pending explicit compatible subset. |
| borrow-tail | incompatible_direct_contract | Calls first-class function f(y,y), unavailable; ordinary named two-arg duplicates covered separately. |

### [test/parc/config.json](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/config.json)

SHA256 `b777a85be4156df9d262bbdabf4e837d135ee53162627a7621a31bb0e103482a`; 4 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| flags | harness_only | Targets C and showfcore: accompanying .out files are compiler core goldens, not program stdout. |
| exclude parc19 | excluded_upstream | Pinned suite explicitly excludes parc19. Its source is reviewed as historical input, not a currently executing peer oracle. |

### [test/parc/hcounter.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/hcounter.kk)

SHA256 `b51344fa4551e56dcc491287552692e311947aaf13403d14a88e7b9d1b159631`; 42 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| state get/put handler | incompatible_direct_contract | User effect declarations/resumption unavailable. |
| fib / comp | covered_existing_contract | Scalar recursion not an RC regression in Minyar; bounded small recursion already tested. |
| count | incompatible_direct_contract | Recursively invokes state effects. |
| test-normal | incompatible_direct_contract | Handler closure mutates captured state; cannot replace with global counter and claim same collector behavior. |
| test-direct | reviewed_adaptation_pending | Plain scalar tail recursion possible but 100million depth/time benchmark outside tiny memory suite. |
| main | incompatible_direct_contract | Invokes unsupported effectful count; large benchmark not run. |

### [test/parc/hqueens.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/hqueens.kk)

SHA256 `49437ccbe3dbbd6a24f57695f83321b93b3d4bcbe37daa79cc30505cbb116d3c`; 95 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| safe? | reviewed_adaptation_pending | Scalar queen and List diagonal traversal can be implemented; not a direct memory oracle. |
| append-safe | reviewed_adaptation_pending | Hand-tuned recursive shared solutions; fresh arrays can model values with different representation/cost, pending separately designed workload. |
| extend | reviewed_adaptation_pending | Same fresh-array caveat; no code port yet. |
| find-solutions / queens | reviewed_adaptation_pending | Persistent solution sharing can be mapped carefully; benchmark n12 intentionally not run. |
| choose pick/fail effect | incompatible_direct_contract | No algebraic effect handlers. |
| choose-all | incompatible_direct_contract | Multi-shot resume and callback list concat absent. |
| find-solution | incompatible_direct_contract | Invokes unsupported choose/fail effects. |
| queens-choose | incompatible_direct_contract | Handler-driven nondeterminism unavailable. |
| test / main | incompatible_direct_contract | Upstream executes effectful twelve-queens search, not scalar implementation. |
| show-solutions | incompatible_direct_contract | First-class foreach callback and generic List show absent. |

### [test/parc/inline1.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/inline1.kk)

SHA256 `96dc224469c28a3e13b95c9f28681c62c3625f6a81dc2687ab44749f27c6e18d`; 6 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test two heads / fallback42 | covered_existing_contract | Indexed scalar List reads and branch result exist; memory oracle is boxed integer specialization and is not claimed by scalar Minyar coverage. |

### [test/parc/inline2.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/inline2.kk)

SHA256 `56c3d68755b7d36b7dc1fa8c341363e15f82910918e17ad4b648813a9ceb7835`; 10 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test A/B nested reuse / B2 | incompatible_direct_contract | Generic mutually typed ADT cases and inner-constructor reuse absent. |

### [test/parc/inline3.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/inline3.kk)

SHA256 `e265142ae2a74b517522a2812e5657014eb365a36937515ec8524a6d3dcc184f`; 10 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test A/B swap-and-reuse / A2 | incompatible_direct_contract | Generic nested ADT reconstruction with two reuse tokens absent; record reconstruction would only test a subset. |

### [test/parc/inline4.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/inline4.kk)

SHA256 `1498de6cd23151d538c55bccd05acf186fa607fab0f68f0720f2e81e2b3151ed`; 13 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| joinsepx empty / first head | ported_semantic_subset | Original semantic ownership subset passed O0/O2 in profiling-integrated-focused.json; exact peer layout/IR and accounting not claimed. |
| join-acc Cons / Nil | ported_semantic_subset | Original semantic ownership subset passed O0/O2 in profiling-integrated-focused.json; exact peer layout/IR and accounting not claimed. |

### [test/parc/inline5.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/inline5.kk)

SHA256 `df1a25b460c104be10434f31d1d4fc9316af7ba12a2fee3a9fc353ecf2a7e920`; 7 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| copyx tuple defaults | incompatible_direct_contract | Generic value/nonvalue struct layouts and default arguments absent. Shared Minyar records cannot be treated as independent value-copy structs. |

### [test/parc/parc-leak1.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc-leak1.kk)

SHA256 `0efa6017e3536263052ac661cde55c2caa5562e043bbd7872c2a2b059f23522a`; 5 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| main temporary Just tuple projection | incompatible_direct_contract | Option and tuple expression matching absent; exact transient wrapper leak not ported. |

### [test/parc/parc-leak1b.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc-leak1b.kk)

SHA256 `0e96326e5fc147fc60013edb1d5f9d42f577c82989c1ed0c103492dd280a6d2c`; 5 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| main temporary Just List head/default | incompatible_direct_contract | Option wrapper and default combinator absent; temporary managed projection is covered elsewhere but not exact wrapper leak. |

### [test/parc/parc1.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc1.kk)

SHA256 `952778b13cef984cb37285dc4fa222004fbd2165df86f1309aa042628f96f144`; 1 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test identity | covered_existing_contract | Managed identity/returned borrow covered by tests/ownership.py::test_returns_reassignments_and_identity_conversion; generic type inference not mapped. |

### [test/parc/parc1.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc1.kk.out)

SHA256 `9dc98840513816ff55e6e9376cbe2f6a55588b98ad676b986e8c6b87ea1d8ab6`; 26 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc1.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc1.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc10.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc10.kk)

SHA256 `b5b4c7b93fb3a4d3a2914b541959fe5cd80cf76f3009e255ad467af86764ab6a`; 4 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test drop input and return empty | covered_existing_contract | Source equals parc9; retained as distinct upstream unit, same existing coverage and timing qualification. |

### [test/parc/parc10.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc10.kk.out)

SHA256 `1bfb760998893c8d9ebd2414e4fd50b5ac81f7962254f531cb4bee61a03c0e51`; 28 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc10.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc10.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc11.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc11.kk)

SHA256 `5f977beba7e34d3de0d45ae384400e31aca9372491a19ab17a8f003432d7fa57`; 7 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test nonempty identity / empty result | covered_existing_contract | Branch-returned managed ownership covered by ownership choose/identity; immutable Cons layout and exact core golden incompatible. |

### [test/parc/parc11.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc11.kk.out)

SHA256 `1f0d9cedf9b071b19b63e63612e81241924c4a58bf7e3916a73890026da850dc`; 31 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc11.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc11.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc12.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc12.kk)

SHA256 `bdc28f9dd260f7d4f49cb08df83381798442ca0ef3eb2c469a09d235779e819b`; 8 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test computed-match temporary / original x return | incompatible_direct_contract | The RC check is boxed arbitrary-precision arithmetic temporaries and pattern matching. Minyar scalar arithmetic cannot supply this oracle. |

### [test/parc/parc12.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc12.kk.out)

SHA256 `cf80d843707e6c6bdba76efe0f64be7c34c6ebd7b94fdd94b14802be2e600c21`; 39 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc12.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc12.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc13.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc13.kk)

SHA256 `21cd4f89d9484f4d26209c4ec79d254df2617f4bc4d9211fdf28aede3cfe869c`; 3 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test escaping capture | incompatible_direct_contract | Returns a closure capturing x; Minyar has no first-class closures and this cannot be ported by a nonescaping plain call. |

### [test/parc/parc13.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc13.kk.out)

SHA256 `5dc36e625a4b3827d055e5d8d0d08a61c667fee40a571e81241d2acdba671203`; 28 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc13.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc13.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc14.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc14.kk)

SHA256 `0ccc6c6e9a777451e9aa68efad3871fc042a622e075676b30c69f2ee098c178c`; 6 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test zero chooses y / other chooses z | covered_existing_contract | Both managed branch results and surviving input aliases covered by ownership.py choose; generic x boxed-int RC is separate. |

### [test/parc/parc14.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc14.kk.out)

SHA256 `884ffcbd9e35f20f2fa044815b1456689cbba76dd851f336641ad920480ab1b2`; 39 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc14.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc14.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc15.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc15.kk)

SHA256 `cde4c818a81d99351579b9c31b1de6c3bbf91b327da37ba683644965e3c205ce`; 12 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test nested same-Cons match / fallback arms | incompatible_direct_contract | Constructor match/drop specialization and shadowed pattern variables have no direct frontend counterpart; scalar result-only test would weaken memory oracle. |

### [test/parc/parc15.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc15.kk.out)

SHA256 `b0d3cd9e98a25310d00887011dcb218c7c84bc1ca5a115882069fd792693746b`; 80 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc15.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc15.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc16.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc16.kk)

SHA256 `9ee3bcc7647623dde66b04722bcf44ac8ababb6cdc3391e63270a12868bf09a7`; 13 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test nested same-Cons match plus unused z | incompatible_direct_contract | Same restriction as parc15, with additional unused boxed-int drop; each source retained as distinct compiler regression. |

### [test/parc/parc16.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc16.kk.out)

SHA256 `300223bbf09f6473e93e172d1369b028cdc3f5ecfc56516dbaeb519fccd80a28`; 82 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc16.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc16.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc17.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc17.kk)

SHA256 `176bb2c7a017a702eded12a5935ae022e8a17e123b244db26dc5e7aaf852c76a`; 6 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test whole-pattern alias / Nil | covered_existing_contract | Returned borrowed List whole-object protection covered in ownership/recursive-data; pattern alias syntax not introduced. |

### [test/parc/parc17.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc17.kk.out)

SHA256 `35e82ac6a57d053c96212e049cd943f800f9386f60eb70fcb370f2872a136c59`; 31 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc17.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc17.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc18.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc18.kk)

SHA256 `7ac17cfa87351897627de43c4c3ea839c786de09d250e3e87106dd6bd4201372`; 9 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test both nonempty / right empty / left empty | ported_semantic_subset | Replace Cons matches with length/index; preserve selected managed child and both whole-input return arms. Extra empty/empty control; no allocation-reuse claim. |

### [test/parc/parc18.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc18.kk.out)

SHA256 `ff72b66655f8ad232e8954d13b88917e20fb322d4c2ba320ff73345341b6e062`; 75 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc18.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc18.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc19.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc19.kk)

SHA256 `4ef28d260dda3cb5ff17f9149ed833f0b5e8ed2ed8ef1fe0d3f0bd4012b8a142`; 6 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test shadowed head / Nil | excluded_upstream | Source read; config excludes this exact test, output uses an older core naming format. Do not count it as validated active peer behavior. |

### [test/parc/parc19.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc19.kk.out)

SHA256 `9d0619724b4db78f82ca1d71c3ede4da3f44af2d2fb01a28b7e2348506b4a7f6`; 27 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc19.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc19.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc2.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc2.kk)

SHA256 `505aca0f5165a620d81f0329eae21cf651e1183fe4c1f56c8325a3c15169e1cc`; 3 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test duplicate list | reviewed_adaptation_pending | Immutable concatenation x++x requires a fresh List copy; candidate owned by peer_profiling, pending validation; no List ++ API assumed. |

### [test/parc/parc2.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc2.kk.out)

SHA256 `85384d2d4097739cafdf024bc9728dce1b5608e150cea6540d37a5499c92108d`; 31 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc2.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc2.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc20.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc20.kk)

SHA256 `bb49fdc8face9fd7f6e2ce30cf3663aaf2e3d0aa4394e909cdce65f2921ddd4d`; 7 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test head reused while whole xs transferred | ported_semantic_subset | Original semantic ownership subset passed O0/O2 in profiling-integrated-focused.json; exact peer layout/IR and accounting not claimed. |

### [test/parc/parc20.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc20.kk.out)

SHA256 `cc03bad77ded685f7b4a7e70b55398f855fe0e5fa02b3a4d026b667b77547644`; 34 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc20.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc20.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc21.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc21.kk)

SHA256 `dc575a3785649e6c283301c5d3091e38edbe2566ad1bb55544e087894c884558`; 15 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| bo owning a / borrowing b | covered_existing_contract | No new source borrow syntax; effectful argument lifetime protection covered in ownership.py::test_borrow_survives_mutating_argument. |
| print-ret printing before return | covered_existing_contract | Left-to-right call evaluation already checked in recursive-data.py List argument-order and peer-research semantic probes. |
| test pure then effectful bo call | covered_existing_contract | Inspected core preserves prints 3 then4 despite borrowed second argument; existing effectful ownership test covers ordering/lifetime, no claim identical generated IR. |

### [test/parc/parc21.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc21.kk.out)

SHA256 `982a3fa0e8da47caf9f3d0baa393667c777abc7e61a913e2ce824151c702c939`; 44 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc21.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc21.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc22.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc22.kk)

SHA256 `4ff84169da50be7ba2af776d2db55f53118cd938e59a9f4b19fc50191d7a6da1`; 5 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| f drop-reuse old World into new World | reviewed_adaptation_pending | Single-constructor fresh replacement can map to a record, but no Minyar record-reuse optimization exists; exact alloc-at golden incompatible. Semantic discard-return control pending if needed. |

### [test/parc/parc22.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc22.kk.out)

SHA256 `88f7a42c02d17fc3218b026056cfebb2d87ddb8d1f65184b703a816e512b594d`; 76 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc22.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc22.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc23.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc23.kk)

SHA256 `d70f65e003b7a2a1f1cbd09cc893b1524de30dd4ede1568275c6866c4b0f1c75`; 12 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| rotate nonempty / fallback | ported_semantic_subset | Fresh List tails and accumulator preserve tested value/sharing subset; immutable Cons and type-generic boxed reuse layout not claimed. |
| generated pair projections and optional copy helper | incompatible_direct_contract | Compiler-generated generic constructors and optional copy arguments in golden are not Minyar ABI. |
| main unit | covered_existing_contract | No executing call to rotate in upstream main; empty main is not used as semantic evidence of rotation. |

### [test/parc/parc23.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc23.kk.out)

SHA256 `ef483768e601a06ba297d2e9c5633f8f4835eec46a42d3fe1995bbd581ea6142`; 153 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc23.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc23.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc3.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc3.kk)

SHA256 `c4cc9f9c0ad175854ea4b7eabf4ea01264ddb3ed88b7a64908ce6f2c3dd1b5af`; 8 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test four guarded match arms | incompatible_direct_contract | Koka Cons guards and boxed arbitrary-precision int drop/dup golden differ from scalar Integer and indexed mutable List. Branch values alone do not exercise its RC oracle. |

### [test/parc/parc3.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc3.kk.out)

SHA256 `506ae768957b3c7f0723ae925c5796d1d97c9f302f084fa8dfc5081e549efd4e`; 100 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc3.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc3.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc4.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc4.kk)

SHA256 `e2cd0aa5669d5f6a2f6831f92e5b0ba617832bf3996d733eac633e67b3d9787f`; 7 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test Just-equal / Nothing / fallback | incompatible_direct_contract | Nested Maybe/Cons constructor matching and boxed-int golden are absent from Minyar. No Option syntax introduced. |

### [test/parc/parc4.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc4.kk.out)

SHA256 `1853ca8de0d919be4ad1648e74ad74be5631a65316be2773d206a70e0a8f3bca`; 77 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc4.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc4.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc5.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc5.kk)

SHA256 `d22d42f1d78a1154cb82479102915d313715d166a77666f262043e9529fe6d1f`; 10 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test singleton head | covered_existing_contract | Nonempty singleton List indexed read covered by regressions/runtime List tests; commented expansion is not a second executing test. |

### [test/parc/parc5.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc5.kk.out)

SHA256 `db8036c48406785cb3f26bf7ea6e939c153da501cc9a49ccdb8b13b5339da9f5`; 26 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc5.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc5.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc6.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc6.kk)

SHA256 `1eed80131bfee598099c3547a892da7b468eb4d2adf89cc8cb1c1209ea90ba28`; 7 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test head / fallback ownership | incompatible_direct_contract | Constant-folded singleton match uses Koka boxed int dropping unused y; Minyar scalar Integer has no comparable RC obligation. |

### [test/parc/parc6.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc6.kk.out)

SHA256 `c83a57cfbe590ff27844fb23a4ae5a9d0239f51de5cd6f1eebe51c838ae6b2bf`; 28 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc6.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc6.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc7.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc7.kk)

SHA256 `a11271b3f8d55eccd70a9191417ff32d02b1eac4425ab24b1d09f84facd6a580`; 4 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test first argument returned / second unused | covered_existing_contract | Borrowed parameter return protection covered in ownership.py identity/choose; exact eager drop of unused parameter is not Minyar incremental contract. |

### [test/parc/parc7.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc7.kk.out)

SHA256 `5e6bc58c9c09f218b447051a186711b4b85696b0be0a0745978d55fd45f498ca`; 28 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc7.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc7.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc8.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc8.kk)

SHA256 `c3358da08d91ee634da3a49f33b3e6d71ed86b7194d572371625b203f3706719`; 4 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test duplicate integer / drop unused | incompatible_direct_contract | Koka int is arbitrary precision/boxed as needed; duplicating scalar Integer cannot reproduce the memory regression. |

### [test/parc/parc8.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc8.kk.out)

SHA256 `e57aec37cbfeb2141d7ec8615b204a52b58760c8da98553ac3fa51b3cead66f9`; 28 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc8.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc8.kk. No Minyar textual-IR equality claimed. |

### [test/parc/parc9.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc9.kk)

SHA256 `b5b4c7b93fb3a4d3a2914b541959fe5cd80cf76f3009e255ad467af86764ab6a`; 4 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test drop input and return empty | covered_existing_contract | Fresh empty List returns and reassigned old roots covered by recursive-data/ownership fixtures; destruction timing differs. |

### [test/parc/parc9.kk.out](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/parc9.kk.out)

SHA256 `401aafcd718700cd34aeb4453bdfc9e97bc6972c4cf2189001b97cc5f8633af1`; 28 lines; relevant_compiler_core_sections_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| core golden for test/parc/parc9.kk | incompatible_exact_ir | Read ownership/reuse/drop core for associated source; imports are support boilerplate. This is compiler IR golden, not stdout. Source-unit dispositions reference test/parc/parc9.kk. No Minyar textual-IR equality claimed. |

### [test/parc/reuse-spec1.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/reuse-spec1.kk)

SHA256 `a090cb711d5abd1e63188bf838dcb1b185c13a27c01043ca323b835048262899`; 21 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| balance-left Leaf | incompatible_direct_contract | Tagged tree and color constructors unavailable; exact constructor reuse criterion is not reproduced. |
| balance-left left red grandchild | incompatible_direct_contract | Nested ADT balancing/reuse cannot be copied as mutable List update without changing identity. |
| balance-left right red grandchild | incompatible_direct_contract | Same ADT/layout limitation, distinct rebalance arm inspected. |
| balance-left fallback node | incompatible_direct_contract | Existing explicit fresh tree construction covers acyclic ownership broadly, but not red-black algorithm/reuse oracle. |

### [test/parc/reuse1.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/reuse1.kk)

SHA256 `eb465d4625ef9424f79ff0b010d3f7608f949393db204bb3a750bb20ec1222f6`; 13 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| unzipx / iter Cons and Nil | reviewed_adaptation_pending | Fresh record containing two Lists can reproduce ordering/ownership. Candidate owned by peer_profiling; pending validation; tuple/generic code itself incompatible. |

### [test/parc/reuse2.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/reuse2.kk)

SHA256 `ed98a29abddc36fa17e105ee042102777be23e5d95e233e4840f2ca23be328ec`; 7 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test second element partial match | incompatible_direct_contract | int32 and partial-match exception effect absent; returning default on short List would change oracle. |

### [test/parc/reuse3.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/reuse3.kk)

SHA256 `3e6bc13bb0b652c8837fccde7f000a493220a71f9d2feb5992449d043b7c3a04`; 7 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| test second pair first field partial match | incompatible_direct_contract | Tuple/generic int32 projection plus partial-match exception effect absent; do not add fallback semantics. |

### [test/parc/reuse4.kk](https://github.com/koka-lang/koka/blob/39b4bec7327dbbcb2f83ce7aca5fe061931a4dc3/test/parc/reuse4.kk)

SHA256 `491b3eeccd12a8307870930caa2977bc5af80acac6b4709cfb3d7c8c1410e488`; 8 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| mapx Cons / Nil and callback | incompatible_direct_contract | Generic higher-order function and immutable recursive Cons representation; no first-class callbacks in Minyar. |

## Lean v4.23.0

Commit `50aaf682e9b74ab92880292a25c68baa1cc81c87`. [Upstream license](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/LICENSE): Apache-2.0.

All26 candidates of declared recursive basename memory-name filter, including12 initial compiler/IR/runtime sources and14 supplemental theorem/interpreter/playground cases; not exhaustive memory-test discovery.

### [tests/compiler/array.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/compiler/array.lean)

SHA256 `8183c02be65366c15424f733033680bf263167dd1f32986181743650f1528726`; 13 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| f Array.casesOn | incompatible_direct_contract | Dependent eliminator/list backing conversion unavailable; length scalar behavior alone removes memory regression. |
| g Array.toList | incompatible_direct_contract | Separate immutable List/Array representations absent. |
| h List->Array->List | incompatible_direct_contract | Same representation conversion mismatch. |
| main three printed results | incompatible_direct_contract | Generic ToString array/list formatting unavailable; not a physical-ownership oracle. |

### [tests/compiler/arrayMk.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/compiler/arrayMk.lean)

SHA256 `b00cba3126381c6351bd0a8d4a363fe7d7b78e33a62a8a6ecdbe4a2cec348fcb`; 2 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| step/main range Array.mk | incompatible_direct_contract | Two distinct immutable container representations/range constructor absent. Ordinary populated List size existing coverage not exact conversion. |

### [tests/compiler/array_test.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/compiler/array_test.lean)

SHA256 `f4a54c70cea13fe6b7c5ced7e0a80fcbce5ad3b0f601571e7c4a029786096360`; 37 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| print line 10 | incompatible_direct_contract | IO.println (toString a) — generic immutable Array formatting/value-copy API not present. |
| print line 11 | incompatible_direct_contract | IO.println (toString a.size) — generic immutable Array formatting/value-copy API not present. |
| print line 13 | incompatible_direct_contract | IO.println (toString a) — generic immutable Array formatting/value-copy API not present. |
| print line 15 | incompatible_direct_contract | IO.println (toString a) — generic immutable Array formatting/value-copy API not present. |
| print line 16 | incompatible_direct_contract | IO.println (toString a.size) — generic immutable Array formatting/value-copy API not present. |
| print line 19 | incompatible_direct_contract | IO.println (toString a1) — generic immutable Array formatting/value-copy API not present. |
| print line 20 | incompatible_direct_contract | IO.println (toString a2) — generic immutable Array formatting/value-copy API not present. |
| print line 22 | incompatible_direct_contract | IO.println a2 — generic immutable Array formatting/value-copy API not present. |
| assertion/print line 23 | incompatible_direct_contract | IO.println $ (([1, 2, 3, 4].toArray).map (fun a => a + 2)).map toString — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 24 | incompatible_direct_contract | IO.println $ ([1, 2, 3, 4].toArray.extract 1 3) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 25 | incompatible_direct_contract | IO.println $ ([1, 2, 3, 4].toArray.extract 0 100) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 26 | incompatible_direct_contract | IO.println $ ([1, 2, 3, 4].toArray.extract 1 1) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 27 | incompatible_direct_contract | IO.println $ ([1, 2, 3, 4].toArray.extract 2 4) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 28 | incompatible_direct_contract | IO.println [1,2,3,4].toArray.reverse — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 29 | incompatible_direct_contract | IO.println ([] : List Nat).toArray.reverse — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 30 | incompatible_direct_contract | IO.println [1,2,3].toArray.reverse — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 31 | incompatible_direct_contract | IO.println $ [1,2,3,4].toArray.filter (fun a => a % 2 == 0) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 32 | incompatible_direct_contract | IO.println $ [1,2,3,4,5].toArray.filter (fun a =>  a % 2 == 0) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 33 | incompatible_direct_contract | IO.println $ [1,2,3,4,5].toArray.filter (fun a => a % 2 == 1) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 34 | incompatible_direct_contract | IO.println $ [1,2,3,4].toArray.filter (fun a => a > 2) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 35 | incompatible_direct_contract | IO.println $ [1,2,3,4].toArray.filter (fun a => a > 10) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 36 | incompatible_direct_contract | IO.println $ [1,2,3,4].toArray.filter (fun a => a > 0) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| foo repeated persistent push | incompatible_direct_contract | Minyar add mutates shared List, while Lean push returns value and may COW; using add alone changes alias semantics. |
| main pop/push branched persistent arrays | incompatible_direct_contract | No pop API or persistent Array value semantics; copied arrays need explicit construction, not aliasing assignments. |

### [tests/compiler/array_test2.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/compiler/array_test2.lean)

SHA256 `40dbcd1b8abed8315d130b258ef715e47f5a8d45581084bd6cb922e6eb56c8ad`; 15 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| check | incompatible_direct_contract | IO exception-free failed print helper not separate ownership test. |
| main isEqv true | incompatible_direct_contract | Higher-order equivalence predicate absent. |
| main isEqv false | incompatible_direct_contract | Same API gap, distinct negative oracle. |
| main concatenation | reviewed_adaptation_pending | Fresh immutable output values can adapt by explicit List loops; peer_profiling Koka duplicate-list candidate partly covers. |
| main any true | incompatible_direct_contract | Higher-order Array.any absent. |
| main any false | incompatible_direct_contract | Same API gap, negative predicate result inspected. |
| main all true | incompatible_direct_contract | Higher-order Array.all absent. |

### [tests/compiler/bytearray_bug.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/compiler/bytearray_bug.lean)

SHA256 `6a96e2a3c3a51d86a74032f403f2b3d0683091d2866ab2248e60e5b1031211cc`; 5 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| main temporary ByteArray.data.get! | incompatible_direct_contract | ByteArray and underlying managed-array projection have no same representation in Minyar; Bytes API differs. Direct value10 alone weakens temporary wrapper regression. |

### [tests/compiler/reusebug.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/compiler/reusebug.lean)

SHA256 `102bc13bb452572a6a682622f0d583b6e6104bd59240a219bd2d260e5c219513`; 32 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| Expr inductive/ToString instance | incompatible_direct_contract | Tagged sum types and instances absent; explicit tag-record encoding used only as declared subset. |
| Expr.toString Val/Var/Add/Mul | ported_semantic_subset | Four cases mapped by explicit tag records; preserves tested strings and shared DAG, not original ADT layout/reuse. |
| addAux recursive-head / fallback and add | ported_semantic_subset | Preserves partial source algorithm on terminating inputs; extra initially divergent Val/Val input recorded under port_trial_notes. |
| main shared Var x twice | ported_semantic_subset | Checks original expression and retained input, plus terminating recursive-arm case. |

### [tests/ir/lirc.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/ir/lirc.lean)

SHA256 `ad44921000b566f21798650d8f7a7947cbf09376b07e2573d24f218b41c7064b`; 13 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| main lirc input C++ output | incompatible_direct_contract | Compiler IR translator CLI and historical init modules absent; not a user heap semantic test. |

### [tests/lean/run/array1.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/array1.lean)

SHA256 `a705a542e9e266c538b150f3701616cb3dfb2ec67796c780305af5e4bceddd0c`; 108 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| assertion/print line 5 | reviewed_adaptation_pending | #guard v == #[1, 2, 3, 4, ] — scalar result can be adapted, but proof-indexed/immutable Array ownership and interpreter validation differ; no port yet. |
| assertion/print line 18 | reviewed_adaptation_pending | #guard mkArray 4 1 == #[1, 1, 1, 1] — scalar result can be adapted, but proof-indexed/immutable Array ownership and interpreter validation differ; no port yet. |
| assertion/print line 20 | incompatible_direct_contract | #guard Array.map (fun x => x+10) v == #[11, 12, 13, 14] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 22 | reviewed_adaptation_pending | #guard f ⟨1, sorry⟩ == 1 — scalar result can be adapted, but proof-indexed/immutable Array ownership and interpreter validation differ; no port yet. |
| assertion/print line 24 | reviewed_adaptation_pending | #guard f ⟨9, sorry⟩ == 3 — scalar result can be adapted, but proof-indexed/immutable Array ownership and interpreter validation differ; no port yet. |
| assertion/print line 26 | reviewed_adaptation_pending | #guard (((mkArray 1 1).push 2).push 3).foldl (fun x y => x + y) 0 == 6 — scalar result can be adapted, but proof-indexed/immutable Array ownership and interpreter validation differ; no port yet. |
| assertion/print line 28 | reviewed_adaptation_pending | #guard arraySum (mkArray 10 1) == 10 — scalar result can be adapted, but proof-indexed/immutable Array ownership and interpreter validation differ; no port yet. |
| assertion/print line 33 | incompatible_direct_contract | #guard #[1, 2, 3].insertIdx 0 10 == #[10, 1, 2, 3] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 34 | incompatible_direct_contract | #guard #[1, 2, 3].insertIdx 1 10 == #[1, 10, 2, 3] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 35 | incompatible_direct_contract | #guard #[1, 2, 3].insertIdx 2 10 == #[1, 2, 10, 3] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 36 | incompatible_direct_contract | #guard #[1, 2, 3].insertIdx 3 10 == #[1, 2, 3, 10] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 37 | incompatible_direct_contract | #guard #[].insertIdx 0 10 == #[10] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 51 | incompatible_direct_contract | #guard #[1, 2].extract 0 1 == #[1] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 52 | incompatible_direct_contract | #guard #[1, 2].extract 0 0 == #[] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 53 | incompatible_direct_contract | #guard #[1, 2].extract 0 2 == #[1, 2] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 55 | incompatible_direct_contract | #guard #[1, 2, 3, 4].filterMap (fun x => if x % 2 == 0 then some (x + 10) else none) == #[12, 14] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 59 | reviewed_adaptation_pending | IO.println x; — scalar result can be adapted, but proof-indexed/immutable Array ownership and interpreter validation differ; no port yet. |
| assertion/print line 73 | incompatible_direct_contract | #guard #[1, 3, 6, 2].getMax? (fun a b => a < b) == some 6 — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 74 | incompatible_direct_contract | #guard #[].getMax? (fun (a b : Nat) => a < b) == none — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 75 | incompatible_direct_contract | #guard #[1, 8].getMax? (fun a b => a < b) == some 8 — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 76 | incompatible_direct_contract | #guard #[8, 1].getMax? (fun a b => a < b) == some 8 — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 78 | incompatible_direct_contract | #guard #[1, 6, 5, 3, 8, 2, 0].partition (fun x => x % 2 == 0) == (#[6, 8, 2, 0], #[1, 5, 3]) — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 83 | incompatible_direct_contract | #guard #[].isPrefixOf #[2, 3] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 84 | incompatible_direct_contract | #guard (#[] : Array Nat).isPrefixOf #[] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 85 | incompatible_direct_contract | #guard #[2, 3].isPrefixOf #[2, 3] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 86 | incompatible_direct_contract | #guard #[2, 3].isPrefixOf #[2, 3, 4, 5] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 87 | incompatible_direct_contract | #guard ! #[2, 4].isPrefixOf #[2, 3] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 88 | incompatible_direct_contract | #guard ! #[2, 3, 4].isPrefixOf #[2, 3] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 89 | incompatible_direct_contract | #guard ! #[2].isPrefixOf #[] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 90 | incompatible_direct_contract | #guard ! #[4, 3].isPrefixOf #[2, 3, 4, 5] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 92 | incompatible_direct_contract | #guard #[1, 2, 3].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 93 | incompatible_direct_contract | #guard !#[1, 2, 1, 3].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 94 | incompatible_direct_contract | #guard #[1, 2, 4, 3].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 95 | incompatible_direct_contract | #guard (#[] : Array Nat).allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 96 | incompatible_direct_contract | #guard !#[1, 1].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 97 | incompatible_direct_contract | #guard !#[1, 2, 3, 4, 5, 1].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 98 | incompatible_direct_contract | #guard #[1, 2, 3, 4, 5].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 99 | incompatible_direct_contract | #guard !#[1, 2, 3, 4, 5, 5].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 100 | incompatible_direct_contract | #guard !#[1, 3, 3, 4, 5].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 101 | incompatible_direct_contract | #guard !#[1, 2, 3, 4, 5, 3].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 102 | incompatible_direct_contract | #guard !#[1, 2, 3, 4, 5, 4].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 103 | incompatible_direct_contract | #guard #[1, 2, 3, 4, 5, 6].allDiff — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| assertion/print line 105 | incompatible_direct_contract | #guard Array.zip #[1, 2] #[3, 4, 6] == #[(1, 3), (2, 4)] — exact higher-order/persistent Array API not present; explicit loop adaptation would need a separately declared subset. |
| v/w/f dependent index definitions | incompatible_direct_contract | Fin proof index and Array.get proof argument absent. |
| arraySum foldl | incompatible_direct_contract | Higher-order fold absent; scalar sum possible by loop but not exact memory operation. |
| tst1 forRevM | incompatible_direct_contract | Callback reverse iteration absent. |
| tst filterMapM effects/guard_msgs | incompatible_direct_contract | Option callback and monadic filter/map absent. |
| check IO throw helper | incompatible_direct_contract | IO userError exception/proof interpreter not Minyar. |
| ex1 theorem rfl | incompatible_direct_contract | Proof definitional equality and Array.set! persistent semantics not runtime behavior. |

### [tests/lean/run/borrowBug.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/borrowBug.lean)

SHA256 `54080e5dc3374829bbd0d09442e801e2081628a48d8b503616440c6423cd01f6`; 16 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| g returns duplicated managed ownership shape | ported_semantic_subset | Nat pair replaced by Payload pair explicitly; immediate/boxed Nat distinction not claimed. |
| p/jp/f both branches | ported_semantic_subset | Managed predicate argument protected across temporary pair and short-circuit calls, with live original aliases. |
| h borrowed x | covered_existing_contract | Plain borrowed scalar predicate no additional ownership; managed borrow coverage existing. |
| trace.compiler.ir.rc golden | incompatible_direct_contract | Exact ownership inference trace is Lean-specific and not reproduced by value output. |

### [tests/lean/run/rc_tests.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/rc_tests.lean)

SHA256 `b5c2582aacb4dc82006222cfffd6e427baf7402de83c560c45403662f8ebfd2f`; 85 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| x1.f conditional repeated Nat arithmetic | incompatible_direct_contract | Nat boxing/arbitrary precision differs from scalar Integer; arithmetic values covered but RC oracle incompatible. |
| x2.f identity | covered_existing_contract | Managed identity adaptation covered existing ownership tests; Nat representation caveat. |
| x3.f first/unused argument | covered_existing_contract | Unused managed arg and returned borrow covered existing choose/identity. |
| x4.h/f1 | incompatible_direct_contract | Nat calling convention and noinline ownership trace not Minyar ABI. |
| x4.f2 two nested calls | incompatible_direct_contract | Same Nat representation limitation; effect order and managed calls covered separately. |
| x4.f3 three repeated x | incompatible_direct_contract | Same RC-on-Nat limitation. |
| x4.f4 immediate constants0/1 | incompatible_direct_contract | Immediate/tagged constants ownership specialization not reproduced. |
| x4.f5 constants1/1 | incompatible_direct_contract | Distinct constant arithmetic core case; scalar output not RC evidence. |
| x5.myMap | incompatible_direct_contract | Higher-order polymorphic immutable Cons recursion absent. |
| x6.act/f StateM sequencing | incompatible_direct_contract | State monad callback/combinator not a source feature. |
| x7.S/foo | incompatible_direct_contract | Tagged enum and tuple constructors absent. |
| x8.f x stored twice | reviewed_adaptation_pending | Can use managed Payload twice in List; existing nested shared aliases cover shape; no Nat RC specialization claim. |

### [tests/lean/run/parray1.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/parray1.lean)

SHA256 `066173119bed3a3766f91ee61d88ae3ea7e47845cd25ee0bd96a1ff52ac45a40`; 17 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| check persistent array foldr conversion | incompatible_direct_contract | PersistentArray tree container and callback fold absent; flat List values not same memory layout. |
| tst1 six lengths 3/0/17/533/1000/2600 | incompatible_direct_contract | Each converted persistent-array fold-back assertion inspected; no matching Minyar persistent container API. |
| guard_msgs output done | incompatible_direct_contract | Interpreter/proof command not a native Minyar memory oracle. |

### [tests/lean/run/sarray.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/sarray.lean)

SHA256 `f4fe0a099552a106661eb06fc91035a2313650824b752bdf29b6789b73ced7db`; 43 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| mkByteArray | incompatible_direct_contract | ByteArray push and UInt8 narrowing absent. |
| tst1 foldl sum100 | incompatible_direct_contract | Callback fold and UInt32 representation absent. |
| tst2 byte iteration sum100 | incompatible_direct_contract | Typed byte iterator unavailable; equivalent Bytes value sum not same managed-array ownership. |
| tst3 indexed byte sum100 | incompatible_direct_contract | Typed ByteArray ownership differs; raw Bytes indexed value checks already exist. |
| computeByteHash/compiler IR trace | incompatible_direct_contract | Lean hashing callbacks and exact compiler trace absent. |

### [tests/lean/arrayGetU.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/arrayGetU.lean)

SHA256 `acf01835ded27fad66fe335c59c496eb8e9a4b9fbb9303c781fc27354aa79819`; 17 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| f indexed persistent set/get | incompatible_direct_contract | Proof-indexed Array set produces a value result; no proof indices or persistent List mutation semantics. |
| theorem ex1 | incompatible_direct_contract | Elaboration/simp/trace_state equality proof, not an executed memory oracle. |
| theorem ex2 | incompatible_direct_contract | Elaboration/simp/trace_state equality proof, not an executed memory oracle. |
| theorem ex3 | incompatible_direct_contract | Elaboration/simp/trace_state equality proof, not an executed memory oracle. |
| pp.proofs true | harness_only | Printing configuration, no runtime ownership. |

### [tests/lean/bytearray.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/bytearray.lean)

SHA256 `4d2781affa175f734db41b33a438734b1d102854c5280680dea38b1bef75dd49`; 23 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| tst persistent push/set/alias helpers | incompatible_direct_contract | ByteArray persistent values and push/set/concatenation/extract APIs do not match shared Minyar Bytes/List; native memory layout differs. |
| assertion/print line 5 | incompatible_direct_contract | IO.println bs; — Persistent ByteArray print/API scenario with incompatible mutation/value semantics; see tst helper. |
| assertion/print line 8 | incompatible_direct_contract | IO.println bs; — Persistent ByteArray print/API scenario with incompatible mutation/value semantics; see tst helper. |
| assertion/print line 10 | incompatible_direct_contract | IO.println bs₁; — Persistent ByteArray print/API scenario with incompatible mutation/value semantics; see tst helper. |
| assertion/print line 11 | incompatible_direct_contract | IO.println bs; — Persistent ByteArray print/API scenario with incompatible mutation/value semantics; see tst helper. |
| assertion/print line 12 | incompatible_direct_contract | IO.println bs.size; — Persistent ByteArray print/API scenario with incompatible mutation/value semantics; see tst helper. |
| assertion/print line 13 | incompatible_direct_contract | IO.println (bs ++ bs); — Persistent ByteArray print/API scenario with incompatible mutation/value semantics; see tst helper. |
| assertion/print line 14 | incompatible_direct_contract | IO.println (bs.extract 1 3); — Persistent ByteArray print/API scenario with incompatible mutation/value semantics; see tst helper. |
| assertion/print line 17 | incompatible_direct_contract | #eval tst — Persistent ByteArray print/API scenario with incompatible mutation/value semantics; see tst helper. |
| assertion/print line 19 | incompatible_direct_contract | #eval "abcd".hash — Peer-specific hash output/API; Minyar does not promise same hash algorithm or public ByteArray hash. |
| assertion/print line 20 | incompatible_direct_contract | #eval [97, 98, 99, 100].toByteArray.hash — Peer-specific hash output/API; Minyar does not promise same hash algorithm or public ByteArray hash. |
| assertion/print line 22 | incompatible_direct_contract | #eval [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88].toByteArray.toUInt64LE! == 0x8877665544332211 — ByteArray endian UInt64 conversion absent; unsigned64 expected value may exceed signed Integer range. |
| assertion/print line 23 | incompatible_direct_contract | #eval [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88].toByteArray.toUInt64BE! == 0x1122334455667788 — ByteArray endian UInt64 conversion absent; unsigned64 expected value may exceed signed Integer range. |

### [tests/lean/run/array_isEqvAux.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/array_isEqvAux.lean)

SHA256 `28fd479149367ab89a8c98dd63d4ddb37ad2f4ca7e06695a1cb209e6a6330220`; 47 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| example line 18 | incompatible_direct_contract | example : #[0, 1] = #[0, 1] := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 20 | incompatible_direct_contract | example : let a := Array.range (10^6); a == a := by native_decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 27 | incompatible_direct_contract | example : Array.ofFn (id : Fin 2 → Fin 2) = #[0, 1] := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 29 | incompatible_direct_contract | example : #[0, 1].map (· + 1) = #[1, 2] := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 31 | incompatible_direct_contract | example : #[0, 1].any (· % 2 = 0) := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 33 | incompatible_direct_contract | example : #[0, 1].findIdx? (· % 2 = 0) = some 0 := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 35 | incompatible_direct_contract | example : #[0, 1, 2].popWhile (· % 2 = 0) = #[0, 1] := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 37 | incompatible_direct_contract | example : #[0, 1, 2].takeWhile (· % 2 = 0) = #[0] := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 39 | incompatible_direct_contract | example : #[0, 1, 2].eraseIdx 1 = #[0, 2] := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 41 | incompatible_direct_contract | example : #[0, 1, 2].insertIdx 1 3 = #[0, 3, 1, 2] := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 43 | incompatible_direct_contract | example : #[0, 1, 2].isPrefixOf #[0, 1, 2, 3] = true := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 45 | incompatible_direct_contract | example : Array.zipWith (· + ·) #[0, 1, 2] #[3, 4, 5] = #[3, 5, 7] := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |
| example line 47 | incompatible_direct_contract | example : #[0, 1, 2].allDiff = true := by decide — decide/native_decide reducibility theorem; no proof system or exact higher-order Array API. Million-element native_decide self-equality not executed. |

### [tests/lean/run/array_simp.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/array_simp.lean)

SHA256 `5e4974e7b4e0b38d0a99cd1606f081d15d4226fc5f55526485dde4bc6b9fe89c`; 26 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| remove Nat.default_eq_zero simp attribute | harness_only | Theorem simplification environment adjustment; no runtime effect. |
| directive line 3 | incompatible_direct_contract | #check_simp #[1,2,3,4,5][2]  ~> 3 — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 4 | incompatible_direct_contract | #check_simp #[1,2,3,4,5][2]? ~> some 3 — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 5 | incompatible_direct_contract | #check_simp #[1,2,3,4,5][7]? ~> none — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 6 | incompatible_direct_contract | #check_simp #[][0]? ~> none — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 7 | incompatible_direct_contract | #check_simp #[1,2,3,4,5][2]! ~> 3 — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 8 | incompatible_direct_contract | #check_simp #[1,2,3,4,5][7]! ~> (default : Nat) — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 9 | incompatible_direct_contract | #check_simp (#[] : Array Nat)[0]! ~> (default : Nat) — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 12 | incompatible_direct_contract | #check_simp xs.size = 0 ~> xs = #[] — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 14 | incompatible_direct_contract | #check_simp — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 21 | incompatible_direct_contract | #check_simp — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |

### [tests/lean/run/floatarray.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/floatarray.lean)

SHA256 `868c410dbeb2e3903c8679239490394f01f2f8df77a5bbee043eefe990d40abe`; 24 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| tst FloatArray persistent overwrite and old alias | incompatible_direct_contract | Lean FloatArray specialized persistent backing and six-decimal output differ from shared Minyar List<Float>; direct set alias would change expected old contents. |
| print line 6 | incompatible_direct_contract | IO.println bs; — specialized persistent FloatArray values and Lean Float formatting; direct shared mutation would change old-alias output. |
| print line 9 | incompatible_direct_contract | IO.println bs; — specialized persistent FloatArray values and Lean Float formatting; direct shared mutation would change old-alias output. |
| print line 11 | incompatible_direct_contract | IO.println bs₁; — specialized persistent FloatArray values and Lean Float formatting; direct shared mutation would change old-alias output. |
| print line 12 | incompatible_direct_contract | IO.println bs; — specialized persistent FloatArray values and Lean Float formatting; direct shared mutation would change old-alias output. |
| print line 13 | incompatible_direct_contract | IO.println bs.size; — specialized persistent FloatArray values and Lean Float formatting; direct shared mutation would change old-alias output. |

### [tests/lean/run/forInPArray.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/forInPArray.lean)

SHA256 `2f7c607344fd73afd9ad415a66ff057f46f86b603a08a2b51dbd468a74a66687`; 117 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| check exception helper | incompatible_direct_contract | IO.userError throw interface absent; explicit scalar value check can substitute but loses this failure contract. |
| f1 early return after even sums | reviewed_adaptation_pending | Indexed loop can reproduce print/value behavior and owner-frame exit; PArray iterator representation unavailable. Scalar subset pending, no distinct ownership gap yet. |
| f2 break followed by final print | reviewed_adaptation_pending | Loop break/final output can adapt values; PArray representation absent and not a new memory oracle. |
| eval line 26 | reviewed_adaptation_pending | #eval f1 [1, 2, 3, 4, 5, 10, 20].toPArray' 10 — loop value/print subset possible, but PArray iteration and exception harness differ; not yet ported. |
| eval line 34 | reviewed_adaptation_pending | #eval check (f1 [1, 2, 3, 4, 5, 10, 20].toPArray' 10) (pure 16) — loop value/print subset possible, but PArray iteration and exception harness differ; not yet ported. |
| eval line 117 | reviewed_adaptation_pending | #eval check (f1 (List.range 100).toPArray' 1000) (f2 (List.range 100).toPArray' 1000) — loop value/print subset possible, but PArray iteration and exception harness differ; not yet ported. |

### [tests/lean/run/grind_array.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/grind_array.lean)

SHA256 `9a08ff36761c7bb78575012cc5f28b17495684c9c6668080afb4b85cb195dafd`; 2 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| uset/list-set conversion theorem | incompatible_direct_contract | Proof-indexed USize set and grind tactic theorem; no executed ownership scenario. |

### [tests/lean/run/matchArrayLit.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/matchArrayLit.lean)

SHA256 `259c3dd4570883416b776799df965910ff6c7e4f96bdd33228438a0e9423f5b3`; 64 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| eqLitOfSize0 | incompatible_direct_contract | Dependent equality theorem over Array literals; proof system absent. |
| eqLitOfSize1 | incompatible_direct_contract | Dependent equality theorem over Array literals; proof system absent. |
| eqLitOfSize2 | incompatible_direct_contract | Dependent equality theorem over Array literals; proof system absent. |
| eqLitOfSize3 | incompatible_direct_contract | Dependent equality theorem over Array literals; proof system absent. |
| matchArrayLit empty branch | incompatible_direct_contract | Dependent motive C and Eq.rec cast/match implementation; no equivalent source eliminator/representation. |
| matchArrayLit singleton branch | incompatible_direct_contract | Dependent motive C and Eq.rec cast/match implementation; no equivalent source eliminator/representation. |
| matchArrayLit three branch | incompatible_direct_contract | Dependent motive C and Eq.rec cast/match implementation; no equivalent source eliminator/representation. |
| matchArrayLit fallback branch | incompatible_direct_contract | Dependent motive C and Eq.rec cast/match implementation; no equivalent source eliminator/representation. |
| matchArrayLit.eq1 | incompatible_direct_contract | Definitional dependent equality theorem; not runtime allocation/reuse validation. |
| matchArrayLit.eq2 | incompatible_direct_contract | Definitional dependent equality theorem; not runtime allocation/reuse validation. |
| matchArrayLit.eq3 | incompatible_direct_contract | Definitional dependent equality theorem; not runtime allocation/reuse validation. |

### [tests/lean/run/missingSizeOfArrayGetThm.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/missingSizeOfArrayGetThm.lean)

SHA256 `734e8e8cc4d651254ab70bdc67d8ec0677f86742ec02fb7521496b4ef43a8805`; 13 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| Node empty/node/leaf constructors | incompatible_direct_contract | Generic inductive data, proof-oriented recursion and exact Lean ADT layout absent; existing managed recursive tree tests cover a related acyclic ownership shape only. |
| Node.FixedBranching cases | incompatible_direct_contract | Prop-valued recursive theorem and proof-indexed child access; no runtime Boolean predicate claimed. |
| MNode proof-bearing structure | incompatible_direct_contract | Erased branching proof dependent on Nat parameter, not ordinary stored scalar metadata. |

### [tests/lean/run/subarray_split.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/subarray_split.lean)

SHA256 `da2b2793766b6b9df900fe13658889db1760aea99f555f29dfd1f116eb6b1686`; 91 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| abc parent array/subarray bindings | incompatible_direct_contract | Subarray owns persistent Array backing with ranges; Minyar has no List Subarray type. A custom view record would be a distinct adaptation. |
| eval line 20 | incompatible_direct_contract | #eval (#[1,2,3,4].toSubarray.split 0) — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 24 | incompatible_direct_contract | #eval (#[1,2,3,4].toSubarray.split 1) — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 28 | incompatible_direct_contract | #eval (#[1,2,3,4].toSubarray.split 2) — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 32 | incompatible_direct_contract | #eval (#[1,2,3,4].toSubarray.split 3) — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 36 | incompatible_direct_contract | #eval (#[1,2,3,4].toSubarray.split ⟨4, by decide⟩) — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 40 | incompatible_direct_contract | #eval (#[1,2,3,4].toSubarray (start := 1) \|>.split ⟨2, by decide⟩) — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 45 | incompatible_direct_contract | #eval abc.split 0 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 49 | incompatible_direct_contract | #eval abc.split 1 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 53 | incompatible_direct_contract | #eval abc.split 2 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 57 | incompatible_direct_contract | #eval abc.split 3 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 65 | incompatible_direct_contract | #eval #[1,2,3].toSubarray.take 0 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 69 | incompatible_direct_contract | #eval #[1,2,3].toSubarray.take 1 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 72 | incompatible_direct_contract | #eval #[1,2,3].toSubarray.take 2 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 75 | incompatible_direct_contract | #eval #[1,2,3].toSubarray.take 100 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 79 | incompatible_direct_contract | #eval #[1,2,3].toSubarray.drop 0 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 83 | incompatible_direct_contract | #eval #[1,2,3].toSubarray.drop 1 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 87 | incompatible_direct_contract | #eval #[1,2,3].toSubarray.drop 2 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |
| eval line 91 | incompatible_direct_contract | #eval #[1,2,3].toSubarray.drop 100 — absent Subarray range-view API; manual List copying removes backing-owner/view retention obligation. No direct port. |

### [tests/lean/run/toArrayEq.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/run/toArrayEq.lean)

SHA256 `46f2d8edfb45078207f2858acb3617d6b936d9f1ed4313c04ec7826528ed4925`; 12 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| Foo inductive deriving BEq | incompatible_direct_contract | Generic ADT-generated structural equality absent; Minyar records and Lists explicitly lack equality. |
| example line 6 | incompatible_direct_contract | example : Foo.foo 0 ≠ Foo.foo 1 := by simp — proof/structural Array or ADT equality absent. |
| example line 8 | incompatible_direct_contract | example : #[0] ≠ #[1] := by simp — proof/structural Array or ADT equality absent. |
| example line 10 | incompatible_direct_contract | example : #[Foo.foo 0] ≠ #[Foo.foo 1] := by simp — proof/structural Array or ADT equality absent. |
| example line 12 | incompatible_direct_contract | example : Foo.foos #[.foo 0] ≠ Foo.foos #[.foo 1] := by simp — proof/structural Array or ADT equality absent. |

### [tests/lean/simpArrayIdx.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/lean/simpArrayIdx.lean)

SHA256 `73e871c91f17944310bd9643039990648b53e8c0c6654aeca769a8118e4c3635`; 26 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| directive line 10 | incompatible_direct_contract | #check_simp (i + 0) ~> i — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 12 | incompatible_direct_contract | #check_simp (a.set! i v)[i] ~> v — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 13 | incompatible_direct_contract | #check_simp (a.set! i v)[i]! ~> (a.setIfInBounds i v)[i]! — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 14 | incompatible_direct_contract | #check_simp (a.set! i v).getD i d ~> if i < a.size then v else d — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 15 | incompatible_direct_contract | #check_simp (a.set! i v)[i] ~> v — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 18 | incompatible_direct_contract | #check_simp (a.set! i v)[j]'j_lt  ~> (a.setIfInBounds i v)[j]'_ — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 19 | incompatible_direct_contract | #check_simp (a.setIfInBounds i v)[j]'j_lt !~> — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |
| directive line 23 | incompatible_direct_contract | #check_tactic (a.set! i v)[i]? ~> .some v by simp[p] — Theorem simplification/tactic contract, not executing compiled ownership. Proof-indexed/getD/Option/default access semantics differ; Minyar out-of-bounds access terminates rather than returning default. |

### [tests/playground/persistentarray.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/playground/persistentarray.lean)

SHA256 `58b8f5b0c01cead7a37b292dce6b053afefa2c05ed5051d4a66b96a88894977a`; 50 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| MyArray historical alias/import | incompatible_direct_contract | Playground imports old init.data.persistentarray spelling; no assertion it executes in this pinned toolchain. Specialized persistent-array layout/API absent. |
| mkMyArray fold/push | incompatible_direct_contract | Higher-order Nat fold and persistent append absent. Fresh indexed List construction can map values, not radix-tree lifetime. |
| check/checkId | incompatible_direct_contract | Higher-order predicate and IO exception instrumentation, no Minyar direct callback API. |
| inc1 persistent updates | incompatible_direct_contract | Would need fresh copies to preserve earlier values; shared indexed updates change contract. |
| popTest repeated checks and pop | incompatible_direct_contract | Persistent pop/radix-tree sharing and stats absent; fresh copies would not reproduce reclaim/reuse behavior. |
| main construct/check | incompatible_direct_contract | Historical playground scenario with persistent backing/stats, Nat saturating subtraction and higher-order callbacks; not ported or executed. |
| main increment/check | incompatible_direct_contract | Historical playground scenario with persistent backing/stats, Nat saturating subtraction and higher-order callbacks; not ported or executed. |
| main pop to33 | incompatible_direct_contract | Historical playground scenario with persistent backing/stats, Nat saturating subtraction and higher-order callbacks; not ported or executed. |
| main append1000/check | incompatible_direct_contract | Historical playground scenario with persistent backing/stats, Nat saturating subtraction and higher-order callbacks; not ported or executed. |
| main pop all/check | incompatible_direct_contract | Historical playground scenario with persistent backing/stats, Nat saturating subtraction and higher-order callbacks; not ported or executed. |

### [tests/playground/pldi/array_map.lean](https://github.com/leanprover/lean4/blob/50aaf682e9b74ab92880292a25c68baa1cc81c87/tests/playground/pldi/array_map.lean)

SHA256 `4f7324248ce1cd5ad7a6512213ff6923deb89c0d1f357e7cf147544dc9353cb8`; 33 lines; source_read_and_semantically_reviewed.

| Upstream unit | Disposition | Reason / completed evidence |
| --- | --- | --- |
| umapAux save element then clear slot then callback | covered_existing_contract | Unsafe generic NonScalar/unsafeCast/placeholder representation and callback API absent. Related obligation keep projected child across container overwrite is covered by test_nim_returned_member_survives_same_slot_overwrite and constructor projection adaptation; exact in-place generic mapping not certified. |
| umap unsafe coercions | incompatible_direct_contract | unsafeCast generic specialized backing has no direct Minyar counterpart; no native unsafe memory oracle. |
| map safe foldl versus implemented_by umap | incompatible_direct_contract | Replacement of pure function by unsafe specialized implementation and higher-order fold absent. |
| compiler.extract_closed false | harness_only | Compiler optimization directive; no corresponding option contract. |
| tst1 stringify numeric values | reviewed_adaptation_pending | Compatible explicit fresh List output values possible, but no higher-order/NonScalar reuse equivalence and no new memory gap. |
| tst2 map same source twice then append | reviewed_adaptation_pending | Fresh managed output Lists can adapt dual-source lifetimes; generic/native persistent map/append reuse not covered, candidate pending. |
| eval line 25 | reviewed_adaptation_pending | #eval tst1 — historical unsafe higher-order map playground; named value subset still pending and no upstream runtime execution. |
| eval line 33 | reviewed_adaptation_pending | #eval tst2 — historical unsafe higher-order map playground; named value subset still pending and no upstream runtime execution. |

