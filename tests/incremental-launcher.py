#!/usr/bin/env python3
"""Exercise the incremental option through the existing launcher race oracles."""
import importlib.util
from pathlib import Path
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('launcher', ROOT / 'tests/launcher-isolation.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class IncrementalLauncher(launcher.LauncherIsolation):
    def setUp(self):
        super().setUp()
        names = ('minyarc-modules', 'minyar-module-build')
        for name in names:
            shutil.copy2(ROOT / 'build' / name, self.project / 'build' / name)
        with (self.project / 'Makefile').open('a') as stream:
            stream.write('\n.PHONY: ' + ' '.join('build/' + name for name in names) + '\n')
            stream.write(' '.join('build/' + name for name in names) + ':\n\t@:\n')

    def command(self, *args, **kwargs):
        command, output = super().command(*args, **kwargs)
        command.insert(1, '--incremental')
        return command, output

    def assert_clean(self):
        super().assert_clean()
        cache = self.project / 'build/module-cache'
        self.assertEqual(list(cache.glob('invocation.*')), [])


if __name__ == '__main__':
    unittest.main()
