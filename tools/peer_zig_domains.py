"""Exact finite domain of the pinned Zig integer-logarithm tests.

This validates source-derived input identities, complete partitions and oracles.
It neither reads upstream files nor asserts that Minyar executed any input.
"""
from functools import lru_cache
import hashlib
import json


SOURCE = {
    'language': 'zig', 'repo': 'ziglang/zig',
    'revision': '738d2be9d6b6ef3ff3559130c05159ef53336224',
    'path': 'lib/std/math/log_int.zig',
    'source_sha256': 'a8cdf0eaabcde7493ad607be576a84bb73d10402e45cb8a1b8c9d542529d7278',
}
MAXIMUM = (1 << 63) - 1
COHORTS = ('boundary-representable', 'boundary-outside-integer', 'log2-comparison', 'log10-comparison')
KEY_FIELDS = ('language', 'repo', 'revision', 'path', 'case_id')


def instances():
    """Yield (cohort, exact identity, base, input, expected) in source order.

    The base condition precedes increment in the source, so 1025 is included.
    A duplicate numerical operand at a different width remains a separate case.
    """
    for bits in range(2, 65):
        maximum = (1 << bits) - 1
        for base in range(2, min(maximum, 1025) + 1):
            yield ('boundary-representable', f'bits{bits}/base{base}/one', base, 1, 0)
            exponent = 1
            while base ** exponent <= maximum:
                power = base ** exponent
                for suffix, value, expected in [('below', power - 1, exponent - 1), ('at', power, exponent)]:
                    cohort = 'boundary-representable' if value <= MAXIMUM else 'boundary-outside-integer'
                    yield cohort, f'bits{bits}/base{base}/power{exponent}/{suffix}', base, value, expected
                exponent += 1
    for base, widths in [(2, (2, 3, 4, 8, 16)), (10, (4, 5, 6, 8, 16))]:
        for bits in widths:
            for value in range(1, 1 << bits):
                # Integer bit count and decimal digit count are independent of
                # the translated Minyar helper's repeated division algorithm.
                expected = value.bit_length() - 1 if base == 2 else len(str(value)) - 1
                yield f'log{base}-comparison', f'bits{bits}/n{value}', base, value, expected


def _encoded(value):
    return (json.dumps(value, ensure_ascii=True, separators=(',', ':')) + '\n').encode('ascii')


@lru_cache(maxsize=1)
def _expected_json():
    hashes = {name: [0, hashlib.sha256(), hashlib.sha256()] for name in COHORTS}
    for cohort, identity, base, value, expected in instances():
        state = hashes[cohort]
        state[0] += 1
        state[1].update(_encoded([identity, base, value]))
        state[2].update(_encoded([identity, base, value, expected]))
    cohorts = []
    for name in COHORTS:
        count, input_hash, oracle_hash = hashes[name]
        cohorts.append(dict(id=name, instances=count,
                            disposition='reject' if name == 'boundary-outside-integer' else 'adapt',
                            input_sha256=input_hash.hexdigest(), oracle_sha256=oracle_hash.hexdigest()))
    return json.dumps(dict(
        schema_version=1, schema='zig-log-int-v1', domain_id='zig-log-int-full-domain',
        **SOURCE,
        axes={'boundary_bits_inclusive': [2, 64], 'base_inclusive': [2, 1025],
              'base_maximum': 'min((1<<bits)-1,1025)',
              'power_rule': 'base**exponent <= (1<<bits)-1; exponent starts at1',
              'boundary_branches': ['one', 'below', 'at'],
              'log2_bits': [2, 3, 4, 8, 16], 'log10_bits': [4, 5, 6, 8, 16],
              'comparison_inputs': '1..(1<<bits)-1 inclusive',
              'integer_maximum': MAXIMUM},
        case_identity='cohort plus width/base/power/branch, or width/n; duplicate operands at different widths remain distinct',
        hash_encoding='UTF-8 compact JSON arrays followed by LF, in source order within each cohort; inputs=[identity,base,input], oracles=[identity,base,input,expected]',
        oracle_rules='boundary one=0, below power exponent-1, at power exponent; log2=bit_length-1; log10=decimal digit count-1',
        review_method='Derived from complete pinned generator and helpers; generated instances are mathematically enumerated, not individually read source files',
        cohorts=cohorts, total_instances=sum(c['instances'] for c in cohorts),
        reviewed_instances=sum(c['instances'] for c in cohorts), execution_claim=False,
    ))


def expected_domain():
    """Return a fresh descriptor, avoiding mutable cached validation state."""
    return json.loads(_expected_json())


def _same(actual, expected, label):
    if type(actual) is not type(expected):
        raise ValueError('Invalid type at ' + label)
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError('Missing or extra fields at ' + label)
        for key in expected:
            _same(actual[key], expected[key], label + '.' + key)
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError('Invalid length at ' + label)
        for index, (left, right) in enumerate(zip(actual, expected)):
            _same(left, right, label + f'[{index}]')
    elif actual != expected:
        raise ValueError('Incorrect value at ' + label)


def validate_domain(domain):
    """Require the entire exact domain, including all four decided cohorts."""
    _same(domain, expected_domain(), 'zig-log-int')
    return {cohort['id']: dict(cohort) for cohort in domain['cohorts']}


def validate_reference(row, reference, domain):
    """Check one ledger row against its cohort; artifact hashes are caller-owned."""
    cohorts = validate_domain(domain)
    for key, value in SOURCE.items():
        _same(row.get(key), value, 'row.' + key)
    _same(reference.get('domain_id'), domain['domain_id'], 'reference.domain_id')
    cohort_id = reference.get('cohort')
    if cohort_id not in cohorts:
        raise ValueError('Unknown Zig log cohort')
    cohort = cohorts[cohort_id]
    _same(reference.get('instances'), cohort['instances'], 'reference.instances')
    _same(row.get('disposition'), cohort['disposition'], 'row.disposition')
    _same(row.get('implementation_needed'), cohort['disposition'] == 'adapt', 'row.implementation_needed')
    _same(row.get('case_id'), 'generated-domain/' + cohort_id, 'row.case_id')
    return cohort_id


def validate_complete(domain, rows, resolutions):
    """Completion guard: all cohorts referenced and every adapt key resolved.

    The caller still validates resolution test names and execution evidence.
    Supplying a resolution key alone here never claims its evidence is sound.
    """
    expected = validate_domain(domain)
    references = {}
    for row in rows:
        cohort = validate_reference(row, row.get('generated_domain', {}), domain)
        if cohort in references:
            raise ValueError('Duplicate cohort reference: ' + cohort)
        references[cohort] = row
    if references.keys() != expected.keys():
        raise ValueError('Unreferenced Zig log cohorts')
    resolved = {tuple(row.get(k) for k in KEY_FIELDS) for row in resolutions}
    for cohort, row in references.items():
        if row['implementation_needed'] and tuple(row[k] for k in KEY_FIELDS) not in resolved:
            raise ValueError('Unresolved Zig log cohort: ' + cohort)
