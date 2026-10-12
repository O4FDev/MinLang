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
    parser.add_argument('--buffers-only', action='store_true')
    parser.add_argument('--sanitize', choices=['none', 'address,undefined', 'thread'], default='none')
    args = parser.parse_args()
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    (build / 'thread-cycle-engine.c').write_text(engine_source(ROOT))
    compiler = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    sources = ['thread-buffers.c'] if args.buffers_only else ['thread-domain.c'] if args.domain_only else ['thread-domain.c', 'thread-buffers.c']
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
                    if os.environ.get('MINYAR_TEST_RC_BUDGET'):
                        command += ['-DMINYAR_RC_POLL_BUDGET=' + os.environ['MINYAR_TEST_RC_BUDGET']]
                if args.sanitize != 'none':
                    command += ['-fsanitize=' + args.sanitize, '-fno-omit-frame-pointer']
                command += [native_path(ROOT / 'tests' / source), '-o', native_path(output)]
                command += [] if os.name == 'nt' else ['-pthread', '-lm']
                subprocess.run(command, check=True, timeout=120)
                environment = dict(os.environ, UBSAN_OPTIONS='halt_on_error=1', TSAN_OPTIONS='halt_on_error=1')
                environment['ASAN_OPTIONS'] = 'detect_leaks=' + ('1' if sys.platform.startswith('linux') else '0')
                subprocess.run([native_path(output)], check=True, timeout=90, env=environment)
                if source == 'thread-runtime.c':
                    for case, diagnostic in [('capacity', 'capacity'), ('bounds', 'position'),
                            ('bounds64', 'position'), ('start-result', 'Result'),
                            ('join-result', 'Result'), ('frozen-result', 'Result')]:
                        stopped = subprocess.run([native_path(output), case], capture_output=True,
                                                 timeout=10, env=environment, text=True)
                        if stopped.returncode in (0, 99) or diagnostic not in stopped.stderr:
                            raise AssertionError((label, case, stopped.returncode, stopped.stderr))
                print(label + ' ' + args.sanitize + ' passed', flush=True)


if __name__ == '__main__':
    main()
