#!/usr/bin/env python3
"""A helper's branch identities must survive inlining without hiding either arm."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('minyar_coverage', ROOT / 'scripts/coverage.py')
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class CoverageInlining(unittest.TestCase):
    def test_shared_branch_identity_survives_inlining(self):
        clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
        opt = coverage.find_tool('LLVM_OPT', 'opt')
        with tempfile.TemporaryDirectory(prefix='minyar-coverage-inlining-') as directory:
            directory = Path(directory)
            counts = {}
            for phase in ('before-inlining', 'after-inlining'):
                for calls in (1, 16):
                    work = directory / f'{phase}-{calls}'
                    work.mkdir()
                    source = work / 'source.ll'
                    source.write_text('''@effect = internal global i32 0
define internal void @helper(i1 %condition) alwaysinline {
entry:
  br i1 %condition, label %yes, label %no
yes:
  store volatile i32 1, ptr @effect
  ret void
no:
  store volatile i32 2, ptr @effect
  ret void
}
define i32 @main(i32 %argc, ptr %argv) {
entry:
  %condition = icmp ugt i32 %argc, 1
''' + '  call void @helper(i1 %condition)\n' * calls + '''  %result = load volatile i32, ptr @effect
  ret i32 %result
}
''')
                    instrumented = work / 'instrumented.ll'
                    environment = {**os.environ, 'MINYAR_SANCOV_DIR': str(work)}
                    coverage.instrument_compiler_ir(source, instrumented, clang=clang,
                                                    opt=opt, phase=phase, env=environment)
                    executable = work / 'program'
                    coverage.run([clang, '-O0', '-Wno-override-module', str(instrumented),
                                  str(ROOT / 'tests/compiler-coverage-runtime.c'),
                                  '-o', str(executable)], env=environment)
                    for arguments, expected in (([], 2), (['take-other-arm'], 1)):
                        result = subprocess.run([str(executable), *arguments], env=environment,
                                                capture_output=True, timeout=10)
                        self.assertEqual(result.returncode, expected, result.stderr)
                    edges = coverage.compiler_edge_coverage(work)
                    self.assertEqual(edges['covered'], edges['count'],
                                     'both distinct branch arms must remain measured')
                    counts[phase, calls] = edges['count']
            self.assertEqual(counts['before-inlining', 1], counts['before-inlining', 16],
                             'inlined copies inflated the distinct-branch denominator')
            self.assertGreater(counts['after-inlining', 16], counts['after-inlining', 1],
                               'raw measurement must still expose duplicated branch sites')


if __name__ == '__main__':
    unittest.main(verbosity=2)
