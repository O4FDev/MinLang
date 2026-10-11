#!/usr/bin/env python3
"""Independent Result review adversaries; run on the optional frontend.

Adapted from Rust's propagation/lexical-scope contracts and Gleam's
exhaustive results, with Minyar's exact object/frame/debt oracle.
"""
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location(
    "result_language_cases", pathlib.Path(__file__).with_name("errors-language.py"))
language = importlib.util.module_from_spec(spec)
spec.loader.exec_module(language)

class ResultReview(language.ErrorsLanguage):
    def test_review_nested_match_shadowing_and_mixed_returns(self):
        self.executes("""function choose(input: Result<Text, Text>, good: Boolean): Text {
    let payload = "outer" + "!"
    match input {
        Err(payload) {
            if good { return payload + " early" }
            print(payload)
        }
        Ok(payload) {
            match Err<Integer, Text>(payload) {
                Ok(payload) { print(payload) }
                Err(payload) { print(payload + " inner") }
            }
        }
    }
    return payload
}
print(choose(Ok<Text, Text>("yes" + "!"), false))
print(choose(Err<Text, Text>("no" + "!"), false))
print(choose(Err<Text, Text>("no" + "!"), true))
""", 'yes! inner\nouter!\nno!\nouter!\nno! early\n')

    def test_review_loop_jumps_and_match_followthrough(self):
        self.executes("""function scan(): Integer {
    let count = 0
    for i in 0..100 {
        let local = Bytes("loop")
        match Ok<Integer, Text>(i) {
            Err(error) { return error.length }
            Ok(value) {
                if value == 3 { break }
                if value == 1 { continue }
                count = count + local.length
            }
        }
    }
    let i = 0
    while i < 5 {
        i = i + 1
        match Err<Text, Integer>(i) {
            Ok(value) { print(value) }
            Err(code) {
                if code == 2 { continue }
                if code == 4 { break }
                count = count + code
            }
        }
    }
    return count
}
print(scan())
""", '12\n')

    def test_review_try_owns_extracted_value_after_input_replacement(self):
        self.executes("""record Store { values: List<Result<Text, Text>> }
function extract(store: Store): Result<Text, Text> {
    let text: Text = try store.values[0]
    store.values[0] = Err<Text, Text>("replaced" + "!")
    return Ok<Text, Text>(text + " kept")
}
let store = Store { values: [Ok<Text, Text>("original" + "!")] }
match extract(store) { Ok(v) { print(v) } Err(e) { print(e) } }
match store.values[0] { Ok(v) { print(v) } Err(e) { print(e) } }
""", 'original! kept\nreplaced!\n')

    def test_review_callback_early_error_is_local_to_inner_callback(self):
        self.executes("""function maker(): Callback<Boolean, Result<Text, Text>> {
    let counter = [0]
    return function(good: Boolean): Result<Text, Text> {
        let nested: Callback<Boolean, Result<Integer, Text>> = function(ok: Boolean): Result<Integer, Text> {
            let guard = Bytes("guard")
            if !ok { return Err<Integer, Text>("inner" + Text(guard.length)) }
            return Ok<Integer, Text>(42)
        }
        let n = try nested(good)
        counter[0] = counter[0] + 1
        return Ok<Text, Text>(Text(n) + ":" + Text(counter[0]))
    }
}
let call = maker()
match call(false) { Ok(v) { print(v) } Err(e) { print(e) } }
match call(true) { Ok(v) { print(v) } Err(e) { print(e) } }
""", 'inner5\n42:1\n')

    def test_review_same_record_spelling_in_distinct_modules_is_not_same_error(self):
        (self.directory / 'left.min').write_text("""public record Failure { text: Text }
public function failRead(): Result<Integer, Failure> {
    return Err<Integer, Failure>(Failure { text: "left" })
}
""")
        (self.directory / 'right.min').write_text("public record Failure { text: Text }\n")
        self.rejects("""use "./left.min" as left
use "./right.min" as right
function wrong(): Result<Integer, right.Failure> {
    let n = try left.failRead()
    return Ok<Integer, right.Failure>(n)
}
""", 'try error type must match')

    def test_review_module_alias_diamond_nested_callback_result_identity(self):
        (self.directory / 'shared.min').write_text("""public record Payload { text: Text }
public function make(): Result<Payload, Text> {
    return Ok<Payload, Text>(Payload { text: "diamond" + "!" })
}
""")
        (self.directory / 'bridge.min').write_text("""use "./shared.min" as source
public function callback(): Callback<Result<source.Payload, Text>> {
    return function(): Result<source.Payload, Text> { return source.make() }
}
""")
        self.executes("""use "./shared.min" as first
use "./shared.min" as second
use "./bridge.min" as bridge
function run(): Result<Text, Text> {
    let call = bridge.callback()
    let result: Result<second.Payload, Text> = call()
    let payload: first.Payload = try result
    return Ok<Text, Text>(payload.text)
}
match run() { Ok(v) { print(v) } Err(e) { print(e) } }
""", 'diamond!\n')

    def test_review_match_inside_module_with_constant_named_payload(self):
        (self.directory / 'worker.min').write_text("""constant payload: Integer = 999
public function process(input: Result<Text, Text>): Text {
    match input {
        Ok(payload) { return payload + " good" }
        Err(payload) { return payload + " bad" }
    }
}
""")
        self.executes("""use "./worker.min" as worker
print(worker.process(Ok<Text, Text>("value" + "!")))
print(worker.process(Err<Text, Text>("error" + "!")))
""", 'value! good\nerror! bad\n')

    def test_review_result_names_remain_values_in_ordinary_comparisons(self):
        self.executes("""let Result = 1
let Ok = 2
let Err = 3
print(Result < 2)
print(Ok < Err)
print(Err < 4)
""", 'true\ntrue\ntrue\n')

    def test_review_quoted_generic_delimiters_are_rejected(self):
        cases = [
            'let x: Result"<"Integer, Text> = Ok<Integer, Text>(1)\n',
            'let x: Result<Integer "," Text> = Ok<Integer, Text>(1)\n',
            'let x: Result<Integer, Text">" = Ok<Integer, Text>(1)\n',
            'let x = Ok"<"Integer, Text>(1)\n',
            'let x = Ok<Integer "," Text>(1)\n',
            'let x = Ok<Integer, Text">"(1)\n',
        ]
        for source in cases:
            with self.subTest(source=source):
                result, llvm = self.compile(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(llvm.exists())
                self.assertNotIn('List position', result.stderr)

    def test_review_truncated_headers_reject_without_runtime_fault(self):
        cases = ['Result<', 'Result<Integer,', 'Result<Result<Integer, Text>',
                 'Ok<Integer, Text>(', 'Err<List<Text>, Result<Integer,']
        for header in cases:
            with self.subTest(header=header):
                result, llvm = self.compile('let x = ' + header + '\n')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(llvm.exists())
                self.assertNotIn('List position', result.stderr)
                self.assertNotIn('callback body', result.stderr)

    def test_review_results_preserve_nested_reference_errors(self):
        self.executes("""function first(good: Boolean): Result<Bytes, Result<List<Text>, Bytes>> {
    if good { return Ok<Bytes, Result<List<Text>, Bytes>>(Bytes("abc")) }
    return Err<Bytes, Result<List<Text>, Bytes>>(Ok<List<Text>, Bytes>(["nested" + "!"]))
}
function second(good: Boolean): Result<Integer, Result<List<Text>, Bytes>> {
    let bytes = try first(good)
    return Ok<Integer, Result<List<Text>, Bytes>>(bytes.length)
}
for good in [false, true] {
    match second(good) {
        Ok(n) { print(n) }
        Err(error) { match error {
            Ok(words) { print(words[0]) }
            Err(bytes) { print(Text(bytes)) }
        } }
    }
}
""", 'nested!\n3\n')

    def test_review_callback_mutation_removes_last_container_owner(self):
        self.executes("""record Node { values: List<Result<Callback<Text>, Callback<Text>>> }
function make(): Node {
    let node = Node { values: [] }
    let callback = function(): Text {
        node.values = []
        return "alive" + "!"
    }
    node.values.add(Ok<Callback<Text>, Callback<Text>>(callback))
    node.values.add(Err<Callback<Text>, Callback<Text>>(callback))
    return node
}
let first = make()
match first.values[0] { Ok(call) { print(call()) } Err(call) { print(call()) } }
let second = make()
match second.values[1] { Ok(call) { print(call()) } Err(call) { print(call()) } }
print(first.values.length); print(second.values.length)
""", 'alive!\nalive!\n0\n0\n')

if __name__ == '__main__':
    suite = unittest.TestSuite(ResultReview(name) for name in
        unittest.defaultTestLoader.getTestCaseNames(ResultReview)
        if name.startswith('test_review_'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())

