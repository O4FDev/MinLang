#!/usr/bin/env python3
"""Native runtime objects are compiled once per distinct content and flags."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get('MINYAR_CLANG', os.environ.get('LLVM_CC', 'clang'))
spec = importlib.util.spec_from_file_location('clang_driver', ROOT / 'tools/clang-driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class NativeObjectCache(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-cache-')
        self.project = Path(self.temporary.name)
        (self.project / 'runtime/native').mkdir(parents=True)
        (self.project / 'runtime/value.h').write_text('#define VALUE 1\n')
        (self.project / 'runtime/native/bridge.c').write_text('#include "../value.h"\nint bridge(void) { return VALUE; }\n')
        self.base = driver.clang_identity(CLANG)

    def tearDown(self):
        self.temporary.cleanup()

    def build(self, flags=('-O1',)):
        return Path(driver.native_object(self.project, CLANG, self.base, 'bridge.c', list(flags)))

    def test_unchanged_sources_reuse_the_object(self):
        first = self.build()
        stamp = first.stat().st_mtime_ns
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(second.stat().st_mtime_ns, stamp, 'an unchanged object must not be recompiled')

    def test_header_source_and_flag_changes_compile_a_new_object(self):
        first = self.build()
        (self.project / 'runtime/value.h').write_text('#define VALUE 2\n')
        header = self.build()
        (self.project / 'runtime/native/bridge.c').write_text('#include "../value.h"\nint bridge(void) { return VALUE + 1; }\n')
        source = self.build()
        flags = self.build(('-O2',))
        self.assertEqual(len({first, header, source, flags}), 4)
        for path in (first, header, source, flags):
            self.assertTrue(path.is_file())
        self.assertEqual([p for p in (self.project / 'build/native').iterdir() if not p.name.endswith('.o')], [],
                         'temporary objects must not be left behind')


if __name__ == '__main__':
    unittest.main()
