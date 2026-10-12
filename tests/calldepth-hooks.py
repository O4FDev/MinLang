import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from clang_helpers import asan_leak_options, launcher_command

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    environment = dict(os.environ, LIMITED='', SANITIZER_LIMITED='')
    if args.sanitize:
        environment.update(ASAN_OPTIONS=asan_leak_options() + ':detect_stack_use_after_return=1:halt_on_error=1',
                           UBSAN_OPTIONS='halt_on_error=1')
    with tempfile.TemporaryDirectory(prefix='minyar-recovery-threads-') as temporary:
        for profile in ('system', 'eager'):
            for optimization in ('-O0', '-O2'):
                flags = optimization + ' -Wno-override-module'
                if args.sanitize:
                    flags += ' -g -fsanitize=address,undefined -fno-omit-frame-pointer'
                environment.update(MINYAR_CLANG_FLAGS=flags, MINYAR_RUNTIME_FLAGS=flags)
                executable = Path(temporary) / (profile + optimization)
                command = [*launcher_command(ROOT), '--memory-profile', profile,
                           str(ROOT / 'tests/thread-fixtures/recovery-unwind.min'), '-o', str(executable)]
                compiled = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=300)
                assert compiled.returncode == 0, compiled.stdout + compiled.stderr
                executed = subprocess.run([str(executable)], env=environment, capture_output=True, text=True, timeout=30)
                assert (executed.returncode, executed.stdout, executed.stderr) == (0, 'recovery and child cleanup passed\n', ''), executed
                print(profile + '/' + optimization + ': recovery and child cleanup passed')


if __name__ == '__main__':
    main()
