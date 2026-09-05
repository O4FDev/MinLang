#!/usr/bin/env python3
"""Run language/ownership oracles against cold and then cached module output."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    suffix = '-sanitize' if args.sanitize else ''
    driver = ROOT / ('build/minyar-module-build' + suffix)
    compiler = ROOT / ('build/minyarc-modules' + suffix)
    with tempfile.TemporaryDirectory(prefix='minyar-module-oracles-') as name:
        directory = Path(name)
        wrapper = directory / 'compiler'
        command = ' '.join([shlex.quote(str(driver)), shlex.quote(str(compiler)),
                            '"$1"', '"$2"', shlex.quote(str(directory / 'cache'))])
        wrapper.write_text('#!/bin/sh\nset -eu\n' + command + '\n' + command + '\n')
        wrapper.chmod(0o755)
        env = dict(os.environ, MINYAR_TEST_COMPILER=str(wrapper))
        if args.sanitize:
            env.update(ASAN_OPTIONS='detect_leaks=0',
                       MINYAR_TEST_RUNTIME=str(ROOT / 'build/ownership-runtime.o'),
                       MINYAR_TEST_LINK_FLAGS='-fsanitize=address,undefined')
        for test in ('regressions.py', 'ownership.py', 'recursive-data.py'):
            if args.sanitize:
                # Deliberate runtime errors do not run normal-exit cleanup.
                # Use the ordinary sanitizer runtime for those regressions;
                # ownership/recursive tests also enforce exact reclamation.
                runtime='minyar-runtime-sanitize.o' if test=='regressions.py' else 'ownership-runtime.o'
                env['MINYAR_TEST_RUNTIME']=str(ROOT/'build'/runtime)
            subprocess.run(['python3', str(ROOT / 'tests' / test)], env=env, check=True)


if __name__ == '__main__':
    main()
