#!/usr/bin/env python3
"""Calibrate the new embedded-NUL equality oracle using one isolated mutant."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-results', type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline_results.read_text())
    assert baseline['status'] == 'passed'
    case = baseline['coverage'][0]['observed'][0]
    assert case['test'].endswith('.test_text_equality_after_nul_at_every_short_mismatch_position')
    compiler = ROOT / 'build/minyarc'
    assert sha(compiler) == baseline['compiler_sha256']
    parent = ROOT / 'build/memory-research-peer-nul-calibration'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    shutil.copytree(args.baseline_results.parent / 'runtime', out / 'runtime')
    runtime = out / 'runtime/minyar_runtime.c'
    original = runtime.read_text()
    marker = 'bytes_are_equal(left->bytes, right->bytes, (size_t)left->byte_length)'
    assert original.count(marker) == 1
    mutant = original.replace(marker, 'strcmp((const char *)left->bytes, (const char *)right->bytes) == 0')
    runtime.write_text(mutant)
    (out / 'mutant.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),
        mutant.splitlines(True), fromfile='minyar_runtime.c', tofile='nul-mutant/minyar_runtime.c')))
    source, llvm, object_file = out / 'case.min', out / 'case.ll', out / 'runtime.o'
    source.write_text(case['source'])
    (out / 'expected.stdout').write_text(case['expected_stdout'])
    shutil.copyfile(Path(__file__), out / Path(__file__).name)
    shutil.copyfile(ROOT / 'tests/clang_helpers.py', out / 'clang_helpers.py')
    report = {'status': 'running', 'checks': [], 'mutant_detections': [],
              'compiler_sha256': sha(compiler), 'baseline_result_sha256': sha(args.baseline_results),
              'scope': 'One C equality mutant, generated O0/O2; no production modification or timing.'}

    def save():
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, command):
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        report['checks'].append({'label': label, 'command': command, 'returncode': result.returncode,
                                'stdout': label + '.stdout', 'stderr': label + '.stderr'})
        save()
        assert result.returncode == 0, (label, result.stderr)
        return result

    print('Evidence: ' + str(out), flush=True)
    try:
        run('runtime-compile', clang_command(['clang', '-O2', '-DMINYAR_SYSTEM_HEAP=1',
            '-DMINYAR_RC_POLL_BUDGET=32', '-c', str(runtime), '-o', str(object_file)]))
        run('generate', [str(compiler), str(source), str(llvm)])
        expected = case['expected_stdout'].splitlines()
        assert len(expected) == 611
        for optimization in ('O0', 'O2'):
            binary = out / optimization
            run(optimization + '-link', clang_command(['clang', '-' + optimization,
                '-Wno-override-module', str(llvm), str(object_file), '-o', str(binary)]))
            result = run(optimization + '-execute', [str(binary)])
            actual = result.stdout.splitlines()
            assert len(actual) == len(expected)
            differences = [{'line': i + 1, 'expected': a, 'actual': b}
                           for i, (a, b) in enumerate(zip(expected, actual)) if a != b]
            assert differences[0] == {'line': 31, 'expected': 'false', 'actual': 'true'}
            assert differences[1] == {'line': 32, 'expected': 'true', 'actual': 'false'}
            report['mutant_detections'].append({'optimization': optimization, 'differences': differences,
                'witness': 'Size3, changedposition2 after NUL at1; same byte length, unequal content.'})
        report.update(status='passed', production_runtime_unchanged=sha(ROOT / 'runtime/minyar_runtime.c') ==
            hashlib.sha256(original.encode()).hexdigest(),
            sources=[{'path': str(p.relative_to(out)), 'sha256': sha(p)} for p in out.rglob('*')
                     if p.is_file() and p.suffix in ('.c', '.h', '.py', '.min', '.patch')])
        assert report['production_runtime_unchanged']
        print('Semantic NUL oracle kills strcmp mutant at O0 and O2.', flush=True)
    except Exception as error:
        report.update(status='failed', failure=str(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
