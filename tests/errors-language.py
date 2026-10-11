#!/usr/bin/env python3
"""Compiler-owned generic results, exhaustive handling, propagation and cleanup.

Original scenarios adapted from primary peer tests; provenance is recorded in
docs/research/errors-language.md. Execution uses the allocation/debt oracle.
"""
import hashlib
import os
from pathlib import Path
import unittest
from callbacks import Callbacks
from regressions import ROOT, LINK_FLAGS
from llvm_sanitizer import prepare_llvm_for_link, address_sanitizer_enabled

DEFAULT = 'minyarc-errors-sanitize' if address_sanitizer_enabled(LINK_FLAGS) else 'minyarc-errors'
FRONTEND = Path(os.environ.get('MINYAR_ERRORS_COMPILER', ROOT / 'build' / DEFAULT))

class ErrorsLanguage(Callbacks):
    def setUp(self):
        super().setUp()
        for path in (FRONTEND, ROOT / 'compiler/errors-compiler.min',
                     ROOT / 'compiler/build-errors-compiler.py'):
            if path.is_file():
                self.evidence.inputs[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()

    def compile(self, source):
        self.serial += 1
        path = self.directory / f'case{self.serial}.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        result = self.evidence.run([str(FRONTEND), str(path), str(llvm), *self.compiler_arguments],
            capture_output=True, text=True, timeout=30, phase='compile-errors')
        if result.returncode == 0:
            prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def test_generic_variants_and_zero_false_success(self):
        self.executes("""let number = Ok<Integer, Text>(0)
match number { Ok(value) { print(value) } Err(error) { print(error) } }
let flag = Ok<Boolean, Integer>(false)
match flag { Err(code) { print(code) } Ok(value) { print(value) } }
let failed = Err<Bytes, Text>("bad" + " packet")
match failed { Ok(data) { print(data.length) } Err(error) { print(error) } }
print("alive")
""", '0\nfalse\nbad packet\nalive\n')

    def test_malformed_packet_is_recoverable(self):
        self.executes("""function parse(packet: Bytes): Result<Integer, Text> {
    if packet.length < 2 { return Err<Integer, Text>("short" + " packet") }
    return Ok<Integer, Text>(packet[0] * 256 + packet[1])
}
let valid = Bytes(2); valid[0] = 1; valid[1] = 2
for packet in [Bytes(1), valid] {
    match parse(packet) { Ok(value) { print(value) } Err(error) { print(error) } }
}
print("recovered")
""", 'short packet\n258\nrecovered\n')

    def test_try_changes_success_type_preserves_exact_error_type(self):
        self.executes("""function read(good: Boolean): Result<Bytes, Text> {
    if !good { return Err<Bytes, Text>("read" + " failed") }
    return Ok<Bytes, Text>(Bytes("abc"))
}
function count(good: Boolean): Result<Integer, Text> {
    let guard = ["owned" + " local"]
    let data = try read(good)
    return Ok<Integer, Text>(data.length + guard.length)
}
match count(true) { Ok(n) { print(n) } Err(e) { print(e) } }
match count(false) { Ok(n) { print(n) } Err(e) { print(e) } }
print("after")
""", '4\nread failed\nafter\n')

    def test_nested_results_and_lists_have_typed_owned_payloads(self):
        self.executes("""let nested = Ok<Result<List<Text>, Bytes>, Text>(
    Err<List<Text>, Bytes>(Bytes("binary")))
match nested {
    Ok(inner) { match inner {
        Ok(words) { print(words.length) }
        Err(data) { print(Text(data)) }
    } }
    Err(error) { print(error) }
}
let values: List<Result<Text, Integer>> = []
values.add(Ok<Text, Integer>("first" + "!"))
values.add(Err<Text, Integer>(9))
for result in values { match result {
    Ok(text) { print(text) } Err(code) { print(code) }
} }
""", 'binary\nfirst!\n9\n')

    def test_match_payload_survives_scrutinee_replacement_and_aliasing(self):
        self.executes("""record Box { results: List<Result<Text, Text>> }
let box = Box { results: [Ok<Text, Text>("old" + "!")] }
let saved = box.results[0]
match box.results[0] {
    Ok(value) {
        box.results[0] = Err<Text, Text>("new" + "!")
        print(value)
    }
    Err(error) { print(error) }
}
match saved { Ok(value) { print(value) } Err(error) { print(error) } }
match box.results[0] { Ok(value) { print(value) } Err(error) { print(error) } }
""", 'old!\nold!\nnew!\n')

    def test_nested_early_return_and_error_cleanup(self):
        self.executes("""function leaf(n: Integer): Result<Text, Text> {
    let local = Bytes("owned")
    if n == 2 { return Err<Text, Text>("error" + Text(n)) }
    return Ok<Text, Text>("value" + Text(n) + Text(local.length))
}
function outer(n: Integer): Result<Text, Text> {
    let locals = [Bytes("a"), Bytes("b")]
    for i in 0..4 {
        if i == n {
            let value = try leaf(n)
            if value.length > 0 { return Ok<Text, Text>(value + Text(locals.length)) }
        }
    }
    return Err<Text, Text>("missing" + "!")
}
for n in 0..5 {
    match outer(n) { Ok(value) { print(value) } Err(error) { print(error) } }
}
""", 'value052\nvalue152\nerror2\nvalue352\nmissing!\n')

    def test_result_returning_callback_and_captured_result(self):
        self.executes("""function maker(seed: Result<Text, Text>): Callback<Boolean, Result<Text, Text>> {
    return function(good: Boolean): Result<Text, Text> {
        let owned = Bytes("callback")
        let value = try seed
        if !good { return Err<Text, Text>(value + Text(owned.length)) }
        return Ok<Text, Text>(value + "!")
    }
}
let callback = maker(Ok<Text, Text>("captured" + "!"))
match callback(true) { Ok(v) { print(v) } Err(e) { print(e) } }
match callback(false) { Ok(v) { print(v) } Err(e) { print(e) } }
let failed = maker(Err<Text, Text>("failure" + "!"))
match failed(true) { Ok(v) { print(v) } Err(e) { print(e) } }
""", 'captured!!\ncaptured!8\nfailure!\n')

    def test_exhaustiveness_duplicate_and_unknown_arms_are_errors(self):
        for arms, diagnostic in [
            ('Ok(v) { print(v) }', 'match must handle both Ok and Err'),
            ('Err(e) { print(e) }', 'match must handle both Ok and Err'),
            ('Ok(v) {} Ok(w) {} Err(e) {}', 'duplicate result arm'),
            ('Ok(v) {} Err(e) {} Other(x) {}', 'expected Ok or Err'),
            ('_ {}', 'expected Ok or Err'),
        ]:
            with self.subTest(arms=arms):
                self.rejects('let r = Ok<Integer, Text>(1)\nmatch r { ' + arms + ' }\n',
                             diagnostic)

    def test_match_requires_result_and_payload_is_scoped(self):
        self.rejects('match 42 { Ok(v) {} Err(e) {} }\n', 'match needs a Result')
        self.rejects('let r = Ok<Integer, Text>(1)\nmatch r { Ok(v) {} Err(e) {} }\nprint(v)\n',
                     "find a value named 'v'")

    def test_constructors_and_bindings_are_type_checked(self):
        self.rejects('let r = Ok<Integer, Text>("wrong")\n', 'result payload has the wrong type')
        self.rejects('let r = Err<Integer, Text>(42)\n', 'result payload has the wrong type')
        self.rejects('let r: Result<Integer, Text> = Ok<Boolean, Text>(false)\n',
                     'does not match its declared type')
        self.rejects('let r: Result<Nothing, Text> = Err<Nothing, Text>("bad")\n',
                     'Nothing cannot be used as a value type')

    def test_result_representation_is_not_public(self):
        for field in ('ok', 'value', 'error'):
            self.rejects('let r = Ok<Integer, Text>(1)\nprint(r.' + field + ')\n',
                         'Result payloads are only accessible through match or try')
        self.rejects('record minyar_result_0 { forged: Integer }\n',
                     'reserved result compiler name')

    def test_try_requires_result_function_and_identical_error(self):
        self.rejects('let value = try Ok<Integer, Text>(1)\n', 'try requires a Result-returning function')
        self.rejects('function f(): Result<Integer, Integer> { let v = try Err<Integer, Text>("bad"); return Ok<Integer, Integer>(v) }\n',
                     'try error type must match the enclosing Result error type')
        self.rejects('function f(): Result<Integer, Text> { let v = try 42; return Ok<Integer, Text>(v) }\n',
                     'try needs a Result')
        self.rejects('function f(): Result<Integer, Text> { return try Ok<Integer, Text>(1) }\n',
                     'try is only supported as a binding initializer')

    def test_match_both_returns_is_exhaustive_function_return(self):
        self.executes("""function choose(r: Result<Text, Text>): Text {
    match r { Ok(v) { return v } Err(e) { return e } }
}
print(choose(Ok<Text, Text>("ok" + "!")))
print(choose(Err<Text, Text>("error" + "!")))
""", 'ok!\nerror!\n')

    def test_errors_in_a_module_have_generic_type_identity(self):
        (self.directory / 'packet.min').write_text("""public record Failure { message: Text }
public function parse(packet: Bytes): Result<Integer, Failure> {
    if packet.length == 0 { return Err<Integer, Failure>(Failure { message: "empty" + "!" }) }
    return Ok<Integer, Failure>(packet[0])
}
""")
        self.executes("""use "./packet.min" as packet
function wrapper(): Result<Text, packet.Failure> {
    let n = try packet.parse(Bytes())
    return Ok<Text, packet.Failure>(Text(n))
}
match wrapper() { Ok(v) { print(v) } Err(e) { print(e.message) } }
""", 'empty!\n')

if __name__ == '__main__':
    unittest.main()
