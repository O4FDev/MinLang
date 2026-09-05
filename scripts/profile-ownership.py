#!/usr/bin/env python3
"""Profile runtime operation counts with LLVM instrumentation.

Execution counts do not measure time spent in each operation. Use uninstrumented,
interleaved runs for timing comparisons."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    parser.add_argument('--runtime', type=Path, default=ROOT / 'runtime/minyar_runtime.c')
    parser.add_argument('--llvm-bin', type=Path, default=Path('/opt/homebrew/opt/llvm/bin'))
    parser.add_argument('--scale', type=int, default=8)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    directory = Path(tempfile.mkdtemp(prefix='minyar-ownership-profile-'))
    clang = str(args.llvm_bin / 'clang')
    benchmark = ROOT / 'tests/performance/runtime.min'
    flags = ['-fprofile-instr-generate', '-fcoverage-mapping']

    def run(command, **kwargs):
        return subprocess.run(command, check=True, capture_output=True, text=True,
                              timeout=60, **kwargs)

    run([str(args.compiler.resolve()), str(benchmark), str(directory / 'program.ll')])
    run([clang, '-O2', '-g', *flags, '-c', str(args.runtime.resolve()),
         '-o', str(directory / 'runtime.o')])
    run([clang, '-O0', '-Wno-override-module', '-fprofile-instr-generate',
         str(directory / 'program.ll'), str(directory / 'runtime.o'),
         '-o', str(directory / 'program')])
    env = dict(os.environ, LLVM_PROFILE_FILE=str(directory / 'runtime.profraw'))
    program = run([str(directory / 'program'), str(args.scale)], env=env)
    run([str(args.llvm_bin / 'llvm-profdata'), 'merge', '-sparse',
         str(directory / 'runtime.profraw'), '-o', str(directory / 'runtime.profdata')])
    export = run([str(args.llvm_bin / 'llvm-cov'), 'export', str(directory / 'program'),
                  '-instr-profile=' + str(directory / 'runtime.profdata')])
    coverage = json.loads(export.stdout)
    operations = {function['name']: function['count']
                  for function in coverage['data'][0]['functions']}
    result = {
        'method': 'LLVM instrumentation of the O2 C runtime, linked to O0 Minyar LLVM; execution counts, not timings',
        'scale': args.scale,
        'benchmark_sha256': hashlib.sha256(benchmark.read_bytes()).hexdigest(),
        'runtime_sha256': hashlib.sha256(args.runtime.read_bytes()).hexdigest(),
        'compiler_sha256': hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
        'operations': operations,
        'stdout': program.stdout,
        'artifacts': str(directory),
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    (directory / 'coverage.json').write_text(export.stdout)
    print(json.dumps({name: count for name, count in operations.items()
                      if name.startswith('minyar_rc_')}, indent=2))


if __name__ == '__main__':
    main()
