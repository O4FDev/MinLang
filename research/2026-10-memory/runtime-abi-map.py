#!/usr/bin/env python3
"""Source-defined ABI inventory with conservative, explicitly mapped evidence."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFINITION = re.compile(r'(?m)^([A-Za-z_][A-Za-z0-9_ \t*]*?)\b(minyar_[A-Za-z0-9_]+)\s*\(([^;{}]*)\)\s*\{')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def names(text):
    return set(text.split())


def main():
    index = json.loads((HERE / 'evidence/runtime/index.json').read_text())
    selected = {item['label']: item for item in index['results']}
    registry = {}
    sources = []
    excluded_static = []
    for path in sorted((ROOT / 'runtime').glob('minyar_*')):
        if path.suffix not in ('.h', '.c'):
            continue
        text = path.read_text()
        sources.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        for match in DEFINITION.finditer(text):
            location = {'path': str(path.relative_to(ROOT)),
                        'line': text[:match.start()].count('\n') + 1,
                        'signature': re.sub(r'\s+', ' ', match.group(0)[:-1]).strip(),
                        'sha256': sha(path)}
            if 'static' in match.group(1).split():
                excluded_static.append({'name': match.group(2), **location})
                continue
            entry = registry.setdefault(match.group(2), {'name': match.group(2), 'definitions': [],
                'source_review': 'signature_inventory_only', 'direct_correctness_evidence': [],
                'count_profile_evidence': [], 'workload_timing_evidence': [],
                'isolated_function_timing': 'none_mapped', 'available_test_source_mentions': []})
            entry['definitions'].append(location)

    # Explicitly expand the four source macro invocations; token-pasted names are
    # not discoverable by the literal-definition expression above.
    path = ROOT / 'runtime/minyar_bytes.h'
    text = path.read_text()
    for match in re.finditer(r'(?m)^MINYAR_BYTES_INTEGER\((\w+),\s*(\d+),\s*(\d+),\s*(\w+)\)', text):
        for operation, template_line in [('add', 136), ('set', 142), ('get', 147)]:
            name = 'minyar_bytes_' + operation + '_' + match.group(1)
            assert name not in registry
            registry[name] = {'name': name, 'definitions': [{
                'path': 'runtime/minyar_bytes.h', 'line': text[:match.start()].count('\n') + 1,
                'macro': 'MINYAR_BYTES_INTEGER', 'macro_template_line': template_line,
                'width_bytes': int(match.group(2)), 'signed': bool(int(match.group(3))),
                'cast': match.group(4), 'sha256': sha(path)}],
                'source_review': 'signature_inventory_only', 'direct_correctness_evidence': [],
                'count_profile_evidence': [], 'workload_timing_evidence': [],
                'isolated_function_timing': 'none_mapped', 'available_test_source_mentions': []}
    assert len(registry) == 105, 'Inventory changed: review literal and macro definitions.'
    compiler = ROOT / 'compiler/compiler.min'
    declarations = set(re.findall(r'declare [^@\n]*@(minyar_\w+)\(', compiler.read_text()))
    for name, entry in registry.items():
        entry['compiler_declaration_present'] = name in declarations
        entry['abi_audience'] = 'compiler_emitted_or_declared' if name in declarations else 'runtime_or_extension_export'
        entry['availability'] = ('bounded-RC implementation; no arena poll definition'
                                 if name == 'minyar_rc_poll' else
                                 'default-runtime stack-frame supplement; arena variant is a no-op'
                                 if name.endswith('_stack_v1') else
                                 'profile-dependent arena/no-op and RC definitions' if name.startswith('minyar_rc_') else
                                 'core runtime source definition; platform branches may differ')

    def mapped(field, functions, label, fixture, limitation):
        record = selected[label]
        for name in names(functions):
            assert name in registry, name
            if fixture:
                assert name in (ROOT / fixture).read_text(), (name, fixture)
            registry[name][field].append({'result': 'evidence/runtime/' + record['path'],
                                         'result_sha256': record['sha256'], 'fixture': fixture,
                                         'scope': limitation})
            registry[name]['source_review'] = 'bounded_contract_review; no complete path proof'

    mapped('direct_correctness_evidence', '''minyar_list_new minyar_list_references minyar_list_add
        minyar_list_appended minyar_rc_release minyar_rc_retain minyar_rc_poll''',
        'list-sanitizer-matrix', 'tests/memory-research-list-reserve.c',
        'Explicit native fixture calls and ownership/content oracles; matrix snapshot retained, not every API input.')
    mapped('direct_correctness_evidence', '''minyar_join_text minyar_join_text_take_left
        minyar_text_length minyar_text_character_at minyar_text_slice''',
        'final-text-matrix', 'tests/memory-research-text-join-index.c',
        'Final-runtime native18-case oracle plus generated checks; Unicode/ASCII, alias/view/self and index boundaries.')
    mapped('direct_correctness_evidence', '''minyar_boolean_text minyar_text_length minyar_text_slice''',
        'api-count-native', 'tests/memory-research-api-counts.c',
        'Native baseline Boolean/view content, lifetime and metadata queries; no changed policy.')
    mapped('direct_correctness_evidence', '''minyar_rc_enter minyar_rc_keep minyar_rc_leave
        minyar_rc_local_move minyar_rc_local_take minyar_record_new minyar_record_set_reference
        minyar_record_set_scalar''', 'accounting-probes', 'tests/memory-research-accounting-edges.c',
        'Public operations mixed with private detach/kernel probes; not a pure public-ABI trace equivalence claim.')
    mapped('direct_correctness_evidence', '''minyar_bytes_new minyar_bytes_resize minyar_bytes_extend
        minyar_bytes_set_int64 minyar_record_new''', 'guard-order-native', 'tests/memory-research-guard-order.c',
        'Selected invalid-size native trap/order branches, not successful-operation completeness.')
    mapped('direct_correctness_evidence', 'minyar_integer_text', 'hud-formatting-matrix',
        'tests/memory-research-hud-formatting.c',
        'Generated HUD invokes instrumented wrapper around real function; exact status/cache/lifetime oracle.')
    mapped('count_profile_evidence', 'minyar_list_appended minyar_list_add', 'list-sanitizer-matrix',
        'tests/memory-research-list-reserve.c', 'Allocation/reallocation and service observations for defined fixture operations.')
    mapped('count_profile_evidence', 'minyar_join_text minyar_text_length', 'ascii-final-lazy-sanitizer',
        None, 'Instrumented index scan/allocation/service counts in borrowed-join/query workloads; no isolated per-call latency.')
    mapped('count_profile_evidence', 'minyar_join_text_take_left', 'deferred-isolated', None,
        'Physical-owner/reuse/copied-byte/retained-capacity experiment; extra-service policy stayed test-only.')
    mapped('count_profile_evidence', 'minyar_text_slice minyar_boolean_text', 'api-count-native',
        'tests/memory-research-api-counts.c', 'Backing retention, allocation/service/index counts on selected distributions.')
    mapped('count_profile_evidence', 'minyar_integer_text', 'hud-formatting-matrix',
        'tests/memory-research-hud-formatting.c', 'Public formatter calls versus allocating conversions/cache storage; actual queued work zero.')
    mapped('count_profile_evidence', 'minyar_rc_poll', 'accounting-probes',
        'tests/memory-research-accounting-edges.c', 'Exact returned scheduler work, pending tasks, retained bytes and recovery on bounded traces.')
    mapped('count_profile_evidence', 'minyar_bytes_resize minyar_bytes_new', 'rejected-bytes-policy', None,
        'Original versus rejected test-only growth policy; includes allocation/service/admission observations.')
    mapped('workload_timing_evidence', 'minyar_list_add minyar_list_appended', 'final-list-timing', None,
        'Paired C workloads containing the operation; fixed ordinary-growth slowdown retained. Not isolated function timings.')
    mapped('workload_timing_evidence', 'minyar_join_text minyar_text_length', 'ascii-paired-timing', None,
        'Paired generated workloads, including known/unknown/Unicode/no-query controls; no attribution of whole-program time to one function.')

    equality_path = HERE / 'evidence/runtime-peer-projections/run-egbfb2e0/results.json'
    equality = json.loads(equality_path.read_text())
    call_path = HERE / 'evidence/runtime-peer-calibrations/run-slxiueks/generated-call-sites.json'
    call_sites = json.loads(call_path.read_text())
    assert equality['status'] == 'passed' and equality['summary']['generated_executions'] == 6
    assert call_sites['call_sites']['minyar_texts_are_equal'] > 0
    registry['minyar_texts_are_equal']['direct_correctness_evidence'].append({
        'result': str(equality_path.relative_to(HERE)), 'result_sha256': sha(equality_path),
        'fixture': 'tests/memory-research-peer-projections.py',
        'call_site_inventory': str(call_path.relative_to(HERE)), 'call_site_sha256': sha(call_path),
        'scope': 'Selected original generated equality fixture: all mismatch positions at byte lengths '
                 '0..17/31/32/33, prefix length, embedded NUL and Unicode tails. O0/O2 native/generated-ASan '
                 'matrices; corresponding original LLVM direct call sites retained by separate C oracle '
                 'calibration. Static call sites are not dynamic work counts; no isolated function timing.'})
    registry['minyar_texts_are_equal']['source_review'] = 'bounded_contract_review; no complete path proof'

    float_path = HERE / 'evidence/runtime-float-text/run-lbcunlb1/results.json'
    float_result = json.loads(float_path.read_text())
    assert float_result['status'] == 'passed' and float_result['source_hashes_unchanged']
    assert len(float_result['observations']['native']) == 10
    assert float_result['observations']['native'] == float_result['observations']['sanitize']
    for field in ['direct_correctness_evidence', 'count_profile_evidence']:
        registry['minyar_float_text'][field].append({
            'result': str(float_path.relative_to(HERE)), 'result_sha256': sha(float_path),
            'fixture': 'tests/memory-research-float-text.c',
            'scope': 'Ten fixed binary64 public conversions plus separate pressure conversions: '
                     'exact strings, ASCII metadata, Character contents, retained alias and full recovery. '
                     'System/K32 native O2 and C ASan+UBSan O1; omitted backing-allocation observer event '
                     'rejected after recovery. Managed allocation/helper service/public-poll edges only; '
                     'actual queued work zero. No private formatter/libc counts, generated LLVM, '
                     'application hot-path evidence or timing measurement.'})
    registry['minyar_float_text']['source_review'] = 'bounded_contract_review; no complete path proof'

    aggregate_path = HERE / 'evidence/runtime-aggregate/run-ltiaucr9/results.json'
    aggregate = json.loads(aggregate_path.read_text())
    assert aggregate['status'] == 'passed' and aggregate['variant'] == 'baseline'
    assert len(aggregate['observations']) == 18 and len(aggregate['native_observations']) == 8
    for name in ['minyar_join_texts', 'minyar_character_text']:
        for field in ['direct_correctness_evidence', 'count_profile_evidence']:
            registry[name][field].append({
                'result': str(aggregate_path.relative_to(HERE)), 'result_sha256': sha(aggregate_path),
                'fixture': 'tests/memory-research-aggregate-join.min',
                'scope': 'Baseline generated escaped-literal projection: exact byte/scalar/alias oracle; '
                         'entry, fragment, allocation, helper-mediated service and all-public-poll counts. '
                         'Nested poll work is not added twice. Character ASCII/nonASCII calls '
                         'are phase counts, not isolated function costs. Aggregate native debt and '
                         'malformed controls add explicit public join calls at private retirement boundaries.'})
        registry[name]['source_review'] = 'bounded_contract_review; no complete path proof'
    aggregate_timing_path = HERE / 'evidence/runtime-aggregate-timing/run-rrkuiyad/results.json'
    aggregate_timing = json.loads(aggregate_timing_path.read_text())
    assert aggregate_timing['status'] == 'passed' and aggregate_timing['immutable_hashes_match_after']
    for name in ['minyar_join_texts', 'minyar_text_length']:
        registry[name]['workload_timing_evidence'].append({
            'result': str(aggregate_timing_path.relative_to(HERE)), 'result_sha256': sha(aggregate_timing_path),
            'fixture': 'tests/memory-research-aggregate-timing.min',
            'scope': 'Pristine versus isolated test-only metadata candidate in repeated generated joins; '
                     'all 60 paired program CPU/wall observations retained, known/short/unknown/Unicode/no-query. '
                     'Shared host and paced soak; no whole-compiler or isolated function latency claim.'})

    reviewed = names('''minyar_argument minyar_argument_count minyar_initialize_arguments
        minyar_read_text_file minyar_write_text_file minyar_read_bytes_file minyar_write_bytes_file
        minyar_file_exists minyar_print_float minyar_float_text minyar_float_integer
        minyar_integer_character minyar_integer_absolute minyar_check_clamp_integer
        minyar_check_clamp_float minyar_check_shift minyar_tan minyar_asin minyar_acos
        minyar_atan minyar_atan2''')
    for name in reviewed:
        registry[name]['source_review'] = 'current public body and boundary/platform conditions read; no complete path proof'
    # Source mentions expose available tests, never turn text presence into a
    # function-execution or performance claim.
    for path in sorted((ROOT / 'tests').rglob('*')):
        if path.suffix not in ('.c', '.py', '.min') or not path.is_file():
            continue
        for number, line in enumerate(path.read_text(errors='replace').splitlines(), 1):
            for name in set(re.findall(r'\bminyar_\w+\b', line)) & registry.keys():
                registry[name]['available_test_source_mentions'].append({
                    'path': str(path.relative_to(ROOT)), 'line': number,
                    'meaning': 'source mention only; may be a declaration, wrapper, conditional or unused path'})
    native = []
    for path in sorted((ROOT / 'runtime/native').glob('*.c')):
        for match in DEFINITION.finditer(path.read_text()):
            if 'static' not in match.group(1).split():
                native.append({'name': match.group(2), 'path': str(path.relative_to(ROOT)),
                               'line': path.read_text()[:match.start()].count('\n') + 1,
                               'status': 'outside_core_runtime_evidence_scope; separate native lane'})
    entries = sorted(registry.values(), key=lambda item: item['name'])
    report = {'schema': 1, 'generator_sha256': sha(Path(__file__)), 'runtime_sources': sources,
              'compiler_declaration_source': {'path': 'compiler/compiler.min', 'sha256': sha(compiler)},
              'inventory_method': 'Nonstatic minyar_ function definitions in current runtime/minyar_*; '
                                  'conditional variants grouped; four Bytes macro invocations explicitly expanded. '
                                  'Source-defined inventory, not a preprocessed object symbol-table audit.',
              'limits': 'Evidence classification is conservative and nonexclusive. No inference from file-wide coverage, '
                        'category names, source mentions or successful compilation. No complete path/platform proof. '
                        'Historical broader-suite evidence is separately scoped before final ASCII repair; '
                        'current native/kernel and generated checks each retain their own exact snapshot. '
                        'No mapped correctness evidence means absent from this explicit registry, not never tested.',
              'excluded_static_helpers': excluded_static,
              'outside_scope': {'native_export_inventory': native,
                               'compiler': 'Compiler parser, semantic analysis, optimizer, code generation and native toolchain are separate lanes.',
                               'nonprefixed_helpers': 'Link-visible allocation/arena/copy helpers are internal implementation APIs, excluded from the public minyar_ ABI inventory.',
                               'platforms': 'Windows argument conversion and I/O branches have no new campaign execution here.'},
              'functions': entries,
              'summary': {'source_defined_core_entry_points': len(entries), 'literal_names': 93, 'macro_expanded_names': 12,
                          'with_explicit_direct_correctness_map': sum(bool(e['direct_correctness_evidence']) for e in entries),
                          'with_count_profile_map': sum(bool(e['count_profile_evidence']) for e in entries),
                          'with_workload_timing_map': sum(bool(e['workload_timing_evidence']) for e in entries),
                          'with_isolated_function_timings': 0,
                          'source_inventory_only': sum(e['source_review'] == 'signature_inventory_only' for e in entries)}}
    (HERE / 'runtime-abi-evidence-map.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
