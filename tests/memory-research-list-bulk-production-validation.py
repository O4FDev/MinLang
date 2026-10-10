#!/usr/bin/env python3
"""Validate actual testing-disabled scalar timing configurations, without acquisition."""
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('calibration', ROOT / 'tests/memory-research-list-bulk-cpu-calibration.py')
calibration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(calibration)
bulk = calibration.bulk
TELEMETRY = ['rc_object_count', 'rc_bytes', 'rc_bounded_last_work', 'rc_heap_allocation_count',
             'minyar_pool_allocation_count', 'minyar_pool_last_steps', 'minyar_pool_max_steps']


def main():
    parent = ROOT / 'build/memory-research-list-bulk-production-validation'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'scope': 'Configuration and one-iteration correctness only; no CPU estimates',
              'checks': [], 'configurations': [], 'plain_executions': 0, 'sanitizer_executions': 0}
    frozen = {str(p): bulk.digest(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def limits():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))

    def execute(label, command, large=False):
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, preexec_fn=limits, env=env)
        timeout = False
        try:
            out, err = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(process.pid, signal.SIGKILL)
            out, err = process.communicate()
        row = {'label': label, 'command': command, 'returncode': process.returncode,
               'timed_out': timeout, 'stderr': err}
        if large:
            target = evidence / (label + '.txt')
            target.write_text(out)
            row.update(stdout_path=target.name, stdout_sha256=bulk.digest(target))
        else:
            row['stdout'] = out
        report['checks'].append(row)
        save()
        assert not timeout and process.returncode == 0, row
        return out, row

    try:
        execute('toolchain', ['clang', '--version'])
        old = ROOT / 'research/2026-10-memory/evidence/runtime-list-bulk-cpu/run-ws0ma9zu/baseline/tests/memory-research-list-bulk-cpu.c'
        old_macros, _ = execute('original-config-macros', ['clang', '-E', '-dM', '-DMINYAR_SYSTEM_HEAP=1',
                                                       '-DMINYAR_RC_POLL_BUDGET=32', str(old)], True)
        assert re.search(r'^#define MINYAR_RC_TESTING\b', old_macros, re.M)
        report['configuration_red'] = {'original_fixture_sha256': bulk.digest(old),
                                      'expected': 'MINYAR_RC_TESTING absent', 'actual': 'defined 1',
                                      'disposition': 'Expected configuration oracle rejection; preprocessing succeeds; not a runtime red'}
        for variant in ['baseline', 'candidate']:
            directory = evidence / variant
            shutil.copytree(ROOT / 'runtime', directory / 'runtime', ignore=shutil.ignore_patterns('native'))
            (directory / 'tests').mkdir()
            for name in ['memory-research-list-bulk-cpu.c', 'memory-research-list-bulk-checksum.c',
                         'memory-research-list-bulk.py', 'memory-research-list-bulk-cpu-calibration.py',
                         Path(__file__).name, 'clang_helpers.py']:
                shutil.copyfile(ROOT / 'tests' / name, directory / 'tests' / name)
            if variant == 'candidate':
                bulk.candidate(directory / 'runtime')
            for profile, sanitizer in [('system', False), ('fixed', False), ('system', True)]:
                label = variant + '-' + profile + ('-sanitize' if sanitizer else '-plain')
                defines = ['-DMINYAR_SYSTEM_HEAP=1'] if profile == 'system' else [
                    '-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=16777216']
                flags = ['-std=c11', '-O1' if sanitizer else '-O2', *defines, '-DMINYAR_RC_POLL_BUDGET=32']
                if sanitizer:
                    flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
                source = directory / 'tests/memory-research-list-bulk-cpu.c'
                macros, _ = execute(label + '-macros', ['clang', *flags, '-E', '-dM', str(source)], True)
                for macro in ['MINYAR_RC_TESTING', 'MINYAR_RESEARCH_COUNT', 'MINYAR_RESEARCH_TEST_ACCOUNTING', 'NDEBUG']:
                    assert not re.search(r'^#define ' + macro + r'\b', macros, re.M), macro
                body, _ = execute(label + '-preprocessed', ['clang', *flags, '-E', str(source)], True)
                assert all(not re.search(r'\b' + word + r'\b', body) for word in TELEMETRY)
                checksum = directory / (label + '-checksum.o')
                main_object = directory / (label + '-main.o')
                binary = directory / label
                execute(label + '-checksum', clang_command(['clang', *flags, '-c',
                        str(directory / 'tests/memory-research-list-bulk-checksum.c'), '-o', str(checksum)]))
                execute(label + '-compile', clang_command(['clang', *flags, '-Wall', '-Wextra', '-Werror',
                                                          '-c', str(source), '-o', str(main_object)]))
                execute(label + '-link', clang_command(['clang', *flags, str(main_object), str(checksum), '-o', str(binary)]))
                symbols, _ = execute(label + '-symbols', ['nm', '-a', str(binary)], True)
                disassembly, _ = execute(label + '-disassembly', ['otool', '-tvV', str(binary)], True)
                assert all(not re.search(r'\b_?' + word + r'\b', symbols + disassembly) for word in TELEMETRY)
                assert '_research_checksum' in symbols and '_research_checksum' in disassembly
                report['configurations'].append({'label': label, 'actual_macros_file': label + '-macros.txt',
                    'source_sha256': bulk.digest(source), 'runtime_sha256': bulk.digest(directory / 'runtime/minyar_runtime.c'),
                    'collections_sha256': bulk.digest(directory / 'runtime/minyar_collections.h'),
                    'main_object_sha256': bulk.digest(main_object), 'checksum_object_sha256': bulk.digest(checksum),
                    'binary_sha256': bulk.digest(binary), 'testing_and_observers_absent': True, 'semantic_asserts_enabled': True,
                    'effective_optimization': '-O1' if sanitizer else '-O2', 'sanitizer_scope': 'native C ASan+UBSan; LSan disabled' if sanitizer else 'none'})
                for length, mode in calibration.CASES:
                    expected = calibration.expected(length, mode)
                    out, row = execute(f'{label}-n{length}-mode{mode}', ['/usr/sbin/taskpolicy', '-m', '128',
                        str(binary), str(length), '1', str(mode), f'{calibration.SEED:x}', f'{expected:x}'])
                    observations = [json.loads(line) for line in out.splitlines() if line.startswith('{')]
                    assert len(observations) == 1
                    result = observations[0]
                    assert result['checksum'] == f'{expected:016x}' and result['quiescent'] and result['repetitions'] == 1
                    row['observation'] = result
                    report['sanitizer_executions' if sanitizer else 'plain_executions'] += 1
                    save()
        assert report['plain_executions'] == 32 and report['sanitizer_executions'] == 16
        assert all(bulk.digest(Path(path)) == sha for path, sha in frozen.items())
        report.update(status='passed', production_frozen_hashes=frozen,
                      recovery_limitation='System quiescence is not independently counted physical allocation recovery; fixed poolused zero asserted')
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        save()
        print('Results: ' + str(evidence / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
