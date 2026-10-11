#!/usr/bin/env python3
"""Real selectors/timers plus compiled Minyar, with sanitizer ownership checks."""
import argparse
from contextlib import nullcontext
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from clang_helpers import windows_host
from network_evidence import captured_run, digest, finalize_evidence

ROOT = Path(__file__).resolve().parents[1]
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
WINDOWS = windows_host()


def selected_modes(parser, mode):
    if WINDOWS and mode == 'sanitize':
        parser.error('event-loop sanitizer mode is unavailable in this suite on Windows')
    if mode == 'native':
        return ['native'] if WINDOWS else ['native', 'app-native']
    if mode == 'sanitize':
        return ['sanitize', 'app-sanitize']
    return ['native'] if WINDOWS else ['native', 'sanitize', 'app-native', 'app-sanitize']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('native', 'sanitize'))
    parser.add_argument('--evidence', type=Path)
    options = parser.parse_args()
    modes = selected_modes(parser, options.mode)
    if options.evidence:
        directory = options.evidence.resolve()
        directory.mkdir(parents=True, exist_ok=True)
        if any(directory.iterdir()):
            parser.error('event-loop evidence directory must be empty')
        workspace = nullcontext(str(directory))
    else:
        workspace = tempfile.TemporaryDirectory(prefix='net-loop-', dir=ROOT / 'build')
    with workspace as temporary:
        temporary = Path(temporary)
        records, errors = [], []
        inputs = {}
        if options.evidence:
            sources = [Path(__file__), ROOT/'tests/network_evidence.py',
                       ROOT/'tests/clang_helpers.py', ROOT/'tests/net-loop.c',
                       ROOT/'tests/net-loop.min', ROOT/'runtime/minyar_runtime.c',
                       ROOT/'library/eventloop.min', ROOT/'library/net.min', ROOT/'minyar']
            sources.extend((ROOT/'runtime').rglob('*.h'))
            inputs = {str(path.relative_to(ROOT)): digest(path) for path in sources}
        def run(command, *, phase, **kwargs):
            if not options.evidence:
                return subprocess.run(command, **kwargs)
            return captured_run(temporary, records, errors, command, phase=phase, **kwargs)
        status, primary = 'failed', None
        try:
            if options.evidence:
                run([CLANG, '--version'], phase='clang-version', check=True,
                    capture_output=True, timeout=10)
            for mode in modes:
                executable = temporary / (mode + ('.exe' if WINDOWS else ''))
                flags = ['-O2'] if mode.endswith('native') else [
                    '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                if mode.startswith('app-'):
                    flags += ['-DMINYAR_APP_EVENT_LOOP=1']
                command = [CLANG, '-std=c11', '-D_GNU_SOURCE', '-DMINYAR_SYSTEM_HEAP=1',
                           '-Wall', '-Wextra', '-Werror', *flags,
                           str(ROOT / 'tests/net-loop.c'), str(ROOT / 'runtime/minyar_runtime.c'),
                           '-lm', '-o', str(executable)]
                if WINDOWS:
                    command += ['-lws2_32']
                run(command, phase=mode+'-compile', check=True, cwd=ROOT)
                environment = os.environ.copy()
                environment['ASAN_OPTIONS'] = 'detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
                environment['UBSAN_OPTIONS'] = 'halt_on_error=1'
                run([executable], phase=mode+'-run', check=True, env=environment, timeout=30)
            # Preserve the original public launcher path and caller-supplied flags.
            if options.mode != 'sanitize':
                for mode in ['--debug', '--release']:
                    program = temporary / ('minyar-' + mode[2:] + ('.exe' if WINDOWS else ''))
                    compiled = run([ROOT / 'minyar', mode, ROOT / 'tests/net-loop.min', '-o', program],
                                   phase=mode[2:]+'-compile', capture_output=True,
                                   text=True, cwd=ROOT, timeout=60)
                    assert compiled.returncode == 0, compiled.stderr
                    result = run([program], phase=mode[2:]+'-run', check=True,
                                 capture_output=True, text=True, timeout=30)
                    assert result.stdout == 'loop module verified\n', (result.stdout, result.stderr)
                print('Compiled Minyar event loop API verified at O0/release')
            else:
                print('Native event loop ASan/UBSan contracts verified')
            status = 'passed'
        except BaseException as error:
            primary = error
            raise
        finally:
            if options.evidence:
                finalize_evidence(temporary, inputs, records, errors, modes, status,
                                  primary, root=ROOT)


if __name__ == '__main__':
    main()
