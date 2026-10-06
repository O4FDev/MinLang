#!/usr/bin/env python3
"""One input-source control reads the mutated slot instead of captured scalar."""
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
    assert case['test'].endswith('.test_scalar_loop_capture_survives_mutation_continue_and_break')
    compiler = ROOT / 'build/minyarc'
    runtime = args.baseline_results.parent / 'system-k32.o'
    assert sha(compiler) == baseline['compiler_sha256']
    parent = ROOT / 'build/memory-research-peer-loop-calibration'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    original = case['source']
    marker = 'captured = captured * 100 + value'
    assert original.count(marker) == 1
    altered = original.replace(marker, 'captured = captured * 100 + source[index]')
    source, llvm = out / 'altered.min', out / 'altered.ll'
    source.write_text(altered)
    (out / 'original.min').write_text(original)
    (out / 'source-control.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),
        altered.splitlines(True), fromfile='original.min', tofile='altered.min')))
    (out / 'expected.stdout').write_text(case['expected_stdout'])
    for p in (Path(__file__).resolve(), ROOT / 'tests/clang_helpers.py'):
        shutil.copyfile(p, out / p.name)
    report = {'status': 'running', 'checks': [], 'detections': [], 'compiler_sha256': sha(compiler),
              'runtime_object_sha256': sha(runtime), 'baseline_result_sha256': sha(args.baseline_results),
              'scope': 'Input-source oracle calibration; no compiler/runtime mutation, saved-output corruption or timing.'}

    def save():
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, command):
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        report['checks'].append({'label': label, 'command': command, 'returncode': result.returncode,
                                'stdout': label + '.stdout', 'stderr': label + '.stderr'})
        save()
        assert result.returncode == 0 and not result.stderr, (label, result.stderr)
        return result

    print('Evidence: ' + str(out), flush=True)
    try:
        run('generate', [str(compiler), str(source), str(llvm)])
        expected = case['expected_stdout'].splitlines()
        assert len(expected) == 11 and expected[0] == '40709'
        for optimization in ('O0', 'O2'):
            binary = out / optimization
            run(optimization + '-link', clang_command(['clang', '-' + optimization,
                '-Wno-override-module', str(llvm), str(runtime), '-o', str(binary)]))
            result = run(optimization + '-execute', [str(binary)])
            actual = result.stdout.splitlines()
            assert len(actual) == 11 and actual[0] == str(104 * 10000 + 107 * 100 + 109)
            assert actual[1:] == expected[1:]
            report['detections'].append({'optimization': optimization, 'line': 1,
                'expected_captured': expected[0], 'actual_mutated_source': actual[0],
                'remaining_lines_unchanged': True, 'returncode': 0})
        assert sha(compiler) == report['compiler_sha256'] and sha(runtime) == report['runtime_object_sha256']
        report.update(status='passed', sources=[{'path': str(p.relative_to(out)), 'sha256': sha(p)}
            for p in out.iterdir() if p.is_file() and p.suffix in ('.py', '.min', '.patch')])
        print('Oracle rejects mutated-slot source control at O0 and O2.', flush=True)
    except Exception as error:
        report.update(status='failed', failure=str(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
