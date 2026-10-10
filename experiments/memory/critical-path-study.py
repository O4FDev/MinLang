#!/usr/bin/env python3
"""Independent critical-path contracts and checked C++ comparisons.

No existing benchmark or baseline is modified. --measure reports only the
selected function, with setup and complete teardown outside its timer; these
results are never whole-program or hard-real-time guarantees.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'experiments/memory'
sys.path.insert(0, str(ROOT / 'tests'))
from llvm_sanitizer import prepare_llvm_for_link
from measurement_stats import paired_cpu_ratio_summary


def oracle(kind, count, seed):
    state, total, values = seed, 0, list(range(257))
    for _ in range(count):
        state = (state * 17 + 23) % 1000003
        if kind == 'book':
            index = state % len(values)
            values[index] = state
            total = (total + values[index]) % 1000003
        else:
            total = (total + state) % 1000003
    return total, values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measure', action='store_true')
    parser.add_argument('--samples', type=int, default=21)
    parser.add_argument('--count', type=int, default=1000000)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--cxx', default='clang++')
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    args = parser.parse_args()
    assert 3 <= args.samples <= 101 and 0 < args.count <= 100000000
    work = Path(tempfile.mkdtemp(prefix='minyar-critical-path-'))
    commands = []
    native_normalizations = []
    print(work, flush=True)

    def run(command, label, env=None):
        p = subprocess.run([str(x) for x in command], cwd=ROOT, text=True,
                           capture_output=True, env=env, timeout=240)
        (work / f'{label}.log').write_text(p.stdout + p.stderr)
        commands.append({'label': label, 'argv': [str(x) for x in command],
                         'returncode': p.returncode})
        if p.returncode:
            raise RuntimeError(f'{label} failed: {p.stdout}{p.stderr}')
        return p

    ir = work / 'fixture.ll'
    run([args.compiler.resolve(), HERE / 'critical-path.min', ir], 'compile-fixture')
    source_ir = ir.read_text()
    # This syntactic contract complements actual allocator instrumentation.
    required = ['criticalArithmetic', 'criticalBook']
    if not args.measure:
        required.append('criticalRecords')
    for name in required:
        body = re.search(rf'^define [^\n]* @{re.escape(".minyar.fn." + name)}\(.*?^}}', source_ir, re.M | re.S)
        assert body and '@minyar_rc_' not in body.group(), name
    source_ir, count = re.subn(r'(@)main(\()', r'\1fixtureMain\2', source_ir)
    assert count == 1
    ir.write_text(source_ir)
    configurations = ([('system', '-O2', False, False), ('system-lto', '-O2', False, True),
                       ('eager', '-O2', False, False), ('eager-lto', '-O2', False, True),
                       ('bounded-lto', '-O2', True, True)] if args.measure else
                      [('eager-o0', '-O0', False, False), ('eager-o2', '-O2', False, False),
                       ('bounded-o2', '-O2', True, False),
                       ('eager-sanitize', '-O1', False, False),
                       ('bounded-sanitize', '-O1', True, False)])
    executables = {}
    for name, optimization, bounded, lto in configurations:
        flags = [optimization, '-Wno-override-module']
        sanitize = name.endswith('sanitize')
        if sanitize:
            flags += ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        link_ir = ir
        if sanitize:
            link_ir = work / f'{name}-fixture.ll'
            link_ir.write_text(ir.read_text())
            prepare_llvm_for_link(link_ir, flags)
        defines = ['-DMINYAR_BOUNDED_HEAP=1'] if bounded else []
        if name.startswith('system'):
            defines += ['-DMINYAR_SYSTEM_HEAP=1']
        if not args.measure:
            defines += ['-DMINYAR_CRITICAL_ACCOUNTING=1']
        driver, cpp = work / f'{name}-driver.o', work / f'{name}-cpp.o'
        if lto:
            # Match the generated LLVM's generic target attributes so normal
            # runtime helpers can actually inline across the language boundary.
            for compiler, src, dest in [(args.cc, HERE / 'critical-path-driver.c', driver),
                                        (args.cxx, HERE / 'critical-path-cpp.cpp', cpp)]:
                ll = dest.with_suffix('.ll')
                run([compiler, *flags, *defines, '-S', '-emit-llvm', src, '-o', ll],
                    f'{name}-{src.stem}-ir')
                before = ll.read_text()
                before_path = ll.with_suffix('.before-normalization.ll')
                before_path.write_text(before)
                native_ir = re.sub(r'"(?:target-cpu|target-features|tune-cpu)"="[^"]*" ?', '', before)
                # C asm aliases suppress target mangling (LLVM \01). Canonical
                # names let LTO resolve them to the unchanged language IR.
                alias_pattern = r'@"\\01_?(\.minyar\.fn\.([A-Za-z0-9_]+))"'
                aliases = re.findall(alias_pattern, native_ir)
                expected_aliases = {'criticalArithmetic', 'criticalBook', 'criticalRecords'} if src.suffix == '.c' else set()
                assert {name for _, name in aliases} == expected_aliases, (src, aliases)
                native_ir, replaced = re.subn(alias_pattern, r'@\1', native_ir)
                assert replaced == len(aliases)
                ll.write_text(native_ir)
                native_normalizations.append({'before': str(before_path), 'after': str(ll),
                    'before_sha256': hashlib.sha256(before.encode()).hexdigest(),
                    'after_sha256': hashlib.sha256(native_ir.encode()).hexdigest(),
                    'alias_replacements': replaced, 'alias_names': sorted(expected_aliases),
                    'method': 'Remove generic target attributes and canonicalize only C asm language aliases for LLVM LTO resolution.'})
                run([compiler, *flags, '-flto', '-c', ll, '-o', dest], f'{name}-{src.stem}-object')
        else:
            run([args.cc, *flags, *defines, '-c', HERE / 'critical-path-driver.c', '-o', driver],
                f'{name}-driver')
            run([args.cxx, *flags, '-c', HERE / 'critical-path-cpp.cpp', '-o', cpp], f'{name}-cpp')
        executable = work / name
        run([args.cxx, *flags, *(['-flto'] if lto else []), link_ir, driver, cpp, '-o', executable],
            f'{name}-link')
        executables[name] = executable
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
    sources = ['compiler/compiler.min', 'runtime/minyar_runtime.c',
               *(str(path.relative_to(ROOT)) for path in sorted((ROOT / 'runtime').glob('*.h'))),
               'experiments/memory/critical-path.min', 'experiments/memory/critical-path-driver.c',
               'experiments/memory/critical-path-cpp.cpp', 'experiments/memory/critical-path-study.py',
               'experiments/memory/measurement_stats.py', 'tests/llvm_symbols.h']
    result = {'directory': str(work), 'mode': 'measurement' if args.measure else 'correctness',
              'compiler_executable': str(args.compiler.resolve()),
              'compiler_sha256': hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
              'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
              'commands': commands, 'native_ir_normalizations': native_normalizations, 'configurations': {},
              'limitations': ['Only the function is timed; setup and full teardown are outside timing.',
                              'A 257-entry prepared integer List is not a complete trading system.',
                              'No OS isolation, hard deadline, physical memory residency or embedded ABI is proved.',
                              'C++ arithmetic and indexing retain corresponding overflow/bounds checks.',
                              'Bootstrap intervals resample observed pairs as independent; host trends require separate analysis.']}
    if args.measure:
        seed = 271828
        expected = {kind: oracle(kind, args.count, seed) for kind in ('arithmetic', 'book', 'records')}
        for name, executable in executables.items():
            entries = result['configurations'][name] = {}
            for kind in ('arithmetic', 'book', 'records'):
                samples = {'cpp': [], 'minyar': []}
                warmup = {}
                for i in range(args.samples + 1):
                    for language in (('cpp', 'minyar') if i % 2 else ('minyar', 'cpp')):
                        p = run([executable, language, kind, args.count, seed],
                                f'{name}-{kind}-{language}-{i}', env)
                        row = json.loads(p.stdout)
                        assert (row['result'], row['values']) == expected[kind]
                        if i:
                            samples[language].append(row)
                        else:
                            warmup[language] = row
                paired_ratio = paired_cpu_ratio_summary(
                    [row['cpu_ns'] for row in samples['minyar']],
                    [row['cpu_ns'] for row in samples['cpp']])
                paired_ratio.update(numerator='minyar', denominator='cpp')
                entries[kind] = {'samples': samples, 'warmup_samples': warmup, 'median_cpu_ns': {
                    language: statistics.median(row['cpu_ns'] for row in rows)
                    for language, rows in samples.items()}, 'paired_cpu_ratio': paired_ratio}
                print(name, kind, entries[kind]['median_cpu_ns'], flush=True)
    else:
        rng = random.Random(9102026)
        cases = [(0, 0), (1, 1000002), (257, 1), (1027, 999983)]
        cases += [(rng.randrange(2, 1500), rng.randrange(1000003)) for _ in range(4)]
        for name, executable in executables.items():
            entries = []
            for kind in ('arithmetic', 'book', 'records'):
                for index, (count, seed) in enumerate(cases):
                    expected = oracle(kind, count, seed)
                    for language in ('minyar', 'cpp'):
                        p = run([executable, language, kind, count, seed],
                                f'{name}-{kind}-{language}-{index}', env)
                        row = json.loads(p.stdout)
                        assert (row['result'], row['values']) == expected
                        entries.append({'kind': kind, 'language': language, 'count': count,
                                        'system_operations': row['system_operations'],
                                        'pool_allocations': row['pool_allocations']})
            result['configurations'][name] = entries
            print(f'{name}: 48 oracle/allocator checks passed', flush=True)
    destination = args.output or work / 'results.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(destination, flush=True)


if __name__ == '__main__':
    main()
