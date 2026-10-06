#!/usr/bin/env python3
"""Independent binary64 roundtrip, exact strings, bounds and formatter work checks."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shlex
import statistics
import struct
import subprocess
import tempfile
from llvm_sanitizer import prepare_llvm_for_link
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def bits(value: float) -> int:
    return struct.unpack('>Q', struct.pack('>d', value))[0]


def significant_digits(text: str) -> int:
    digits = list(Decimal(text).as_tuple().digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
    return len(digits)


def oracle_cases(count: int, seed: int) -> tuple[list[int], dict[int, str]]:
    golden_values = [
        (0.0, '0.0'), (-0.0, '-0.0'), (1.0, '1.0'), (-1.0, '-1.0'),
        (42.0, '42.0'), (-42.0, '-42.0'), (0.1, '0.1'), (0.1 + 0.2, '0.30000000000000004'),
        (1e-7, '0.0000001'), (1e-8, '1.0e-8'), (1e20, '100000000000000000000.0'),
        (1e21, '1.0e+21'), (9007199254740991.0, '9007199254740991.0'),
        (-9007199254740991.0, '-9007199254740991.0'),
        (9007199254740992.0, '9007199254740992.0'),
        (0.5, '0.5'), (1.25, '1.25'), (2.5, '2.5'),
        (float.fromhex('0x1.0000000000000p-788'), '6.142758149716505e-238'),
        (float.fromhex('0x0.0000000000001p-1022'), '5.0e-324'),
        (float.fromhex('0x1.fffffffffffffp+1023'), '1.7976931348623157e+308'),
        (float('inf'), 'Infinity'), (-float('inf'), '-Infinity'), (float('nan'), 'NaN')]
    golden = {bits(value): expected for value, expected in golden_values}
    generated = list(golden)
    # Stratify exponent transitions and neighbors of fast-path / notation cutoffs.
    for exponent in range(-1074, 1024):
        value = math.ldexp(1.0, exponent)
        below, above = math.nextafter(value, 0.0), math.nextafter(value, math.inf)
        generated += [bits(value), bits(-value), bits(below), bits(above), bits(-below), bits(-above)]
    for value in [0.0, 1.0, 1e-7, 1e-8, 1e20, 1e21, 2.0**52, 2.0**53]:
        generated += [bits(math.nextafter(value, -math.inf)), bits(math.nextafter(value, math.inf))]
    rng = random.Random(seed)
    generated += [rng.getrandbits(64) for _ in range(count)]
    generated += [bits(float(rng.randrange(-(2**53) + 1, 2**53))) for _ in range(count // 4)]
    return generated, golden


def verify_output(raw_bits: list[int], output: str, golden: dict[int, str]) -> None:
    lines = output.splitlines()
    if len(lines) != len(raw_bits):
        raise AssertionError(f'formatter returned {len(lines)} lines for {len(raw_bits)} values')
    for encoded, text in zip(raw_bits, lines):
        value = struct.unpack('>d', struct.pack('>Q', encoded))[0]
        if encoded in golden and text != golden[encoded]:
            raise AssertionError(f'golden {encoded:016x}: expected {golden[encoded]!r}, got {text!r}')
        if math.isnan(value):
            if text != 'NaN':
                raise AssertionError(f'NaN spelling changed: {text}')
        elif math.isinf(value):
            if text != ('-Infinity' if value < 0 else 'Infinity'):
                raise AssertionError(f'infinity spelling changed: {text}')
        else:
            if bits(float(text)) != encoded:
                raise AssertionError(f'bit roundtrip failed: {encoded:016x} -> {text!r}')
            if '.' not in text and 'e' not in text:
                raise AssertionError(f'Float lost its point/exponent: {text}')
            # CPython's independent shortest conversion bounds significant digits.
            if significant_digits(text) > significant_digits(repr(value)):
                raise AssertionError(f'not shortest: {encoded:016x} -> {text}, Python reference {value!r}')
        if len(text) >= 48:
            raise AssertionError(f'formatter exceeded its production buffer: {text}')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cc', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--compiler', type=Path,
                        default=Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc')))
    parser.add_argument('--cases', type=int, default=20000)
    parser.add_argument('--seed', type=lambda value: int(value, 0), default=0x4e554d45524943)
    parser.add_argument('--mode', choices=['native', 'sanitize', 'both'], default='both')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/numeric')
    parser.add_argument('--baseline-executable', type=Path)
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--iterations', type=int, default=100000)
    arguments = parser.parse_args()
    link_flags = shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', ''))
    runtime = Path(os.environ.get('MINYAR_TEST_RUNTIME', ROOT / 'runtime/minyar_runtime.c')).resolve()
    if arguments.cases < 1 or arguments.iterations < 1:
        parser.error('case and iteration counts must be positive')
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='campaign-', dir=arguments.output_dir.resolve()))
    report = {'seed': arguments.seed, 'platform': platform.platform(), 'machine': platform.machine(),
              'compiler': str(arguments.compiler.resolve()),
              'runtime': str(runtime), 'link_flags': link_flags,
              'numeric_header_sha256': hashlib.sha256((ROOT / 'runtime/minyar_numbers.h').read_bytes()).hexdigest(),
              'commands': [], 'results': []}

    def run(command, *, input=None, timeout=120, env=None):
        result = subprocess.run(command, cwd=ROOT, input=input, env=env, text=True, capture_output=True, timeout=timeout)
        report['commands'].append({'command': command, 'status': result.returncode,
                                   'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode or result.stderr:
            raise AssertionError(f'command failed: {command!r}; status={result.returncode}; stderr={result.stderr}')
        return result.stdout

    try:
        raw_bits, golden = oracle_cases(arguments.cases, arguments.seed)
        inputs = ''.join(f'{value:016x}\n' for value in raw_bits)
        (evidence / 'input.bits').write_text(inputs)
        source = ROOT / 'tests/numeric-formatting.min'
        llvm = evidence / 'numeric-formatting.ll'
        run([str(arguments.compiler.resolve()), str(source), str(llvm)])
        expected = source.with_suffix('.stdout').read_text()
        modes = ['native', 'sanitize'] if arguments.mode == 'both' else [arguments.mode]
        native = None
        for mode in modes:
            executable = evidence / f'numeric-{mode}'
            flags = ['-O2'] if mode == 'native' else ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            sanitizer_env = None
            language_llvm = llvm
            if mode == 'sanitize':
                sanitizer_env = dict(os.environ)
                sanitizer_env['ASAN_OPTIONS'] = os.environ.get('ASAN_OPTIONS', '') + ':halt_on_error=1:abort_on_error=1:detect_leaks=0'
                sanitizer_env['UBSAN_OPTIONS'] = os.environ.get('UBSAN_OPTIONS', '') + ':halt_on_error=1:print_stacktrace=1'
                language_llvm = llvm.with_name('numeric-formatting-sanitize.ll')
                language_llvm.write_bytes(llvm.read_bytes())
                prepare_llvm_for_link(language_llvm, flags)
            command = clang_command([arguments.cc, *flags, str(ROOT / 'tests/runtime-numeric.c'),
                                     *link_flags, '-o', str(executable)])
            run(command)
            stdout = run([str(executable)], input=inputs, env=sanitizer_env)
            verify_output(raw_bits, stdout, golden)
            run([str(executable), '--bounds'], env=sanitizer_env)
            budget = json.loads(run([str(executable), '--budget'], env=sanitizer_env))
            report['results'].append({'mode': mode, 'roundtrip_values': len(raw_bits), 'golden_values': len(golden), 'budget': budget})
            for optimization in ['-O0', '-O2']:
                language_executable = evidence / f'language-{mode}-{optimization[2:]}'
                instrumentation = [] if mode == 'native' else ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                run(clang_command([arguments.cc, optimization, *instrumentation, '-Wno-override-module',
                                   str(language_llvm), str(runtime), *link_flags,
                                   '-o', str(language_executable)]))
                actual = run([str(language_executable)], env=sanitizer_env)
                if actual != expected:
                    raise AssertionError(f'numeric aliases changed at {mode} {optimization}: {actual!r}')
            report['results'][-1]['language_aliases'] = ['O0', 'O2']
            if mode == 'native':
                native = executable
        if arguments.benchmark:
            if not native or not arguments.baseline_executable:
                raise AssertionError('benchmark requires native mode and --baseline-executable')
            report['benchmark'] = []
            report['baseline_executable_sha256'] = hashlib.sha256(arguments.baseline_executable.read_bytes()).hexdigest()
            for kind in ['integer', 'mixed', 'fractional']:
                samples = {'baseline': [], 'candidate': []}
                checksums = set()
                for sample in range(7):
                    # Alternate order to reduce systematic drift.
                    names = ['baseline', 'candidate'] if sample % 2 == 0 else ['candidate', 'baseline']
                    for name in names:
                        binary = arguments.baseline_executable if name == 'baseline' else native
                        result = json.loads(run([str(binary.resolve()), '--bench', kind, str(arguments.iterations)]))
                        samples[name].append(result)
                        checksums.add(result['checksum'])
                if len(checksums) != 1:
                    raise AssertionError(f'benchmark observable output changed for {kind}')
                baseline = statistics.median(row['cpu_seconds'] for row in samples['baseline'])
                candidate = statistics.median(row['cpu_seconds'] for row in samples['candidate'])
                report['benchmark'].append({'kind': kind, 'samples': samples,
                                            'baseline_median_seconds': baseline, 'candidate_median_seconds': candidate,
                                            'speedup': baseline / candidate})
        report['status'] = 'passed'
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        report.update(status='failed', failure=str(error))
        print(report['failure'])
    finally:
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'numeric evidence: {evidence}')
    if report['status'] != 'passed':
        return 1
    print(json.dumps(report['results'], indent=2))
    if report.get('benchmark'):
        print(json.dumps([{key: value for key, value in row.items() if key != 'samples'} for row in report['benchmark']], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
