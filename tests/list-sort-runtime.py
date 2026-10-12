#!/usr/bin/env python3
"""Stable-sort independent models in both engines and supported heap profiles."""
import argparse
import json
import os
from pathlib import Path
import sys
from clang_helpers import clang_command, windows_host, asan_leak_options
from test_evidence import Evidence
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('native', 'sanitize', 'both'), default='both')
    parser.add_argument('--report', type=Path, default=ROOT / 'build/list-sort-runtime.json')
    args = parser.parse_args()
    profiles = {'arena': ['-DMINYAR_COMPILER_ARENA=1'], 'eager': [],
                'system-k1': ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=1'],
                'system-k32': ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=32'],
                'bounded': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=33554432']}
    if not windows_host(): profiles['lazy'] = profiles['bounded'] + ['-DMINYAR_LAZY_HEAP=1']
    source = ROOT / 'tests/list-sort-runtime.c'
    observations = []
    with Evidence('list-sort-runtime', inputs=[source, Path(__file__), ROOT / 'tools/cycle_runtime.py', ROOT / 'runtime/minyar_runtime.c', *sorted((ROOT / 'runtime').glob('*.h'))], controls={'profiles': profiles, 'mode': args.mode}) as evidence:
        for mode in (('native', 'sanitize') if args.mode == 'both' else (args.mode,)):
            flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g'] if mode == 'sanitize' else []
            for engine in ('ordinary', 'graph'):
                text = source.read_text()
                replacement = engine_source(ROOT) if engine == 'graph' else (ROOT / 'runtime/minyar_runtime.c').read_text()
                harness = evidence.path / (engine + '.c')
                harness.write_text(text.replace('#include "../runtime/minyar_runtime.c"', replacement))
                for profile, defines in profiles.items():
                    for optimization in ('-O0', '-O2'):
                        exe = evidence.path / (mode + '-' + engine + '-' + profile + '-' + optimization[1:])
                        built = evidence.run(clang_command([os.environ.get('MINYAR_TEST_CLANG', 'clang'), '-std=c11', optimization, *flags, *defines, '-iquote', ROOT / 'runtime', harness, '-o', exe]), timeout=60, phase='build-sort-model')
                        assert built.returncode == 0, built.stderr
                        env = dict(os.environ, ASAN_OPTIONS=('detect_leaks=0' if profile == 'arena' else asan_leak_options()) + ':halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
                        run = evidence.run([exe], env=env, timeout=30, phase='sort-model')
                        assert (run.returncode, run.stdout, run.stderr) == (0, b'natural-models-alias-copy-float-text-comparator-stability-ok\n', b''), (run.returncode, run.stdout, run.stderr)
                        for mutation in ('set', 'add'):
                            run = evidence.run([exe, mutation], env=dict(env, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'), timeout=30, phase='sort-mutation-reject')
                            assert (run.returncode, run.stdout, run.stderr) == (1, b'', b'Minyar stopped: the List was mutated during its sort comparator.\n'), (run.returncode, run.stdout, run.stderr)
                        observations.append(dict(mode=mode, engine=engine, profile=profile, optimization=optimization, mutation_rejections=['set','add']))
                        print(mode, engine, profile, optimization, 'PASS', flush=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(dict(successful=True, observations=observations, inputs=evidence.inputs, commands=evidence.commands), indent=2)+'\n')
    print(len(observations), 'configurations passed;', args.report)

if __name__ == '__main__': main()
