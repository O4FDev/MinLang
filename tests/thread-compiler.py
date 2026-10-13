

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = '''thread function worker(seed: Integer, input: FrozenBytes, channel: BytesChannel): Integer {
    return seed + input.length
}
'''
MAIN = '''function main() {
    let bytes = Bytes(8)
    let frozen = freezeBytes(bytes)
    let channel = bytesChannel(4096, 8)
    let workerHandle = startThread(worker, 7, frozen, channel)
    print(joinThread(workerHandle))
}
'''


class ThreadCompiler(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minyar-thread-check-')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def compile(self, source, modules=None, success=True, diagnostic=None):
        path = self.work / 'main.min'
        path.write_text(source)
        for name, text in (modules or {}).items():
            (self.work / name).write_text(text)
        ir = self.work / 'program.ll'
        ir.unlink(missing_ok=True)
        result = subprocess.run([str(COMPILER), str(path), str(ir), '--bounded-owners', '32',
                                 '--library', str(ROOT / 'library')],
                                capture_output=True, text=True, timeout=60)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(ir.is_file())
            return ir.read_text()
        self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(ir.exists(), 'failed checking published runnable IR')
        if diagnostic:
            self.assertIn(diagnostic, result.stderr + result.stdout)

    def test_exact_entry_signature_even_unused(self):
        for signature in ('Text, FrozenBytes, BytesChannel', 'Integer, Bytes, BytesChannel',
                          'Integer, FrozenBytes, Integer', 'Integer, FrozenBytes',
                          'Integer, FrozenBytes, BytesChannel, Integer'):
            params = ', '.join(f'p{i}: {t}' for i, t in enumerate(signature.split(', ')))
            with self.subTest(signature=signature):
                self.compile(f'thread function unused({params}): Integer {{ return 0 }}\n' + ENTRY + MAIN,
                             success=False, diagnostic='thread entry')
        for result in ('Text', 'Bytes', 'FrozenBytes', 'Thread', 'Boolean'):
            with self.subTest(result=result):
                self.compile(ENTRY.replace(': Integer {', ': ' + result + ' {') + MAIN,
                             success=False, diagnostic='thread entry')

    def test_named_entry_only(self):
        for target in ('7', '(worker)', 'worker + 1', 'function() { return 0 }'):
            with self.subTest(target=target):
                self.compile(ENTRY + MAIN.replace('startThread(worker,', f'startThread({target},'),
                             success=False, diagnostic='startThread')
        self.compile(ENTRY.replace('thread function', 'function') + MAIN,
                     success=False, diagnostic='thread entry')
        self.compile(ENTRY.replace('worker(', 'main('), success=False, diagnostic='thread entry')

    def test_opaque_nominal_send_boundary(self):
        for type_name in ('FrozenBytes', 'BytesChannel', 'Thread', 'ThreadStartResult', 'ThreadJoinResult', 'FrozenBytesChannel', 'FrozenBytesResult'):
            for expression in (type_name + '(1)', type_name + ' { raw: 1 }'):
                with self.subTest(expression=expression):
                    self.compile(ENTRY + MAIN.replace('let bytes = Bytes(8)', 'let forged = ' + expression + '\nlet bytes = Bytes(8)'), success=False)
            self.compile(f'record {type_name} {{ raw: Integer }}\n' + ENTRY + MAIN, success=False, diagnostic='reserved')
        for value in ('Bytes(8)', '"local"', '[1]', '7', 'channel'):
            with self.subTest(value=value):
                self.compile(ENTRY + MAIN.replace('worker, 7, frozen, channel', 'worker, 7, ' + value + ', channel'), success=False)
        self.compile(ENTRY + MAIN.replace('print(joinThread(workerHandle))', 'print(Integer(frozen))'), success=False)
        self.compile(ENTRY + MAIN.replace('print(joinThread(workerHandle))', 'frozen[0] = 7'), success=False)

    def test_native_signature_cannot_export_handles(self):
        self.compile('function escape(value: FrozenBytes): Integer { native "test" }\n' + ENTRY + MAIN, success=False, diagnostic='native')
        
        
        for name, library in (('take', 'frozen_bytes'), ('start_result_value', 'thread'),
                              ('process_id', 'thread'), ('try_receive', 'frozen_channel')):
            self.compile(f'function {name}(value: Bytes): Bytes {{ native "{library}" }}\n' + ENTRY + MAIN,
                         success=False, diagnostic='native symbol conflicts')

    def test_complete_resolved_effect_graph(self):
        unsafe = 'public function unsafe(value: Bytes): Integer { native "test" }\n'
        for body in ('let ignored = evil.unsafe(Bytes(1))\nreturn seed',
                     'return middle(seed)'):
            modules = {'evil.min': unsafe}
            helper = 'function middle(n: Integer): Integer { return bottom(n) }\nfunction bottom(n: Integer): Integer { return evil.unsafe(Bytes(n)) }\n'
            self.compile('use "./evil.min" as evil\n' + helper + ENTRY.replace('return seed + input.length', body) + MAIN,
                         modules, success=False, diagnostic='unsafe thread effect')
        self.compile('use "machine" as machine\n' + ENTRY + MAIN.replace('let frozen = freezeBytes(bytes)',
                     'let saved = [machine.address(bytes)]\nlet frozen = freezeBytesTake(bytes)'), success=False, diagnostic='unsafe thread effect')

    def test_main_callbacks_and_worker_effect_boundaries(self):
        callback = 'let callback = function(value: Integer): Integer { return value }\nprint(callback(1))'
        self.compile(ENTRY + MAIN.replace('print(joinThread(workerHandle))', callback))
        self.compile(ENTRY.replace('return seed + input.length', callback + '\nreturn seed') + MAIN,
                     success=False, diagnostic='unsafe thread effect')
        hidden = 'use "machine" as machine\nfunction unsafe(): Integer { return machine.address(Bytes(1)) }\n'
        self.compile(hidden + ENTRY + MAIN.replace('print(joinThread(workerHandle))',
                     'let callback = function(): Integer { return unsafe() }\nprint(callback())'),
                     success=False, diagnostic='unsafe thread effect')
        result = '''function unsafe(): Result<Integer, Text> {
    let saved = machine.address(Bytes(1))
    return Ok<Integer, Text>(saved)
}
'''
        self.compile('use "machine" as machine\n' + result + ENTRY + MAIN.replace('print(joinThread(workerHandle))', 'let value = unsafe()'), success=False, diagnostic='unsafe thread effect')

    def test_public_qualified_entry(self):
        ir = self.compile('use "./entry.min" as entry\n' + MAIN.replace('startThread(worker,', 'startThread(entry.worker,'),
                          {'entry.min': ENTRY.replace('thread function', 'public thread function')})
        self.assertIn('; minyar-thread-entry:', ir)
        self.assertIn('@minyar_thread_spawn(ptr @.minyar.thread.bridge.', ir)

    def test_literals_constants_and_nothing_bridge(self):
        ir = self.compile('constant label = "λ🙂"\n' + ENTRY.replace(': Integer {', ' {').replace('return seed + input.length', 'print(label)') + MAIN)
        self.assertIn('@minyar_thread_text_literal(ptr getelementptr', ir)
        self.assertIn('ret i64 0', ir)
        self.assertIn('; minyar-thread-runtime: 1', ir)
        self.assertIn('call void @minyar_thread_join_children()', ir)
        self.assertIn('; minyar-thread-effect:', ir)
        bridge = ir.split('define internal i64 @.minyar.thread.bridge.', 1)[1]
        self.assertLess(bridge.index('@minyar_stack_enter'), bridge.index('@.minyar.fn.'))
        self.assertLess(bridge.index('@minyar_stack_leave'), bridge.index('ret i64 0'))

    def test_maintained_language_fixtures_compile(self):
        for path in sorted((ROOT / 'tests/thread-fixtures').glob('*.min')):
            with self.subTest(path=path.name):
                ir = self.compile(path.read_text())
                self.assertIn('; minyar-thread-runtime: 1', ir)
                self.assertIn('@minyar_thread_spawn', ir)

    def test_shared_readers_channels_and_local_graphs(self):
        ir = self.compile('record Node { text: Text, edges: List<Node> }\n' + ENTRY.replace('return seed + input.length', '''
let node = Node { text: "λ🙂", edges: [] }
node.edges.add(node)
let local = copyFrozenBytes(input)
let aliases: List<Bytes> = [local]
let frozen = freezeBytesTake(local)
let copied = copyFrozenBytes(frozen)
copied.add(3)
let sent = trySendBytes(channel, copied)
let received = tryReceiveBytes(channel, local)
let blocking = sendBytes(channel, copied)
let next = receiveBytes(channel, local)
closeBytesChannel(channel)
return frozen[0] + input.getUInt8(0) + input.getInt64(0) + aliases[0].length
''') + MAIN)
        for symbol in ('minyar_frozen_bytes_get_uint8', 'minyar_frozen_bytes_get_int64',
                       'minyar_bytes_channel_send', 'minyar_bytes_channel_receive'):
            self.assertIn('call ', ir)
            self.assertIn('@' + symbol + '(', ir)
        self.assertIn('; minyar-cycle-runtime: 1', ir)

    def test_recursion_and_ordinary_parallel_abi(self):
        source = 'function count(n: Integer): Integer { if n == 0 { return 0 }\nreturn count(n - 1) + 1 }\n'
        self.compile(source + ENTRY.replace('return seed + input.length', 'return count(seed)') + MAIN)
        self.compile('parallel function scalar(n: Integer): Integer { return n + 1 }\n' + ENTRY + MAIN)
        scalar = 'parallel function scalar(n: Integer): Integer { return n + 1 }\n'
        ir = self.compile(scalar + 'print(parallelEntry(scalar))\n')
        self.assertIn('ptrtoint ptr @.minyar.fn.scalar to i64', ir)
        self.compile(scalar + ENTRY + MAIN.replace('print(joinThread(workerHandle))', 'let raw = [parallelEntry(scalar)]'),
                     success=False, diagnostic='unsafe thread effect')

    def test_recheck_changed_same_signature_helper(self):
        source = 'use "./helper.min" as helper\n' + ENTRY.replace('return seed + input.length', 'return helper.value(seed)') + MAIN
        safe = 'public function value(n: Integer): Integer { return n }\n'
        self.compile(source, {'helper.min': safe})
        unsafe = 'public function value(n: Integer): Integer { native "test" }\n'
        self.compile(source, {'helper.min': unsafe}, success=False, diagnostic='unsafe thread effect')
        self.compile(source, {'helper.min': unsafe}, success=False, diagnostic='unsafe thread effect')

    def test_recoverable_owned_projections_and_frozen_channels(self):
        source = ENTRY.replace('channel: BytesChannel', 'channel: FrozenBytesChannel').replace('return seed + input.length', '''
let own = freezeBytes(Bytes(seed))
let sent = sendFrozen(channel, own)
return seed
''') + MAIN.replace('bytesChannel(4096, 8)', 'frozenBytesChannel(4096, 8)').replace(
            'let workerHandle = startThread(worker, 7, frozen, channel)\n    print(joinThread(workerHandle))', '''
let started = startThreadResult(worker, 7, frozen, channel)
if started.ok {
    let workerHandle = started.thread
    let joined = joinThreadResult(workerHandle)
    if joined.ok { print(joined.value) }
    print(joined.code)
}
let received = receiveFrozen(channel)
if received.ok {
    let retained = received.value
    print(retained.length)
}
let attempt = tryReceiveFrozen(channel)
print(attempt.code)
let sent = trySendFrozen(channel, frozen)
closeFrozenChannel(channel)
''')
        ir = self.compile(source)
        for symbol in ('minyar_thread_spawn_result', 'minyar_thread_join_result',
                       'minyar_thread_start_result_value', 'minyar_thread_join_result_value',
                       'minyar_thread_result_code', 'minyar_frozen_result_value',
                       'minyar_frozen_result_code', 'minyar_frozen_channel_send'):
            self.assertIn('@' + symbol + '(', ir)
        self.compile(source.replace('started.thread', 'started.value'), success=False)
        self.compile(source.replace('print(attempt.code)', 'attempt.code = 0'), success=False)
        self.compile(source.replace('worker, 7, frozen, channel', 'worker, 7, frozen, bytesChannel(8, 8)'), success=False)
        self.compile(ENTRY + MAIN.replace('worker, 7, frozen, channel', 'worker, 7, frozen, frozenBytesChannel(8, 8)'), success=False)

    def test_pointer_free_kernel_builtins(self):
        ir = self.compile(ENTRY + MAIN.replace('print(joinThread(workerHandle))', '''
print(threadProcessId())
print(threadSleepNanoseconds(1))
print(threadFsync(1))
print(threadKernelRun(1))
'''))
        for symbol in ('minyar_thread_process_id', 'minyar_thread_sleep_ns',
                       'minyar_thread_fsync', 'minyar_thread_kernel_run'):
            self.assertIn('@' + symbol + '(', ir)
        for expression in ('threadProcessId(1)', 'threadSleepNanoseconds(frozen)',
                           'threadFsync(bytes)', 'threadKernelRun(channel)'):
            self.compile(ENTRY + MAIN.replace('print(joinThread(workerHandle))', expression), success=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', type=Path, default=Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc-threads')))
    args, remaining = parser.parse_known_args()
    COMPILER = args.compiler.resolve()
    unittest.main(argv=[__file__, *remaining])
