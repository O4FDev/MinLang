# Recorded backlog implementation, round 2

All 119 assigned records are accounted for individually in `implemented-round2-progress.jsonl`. **99 have validated implementations or matching existing coverage; 20 remain open.** This does not complete the larger source audit or the project goal. No production source, shared manifest, Makefile, CI or central implementation ledger was edited.

The ready resolutions comprise Python 13, Swift 35, Ruby 12 and Lua 39. `implemented-round2-batch.jsonl` contains these 99 scoped resolutions; `implemented-round2-cases.jsonl` contains 33 new passing methods. The owned suite now has 47 methods: 11 previously integrated, 33 newly passing, and three failing regressions exposing production gaps.

Validation ran in focused groups, preserving each entire method and generated domain. There is no all-green full-suite claim. Native executable cases passed O0/O2/O3/Os, normal ASan/UBSan cases passed O0/O2, and ownership-sensitive positive cases passed the ownership runtime. Pure rejection cases are frontend checks. Two C/allocator methodology methods intentionally use fixed O2 and require explicit exceptions in the parent's manifest checker.

Validated domains include:

- Ruby's exact 79 signed64-compatible VS values: all 6,241 ordered pairs, safe arithmetic and inverses, six Boolean comparisons through typed calls and List storage, and quotient/remainder reconstruction. Another 1,328 overflow and 158 zero-divisor executions run per optimization. Arbitrary precision and absent Ruby APIs are excluded.
- Every 1,092 token in Ruby's lexical product, Python's separator cases, and every byte at identifier start and continuation. All 116 accepted identifier compositions execute.
- Lua's Boolean generator restricted to its three Boolean-compatible leaves: 26,823 syntax trees through four leaves, both global values, local/literal false binding, branch/results and independent short-circuit visit traces. All 140 chunks passed native four-optimization validation in 344.5 seconds and sanitizer validation in 271.5 seconds. No sampled substitute is used.
- All 23 List literal capacity sizes, selected owned-record literals, 300 dynamic fragments, Unicode/NUL assembly, malformed source/BOM inputs and supported operator placements.
- Six workloads using the existing allocation campaign: scalar call, empty List, file read, owned-record growth, join100 and join300. Both cleanup budgets passed native and sanitizer allocation/resize ordinals, payload-byte boundaries, forced movement and cleanup controls. The unwrapped scalar call allocated nothing; an explicit Text output wrapper permits meaningful failpoints without promising Lua's allocation schedule.
- Nineteen capacity configurations per mode: full small heap/cache/cleanup-budget combinations in fixed/lazy profiles, plus default controls. These reuse the existing C exact storage and alias oracle.
- Required-suite negative controls for a compiler emitting a different valid program and a link-incompatible runtime. The fake compiler is a compiled C executable, independently verified to copy its intended LLVM. Cwd, environment and output isolation are checked separately.

Still open:

- Nine filename vectors retain the upstream non-Apple guard and have no runtime validation on this macOS host.
- Two source keys refer to the parent's Linux-only `/dev/full` test. Linux validation remains unavailable.
- One Python unary-100000 source shape passes the native gate, but the parent reports a sanitized compiler stack-overflow abort.
- Two Swift numeric-name keys: `function 1() {}` and `record 13 {}` currently succeed and emit LLVM. The four floatlike/digit-prefix variants pass separately.
- Three Ruby malformed-F1 keys: directly printing `readTextFile` of bytes `F1 61 62 63 64` succeeds and emits malformed bytes. Adding `.length` would hide the ingress gap and was not substituted.
- One Lua multiline diagnostic key: seven shapes are implemented; five binary/ordinary-call errors lack source locations, while unary and missing-method cases carry locations.
- Two Lua shared-runner reporting keys require parent-owned capability inventory and consolidated surviving skip reasons. Successful Evidence cleanup currently discards filename exclusions. Incompatibility checks do not substitute for reporting.

The three new failing methods reproduce in `build/peer-pyswru-round2-production-gaps-native.log` (11 subcase failures) and `build/peer-pyswru-round2-production-gaps-sanitize.log` (nine subcase failures). They are omitted from the passing manifest fragment until fixed. Every ready source row has precise test references and validation logs; body hashes distinguish validated methods from later additive edits.

Parent integration must import the 99 resolutions, merge the 33 case entries, add the ownership subset below, support the two fixed-O2 host-method records, fix the three failing methods and the existing unary sanitizer failure, and finish platform and reporting work. The full source audit remains incomplete.

Additional ownership gate methods, all in `PeerPythonSwiftRubyLua`:

- `test_signed_integer_peer_corpus_safe_arithmetic_and_boolean_storage`
- `test_boolean_list_toggle_keeps_other_elements`
- `test_supplementary_scalar_23456_has_exact_utf8`
- `test_nul_prefix_slices_and_control_fragment_join`
- `test_nested_triangular_loops_preserve_outer_binding`
- `test_long_ascii_literal_and_supported_escapes`
- `test_list_literal_capacity_boundaries_and_computed_elements`
- `test_three_hundred_owned_fragments_join_after_reassignment`
- `test_ascii_and_empty_scalar_sequence_assembly`
- `test_runner_cwd_environment_and_output_isolation`

These passed in `build/peer-pyswru-round2-ownership.log` and `build/peer-pyswru-round2-ownership-extra.log`. All fixture hashes are recorded in `implemented-round2-artifacts.jsonl`.

Frozen suite SHA256: `7c0c26d7507648e76f9b927b79ead99b1f323cf7bd69e5e81ca36c09c57e9ef9`.
