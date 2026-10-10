#!/usr/bin/env python3
"""Freeze, transform, build, and serially run a synthetic scheduler pilot."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone

from variants import POLICIES, transform

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values, fraction):
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def validate(data, rows, policy, shape, nodes, seed, mode, budget):
    expected = dict(shape=shape, nodes=nodes, seed=seed, mode=mode,
                    checksum=nodes if shape == 'chain' else nodes * (nodes - 1) // 2)
    for key, value in expected.items():
        if data.get(key) != value:
            raise ValueError(f'{key}: expected {value}, got {data.get(key)}')
    if mode == 'diagnostic' and (data['final_bytes'] != 0 or data['prepared_bytes'] <= 0):
        raise ValueError('missing complete-reclamation accounting')
    if mode != 'diagnostic' and (data['final_bytes'] != -1 or data['prepared_bytes'] != -1):
        raise ValueError('timing build unexpectedly contains accounting')
    if mode == 'batch':
        if rows or data['samples'] != 0 or data['initial_ns'] != 0:
            raise ValueError('batch build must not claim operation samples')
        return {}
    if len(rows) != data['samples'] or len(rows) != data['polls'] + 1:
        raise ValueError('incomplete trace')
    if [int(r['sample']) for r in rows] != list(range(len(rows))):
        raise ValueError('sample sequence broken')
    if int(rows[-1]['pending']) != 0:
        raise ValueError('undrained retirement')
    if policy == 'eager' and data['polls'] != 0:
        raise ValueError('eager baseline unexpectedly polled')
    for i, row in enumerate(rows):
        if row['kind'] != ('poll' if i else 'retire'):
            raise ValueError('incorrect event classification')
        if policy != 'eager' and (i or mode == 'diagnostic'):
            if not 0 <= int(row['work']) <= budget or (i and int(row['work']) == 0):
                raise ValueError('cleanup work budget violated')
    if mode == 'diagnostic':
        if any(int(r['ns']) != 0 for r in rows):
            raise ValueError('diagnostic run cannot claim timing measurements')
        if sum(int(r['work']) for r in rows) != data['diagnostic_total_work']:
            raise ValueError('work accounting does not match trace')
        retained = [int(r['managed_bytes']) - int(rows[-1]['managed_bytes']) for r in rows]
        if any(a < b for a, b in zip(retained, retained[1:])) or min(retained) < 0:
            raise ValueError('retirement-only requested bytes increased')
        return {'post_retire_dead_managed_bytes': retained[0],
                'final_live_managed_bytes': int(rows[-1]['managed_bytes'])}
    polls = [int(r['ns']) for r in rows[1:]]
    if int(rows[0]['ns']) != data['initial_ns']:
        raise ValueError('initial timing differs from raw trace')
    return {'poll_p50_ns': percentile(polls, .5), 'poll_p99_ns': percentile(polls, .99),
            'poll_max_ns': max(polls, default=None), 'poll_sample_count': len(polls)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--mode', choices=['diagnostic', 'sampled', 'batch'], default='diagnostic')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--nodes', type=int, nargs='+', default=[2048])
    parser.add_argument('--budgets', type=int, nargs='+', default=[1, 32, 128])
    parser.add_argument('--seeds', type=int, nargs='+', default=[271828, 314159, 161803])
    parser.add_argument('--policies', choices=POLICIES, nargs='+', default=list(POLICIES))
    parser.add_argument('--shapes', choices=['chain', 'wide', 'dag', 'frames'], nargs='+',
                        default=['chain', 'wide', 'dag', 'frames'])
    parser.add_argument('--order-seed', type=int, default=20260920)
    args = parser.parse_args()
    if args.sanitize and args.mode != 'diagnostic':
        parser.error('sanitizers require diagnostic mode')
    for values, low, high in [(args.nodes, 2, 1000000), (args.budgets, 1, 1024),
                              (args.seeds, 1, 1000000000)]:
        if len(values) != len(set(values)) or not all(low <= x <= high for x in values):
            parser.error('numeric lists must contain unique values in the supported range')
    if len(set(args.policies)) != len(args.policies) or len(set(args.shapes)) != len(args.shapes):
        parser.error('policies and shapes must be unique')
    out = args.output.resolve()
    if out == ROOT or ROOT.is_relative_to(out) or out.is_relative_to(HERE) or out.is_relative_to(ROOT / 'runtime'):
        parser.error('output must be a fresh evidence directory outside research sources and runtime')
    out.mkdir(parents=True, exist_ok=False)
    snapshot = out / 'snapshot'
    sources = [*sorted((ROOT / 'runtime').glob('*.[ch]')),
               *sorted(HERE.glob('*.py')), *sorted(HERE.glob('*.c')), *sorted(HERE.glob('*.md'))]
    for source in sources:
        dest = snapshot / source.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
    manifest = {
        'schema': 1, 'status': 'running', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'invocation': sys.argv, 'host': platform.platform(), 'machine': platform.machine(),
        'python': sys.version, 'mode': args.mode, 'sanitize': args.sanitize,
        'order_seed': args.order_seed, 'commands': [], 'runs': [], 'builds': [],
        'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in sources},
        'limitations': [
            'Synthetic direct C-runtime retirement; no generated Minyar or application replay.',
            'Single system allocator; eager also changes ownership-frame representation.',
            'Finite drains do not establish fairness under sustained arrivals or backlog stability.',
            'No controlled cold-cache sweep, affinity, page locking, or OS isolation.',
            'Sampled polls are dependent; each process supplies one root/frame retirement.',
            'Accounting requested managed bytes excludes owner storage and allocator retention.',
            'Sampled complete-drain time includes per-poll timing and trace stores.',
            'Only current versus fair-unit isolates batching; FIFO/LIFO also change traversal order.',
            'Abstract work budgets are not elapsed-time bounds.'
        ]}

    def save():
        temporary = out / 'results.json.tmp'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(out / 'results.json')

    def execute(label, command, cwd=ROOT):
        entry = {'label': label, 'argv': [str(x) for x in command], 'cwd': str(cwd)}
        env = dict(os.environ)
        if args.sanitize:
            env.update(ASAN_OPTIONS='detect_leaks=0:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        stdout = stderr = b''
        try:
            p = subprocess.run(entry['argv'], cwd=cwd, env=env, capture_output=True, timeout=120)
            stdout, stderr = p.stdout, p.stderr
            entry.update(returncode=p.returncode, status='passed' if p.returncode == 0 else 'failed')
        except subprocess.TimeoutExpired as e:
            stdout, stderr = e.stdout or b'', e.stderr or b''
            entry.update(returncode=None, status='timeout')
        except OSError as e:
            entry.update(returncode=None, status='launch_error', error=str(e))
        (out / f'{label}.stdout').write_bytes(stdout)
        (out / f'{label}.stderr').write_bytes(stderr)
        manifest['commands'].append(entry); save()
        if entry['status'] != 'passed':
            raise RuntimeError(f'{label}: {entry["status"]}; see retained logs in {out}')
        return stdout.decode()

    save()
    print(out, flush=True)
    try:
        manifest['git_revision'] = execute('git-revision', ['git', 'rev-parse', 'HEAD']).strip()
        execute('git-status', ['git', 'status', '--short'])
        execute('git-diff', ['git', 'diff', '--binary'])
        manifest['compiler_version'] = execute('compiler-version', [args.cc, '--version'])
        original = (snapshot / 'runtime/minyar_bounded_rc.h').read_text()
        configurations = []
        for policy in args.policies:
            variant = out / 'variants' / policy
            for source in (snapshot / 'runtime').glob('*'):
                destination = variant / 'runtime' / source.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
            header = variant / 'runtime/minyar_bounded_rc.h'
            header.write_text(transform(original, policy))
            fixture = variant / 'research/reclamation/probe.c'
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_bytes((snapshot / 'research/reclamation/probe.c').read_bytes())
            for budget in ([0] if policy == 'eager' else args.budgets):
                label = f'{policy}-k{budget}'
                binary = variant / label
                flags = ['-O2', '-g', '-std=c11']
                if policy != 'eager':
                    flags += ['-DMINYAR_SYSTEM_HEAP=1', f'-DMINYAR_RC_POLL_BUDGET={budget}']
                if args.mode == 'diagnostic':
                    flags += ['-DRESEARCH_DIAGNOSTIC=1']
                if args.sanitize:
                    flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                execute(label + '-build', [args.cc, *flags, fixture, '-o', binary])
                manifest['builds'].append({'policy': policy, 'budget': budget, 'binary': str(binary),
                    'binary_sha256': digest(binary), 'scheduler_sha256': digest(header), 'flags': flags})
                configurations.append((policy, budget, binary))
        jobs = [(p, k, binary, shape, n, seed) for p, k, binary in configurations
                for shape in args.shapes for n in args.nodes for seed in args.seeds]
        random.Random(args.order_seed).shuffle(jobs)
        manifest['planned_runs'] = len(jobs); save()
        for index, (policy, budget, binary, shape, n, seed) in enumerate(jobs):
            label = f'run-{index:04d}-{policy}-k{budget}-{shape}-n{n}-s{seed}'
            csv_path = out / f'{label}.csv'
            data = json.loads(execute(label, [binary, shape, n, seed, args.mode, csv_path]))
            rows = []
            if args.mode != 'batch':
                with csv_path.open() as f:
                    rows = list(csv.DictReader(f))
            metrics = validate(data, rows, policy, shape, n, seed, args.mode, budget)
            manifest['runs'].append({'label': label, 'policy': policy, 'budget': budget,
                                     'summary': data, 'metrics': metrics,
                                     'trace_sha256': digest(csv_path) if rows else None})
            save()
        manifest['status'] = 'passed'
        print(f'{len(jobs)} runs passed ({args.mode}, sanitizer={args.sanitize})', flush=True)
    except Exception as e:
        manifest.update(status='failed', error=str(e))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
