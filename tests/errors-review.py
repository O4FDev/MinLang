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


    def test_review_each_result_generic_delimiter_keeps_lexical_kind(self):
        headers = [
            'Ok<Integer, Text>(1)', 'Err<Integer, Text>("bad")',
            'Ok<List<Integer>, Text>([1])',
            'Ok<Result<Integer, Text>, Bytes>(Ok<Integer, Text>(1))',
        ]
        import re
        for constructor in headers:
            for match in re.finditer(r'>>|[<,>]', constructor):
                mutated = constructor[:match.start()] + '"' + match.group() + '"' + constructor[match.end():]
                with self.subTest(constructor=mutated):
                    result, llvm = self.compile('let result = ' + mutated + '\n')
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertFalse(llvm.exists())
                    self.assertNotIn('List position', result.stderr)

    def test_review_collect_short_circuits_before_fatal_callback(self):
        self.executes("""function collect(calls: List<Callback<Result<Integer, Text>>>): Result<List<Integer>, Text> {
    let collected: List<Integer> = []
    for call in calls {
        let value = try call()
        collected.add(value)
    }
    return Ok<List<Integer>, Text>(collected)
}
let first = function(): Result<Integer, Text> { return Ok<Integer, Text>(42) }
let error = function(): Result<Integer, Text> { return Err<Integer, Text>("stop" + "!") }
let fatal = function(): Result<Integer, Text> { fail("must never run"); return Ok<Integer, Text>(0) }
match collect([first, error, fatal]) {
    Ok(values) { print(values.length) }
    Err(error) { print(error) }
}
match collect([first, first]) {
    Ok(values) { print(values[0] + values[1]) }
    Err(error) { print(error) }
}
""", 'stop!\n84\n')

    def test_review_match_and_try_evaluate_input_once(self):
        self.executes("""record Counter { calls: Integer }
function next(counter: Counter): Result<Integer, Text> {
    counter.calls = counter.calls + 1
    return Ok<Integer, Text>(counter.calls)
}
function twice(counter: Counter): Result<Integer, Text> {
    let first = try next(counter)
    match next(counter) {
        Ok(second) { return Ok<Integer, Text>(first + second) }
        Err(error) { return Err<Integer, Text>(error) }
    }
}
let counter = Counter { calls: 0 }
match twice(counter) { Ok(value) { print(value) } Err(error) { print(error) } }
print(counter.calls)
""", '3\n2\n')

    def test_review_udp_truncation_empty_packet_wouldblock_and_recovery(self):
        self.native_sources = (str(language.ROOT / 'runtime/native/net.c'),)
        self.executes("""use "results" as results
use "errors" as errors
use "net" as net
let receiver = net.udp("127.0.0.1", 0)
let sender = net.udp("127.0.0.1", 0)
print(receiver >= 0 && sender >= 0)
print(net.udpConnect(sender, "127.0.0.1", net.localPort(receiver)))
match results.receiveDatagram(receiver, 16) {
    Ok(read) { print("unexpected initial packet") }
    Err(error) { print(errors.code(results.error(error)) == errors.wouldBlockCode()) }
}
match results.write(sender, Bytes("abcdef")) { Ok(n) { print(n) } Err(e) { print(errors.message(e)) } }
print(net.ready(receiver, 1000))
let failed = results.receiveDatagram(receiver, 3)
match failed {
    Ok(read) { print("unexpected full packet") }
    Err(error) {
        print(errors.code(results.error(error)) == errors.truncatedCode())
        print(Text(results.prefix(error)))
    }
}
match results.write(sender, Bytes()) { Ok(n) { print(n) } Err(e) { print(errors.message(e)) } }
print(net.ready(receiver, 1000))
match results.receiveDatagram(receiver, 16) {
    Ok(read) { print(results.ended(read)); print(results.data(read).length) }
    Err(error) { print(errors.message(results.error(error))) }
}
match failed { Ok(read) { print("unexpected") } Err(error) { print(Text(results.prefix(error))) } }
net.close(sender); net.close(receiver)
""", 'true\ntrue\ntrue\n6\ntrue\ntrue\nabc\n0\ntrue\nfalse\n0\nabc\n')


    def test_review_tcp_short_reads_and_eof_are_distinct(self):
        self.native_sources = (str(language.ROOT / 'runtime/native/net.c'),)
        self.executes("""use "net" as net
use "results" as results
use "errors" as errors
let listener = net.listen("127.0.0.1", 0, 4)
let sender = net.connect("127.0.0.1", net.localPort(listener))
let receiver = net.accept(listener)
print(listener >= 0 && sender >= 0 && receiver >= 0)
match results.write(sender, Bytes("abc")) { Ok(n) { print(n) } Err(e) { print(errors.message(e)) } }
net.close(sender)
print(net.ready(receiver, 1000))
match results.read(receiver, 2) {
    Ok(read) { print(Text(results.data(read))); print(results.ended(read)) }
    Err(error) { print(errors.message(results.error(error))) }
}
match results.read(receiver, 16) {
    Ok(read) { print(Text(results.data(read))); print(results.ended(read)) }
    Err(error) { print(errors.message(results.error(error))) }
}
match results.read(receiver, 16) {
    Ok(read) { print(results.data(read).length); print(results.ended(read)) }
    Err(error) { print(errors.message(results.error(error))) }
}
net.close(receiver); net.close(listener)
""", 'true\n3\ntrue\nab\nfalse\nc\nfalse\n0\ntrue\n')

    def test_review_inactive_reference_slots_are_null_and_unowned(self):
        # A test-only LLVM call checks the real slots immediately before each
        # match tag read. Preserve the uninstrumented IR as replay evidence.
        self.native_helpers = """
void review_result_slots(MinyarRecord *result) {
    assert(result->length == 3);
    long long good = result->values[0];
    assert(good == 0 || good == 1);
    unsigned char *references = (unsigned char *)(result->values + result->length);
    long long active = good ? 1 : 2, inactive = good ? 2 : 1;
    assert(references[0] == 0);
    assert(references[active] == 1);
    assert(references[inactive] == 0);
    assert(result->values[active] != 0);
    assert(result->values[inactive] == 0);
}
"""
        original_compile = self.compile
        def compile_with_slot_assertions(source):
            import re
            result, llvm = original_compile(source)
            if result.returncode == 0:
                original = llvm.read_text()
                llvm.with_suffix('.original.ll').write_text(original)
                pattern = r'(?m)^(  %[^ ]+ = call i64 @minyar_record_get\(ptr ([^,]+), i64 0\)\n)'
                patched, count = re.subn(pattern,
                    lambda found: '  call void @review_result_slots(ptr ' + found.group(2) + ')\n' + found.group(1),
                    original)
                self.assertEqual(count, 2, 'instrumentation must cover both active slots')
                patched += '\ndeclare void @review_result_slots(ptr)\n'
                llvm.write_text(patched)
                self.evidence.controls['slot_assertion_instrumentation'] = {
                    'original': llvm.with_suffix('.original.ll').name,
                    'instrumented': llvm.name, 'assertion_calls': count}
            return result, llvm
        self.compile = compile_with_slot_assertions
        try:
            self.executes("""let ok = Ok<Text, Text>("active" + " success")
let error = Err<Text, Text>("active" + " error")
match ok { Ok(value) { print(value) } Err(error) { print(error) } }
match error { Ok(value) { print(value) } Err(error) { print(error) } }
""", 'active success\nactive error\n')
        finally:
            self.compile = original_compile

    def test_review_early_return_reclaims_cycles_before_next_iteration(self):
        self.native_helpers = """
long long minyar_reviewcleanup_live(void) {
    while (rc_pending_count) assert(minyar_rc_poll(1) > 0);
    return (long long)(rc_object_count - rc_immortal_object_count);
}
"""
        self.executes("""function live(): Integer { native "reviewcleanup" }
record Node { results: List<Result<Callback<Integer>, Callback<Integer>>> }
function leaf(good: Boolean): Result<Integer, Integer> {
    if good { return Ok<Integer, Integer>(42) }
    return Err<Integer, Integer>(7)
}
function work(good: Boolean): Result<Integer, Integer> {
    let node = Node { results: [] }
    let callback = function(): Integer { return node.results.length }
    node.results.add(Ok<Callback<Integer>, Callback<Integer>>(callback))
    node.results.add(Err<Callback<Integer>, Callback<Integer>>(callback))
    let local = Bytes(256)
    let value = try leaf(good)
    return Ok<Integer, Integer>(value + local.length)
}
let baseline = live()
for i in 0..64 {
    match work(i % 2 == 0) {
        Ok(value) { if value != 298 { fail("wrong success") } }
        Err(error) { if error != 7 { fail("wrong error") } }
    }
    if live() != baseline { fail("early return retained an owner") }
}
print("clean each iteration")
""", 'clean each iteration\n')

    def test_review_quoted_double_close_is_not_type_punctuation(self):
        for source in [
            'let x: Result<Text, Result<Integer, Bytes">>" = Err<Text, Result<Integer, Bytes>>(Err<Integer, Bytes>(Bytes()))\n',
            'let x: Result<Result<Integer, Bytes>, Text">" = Err<Result<Integer, Bytes>, Text>("bad")\n',
        ]:
            with self.subTest(source=source):
                result, llvm = self.compile(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(llvm.exists())
                self.assertNotIn('List position', result.stderr)

if __name__ == '__main__':
    suite = unittest.TestSuite(ResultReview(name) for name in
        unittest.defaultTestLoader.getTestCaseNames(ResultReview)
        if name.startswith('test_review_'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())

