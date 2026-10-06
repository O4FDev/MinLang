#!/usr/bin/env python3
"""Fault injection for scalar benchmark evidence and paired observations."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'experiments/memory/checked-scalars-study.py'
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location('scalar_study', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
work = Path(tempfile.mkdtemp())
output = work / 'compile-failed.json'
p = subprocess.run([sys.executable, str(path), '--compiler', sys.executable, '--output', str(output)], text=True, capture_output=True)
r = json.loads(output.read_text())
assert p.returncode and r['status'] == 'failed' and r['commands'][0]['returncode'] != 0
assert Path(r['directory'], 'compile-fixture.log').exists()
print('GREEN: compile failure report and command log retained')
output = work / 'partial-measurement.json'
sample_calls = 0


def fake_run(command, **kwargs):
    global sample_calls
    if command[0] == str(Path(sys.executable).resolve()):
        Path(command[-1]).write_text('\n'.join(f'define i64 @.minyar.fn.{name}(i64 %a, i64 %b) {{\n ret i64 0\n}}' for name in m.FUNCTIONS) + '\n@minyar_checked_scalars_runScalarStudy(\n')
    elif '-emit-llvm' in command:
        Path(command[-1]).write_text('\n'.join('@"\\01_.minyar.fn.' + name + '"' for name in m.FUNCTIONS) if str(command[-3]).endswith('-driver.c') else '; native mock module\n')
    elif len(command) == 5 and command[1] in ('cpp', 'minyar'):
        sample_calls += 1
        if sample_calls == 4:
            return subprocess.CompletedProcess(command, 7, '', 'injected sample failure')
        row = {'result': m.oracle(command[2], int(command[3]), int(command[4])), 'cpu_ns': 100, 'wall_ns': 100}
        return subprocess.CompletedProcess(command, 0, json.dumps(row), '')
    return subprocess.CompletedProcess(command, 0, '', '')


with patch.object(sys, 'argv', [str(path), '--measure', '--samples', '3', '--count', '1', '--compiler', sys.executable, '--output', str(output)]), patch.object(m.subprocess, 'run', fake_run):
    try:
        with redirect_stdout(io.StringIO()):
            m.main()
    except RuntimeError:
        pass
    else:
        raise AssertionError('expected injected failure')
r = json.loads(output.read_text())
entry = r['configurations']['system']['shift']
assert r['status'] == 'failed' and len(entry['warmup_samples']) == 2
assert len(entry['samples']['cpp']) == 1 and len(entry['samples']['minyar']) == 0
assert r['commands'][-1]['returncode'] == 7
print('GREEN: failure preserves both warmups, completed unmatched pair row, failing command, exact log')
output = work / 'timeout.json'
with patch.object(sys, 'argv', [str(path), '--compiler', sys.executable, '--output', str(output)]), patch.object(m.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['mock'], 240, output=b'partial stdout', stderr=b'partial stderr')):
    try:
        with redirect_stdout(io.StringIO()):
            m.main()
    except subprocess.TimeoutExpired:
        pass
r = json.loads(output.read_text())
assert r['status'] == 'failed' and r['commands'][0]['error'] == 'timeout'
assert Path(r['directory'], 'compile-fixture.log').read_bytes() == b'partial stdoutpartial stderr'
print('GREEN: timeout preserves partial subprocess output and durable error report')

sample_calls = -10000
for measure in (False, True):
    output = work / ('successful-measure.json' if measure else 'successful-correctness.json')
    argv = [str(path), '--samples', '3', '--count', '1', '--compiler', sys.executable, '--output', str(output)]
    if measure:
        argv.append('--measure')
    def successful_run(command, **kwargs):
        completed = fake_run(command, **kwargs)
        if len(command) == 5 and command[1] in ('cpp', 'minyar'):
            row = json.loads(completed.stdout)
            row.update(system_operations=0, pool_allocations=0)
            completed.stdout = json.dumps(row)
        return completed
    with patch.object(sys, 'argv', argv), patch.object(m.subprocess, 'run', successful_run):
        with redirect_stdout(io.StringIO()):
            m.main()
    r = json.loads(output.read_text())
    assert r['status'] == 'passed'
    assert len(r['configurations']) == (5 if measure else 6)
    if measure:
        for entries in r['configurations'].values():
            for entry in entries.values():
                assert entry['paired_cpu_ratio']['median'] == 1
                assert entry['paired_cpu_ratio']['sample_count'] == 3
    else:
        assert sum(map(len, r['configurations'].values())) == 576
print('GREEN: mock happy paths preserve all 576 oracle entries and 20 complete paired summaries')

output = work / 'missing-linkage-alias.json'
def missing_alias_run(command, **kwargs):
    completed = successful_run(command, **kwargs)
    if '-emit-llvm' in command and str(command[-3]).endswith('-driver.c'):
        Path(command[-1]).write_text('; intentionally omitted language aliases\n')
    return completed
with patch.object(sys, 'argv', [str(path), '--measure', '--count', '1', '--samples', '3', '--compiler', sys.executable, '--output', str(output)]), patch.object(m.subprocess, 'run', missing_alias_run):
    try:
        with redirect_stdout(io.StringIO()):
            m.main()
    except AssertionError:
        pass
    else:
        raise AssertionError('missing C language aliases must fail before LTO link')
r = json.loads(output.read_text())
assert r['status'] == 'failed' and r['error']['type'] == 'AssertionError'
assert not r['configurations']
print('GREEN: omitted C linkage aliases rejected before LTO link or measurement')
