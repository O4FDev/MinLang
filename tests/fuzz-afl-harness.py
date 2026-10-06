#!/usr/bin/env python3
"""Test AFL driver instrumentation and reject campaigns without executions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AflHarness(unittest.TestCase):
    def campaign(self, *, validate=True, executions=3, finding=None):
        with tempfile.TemporaryDirectory(prefix='minyar-afl-harness-') as directory:
            root = Path(directory)
            for name in ['scripts', 'tests/fuzz-corpus/inputs', 'runtime', 'bin']:
                (root / name).mkdir(parents=True)
            shutil.copy2(ROOT / 'scripts/fuzz-afl.sh', root / 'scripts/fuzz-afl.sh')
            shutil.copy2(ROOT / 'tests/llvm_sanitizer.py', root / 'tests/llvm_sanitizer.py')
            (root / 'runtime/minyar_runtime.c').write_text('/* stub */\n')
            (root / 'tests/fuzz-corpus/minyar.dict').write_text('"print"\n')
            (root / 'tests/fuzz-corpus/inputs/seed.min').write_text('print(1)\n')
            programs = {
                'make': '''from pathlib import Path
root=Path.cwd()
root=Path(__import__('sys').argv[__import__('sys').argv.index('-C')+1])
(root/'build').mkdir(exist_ok=True)
(root/'build/compiler-stage2.ll').write_text('define void @value() {\\n  ret void\\n}\\n')
''',
                'afl-clang-fast': '''import json,os,sys
from pathlib import Path
args=sys.argv[1:]
source=next(Path(value) for value in args if value.endswith('.ll'))
if os.environ['VALIDATE_INSTRUMENTATION']=='1':
 assert 'sanitize_address' in source.read_text(), 'generated LLVM lacks sanitize_address'
 runtime=next(value for value in args if value.endswith('minyar_runtime.c'))
 assert '-lm' in args and args.index('-lm')>args.index(runtime), 'libm must follow runtime source'
 assert os.environ.get('AFL_USE_ASAN')=='1' and os.environ.get('AFL_USE_UBSAN')=='1'
Path(os.environ['AFL_BUILD_RECORD']).write_text(json.dumps({'argv':args,'llvm':source.read_text()}))
Path(args[args.index('-o')+1]).write_text('stub target')
''',
                'afl-fuzz': '''import os,sys
from pathlib import Path
args=sys.argv[1:]; root=Path(args[args.index('-o')+1])/'default';root.mkdir(parents=True)
count=os.environ['FAKE_EXECS']
if count!='missing': (root/'fuzzer_stats').write_text('execs_done : '+count+'\\n')
finding=os.environ.get('FAKE_FINDING','')
if finding:
 (root/finding).mkdir();(root/finding/'id:000000').write_text('bad')
''',
            }
            for name, source in programs.items():
                executable = root / 'bin' / name
                executable.write_text('#!/usr/bin/env python3\n' + source)
                executable.chmod(0o755)
            environment = dict(os.environ, PATH=str(root / 'bin') + os.pathsep + os.environ['PATH'],
                               MINYAR_AFL_SECONDS='1', VALIDATE_INSTRUMENTATION=str(int(validate)),
                               AFL_BUILD_RECORD=str(root / 'record.json'), FAKE_EXECS=str(executions),
                               FAKE_FINDING=finding or '')
            # Avoid unrelated user overrides selecting real AFL tools/findings.
            environment.update(AFL_CC=str(root / 'bin/afl-clang-fast'), AFL_FUZZ=str(root / 'bin/afl-fuzz'),
                               MINYAR_AFL_FINDINGS=str(root / 'findings'))
            result = subprocess.run(['sh', str(root / 'scripts/fuzz-afl.sh')], env=environment, text=True,
                                    capture_output=True, timeout=15)
            record = json.loads((root / 'record.json').read_text()) if (root / 'record.json').exists() else None
            return result, record

    def test_generated_compiler_ir_is_prepared_and_libm_is_late(self):
        result, record = self.campaign()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('sanitize_address', record['llvm'])
        self.assertTrue(record['argv'][record['argv'].index('-o')-1] == '-lm')

    def test_zero_execution_campaign_fails(self):
        result, _ = self.campaign(validate=False, executions=0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('executions', result.stderr)

    def test_missing_stats_campaign_fails(self):
        result, _ = self.campaign(validate=False, executions='missing')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stats', result.stderr)

    def test_crashes_and_hangs_fail(self):
        for category in ['crashes', 'hangs']:
            with self.subTest(category=category):
                result, _ = self.campaign(validate=False, finding=category)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(category, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
