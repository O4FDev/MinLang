#!/usr/bin/env python3
"""Self-sample the existing workload functions in a temporary repeated driver.

Optional macOS arm64 diagnostic. This measures sampled program counters, not
inclusive stack time, and is separate from uninstrumented timing comparisons.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--optimization', choices=['O0', 'O2'], default='O0')
    args = parser.parse_args()
    directory = Path(tempfile.mkdtemp(prefix='minyar-self-profile-'))
    original = (ROOT / 'tests/performance/runtime.min').read_text()
    source = original[:original.index('let scale = 1')]
    source += '''let iteration = 0
let total = 0
while iteration < 80 {
total = total + listWorkload(1600000)
total = total + recordWorkload(800000)
total = total + textWorkload(800000)
total = total + arithmeticWorkload(4000000)
total = total + callWorkload(160)
iteration = iteration + 1
}
print(total)
'''
    path = directory / 'program.min'
    path.write_text(source)

    def run(command):
        return subprocess.run(list(map(str, command)), check=True, capture_output=True, timeout=60)

    run([ROOT / 'build/minyarc', path, directory / 'program.ll'])
    run(['clang', '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-c',
         ROOT / 'scripts/ownership-sampler.c', '-o', directory / 'sampler.o'])
    run(['clang', '-O' + args.optimization[1:], '-Wno-override-module',
         directory / 'program.ll', ROOT / 'build/minyar-runtime.o', directory / 'sampler.o',
         '-Wl,-export_dynamic', '-o', directory / 'program'])
    result = run([directory / 'program'])
    assert result.stdout == b'25606375772240\n', result.stdout
    counts = Counter()
    for line in result.stderr.decode().splitlines():
        if line.startswith('MINYAR_PC\t'):
            _, library, symbol = line.split('\t')
            counts[(Path(library).name, symbol)] += 1
    total = sum(counts.values())
    assert total > 0, result.stderr
    report = {'method': __doc__, 'optimization': args.optimization,
              'samples': total, 'artifacts': str(directory),
              'symbols': [{'library': library, 'symbol': symbol, 'samples': n,
                           'percent': n * 100 / total} for (library, symbol), n in counts.most_common()]}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    (directory / 'raw-samples.txt').write_bytes(result.stderr)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
