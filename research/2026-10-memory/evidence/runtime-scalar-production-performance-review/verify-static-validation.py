"""Saved bytes/document checks only: no imports of owner runners or subprocesses."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
ORIGINAL = OUT / 'original-inputs'
NEW = OUT / 'new-inputs'
RUN = Path('build/memory-research-list-bulk-production-validation/run-423km4w0')
SAVED = NEW / RUN
MASK = (1 << 64) - 1
SEED = 0x51F37
CASES = [(n, 0) for n in [0, 2, 31, 32, 1024, 8193]] + [(31, 1), (31, 2)]
TELEMETRY = ['rc_object_count', 'rc_bytes', 'rc_bounded_last_work',
             'rc_heap_allocation_count', 'rc_immortal_object_count', 'text_decode_count',
             'minyar_pool_allocation_count', 'minyar_pool_last_steps', 'minyar_pool_max_steps',
             'research_adds', 'research_takes', 'research_copies', 'research_copy_bytes',
             'research_guard_pending', 'research_retains', 'research_phase', 'research_event']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected(length, mode):
    # Authored from the stated input domain, not imported from calibration.
    words = [1] * (length + 1) if mode == 2 else [
        (SEED + i * 0x9e3779b97f4a7c15) & MASK for i in range(length)
    ] + [0xfedcba9876543210]
    result = 0xcbf29ce484222325
    for word in words:
        result = ((result ^ word) * 0x100000001b3) & MASK
    return result


def routine(text, name):
    match = re.search(r'^_' + name + r':\n.*?(?=^_[^\s:]+:|\Z)', text, re.M | re.S)
    assert match, name
    return match.group()


def apply_diff(text, patch):
    source = text.splitlines(True)
    lines = patch.splitlines(True)
    cursor = 0
    output = []
    i = 2
    while i < len(lines):
        header = re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@', lines[i])
        assert header, lines[i]
        start = int(header.group(1)) - 1
        output.extend(source[cursor:start])
        cursor = start
        i += 1
        while i < len(lines) and not lines[i].startswith('@@ '):
            line = lines[i]
            if line.startswith((' ', '-')):
                assert source[cursor] == line[1:], (cursor, source[cursor], line)
                cursor += 1
            if line.startswith((' ', '+')):
                output.append(line[1:])
            i += 1
    output.extend(source[cursor:])
    return ''.join(output)


def main():
    original_manifest = json.loads((OUT / 'original-inputs.json').read_text())
    new_manifest = json.loads((OUT / 'new-inputs.json').read_text())
    for manifest in [original_manifest, new_manifest]:
        for row in manifest['files']:
            if row.get('snapshot'):
                path = Path(row['snapshot'])
                if not path.is_absolute():
                    path = ROOT / path
                assert digest(path) == row['sha256'], row
    report = json.loads((SAVED / 'results.json').read_text())
    assert report['status'] == 'passed'
    assert len(report['checks']) == 92 and len(report['configurations']) == 6
    assert all(c['returncode'] == 0 and not c['timed_out'] for c in report['checks'])
    for check in report['checks']:
        if check.get('stdout_path'):
            assert digest(SAVED / check['stdout_path']) == check['stdout_sha256']
    old = ROOT / 'research/2026-10-memory/evidence/runtime-list-bulk-cpu/run-ws0ma9zu/baseline/tests/memory-research-list-bulk-cpu.c'
    patch = (ORIGINAL / 'research/2026-10-memory/runtime-list-bulk-production-fixture.patch').read_text()
    current = (ORIGINAL / 'tests/memory-research-list-bulk-cpu.c').read_text()
    assert apply_diff(old.read_text(), patch) == current
    clock_start = '    uint64_t start = cpu_nanoseconds();'
    clock_end = '    uint64_t duration = cpu_nanoseconds() - start;'
    def measured(text):
        return text[text.index(clock_start):text.index(clock_end) + len(clock_end)]
    assert measured(old.read_text()) == measured(current)
    assert re.search(r'^#define MINYAR_RC_TESTING 1$', (SAVED / 'original-config-macros.txt').read_text(), re.M)
    assert digest(old) == report['configuration_red']['original_fixture_sha256']
    configurations = []
    native_rows = []
    for configuration in report['configurations']:
        label = configuration['label']
        variant, profile, mode = label.split('-')
        directory = SAVED / variant
        source = directory / 'tests/memory-research-list-bulk-cpu.c'
        assert digest(source) == configuration['source_sha256'] == hashlib.sha256(current.encode()).hexdigest()
        assert digest(directory / 'runtime/minyar_runtime.c') == configuration['runtime_sha256']
        assert digest(directory / 'runtime/minyar_collections.h') == configuration['collections_sha256']
        for suffix, key in [('', 'binary_sha256'), ('-main.o', 'main_object_sha256'), ('-checksum.o', 'checksum_object_sha256')]:
            path = ROOT / RUN / variant / (label + suffix)
            manifest_row = next(r for r in new_manifest['files'] if r['path'] == str(path.relative_to(ROOT)))
            assert manifest_row['sha256'] == configuration[key]
        macros = (SAVED / (label + '-macros.txt')).read_text()
        for name in ['MINYAR_RC_TESTING', 'MINYAR_RESEARCH_COUNT', 'MINYAR_RESEARCH_TEST_ACCOUNTING', 'NDEBUG', 'MINYAR_COMPILER_ARENA']:
            assert not re.search(r'^#define ' + name + r'\b', macros, re.M), (label, name)
        assert '#define RC_ACCOUNT(expression) ((void)0)' in macros
        assert '#define MINYAR_BOUNDED_RC 1' in macros and '#define MINYAR_RC_POLL_BUDGET 32' in macros
        assert '#define ' + ('MINYAR_SYSTEM_HEAP 1' if profile == 'system' else 'MINYAR_BOUNDED_HEAP_BYTES 16777216') in macros
        body = (SAVED / (label + '-preprocessed.txt')).read_text()
        symbols = (SAVED / (label + '-symbols.txt')).read_text()
        assembly = (SAVED / (label + '-disassembly.txt')).read_text()
        for name in TELEMETRY:
            assert not re.search(r'\b_?' + name + r'\b', body + symbols + assembly), (label, name)
        assert '__assert_rtn' in body and '__assert_rtn' in symbols
        assert 'checksum == expected' in body and 'source->values[0] == old' in body
        assert '!rc_pending_count && !rc_frames && !rc_free_frames' in body
        assert ('!minyar_pool_used' in body) == (profile == 'fixed')
        main_code = routine(assembly, 'main')
        checksum_code = routine(assembly, 'research_checksum')
        assert re.search(r'\bbl\s+_research_checksum\b', main_code)
        assert all(re.search(r'\b' + instruction + r'\b', checksum_code) for instruction in ['ldr', 'eor', 'mul', 'subs'])
        assert 'b.ne' in checksum_code
        appended_code = routine(assembly, 'minyar_list_appended')
        assert '_minyar_list_add' in appended_code
        if variant == 'candidate' and mode == 'plain':
            assert '_memcpy' in appended_code and '_list_reserve' in appended_code
        selected = main_code + '\n' + checksum_code + '\n' + appended_code
        (OUT / (label + '-selected-code.txt')).write_text(selected)
        commands = {c['label']: c['command'] for c in report['checks'] if c['label'].startswith(label)}
        for phase in ['macros', 'preprocessed', 'checksum', 'compile', 'link']:
            command = commands[label + '-' + phase]
            assert configuration['effective_optimization'] in command
            assert '-DMINYAR_RC_POLL_BUDGET=32' in command
            assert not any('flto' in flag or 'NDEBUG' in flag or 'TEST_ACCOUNTING' in flag or 'RESEARCH_COUNT' in flag for flag in command)
            assert any('fsanitize=address,undefined' == flag.lstrip('-') for flag in command) == (mode == 'sanitize')
        assert '-c' in commands[label + '-checksum'] and '-c' in commands[label + '-compile']
        assert str(ROOT / RUN / variant / (label + '-main.o')) in commands[label + '-link']
        assert str(ROOT / RUN / variant / (label + '-checksum.o')) in commands[label + '-link']
        cases = []
        for check in report['checks']:
            if not re.match(re.escape(label) + r'-n\d+-mode\d+$', check['label']):
                continue
            length, repeats, reference_mode, seed, checksum = check['command'][-5:]
            length, repeats, reference_mode = int(length), int(repeats), int(reference_mode)
            assert repeats == 1 and int(seed, 16) == SEED
            expected_checksum = expected(length, reference_mode)
            assert int(checksum, 16) == expected_checksum
            observation = json.loads(check['stdout'])
            assert observation == check['observation']
            assert observation['kind'] == 'result' and observation['quiescent'] is True
            assert observation['repetitions'] == 1 and observation['checksum'] == f'{expected_checksum:016x}'
            assert observation['cpu_nanoseconds'] > 0
            assert 'recovered' not in observation
            cases.append((length, reference_mode))
            native_rows.append({'label': check['label'], 'case': [length, reference_mode], 'independent_checksum': f'{expected_checksum:016x}', 'normal_return': True, 'completed_RSS_recorded': 'peak_rss_bytes' in check})
        assert cases == CASES
        configurations.append({**configuration, 'independently_rehashed_original_binary_and_objects': True,
                               'macro_body_and_linked_telemetry_absence_verified': True,
                               'separate_checksum_calls_and_word_loop_verified': True})
    assert len(native_rows) == 48
    assert sum('sanitize' in r['label'] for r in native_rows) == 16
    baseline = SAVED / 'baseline/runtime/minyar_collections.h'
    candidate = SAVED / 'candidate/runtime/minyar_collections.h'
    scalar_patch = SAVED / 'candidate/candidate.patch'
    assert apply_diff(baseline.read_text(), scalar_patch.read_text()) == candidate.read_text()
    runtime_differences = [p.name for p in (SAVED / 'baseline/runtime').iterdir()
                           if p.read_bytes() != (SAVED / 'candidate/runtime' / p.name).read_bytes()]
    assert runtime_differences == ['minyar_collections.h']
    for path, expected_digest in report['production_frozen_hashes'].items():
        assert digest(Path(path)) == expected_digest
    result = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'Saved bytes and documentary correctness/configuration checks; no CPU estimation',
              'validation_results_sha256': digest(SAVED / 'results.json'),
              'minimal_fixture_diff_exact': True, 'measured_loop_byte_equal_to_old': True,
              'configuration_red_macro_verified': True,
              'scalar_patch_sha256': digest(scalar_patch),
              'runtime_differing_files': runtime_differences,
              'source_production_hashes_verified': len(report['production_frozen_hashes']),
              'configurations': configurations, 'native_rows': native_rows,
              'plain_executions': 32, 'sanitizer_executions': 16,
              'completed_RSS_compliance_certified': False,
              'resource_gap': 'No completed RSS data or check in any of48 native rows; taskpolicy -m128 is a pressure policy.',
              'new_performance_evidence': 'pending; these one-iteration CPU fields are not analyzed as performance observations',
              'native_or_compiler_execution': False}
    (OUT / 'static-validation-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['validation_results_sha256', 'minimal_fixture_diff_exact', 'measured_loop_byte_equal_to_old', 'plain_executions', 'sanitizer_executions', 'completed_RSS_compliance_certified']}))


if __name__ == '__main__':
    main()
