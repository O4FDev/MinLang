#!/usr/bin/env python3
"""Short copied-message isolation and worker failure tests, without load runs."""
import unittest
import struct
import os
import json
from regressions import CompilerTestCase, ROOT, CLANG, LINK_FLAGS
from clang_helpers import clang_command, native_path, windows_host
from pathlib import Path

WORKER_RUNTIME = Path(os.environ.get('MINYAR_WORKER_RUNTIME', ROOT / 'build/minyar-default-runtime.o'))


class IsolatedWorkers(CompilerTestCase):
    compiler_arguments = ('--library', str(ROOT / 'library'))

    @unittest.skipUnless(windows_host(), 'native Windows process and handle contract')
    def test_native_windows_handle_allowlist_and_job_lifecycle(self):
        executable = self.directory / 'windows-workers-native.exe'
        linked = self.evidence.run(clang_command([CLANG, '-std=c11', '-O2', *LINK_FLAGS,
            '-Wall', '-Wextra', '-Werror', '-municode',
            str(ROOT / 'tests/windows-workers-native.c'), str(WORKER_RUNTIME),
            '-ladvapi32', '-o', str(executable)]), capture_output=True, text=True,
            timeout=30, phase='link-windows-worker-lifecycle')
        self.assertEqual(linked.returncode, 0, linked.stderr)
        run = self.evidence.run([str(executable)], capture_output=True, timeout=30,
                               phase='execute-windows-worker-lifecycle')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, b'Windows worker handle isolation and process lifecycle verified\n')
        self.assertEqual(run.stderr, b'')

    def worker_program(self, source, expected):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        executable = llvm.with_suffix('.exe')
        linked = self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS,
            '-Wno-override-module', str(llvm), str(WORKER_RUNTIME),
            str(ROOT / 'runtime/native/workers.c'), '-o', str(executable)]),
            capture_output=True, text=True, timeout=30, phase='link-isolated-worker')
        self.assertEqual(linked.returncode, 0, linked.stderr)
        run = self.evidence.run([str(executable)], capture_output=True,
                                timeout=10, phase='execute-isolated-worker')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, expected.encode())
        self.assertEqual(run.stderr, b'')

    def test_messages_copy_and_domains_run_independently(self):
        self.worker_program('''use "workers" as workers
use "errors" as errors
if workers.isWorker() {
    let input = workers.readMessage()
    if !errors.bytesOk(input) { fail("worker read failed") }
    let message = errors.bytesValue(input)
    message[0] = message[0] + 1
    if !errors.integerOk(workers.reply(message)) { fail("worker reply failed") }
} else {
    let first = workers.value(workers.spawnSelf("echo"))
    let second = workers.value(workers.spawnSelf("echo"))
    let input = Bytes(3)
    input[0] = 40
    input[1] = 0
    input[2] = 255
    if !errors.integerOk(workers.send(first, input)) { fail("send failed") }
    if !errors.integerOk(workers.send(second, input)) { fail("send failed") }
    input[0] = 7
    let a = workers.receive(first, 2000)
    let b = workers.receive(second, 2000)
    print(errors.bytesValue(a)[0])
    print(errors.bytesValue(b)[0])
    print(input[0])
    print(errors.bytesValue(a)[1])
    print(errors.bytesValue(a)[2])
    print(errors.booleanValue(workers.close(first)))
    print(errors.booleanValue(workers.close(second)))
    print(errors.integerOk(workers.send(first, input)))
}
''', '41\n41\n7\n0\n255\ntrue\ntrue\nfalse\n')

    def test_empty_messages_are_success_and_child_exit_is_eof(self):
        self.worker_program('''use "workers" as workers
use "errors" as errors
if workers.isWorker() {
    let input = workers.readMessage()
    if errors.bytesStatus(input) != errors.successStatus() { fail("empty frame was not success") }
    workers.reply(errors.bytesValue(input))
} else {
    let worker = workers.value(workers.spawnSelf("empty"))
    workers.send(worker, Bytes())
    let empty = workers.receive(worker, 2000)
    print(errors.bytesStatus(empty))
    print(errors.bytesValue(empty).length)
    print(errors.bytesStatus(workers.receive(worker, 2000)))
    workers.close(worker)
    print(workers.ok(workers.spawn("/path/that/does/not/exist", "bad")))
}
''', '0\n0\n2\nfalse\n')

    def test_malformed_worker_output_is_a_recoverable_failure(self):
        self.worker_program('''use "workers" as workers
use "errors" as errors
if workers.isWorker() {
    print("not a framed message")
} else {
    let worker = workers.value(workers.spawnSelf("malformed"))
    let result = workers.receive(worker, 2000)
    print(errors.bytesStatus(result))
    print(errors.isError(errors.bytesError(result)))
    print(errors.booleanValue(workers.close(worker)))
}
''', '3\ntrue\ntrue\n')

    def test_poll_result_remains_independent_and_stale_identity_is_rejected(self):
        self.worker_program('''use "workers" as workers
use "errors" as errors
if workers.isWorker() {
    let input = workers.readMessage()
    workers.reply(errors.bytesValue(input))
} else {
    let first = workers.value(workers.spawnSelf("poll"))
    let polled = workers.receive(first, 0)
    print(errors.bytesStatus(polled))
    print(errors.bytesStatus(workers.receive(first, -2)))
    workers.send(first, Bytes())
    print(errors.bytesStatus(workers.receive(first, 2000)))
    print(errors.bytesStatus(polled))
    workers.close(first)
    let next = workers.value(workers.spawnSelf("replacement"))
    print(errors.integerOk(workers.send(first, Bytes())))
    print(errors.booleanOk(workers.close(first)))
    workers.close(next)
}
''', '1\n3\n0\n1\nfalse\nfalse\n')

    def test_backpressure_accepts_no_partial_frame_and_close_releases_queue(self):
        # MinGW's driver can corrupt non-ASCII intermediate object filenames.
        # Compile an ASCII fixture, then test the actual Unicode executable path.
        waiting = self.directory / 'waiting-worker.c'
        waiting.write_text('#ifdef _WIN32\n#include <windows.h>\nint main(void) { Sleep(INFINITE); }\n'
                           '#else\n#include <unistd.h>\nint main(void) { for (;;) pause(); }\n#endif\n')
        built = waiting.with_suffix('.exe')
        compiled = self.evidence.run([CLANG, '-std=c11', '-O2', str(waiting), '-o', str(built)],
            capture_output=True, text=True, timeout=30, phase='compile-idle-worker')
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        child = self.directory / 'waiting worker é.exe'
        built.rename(child)
        self.worker_program(f'''use "workers" as workers
use "errors" as errors
let worker = workers.value(workers.spawn({json.dumps(native_path(child), ensure_ascii=False)}, "blocked"))
let message = Bytes(16777216)
print(errors.integerOk(workers.send(worker, message)))
print(errors.integerOk(workers.send(worker, message)))
let blocked = workers.send(worker, message)
print(errors.integerOk(blocked))
print(errors.isWouldBlock(errors.integerError(blocked)))
print(errors.bytesStatus(workers.receive(worker, 0)))
print(errors.booleanValue(workers.close(worker)))
''', 'true\ntrue\nfalse\ntrue\n1\ntrue\n')

    def test_every_truncated_frame_prefix_and_oversized_header(self):
        source = '''use "workers" as workers
use "errors" as errors
let result = workers.readMessage()
let status = Bytes(1)
status[0] = errors.bytesStatus(result)
workers.reply(status)
'''
        compiled, llvm = self.compile(source)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executable = llvm.with_suffix('.exe')
        linked = self.evidence.run(clang_command([CLANG, '-O2', *LINK_FLAGS,
            '-Wno-override-module', str(llvm), str(WORKER_RUNTIME),
            str(ROOT / 'runtime/native/workers.c'), '-o', str(executable)]),
            capture_output=True, text=True, timeout=30, phase='link-worker-parser')
        self.assertEqual(linked.returncode, 0, linked.stderr)
        packet = struct.pack('<I', 3) + b'a\x00\xff'
        cases = [(packet[:length], 2 if length == 0 else 3) for length in range(len(packet))]
        cases += [(packet, 0), (struct.pack('<I', 0), 0), (struct.pack('<I', 16 * 1024 * 1024 + 1), 3), (b'\xff' * 4, 3)]
        for frame, status in cases:
            with self.subTest(frame=frame):
                run = self.evidence.run([str(executable), '--minyar-worker', 'parser'], input=frame,
                                        capture_output=True, timeout=3, phase='execute-worker-parser')
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(run.stdout, struct.pack('<I', 1) + bytes((status,)))

    def test_supported_backend_and_spawn_failure_are_values(self):
        self.worker_program('''use "workers" as workers
use "errors" as errors
print(workers.supported())
let result = workers.spawn("/path/that/does/not/exist", "unavailable")
print(workers.ok(result))
print(errors.isError(workers.error(result)))
''', 'true\nfalse\ntrue\n')

    def test_mode_arguments_preserve_empty_unicode_quotes_and_backslashes(self):
        for mode in ('', 'two words', 'é🙂 device', 'a"b', 'trailing\\', '\\"quoted\\"'):
            with self.subTest(mode=mode):
                literal = json.dumps(mode, ensure_ascii=False)
                self.worker_program(f'''use "workers" as workers
use "errors" as errors
if workers.isWorker() {{
    let response = Bytes(1)
    if workers.mode() == {literal} {{ response[0] = 1 }}
    workers.reply(response)
}} else {{
    let worker = workers.value(workers.spawnSelf({literal}))
    print(errors.bytesValue(workers.receive(worker, 2000))[0])
    workers.close(worker)
}}
''', '1\n')

    def test_pending_reads_survive_registry_growth_and_frames_remain_separate(self):
        self.worker_program('''use "workers" as workers
use "errors" as errors
if workers.isWorker() {
    let first = workers.readMessage()
    let second = workers.readMessage()
    workers.reply(errors.bytesValue(first))
    workers.reply(errors.bytesValue(second))
} else {
    let pool: List<workers.Worker> = []
    for index in 0..12 {
        let worker = workers.value(workers.spawnSelf("pending"))
        pool.add(worker)
        if errors.bytesStatus(workers.receive(worker, 0)) != errors.wouldBlockStatus() { fail("poll did not wait") }
    }
    for index in 0..12 {
        let message = Bytes(1)
        message[0] = index
        workers.send(pool[index], message)
        message[0] = index + 100
        workers.send(pool[index], message)
        message[0] = 255
    }
    for index in 0..12 {
        let first = workers.receive(pool[index], 2000)
        let second = workers.receive(pool[index], 2000)
        if errors.bytesValue(first)[0] != index || errors.bytesValue(second)[0] != index + 100 { fail("copied frame changed") }
        if errors.bytesStatus(workers.receive(pool[index], 2000)) != errors.endOfStreamStatus() { fail("other child inherited the pipe") }
        if !errors.booleanOk(workers.close(pool[index])) { fail("close failed") }
    }
    print("stable")
}
''', 'stable\n')


if __name__ == '__main__':
    unittest.main()
