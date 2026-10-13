#!/usr/bin/env python3
"""Native runtime objects are compiled once per distinct content and flags."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get('MINYAR_CLANG', os.environ.get('LLVM_CC', 'clang'))
DRIVER = ROOT / 'build/tooling/tools/clang-driver'


class NativeObjectCache(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-cache-')
        self.project = Path(self.temporary.name)
        (self.project / 'runtime/native').mkdir(parents=True)
        (self.project / 'runtime/value.h').write_text('#define VALUE 1\n')
        (self.project / 'runtime/native/net.c').write_text('#include "../value.h"\nint bridge(void) { return VALUE; }\n')
        self.program = self.project / 'program.ll'
        self.program.write_text('; minyar-native-library: net\ndefine i32 @main() {\nentry:\n  ret i32 0\n}\n')
        source = self.project / 'runtime.c'
        source.write_text('int minyar_native_cache_runtime;\n')
        self.runtime = self.project / 'runtime.o'
        subprocess.run([CLANG, '-c', str(source), '-o', str(self.runtime)], check=True, timeout=60)

    def tearDown(self):
        self.temporary.cleanup()

    def build(self, flags=('-O1',)):
        evidence = Path(tempfile.mkdtemp(prefix='native-cache-evidence-')) / 'link'
        environment = dict(os.environ, MINYAR_CLANG=CLANG, MINYAR_NATIVE_FLAGS=' '.join(flags),
                           MINYAR_CLANG_FLAGS='-O1 -Wno-override-module', MINYAR_LINK_ARTIFACTS=str(evidence))
        try:
            result = subprocess.run([str(DRIVER), 'link', str(self.project), str(self.program), str(self.runtime),
                                     str(self.project / 'program'), '0'], env=environment,
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((evidence / 'manifest.json').read_text())
        finally:
            shutil.rmtree(evidence.parent)
        rows = [row for row in manifest['inputs'] if row['retained'].startswith('native-')]
        self.assertEqual(len(rows), 1)
        return Path(rows[0]['original'])

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
        (self.project / 'runtime/native/net.c').write_text('#include "../value.h"\nint bridge(void) { return VALUE + 1; }\n')
        source = self.build()
        flags = self.build(('-O2',))
        self.assertEqual(len({first, header, source, flags}), 4)
        for path in (first, header, source, flags):
            self.assertTrue(path.is_file())
        # Temporaries are named net-<random>; finished objects carry the
        # 64-digit content key, so anything else was left behind.
        leftovers = [p.name for p in (self.project / 'build/native').iterdir()
                     if not re.fullmatch(r'net-[0-9a-f]{64}\.o', p.name)]
        self.assertEqual(leftovers, [], 'temporary objects must not be left behind')


if __name__ == '__main__':
    unittest.main()
