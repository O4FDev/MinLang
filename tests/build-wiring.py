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
                             'check-peer-grpc-retire'):
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
