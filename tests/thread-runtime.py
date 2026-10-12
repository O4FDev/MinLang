#!/usr/bin/env python3
"""Native managed-thread fixtures; no compiler build or scalar worker substitute."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
from clang_helpers import native_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--domain-only', action='store_true')
    parser.add_argument('--sanitize', choices=['none', 'address,undefined', 'thread'], default='none')
    args = parser.parse_args()
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    (build / 'thread-cycle-engine.c').write_text(engine_source(ROOT))
    compiler = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    sources = ['thread-domain.c'] if args.domain_only else ['thread-domain.c', 'thread-runtime.c']
    for source in sources:
        for cycles in (False, True):
            for bounded in (False, True):
                label = f'{Path(source).stem}-{"cycle" if cycles else "rc"}-{"bounded" if bounded else "eager"}'
                output = build / (label + ('.exe' if os.name == 'nt' else ''))
                command = [compiler, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                           '-DMINYAR_THREADED=1', '-I' + native_path(ROOT / 'runtime')]
                if cycles:
                    command += ['-DMINYAR_TEST_CYCLES=1']
                if bounded:
                    command += ['-DMINYAR_SYSTEM_HEAP=1']
                if args.sanitize != 'none':
                    command += ['-fsanitize=' + args.sanitize, '-fno-omit-frame-pointer']
                command += [native_path(ROOT / 'tests' / source), '-o', native_path(output)]
                command += [] if os.name == 'nt' else ['-pthread', '-lm']
                subprocess.run(command, check=True, timeout=120)
                environment = dict(os.environ, UBSAN_OPTIONS='halt_on_error=1', TSAN_OPTIONS='halt_on_error=1')
                environment['ASAN_OPTIONS'] = 'detect_leaks=' + ('1' if sys.platform.startswith('linux') else '0')
                subprocess.run([native_path(output)], check=True, timeout=90, env=environment)
                print(label + ' ' + args.sanitize + ' passed', flush=True)


if __name__ == '__main__':
    main()
