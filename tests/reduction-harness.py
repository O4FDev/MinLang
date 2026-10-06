#!/usr/bin/env python3
"""Prove reduction preserves a real compiled-program mismatch and valid typing."""
import json
import os
from pathlib import Path
import sys

from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]


def main():
    compiler = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc')).resolve()
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    runtime = Path(os.environ.get('MINYAR_TEST_RUNTIME', ROOT / 'build/minyar-runtime.o')).resolve()
    with Evidence('reduction-harness', inputs=(compiler, runtime)) as evidence:
        source = evidence.path / 'failure.min'
        source.write_text('''function bug(value: Integer): Integer { return value + 1 }
print("unrelated prefix")
print(bug(41))
print("unrelated suffix")
''')
        oracle = evidence.path / 'oracle.py'
        # Controlled mismatch: the undesired 42 result must survive reduction.
        # Removing either function or call invalidates typing or loses the bug.
        oracle.write_text('import subprocess,sys\nfrom pathlib import Path\n'
                         'llvm=Path(sys.argv[1]); binary=llvm.with_suffix(".exe")\n'
                         f'linked=subprocess.run([{clang!r},"-O0","-Wno-override-module",str(llvm),{str(runtime)!r},"-o",str(binary)],capture_output=True)\n'
                         'if linked.returncode: raise SystemExit(2)\n'
                         'result=subprocess.run([str(binary)],capture_output=True)\n'
                         'raise SystemExit(0 if result.returncode==0 and b"42\\n" in result.stdout and not result.stderr else 1)\n')
        output = evidence.path / 'reduced.min'
        command = [sys.executable, ROOT / 'tools/reduce-minyar.py', source,
                   '--compiler', compiler, '--output', output,
                   '--oracle', sys.executable, 'oracle.py', '{llvm}']
        evidence.run(command, cwd=evidence.path, timeout=60, phase='reduce', check=True)
        protected = evidence.path / 'protected.min'
        sidecar = protected.with_suffix('.min.json')
        sidecar.write_text('preserve this report')
        refusal = evidence.run([sys.executable, ROOT / 'tools/reduce-minyar.py', source,
                                '--compiler', compiler, '--output', protected,
                                '--oracle', sys.executable, oracle, '{llvm}'], timeout=20)
        assert refusal.returncode != 0 and not protected.exists()
        assert sidecar.read_text() == 'preserve this report'
        reduced = output.read_text()
        assert 'unrelated' not in reduced and 'function bug' in reduced and 'print(bug(41))' in reduced, reduced
        report = json.loads(output.with_suffix('.min.json').read_text())
        assert report['original_lines'] == 4 and report['reduced_lines'] == 2, report
        # A non-reproducing oracle must fail rather than emit a bogus reduction.
        refused = evidence.path / 'refused.min'
        result = evidence.run([sys.executable, ROOT / 'tools/reduce-minyar.py', source,
                               '--compiler', compiler, '--output', refused, '--oracle',
                               sys.executable, '-c', 'raise SystemExit(1)', '{source}'], timeout=20, phase='negative-control')
        assert result.returncode != 0 and not refused.exists(), result
        # A source-name-dependent oracle must not certify a differently named
        # deliverable merely because the internal candidate preserved the name.
        named_output = evidence.path / 'name-sensitive.min'
        result = evidence.run([sys.executable, ROOT / 'tools/reduce-minyar.py', source,
                               '--compiler', compiler, '--output', named_output,
                               '--oracle', sys.executable, '-c',
                               'import pathlib,sys; raise SystemExit(0 if pathlib.Path(sys.argv[1]).name == "failure.min" else 1)',
                               '{source}'], timeout=30, phase='negative-relocation')
        assert result.returncode != 0 and not named_output.exists(), result
        assert b'does not preserve the oracle' in result.stderr, result.stderr
        # Keep imports runnable after relocation, even when evidence is inside
        # the source directory (a live recursive copy would copy itself).
        module_source = evidence.path / 'import-case' / 'entry.min'
        module_source.parent.mkdir()
        (module_source.parent / 'helper.min').write_text('public function answer(): Integer { return 42 }\n')
        module_source.write_text('use "./helper.min" as helper\nprint("unrelated")\nprint(helper.answer())\n')
        module_output = evidence.path / 'relocated' / 'entry.min'
        evidence.run([sys.executable, ROOT / 'tools/reduce-minyar.py', module_source,
                      '--compiler', compiler, '--output', module_output,
                      '--oracle', sys.executable, oracle, '{llvm}'], timeout=60,
                     env={**os.environ, 'MINYAR_TEST_EVIDENCE': str(module_source.parent / 'evidence')},
                     phase='reduce-imports', check=True)
        assert (module_output.parent / 'helper.min').is_file()
        relocated_llvm = evidence.path / 'relocated.ll'
        evidence.run([compiler, module_output, relocated_llvm], timeout=20, check=True)
        evidence.run([sys.executable, oracle, relocated_llvm], timeout=20, check=True)
    print('Reduction preserves the compiled mismatch, required definitions, and rejects a false baseline')


if __name__ == '__main__':
    main()
