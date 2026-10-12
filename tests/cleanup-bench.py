import argparse
import os
from pathlib import Path
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    'cleanup': ('tests/cleanup-cost.min', []),
    'runtime': ('tests/performance/runtime.min', ['4']),
    'json': ('benchmarks/json/history-parse.min', ['build/cleanup-bench/history.json', '20']),
    'text': ('benchmarks/text-basics.min', []),
    'maps': ('tests/cleanup-maps.min', []),
}
p = argparse.ArgumentParser()
p.add_argument('mode', choices=['build', 'run'])
p.add_argument('--output', type=Path, default=Path('build/cleanup-bench'))
p.add_argument('--small', action='store_true')
p.add_argument('--repeats', type=int, default=9)
p.add_argument('--compare', nargs='+', type=Path)
a = p.parse_args()
if a.mode == 'build':
    a.output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if a.small:
        env['MINYAR_RUNTIME_FLAGS'] = '-O2 -Wno-override-module -DMINYAR_SYSTEM_SMALL_HEAP=1'
    with (a.output / 'history.json').open('w') as output:
        subprocess.run(['python3', 'benchmarks/json/history.py', '500'], stdout=output, check=True)
    for name, (source, _) in CASES.items():
        subprocess.run(['./minyar', '--release', source, '-o', str(a.output / name)], env=env, check=True)
else:
    assert a.compare and len(a.compare) >= 2
    results = {name: [[] for _ in a.compare] for name in CASES}
    for repeat in range(a.repeats + 1):
        for name, (_, arguments) in CASES.items():
            outputs = []
            for i in (range(len(a.compare)) if repeat % 2 == 0 else reversed(range(len(a.compare)))):
                command = ['taskset', '-c', '2', str((a.compare[i] / name).resolve()), *arguments]
                start = time.perf_counter()
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                elapsed = time.perf_counter() - start
                if repeat:
                    results[name][i].append(elapsed)
                outputs.append(result.stdout)
            if name == 'cleanup':
                assert all('(12000000)' in output for output in outputs), outputs
            else:
                assert len(set(outputs)) == 1, (name, outputs)
    for name, samples in results.items():
        medians = [statistics.median(sample) for sample in samples]
        print(name, flush=True)
        for path, sample, median in zip(a.compare, samples, medians):
            print(f'  {path}: median={median:.6f}s range={min(sample):.6f}..{max(sample):.6f}s speedup={medians[0]/median:.3f}x', flush=True)
