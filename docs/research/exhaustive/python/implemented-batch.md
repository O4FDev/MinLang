# Implemented peer batch

11 original regression methods in `tests/peer-python-swift-ruby-lua.py` and fixture `tests/peer-pyswru-vectors.json`. 114 exact scoped upstream source keys fully validated. No upstream test-body code copied; literal/byte/graph inputs retain pinned provenance in fixture and ledger. No production bug found.

Native suite:11passed at O0/O2/O3/Os. ASan/UBSan normalruntime:11passed at O0/O2. Ownershipruntime:9positive methods passed at O0/O2. The final filename change received separate focused native4opt and sanitizerO0/O2 reruns; each optimization must recreate outputfiles and host byte checks happen immediately.

Nine Apple-excluded filename vectors (11through19) are implemented behind their source platformguard but not run here; not included in implemented-batch.jsonl. No C/POSIX locale setup claims beyond those explicit environmentvalues.

Root integration is required: import implemented-cases.jsonl into peer-cases.json, wire suite into normal/optimization/sanitizer gates, and register suite class in audit checker plus host suite catalogue. No shared manifest,Makefile,CI or central implementations ledger was edited.

Ownership subset:

- `PeerPythonSwiftRubyLua.test_python_literal_payloads_match_independent_utf8_files`
- `PeerPythonSwiftRubyLua.test_swift_flag_and_mathematical_scalar_literals`
- `PeerPythonSwiftRubyLua.test_utf8_program_arguments_in_c_and_posix_locales`
- `PeerPythonSwiftRubyLua.test_three_hundred_positional_parameters_and_values`
- `PeerPythonSwiftRubyLua.test_five_module_cycle_shapes_and_acyclic_controls`
- `PeerPythonSwiftRubyLua.test_iterative_fibonacci_uses_previous_pair`
- `PeerPythonSwiftRubyLua.test_parenthesized_division_and_mixed_unary_precedence`
- `PeerPythonSwiftRubyLua.test_ruby_negation_at_signed32_transition`
- `PeerPythonSwiftRubyLua.test_ruby_quotient_remainder_operand_placements`

Frozen source SHA256: `9d368ee8319c3cdb62fd961b7430353e302eb69a9b030fad545ad0ea0d8ca2fa`.
Fixture SHA256: `562e4c3a54b971fcf542ec408b219d132a6ff35a41c08f390263a82cc85c40b1`.

All19 filename fixture/candidate values were independently matched with pinned-source AST literal_eval without executing the upstream module; see filename-fixture-correspondence.jsonl. No data mismatch was found. The test now explicitly asserts U+2000/U+2001/U+2003 triplets for names16/17/18 and rejects unevaluated backslash-u sequences before platform filtering. Nine guarded runtime cases remain excluded on macOS.
