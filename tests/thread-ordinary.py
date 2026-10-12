#!/usr/bin/env python3
"""Paired ordinary O2 object/LLVM identity; application timing is a separate gate."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
from clang_helpers import native_path, without_asm_source_locations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-root', type=Path, required=True)
    args = parser.parse_args()
    build = ROOT / 'build/thread-ordinary'
    build.mkdir(parents=True, exist_ok=True)
    compiler = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    profiles = [('eager', []), ('system', ['MINYAR_SYSTEM_HEAP=1']),
                ('arena', ['MINYAR_COMPILER_ARENA=1']), ('fixed', ['MINYAR_BOUNDED_HEAP=1']),
                ('lazy', ['MINYAR_LAZY_HEAP=1'])]
    for engine in ('rc', 'cycle'):
        for name, definitions in profiles:
            for suffix, phase in [('o', ['-c']), ('ll', ['-S', '-emit-llvm'])]:
                artifacts = []
                for label, root in [('base', args.base_root), ('candidate', ROOT)]:
                    source = engine_source(root) if engine == 'cycle' else (root / 'runtime/minyar_runtime.c').read_text()
                    output = build / (engine + '-' + name + '-' + label + '.' + suffix)
                    # Identical stdin source name avoids path/debug differences
                    # while each side uses its own complete runtime headers.
                    command = [compiler, '-std=c11', '-O2', '-g0', '-x', 'c', '-',
                               '-I' + native_path(root / 'runtime')]
                    command += ['-D' + definition for definition in definitions]
                    command += phase + ['-o', native_path(output)]
                    subprocess.run(command, input=source, text=True, check=True, timeout=60)
                    data = output.read_bytes()
                    artifacts.append(without_asm_source_locations(data) if suffix == 'll' else data)
                if artifacts[0] != artifacts[1]:
                    raise AssertionError(engine + ' ' + name + ' ' + suffix + ' changed')
                print(engine, name, suffix, hashlib.sha256(artifacts[1]).hexdigest(), 'identical', flush=True)


if __name__ == '__main__':
    main()
