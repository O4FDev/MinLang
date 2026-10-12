#!/usr/bin/env python3
"""Map contracts across maintained frontends and allocation/collector profiles.

Run heavy verification on the assigned Boat under its serial build lock.
Every normal language exit checks exact live-object recovery, including cycles.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    directory = ROOT / 'build' / ('maps-sanitize' if args.sanitize else 'maps-matrix')
    directory.mkdir(parents=True, exist_ok=True)
    cycle = directory / 'cycle-engine.c'
    cycle.write_text(engine_source(ROOT))
    profiles = [('eager', []), ('system-1', ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=1']),
                ('system-32', ['-DMINYAR_SYSTEM_HEAP=1']),
                ('fixed-1', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=1']),
                ('arena', ['-DMINYAR_COMPILER_ARENA=1'])]
    if sys.platform != 'win32':
        profiles.append(('lazy', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1']))
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g'] if args.sanitize else []
    env = dict(os.environ, MINYAR_TEST_CLANG=clang, MINYAR_TEST_LINK_FLAGS=' '.join(flags),
               ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
    suffix = '-sanitize' if args.sanitize else ''
    frontends = tuple(name + suffix for name in ('minyarc', 'minyarc-modules', 'minyarc-callbacks', 'minyarc-errors'))
    runtimes = []
    for traced in (False, True):
        for profile, definitions in profiles:
            # Arena has process-lifetime ownership; all others enforce recovery.
            if traced and profile == 'arena':
                continue
            name = ('cycle-' if traced else '') + profile
            print('PROFILE', name, flush=True)
            native = directory / (name + '-native')
            native_flags = definitions + (['-DMINYAR_MAP_TEST_ENGINE="' + str(cycle) + '"'] if traced else [])
            subprocess.run([clang, '-O1' if args.sanitize else '-O0', *flags,
                            '-std=c11', '-Wall', '-Wextra', '-Werror', '-iquote', str(ROOT / 'runtime'),
                            *native_flags, str(ROOT / 'tests/map-runtime.c'), '-lm', '-o', str(native)], check=True)
            # Compiler arenas deliberately retain all allocations until exit.
            native_env = dict(env, ASAN_OPTIONS='detect_leaks=0') if profile == 'arena' else env
            subprocess.run([str(native)], env=native_env, check=True)
            if profile == 'arena':
                continue
            harness = directory / (name + '.c')
            contract = (ROOT / 'tests/memory-contracts-runtime.c').read_text()
            replacement = engine_source(ROOT) if traced else '#include "minyar_runtime.c"'
            harness.write_text(contract.replace('#include "../runtime/minyar_runtime.c"', replacement))
            runtime = harness.with_suffix('.o')
            subprocess.run([clang, '-O1' if args.sanitize else '-O2', *flags, *definitions,
                            '-iquote', str(ROOT / 'runtime'), '-c', str(harness), '-o', str(runtime)], check=True)
            runtimes.append([name, str(runtime)])
    # Each frontend runs the map suite once against every runtime profile:
    # programs compile once, and only the link and run repeat per runtime.
    # Frontends are independent (separate evidence workspaces), so up to
    # MINYAR_TEST_JOBS of them run at once; each one's output prints whole.
    def run(frontend):
        result = subprocess.run([sys.executable, str(ROOT / 'tests/maps.py')], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                env=dict(env, MINYAR_TEST_COMPILER=str(ROOT / 'build' / frontend),
                                         MINYAR_TEST_RUNTIME=runtimes[0][1], MINYAR_MAP_RUNTIMES=json.dumps(runtimes)))
        print('FRONTEND', frontend, *(name for name, _ in runtimes), flush=True)
        print(result.stdout, end='', flush=True)
        return result.returncode
    jobs = max(1, int(os.environ.get('MINYAR_TEST_JOBS', '2')))
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        failed = [frontend for frontend, status in zip(frontends, pool.map(run, frontends)) if status]
    if failed:
        sys.exit('Map suite failed for ' + ', '.join(failed))
    print('Map frontend/profile ownership matrix passed', flush=True)


if __name__ == '__main__':
    main()
