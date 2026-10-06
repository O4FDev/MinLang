#!/usr/bin/env python3
"""One approved unchanged Craft generation; frozen runtime reuse and bounded supervision."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory/evidence/native-application-round7'
MATRIX = ROOT / 'research/2026-10-memory/evidence/native-application-round2/final-matrix'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--approval-file', required=True, type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z0-9-]+', args.label)
    assert args.approval_file.is_file()
    evidence = BASE / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix='minyar-native-round7-'))
    source = evidence / 'sources'
    source.mkdir()
    report = {'status': 'preparing', 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'invocation': sys.argv, 'commands': [], 'sources': [], 'work': str(work),
              'limits': {'children': 1, 'wall_seconds': 30, 'native_rss_bytes': 128 * 1024**2,
                         'compiler_rss_bytes': 512 * 1024**2},
              'optimization': '-O2 only; frozen runtime compiled at-O2',
              'sanitizer_coverage': 'None; this run is ordinary O2.',
              'scope': 'One generation; no performance comparison, full-world equality, repeatability or leak-proof claim.'}
    def save():
        write_json(evidence / 'results.json', report)
    def run(label, command, cwd, native=False):
        argv = ['/usr/bin/time', '-l', *map(str, command)]
        outpath, errpath = evidence / (label + '.stdout'), evidence / (label + '.stderr')
        limit = report['limits']['native_rss_bytes' if native else 'compiler_rss_bytes']
        samples, failure, start = [], None, time.monotonic()
        with outpath.open('w') as stdout, errpath.open('w') as stderr:
            process = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr, start_new_session=True)
            while process.poll() is None:
                output = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], text=True, capture_output=True, timeout=2)
                rows = [tuple(map(int, line.split())) for line in output.stdout.splitlines() if line.strip()]
                children = {process.pid}
                while True:
                    next_children = children | {pid for pid, parent, rss in rows if parent in children}
                    if children == next_children:
                        break
                    children = next_children
                resident = [rss * 1024 for pid, parent, rss in rows if pid in children]
                total = sum(resident)
                samples.append({'wall_seconds': time.monotonic() - start,
                                'process_group_rss_bytes': total,
                                'largest_process_rss_bytes': max(resident, default=0)})
                if total > limit:
                    failure = 'sampled_process_group_rss_limit'
                if time.monotonic() - start > 30:
                    failure = 'wall_limit'
                if failure:
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(.025)
            process.wait(timeout=2)
        elapsed = time.monotonic() - start
        stderr = errpath.read_text()
        peak_match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', stderr, re.M)
        timing_match = re.search(r'([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys', stderr)
        peak = int(peak_match[1]) if peak_match else None
        row = {'label': label, 'command': argv, 'cwd': str(cwd), 'returncode': process.returncode,
               'supervised_wall_seconds': elapsed, 'sampled_process_group_peak_rss_bytes':
               max((s['process_group_rss_bytes'] for s in samples), default=0),
               'darwin_time_child_peak_rss_bytes': peak, 'limit_failure': failure,
               'native': native, 'stdout_path': outpath.name, 'stderr_path': errpath.name,
               'darwin_time_real_user_sys_seconds': list(map(float, timing_match.groups())) if timing_match else None}
        report['commands'].append(row)
        write_json(evidence / (label + '-rss-samples.json'), samples)
        save()
        assert not failure and peak is not None and peak <= limit and elapsed <= 30, row
        assert process.returncode == 0, row
        return row
    try:
        shutil.copyfile(args.approval_file, evidence / 'authorization.txt')
        paths = [ROOT / 'examples/craft' / name for name in ['terrain.min', 'noise.min', 'blocks.min', 'main.min']]
        paths += [p for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()]
        paths += [ROOT / 'runtime/native/graphics.c']
        paths += [p for p in (ROOT / 'library').glob('*.min')]
        paths += [ROOT / 'tests' / name for name in ['native-research-round7.min', 'native-research-round7.py', 'native-research-round7-oracle.py']]
        paths += [ROOT / 'README.md', ROOT / 'research/2026-10-memory/README.md']
        paths += list((ROOT / 'docs').glob('*.md'))
        paths += [ROOT / 'research/2026-10-memory/native-application-round7-preregistered.json']
        for path in paths:
            relative = path.relative_to(ROOT)
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            report['sources'].append({'path': str(relative), 'sha256': digest(target)})
        historical = []
        for path in (ROOT / 'research/2026-10-memory').glob('native-application*'):
            if path.is_file() and 'round7' not in path.name:
                historical.append({'path': str(path.relative_to(ROOT)), 'sha256': digest(path)})
        report['historical_entry_hashes'] = historical
        (evidence / 'entry-status.txt').write_text(subprocess.run(['git', 'status', '--porcelain=v1'],
            cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        (evidence / 'entry-production.patch').write_bytes(subprocess.run(['git', 'diff', '--binary', '--',
            'examples/craft', 'runtime/native/graphics.c'], cwd=ROOT, capture_output=True, check=True).stdout)
        prior = json.loads((MATRIX / 'results.json').read_text())
        report['compiler_sha256'] = digest(ROOT / 'build/minyarc')
        assert report['compiler_sha256'] == prior['compiler_sha256']
        runtime = Path(prior['work']) / 'system-o2-runtime.o'
        assert digest(runtime) == 'becb749c61f922ea103e3e3276bd196c73bd3d3e0665bf9132eca336ebaaad0f'
        deps = [row for row in prior['sources'] if row['path'].startswith('runtime/minyar_')]
        for row in deps:
            assert digest(ROOT / row['path']) == row['sha256'], row
        report['runtime'] = {'path': str(runtime), 'sha256': digest(runtime),
                             'verified_dependencies': deps,
                             'original_compile': next(row for row in prior['commands'] if row['label'] == 'system-o2-runtime')}
        spec = importlib.util.spec_from_file_location('round7_oracle', source / 'tests/native-research-round7-oracle.py')
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        expected_start = time.monotonic()
        expected = oracle.expected_inputs()
        write_json(evidence / 'expected-inputs.json', expected)
        report['expected_saved_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['expected_preparation_wall_seconds'] = time.monotonic() - expected_start
        report['expected_sha256'] = digest(evidence / 'expected-inputs.json')
        save()
        run('clang-identity', ['clang', '--version'], source)
        llvm = work / 'application.ll'
        run('frontend', [ROOT / 'build/minyarc', source / 'tests/native-research-round7.min', llvm,
                         '--library', source / 'library'], source)
        shutil.copyfile(llvm, evidence / 'application.ll')
        report['llvm_sha256'] = digest(llvm)
        report['llvm_definitions'] = len(re.findall(r'^define ', llvm.read_text(), re.M))
        binary = work / 'generation-o2'
        run('link-o2', ['clang', '-O2', '-Wno-override-module', llvm, runtime, '-lm', '-o', binary], source)
        report['binary_sha256'] = digest(binary)
        report['native_start_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['status'] = 'executing_one_generation'
        save()
        run('native-o2', [binary], work, native=True)
        assert (evidence / 'native-o2.stdout').read_text() == 'round7 generation and lighting returned\n'
        report['output_files'] = [{'name': path.name, 'bytes': path.stat().st_size, 'sha256': digest(path)}
                                  for path in sorted(work.glob('*.bin'))]
        save()
        oracle_start = time.monotonic()
        report['oracle'] = oracle.validate(work, expected)
        report['oracle_wall_seconds'] = time.monotonic() - oracle_start
        for name in ['state.bin', 'dirty.bin', 'tops.bin']:
            shutil.copyfile(work / name, evidence / name)
        payload = (work / 'world.bin').read_bytes()
        write_json(evidence / 'observed-selected-columns.json', [
            {'x': r['x'], 'z': r['z'], 'column_hex': bytes(payload[y * 512 * 512 + r['z'] * 512 + r['x']]
                                                        for y in range(80)).hex()}
            for r in expected['selected_columns']])
        report['protected_changed'] = [row['path'] for row in report['sources'] + historical
                                       if digest(ROOT / row['path']) != row['sha256']]
        assert all(p == 'research/2026-10-memory/README.md' for p in report['protected_changed'])
        assert digest(ROOT / 'build/minyarc') == report['compiler_sha256']
        assert digest(runtime) == report['runtime']['sha256']
        report['status'] = 'passed_one_generation'
        report['completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
        shutil.rmtree(work)
        report['disposable_outputs_removed'] = True
        save()
        print(json.dumps({'status': report['status'], 'evidence': str(evidence), 'oracle': report['oracle']}))
    except Exception as error:
        report.update(status='failed_preserved', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    main()
