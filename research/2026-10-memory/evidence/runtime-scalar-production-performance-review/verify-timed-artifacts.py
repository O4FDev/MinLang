"""Check archived acquisition bytes, commands, and saved code. No native tools."""
from pathlib import Path
import ast
import datetime
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REL = Path('build/memory-research-list-bulk-production-cpu/run-x3798c1e')
RUN = OUT / 'timed-inputs' / REL
TELEMETRY = ['rc_object_count', 'rc_bytes', 'rc_heap_allocation_count', 'rc_bounded_last_work',
             'rc_immortal_object_count', 'text_decode_count', 'minyar_pool_allocation_count',
             'minyar_pool_last_steps', 'minyar_pool_max_steps', 'research_phase',
             'research_adds', 'research_takes', 'research_copies', 'research_copy_bytes',
             'research_guard_pending', 'research_retains', 'research_event']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def routine(text, name):
    match = re.search(r'^_' + name + r':\n.*?(?=^_[^\s:]+:|\Z)', text, re.M | re.S)
    assert match, name
    return match.group()


def main():
    report = json.loads((RUN / 'results.json').read_text())
    manifest = json.loads((OUT / 'timed-inputs.json').read_text())
    captured = {row['path']: row for row in manifest['files']}
    for row in manifest['files']:
        if row.get('snapshot'):
            assert digest(ROOT / row['snapshot']) == row['sha256']
    freeze = []
    for filename, declared in report['frozen_artifacts'].items():
        relative = Path(filename).relative_to(ROOT)
        assert str(relative) in captured, relative
        entry = captured[str(relative)]
        assert entry['sha256'] == declared, filename
        freeze.append({'path': str(relative), 'sha256': declared,
                       'reviewer_independent_original_byte_hash': entry['snapshot'] is None})
    assert len(freeze) == 67
    assert json.loads((RUN / 'inputs-and-order.json').read_text()) == report['planned_pairs']
    release = json.loads((OUT / 'release-inputs.json').read_text())
    released = {row['path']: row for row in release['files']}
    assert digest(RUN / 'proposal.json') == released['research/2026-10-memory/runtime-list-bulk-production-cpu-proposal.json']['sha256']
    proposal = json.loads((RUN / 'proposal.json').read_text())
    assert proposal['runner_sha256'] == released['tests/memory-research-list-bulk-cpu.py']['sha256']
    original = OUT / 'original-inputs'
    different = []
    for p in (RUN / 'baseline/runtime').iterdir():
        assert p.read_bytes() == (original / 'runtime' / p.name).read_bytes(), p
        if p.read_bytes() != (RUN / 'candidate/runtime' / p.name).read_bytes():
            different.append(p.name)
    assert different == ['minyar_collections.h']
    baseline = (RUN / 'baseline/runtime/minyar_collections.h').read_text()
    patch = (RUN / 'candidate/candidate.patch').read_text()
    candidate = (RUN / 'candidate/runtime/minyar_collections.h').read_text()
    # Exact diff reconstruction does not execute the owner's patch application code.
    import difflib
    reconstructed_patch = ''.join(difflib.unified_diff(baseline.splitlines(True), candidate.splitlines(True),
                               fromfile='a/runtime/minyar_collections.h', tofile='b/runtime/minyar_collections.h'))
    assert reconstructed_patch == patch
    assert hashlib.sha256(patch.encode()).hexdigest() == 'aca55490803528a0aeabbc8d21760a00ea8531c41f7edc2f066e4c7f8a31be66'
    helper_changes = []
    for p in (RUN / 'baseline/tests').iterdir():
        assert p.read_bytes() == (RUN / 'candidate/tests' / p.name).read_bytes()
        if p.name == 'memory-research-list-bulk-cpu.py':
            assert digest(p) == proposal['runner_sha256']
        elif p.name == 'configuration-probe.c':
            assert '__has_feature(address_sanitizer)' in p.read_text()
            assert '__has_feature(undefined_behavior_sanitizer)' in p.read_text()
            assert '__has_feature(thread_sanitizer)' in p.read_text()
            assert '#include "memory-research-list-bulk-cpu.c"' in p.read_text()
        elif p.name == 'memory-research-list-bulk.py':
            old = (original / 'tests' / p.name).read_text()
            new = p.read_text()
            old_functions = {n.name: ast.dump(n) for n in ast.parse(old).body if isinstance(n, ast.FunctionDef)}
            new_functions = {n.name: ast.dump(n) for n in ast.parse(new).body if isinstance(n, ast.FunctionDef)}
            for used in ['digest', 'replace_once', 'candidate']:
                assert old_functions[used] == new_functions[used], used
            diff = ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                              fromfile='initial-helper.py', tofile='executed-helper.py'))
            (OUT / 'initial-to-executed-candidate-helper.diff').write_text(diff)
            helper_changes.append({'name': p.name, 'initial_sha256': digest(original / 'tests' / p.name),
                                   'executed_sha256': digest(p),
                                   'used_digest_replace_once_candidate_AST_equal': True,
                                   'changed_extent': 'Adds unused verify_candidate and already-applied main CLI; acquisition calls existing candidate directly.',
                                   'compiled_candidate_bytes_exact': True})
        else:
            assert p.read_bytes() == (original / 'tests' / p.name).read_bytes(), p
    for path, sha in report['production_entry_hashes'].items():
        assert digest(Path(path)) == sha
        assert digest(original / 'runtime' / Path(path).name) == sha
    checks = {check['label']: check for check in report['checks']}
    code = []
    for variant in ['baseline', 'candidate']:
        checksum_command = checks['compile-checksum-' + variant]['command']
        assert '-c' in checksum_command and '-O2' in checksum_command
        assert not any(flag.startswith(('-flto', '-fsanitize')) for flag in checksum_command)
        for profile in ['system', 'fixed']:
            prefix = 'configuration-' + variant + '-' + profile
            command = checks['compile-' + variant + '-' + profile]['command']
            assert '-O2' in command and '-std=c11' in command and '-DMINYAR_RC_POLL_BUDGET=32' in command
            assert all(flag in command for flag in ['-Wall', '-Wextra', '-Werror'])
            assert not any(flag.startswith(('-flto', '-fsanitize', '-DNDEBUG', '-DMINYAR_RC_TESTING', '-DMINYAR_RESEARCH_')) for flag in command)
            assert str(ROOT / REL / variant / 'checksum.o') in command
            macro_check = checks[prefix + '-macros']
            body_check = checks[prefix + '-preprocessed']
            macro_path = RUN / macro_check['assembly_file']
            body_path = RUN / body_check['assembly_file']
            assert digest(macro_path) == macro_check['assembly_sha256']
            assert digest(body_path) == body_check['assembly_sha256']
            macros = macro_path.read_text()
            body = body_path.read_text()
            for name in ['MINYAR_RC_TESTING', 'MINYAR_RESEARCH_COUNT', 'MINYAR_RESEARCH_TEST_ACCOUNTING',
                         'NDEBUG', '__SANITIZE_ADDRESS__', '__SANITIZE_THREAD__', 'MINYAR_COMPILER_ARENA']:
                assert not re.search(r'^#define ' + name + r'\b', macros, re.M)
            assert '#define RC_ACCOUNT(expression) ((void)0)' in macros
            assert '#define MINYAR_BOUNDED_RC 1' in macros and '#define MINYAR_RC_POLL_BUDGET 32' in macros
            feature = checks[prefix + '-feature-check']
            assert feature['returncode'] == 0 and '-fsyntax-only' in feature['command']
            assert '-O2' in feature['command']
            if profile == 'fixed':
                assert '#define MINYAR_BOUNDED_HEAP_BYTES 16777216' in macros
                assert '!minyar_pool_used' in body
            else:
                assert '#define MINYAR_SYSTEM_HEAP 1' in macros
            main_start = body.rfind('int main(')
            main_body = body[main_start:]
            assert main_start >= 0
            for assertion in ['checksum == expected', 'control->values[i] == source->values[i]',
                              'control->values[length] == tail', 'source->values[0] == old',
                              '!rc_pending_count && !rc_frames && !rc_free_frames']:
                assert assertion in main_body
            assert '__assert_rtn' in main_body
            symbols_check = checks[prefix + '-linked-symbols']
            symbols = (RUN / symbols_check['assembly_file']).read_text()
            linked_check = checks['linked-machine-code-' + variant + '-' + profile]
            linked = (RUN / linked_check['assembly_file']).read_text()
            assembly_check = checks['fixture-assembly-' + variant + '-' + profile]
            fixture_assembly = (RUN / assembly_check['assembly_file']).read_text()
            for name in TELEMETRY:
                assert not re.search(r'\b_?' + name + r'\b', body + symbols + linked + fixture_assembly)
            assert '___assert_rtn' in symbols
            checksum = routine(linked, 'research_checksum')
            main_code = routine(linked, 'main')
            appended = routine(linked, 'minyar_list_appended')
            assert all(re.search(r'\b' + op + r'\b', checksum) for op in ['ldr', 'eor', 'mul', 'subs'])
            assert 'b.ne' in checksum
            assert re.search(r'\bbl\s+_research_checksum\b', main_code)
            clock_lines = [line for line in main_code.splitlines() if '_clock_gettime' in line]
            assert len(clock_lines) == 2
            checksum_lines = [line for line in main_code.splitlines() if re.search(r'\bbl\s+_research_checksum\b', line)]
            assert main_code.index(clock_lines[0]) < main_code.index(checksum_lines[0]) < main_code.index(clock_lines[1])
            assert '_rc_drop' in main_code and '_minyar_rc_poll' in main_code
            assert '_minyar_list_add' in appended
            if variant == 'candidate':
                assert '_memcpy' in appended and '_list_reserve' in appended
            selected_file = OUT / ('timed-' + variant + '-' + profile + '-selected-code.txt')
            selected_file.write_text(main_code + '\n' + checksum + '\n' + appended)
            code.append({'variant': variant, 'profile': profile,
                         'linked_listing_sha256': digest(RUN / linked_check['assembly_file']),
                         'clock_calls': clock_lines, 'checksum_calls': checksum_lines,
                         'prefix_copy_calls': [line for line in appended.splitlines() if '_memcpy' in line],
                         'selected_code_path': str(selected_file.relative_to(ROOT)),
                         'test_telemetry_absent_from_body_and_saved_code': True})
    resource_rows = report['checks']
    assert all(row['aggregate_child_cpu_seconds'] <= 180 and row['runner_elapsed_seconds'] <= 600 for row in resource_rows)
    assert all(row['observer_wall_seconds'] <= 10 for row in resource_rows)
    native = [row for row in resource_rows if 'observation' in row]
    assert len(native) == 588
    result = {'verified_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'frozen_artifact_entries_independently_verified': freeze,
              'original_executable_and_checksum_object_bytes_independently_rehashed': 6,
              'source_pair_different_files': different, 'patch_diff_exact': True,
              'helper_changes_since_initial_checkpoint': helper_changes,
              'proposal_exact_released_bytes': True, 'runner_exact_released_bytes': True,
              'seeded_plan_matches_saved_input_file': True, 'production_entry_hashes_unchanged': report['production_entry_hashes'],
              'actual_macro_body_feature_flags_and_linked_telemetry_checks_verified': True,
              'linked_code': code, 'recorded_operations': len(resource_rows), 'native_records': len(native),
              'resources': {'summed_child_cpu_seconds': sum(row['observed_child_cpu_seconds'] for row in resource_rows),
                            'runner_wall_seconds': report['runner_wall_seconds'],
                            'max_check_child_cpu_seconds': max(row['observed_child_cpu_seconds'] for row in resource_rows),
                            'max_check_wall_seconds': max(row['observer_wall_seconds'] for row in resource_rows),
                            'max_native_RSS_bytes': max(row['peak_rss_bytes'] for row in native),
                            'per_child_CPU_seconds': 5, 'per_child_file_bytes': 8388608,
                            'per_child_wall_seconds': 10, 'completed_RSS_threshold_bytes': 134217728,
                            'aggregate_CPU_seconds': 180, 'runner_wall_limit_seconds': 600,
                            'continuous_aggregate_CPU_or_RSS_enforcement': False,
                            'stdout_pipe_bounded_by_file_limit': False},
              'execution': 'Hash/source/data/listing checks only; no native or compiler invocation'}
    (OUT / 'timed-artifact-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ['original_executable_and_checksum_object_bytes_independently_rehashed',
                                               'source_pair_different_files', 'recorded_operations', 'native_records', 'resources']}))


if __name__ == '__main__':
    main()
