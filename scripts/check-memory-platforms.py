#!/usr/bin/env python3
"""Check correctness with Rosetta x86_64 and a second LLVM toolchain.

A retained temporary directory contains source snapshots, command logs,
executables and results.json. Rosetta exercises x86_64 instructions on macOS;
it does not test a Linux ABI or native Intel hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=('all', 'rosetta', 'llvm22'), default='all')
    parser.add_argument('--llvm', default='/opt/homebrew/opt/llvm/bin/clang')
    args = parser.parse_args()
    destination = Path(tempfile.mkdtemp(prefix='minyar-memory-platforms-'))
    source = destination / 'source'
    files = ['src/compiler.min', 'build/compiler-stage2.ll', 'runtime/minyar_runtime.c',
             'runtime/minyar_rc.h', 'runtime/minyar_pool.h', 'runtime/minyar_bounded_rc.h',
             'runtime/minyar_heap.h',
             'tests/regressions.py', 'tests/recursive-data.py', 'tests/production-memory.py',
             'tests/bounded-ownership-runtime.c', 'experiments/memory/production-live-oracle.c',
             'experiments/memory/production-frame-oracle.c']
    hashes = {}
    for name in files:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    results = {'directory': str(destination), 'source_sha256': hashes, 'platforms': {},
               'limitations': ['Rosetta is translation on Apple Silicon, not native Intel hardware.',
                               'These checks do not validate Linux, Windows, real-time scheduling or throughput.']}
    print(destination, flush=True)

    def save():
        (destination / 'results.json').write_text(json.dumps(results, indent=2) + '\n')

    for platform in ('rosetta', 'llvm22'):
        if args.platform not in ('all', platform):
            continue
        work = destination / platform
        work.mkdir()
        compiler = 'clang' if platform == 'rosetta' else args.llvm
        architecture = ['-arch', 'x86_64'] if platform == 'rosetta' else []
        record = {'commands': [], 'complete': False}
        results['platforms'][platform] = record

        def run(label, command, env=None, timeout=180):
            completed = subprocess.run(command, cwd=source, env=env, text=True,
                                       capture_output=True, timeout=timeout)
            (work / (label + '.log')).write_text(completed.stdout + completed.stderr)
            record['commands'].append({'label': label, 'argv': [str(arg) for arg in command],
                                       'returncode': completed.returncode})
            save()
            if completed.returncode:
                raise RuntimeError(f'{platform}/{label} failed; see {work / (label + ".log")}')
            print(f'{platform}: {label} passed', flush=True)
            return completed

        run('toolchain', [compiler, '--version'])
        if platform == 'rosetta':
            probe = run('architecture', ['/usr/bin/arch', '-x86_64', '/usr/bin/uname', '-m'])
            assert probe.stdout.strip() == 'x86_64'
        base = [compiler, *architecture, '-Wno-override-module']
        runtime = source / 'runtime/minyar_runtime.c'
        compiler_ir = work / 'compiler-runtime.ll'
        run('compiler-runtime-ir', [*base, '-O2', '-DMINYAR_COMPILER_ARENA', '-S', '-emit-llvm',
                                    str(runtime), '-o', str(compiler_ir)])
        compiler_ir.write_text(re.sub(r'"(?:target-cpu|target-features|tune-cpu)"="[^"]*" ?',
                                      '', compiler_ir.read_text()))
        executable = work / 'minyarc'
        run('compiler-link', [*base, '-O2', '-flto', str(source / 'build/compiler-stage2.ll'),
                              str(compiler_ir), '-o', str(executable)])
        emitted = work / 'compiler-stage3.ll'
        run('compiler-self-host', [str(executable), str(source / 'src/compiler.min'), str(emitted)])
        assert emitted.read_bytes() == (source / 'build/compiler-stage2.ll').read_bytes(), \
            f'{platform}: self-hosting fixed point differs'
        record['fixed_point'] = True
        run('runtime-native', [*base, '-O2', '-c', str(runtime), '-o', str(work / 'runtime.o')])
        run('runtime-bounded', [*base, '-O2', '-DMINYAR_BOUNDED_HEAP=1', '-c', str(runtime),
                               '-o', str(work / 'bounded.o')])
        environment = dict(os.environ, MINYAR_TEST_COMPILER=str(executable),
                           MINYAR_TEST_CLANG=compiler, MINYAR_TEST_LINK_FLAGS=' '.join(architecture))
        for profile, object_name in (('native', 'runtime.o'), ('bounded', 'bounded.o')):
            environment['MINYAR_TEST_RUNTIME'] = str(work / object_name)
            run(profile + '-production-contracts',
                [sys.executable, str(source / 'tests/production-memory.py')], environment)
        environment['MINYAR_TEST_RUNTIME'] = str(work / 'bounded.o')
        run('bounded-recursive-contracts',
            [sys.executable, str(source / 'tests/recursive-data.py')], environment)

        sanitizer = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        run('sanitized-runtime', [*base, *sanitizer, '-c',
                                  str(source / 'tests/bounded-ownership-runtime.c'),
                                  '-o', str(work / 'bounded-sanitize.o')])
        environment.update(MINYAR_TEST_RUNTIME=str(work / 'bounded-sanitize.o'),
                           MINYAR_TEST_LINK_FLAGS=' '.join([*architecture, '-fsanitize=address,undefined']),
                           ASAN_OPTIONS='detect_leaks=0')
        run('sanitized-production-contracts',
            [sys.executable, str(source / 'tests/production-memory.py')], environment)
        run('sanitized-oracle-build', [*base, *sanitizer,
                                       str(source / 'experiments/memory/production-live-oracle.c'),
                                       '-o', str(work / 'live-oracle')])
        run('sanitized-ownership-oracle', [str(work / 'live-oracle')], environment)
        for budget in (1, 32):
            label = f'sanitized-frame-oracle-k{budget}'
            run(label + '-build', [*base, *sanitizer, f'-DMINYAR_RC_POLL_BUDGET={budget}',
                                   str(source / 'experiments/memory/production-frame-oracle.c'),
                                   '-o', str(work / label)])
            run(label, [str(work / label)], environment)
        record['complete'] = True
        save()
    print(f'All requested correctness checks passed; evidence: {destination / "results.json"}', flush=True)


if __name__ == '__main__':
    main()
