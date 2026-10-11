#!/usr/bin/env python3
"""Probe actual Make prerequisites under POSIX and native Windows host names."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildWiring(unittest.TestCase):

    def test_registration_exposure_has_required_native_and_sanitizer_gates(self):
        import importlib.util
        import json
        import re
        from unittest.mock import patch
        native = 'check-cycle-registration-exposure'
        sanitize = native + '-sanitize'
        source = (ROOT / 'build-support/managed-graphs.mk').read_text()

        def verify(text):
            with tempfile.TemporaryDirectory(prefix='minyar registration wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                makefile.write_text(text + '\n.PHONY: build/minyarc-errors build/minyarc-errors-sanitize\n'
                                   'build/minyarc-errors build/minyarc-errors-sanitize:\n\t@echo ARTIFACT $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(
                    ['make', '-np', '-f', str(makefile), native, sanitize],
                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                both = {native, sanitize}
                for gate in ('check', 'check-portable', 'check-managed-graphs-profiles'):
                    self.assertTrue(both <= rules.get(gate, set()), gate)
                self.assertIn(sanitize, rules.get('check-sanitize', set()))
                fixtures = {'tests/cycle-registration-exposure.c', 'tests/cycle-late-registration.c',
                            'tests/cycle-late-registration.min', 'tests/cycle-additive.c',
                            'tests/cycle-registration.py', 'tools/cycle_runtime.py'}
                for target in both:
                    self.assertTrue(fixtures <= rules.get(target, set()), target)
                self.assertIn('build/minyarc-errors', rules[native])
                self.assertIn('build/minyarc-errors-sanitize', rules[sanitize])
                commands = result.stdout.split('# GNU Make', 1)[0]
                self.assertEqual(commands.count('tests/cycle-registration.py'), 2)
                self.assertEqual(commands.count('--sanitize'), 1)
                self.assertNotIn('--nodes', commands)
                self.assertIn('cycle-registration-exposure-native', commands)
                self.assertIn('cycle-registration-exposure-sanitize', commands)

        verify(source)
        # Removing any required aggregate really changes Make's prerequisite
        # database; a source-string reference alone cannot satisfy this gate.
        for gate in ('check', 'check-portable', 'check-managed-graphs-profiles', 'check-sanitize'):
            line = gate + ': ' + (sanitize if gate == 'check-sanitize'
                                  else native + ' ' + sanitize) + '\n'
            self.assertEqual(source.count(line), 1, gate)
            with self.subTest(missing_gate=gate), self.assertRaises(AssertionError):
                verify(source.replace(line, '', 1))

        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        runner = load('registration_linux_runner', 'scripts/check-linux.py')
        for target in (native, sanitize):
            self.assertEqual(runner.TARGETS.count(target), 1)
        formatter = load('registration_formatter', 'scripts/format.py')
        for fixture in ('tests/cycle-registration-exposure.c', 'tests/cycle-late-registration.c'):
            self.assertIn(fixture, formatter.FILES)
        catalogue = load('registration_catalogue', 'tests/suite-catalogue.py')
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for fixture in ('tests/cycle-registration-exposure.c', 'tests/cycle-late-registration.c',
                        'tests/cycle-late-registration.min', 'tests/cycle-registration.py'):
            self.assertIn(fixture, catalogue.discover(ROOT))
            with self.subTest(uncatalogued=fixture), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[row for row in data['sources']
                                                       if row['path'] != fixture]), ROOT)
        driver = load('registration_driver', 'tests/cycle-registration.py')
        import inspect
        language = driver.load('registration_inspection_control', 'tests/errors-language.py')
        self.assertEqual(Path(inspect.getsourcefile(language.ErrorsLanguage)),
                         ROOT / 'tests/errors-language.py')
        with patch('clang_helpers.platform.system', return_value='Windows'):
            profiles, unsupported = driver.profile_selection(None, True)
            self.assertEqual(profiles, ['system', 'fixed', 'eager'])
            self.assertEqual(unsupported[0]['profile'], 'lazy')
            with self.assertRaises(ValueError):
                driver.profile_selection(['lazy'], True)
        with patch.object(driver, 'windows_host', return_value=True), \
                patch.object(sys, 'argv', ['cycle-registration.py', '--profiles', 'lazy',
                                         '--evidence', 'unused']), \
                self.assertRaises(SystemExit) as unsupported_exit:
            driver.main()
        self.assertEqual(unsupported_exit.exception.code, 2)
        # These schedules are built into main(void), not runtime graph sizes.
        self.assertFalse(driver.build_parser().parse_args(['--evidence', 'out']).__dict__.get('nodes'))
        with self.assertRaises(SystemExit):
            driver.build_parser().parse_args(['--evidence', 'out', '--nodes', '2048'])

    def test_registered_growth_is_mandatory_with_native_and_sanitizer_drivers(self):
        import re
        with tempfile.TemporaryDirectory(prefix='minyar registry wiring ') as folder:
            makefile = Path(folder) / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/managed-graphs.mk').replace(' ', '\\ ') + '\n')
            env = dict(os.environ)
            env.pop('MAKEFLAGS', None)
            result = subprocess.run(
                ['make', '-np', '-f', str(makefile), 'check-cycle-registry-growth',
                 'check-cycle-registry-growth-sanitize'],
                cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            rules = {}
            for line in result.stdout.splitlines():
                match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                if match:
                    rules.setdefault(match[1], set()).update(match[2].split())
            both = {'check-cycle-registry-growth', 'check-cycle-registry-growth-sanitize'}
            for gate in ('check', 'check-portable', 'check-managed-graphs-profiles'):
                self.assertTrue(both <= rules.get(gate, set()), gate)
            self.assertIn('check-cycle-registry-growth-sanitize', rules.get('check-sanitize', set()))
            for target in both:
                self.assertIn('tests/cycle-registry-growth.c', rules.get(target, set()), target)
                self.assertIn('tests/cycle-additive.c', rules.get(target, set()), target)
            commands = result.stdout.split('# GNU Make', 1)[0]
            self.assertEqual(commands.count('tests/cycle-additive.py'), 2)
            self.assertEqual(commands.count('--fixture cycle-registry-growth.c'), 2)
            self.assertEqual(commands.count('--sanitize'), 1)
            self.assertIn('cycle-registry-growth-native', commands)
            self.assertIn('cycle-registry-growth-sanitize', commands)

    def test_native_sanitizers_use_supported_leak_detection(self):
        from unittest.mock import patch
        from clang_helpers import asan_leak_options
        with tempfile.TemporaryDirectory(prefix='minyar sanitizer wiring ') as folder:
            work = Path(folder)
            uname = work / 'uname'
            uname.write_text('#!' + sys.executable + '\nimport os\nprint(os.environ["TEST_UNAME"])\n')
            uname.chmod(0o755)
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'Makefile').replace(' ', '\\ ') + '\n'
                '.PHONY: probe\nprobe:\n\t@echo "$(NATIVE_SANITIZER_ENV)"\n')
            for system, os_value, leaks in (
                    ('Linux', '', 1), ('Darwin', '', 0),
                    ('Windows', 'Windows_NT', 0), ('Linux', 'Windows_NT', 0),
                    ('MINGW64_NT-10.0', '', 0), ('MSYS_NT-10.0', '', 0),
                    ('CYGWIN_NT-10.0', '', 0)):
                with self.subTest(system=system, os_value=os_value):
                    env = dict(os.environ, PATH=str(work) + os.pathsep + os.environ['PATH'],
                               TEST_UNAME=system)
                    env.pop('MAKEFLAGS', None)
                    result = subprocess.run(
                        ['make', '-n', '-f', str(makefile), 'OS=' + os_value,
                         '-o', 'build/minyarc', 'probe', 'check-tls-validity-sanitize'],
                        cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    expected = f'ASAN_OPTIONS=detect_leaks={leaks} UBSAN_OPTIONS=halt_on_error=1'
                    self.assertEqual(result.stdout.count(expected), 2, result.stdout)
                    self.assertIn('tests/tls-validity.py --sanitize', result.stdout)
                    if not os_value or system == 'Windows':
                        with patch('clang_helpers.platform.system', return_value=system):
                            self.assertEqual(asan_leak_options(), f'detect_leaks={leaks}')

    def test_managed_graph_launcher_builds_only_supported_incremental_driver(self):
        with tempfile.TemporaryDirectory(prefix='minyar build wiring ') as folder:
            work = Path(folder)
            uname = work / 'uname'
            uname.write_text('#!' + sys.executable + '\nimport os\nprint(os.environ["TEST_UNAME"])\n')
            uname.chmod(0o755)
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/managed-graphs.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: build/minyarc build/minyarc-callbacks build/minyarc-modules build/minyar-module-build\n'
                'build/minyarc build/minyarc-callbacks build/minyarc-modules build/minyar-module-build:\n'
                '\t@echo ARTIFACT $@\n')
            for system, os_value, incremental in (
                    ('Linux', '', True), ('Darwin', '', True), ('Windows_NT', 'Windows_NT', False),
                    ('MINGW64_NT-10.0', '', False), ('MSYS_NT-10.0', '', False),
                    ('CYGWIN_NT-10.0', '', False)):
                with self.subTest(system=system):
                    env = dict(os.environ, PATH=str(work) + os.pathsep + os.environ['PATH'],
                               TEST_UNAME=system)
                    env.pop('MAKEFLAGS', None)
                    result = subprocess.run(['make', '-n', '-f', str(makefile),
                                             'OS=' + os_value, 'check-managed-graphs-launcher'],
                                            cwd=work, env=env, text=True, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    artifacts = {line.split('ARTIFACT ', 1)[1] for line in result.stdout.splitlines()
                                 if 'ARTIFACT ' in line}
                    expected = {'build/minyarc', 'build/minyarc-callbacks'}
                    if incremental: expected |= {'build/minyarc-modules', 'build/minyar-module-build'}
                    self.assertEqual(artifacts, expected)
                    self.assertIn('tests/managed-graphs-launcher.py', result.stdout)


    def test_peer_driver_gates_prepare_the_request_frontend(self):
        # The real driver runs the request parser after status 1 or 86. Its
        # artifact-only make shim must never trigger a build while testing
        # rejection diagnostics or declaration-cache transitions.
        with tempfile.TemporaryDirectory(prefix='minyar peer wiring ') as folder:
            work = Path(folder)
            makefile = work / 'probe.mk'
            targets = (
                'build/minyarc', 'build/minyarc-modules',
                'build/minyar-default-runtime.o', 'build/minyar-module-build',
                'build/minyarc-errors-request', 'build/minyar-runtime.o',
                'build/minyarc-sanitize', 'build/minyar-runtime-sanitize.o',
                'build/ownership-runtime.o')
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/peer-tests.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: ' + ' '.join(targets) + '\n' +
                ' '.join(targets) + ':\n\t@echo ARTIFACT $@\n')
            for suite in ('tests/peer-rust-go-zig.py', 'tests/peer-regressions.py'):
                for gate in ('check-peer-regressions', 'check-peer-optimizations',
                             'check-peer-sanitize', 'check-peer-ownership'):
                    with self.subTest(suite=suite, gate=gate):
                        env = dict(os.environ)
                        env.pop('MAKEFLAGS', None)
                        result = subprocess.run(
                            ['make', '-n', '-f', str(makefile),
                             'PEER_SUITES=' + suite, gate],
                            cwd=work, env=env, text=True, capture_output=True,
                            timeout=10)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        artifacts = {
                            line.split('ARTIFACT ', 1)[1]
                            for line in result.stdout.splitlines()
                            if 'ARTIFACT ' in line}
                        needs_driver = (suite == 'tests/peer-rust-go-zig.py'
                                        or gate == 'check-peer-ownership')
                        self.assertEqual(
                            'build/minyarc-errors-request' in artifacts,
                            needs_driver)
                        self.assertEqual(
                            'build/minyar-module-build' in artifacts,
                            needs_driver)


    def test_grpc_gates_verify_external_peers_and_bound_default_builds(self):
        with tempfile.TemporaryDirectory(prefix='minyar grpc wiring ') as folder:
            work = Path(folder)
            for name in ('tests/interop/peergrpc/requirements.txt',
                         'scripts/check-peer-python.py'):
                path = work / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('')
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/peer-grpc.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: build/minyarc\n'
                'build/minyarc:\n\t@echo ARTIFACT $@\n')
            for selected in ('build/peergrpc-venv/bin/python', 'preinstalled-python',
                             'preinstalled Python'):
                for gate in ('check-http2', 'check-peer-grpc', 'check-peer-grpc-sanitize',
                             'check-http2-churn', 'check-peer-grpc-churn',
                             'check-peer-grpc-retire', 'check-peer-edge-cids',
                             'check-peer-edge-cids-sanitize'):
                    with self.subTest(selected=selected, gate=gate):
                        env = dict(os.environ)
                        env.pop('MAKEFLAGS', None)
                        result = subprocess.run(
                            ['make', '-n', '-f', str(makefile),
                             'PEER_GRPC_PYTHON=' + selected, gate],
                            cwd=work, env=env, text=True, capture_output=True, timeout=10)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('scripts/check-peer-python.py', result.stdout)
                        self.assertIn('"' + selected + '" scripts/check-peer-python.py', result.stdout)
                        self.assertIn('"' + selected + '" tests/', result.stdout)
                        setup = selected == 'build/peergrpc-venv/bin/python'
                        self.assertEqual('python3 -m venv' in result.stdout, setup)
                        if setup:
                            self.assertIn('GRPC_PYTHON_BUILD_EXT_COMPILER_JOBS=1', result.stdout)
                            self.assertIn('CMAKE_BUILD_PARALLEL_LEVEL=1', result.stdout)



    def test_successful_empty_pip_cannot_publish_peer_ready_stamp(self):
        # Windows task termination can return zero to the MSYS parent even
        # though wheel installation never completed. Verify actual imports
        # before publishing the cache stamp.
        with tempfile.TemporaryDirectory(prefix='minyar incomplete peer ') as folder:
            work = Path(folder)
            for name in ('tests/interop/peergrpc/requirements.txt',
                         'scripts/check-peer-python.py'):
                path = work / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / name).read_bytes())
            mock = work / 'bin/python3'
            mock.parent.mkdir()
            mock.write_text(
                '#!' + sys.executable + '\nfrom pathlib import Path\n'
                'root=Path("build/peergrpc-venv/bin"); root.mkdir(parents=True)\n'
                'pip=root/"pip"; pip.write_text("#!/bin/sh\\n'
                'echo PIP_JOBS=$GRPC_PYTHON_BUILD_EXT_COMPILER_JOBS\\nexit 0\\n"); pip.chmod(0o755)\n'
                'python=root/"python"; python.write_text(' +
                repr('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n') +
                '); python.chmod(0o755)\n')
            mock.chmod(0o755)
            # No interpreter can satisfy this exact pin; the empty installer
            # must not make that incomplete environment appear ready.
            requirements = work / 'tests/interop/peergrpc/requirements.txt'
            requirements.write_text(requirements.read_text().replace('h2==4.3.0', 'h2==0.0.0'))
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/peer-grpc.mk').replace(' ', '\\ ') + '\n')
            env = dict(os.environ, PATH=str(mock.parent) + os.pathsep + os.environ['PATH'])
            env.pop('MAKEFLAGS', None)
            result = subprocess.run(
                ['make', '-f', str(makefile), 'build/peergrpc-venv/.ready'],
                cwd=work, env=env, text=True, capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PIP_JOBS=1', result.stdout)
            self.assertIn('peer Python verification failed:', result.stderr)
            self.assertFalse((work / 'build/peergrpc-venv/.ready').exists())



if __name__ == '__main__':
    unittest.main()
