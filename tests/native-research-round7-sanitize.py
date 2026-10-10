#!/usr/bin/env python3
"""One explicitly released sanitizer generation from frozen first-O2 artifacts."""
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
FIRST = BASE / 'first-o2'
PROPOSAL = ROOT / 'research/2026-10-memory/native-application-round7-sanitizer-proposal.json'
sys.dont_write_bytecode = True


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--release-file', required=True, type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z0-9-]+', args.label)
    assert args.release_file.is_file() and args.release_file.read_text().strip()
    evidence = BASE / args.label
    evidence.mkdir(exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix='minyar-native-round7-sanitize-'))
    proposal = json.loads(PROPOSAL.read_text())
    first = json.loads((FIRST / 'results.json').read_text())
    report = {'status': 'preparing_after_explicit_release', 'invocation': sys.argv,
              'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'commands': [], 'work': str(work), 'limits': proposal['limits'],
              'optimization': '-O1 only; matching frozen native runtime-O1',
              'sanitizer_environment': proposal['sanitizer_environment'],
              'quarantine': proposal['quarantine'], 'native_generation_invocations': 0, 'generation_completion_observed': False,
              'scope': 'One additional generation; independent mathematical oracles and comparative O2 equality remain distinct.'}
    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    def run(label, command, native=False):
        argv = ['/usr/bin/time', '-l', *map(str, command)]
        outpath, errpath = evidence / (label + '.stdout'), evidence / (label + '.stderr')
        limit = report['limits']['native_sampled_rss_bytes' if native else 'compile_sampled_rss_bytes']
        samples, failure, start = [], None, time.monotonic()
        with outpath.open('w') as stdout, errpath.open('w') as stderr:
            process = subprocess.Popen(argv, cwd=work, env={**os.environ, **report['sanitizer_environment']},
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            while process.poll() is None:
                output = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], text=True, capture_output=True, timeout=2)
                rows = [tuple(map(int, line.split())) for line in output.stdout.splitlines() if line.strip()]
                children = {process.pid}
                while True:
                    following = children | {pid for pid, parent, rss in rows if parent in children}
                    if following == children:
                        break
                    children = following
                resident = [rss * 1024 for pid, parent, rss in rows if pid in children]
                total = sum(resident)
                samples.append({'wall_seconds': time.monotonic() - start, 'process_group_rss_bytes': total,
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
        stderr = errpath.read_text()
        peak_match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', stderr, re.M)
        timing_match = re.search(r'([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys', stderr)
        peak = int(peak_match[1]) if peak_match else None
        row = {'label': label, 'command': argv, 'cwd': str(work), 'returncode': process.returncode,
               'supervised_wall_seconds': time.monotonic() - start,
               'sampled_process_group_peak_rss_bytes': max((s['process_group_rss_bytes'] for s in samples), default=0),
               'darwin_time_child_peak_rss_bytes': peak, 'limit_failure': failure, 'native': native,
               'stdout_path': outpath.name, 'stderr_path': errpath.name,
               'darwin_time_real_user_sys_seconds': list(map(float, timing_match.groups())) if timing_match else None}
        report['commands'].append(row)
        (evidence / (label + '-rss-samples.json')).write_text(json.dumps(samples, indent=2) + '\n')
        save()
        assert not failure and peak is not None and peak <= limit and row['supervised_wall_seconds'] <= 30, row
        assert process.returncode == 0, row
        # Exact expected time rows are indented; all unindented diagnostics are unexpected.
        assert not [line for line in stderr.splitlines() if line and not line[0].isspace()], stderr
        return row
    try:
        shutil.copyfile(args.release_file, evidence / 'explicit-core-cpu-release.txt')
        shutil.copyfile(BASE / 'authorization-sanitizer-hold.json', evidence / 'authorization.json')
        shutil.copyfile(PROPOSAL, evidence / 'approved-proposal.json')
        shutil.copyfile(Path(__file__), evidence / 'native-research-round7-sanitize.py')
        manifest = json.loads((BASE / 'sanitizer-proposal/first-o2-entry-hashes.json').read_text())
        assert all(digest(Path(name)) == value for name, value in manifest.items())
        (evidence / 'first-o2-entry-hashes.json').write_text(json.dumps(manifest, indent=2) + '\n')
        assert digest(ROOT / 'build/minyarc') == first['compiler_sha256']
        runtime = Path(proposal['runtime']['path'])
        assert digest(runtime) == proposal['runtime']['sha256']
        for row in first['runtime']['verified_dependencies']:
            assert digest(ROOT / row['path']) == row['sha256'], row
        report['runtime'] = proposal['runtime']
        report['compiler_sha256'] = first['compiler_sha256']
        report['source_hashes'] = first['sources']
        llvm = work / 'application-asan.ll'
        shutil.copyfile(BASE / 'sanitizer-proposal/application-asan.ll', llvm)
        coverage = proposal['generated_address_sanitizer_preparation']
        assert digest(llvm) == coverage['prepared_llvm_sha256']
        headers = re.findall(r'^define [^\n]*', llvm.read_text(), re.M)
        attributed = [h for h in headers if re.search(r'\bsanitize_address\b', h[h.rfind(')') + 1:])]
        assert len(headers) == len(attributed) == 41
        report['generated_address_sanitizer'] = {'definitions': len(headers),
                                                'annotated_definitions': len(attributed), 'sha256': digest(llvm)}
        report['generated_ubsan'] = False
        shutil.copyfile(llvm, evidence / llvm.name)
        expected_path = BASE / 'sanitizer-proposal/expected-inputs.json'
        oracle_path = BASE / 'sanitizer-proposal/native-research-round7-oracle.py'
        assert digest(expected_path) == proposal['oracles']['expected_math_sha256']
        assert digest(oracle_path) == proposal['oracles']['frozen_independent_oracle_sha256']
        shutil.copyfile(expected_path, evidence / 'expected-inputs.json')
        shutil.copyfile(oracle_path, evidence / 'native-research-round7-oracle.py')
        expected = json.loads(expected_path.read_text())
        spec = importlib.util.spec_from_file_location('round7_frozen_oracle', oracle_path)
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        binary = work / 'generation-sanitize'
        save()
        run('link-sanitize', ['clang', '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                             '-Wno-override-module', llvm, runtime, '-lm', '-o', binary])
        report['binary_sha256'] = digest(binary)
        report['native_start_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['native_generation_invocations'] = 1
        save()
        run('native-sanitize', [binary], native=True)
        assert (evidence / 'native-sanitize.stdout').read_text() == 'round7 generation and lighting returned\n'
        report['generation_completion_observed'] = True
        report['output_files'] = [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p)}
                                  for p in sorted(work.glob('*.bin'))]
        report['oracle'] = oracle.validate(work, expected)
        save()
        reference_hash = proposal['oracles']['expected_cross_configuration_world_sha256']
        assert report['oracle']['world_sha256'] == reference_hash, 'Comparative-O2 world hash mismatch'
        for name in ['tops.bin', 'dirty.bin', 'state.bin']:
            assert (work / name).read_bytes() == (FIRST / name).read_bytes(), ('Comparative-O2 metadata', name)
            shutil.copyfile(work / name, evidence / name)
        report['comparative_o2_equality'] = {'world_sha256': reference_hash,
                                            'metadata_equal': ['tops.bin', 'dirty.bin', 'state.bin'],
                                            'scope': 'Equality against observed first-O2 control; separate from independent sampled math.'}
        observed = [{'x': x['x'], 'z': x['z'], 'column_hex': x['column_hex']}
                    for x in expected['selected_columns']]
        # Actual equality was checked by oracle.validate; preserve the identical
        # observed selected rows from the already checked first control.
        assert observed == json.loads((FIRST / 'observed-selected-columns.json').read_text())
        shutil.copyfile(FIRST / 'observed-selected-columns.json', evidence / 'observed-selected-columns.json')
        assert all(digest(Path(name)) == value for name, value in manifest.items())
        assert digest(runtime) == proposal['runtime']['sha256']
        assert digest(ROOT / 'build/minyarc') == first['compiler_sha256']
        report['first_o2_evidence_unchanged_files'] = len(manifest)
        report['status'] = 'passed_one_sanitizer_generation'
        report['completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
        shutil.rmtree(work)
        report['disposable_outputs_removed'] = True
        save()
        print(json.dumps({'status': report['status'], 'oracle': report['oracle'],
                          'comparison': report['comparative_o2_equality'], 'evidence': str(evidence)}))
    except Exception as error:
        report.update(status='failed_preserved_no_retry', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    main()
