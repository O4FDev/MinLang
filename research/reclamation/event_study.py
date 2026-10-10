#!/usr/bin/env python3
"""Compiled Minyar under prescribed arrivals; independent output/memory checks."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from run_study import percentile
from variants import transform

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def oracle(count, width, seed):
    snapshots = [[(s * 97 + i * 13) % 1000003 for i in range(width)] for s in range(4)]
    values = list(range(257))
    answers = []
    for sequence in range(count):
        state = (seed * 17 + sequence * 23) % 1000003
        slot = (sequence // 256) % 4
        if sequence % 256 == 0:
            generation = sequence + 4
            snapshots[slot] = [old if (i + generation) % 4 == 0 else (generation * 97 + i * 13) % 1000003
                               for i, old in enumerate(snapshots[slot])]
        index = state % 257
        values[index] = (values[index] + state) % 1000003
        price = snapshots[slot][state % width]
        lengths = [len(str(40000 + state + j)) for j in range(8)]
        owned = sum(lengths[:4]) + lengths[0] - 1 + sum(lengths)
        answers.append((values[index] + 2 * price + len(str(40000 + price)) + owned) % 1000003)
    return answers


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open() as f:
        return [{k: v if k == 'kind' else int(v) for k, v in row.items()} for row in csv.DictReader(f)]


def analyze(summary, rows, recovery, expected, spacing, burst, diagnostic, ownership, width, seed):
    count = len(expected)
    for key, value in dict(events=count, width=width, seed=seed, spacing_ns=spacing, burst=burst).items():
        if summary.get(key) != value:
            raise ValueError(f'incorrect summary field {key}')
    if len(rows) != count or len(recovery) != 4:
        raise ValueError('missing event/recovery records')
    for i, row in enumerate(rows):
        cycle, j = divmod(i, count // 4)
        arrival = cycle * ((count // 4) * spacing + (10000000 if spacing else 0)) + (j // burst) * burst * spacing
        if (row['event'], row['cycle'], row['result'], row['arrival_ns'], row['kind']) != (
                i, cycle, expected[i], arrival, 'rebuild' if i % 256 == 0 else 'ordinary'):
            raise ValueError(f'event oracle/schedule mismatch at {i}')
        if diagnostic:
            if any(row[x] != 0 for x in ['start_ns', 'service_ns', 'response_ns']):
                raise ValueError('diagnostic trace claimed timing')
            if not 0 <= row['live_bytes'] <= row['managed_bytes'] or row['owner_bytes'] < 0:
                raise ValueError('invalid live/retained accounting')
        else:
            if spacing and row['start_ns'] < arrival:
                raise ValueError('event processed before its prescribed arrival')
            if row['service_ns'] < 0 or row['response_ns'] != (
                    row['start_ns'] + row['service_ns'] - arrival if spacing else row['service_ns']):
                raise ValueError('response identity failed')
            if any(row[x] != -1 for x in ['managed_bytes', 'live_bytes', 'owner_bytes']):
                raise ValueError('timing build contains diagnostic measurements')
            if i and row['start_ns'] < rows[i - 1]['start_ns'] + rows[i - 1]['service_ns']:
                raise ValueError('serialized event intervals overlap')
        if row['pending'] < 0:
            raise ValueError('negative pending task count')
    if summary['total_service_ns'] != sum(r['service_ns'] for r in rows):
        raise ValueError('service total differs from trace')
    if diagnostic:
        if summary['final_bytes'] != 0 or (summary['stack_admissions'] > 0) != (ownership == 'budget'):
            raise ValueError('final reclamation/actual stack admission failed')
    elif summary['final_bytes'] != -1 or summary['stack_admissions'] != -1:
        raise ValueError('timing build claimed unavailable counters')
    if not diagnostic and summary['lifecycle_ns'] < rows[-1]['start_ns'] + rows[-1]['service_ns']:
        raise ValueError('lifecycle excludes completed events')
    if summary['pending_before_teardown'] != recovery[-1]['pending_after']:
        raise ValueError('teardown debt differs from recovery trace')
    for cycle, r in enumerate(recovery):
        if r['cycle'] != cycle or r['pending_before'] != rows[(cycle + 1) * (count // 4) - 1]['pending']:
            raise ValueError('recovery boundary mismatch')
        if diagnostic and (r['pending_after'] or r['managed_bytes'] != r['live_bytes']):
            raise ValueError('diagnostic drain retained unreachable objects')
        if r['pending_after'] < 0 or r['duration_ns'] < 0 or r['overrun_ns'] < 0:
            raise ValueError('invalid recovery accounting')
        if not diagnostic and spacing:
            boundary = (cycle + 1) * (count // 4) * spacing + cycle * 10000000
            if r['start_ns'] < boundary or r['overrun_ns'] != max(0, r['start_ns'] + r['duration_ns'] - boundary - 10000000):
                raise ValueError('quiet window was extended or overrun misreported')
    result = {'recovery_failed_cycles': sum(r['pending_after'] != 0 or r['overrun_ns'] > 0 for r in recovery),
              'max_pending': max(r['pending'] for r in rows),
              'cycle_end_pending': [r['pending_before'] for r in recovery],
              'max_recovery_ns': max(r['duration_ns'] for r in recovery)}
    for kind in ['ordinary', 'rebuild']:
        subset = [r for r in rows if r['kind'] == kind]
        result[kind] = {'count': len(subset)}
        if not diagnostic:
            for metric in ['service_ns', 'response_ns']:
                values = [r[metric] for r in subset]
                result[kind][metric] = {'p50': percentile(values, .5), 'p99': percentile(values, .99),
                                        'max': max(values), 'mean': sum(values) / len(values)}
    if diagnostic:
        result.update(max_boundary_dead_managed_bytes=max(r['managed_bytes'] - r['live_bytes'] for r in rows),
                      max_boundary_owner_bytes=max(r['owner_bytes'] for r in rows),
                      max_boundary_managed_plus_owner_bytes=max(r['managed_bytes'] + r['owner_bytes'] for r in rows))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    p.add_argument('--cc', default='clang')
    p.add_argument('--mode', choices=['diagnostic', 'timing'], default='diagnostic')
    p.add_argument('--sanitize', action='store_true')
    p.add_argument('--events', type=int)
    p.add_argument('--width', type=int)
    p.add_argument('--seeds', type=int, nargs='+', default=[271828, 314159, 161803])
    p.add_argument('--budgets', type=int, nargs='+', default=[1, 8, 32])
    p.add_argument('--spacings', type=int, nargs='+', default=[10000, 50000])
    p.add_argument('--bursts', type=int, nargs='+', default=[1, 16])
    p.add_argument('--policies', nargs='+', choices=['current', 'fair-unit', 'fifo', 'lifo', 'eager'],
                   default=['current', 'fair-unit', 'fifo', 'lifo', 'eager'])
    args = p.parse_args()
    diagnostic = args.mode == 'diagnostic'
    count = args.events or (2048 if diagnostic else 8192)
    width = args.width or (128 if diagnostic else 1024)
    if args.sanitize and not diagnostic:
        p.error('sanitizers require diagnostic mode')
    if not 128 <= count <= 1000000 or count % 64 or not 4 <= width <= 8192:
        p.error('events must be 128..1000000 and divisible by 64; width must be 4..8192')
    for values, low, high in [(args.budgets, 1, 1024), (args.seeds, 1, 1000000000), (args.spacings, 0, 1000000), (args.bursts, 1, 16)]:
        if len(set(values)) != len(values) or not all(low <= x <= high for x in values):
            p.error('invalid or duplicated numeric parameter')
    if any((count // 4) % b for b in args.bursts):
        p.error('burst must divide events per cycle')
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    snapshot = out / 'snapshot'
    sources = [*sorted((ROOT / 'runtime').glob('*.[ch]')), ROOT / 'compiler/compiler.min',
               *sorted(HERE.glob('*.py')), *sorted(HERE.glob('*.c')), *sorted(HERE.glob('*.min')),
               HERE / 'event-protocol.md', HERE / 'formal-model.md']
    for source in sources:
        dest = snapshot / source.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
    compiler = snapshot / 'minyarc'; shutil.copy2(args.compiler.resolve(), compiler)
    manifest = dict(schema=1, status='running', mode=args.mode, sanitize=args.sanitize,
                    created_utc=datetime.now(timezone.utc).isoformat(), invocation=sys.argv,
                    host=platform.platform(), machine=platform.machine(), python=sys.version,
                    source_sha256={str(s.relative_to(ROOT)): sha(snapshot / s.relative_to(ROOT)) for s in sources},
                    compiler_sha256=sha(compiler), commands=[], builds=[], runs=[], order_seed=20260921,
                    limitations=['Application-shaped synthetic workload, not production traffic.',
                                 'No LTO, core isolation, pinning, or locked memory.',
                                 'Diagnostic boundary peaks exclude intra-event peaks and libc/RSS overhead.',
                                 'Stack lowering includes its required noinline attribute; this is a policy comparison.',
                                 'Three correlated workload runs do not certify rare-tail or hard-real-time guarantees.',
                                 'Quiet windows are deliberate service opportunities; finite recovery is not infinite stability.'])

    def save():
        temp = out / 'results.json.tmp'; temp.write_text(json.dumps(manifest, indent=2) + '\n')
        temp.replace(out / 'results.json')

    def run(label, command):
        entry = dict(label=label, argv=list(map(str, command)), cwd=str(ROOT))
        stdout = stderr = b''
        try:
            process = subprocess.run(entry['argv'], cwd=ROOT, capture_output=True, timeout=180,
                                     env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                                              UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
            stdout, stderr = process.stdout, process.stderr
            entry.update(returncode=process.returncode, status='passed' if process.returncode == 0 else 'failed')
        except subprocess.TimeoutExpired as e:
            stdout, stderr = e.stdout or b'', e.stderr or b''
            entry.update(returncode=None, status='timeout')
        except OSError as e:
            entry.update(returncode=None, status='launch_error', error=str(e))
        (out / (label + '.stdout')).write_bytes(stdout); (out / (label + '.stderr')).write_bytes(stderr)
        manifest['commands'].append(entry); save()
        if entry['status'] != 'passed':
            raise RuntimeError(f'{label} {entry["status"]}; see {out}')
        return stdout.decode()

    print(out, flush=True); save()
    try:
        manifest['git_revision'] = run('git-revision', ['git', 'rev-parse', 'HEAD']).strip()
        run('git-status', ['git', 'status', '--short']); run('git-diff', ['git', 'diff', '--binary'])
        manifest['cc_version'] = run('cc-version', [args.cc, '--version'])
        if platform.system() == 'Darwin':
            manifest['hardware'] = run('host-hardware', ['sysctl', 'machdep.cpu.brand_string',
                                                         'hw.memsize', 'hw.logicalcpu']).strip()
        irs = {}
        for policy in [0, *[b for b in args.budgets if b > 1 and 'current' in args.policies]]:
            ir = out / f'ownership-{policy}.ll'
            run(f'frontend-{policy}', [compiler, snapshot / 'research/reclamation/event_workload.min', ir,
                                      *(['--bounded-owners', str(policy)] if policy else [])])
            raw = ir.read_text(); ir.with_suffix('.raw.ll').write_text(raw)
            expected = {'eventOwners5': policy >= 6, 'eventOwners8': policy >= 9}
            for name, stack in expected.items():
                body = re.search(r'^define [^\n]* @' + name + r'\(.*?^}', raw, re.M | re.S)
                if body is None or ('call void @minyar_rc_enter_stack_v1(' in body[0]) != stack:
                    raise ValueError(f'wrong compiler ownership admission: {name}, K{policy}')
            raw, renamed = re.subn(r'(@)main(\()', r'\1eventFixtureMain\2', raw)
            if renamed != 1:
                raise ValueError('expected one generated entry point')
            ir.write_text(raw); irs[policy] = ir
        configurations = [(policy, budget, 'heap') for policy in args.policies
                          for budget in ([0] if policy == 'eager' else args.budgets)]
        if 'current' in args.policies:
            configurations += [('current', k, 'budget') for k in args.budgets if k >= 6]
        original = (snapshot / 'runtime/minyar_bounded_rc.h').read_text()
        for policy, budget, ownership in configurations:
            label = f'{policy}-k{budget}-{ownership}'; variant = out / label
            shutil.copytree(snapshot / 'runtime', variant / 'runtime')
            header = variant / 'runtime/minyar_bounded_rc.h'; header.write_text(transform(original, policy))
            fixture = variant / 'research/reclamation/event_driver.c'; fixture.parent.mkdir(parents=True)
            fixture.write_bytes((snapshot / 'research/reclamation/event_driver.c').read_bytes())
            flags = ['-O2', '-g', '-Wno-override-module', '-DMINYAR_INTEGER_TEXT_CACHE_LIMIT=0']
            if policy != 'eager': flags += ['-DMINYAR_SYSTEM_HEAP=1', f'-DMINYAR_RC_POLL_BUDGET={budget}']
            if diagnostic: flags += ['-DEVENT_DIAGNOSTIC=1']
            if args.sanitize: flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            llvm = irs[budget if ownership == 'budget' else 0]
            binary = variant / 'event-loop'
            run(label + '-build', [args.cc, *flags, llvm, fixture, '-o', binary])
            manifest['builds'].append(dict(label=label, policy=policy, budget=budget, ownership=ownership,
                binary=str(binary), binary_sha256=sha(binary), llvm=str(llvm), llvm_sha256=sha(llvm),
                scheduler_sha256=sha(header), flags=flags))
        expected_by_seed = {}
        for seed in args.seeds:
            expected_by_seed[seed] = oracle(count, width, seed)
            (out / f'oracle-{seed}.txt').write_text(''.join(f'{v}\n' for v in expected_by_seed[seed]))
        arrivals = [(0, 1)] if diagnostic else [(s, b) for s in args.spacings for b in args.bursts if s or b == 1]
        jobs = [(build, seed, spacing, burst) for build in manifest['builds'] for seed in args.seeds for spacing, burst in arrivals]
        random.Random(manifest['order_seed']).shuffle(jobs)
        manifest['planned_runs'] = len(jobs); save()
        for index, (build, seed, spacing, burst) in enumerate(jobs):
            label = f'run-{index:04d}-{build["label"]}-s{seed}-ns{spacing}-b{burst}'
            events, recovery = out / (label + '.events.csv'), out / (label + '.recovery.csv')
            summary = json.loads(run(label, [build['binary'], count, width, seed, spacing, burst,
                                             out / f'oracle-{seed}.txt', events, recovery]))
            metrics = analyze(summary, read_csv(events), read_csv(recovery), expected_by_seed[seed], spacing,
                              burst, diagnostic, build['ownership'], width, seed)
            manifest['runs'].append(dict(label=label, configuration=build['label'], summary=summary, metrics=metrics,
                                         events_sha256=sha(events), recovery_sha256=sha(recovery)))
            save()
        manifest['status'] = 'passed'
        print(f'{len(jobs)} {args.mode} runs validated, sanitize={args.sanitize}', flush=True)
    except Exception as e:
        manifest.update(status='failed', error=str(e)); raise
    finally:
        save()


if __name__ == '__main__':
    main()
