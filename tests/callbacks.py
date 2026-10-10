#!/usr/bin/env python3
"""Independent typed closure cases inspired by Rust/Swift ownership tests.

Scenarios, not peer test code, are adapted. Source/license links are recorded
in docs/research/runtime-concurrency-errors.md. Every execution uses the
repository's exact allocation/debt accounting harness at O0 and O2.
"""
import unittest
from pathlib import Path
import importlib.util
import os
import subprocess
from regressions import CompilerTestCase, ROOT, CLANG, LINK_FLAGS
from clang_helpers import clang_command, windows_host
from llvm_sanitizer import prepare_llvm_for_link, address_sanitizer_enabled
import sys
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source

DEFAULT_FRONTEND = 'minyarc-callbacks-sanitize' if address_sanitizer_enabled(LINK_FLAGS) else 'minyarc-callbacks'
COMPILER = Path(os.environ.get('MINYAR_CALLBACK_COMPILER', ROOT / 'build' / DEFAULT_FRONTEND))

class Callbacks(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    def compile(self, source):
        self.serial += 1
        path = self.directory / f'case{self.serial}.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        result = self.evidence.run([str(COMPILER), str(path), str(llvm), *self.compiler_arguments],
                                  capture_output=True, text=True, timeout=30, phase='compile-callback')
        if result.returncode == 0: prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def executes(self, source, expected, optimizations=('-O0', '-O2')):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        harness = self.directory / 'runtime.c'
        contract = (ROOT / 'tests/memory-contracts-runtime.c').read_text()
        harness.write_text(contract.replace('#include "../runtime/minyar_runtime.c"', engine_source(ROOT))
                           + getattr(self, 'native_helpers', ''))
        runtime = harness.with_suffix('.o')
        compiled = self.evidence.run(clang_command([CLANG, '-O1' if LINK_FLAGS else '-O2',
            *LINK_FLAGS, '-DMINYAR_SYSTEM_HEAP=1', '-iquote', str(ROOT / 'runtime'),
            '-c', str(harness), '-o', str(runtime)]), capture_output=True, text=True,
            timeout=30, phase='compile-callback-ownership-runtime')
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        for optimization in optimizations:
            with self.subTest(optimization=optimization):
                executable = llvm.with_suffix('.' + optimization[1:] + ('.exe' if windows_host() else ''))
                native_sources = getattr(self, 'native_sources', ())
                native_flags = ['-lws2_32'] if windows_host() and native_sources else []
                linked = self.evidence.run(clang_command([CLANG, optimization, *LINK_FLAGS,
                    '-Wno-override-module', str(llvm), str(runtime),
                    *native_sources, *native_flags, '-o', str(executable)]),
                    capture_output=True, text=True, timeout=30, phase='link-callback-ownership')
                self.assertEqual(linked.returncode, 0, linked.stderr)
                run = self.evidence.run([str(executable)], capture_output=True, timeout=30,
                                       phase='execute-callback-ownership')
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(run.stdout, expected.encode())
                self.assertEqual(run.stderr, b'')

    def test_native_loop_borrow_has_stable_identity_and_rejects_closed_dispatcher(self):
        self.native_sources = (str(ROOT / 'runtime/native/net.c'),)
        self.executes('''use "eventcallbacks" as callbacks
use "eventloop" as eventloop
use "errors" as errors
let dispatcher = callbacks.value(callbacks.create())
let first = callbacks.nativeLoop(dispatcher)
let second = callbacks.nativeLoop(dispatcher)
print(errors.integerOk(first))
print(errors.integerValue(first) == errors.integerValue(second))
let ready = eventloop.timer(errors.integerValue(first), 0, 0, 7)
print(errors.integerOk(ready))
print(eventloop.events(eventloop.wait(errors.integerValue(first), 0, 8)).length)
print(errors.booleanOk(callbacks.close(dispatcher)))
let closed = callbacks.nativeLoop(dispatcher)
print(errors.integerOk(closed))
print(errors.code(errors.integerError(closed)) == errors.closedCode())
print(errors.integerOk(first))
''', 'true\ntrue\ntrue\n1\ntrue\nfalse\ntrue\ntrue\n')

    def test_scalar_and_reference_captures_escape_creator(self):
        self.executes('''record Box { value: Integer }
function make(box: Box): Callback<Integer, Integer> {
    let offset = 40
    return function(delta: Integer): Integer { return offset + box.value + delta }
}
let box = Box { value: 1 }
let callback = make(box)
box.value = 2
print(callback(3))
''', '45\n')

    def test_no_capture_and_parameter_shadowing(self):
        self.executes('''let value = 999
let noCapture: Callback<Integer, Integer> = function(value: Integer): Integer { return value + 1 }
print(noCapture(41))
''', '42\n')

    def test_capture_environment_closes_reference_cycle(self):
        self.executes('''record Node { value: Integer; callbacks: List<Callback<Integer, Integer>> }
let node = Node { value: 40; callbacks: [] }
let callback = function(delta: Integer): Integer { return node.value + delta }
node.callbacks.add(callback)
let stored = node.callbacks[0]
print(stored(2))
''', '42\n')

    def test_reference_arguments_and_results_survive_indirect_call(self):
        self.executes('''record Box { value: Text }
let callback: Callback<Box, Box> = function(box: Box): Box { return Box { value: box.value + "!" } }
let result = callback(Box { value: "alive" })
print(result.value)
''', 'alive!\n')

    def test_nested_callback_and_recursive_named_function(self):
        self.executes('''function factorial(n: Integer): Integer {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}
function outer(offset: Integer): Callback<Integer, Callback<Integer, Integer>> {
    return function(a: Integer): Callback<Integer, Integer> {
        return function(b: Integer): Integer { return offset + a + factorial(b) }
    }
}
let make = outer(10)
let inner = make(2)
print(inner(3))
''', '18\n')

    def test_cross_module_signature_and_capture_ownership(self):
        (self.directory / 'factory.min').write_text('''public record Box { value: Text }
public function make(box: Box): Callback<Text, Text> {
    return function(suffix: Text): Text { return box.value + suffix }
}
''')
        self.executes('''use "./factory.min" as factory
let callback = factory.make(factory.Box { value: "kept" })
print(callback(" alive"))
''', 'kept alive\n')

    def test_wrong_signature_and_argument_types_are_rejected(self):
        cases = (
            ('let callback: Callback<Integer, Integer> = function(x: Text): Integer { return x.length }\n', 'declared type'),
            ('let callback = function(x: Integer): Integer { return x }\ncallback("bad")\n', 'callback argument'),
            ('let callback = function(): Integer { return 1 }\ncallback(2)\n', 'callback expects'),
        )
        for source, message in cases:
            with self.subTest(source=source):
                result, llvm = self.compile(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertFalse(llvm.exists())

    def test_timer_callbacks_cancel_and_release_cyclic_captures(self):
        self.native_sources = (str(ROOT / 'runtime/native/net.c'),)
        self.executes('''use "eventcallbacks" as callbacks
use "eventloop" as eventloop
use "errors" as errors
record State { calls: Integer; sum: Integer; cancelled: Integer }
let state = State { calls: 0; sum: 0; cancelled: 0 }
let dispatcher = callbacks.value(callbacks.create())
let later = errors.integerValue(callbacks.timer(dispatcher, 1000, 0, 999, function(event: eventloop.Event) { state.calls = state.calls + 100 }))
state.cancelled = later
let first = callbacks.timer(dispatcher, 0, 0, 40, function(event: eventloop.Event) {
    state.calls = state.calls + 1
    state.sum = state.sum + event.token
    if !errors.booleanOk(callbacks.cancel(dispatcher, state.cancelled)) { fail("cancel failed") }
})
if !errors.integerOk(first) { fail("timer failed") }
print(errors.integerValue(callbacks.dispatch(dispatcher, 0, 8)))
print(state.calls)
print(state.sum)
print(errors.booleanOk(callbacks.cancel(dispatcher, errors.integerValue(first))))
print(errors.booleanValue(callbacks.close(dispatcher)))
print(errors.integerOk(callbacks.dispatch(dispatcher, 0, 8)))
''', '1\n1\n40\nfalse\ntrue\nfalse\n')

    def test_generated_capture_values(self):
        # Boundary values and combinations are derived independently; exact
        # sum accounting makes unexpected reads/capture aliasing observable.
        for scalar in (-2147483648, -1, 0, 7, 2147483647):
            with self.subTest(scalar=scalar):
                self.executes(f'''record Box {{ value: Integer }}
function make(base: Integer): Callback<Integer, Integer> {{
    let box = Box {{ value: base }}
    return function(delta: Integer): Integer {{ return box.value + base + delta }}
}}
let callback = make({scalar})
print(callback(11))
''', str(scalar * 2 + 11) + '\n', optimizations=('-O2',))

    def test_cancelled_batch_event_cannot_call_a_reused_slot(self):
        self.native_sources = (str(ROOT / 'runtime/native/net.c'),)
        self.executes('''use "eventcallbacks" as callbacks
use "eventloop" as eventloop
use "errors" as errors
record State { old: Integer; calls: Integer; replacement: Integer }
let state = State { old: 0; calls: 0; replacement: 0 }
let dispatcher = callbacks.value(callbacks.create())
callbacks.timer(dispatcher, 0, 0, 1, function(event: eventloop.Event) {
    state.calls = state.calls + 1
    if !errors.booleanOk(callbacks.cancel(dispatcher, state.old)) { fail("pending cancel failed") }
    state.replacement = errors.integerValue(callbacks.timer(dispatcher, 0, 0, 3, function(next: eventloop.Event) {
        state.calls = state.calls + 100
    }))
})
state.old = errors.integerValue(callbacks.timer(dispatcher, 0, 0, 2, function(event: eventloop.Event) {
    state.calls = state.calls + 10000
}))
print(errors.integerValue(callbacks.dispatch(dispatcher, 0, 8)))
print(state.calls)
print(errors.integerValue(callbacks.dispatch(dispatcher, 0, 8)))
print(state.calls)
print(errors.booleanOk(callbacks.cancel(dispatcher, state.old)))
callbacks.close(dispatcher)
''', '1\n1\n1\n101\nfalse\n')

    def test_udp_read_callback_keeps_empty_datagram_as_success(self):
        self.native_sources = (str(ROOT / 'runtime/native/net.c'),)
        self.executes('''use "eventcallbacks" as callbacks
use "eventloop" as eventloop
use "errors" as errors
use "net" as net
record State { called: Integer; handle: Integer; status: Integer; length: Integer }
let state = State { called: 0; handle: 0; status: -1; length: -1 }
let server = net.udp("127.0.0.1", 0)
let client = net.udp("127.0.0.1", 0)
if server < 0 || client < 0 { fail("UDP bind failed") }
if !net.udpConnect(client, "127.0.0.1", net.localPort(server)) { fail("UDP connect failed") }
let dispatcher = callbacks.value(callbacks.create())
state.handle = errors.integerValue(callbacks.watch(dispatcher, server, eventloop.readableInterest(), 42, function(event: eventloop.Event) {
    let read = net.receiveDatagram(server, 32)
    state.called = state.called + 1
    state.status = errors.bytesStatus(read)
    state.length = errors.bytesValue(read).length
    if event.token != 42 { fail("callback lost token") }
    if !errors.booleanOk(callbacks.cancel(dispatcher, state.handle)) { fail("self cancel failed") }
}))
if !errors.integerOk(net.write(client, Bytes())) { fail("empty UDP write failed") }
print(errors.integerValue(callbacks.dispatch(dispatcher, 1000, 8)))
print(state.called)
print(state.status)
print(state.length)
print(errors.integerValue(callbacks.dispatch(dispatcher, 0, 8)))
callbacks.close(dispatcher)
net.close(client)
net.close(server)
''', '1\n1\n0\n0\n0\n')

    def test_captured_binding_reassignment_has_a_source_diagnostic(self):
        result, llvm = self.compile('''let count = 0
let callback = function(): Integer { count = count + 1; return count }
print(callback())
''')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('captured bindings cannot be reassigned', result.stderr)
        self.assertFalse(llvm.exists())

    def test_nested_parameter_shadow_does_not_capture_outer_object(self):
        self.executes('''record Box { value: Integer }
let box = Box { value: 999 }
let factory = function(): Callback<Box, Integer> {
    return function(box: Box): Integer { return box.value }
}
let callback = factory()
print(callback(Box { value: 42 }))
''', '42\n')

    def test_module_record_types_in_anonymous_signature(self):
        (self.directory / 'factory.min').write_text('''public record Box { value: Text }
public function make(): Callback<Box, Box> {
    return function(box: Box): Box { return Box { value: box.value + "!" } }
}
''')
        self.executes('''use "./factory.min" as factory
let callback = factory.make()
let result = callback(factory.Box { value: "kept" })
print(result.value)
''', 'kept!\n')

    def test_every_incomplete_callback_body_prefix_is_a_diagnostic(self):
        source = 'let callback: Callback<Integer, Integer> = function(value: Integer): Integer { return value + 1 }\n'
        start = source.index('function')
        end = source.rindex('}')
        for length in range(start + 1, end + 1):
            with self.subTest(length=length):
                result, llvm = self.compile(source[:length])
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(llvm.exists())
                self.assertTrue(result.stderr)
                for internal in ('List position', 'record position', 'AddressSanitizer', 'runtime error:', 'Segmentation fault'):
                    self.assertNotIn(internal, result.stderr)

    def test_list_and_nested_callback_signatures_preserve_owned_results(self):
        self.executes('''let factory: Callback<Callback<List<Text>, List<Text>>> = function(): Callback<List<Text>, List<Text>> {
    return function(values: List<Text>): List<Text> { return values.appended("done") }
}
let callback = factory()
let result = callback(["kept"])
print(result[0])
print(result[1])
''', 'kept\ndone\n')

    def test_feature_looking_names_do_not_rewrite_expression_tokens(self):
        self.executes('''let List = 1
let Callback = 1
let callback = function(): Integer { return 42 }
print(List < 2)
print(Callback < 2)
print(8 >> 1)
print(">>")
print(callback())
''', 'true\ntrue\n4\n>>\n42\n')

    def test_idle_cycle_debt_drains_before_the_loop_blocks(self):
        self.native_sources = (str(ROOT / 'runtime/native/net.c'),)
        self.native_helpers = '''
long long minyar_cycleidle_pendingNative(void) { return (long long)rc_pending_count; }
long long minyar_cycleidle_objectsNative(void) { return (long long)(rc_object_count - rc_immortal_object_count); }
long long minyar_cycleidle_nowNative(void) {
#ifdef _WIN32
    return (long long)GetTickCount64();
#else
    struct timespec time; clock_gettime(CLOCK_MONOTONIC, &time);
    return (long long)time.tv_sec * 1000 + time.tv_nsec / 1000000;
#endif
}
'''
        self.executes('''use "eventcallbacks" as callbacks
use "errors" as errors
function pendingNative(): Integer { native "cycleidle" }
function objectsNative(): Integer { native "cycleidle" }
function nowNative(): Integer { native "cycleidle" }
record Node { next: List<Node> }
function garbage() {
    let head = Node { next: [] }
    let cursor = head
    for i in 0..1024 {
        let next = Node { next: [] }
        cursor.next.add(next)
        cursor = next
    }
    cursor.next.add(head)
}
let dispatcher = callbacks.value(callbacks.create())
let baseline = objectsNative()
garbage()
if pendingNative() == 0 || objectsNative() <= baseline { fail("fixture did not leave cyclic debt") }
if errors.integerOk(callbacks.dispatch(dispatcher, -2, 8)) { fail("cleanup hid an invalid timeout") }
let firstWait = nowNative()
if errors.integerValue(callbacks.dispatch(dispatcher, 400, 8)) != 0 { fail("unexpected event") }
if nowNative() - firstWait >= 200 { fail("loop blocked while cyclic debt remained") }
let batches = 0
while pendingNative() != 0 {
    if errors.integerValue(callbacks.dispatch(dispatcher, 100, 8)) != 0 { fail("unexpected event") }
    batches = batches + 1
    if batches > 10000 { fail("idle cleanup did not finish") }
}
if objectsNative() != baseline { fail("idle loop retained cyclic garbage") }
let start = nowNative()
if errors.integerValue(callbacks.dispatch(dispatcher, 100, 8)) != 0 { fail("unexpected event") }
if nowNative() - start < 50 { fail("drained loop spun instead of blocking") }
callbacks.close(dispatcher)
print("idle cycle reclaimed")
''', 'idle cycle reclaimed\n')

if __name__ == '__main__':
    unittest.main()
