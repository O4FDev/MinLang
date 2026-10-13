#!/usr/bin/env python3
"""Keep strict suite consumers inside isolated correctness source snapshots."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('linux_checks', ROOT / 'scripts/check-linux.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
CATALOGUE_SPEC = importlib.util.spec_from_file_location('suite_catalogue', ROOT / 'tests/suite-catalogue.py')
CATALOGUE = importlib.util.module_from_spec(CATALOGUE_SPEC)
CATALOGUE_SPEC.loader.exec_module(CATALOGUE)

# Independent of the runner's directory list; these are OS library inputs.
OS_ADAPTERS = {
    'os/arch/x86_64/tlsverify.min': (b'x86_64 trust\r\n\xff\x00\n', 0o640),
    'os/arch/arm64/tlsverify.min': (b'arm64 trust\r\n\xfe\x00\n', 0o600),
    'os/arch/x86_64/aes.min': (b'x86_64 aes\r\n\xfd\x00\n', 0o644),
    'os/arch/arm64/aes.min': (b'arm64 aes\r\n\xfc\x00\n', 0o755),
}


class LinuxSnapshot(unittest.TestCase):
    def snapshot(self, directory):
        source, work = directory / 'source', directory / 'snapshot'
        source.mkdir()
        work.mkdir()
        for name in RUNNER.DIRECTORIES:
            (source / name).mkdir(parents=True)
        for name in ('Makefile', 'minyar'):
            (source / name).write_text(name + '\n')
        (source / '.github/workflows').mkdir(parents=True, exist_ok=True)
        workflow = source / '.github/workflows/ci.yml'
        workflow.write_text('jobs:\n  native:\n    run: python3 tests/native.py\n')
        (source / 'tests/native.py').write_text('print("native")\n')
        return source, work, workflow

    def test_explicit_llvm_uses_its_matching_linker_instead_of_path_linker(self):
        with tempfile.TemporaryDirectory(prefix='minyar-selected-llvm-') as temporary:
            # resolve_toolchain reports resolved paths; macOS temp dirs sit behind /var -> /private/var.
            work = Path(temporary).resolve()
            chosen = work / 'llvm23'
            old = work / 'llvm18'
            chosen.mkdir()
            old.mkdir()
            for path in (chosen / 'clang', chosen / 'clang++', chosen / 'ld.lld', old / 'ld.lld'):
                path.write_text('#!/bin/sh\nprintf \'%s\\n\' \'clang version 23.1.2\'\n' if path.name != 'ld.lld' else '#!/bin/sh\nprintf \'%s\\n\' \'LLD 23.1.2\'\n')
                path.chmod(0o755)
            commands = {'chosen-clang': str(chosen / 'clang'), 'chosen-cxx': str(chosen / 'clang++'),
                        'make': 'make', 'ld.lld': str(old / 'ld.lld'), 'ld.lld-23': None}
            with mock.patch.object(RUNNER.shutil, 'which', side_effect=commands.get):
                tools = RUNNER.resolve_toolchain('chosen-clang', 'chosen-cxx')
            self.assertEqual(tools['ld.lld'], str(chosen / 'ld.lld'))
            (chosen / 'ld.lld').unlink()
            with mock.patch.object(RUNNER.shutil, 'which', side_effect=commands.get):
                with self.assertRaisesRegex(ValueError, 'matching LLD was not found'):
                    RUNNER.resolve_toolchain('chosen-clang', 'chosen-cxx')

    def test_frontend_checks_wait_for_the_complete_shared_build(self):
        with tempfile.TemporaryDirectory(prefix='minyar-shared-frontends-') as temporary:
            root = Path(temporary)
            (root / 'logs').mkdir()
            (root / 'build').mkdir()
            (root / 'Makefile').write_text('early:\n\t@printf early >build/minyarc; touch early\n'
                'late:\n\t@sleep 0.3; printf final >build/minyarc; touch late\n')
            runner = RUNNER.check_runner.Runner(work=root, logs=root / 'logs', env=dict(os.environ),
                make=['make', '-j1'], jobs=2, timeout=5, report={'checks': []}, save=lambda: None,
                retries=0)
            checks = [RUNNER.check_runner.Check('frontend-identity',
                ['sh', '-c', 'test -f late && test "$(cat build/minyarc)" = final'], goals=['early'], expected=20),
                RUNNER.check_runner.Check('late-input', ['test', '-f', 'late'], goals=['late'], expected=10)]
            runner.run_all(checks)
            self.assertEqual(runner.results, {'frontend-identity': 'passed', 'late-input': 'passed'})

    def test_workflow_consumers_remain_reviewable_and_catalogue_valid(self):
        with tempfile.TemporaryDirectory(prefix='minyar-linux-snapshot-') as temporary:
            source, work, workflow = self.snapshot(Path(temporary))
            RUNNER.copy_source_snapshot(source, work)
            self.assertEqual((work / '.github/workflows/ci.yml').read_bytes(), workflow.read_bytes())
            CATALOGUE.validate({'schema_version': 1, 'sources': [{
                'path': 'tests/native.py', 'role': 'suite', 'reason': 'Native CI control',
                'consumers': ['.github/workflows/ci.yml']} ]}, work)

    def test_build_git_and_python_cache_artifacts_are_not_inherited(self):
        with tempfile.TemporaryDirectory(prefix='minyar-linux-snapshot-') as temporary:
            source, work, _ = self.snapshot(Path(temporary))
            for name in ('build/minyarc', '.git/config', 'tests/__pycache__/native.pyc', 'tests/stale.pyc'):
                artifact = source / name
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_bytes(b'host artifact')
            RUNNER.copy_source_snapshot(source, work)
            for name in ('build', '.git', 'tests/__pycache__', 'tests/stale.pyc'):
                self.assertFalse((work / name).exists(), name)

    def test_os_adapters_retain_bytes_modes_and_manifest_hashes(self):
        with tempfile.TemporaryDirectory(prefix='minyar-linux-snapshot-') as temporary:
            source, work, _ = self.snapshot(Path(temporary))
            for name, (raw, mode) in OS_ADAPTERS.items():
                adapter = source / name
                adapter.parent.mkdir(parents=True, exist_ok=True)
                adapter.write_bytes(raw)
                adapter.chmod(mode)
            expected = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in source.rglob('*') if path.is_file()}
            manifest = RUNNER.snapshot_sources(source, work)
            for name, (raw, mode) in OS_ADAPTERS.items():
                with self.subTest(adapter=name):
                    copied = work / name
                    self.assertTrue(copied.is_file(), name)
                    self.assertEqual(copied.read_bytes(), raw)
                    self.assertEqual(stat.S_IMODE(copied.stat().st_mode), mode)
                    self.assertIn(name, manifest)
                    self.assertEqual(manifest[name], hashlib.sha256(raw).hexdigest())
            self.assertEqual(manifest, expected)

    def test_os_build_git_and_python_cache_artifacts_are_not_inherited(self):
        with tempfile.TemporaryDirectory(prefix='minyar-linux-snapshot-') as temporary:
            source, work, _ = self.snapshot(Path(temporary))
            adapter = source / 'os/arch/x86_64/tlsverify.min'
            adapter.parent.mkdir(parents=True)
            adapter.write_bytes(b'OS source fixture\n')
            for name in ('build/os/arm64/kernel.elf', 'os/build/x86_64/kernel.elf',
                         'os/.git/config', 'os/arch/arm64/__pycache__/adapter.pyc',
                         'os/arch/x86_64/stale.pyc'):
                artifact = source / name
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_bytes(b'host artifact')
            manifest = RUNNER.snapshot_sources(source, work)
            self.assertEqual((work / 'os/arch/x86_64/tlsverify.min').read_bytes(), adapter.read_bytes())
            self.assertEqual(manifest['os/arch/x86_64/tlsverify.min'],
                             hashlib.sha256(adapter.read_bytes()).hexdigest())
            for name in ('build', 'os/build', 'os/.git', 'os/arch/arm64/__pycache__',
                         'os/arch/x86_64/stale.pyc'):
                self.assertFalse((work / name).exists(), name)
                self.assertFalse(any(key == name or key.startswith(name + '/') for key in manifest), name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
