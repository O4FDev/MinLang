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
from clang_helpers import windows_host


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
    def launcher(self, source, options, *, execute=True):
        self.serial += 1
        path = self.directory / f'program-{self.serial}.min'
        output = self.directory / (f'program-{self.serial}' + ('.exe' if windows_host() else ''))
        path.write_text(source)
        environment = os.environ.copy()
        # Use the tested LLVM without forcing the configurable-runtime path.
        for name in ('MINYAR_CLANG', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_CLANG_FLAGS'):
            environment.pop(name, None)
        environment.update(LLVM_CC=CLANG, CC=CLANG)
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
            result = self.evidence.run([str(output)], text=True, timeout=10, phase='launcher-execute')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '42\nkept\n42\n')
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


if __name__ == '__main__':
    unittest.main()
