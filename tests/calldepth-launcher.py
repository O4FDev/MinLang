#!/usr/bin/env python3
"""Exercise parsed recovery selection and full-graph incremental fallback."""
import os
from pathlib import Path
import shutil
import unittest

from clang_helpers import windows_host
from regressions import CLANG, CompilerTestCase, ROOT

PROBE = ROOT / 'build/minyarc-errors-request'


class CallDepthLauncher(CompilerTestCase):
    def request(self, source, status):
        llvm = self.directory / 'request.ll'
        result = self.evidence.run([str(PROBE), str(source), str(llvm), '--library', str(ROOT / 'library')],
                                  timeout=30, phase='recovery-request')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (status, b'', b''))
        self.assertFalse(llvm.exists())

    def launch(self, source, expected, options=()):
        environment = os.environ.copy()
        for name in ('MINYAR_CLANG', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_CLANG_FLAGS', 'MFLAGS'):
            environment.pop(name, None)
        environment.update(LLVM_CC=CLANG, CC=CLANG, MAKEFLAGS='-j1',
                           MINYAR_CLANG_FLAGS='-O0 -Wno-override-module')
        executable = self.directory / ('recovery.exe' if windows_host() else 'recovery')
        shell = shutil.which('sh')
        self.assertTrue(shell)
        compiled = self.evidence.run([shell, '-x', str(ROOT / 'minyar'), '--debug', *options,
                                     str(source), '-o', str(executable)], cwd=ROOT, env=environment,
                                    timeout=180, phase='recovery-public-launcher')
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        self.assertIn(b'build/minyarc-calldepth', compiled.stderr)
        if options:
            selected = compiled.stderr.split(b'+ selected_status=0\n', 1)
            self.assertEqual(len(selected), 2, compiled.stderr)
            self.assertNotIn(b'build/minyar-module-build ', selected[1],
                             'recovery must compile the flattened graph without module reuse')
        executed = self.evidence.run([str(executable)], timeout=30, phase='recovery-execute')
        self.assertEqual((executed.returncode, executed.stdout, executed.stderr), (0, expected, b''))

    def test_million_failure_then_thousand_success(self):
        source = ROOT / 'tests/calldepth/g14-recovered.min'
        self.request(source, 88)
        self.launch(source, b'false\ntrue\n1000\nalive\n')

    @unittest.skipIf(windows_host(), 'the incremental driver requires macOS/Linux')
    def test_results_before_recovery_and_repeated_incremental_request(self):
        imported = self.directory / 'result.min'
        imported.write_text('public function value(): Result<Integer, Text> { return Ok<Integer, Text>(42) }\n')
        source = self.directory / 'root.min'
        source.write_text('use "./result.min" as result\nuse "calldepth" as depth\nuse "errors" as errors\n'
                          'let answer = depth.run(2, function(): Integer {\n'
                          '    match result.value() { Ok(number) { return number } Err(error) { return 0 } }\n'
                          '})\nprint(errors.integerValue(answer))\n')
        self.request(source, 88)
        for _ in range(2): self.launch(source, b'42\n', ('--incremental',))

    def test_text_and_comments_do_not_request_recovery(self):
        source = self.directory / 'ordinary.min'
        source.write_text('// native "calldepth"\n' + r'''print("native \"calldepth\"")''' + '\n')
        self.request(source, 0)


if __name__ == '__main__': unittest.main()
