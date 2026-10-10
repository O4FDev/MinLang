#!/usr/bin/env python3
"""Public launcher argv and native cache contracts, without a cold bootstrap."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ToolchainPortability(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='minyar toolchain ')
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.project = self.work / 'project with spaces'
        build = self.project / 'build'
        build.mkdir(parents=True)
        shutil.copy2(ROOT / 'minyar', self.project / 'minyar')
        shutil.copytree(ROOT / 'runtime', self.project / 'runtime')
        shutil.copytree(ROOT / 'tools', self.project / 'tools')
        (self.project / 'Makefile').write_text('.PHONY: build/minyarc\nbuild/minyarc:\n\t@:\n')
        self.write_executable(build / 'minyarc', '''import os, sys
from pathlib import Path
Path(sys.argv[2]).write_text('; minyar-native-library: graphics\\n' if os.environ.get('TEST_GRAPHICS') else '; test IR\\n')
''')
        self.bin = self.work / 'bin'
        self.bin.mkdir()
        self.log = self.work / 'clang calls.jsonl'
        self.clang = self.work / 'clang with spaces'
        self.write_executable(self.clang, '''import json, os, sys
from pathlib import Path
if '--version' in sys.argv:
    print(os.environ.get('TEST_CLANG_VERSION', 'clang version 23.1.2'))
    sys.exit(0)
with open(os.environ['TEST_CLANG_LOG'], 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
Path(sys.argv[sys.argv.index('-o') + 1]).write_text('; output\\n')
''')
        self.include = self.work / 'GLFW prefix with spaces' / 'include'
        self.include.mkdir(parents=True)
        self.write_executable(self.bin / 'pkg-config', '''import os, shlex, sys
if '--exists' in sys.argv: sys.exit(0)
if '--cflags' in sys.argv: print(shlex.quote('-I' + os.environ['TEST_GLFW_INCLUDE']))
if '--libs' in sys.argv: print('-lglfw')
''')
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        MINYAR_CLANG=str(self.clang), TEST_CLANG_LOG=str(self.log),
                        TEST_GLFW_INCLUDE=str(self.include), LIMITED='', SANITIZER_LIMITED='')
        for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS', 'MAKEFLAGS', 'MFLAGS'):
            self.env.pop(name, None)
        self.source = self.work / 'source file.min'
        self.source.write_text('print(42)\n')
        self.output = self.work / 'output program'

    def write_executable(self, path, code):
        path.write_text('#!' + sys.executable + '\n' + code)
        path.chmod(0o755)

    def launch(self, extra=None):
        self.log.write_text('')
        result = subprocess.run([str(self.project / 'minyar'), str(self.source), '-o', str(self.output)],
                                cwd=self.work, env=dict(self.env, **(extra or {})),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def native_calls(self, calls):
        return [args for args in calls if any(arg.endswith('/native/graphics.c') for arg in args)]

    def test_concurrent_cold_launches_share_a_complete_bootstrap(self):
        compiler = self.project / 'build/minyarc'
        template = self.work / 'compiler-template'
        shutil.copy2(compiler, template)
        compiler.unlink()
        self.write_executable(self.bin / 'make', '''import os, shutil, sys, time
from pathlib import Path
project = Path(sys.argv[sys.argv.index('-C') + 1])
busy = project / 'bootstrap-in-progress'
try:
    busy.mkdir()
except FileExistsError:
    sys.exit('overlapping cold bootstraps wrote shared artifacts')
try:
    time.sleep(0.15)
    shutil.copy2(os.environ['TEST_COMPILER_TEMPLATE'], project / 'build/minyarc')
    time.sleep(0.15)
finally:
    busy.rmdir()
''')
        jobs = []
        try:
            for identity in ('first', 'second'):
                output = self.work / (identity + ' output')
                jobs.append(subprocess.Popen([str(self.project / 'minyar'), str(self.source), '-o', str(output)],
                            cwd=self.work, env=dict(self.env, TEST_COMPILER_TEMPLATE=str(template)),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
            for job in jobs:
                stdout, stderr = job.communicate(timeout=30)
                self.assertEqual(job.returncode, 0, stdout + stderr)
        finally:
            for job in jobs:
                if job.poll() is None: job.kill()
                job.communicate()

    def test_selected_clang_bootstraps_both_c_and_llvm(self):
        self.env.pop('CC', None)
        self.write_executable(self.bin / 'make', '''import json, os
from pathlib import Path
Path(os.environ['TEST_MAKE_LOG']).write_text(json.dumps({name: os.environ.get(name) for name in ('CC', 'LLVM_CC')}))
''')
        log = self.work / 'make environment.json'
        self.launch({'TEST_MAKE_LOG': str(log)})
        chosen = json.loads(log.read_text())
        self.assertEqual(chosen, {'CC': str(self.clang), 'LLVM_CC': str(self.clang)})

    def bootstrap_environment(self, extra=None, system='Linux'):
        spec = importlib.util.spec_from_file_location('driver', ROOT / 'tools/clang-driver.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        environment = dict(self.env, **(extra or {}))
        if not extra or 'COMPILER_LTO_FLAGS' not in extra:
            environment.pop('COMPILER_LTO_FLAGS', None)
        if not extra or 'LLVM_FLAGS' not in extra:
            environment.pop('LLVM_FLAGS', None)
        with patch.dict(driver.os.environ, environment, clear=True), \
             patch.object(driver.platform, 'system', return_value=system), \
             patch.object(driver, 'run') as run:
            driver.bootstrap(self.project, ['build/minyarc-modules'])
        return run.call_args.kwargs['env']

    def test_linux_bootstrap_bounds_matching_lld_threads_with_literal_paths(self):
        linker = self.clang.parent / 'ld.lld'
        self.write_executable(linker, 'pass\n')
        environment = self.bootstrap_environment()
        self.assertEqual(shlex.split(environment['COMPILER_LTO_FLAGS']),
                         ['-flto', '-fuse-ld=' + str(linker.resolve()), '-Wl,--threads=1'])
        self.assertEqual(environment['LIMITED'], self.env['LIMITED'])

    def test_bootstrap_preserves_explicit_limits_lto_and_linker_threads(self):
        self.write_executable(self.clang.parent / 'ld.lld', 'pass\n')
        configured = '-flto=thin ' + shlex.quote('-fuse-ld=/linker path/ld.lld') + ' -Wl,--threads=3'
        environment = self.bootstrap_environment({'COMPILER_LTO_FLAGS': configured,
                        'MINYAR_MAX_MEMORY_MIB': '384', 'MINYAR_MAX_CPU_SECONDS': '90'})
        self.assertEqual(environment['COMPILER_LTO_FLAGS'], configured)
        self.assertEqual(environment['MINYAR_MAX_MEMORY_MIB'], '384')
        self.assertEqual(environment['MINYAR_MAX_CPU_SECONDS'], '90')
        environment = self.bootstrap_environment({'LLVM_FLAGS': '-O2 -fuse-ld=lld -Wl,--threads=2'})
        self.assertEqual(shlex.split(environment['COMPILER_LTO_FLAGS']), ['-flto'])
        self.assertEqual(environment['LLVM_FLAGS'], '-O2 -fuse-ld=lld -Wl,--threads=2')

    def test_elf_thread_option_stays_out_of_apple_and_windows_bootstrap(self):
        self.write_executable(self.clang.parent / 'ld.lld', 'pass\n')
        for system in ('Darwin', 'Windows'):
            environment = self.bootstrap_environment(system=system)
            self.assertNotIn('--threads', environment.get('COMPILER_LTO_FLAGS', ''))

    def test_incremental_windows_reports_supported_alternative(self):
        self.write_executable(self.bin / 'uname', "print('MINGW64_NT')\n")
        result = subprocess.run([str(self.project / 'minyar'), '--incremental', str(self.source)],
                                cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('omit --incremental', result.stderr)
        self.assertFalse(self.log.exists())

    def test_help_and_version_are_available_without_building(self):
        for option in ('--help', '--version'):
            result = subprocess.run([str(self.project / 'minyar'), option], env=self.env,
                                    cwd=self.work, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(self.log.exists(), 'informational options must not invoke Clang')
            if option == '--help':
                for word in ('--release', '--debug', '--incremental', '--doctor', 'MINYAR_CLANG'):
                    self.assertIn(word, result.stdout)
            else:
                self.assertIn('Minyar development', result.stdout)

    def test_missing_source_is_rejected_before_bootstrap(self):
        self.source.unlink()
        marker = self.work / 'make was called'
        self.write_executable(self.bin / 'make', 'from pathlib import Path\n'
                              f'Path({str(marker)!r}).touch()\n')
        result = subprocess.run([str(self.project / 'minyar'), str(self.source)],
                                cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('source file', result.stderr)
        self.assertFalse(marker.exists(), 'bad input paths must not start a cold bootstrap')
        self.assertFalse(self.log.exists())

    def test_output_cannot_replace_source_through_path_aliases(self):
        aliases = [self.source]
        for name, create in [('source symlink', lambda p: p.symlink_to(self.source)),
                             ('source hardlink', lambda p: os.link(self.source, p))]:
            alias = self.work / name
            try:
                create(alias)
            except OSError:
                continue  # Native Windows may disallow creating symlinks.
            # MSYS can emulate symlink creation by copying the file. A copy
            # is a valid separate output, so only exercise real file aliases.
            if alias.samefile(self.source):
                aliases.append(alias)
        original = self.source.read_bytes()
        for alias in aliases:
            with self.subTest(alias=alias):
                result = subprocess.run([str(self.project / 'minyar'), str(self.source), '-o', str(alias)],
                                        cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('replace the source file', result.stderr)
                self.assertEqual(self.source.read_bytes(), original)
                self.assertFalse(self.log.exists(), 'source/output collision must be rejected before Clang')

    def test_failed_link_preserves_previous_executable(self):
        previous = b'previous complete executable\n'
        self.output.write_bytes(previous)
        self.write_executable(self.clang, '''import sys
from pathlib import Path
if '--version' in sys.argv:
    print('clang version 23.1.2')
    sys.exit(0)
Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes(b'partial output')
sys.exit(0 if '-c' in sys.argv or '-emit-llvm' in sys.argv else 37)
''')
        result = subprocess.run([str(self.project / 'minyar'), str(self.source), '-o', str(self.output)],
                                cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(self.output.read_bytes(), previous)
        self.assertEqual(list(self.work.glob('.minyar-link-*')), [], 'failed link staging must be removed')

    def test_windows_implicit_exe_cannot_replace_source(self):
        source = self.work / 'input.exe'
        source.write_text('print(42)\n')
        destination = self.work / 'input'
        self.write_executable(self.clang, '''import sys
from pathlib import Path
if '--version' in sys.argv:
    print('clang version 23.1.2')
    sys.exit(0)
output = sys.argv[sys.argv.index('-o') + 1]
if '-c' not in sys.argv and '-emit-llvm' not in sys.argv:
    output += '.exe'
Path(output).write_bytes(b'compiled output')
''')
        result = subprocess.run([str(self.project / 'minyar'), str(source), '-o', str(destination)],
                                cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('replace the source file', result.stderr)
        self.assertEqual(source.read_text(), 'print(42)\n')
        self.assertEqual(list(self.work.glob('.minyar-link-*')), [])

    def test_successful_link_publishes_only_the_complete_executable(self):
        self.output.write_bytes(b'previous executable')
        ready, proceed = self.work / 'link ready', self.work / 'link continue'
        self.write_executable(self.clang, '''import os, sys, time
from pathlib import Path
if '--version' in sys.argv:
    print('clang version 23.1.2')
    sys.exit(0)
output = Path(sys.argv[sys.argv.index('-o') + 1])
if '-c' in sys.argv or '-emit-llvm' in sys.argv:
    output.write_bytes(b'runtime')
    sys.exit(0)
output.write_bytes(b'incomplete executable')
Path(os.environ['TEST_LINK_READY']).touch()
deadline = time.monotonic() + 15
while not Path(os.environ['TEST_LINK_CONTINUE']).exists():
    if time.monotonic() > deadline:
        sys.exit('link publication barrier timed out')
    time.sleep(0.01)
output.write_bytes(b'complete executable')
''')
        process = subprocess.Popen([str(self.project / 'minyar'), str(self.source), '-o', str(self.output)],
                                   cwd=self.work, env=dict(self.env, TEST_LINK_READY=str(ready),
                                                         TEST_LINK_CONTINUE=str(proceed)),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 15
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists(), 'linker must reach its publication barrier')
            self.assertEqual(self.output.read_bytes(), b'previous executable')
            proceed.touch()
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.assertEqual(self.output.read_bytes(), b'complete executable')
            self.assertEqual(list(self.work.glob('.minyar-link-*')), [])
        finally:
            proceed.touch()
            if process.poll() is None:
                process.kill()
            process.communicate()

    def test_doctor_reports_missing_clang_actionably(self):
        result = subprocess.run([str(self.project / 'minyar'), '--doctor'],
                                env=dict(self.env, MINYAR_CLANG=str(self.work / 'missing clang')),
                                cwd=self.work, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Clang', result.stderr)
        self.assertIn('MINYAR_CLANG', result.stderr)

    def test_optimization_defaults_and_debug_option(self):
        args = self.launch()[-1]
        self.assertIn('-O2', args)
        result = subprocess.run([str(self.project / 'minyar'), '--debug', str(self.source), '-o', str(self.output)],
                                cwd=self.work, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('-O0', json.loads(self.log.read_text().splitlines()[-1]))
        for options in (['--debug', '--release'], ['--release', '--debug'], ['--debug', '--debug']):
            result = subprocess.run([str(self.project / 'minyar'), *options, str(self.source)],
                                    cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_check_mode_does_not_link_or_replace_a_program(self):
        destination = self.work / self.source.stem
        destination.write_bytes(b'previous executable')
        result = subprocess.run([str(self.project / 'minyar'), '--check', str(self.source)],
                                cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('checked ', result.stdout)
        self.assertEqual(destination.read_bytes(), b'previous executable')
        self.assertFalse(self.log.exists(), 'language checking must not compile/link native artifacts')
        self.assertEqual(list((self.project / 'build/programs').iterdir()), [])

    def test_check_mode_rejects_options_that_require_a_native_output(self):
        for extra in (['--debug'], ['--release'], ['--check']):
            with self.subTest(extra=extra):
                result = subprocess.run([str(self.project / 'minyar'), '--check', *extra, str(self.source)],
                                        cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
        result = subprocess.run([str(self.project / 'minyar'), '--check', str(self.source), '-o', str(self.output)],
                                cwd=self.work, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(self.log.exists())

    def test_unix_links_math_even_without_graphics(self):
        spec = importlib.util.spec_from_file_location('driver', ROOT / 'tools/clang-driver.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        llvm = self.work / 'program.ll'
        llvm.write_text('; no native package\n')
        argv = ['clang-driver.py', 'link', str(self.project), str(llvm), 'runtime.o', str(self.output), '0']
        def link(command):
            Path(command[command.index('-o') + 1]).write_text('complete executable')

        with patch.object(driver.platform, 'system', return_value='Linux'), \
             patch.object(driver.sys, 'argv', argv), patch.object(driver, 'run', side_effect=link) as run:
            driver.main()
        self.assertIn('-lm', run.call_args.args[0])
        self.assertEqual(self.output.read_text(), 'complete executable')

    def test_quoted_flags_and_globs_are_literal_arguments(self):
        (self.work / 'expansion-must-not-happen').touch()
        flags = '-O1 ' + shlex.quote('-DNAME=two words') + ' expansion-* ' + shlex.quote('$(touch injected)')
        args = self.launch({'MINYAR_CLANG_FLAGS': flags})[-1]
        self.assertIn('-DNAME=two words', args)
        self.assertIn('expansion-*', args)
        self.assertIn('$(touch injected)', args)
        self.assertFalse((self.work / 'injected').exists())

    def test_graphics_preserves_project_and_dependency_paths(self):
        calls = self.launch({'TEST_GRAPHICS': '1'})
        self.assertIn('-I' + str(self.include), self.native_calls(calls)[0])
        objects = [arg for arg in calls[-1] if arg.endswith('.o') and '/native/' in arg]
        self.assertEqual(len(objects), 1, calls[-1])
        self.assertTrue(Path(objects[0]).is_file(), objects)

    def test_graphics_cache_tracks_flags_and_compiler_version(self):
        base = {'TEST_GRAPHICS': '1'}
        self.assertEqual(len(self.native_calls(self.launch(base))), 1)
        self.assertEqual(len(self.native_calls(self.launch(base))), 0)
        changed = dict(base, MINYAR_NATIVE_FLAGS='-O0 -DPORTABILITY=1')
        self.assertEqual(len(self.native_calls(self.launch(changed))), 1)
        self.assertEqual(len(self.native_calls(self.launch(changed))), 0)
        self.assertEqual(len(self.native_calls(self.launch(dict(changed, TEST_CLANG_VERSION='clang version 24.0.0')))), 1)

    def test_graphics_cache_tracks_header_contents_even_with_old_timestamp(self):
        base = {'TEST_GRAPHICS': '1'}
        self.launch(base)
        header = self.project / 'runtime/minyar_native.h'
        header.write_text(header.read_text() + '\n/* changed dependency */\n')
        os.utime(header, (1, 1))
        self.assertEqual(len(self.native_calls(self.launch(base))), 1)

    def test_graphics_cache_does_not_read_entire_compiler(self):
        spec = importlib.util.spec_from_file_location('driver', ROOT / 'tools/clang-driver.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        read_bytes = Path.read_bytes

        def bounded_read(path):
            self.assertNotEqual(path.resolve(), self.clang.resolve(),
                                'warm native builds must not hash a whole compiler binary')
            return read_bytes(path)

        with patch.dict(os.environ, self.env), patch.object(Path, 'read_bytes', bounded_read):
            driver.graphics(self.project, str(self.clang), driver.clang_identity(str(self.clang)), ['-O2'])

    def test_graphics_cache_tracks_compiler_replacement_with_preserved_mtime(self):
        base = {'TEST_GRAPHICS': '1'}
        self.launch(base)
        before = self.clang.stat()
        self.clang.write_text(self.clang.read_text().replace('output', 'result'))
        os.utime(self.clang, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.clang.stat().st_size, before.st_size)
        self.assertEqual(len(self.native_calls(self.launch(base))), 1)


if __name__ == '__main__':
    unittest.main()
