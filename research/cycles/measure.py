#!/usr/bin/env python3
"""Reproduce instruction measurements on macOS, using a local baseline revision.
No checkout, external worktree, or installed tools are changed.
"""
import argparse
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import platform
import re
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = '3bd7f74af2069e82e5be19546881d20a8457f5eb'


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], cwd=ROOT, text=True,
                          capture_output=True, check=True, timeout=240, **kwargs)


def sample(command, runs):
    rows = []
    for _ in range(runs):
        result = run(['/usr/bin/time', '-l', *command])
        row = {}
        for field, pattern in {
            'instructions': r'(\d+)\s+instructions retired',
            'peak_rss_bytes': r'(\d+)\s+maximum resident set size',
            'real_seconds': r'([\d.]+) real',
            'user_seconds': r'([\d.]+) user',
            'system_seconds': r'([\d.]+) sys',
        }.items():
            match = re.search(pattern, result.stderr)
            row[field] = float(match[1]) if match else None
        rows.append(row)
    return {'command': [str(a) for a in command], 'samples': rows,
            'median': {key: statistics.median(r[key] for r in rows)
                       for key in rows[0] if rows[0][key] is not None}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--runs', type=int, default=5)
    p.add_argument('--baseline', default=BASE)
    args = p.parse_args()
    work = ROOT / 'build/cycle-measure'
    work.mkdir(parents=True, exist_ok=True)
    base = work / 'baseline'
    (base / 'runtime').mkdir(parents=True, exist_ok=True)
    files = run(['git', 'ls-tree', '-r', '--name-only', args.baseline, 'runtime']).stdout.splitlines()
    for name in files:
        if name.endswith(('.c', '.h')) and '/' not in name[len('runtime/'):]:
            (base / name).write_text(run(['git', 'show', args.baseline + ':' + name]).stdout)
    original = base / 'compiler.min'
    original.write_text(run(['git', 'show', args.baseline + ':compiler/compiler.min']).stdout)
    compiler = ROOT / 'build/minyarc'
    old_ir = base / 'compiler.ll'
    run([compiler, original, old_ir])
    old_ir.write_text('\n'.join(line for line in old_ir.read_text().split('\n')
        if '@minyar_rc_cycle_policy(' not in line and '@minyar_rc_enable_cycles(' not in line))
    # Matching LTO/runtime attributes used by the repository compiler build.
    arena_ir = base / 'arena.ll'
    run(['clang', '-O2', '-DMINYAR_COMPILER_ARENA', '-S', '-emit-llvm',
         base / 'runtime/minyar_runtime.c', '-o', arena_ir])
    arena_ir.write_text(re.sub(r'"(?:target-cpu|target-features|tune-cpu)"="[^"]*" ?', '', arena_ir.read_text()))
    baseline_compiler = base / 'minyarc'
    run(['clang', '-O2', '-Wno-override-module', '-flto', old_ir, arena_ir, '-o', baseline_compiler])
    results = {'platform': platform.platform(), 'utc': datetime.now(timezone.utc).isoformat(),
               'compiler_source_sha256': hashlib.sha256((ROOT / 'compiler/compiler.min').read_bytes()).hexdigest(), 'baseline_revision': args.baseline,
               'current_revision': run(['git', 'rev-parse', 'HEAD']).stdout.strip(),
               'runs': args.runs, 'measurements': {}}
    measurements = results['measurements']
    for name, exe, source in (
        ('self.baseline', baseline_compiler, original),
        ('self.current.same_input', compiler, original),
        ('self.current.current_input', compiler, ROOT / 'compiler/compiler.min'),
    ):
        measurements[name] = sample([exe, source, work / 'self.ll'], args.runs)
    for version, ir, runtime in (
        ('baseline', old_ir, base / 'runtime/minyar_runtime.c'),
        ('current', ROOT / 'build/compiler-stage2.ll', ROOT / 'runtime/minyar_runtime.c'),
    ):
        runtime_ir = work / (version + '-system.ll')
        run(['clang', '-O2', '-DMINYAR_SYSTEM_HEAP=1', '-S', '-emit-llvm', runtime, '-o', runtime_ir])
        runtime_ir.write_text(re.sub(r'"(?:target-cpu|target-features|tune-cpu)"="[^"]*" ?', '', runtime_ir.read_text()))
        exe = work / (version + '-system-compiler')
        run(['clang', '-O2', '-Wno-override-module', '-flto', ir, runtime_ir, '-o', exe])
        measurements['self.system.' + version] = sample([exe, original, work / 'system-self.ll'], args.runs)
    for name, source, extra in (
        ('runtime', ROOT / 'tests/performance/runtime.min', ['2']),
        ('acyclic_chain', ROOT / 'research/cycles/acyclic.min', []),
    ):
        ir = work / (name + '.ll')
        run([compiler, source, ir])
        for version, runtime in (
            ('baseline', base / 'runtime/minyar_runtime.c'),
            ('current', ROOT / 'runtime/minyar_runtime.c'),
        ):
            run([baseline_compiler if version == 'baseline' else compiler, source, ir])
            exe = work / (name + '-' + version)
            run(['clang', '-O2', '-Wno-override-module', '-DMINYAR_SYSTEM_HEAP=1', ir, runtime, '-o', exe])
            measurements[name + '.' + version] = sample([exe, *extra], args.runs)
    for budget in (1, 32, 1024):
        ir, exe = work / 'churn.ll', work / f'churn-k{budget}'
        run([compiler, ROOT / 'tests/cycles/churn.min', ir])
        run(['clang', '-O2', '-Wno-override-module', '-DMINYAR_BOUNDED_HEAP=1',
             '-DMINYAR_BOUNDED_HEAP_BYTES=1048576', f'-DMINYAR_RC_POLL_BUDGET={budget}',
             ir, ROOT / 'runtime/minyar_runtime.c', '-o', exe])
        measurements[f'cycles.fixed.k{budget}'] = sample([exe], args.runs)
    output = ROOT / 'research/cycles/measurements.json'
    output.write_text(json.dumps(results, indent=2) + '\n')
    for key, value in measurements.items():
        print(key, value['median'], flush=True)


if __name__ == '__main__':
    main()
