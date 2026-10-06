#!/usr/bin/env python3
"""Preregister and run serial bounded headless native soaks from a passing frozen matrix.

The native child preserves registry and Bytes state throughout each cohort.
Periodic real application replays run while that child is suspended. Timings are
resource accounting under shared host load, never performance measurements.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--label', default='soak')
    parser.add_argument('--seconds', type=int, default=900)
    args = parser.parse_args()
    matrix_path = args.matrix.resolve()
    matrix = json.loads(matrix_path.read_text())
    assert matrix['status'] == 'passed' and not matrix['failures']
    assert matrix['sources_unchanged']
    assert args.seconds >= 5 and args.seconds <= 900
    spec = importlib.util.spec_from_file_location('round2_oracle', matrix_path.parent / 'sources/tests/native-research-round2.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    proposal = {
        'status': 'preregistered_not_started', 'matrix': str(matrix_path), 'matrix_sha256': digest(matrix_path),
        'cohorts': ['system-o2', 'system-sanitize'], 'target_seconds_each': args.seconds,
        'wall_limit_seconds_each': args.seconds + 30,
        'native_child_cpu_limit_seconds_each': args.seconds * 0.05 + 10,
        'native_cpu_fraction_target': 0.05,
        'native_rss_limit_bytes': 128 * 1024 * 1024,
        'sanitizer_rss_limit_bytes': 128 * 1024 * 1024,
        'aggregate_rss_limit_bytes': 384 * 1024 * 1024,
        'native_slots_limit': 256, 'gl_objects_limit': 512, 'registry_bytes_plateau': 4096,
        'registry_realloc_calls': 3, 'borrowed_vertex_bytes_max': 3840,
        'iterations_per_batch': 1024, 'minimum_batches_each': max(1, args.seconds // 2),
        'minimum_mixed_iterations_each': max(1, args.seconds // 2) * 1024,
        'application_checkpoint_seconds': 300 if args.seconds >= 300 else max(1, args.seconds // 2),
        'application_trace_events_per_replay': matrix['terrain_trace']['events'],
        'application_world_block_bytes': 65536,
        'active_worker_policy': 'One active native/application child at a time; native receives SIGSTOP during application checkpoints and resumes afterwards.',
        'sanitizers': matrix['sanitizers'],
        'pilot_peak_rss_bytes': {name: max(row['evidence']['peak_rss_bytes'] for row in matrix['contracts']
                                             if row['passed'] and row['label'].startswith(name + '-mesh-'))
                                 for name in ('system-o2', 'system-sanitize')},
        'abort': ['Wrong API/occupancy/upload/draw invariant or nonzero exit', 'Any sanitizer diagnostic',
                  'Native CPU/RSS, aggregate RSS or wall cap exceeded', 'Source hash changed',
                  'Terrain byte/top/dirty/torch/rectangle/winding/UV/sky/glow oracle failure'],
        'acceptance': ['Native duration and minimum executed batches both met', 'Three reallocations and 4096 retained registry bytes at every drained checkpoint',
                       'No live simulated GL objects after every batch drain', 'Identical independently validated application snapshot/mesh sequence hashes',
                       'Native ASan+UBSan distinct from generated ASan; no generated UBSan or LSan claim'],
        'replay_seed': 0x91a53,
        'performance_disposition': 'No timing reservation; all CPU/wall values are resource observations under external host load.',
        'duration_disposition': 'Active verified batches continue until target; pacing limits CPU rather than padding idle time.'}
    if not args.run:
        assert not args.proposal.exists()
        atomic_json(args.proposal, proposal)
        print(json.dumps(proposal, indent=2))
        return 0
    saved = json.loads(args.proposal.read_text())
    assert saved == proposal, 'preregistered proposal changed or matrix no longer matches'
    evidence = BASE / 'evidence/native-application-round2' / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    source = matrix_path.parent / 'sources'
    work = Path(matrix['work'])
    trace = matrix_path.parent / 'terrain-events.bin'
    driver_path = evidence / Path(__file__).name
    driver_path.write_bytes(Path(__file__).read_bytes())
    report = {'status': 'running', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'proposal': saved, 'proposal_sha256': digest(args.proposal),
              'driver_sha256': digest(driver_path), 'cohorts': [], 'application_replays': [],
              'host': {'loadavg_start': os.getloadavg()}, 'source_checks': [], 'rss_samples': []}
    environment = {**os.environ, **{key: value for key, value in matrix['sanitizers'].items() if key.endswith('_OPTIONS')}}
    usage_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    coordinator_start = time.process_time()

    def save():
        atomic_json(evidence / 'results.json', report)

    def check_sources():
        changed = [row['path'] for row in matrix['sources'] if digest(ROOT / row['path']) != row['sha256']]
        report['source_checks'].append({'elapsed_seconds': time.monotonic() - started, 'changed': changed})
        save()
        assert not changed, ('source changed', changed)

    def native_rows(log):
        rows = []
        for line in log.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                break  # A live writer may not yet have flushed the whole line.
            rows.append(row)
            assert row['creates'] == row['deletes'] and row['updates'] == row['uploads'] == row['draw_calls']
            assert row['active'] == row['array_live'] == row['buffer_live'] == 0
            assert row['capacity'] == 256 and row['registry_bytes'] == row['registry_peak'] == 4096
            assert row['realloc_calls'] == 3 and row['object_peak'] == 512
            assert row['peak_rss_bytes'] <= proposal['native_rss_limit_bytes']
            assert row['cpu_seconds'] <= proposal['native_child_cpu_limit_seconds_each']
        return rows

    def application_replay(name, checkpoint, child):
        if child.poll() is None:
            child.send_signal(signal.SIGSTOP)
        replay = {'configuration': name, 'checkpoint': checkpoint}
        report['application_replays'].append(replay)
        save()
        app = work / (name + '-application')
        output = work / f'{args.label}-{name}-{checkpoint}-terrain.bin'
        command = [str(app), str(trace), str(output)]
        replay['command'] = command
        try:
            run_start = time.monotonic()
            result = subprocess.run(command, cwd=source, env=environment, capture_output=True, text=True, timeout=30)
            replay.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                          child_wall_seconds=time.monotonic() - run_start)
            assert result.returncode == 0 and result.stdout == str(matrix['terrain_trace']['events']) + '\n' and not result.stderr
            replay['oracle'] = oracle.terrain_check(output, oracle.make_events())
            expected = next(row['evidence'] for row in matrix['contracts'] if row['label'] == name + '-terrain')
            assert replay['oracle'] == expected
            replay['passed'] = True
        except Exception as error:
            replay.update(passed=False, error=repr(error))
            raise
        finally:
            save()
            if child.poll() is None:
                child.send_signal(signal.SIGCONT)

    started = time.monotonic()
    save()
    child = None
    try:
        for name in proposal['cohorts']:
            check_sources()
            native = Path(matrix['binaries'][name])
            log, error = evidence / (name + '.ndjson'), evidence / (name + '.stderr')
            command = [str(native), 'mesh', str(proposal['replay_seed']), str(proposal['iterations_per_batch']), str(args.seconds)]
            row = {'configuration': name, 'command': command, 'binary_sha256': digest(native), 'checkpoints': []}
            report['cohorts'].append(row)
            save()
            with log.open('w') as stdout, error.open('w') as stderr:
                begin = time.monotonic()
                child = subprocess.Popen(command, cwd=source, env=environment, stdout=stdout, stderr=stderr)
                row['pid'] = child.pid
                application_replay(name, 0, child)
                next_application = proposal['application_checkpoint_seconds']
                next_source = 60
                while child.poll() is None:
                    elapsed = time.monotonic() - begin
                    assert elapsed <= proposal['wall_limit_seconds_each'], ('wall cap', name, elapsed)
                    rows = native_rows(log)
                    if rows:
                        row['latest'] = rows[-1]
                    assert not error.stat().st_size, ('native stderr', error.read_text())
                    # Sample native plus coordinator resident memory. Application
                    # checkpoints are serial; their pilot covers the same bounded trace.
                    sample = subprocess.run(['ps', '-o', 'rss=', '-p', f'{child.pid},{os.getpid()}'], capture_output=True, text=True, check=True)
                    rss = [int(value) * 1024 for value in sample.stdout.split()]
                    if rss:
                        assert sum(rss) <= proposal['aggregate_rss_limit_bytes'], ('aggregate RSS', rss)
                        row['sampled_aggregate_rss_peak_bytes'] = max(row.get('sampled_aggregate_rss_peak_bytes', 0), sum(rss))
                    if elapsed >= next_source:
                        check_sources()
                        next_source += 60
                    if elapsed >= next_application and elapsed < args.seconds - 5:
                        application_replay(name, int(next_application), child)
                        next_application += proposal['application_checkpoint_seconds']
                    save()
                    time.sleep(1)
                row['returncode'] = child.wait()
            assert row['returncode'] == 0 and not error.stat().st_size
            rows = native_rows(log)
            assert rows
            final = rows[-1]
            row.update(final=final, checkpoint_rows=len(rows), log_sha256=digest(log),
                       actual_mixed_iterations=final['batches'] * proposal['iterations_per_batch'],
                       actual_mesh_api_calls=sum(final[key] for key in ('creates', 'deletes', 'updates', 'draw_calls')))
            assert final['wall_seconds'] >= args.seconds and final['wall_seconds'] <= proposal['wall_limit_seconds_each']
            assert final['batches'] >= proposal['minimum_batches_each']
            assert row['actual_mixed_iterations'] >= proposal['minimum_mixed_iterations_each']
            application_replay(name, args.seconds, child)
            check_sources()
            row['passed'] = True
            save()
        report.update(status='passed', completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        usage_end = resource.getrusage(resource.RUSAGE_CHILDREN)
        report['resource_accounting'] = {'child_cpu_seconds': usage_end.ru_utime + usage_end.ru_stime - usage_start.ru_utime - usage_start.ru_stime,
                                         'coordinator_cpu_seconds': time.process_time() - coordinator_start,
                                         'wall_seconds': time.monotonic() - started}
        report['host']['loadavg_end'] = os.getloadavg()
        save()
        print(json.dumps({'status': report['status'], 'results': str(evidence / 'results.json')}, indent=2))
        return 0
    except Exception as error:
        if child and child.poll() is None:
            child.send_signal(signal.SIGCONT)
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        report.update(status='failed', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    sys.exit(main())
