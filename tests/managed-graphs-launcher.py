#!/usr/bin/env python3
"""Exercise parsed extension dispatch through the real portable launcher.

These short correctness cases check policy selection and module fallback;
they do not measure performance. The independent ownership oracles live in
managed-graphs.py, callbacks.py and managed-graphs-profiles.py.
"""
import os
import shutil
import unittest
from regressions import CompilerTestCase, ROOT, CLANG
from clang_helpers import asan_leak_options, windows_host


SOURCE = '''use "eventcallbacks" as callbacks
use "eventloop" as eventloop
use "errors" as errors
record Node { value: Integer; callbacks: List<Callback<Integer, Integer>> }
function make(): Callback<List<Text>> {
    return function(): List<Text> { return ["kept"] }
}
let node = Node { value: 40; callbacks: [] }
let callback = function(delta: Integer): Integer { return node.value + delta }
node.callbacks.add(callback)
print(callback(2))
let factory = make()
let words = factory()
print(words[0])
let dispatcher = callbacks.value(callbacks.create())
let calls = callbacks.timer(dispatcher, 0, 0, 2, function(event: eventloop.Event) {
    print(callback(event.token))
})
if !errors.integerOk(calls) { fail("timer failed") }
if errors.integerValue(callbacks.dispatch(dispatcher, 0, 8)) != 1 { fail("missing callback") }
if !errors.booleanOk(callbacks.close(dispatcher)) { fail("close failed") }
'''


class ManagedGraphLauncher(CompilerTestCase):
    def launcher(self, source, options, *, execute=True, expected='42\nkept\n42\n', sanitize=False):
        self.serial += 1
        path = self.directory / f'program-{self.serial}.min'
        output = self.directory / (f'program-{self.serial}' + ('.exe' if windows_host() else ''))
        path.write_text(source)
        environment = os.environ.copy()
        # Use the tested LLVM without forcing the configurable-runtime path.
        for name in ('MINYAR_CLANG', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_CLANG_FLAGS'):
            environment.pop(name, None)
        environment.update(LLVM_CC=CLANG, CC=CLANG)
        if sanitize:
            flags = '-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
            environment.update(MINYAR_RUNTIME_FLAGS=flags, MINYAR_CLANG_FLAGS=flags,
                               ASAN_OPTIONS=asan_leak_options() + ':halt_on_error=1',
                               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        command = [str(ROOT / 'minyar'), *options, str(path)]
        if os.name == 'nt':
            shell = shutil.which('sh')
            self.assertTrue(shell, 'the portable Windows launcher requires MSYS2 sh')
            command = [shell, (ROOT / 'minyar').as_posix(), *options, path.as_posix()]
        if execute: command += ['-o', output.as_posix()]
        built = self.evidence.run(command,
            env=environment, cwd=ROOT, text=True, timeout=60, phase='launcher-build')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        if execute:
            self.assertTrue(output.is_file())
            result = self.evidence.run([str(output)], env=environment, text=True, timeout=10,
                                       phase='launcher-execute')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, expected)
            self.assertFalse(result.stderr)
        else:
            self.assertFalse(output.exists())
            self.assertIn('checked ', built.stdout)

    def check_profiles(self, profiles):
        for profile in profiles:
            for optimization in ('--debug', '--release'):
                with self.subTest(profile=profile, optimization=optimization):
                    self.launcher(SOURCE, (*profile, optimization))

    def test_debug_and_release_preserve_selected_heap_and_owner_abi(self):
        self.check_profiles((
            ('--memory-profile', 'system'),
            ('--memory-profile', 'system', '--cleanup-budget', '1'),
            ('--memory-profile', 'fixed', '--heap-bytes', '1048576'),
            ('--memory-profile', 'eager'),
        ))

    @unittest.skipIf(windows_host(), 'existing lazy heap uses POSIX mmap')
    def test_debug_and_release_preserve_lazy_heap_policy(self):
        self.check_profiles((('--memory-profile', 'lazy', '--cleanup-budget', '1', '--heap-bytes', '1048576'),))

    @unittest.skipIf(windows_host(), 'incremental launcher requires macOS/Linux')
    def test_incremental_driver_preserves_parsed_fallback_and_check_mode(self):
        self.launcher(SOURCE, ('--incremental', '--debug'))
        self.launcher(SOURCE, ('--incremental', '--check'), execute=False)

    def test_preserved_bakeoff_workload_on_selected_heap_profiles(self):
        source = (ROOT / 'tests/managed-graphs/sol-graphs.min').read_text()
        expected = '15\n22\n33\n' + ''.join(f'{i}\n' for i in range(0, 20000, 1000))
        profiles = [
            ('--memory-profile', 'system', '--cleanup-budget', '1'),
            ('--memory-profile', 'system', '--cleanup-budget', '32'),
            ('--memory-profile', 'fixed', '--heap-bytes', '1048576', '--cleanup-budget', '1'),
            ('--memory-profile', 'fixed', '--heap-bytes', '1048576', '--cleanup-budget', '32'),
            ('--memory-profile', 'eager'),
        ]
        if not windows_host():
            profiles.extend((
                ('--memory-profile', 'lazy', '--heap-bytes', '1048576', '--cleanup-budget', '1'),
                ('--memory-profile', 'lazy', '--heap-bytes', '1048576', '--cleanup-budget', '32'),
            ))
        for profile in profiles:
            for optimization in ('--debug', '--release'):
                # Retain Sol's bounded sanitizer coverage on platforms whose
                # established launcher supports this instrumentation route.
                for sanitize in ((False, True) if profile[1] != 'eager' and not windows_host() else (False,)):
                    with self.subTest(profile=profile, optimization=optimization, sanitize=sanitize):
                        self.launcher(source, (*profile, optimization), expected=expected, sanitize=sanitize)


if __name__ == '__main__':
    unittest.main()
