#!/usr/bin/env python3
"""Measure pool reserve while cyclic garbage accumulates beside a live ring.

Use --runtime-revision a2fbb02 --heap-bytes 4194304 for the earlier collector.
The compiler and source lowering are unchanged between that revision and the
scan/service optimization. All extracted files stay inside this worktree.
"""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def run(command):
    return subprocess.run([str(x) for x in command], cwd=ROOT, text=True,
                          capture_output=True, check=True, timeout=180)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-revision')
    parser.add_argument('--heap-bytes', type=int, default=1048576)
    parser.add_argument('--iterations', type=int, default=2000000)
    parser.add_argument('--budget', type=int, default=1)
    args = parser.parse_args()
    if args.iterations < 1 or not 1 <= args.budget <= 1024:
        parser.error('positive iteration count and budget 1..1024 required')
    work = ROOT / 'build/cycles-live-reserve'
    work.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / 'runtime'
    if args.runtime_revision:
        runtime = work / 'old-runtime'
        runtime.mkdir(exist_ok=True)
        names = run(['git', 'ls-tree', '-r', '--name-only', args.runtime_revision,
                     'runtime']).stdout.splitlines()
        for name in names:
            if name.endswith(('.c', '.h')) and '/' not in name[len('runtime/'):]:
                (runtime / Path(name).name).write_text(
                    run(['git', 'show', args.runtime_revision + ':' + name]).stdout)
    source = (ROOT / 'tests/cycles/live-churn.min').read_text()
    source = source.replace('i < 100000', f'i < {args.iterations}')
    (work / 'input.min').write_text(source)
    run([ROOT / 'build/minyarc', work / 'input.min', work / 'input.ll',
         '--bounded-owners', args.budget])
    (work / 'runtime.c').write_text(
        '#define MINYAR_RC_TESTING 1\n'
        '#include ' + json.dumps(str(runtime / 'minyar_runtime.c')) + '\n'
        '#include ' + json.dumps(str(runtime / 'minyar_stack_frames.h')) + '\n'
        '__attribute__((destructor)) static void report(void) {\n'
        '  fprintf(stderr, "pool-peak=%zu remaining-objects=%zu cycle-units=%zu epochs=%zu\\n",\n'
        '    minyar_pool_high_water, rc_object_count, rc_cycle_units, rc_cycle_epochs);\n'
        '}\n')
    run(['clang', '-O2', '-Wno-override-module', '-DMINYAR_BOUNDED_HEAP=1',
         f'-DMINYAR_BOUNDED_HEAP_BYTES={args.heap_bytes}',
         f'-DMINYAR_RC_POLL_BUDGET={args.budget}', work / 'input.ll',
         work / 'runtime.c', '-o', work / 'program'])
    result = run([work / 'program'])
    assert result.stdout == f'1\n{args.iterations}\n'
    print('runtime=' + (args.runtime_revision or 'working-tree'),
          f'heap={args.heap_bytes} K={args.budget} iterations={args.iterations}')
    print(result.stdout, end='')
    print(result.stderr, end='')
    print('Counts precede exit cleanup; exact reclamation is checked by the profile matrix.')


if __name__ == '__main__':
    main()
