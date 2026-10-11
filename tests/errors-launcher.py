#!/usr/bin/env python3
"""Real parsed Result dispatch through the public launcher and request frontend."""
import os
from pathlib import Path
import shutil
import unittest

from clang_helpers import windows_host
from regressions import CLANG, COMPILER, CompilerTestCase, ROOT

PROBE = Path(os.environ.get('MINYAR_ERRORS_REQUEST_COMPILER', ROOT / 'build/minyarc-errors-request'))
SIMPLE = '''let r = Ok<Integer, Text>(0)
match r { Ok(v) { print(v) } Err(e) { print(e) } }
'''
NESTED = '''record Holder { items: List<Result<Callback<Result<Integer, Text>>, Text>> }
let h = Holder { items: [] }
let call = function(): Result<Integer, Text> { return Ok<Integer, Text>(7) }
h.items.add(Ok<Callback<Result<Integer, Text>>, Text>(call))
match h.items[0] {
    Ok(f) { match f() { Ok(v) { print(v) } Err(e) { print(e) } } }
    Err(e) { print(e) }
}
'''
CALLBACK_FIRST = '''let f = function(n: Integer): Integer { return n + 1 }
let r = Err<Integer, Text>("bad")
match r { Ok(v) { print(f(v)) } Err(e) { print(e) } }
'''
RECORD_NAME = '''record Result { n: Integer }
let f = function(x: Result): Integer { return x.n }
let r = Ok<Integer, Text>(1)
match r { Ok(v) { print(v) } Err(e) { print(e) } }
'''
PACKET = '''public record Failure { message: Text }
public function make(): Callback<Result<List<Result<Integer, Failure>>, Failure>> {
    return function(): Result<List<Result<Integer, Failure>>, Failure> {
        return Ok<List<Result<Integer, Failure>>, Failure>([Ok<Integer, Failure>(9)])
    }
}
'''
IMPORTED = '''use "./packet.min" as packet
function invoke(): Result<Integer, packet.Failure> {
    let f = packet.make()
    let values = try f()
    let n = try values[0]
    return Ok<Integer, packet.Failure>(n)
}
match invoke() { Ok(v) { print(v) } Err(e) { print(e.message) } }
'''


class ErrorsLauncher(CompilerTestCase):
    def source(self, text):
        self.serial += 1
        path = self.directory / f'program-{self.serial}.min'
        path.write_text(text)
        return path

    def request(self, path, status, flags=()):
        output = path.with_suffix('.probe.ll')
        if output.exists():
            output.unlink()
        result = self.evidence.run([str(PROBE), str(path), str(output), *flags,
                                   '--library', str(ROOT / 'library')],
                                  text=True, timeout=30, phase='request-result')
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertFalse(result.stdout)
        self.assertFalse(output.exists(), 'request probe must never publish LLVM')
        if status in (0, 87):
            self.assertFalse(result.stderr)
        return result

    def launcher(self, path, *, options=(), status=0, trace=False, raw=False):
        output = path.with_suffix('.exe' if windows_host() else '.program')
        environment = os.environ.copy()
        for name in ('MINYAR_CLANG', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_CLANG_FLAGS'):
            environment.pop(name, None)
        environment.pop("MFLAGS", None)
        environment.update(LLVM_CC=CLANG, CC=CLANG, MAKEFLAGS="-j1")
        shell = shutil.which('sh')
        self.assertTrue(shell)
        arguments = [shell, *(['-x'] if trace else []), str(ROOT / 'minyar'),
                     *([] if '--check' in options else ['--debug']), *options, str(path)]
        if '--check' not in options:
            arguments += ['-o', str(output)]
        result = self.evidence.run(arguments, cwd=ROOT, env=environment, text=not raw,
                                  timeout=120, phase='public-result-launcher')
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        self.assertNotEqual(result.returncode, 87, 'internal request escaped public launcher')
        if status != 0:
            self.assertFalse(output.exists())
        return result, output

    def executes_launcher(self, text, expected, options=()):
        path = self.source(text)
        probe_flags = []
        for index, option in enumerate(options):
            if option == '--library':
                probe_flags.extend((option, options[index + 1]))
        self.request(path, 87, probe_flags)
        result, executable = self.launcher(path, options=options)
        self.assertEqual(result.stdout, f"built {executable}\n")
        self.assertFalse(result.stderr, 'selected frontend leaked primary diagnostics')
        run = self.evidence.run([str(executable)], timeout=30, phase='execute-result-launcher')
        self.assertEqual((run.returncode, run.stdout, run.stderr), (0, expected.encode(), b''))

    def test_constructor_nested_callback_and_ordinary_record_names(self):
        for source, expected in ((SIMPLE, '0\n'), (NESTED, '7\n'),
                                 (CALLBACK_FIRST, 'bad\n'), (RECORD_NAME, '1\n')):
            with self.subTest(source=source):
                self.executes_launcher(source, expected)

    def test_imported_public_payloads_and_library_order(self):
        (self.directory / 'packet.min').write_text(PACKET)
        self.executes_launcher(IMPORTED, '9\n')
        self.executes_launcher(IMPORTED.replace('./packet.min', 'packet'), '9\n',
                               ('--library', str(self.directory)))
        root = self.source('use "./packet.min" as packet\nprint("alive")\n')
        self.request(root, 87)

    @unittest.skipIf(windows_host(), 'existing incremental driver requires macOS/Linux')
    def test_incremental_imported_dispatch_is_repeatable(self):
        (self.directory / 'packet.min').write_text(PACKET)
        for _ in range(2):
            self.executes_launcher(IMPORTED, '9\n', ('--incremental',))
        bad = self.source(IMPORTED.replace('print(v)', 'print(missing)'))
        self.request(bad, 87)
        result, _ = self.launcher(bad, options=('--incremental', '--check'), status=1)
        self.assertIn(str(bad), result.stderr)
        self.assertIn("find a value named 'missing'", result.stderr)

    def test_complete_header_and_parser_diagnostics_remain_distinct(self):
        for source in ('let r: Result<Integer> = 1\n',
                       'let r = Ok<Integer, Text>\n',
                       'let r: List<Result<Integer, Text> = []\n'):
            with self.subTest(source=source):
                path = self.source(source)
                self.request(path, 1)
                primary = self.evidence.run([str(COMPILER), str(path), str(path.with_suffix('.core.ll')),
                                            '--library', str(ROOT / 'library')],
                                           timeout=30, phase='primary-errors-control')
                public, _ = self.launcher(path, options=('--check',), status=1, raw=True)
                self.assertEqual(public.stderr, primary.stderr)
        for source, diagnostic in (
                ('let r = Ok<Integer, Text>(\n', None),
                ('let r = Ok<Integer, Text>("wrong")\n', 'result payload has the wrong type'),
                ('let r = Ok<Integer, Text>(1)\nmatch r { Ok(v) {} }\n', 'match must handle both Ok and Err')):
            with self.subTest(source=source):
                path = self.source(source)
                self.request(path, 87)
                result, _ = self.launcher(path, options=('--check',), status=1)
                if diagnostic:
                    self.assertIn(diagnostic, result.stderr)
                self.assertNotIn("unknown type 'Result'", result.stderr)

    def test_nonrequest_diagnostics_and_successful_ordinary_path(self):
        for source in ('let x: Missing = 1\n', 'let x = 1 + true\n'):
            with self.subTest(source=source):
                path = self.source(source)
                self.request(path, 1)
                primary = self.evidence.run([str(COMPILER), str(path), str(path.with_suffix('.core.ll')),
                                            '--library', str(ROOT / 'library')],
                                           timeout=30, phase='primary-ordinary-control')
                public, _ = self.launcher(path, options=('--check',), status=1, raw=True)
                self.assertEqual(public.stderr, primary.stderr)
        path = self.source('''print("Result<Integer, Text> Ok<Integer, Text>( match try >>")
// Result<Integer, Text>
let Result = 2
let Ok = 3
let Err = 4
print(Result < Ok)
print(Err >> 1)
''')
        primary = self.evidence.run([str(COMPILER), str(path), str(path.with_suffix('.core.ll'))],
                                   timeout=30, phase='primary-ordinary-success')
        self.assertEqual(primary.returncode, 0, primary.stderr)
        self.request(path, 0)
        public, _ = self.launcher(path, options=('--check',), trace=True)
        self.assertNotIn('build/minyarc-errors', public.stderr)
        self.assertNotIn('errors-request', public.stderr)

    def test_callable_request_without_result_keeps_callback_frontend(self):
        path = self.source('let f = function(n: Integer): Integer { return n + 1 }\nprint(f(2))\n')
        primary = self.evidence.run([str(COMPILER), str(path), str(path.with_suffix('.core.ll'))],
                                   timeout=30, phase='primary-callable-control')
        self.assertEqual(primary.returncode, 86, primary.stderr)
        self.request(path, 0)
        public, _ = self.launcher(path, options=('--check',), trace=True)
        self.assertIn('build/minyarc-callbacks', public.stderr)
        self.assertNotRegex(public.stderr, r'build/minyarc-errors(?:\s|$)')

    def test_request_forwards_budgets_freestanding_and_bounded_runtime(self):
        path = self.source(SIMPLE)
        for budget in (1, 32, 1024):
            with self.subTest(budget=budget):
                self.request(path, 87, ('--bounded-owners', str(budget), '--freestanding'))
                self.executes_launcher(SIMPLE, '0\n',
                    ('--memory-profile', 'fixed', '--heap-bytes', '1048576',
                     '--cleanup-budget', str(budget)))


if __name__ == '__main__':
    unittest.main()
