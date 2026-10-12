#!/usr/bin/env python3
"""The frozen comparator must survive core evolution and reject changed inputs."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'a5f30a7954381231fbe04a712b72bd9663d1bd7082c667fef851b739ec63c3cf'


class FrozenBaseline(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'compiler').mkdir()
        for name in ('scripts/build-closure-compiler.py', 'compiler/compiler.min',
                     'compiler/foundation-baseline.min'):
            shutil.copyfile(ROOT / name, self.root / name)

    def generate(self):
        target = self.root / 'control.min'
        result = subprocess.run([sys.executable, self.root / 'scripts/build-closure-compiler.py',
                                 '--baseline', target], capture_output=True, timeout=10)
        return result, target

    def test_current_core_evolution_preserves_frozen_comparator(self):
        core = self.root / 'compiler/compiler.min'
        core.write_bytes(core.read_bytes() + b'\n// Later compiler changes do not change the comparator.\n')
        result, target = self.generate()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), EXPECTED)

    def test_modified_snapshot_is_rejected_without_output(self):
        snapshot = self.root / 'compiler/foundation-baseline.min'
        snapshot.write_bytes(snapshot.read_bytes() + b'\n// Corrupted comparator.\n')
        result, target = self.generate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'foundation baseline', result.stderr)
        self.assertFalse(target.exists())

    def test_missing_snapshot_has_no_current_source_fallback(self):
        (self.root / 'compiler/foundation-baseline.min').unlink()
        result, target = self.generate()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
