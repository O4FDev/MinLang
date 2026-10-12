import argparse
from pathlib import Path
import statistics
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--baseline-source', type=Path)
    parser.add_argument('--candidate-arg', action='append', default=[])
    parser.add_argument('--repeats', type=int, default=31)
    args = parser.parse_args()
    samples = {'baseline': [], 'candidate': []}
    with tempfile.TemporaryDirectory(prefix='minyar-self-bench-') as temporary:
        output = Path(temporary) / 'compiler.ll'
        for repeat in range(args.repeats + 3):
            order = ('baseline', 'candidate') if repeat % 2 else ('candidate', 'baseline')
            for name in order:
                start = time.perf_counter_ns()
                source = args.baseline_source if name == 'baseline' and args.baseline_source else args.source
                arguments = args.candidate_arg if name == 'candidate' else []
                subprocess.run([str(getattr(args, name).resolve()), str(source.resolve()), str(output), *arguments],
                               check=True, capture_output=True, timeout=60)
                elapsed = (time.perf_counter_ns() - start) / 1e9
                if repeat >= 3:
                    samples[name].append(elapsed)
    for name, values in samples.items():
        print(f'{name}: median={statistics.median(values):.6f}s '
              f'min={min(values):.6f}s max={max(values):.6f}s n={len(values)}')
    ratio = statistics.median(samples['candidate']) / statistics.median(samples['baseline'])
    print(f'self-compile change: {(ratio - 1) * 100:+.3f}%')
    if ratio > 1.01:
        raise SystemExit('self-compile exceeded the 1% limit')


if __name__ == '__main__':
    main()
