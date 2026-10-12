#!/usr/bin/env python3
"""Compiler-owned generic results, exhaustive handling, propagation and cleanup.

Original scenarios adapted from primary peer tests; provenance is recorded in
docs/research/errors-language.md at tag archive/docs-before-cleanup-20261012. Execution uses the allocation/debt oracle.
"""
import hashlib
import os
import shlex
from pathlib import Path
import unittest
import callbacks
from errors_evidence import retain
from regressions import ROOT, LINK_FLAGS, CompilerTestCase
from llvm_sanitizer import prepare_llvm_for_link, address_sanitizer_enabled

DEFAULT = 'minyarc-errors-sanitize' if address_sanitizer_enabled(LINK_FLAGS) else 'minyarc-errors'
FRONTEND = Path(os.environ.get('MINYAR_ERRORS_COMPILER', ROOT / 'build' / DEFAULT))

class ErrorsLanguage(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))
    def setUp(self):
        super().setUp()
        for path in (FRONTEND, ROOT / 'compiler/errors-compiler.min',
                     ROOT / 'compiler/build-errors-compiler.py',
                     ROOT / 'build/compiler.min', ROOT / 'compiler/closure-compiler.min',
                     ROOT / 'scripts/build-closure-compiler.py', ROOT / 'tests/callbacks.py',
                     ROOT / 'tests/errors_evidence.py', ROOT / 'tools/cycle_runtime.py',
                     ROOT / 'library/results.min', ROOT / 'library/errors.min',
                     ROOT / 'library/net.min', ROOT / 'runtime/native/net.c'):
            if path.is_file():
                self.evidence.inputs[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()

    def close_evidence(self):
        result = self._outcome.result
        failed = any(test.id() == self.id() or test.id().startswith(self.id() + ' ')
                     for test, _ in result.failures + result.errors)
        retain(self.evidence, failed)

    def executes(self, source, expected, optimizations=('-O0', '-O2')):
        self.evidence.controls.setdefault('execution_oracles', []).append({
            'source': f'case{self.serial + 1}.min', 'stdout': expected,
            'stderr': '', 'status': 0, 'optimizations': list(optimizations)})
        runtime_flags = shlex.split(os.environ.get('MINYAR_ERRORS_RUNTIME_FLAGS', ''))
        original_run = self.evidence.run
        def run(command, **options):
            if runtime_flags and options.get('phase') == 'compile-callback-ownership-runtime':
                command = [arg for arg in command if arg != '-DMINYAR_SYSTEM_HEAP=1']
                command = command[:1] + runtime_flags + command[1:]
            return original_run(command, **options)
        self.evidence.run = run
        try:
            return callbacks.Callbacks.executes(self, source, expected, optimizations)
        finally:
            self.evidence.run = original_run

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

    def test_result_callback_cycles_in_both_payload_slots_are_collected(self):
        self.executes("""record Node {
    good: List<Result<Callback<Integer, Integer>, Text>>
    bad: List<Result<Text, Callback<Integer, Integer>>>
}
let node = Node { good: []; bad: [] }
let callback = function(n: Integer): Integer { return n + node.good.length + node.bad.length }
node.good.add(Ok<Callback<Integer, Integer>, Text>(callback))
node.bad.add(Err<Text, Callback<Integer, Integer>>(callback))
match node.good[0] { Ok(f) { print(f(40)) } Err(e) { print(e) } }
match node.bad[0] { Ok(v) { print(v) } Err(f) { print(f(39)) } }
""", '42\n41\n')

    def test_propagation_short_circuits_following_callbacks(self):
        self.executes("""record Counter { calls: Integer }
function step(counter: Counter, good: Boolean): Result<Integer, Text> {
    counter.calls = counter.calls + 1
    if !good { return Err<Integer, Text>("stopped" + "!") }
    return Ok<Integer, Text>(counter.calls)
}
function chain(counter: Counter, good: Boolean): Result<Integer, Text> {
    let first = try step(counter, good)
    let second = try step(counter, true)
    return Ok<Integer, Text>(first + second)
}
let counter = Counter { calls: 0 }
match chain(counter, false) { Ok(v) { print(v) } Err(e) { print(e) } }
print(counter.calls)
match chain(counter, true) { Ok(v) { print(v) } Err(e) { print(e) } }
print(counter.calls)
""", 'stopped!\n1\n5\n3\n')

    def test_discarded_result_expression_is_rejected(self):
        self.rejects('Ok<Integer, Text>(1)\n', 'a Result expression must be handled or bound')

    def test_programmer_failures_are_fatal_inside_result_functions(self):
        CompilerTestCase.executes(self, """function bug(): Result<Integer, Text> {
    let data = Bytes(1)
    return Ok<Integer, Text>(data[1])
}
match bug() { Ok(v) { print(v) } Err(e) { print("recovered") } }
""", '', status=1, stderr='Minyar stopped: Bytes position 1 is outside its length of 1.\n')

    def test_ordinary_ir_is_byte_identical(self):
        samples = [
            'print("try"); print("minyar_result_type_0"); print(42)\n',
            'record Box { words: List<Text> }\nlet b = Box { words: ["a" + "b"] }\nprint(b.words[0])\n',
            'function square(n: Integer): Integer { return n * n }\nfor n in 0..10 { print(square(n)) }\n',
        ]
        for source in samples:
            result, llvm = self.compile(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            ordinary = llvm.with_suffix('.ordinary.ll')
            compiler = ROOT / 'build/minyarc'
            baseline = self.evidence.run([str(compiler), str(llvm.with_suffix('.min')),
                str(ordinary), *self.compiler_arguments], timeout=30,
                capture_output=True, text=True, phase='compile-ordinary-identity')
            self.assertEqual(baseline.returncode, 0, baseline.stderr)
            prepare_llvm_for_link(ordinary, LINK_FLAGS)
            self.assertEqual(llvm.read_bytes(), ordinary.read_bytes())

    def test_network_adapter_preserves_data_eof_blocked_failure_and_prefix(self):
        self.native_sources = (str(ROOT / 'runtime/native/net.c'),)
        self.executes("""use "results" as results
use "errors" as errors
let reads = [errors.bytes(Bytes()), errors.endOfStream(), errors.wouldBlock(11),
             errors.bytesFailure(errors.make(7, 9, "bad" + "!")),
             errors.truncated(Bytes("prefix"), 90)]
for read in reads { match results.bytes(read) {
    Ok(value) { print(results.ended(value)); print(results.data(value).length) }
    Err(failure) {
        print(errors.code(results.error(failure)))
        print(errors.nativeCode(results.error(failure)))
        print(Text(results.prefix(failure)))
    }
} }
match results.integer(errors.integer(0)) { Ok(v) { print(v) } Err(e) { print(errors.code(e)) } }
match results.boolean(errors.boolean(false)) { Ok(v) { print(v) } Err(e) { print(errors.code(e)) } }
""", 'false\n0\ntrue\n0\n1\n11\n\n7\n9\n\n12\n90\nprefix\n0\nfalse\n')

    def test_actual_failed_network_read_remains_owned_and_recoverable(self):
        self.native_sources = (str(ROOT / 'runtime/native/net.c'),)
        self.executes("""use "results" as results
use "errors" as errors
let first = results.read(-1, 16)
let second = results.read(-1, 16)
match first {
    Ok(value) { print("unexpected") }
    Err(failure) { print(errors.code(results.error(failure))); print(errors.message(results.error(failure))) }
}
match second {
    Ok(value) { print("unexpected") }
    Err(failure) { print(errors.code(results.error(failure))) }
}
print("still alive")
""", '7\nsocket read failed\n7\nstill alive\n')

    def test_repeated_success_error_nested_return_and_callback_cleanup(self):
        self.executes("""function parse(n: Integer): Result<Text, Text> {
    let data = Bytes("temporary")
    if n % 2 == 0 { return Err<Text, Text>("bad" + Text(n)) }
    return Ok<Text, Text>("good" + Text(n) + Text(data.length))
}
function run(n: Integer): Result<Integer, Text> {
    let locals = [Bytes("one"), Bytes("two")]
    let value = try parse(n)
    return Ok<Integer, Text>(value.length + locals.length)
}
let successes = 0
let failures = 0
let callback: Callback<Integer, Result<Integer, Text>> = function(n: Integer): Result<Integer, Text> {
    let owned = ["callback" + Text(n)]
    let value = try run(n)
    return Ok<Integer, Text>(value + owned.length)
}
for n in 0..1500 {
    match callback(n) {
        Ok(value) { successes = successes + 1 }
        Err(error) { failures = failures + 1 }
    }
}
print(successes); print(failures)
""", '750\n750\n')

    def test_match_binding_can_escape_in_a_callback(self):
        self.executes("""function pick(result: Result<Text, Text>): Callback<Text> {
    match result {
        Ok(payload) { return function(): Text { return payload + "!" } }
        Err(error) { return function(): Text { return error + "!" } }
    }
}
let good = pick(Ok<Text, Text>("good" + " value"))
let bad = pick(Err<Text, Text>("bad" + " value"))
print(good()); print(bad())
""", 'good value!\nbad value!\n')

    def test_all_scalar_payload_encodings_are_typed(self):
        self.executes("""match Ok<Float, Character>(1.5) { Ok(v) { print(v) } Err(e) { print(e) } }
match Err<Float, Character>('界') { Ok(v) { print(v) } Err(e) { print(e) } }
match Ok<Character, Float>('🙂') { Ok(v) { print(v) } Err(e) { print(e) } }
match Err<Character, Float>(2.5) { Ok(v) { print(v) } Err(e) { print(e) } }
""", '1.5\n界\n🙂\n2.5\n')

    def test_malformed_generic_headers_and_quoted_arms_are_rejected(self):
        for source, diagnostic in [
            ('let x: Result<Integer> = 0\n', "expected ','"),
            ('let x: Result<Integer, Text, Bytes> = 0\n', "expected '>'"),
            ('let x = Ok<Integer, Text>(1)\nmatch x { "Ok"(v) {} Err(e) {} }\n',
             'expected Ok or Err'),
        ]:
            with self.subTest(source=source):
                self.rejects(source, diagnostic)

    def test_result_record_literal_cannot_forge_a_tag(self):
        self.rejects('let r = Result<Integer, Text> { ok: true; value: 1; error: "inactive" }\n',
                     'Result values require Ok or Err constructors')
        self.rejects('let r = Ok<Integer, Text>(1)\nr.ok = false\n',
                     'Result payloads are only accessible through match or try')

if __name__ == '__main__':
    unittest.main()
