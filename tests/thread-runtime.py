#!/usr/bin/env python3
"""Native managed-thread fixtures; no compiler build or scalar worker substitute."""
import argparse
import os
import shlex
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
from clang_helpers import native_path, windows_host, asan_leak_options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--domain-only', action='store_true')
    parser.add_argument('--buffers-only', action='store_true')
    parser.add_argument('--cache-debt-only', action='store_true')
    parser.add_argument('--windows-cross', action='store_true')
    parser.add_argument('--sanitize', choices=['none', 'address,undefined', 'thread'], default='none')
    args = parser.parse_args()
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    (build / 'thread-cycle-engine.c').write_text(engine_source(ROOT))
    compiler = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    windows = args.windows_cross or windows_host()
    launch = ['wine'] if args.windows_cross else []
    if args.windows_cross and args.sanitize != 'none':
        parser.error('Windows cross/Wine fixtures do not qualify native sanitizers')
    sources = ['thread-cache-debt.c'] if args.cache_debt_only else ['thread-buffers.c'] if args.buffers_only else ['thread-domain.c'] if args.domain_only else ['thread-domain.c', 'thread-cache-debt.c', 'thread-buffers.c', 'thread-runtime.c']
    for source in sources:
        for cycles in (False, True):
            for bounded in (False, True):
                label = f'{Path(source).stem}-{"cycle" if cycles else "rc"}-{"bounded" if bounded else "eager"}'
                output = build / (label + ('.exe' if windows else ''))
                command = [compiler, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                           '-DMINYAR_THREADED=1', '-I' + native_path(ROOT / 'runtime')]
                if args.windows_cross:
                    library = subprocess.check_output(['x86_64-w64-mingw32-gcc', '-print-libgcc-file-name'], text=True).strip()
                    command += ['--target=x86_64-w64-windows-gnu', '--sysroot=/usr/x86_64-w64-mingw32',
                                '-L' + str(Path(library).parent)]
                if cycles:
                    command += ['-DMINYAR_TEST_CYCLES=1']
                if bounded:
                    command += ['-DMINYAR_SYSTEM_HEAP=1']
                    if os.environ.get('MINYAR_TEST_RC_BUDGET'):
                        command += ['-DMINYAR_RC_POLL_BUDGET=' + os.environ['MINYAR_TEST_RC_BUDGET']]
                if os.environ.get('MINYAR_TEST_TEXT_CACHE'):
                    command += ['-DMINYAR_INTEGER_TEXT_CACHE_LIMIT=' + os.environ['MINYAR_TEST_TEXT_CACHE']]
                if args.sanitize != 'none':
                    command += ['-fsanitize=' + args.sanitize, '-fno-omit-frame-pointer']
                command += [native_path(ROOT / 'tests' / source), '-o', native_path(output)]
                command += [] if windows else ['-pthread', '-lm']
                print('compile: ' + shlex.join(command), flush=True)
                subprocess.run(command, check=True, timeout=120)
                environment = dict(os.environ, UBSAN_OPTIONS='halt_on_error=1', TSAN_OPTIONS='halt_on_error=1')
                environment['ASAN_OPTIONS'] = asan_leak_options()
                if args.windows_cross:
                    environment['WINEDEBUG'] = '-all'
                subprocess.run(launch + [native_path(output)], check=True, timeout=90, env=environment)
                if source == 'thread-runtime.c':
                    for case, diagnostic in [('allocation', 'memory'), ('allocation-packet', 'memory'),
                            ('allocation-detach', 'memory'), ('capacity', 'capacity'), ('bounds', 'position'),
                            ('bounds64', 'position'), ('start-result', 'Result'),
                            ('join-result', 'Result'), ('frozen-result', 'Result')]:
                        fault_environment = dict(environment)
                        stopped = subprocess.run(launch + [native_path(output), case], capture_output=True,
                                                 timeout=10, env=fault_environment, text=True)
                        if stopped.returncode in (0, 99) or diagnostic not in stopped.stderr:
                            raise AssertionError((label, case, stopped.returncode, stopped.stderr))
                print(label + ' ' + args.sanitize + ' passed', flush=True)


if __name__ == '__main__':
    main()
