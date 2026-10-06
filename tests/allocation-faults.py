#!/usr/bin/env python3
"""Sweep actual system allocation/resize failures and force moving realloc.

Each ordinal executes in a fresh process. Fatal OOM does not promise unwinding;
successful executions use the existing final-drain ownership invariant.
"""
from clang_helpers import clang_command
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from llvm_sanitizer import prepare_llvm_for_link
from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
OOM = b'Minyar stopped: the computer ran out of memory.\n'
CASES = {
    'text': ('''function grow(text: Text): Text {
let result = text
let index = 0
while index < 12 { result = result + text; index = index + 1 }
return result
}
let source = grow("é🙂")
let view = source.slice(1, source.length - 1)
let parts = [view, source, view]
let result = joinText(parts)
print(result.length == view.length * 2 + source.length)
print(source.length)
''', b'true\n26\n'),
    'list': ('''function append(values: List<Text>, alias: List<Text>) {
let index = 0
while index < 40 { values.add("value" + Text(index)); index = index + 1 }
print(alias[0])
print(alias[39])
}
let values: List<Text> = []
append(values, values)
let alias = values
values[0] = values[39]
print(alias[0])
''', b'value0\nvalue39\nvalue39\n'),
    'records': ('''record Leaf { label: Text; values: List<Integer> }
record Tree { leaf: Leaf; children: List<Leaf> }
function make(index: Integer): Leaf { return Leaf { label: "leaf" + Text(index); values: [index, index + 1] } }
let first = make(10)
let tree = Tree { leaf: first; children: [first, make(20), make(30)] }
let alias = tree.children
print(tree.leaf.label)
print(alias[2].values[1])
''', b'leaf10\n31\n'),
}


COMPILER_CASES = {
    'assignment': ('let value = 1\n', b''),
    'file-program': ('''function foo() {}
let items = ["x"]
let text = "aaa"
let index = 0
while index < items.length { text = text + items[index]; index = index + 1 }
foo()
print(text)
''', b'aaax\n'),
}


def require_fault(result, report):
    if report.get('fired') != 1:
        raise AssertionError('Requested allocation failpoint did not fire exactly once')
    if result.returncode != 1 or result.stderr != OOM or report.get('fatal_exit') != 1:
        raise AssertionError(f'Uncontrolled OOM: {result.returncode}, {result.stderr!r}, {report}')


def campaign(args):
    if sys.flags.optimize:
        raise RuntimeError('Allocation campaign requires Python assertions; do not use -O')
    modes = ('native', 'sanitize') if args.mode == 'both' else (args.mode,)
    compiler = args.compiler.resolve()
    rows = []
    inputs = [compiler, Path(__file__), ROOT / 'tests/llvm_sanitizer.py', ROOT / 'tests/test_evidence.py',
              ROOT / 'tests/allocation-fault-runtime.c',
              ROOT / 'runtime/minyar_runtime.c', *sorted((ROOT / 'runtime').glob('*.h'))]
    if args.scope == 'compiler':
        inputs += [args.compiler_ir.resolve(), ROOT / 'build/minyar-runtime.o']
    with Evidence('allocation-faults', inputs=inputs,
                  controls={'modes': modes, 'budgets': [1, 32], 'scope': args.scope}) as evidence:
        def run(command, **kwargs):
            return evidence.run(command, timeout=60, **kwargs)

        def execute(executable, label, env, arguments=()):
            report_path = evidence.path / (label + '.json')
            report_path.unlink(missing_ok=True)
            result = run([executable, *arguments], env={**env, 'MINYAR_ALLOCATION_REPORT': str(report_path)})
            if not report_path.is_file():
                raise AssertionError(f'Missing allocation instrumentation: {label}: {result.stderr!r}')
            return result, json.loads(report_path.read_text())

        def byte_sweep(executable, label, env, baseline, expected, arguments=(), output=None, reference=None):
            # Independently reconstruct every prefix peak from the complete trace.
            live = high = allocations = resizes = 0
            peaks = []
            for index, (kind, size, previous_live) in enumerate(baseline['events']):
                assert previous_live == live and size >= 0, (index, previous_live, live)
                if kind in (1, 2):
                    allocations += kind == 1
                    resizes += kind == 2
                    live += size
                    if live > high:
                        high = live
                        peaks.append({'required': high, 'events': index + 1,
                                      'allocations': allocations, 'resizes': resizes})
                else:
                    assert kind == 3 and size <= live, (index, kind, size, live)
                    live -= size
            assert peaks and peaks == baseline['peaks'], (peaks, baseline)
            assert (live, high, allocations, resizes) == (baseline['live_bytes'], baseline['peak_required'],
                                                         baseline['allocations'], baseline['resizes']), baseline
            budgets = sorted({0, high, high + 1, *(peak['required'] - 1 for peak in peaks)})
            failures = successes = 0
            for budget in budgets:
                if output is not None:
                    output.unlink(missing_ok=True)
                result, report = execute(executable, f'{label}-bytes-{budget}',
                                         {**env, 'MINYAR_FAIL_BYTES': str(budget)}, arguments)
                first_failure = next((peak for peak in peaks if peak['required'] > budget), None)
                if first_failure:
                    require_fault(result, report)
                    assert expected.startswith(result.stdout), (label, budget, result.stdout)
                    assert report['failed_required'] == first_failure['required'], report
                    assert (report['allocations'], report['resizes']) == (first_failure['allocations'], first_failure['resizes']), report
                    assert report['events'] == baseline['events'][:first_failure['events']], 'Byte-budget run diverged from baseline trace prefix'
                    assert report['live_bytes'] == report['events'][-1][2], report
                    assert report['peak_required'] == first_failure['required'], report
                    assert report['peaks'] == peaks[:peaks.index(first_failure) + 1], report
                    assert report['moved'] == sum(event[0] == 2 for event in report['events'][:-1]), report
                    failures += 1
                else:
                    assert (result.returncode, result.stdout, result.stderr) == (0, expected, b''), (result, report)
                    assert report == baseline, 'Byte-budget success changed allocation/free schedule'
                    if output is not None:
                        assert output.read_bytes() == reference.read_bytes(), 'Byte budget changed emitted LLVM'
                    successes += 1
            return {'byte_budget_failures': failures, 'byte_budget_successes': successes,
                    'byte_boundary_classes': len(peaks), 'byte_budgets': budgets,
                    'peak_payload_bytes': high, 'trace_events': len(baseline['events']),
                    'trace_sha256': hashlib.sha256(json.dumps(baseline['events']).encode()).hexdigest()}

        for mode in modes:
            flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if mode == 'sanitize' else []
            env = {k: v for k, v in os.environ.items()
                   if k not in ('MINYAR_FAIL_ALLOCATION', 'MINYAR_FAIL_RESIZE', 'MINYAR_ALLOCATION_REPORT',
                                'MINYAR_FAULT_CORRUPT_SUFFIX', 'MINYAR_FAULT_CORRUPT_BYTE',
                                'MINYAR_FAULT_CORRUPT_ARENA', 'MINYAR_FAIL_BYTES')}
            env.update(ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            probe = evidence.path / ('probe-' + mode)
            run(clang_command([args.clang, '-std=c11', '-O1', '-g', *flags, '-DMINYAR_FAULT_SELF_TEST',
                 ROOT / 'tests/allocation-fault-runtime.c', '-o', probe]), check=True)
            for label, extra, status, fired, moved in (
                ('normal', {}, 0, 0, 2),
                ('allocate', {'MINYAR_FAIL_ALLOCATION': '1'}, 91, 1, 0),
                ('calloc', {'MINYAR_FAIL_ALLOCATION': '2'}, 93, 1, 2),
                ('resize', {'MINYAR_FAIL_RESIZE': '1'}, 92, 1, 0),
                ('shrink', {'MINYAR_FAIL_RESIZE': '2'}, 96, 1, 1),
                ('bytes-zero', {'MINYAR_FAIL_BYTES': '0'}, 91, 1, 0),
                ('bytes-grow', {'MINYAR_FAIL_BYTES': '16'}, 92, 1, 0),
                ('bytes-before-peak', {'MINYAR_FAIL_BYTES': '47'}, 92, 1, 0),
                ('bytes-peak', {'MINYAR_FAIL_BYTES': '48'}, 0, 0, 2),
                ('bytes-above', {'MINYAR_FAIL_BYTES': '49'}, 0, 0, 2),
            ):
                result, report = execute(probe, f'probe-{mode}-{label}', {**env, **extra})
                assert result.returncode == status and not result.stderr, (result, report)
                assert report['fired'] == fired and report['moved'] == moved, report
                if label in ('normal', 'bytes-peak', 'bytes-above'):
                    assert report['events'] == [[1, 16, 0], [2, 32, 16], [3, 16, 48],
                                                [2, 8, 32], [3, 32, 40], [3, 8, 8],
                                                [1, 16, 0], [3, 16, 16]], report
                    assert (report['allocations'], report['resizes'], report['live_bytes'],
                            report['peak_required']) == (2, 2, 0, 48), report
                    assert report['peaks'] == [
                        {'required': 16, 'events': 1, 'allocations': 1, 'resizes': 0},
                        {'required': 48, 'events': 2, 'allocations': 1, 'resizes': 1}], report
                if label == 'bytes-before-peak':
                    assert report['failed_required'] == 48, report
            for operation in ('free', 'resize'):
                for byte in (0, 15):
                    extra = {'MINYAR_FAULT_CORRUPT_BYTE': '15'} if byte else {}
                    result, report = execute(probe, f'probe-{mode}-corrupt-{operation}-{byte}',
                                             {**env, **extra, 'MINYAR_FAULT_CORRUPT_SUFFIX': operation})
                    assert result.returncode == 94 and result.stdout == b'', (result, report)
                    assert result.stderr == b'allocation suffix corrupted\n', (result, report)
                    assert report['fatal_exit'] == 1 and report['fired'] == 0, report
            for index, ordinal in enumerate(('0', '-1', ' -1', '+1', '1junk', '18446744073709551616')):
                result, report = execute(probe, f'probe-{mode}-invalid-ordinal-{index}',
                                         {**env, 'MINYAR_FAIL_ALLOCATION': ordinal})
                assert result.returncode == 90 and result.stdout == b'', (result, report)
                assert result.stderr == b'invalid allocation fault ordinal\n', (result, report)
            # Prove a missing or swallowed fault cannot produce a passing campaign.
            for report, result in (({'fired': 0}, subprocess.CompletedProcess([], 1, b'', OOM)),
                                   ({'fired': 1, 'fatal_exit': 0}, subprocess.CompletedProcess([], 0, b'', b''))):
                try:
                    require_fault(result, report)
                except AssertionError:
                    pass
                else:
                    raise AssertionError('Fault oracle accepted an ineffective or swallowed failpoint')

            compiler_object = None
            if args.scope == 'compiler':
                arena_probe = evidence.path / ('arena-probe-' + mode)
                run(clang_command([args.clang, '-std=c11', '-O1', '-g', *flags, '-DMINYAR_COMPILER_ARENA',
                     '-DMINYAR_FAULT_ARENA_SELF_TEST', ROOT / 'tests/allocation-fault-runtime.c',
                     '-o', arena_probe]), check=True)
                result, report = execute(arena_probe, f'arena-probe-{mode}-normal', env)
                assert (result.returncode, result.stdout, result.stderr) == (0, b'', b''), (result, report)
                assert report['allocations'] == 8 and report['fired'] == report['fatal_exit'] == 0, report
                for block in range(1, 9):
                    result, report = execute(arena_probe, f'arena-probe-{mode}-corrupt-{block}',
                                             {**env, 'MINYAR_FAULT_CORRUPT_ARENA': str(block)})
                    assert (result.returncode, result.stdout, result.stderr) == (94, b'', b'allocation suffix corrupted\n'), (result, report)
                    assert report['fatal_exit'] == 1 and report['fired'] == 0, report
                compiler_llvm = evidence.path / f'compiler-{mode}.ll'
                compiler_llvm.write_bytes(args.compiler_ir.read_bytes())
                prepare_llvm_for_link(compiler_llvm, flags)
                compiler_object = compiler_llvm.with_suffix('.o')
                run(clang_command([args.clang, '-O2', '-g', *flags, '-Wno-override-module', '-c',
                     compiler_llvm, '-o', compiler_object]), check=True)
            profiles = [('system', 1), ('system', 32)]
            if args.scope == 'compiler':
                profiles.append(('arena', 0))
            for profile, budget in profiles:
                runtime = evidence.path / f'runtime-{mode}-{profile}-{budget}.o'
                profile_flags = ['-DMINYAR_COMPILER_ARENA'] if profile == 'arena' else [f'-DMINYAR_RC_POLL_BUDGET={budget}']
                run(clang_command([args.clang, '-std=c11', '-O1', '-g', *flags,
                     *profile_flags, '-c',
                     ROOT / 'tests/allocation-fault-runtime.c', '-o', runtime]), check=True)
                if args.scope == 'compiler':
                    fault_compiler = runtime.with_suffix('.compiler')
                    run(clang_command([args.clang, '-O2', *flags, compiler_object, runtime, '-o', fault_compiler]), check=True)
                    for name, (source, expected) in COMPILER_CASES.items():
                        label = f'compiler-{name}-{mode}-{profile}-k{budget}'
                        path = evidence.path / (label + '.min')
                        path.write_text(source)
                        llvm = path.with_suffix('.ll')
                        reference = path.with_suffix('.reference.ll')
                        reference_result = run([compiler, path, reference], env=env)
                        assert (reference_result.returncode, reference_result.stdout, reference_result.stderr) == (0, b'', b''), reference_result
                        result, baseline = execute(fault_compiler, label + '-baseline', env, [path, llvm])
                        assert (result.returncode, result.stdout, result.stderr) == (0, b'', b''), (result, baseline)
                        assert baseline['allocations'] > 0 and baseline['fired'] == baseline['fatal_exit'] == 0, baseline
                        assert baseline['resizes'] == baseline['moved'], baseline
                        assert llvm.read_bytes() == reference.read_bytes(), 'Instrumented compiler changed emitted LLVM'
                        program = path.with_suffix('.program')
                        run(clang_command([args.clang, '-O2', '-Wno-override-module', llvm,
                             ROOT / 'build/minyar-runtime.o', '-o', program]), check=True)
                        executed = run([program], env=env)
                        assert (executed.returncode, executed.stdout, executed.stderr) == (0, expected, b''), executed
                        for counter, variable in (('allocations', 'MINYAR_FAIL_ALLOCATION'), ('resizes', 'MINYAR_FAIL_RESIZE')):
                            for ordinal in range(1, baseline[counter] + 1):
                                llvm.unlink(missing_ok=True)
                                result, report = execute(fault_compiler, f'{label}-{counter}-{ordinal}',
                                                         {**env, variable: str(ordinal)}, [path, llvm])
                                require_fault(result, report)
                                assert result.stdout == b'', result
                            llvm.unlink(missing_ok=True)
                            result, report = execute(fault_compiler, f'{label}-{counter}-beyond',
                                                     {**env, variable: str(baseline[counter] + 1)}, [path, llvm])
                            assert (result.returncode, result.stdout, result.stderr) == (0, b'', b''), (result, report)
                            assert report == baseline and llvm.read_bytes() == reference.read_bytes(), (report, baseline)
                        byte_results = byte_sweep(fault_compiler, label, env, baseline, b'',
                                                  [path, llvm], llvm, reference)
                        rows.append({'case': name, 'mode': mode, 'profile': profile, 'budget': budget,
                                     'allocation_failures': baseline['allocations'],
                                     'resize_failures': baseline['resizes'], 'forced_moves': baseline['moved'],
                                     **byte_results})
                        print(label + ': ' + json.dumps(rows[-1]), flush=True)
                    continue
                for name, (source, expected) in CASES.items():
                    label = f'{name}-{mode}-k{budget}'
                    path = evidence.path / (label + '.min')
                    llvm = path.with_suffix('.ll')
                    executable = evidence.path / label
                    path.write_text(source)
                    run([compiler, path, llvm], check=True)
                    prepare_llvm_for_link(llvm, flags)
                    run(clang_command([args.clang, '-O2', '-g', *flags, '-Wno-override-module', llvm, runtime, '-o', executable]), check=True)
                    result, baseline = execute(executable, label + '-baseline', env)
                    assert result.returncode == 0 and result.stdout == expected and not result.stderr, (result, baseline)
                    assert baseline['fired'] == 0 and baseline['allocations'] > 0 and baseline['fatal_exit'] == 0, baseline
                    assert baseline['resizes'] == baseline['moved'], baseline
                    # Some constructor-only cases need no resize; list/text must exercise it.
                    if name in ('list', 'text'):
                        assert baseline['moved'] > 0, 'Moving-resize stress did not execute'
                    for counter, variable in (('allocations', 'MINYAR_FAIL_ALLOCATION'), ('resizes', 'MINYAR_FAIL_RESIZE')):
                        for ordinal in range(1, baseline[counter] + 1):
                            result, report = execute(executable, f'{label}-{counter}-{ordinal}', {**env, variable: str(ordinal)})
                            require_fault(result, report)
                            assert expected.startswith(result.stdout), (label, ordinal, result.stdout)
                        # An ordinal beyond the baseline is not coverage; it must remain dormant.
                        result, report = execute(executable, f'{label}-{counter}-beyond', {**env, variable: str(baseline[counter] + 1)})
                        assert result.returncode == 0 and result.stdout == expected and not result.stderr, (result, report)
                        assert report == baseline, ('Nondeterministic allocation path', report, baseline)
                    byte_results = byte_sweep(executable, label, env, baseline, expected)
                    rows.append({'case': name, 'mode': mode, 'budget': budget,
                                 'allocation_failures': baseline['allocations'],
                                 'resize_failures': baseline['resizes'], 'forced_moves': baseline['moved'],
                                 **byte_results})
                    print(label + ': ' + json.dumps(rows[-1]), flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        configurations = sorted({flag[1:] for command in evidence.commands
                                 if '-o' in command['command'] and '-c' not in command['command']
                                 for flag in command['command'] if flag in ('-O0', '-O1', '-O2', '-O3', '-Os')})
        args.output.write_text(json.dumps({'status': 'passed', 'cases': rows,
                                          'configurations': configurations}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--mode', choices=('native', 'sanitize', 'both'), default='both')
    parser.add_argument('--scope', choices=('runtime', 'compiler'), default='runtime')
    parser.add_argument('--compiler-ir', type=Path, default=ROOT / 'build/compiler-stage2.ll')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/allocation-faults.json')
    campaign(parser.parse_args())
