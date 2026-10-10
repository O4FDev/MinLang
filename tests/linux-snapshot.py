#!/usr/bin/env python3
"""Keep strict suite consumers inside isolated correctness source snapshots."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('linux_checks', ROOT / 'scripts/check-linux.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
CATALOGUE_SPEC = importlib.util.spec_from_file_location('suite_catalogue', ROOT / 'tests/suite-catalogue.py')
CATALOGUE = importlib.util.module_from_spec(CATALOGUE_SPEC)
CATALOGUE_SPEC.loader.exec_module(CATALOGUE)


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
