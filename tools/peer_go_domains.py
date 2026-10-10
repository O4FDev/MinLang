"""Validate the pinned Go audit's finite, source-derived domain rules.

This checks cardinalities and disposition proofs, not whether a human read
upstream source or whether a Minyar implementation has passed its tests.
No upstream program is executed and no filesystem access is required.
"""
import itertools
import re


REVISION = '6f5c275ebdc454197fff5f1496521c8f81e20eef'
SUPPORTED_DOMAIN_PATHS = frozenset({
    'test/rotate.go', 'test/slice3.go', 'test/rangegen.go',
    'test/64bit.go', 'test/chan/select5.go',
    *(f'test/rotate{mode}.go' for mode in range(4)),
})
MINIMUM, MAXIMUM = -(1 << 63), (1 << 63) - 1
WORD, HALF = 1 << 32, 1 << 31
SIGNED = [
    0, 1, 2, 3, 100, 10001, HALF - 1, HALF, HALF + 1,
    WORD - (1 << 30), WORD - 1, WORD, WORD + 1, 2 * WORD,
    MAXIMUM - 9999, MAXIMUM, 0x789abcdef0123456,
    -1, -2, -3, -100, -10001, -(HALF - 1), -HALF, -(HALF + 1),
    -(WORD - (1 << 30)), -WORD, -WORD + 1, -2 * WORD,
    MINIMUM + 10000, MINIMUM + 1, MINIMUM,
    -0x789abcde * WORD + 0xf0123456,
]
UNSIGNED = [
    0, 1, 2, 3, 100, 10001, HALF - 1, HALF, HALF + 1,
    WORD - (1 << 30), WORD - 1, WORD, WORD + 1, 2 * WORD,
    MAXIMUM - 9999, MAXIMUM, (WORD - (1 << 30)) * WORD,
    (WORD - 1) * WORD, (WORD - 1) * WORD + WORD - 100,
    (1 << 64) - 1, 0x789abcdef0123456, 0xfedcba9876543210,
]
SHIFTS = [
    0, 1, 2, 3, 15, 16, 17, 31, 32, 33, 61, 62, 63, 64, 65,
    WORD - 1, WORD, WORD + 1, (1 << 28) * WORD, (1 << 31) * WORD,
    (WORD - 1) * WORD, (1 << 64) - 1,
]
INDEX_TOKENS = ['0', '1', '2', '3', '10', '20', 'vminus1',
                'v0', 'v1', 'v2', 'v3', 'v10', 'v20']


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _same(actual, expected, label):
    # bool is an int subclass; JSON true must not stand in for a domain bound.
    if isinstance(expected, list):
        valid = (type(actual) is list and len(actual) == len(expected))
        _require(valid, 'Invalid ' + label)
        for index, (left, right) in enumerate(zip(actual, expected)):
            _same(left, right, f'{label}[{index}]')
    elif isinstance(expected, dict):
        _require(type(actual) is dict and actual.keys() == expected.keys(),
                 'Invalid ' + label)
        for key in expected:
            _same(actual[key], expected[key], label + '.' + key)
    else:
        _require(type(actual) is type(expected) and actual == expected,
                 'Invalid ' + label)


def _fields(domain, expected):
    for key, value in expected.items():
        _require(key in domain, 'Missing domain field ' + key)
        _same(domain[key], value, key)


def _disposition(row, domain, disposition, artifact_key):
    _same(row.get('disposition'), disposition, 'row disposition')
    _same(row.get('implementation_needed'), disposition == 'adapt',
          'implementation_needed')
    _fields(domain, {'per_instance_disposition': disposition, artifact_key: False})


def _rotate(row, domain):
    match = re.fullmatch(r'mode([0-3])/bits(8|16|32|64)/exhaustive-rule', row['case_id'])
    _require(match is not None, 'Invalid rotate case identifier')
    mode, width = map(int, match.groups())
    _fields(domain, {
        'mode': mode, 'bits': width, 'unsigned': bool(mode & 1),
        'inverted': bool(mode & 2), 'left_shift_inclusive': [0, width],
        'right_shift_inclusive': [0, width], 'join': ['|', '^'],
        'order': ['left-then-right', 'right-then-left'],
        'instances': 4 * (width + 1) ** 2,
    })
    _disposition(row, domain, 'reject', 'individually_read_generated_source')


def _slice(row, domain):
    base = domain.get('base')
    _require(base in ('array', 'slice'), 'Invalid slice base')
    _same(row['case_id'], base + '/exhaustive-rule', 'slice case identifier')

    def parse(token):
        return (-1, False) if token == 'vminus1' else (
            int(token.removeprefix('v')), not token.startswith('v'))

    count = 0
    for triple in itertools.product(INDEX_TOKENS, repeat=3):
        (a, ac), (b, bc), (c, cc) = map(parse, triple)
        static_oob = base == 'array' and any(
            constant and value > 10 for value, constant in ((a, ac), (b, bc), (c, cc)))
        if ((ac and bc and a > b) or (bc and cc and b > c)
                or (ac and cc and a > c) or static_oob):
            continue
        count += 1
    _fields(domain, {
        'index_tokens': INDEX_TOKENS, 'instances': count,
        'filter': 'Skip pairs of compile-time indices in descending order, and array compile-time indices>10.',
        'instance_table': 'inventory.generated_domains[test/slice3.go].instances',
    })
    _disposition(row, domain, 'reject', 'individually_read_generated_source')


def _range(row, domain):
    long = domain.get('long')
    depth, double = domain.get('depth'), domain.get('double')
    _require(type(long) is bool and type(depth) is int and type(double) is int,
             'Invalid range configuration types')
    _require(1 <= depth <= (2 if long else 5), 'Invalid range depth')
    _require(-1 <= double <= (depth if long else -1), 'Invalid range double level')

    def code_count(level):
        # Each loop emits seven basic branches and ten for each enclosing label.
        branches = 7 + 10 * level
        if level < depth:
            branches = 2 * branches + code_count(level + 1)
        return branches * (2 if level == double else 1)

    count = code_count(0)
    pairs = count * (count + 1) // 2 if long else count
    _same(row['case_id'], f'{"long" if long else "short"}/depth{depth}/double{double}/exhaustive-rule',
          'range case identifier')
    _fields(domain, {
        'code_count': count, 'pair_functions': pairs,
        'pair_domain': '0<=j<=k<code' if long else '0<=j=k<code',
        'pair_inputs': '[j,k], including duplicate when equal',
        'all_function_inputs_inclusive': [0, count - 1],
        'total_trace_comparisons': 2 * pairs + count,
    })
    _disposition(row, domain, 'reject', 'individually_read_generated_source')


def _integer64(row, domain):
    parts = row['case_id'].split('/')
    _require(parts[0] in ('int64', 'uint64'), 'Invalid 64-bit operand type')
    signed = parts[0] == 'int64'
    values = SIGNED if signed else UNSIGNED
    if len(parts) == 3 and parts[1] == 'unary':
        operator = parts[2]
        _require(operator in ('+', '-', '^'), 'Invalid unary operator')
        _fields(domain, {'values': values, 'operator': operator, 'instances': len(values)})
        disposition = 'adapt' if signed and operator == '-' else 'reject'
        _fields(domain, {'oracle': '-value unless MIN then checked overflow'
                         if disposition == 'adapt' else 'upstream width-limited unary operation'})
    elif len(parts) == 5 and parts[2] == 'shifts':
        placement, host = parts[1], parts[3]
        _require(placement in ('var-var', 'const-var', 'var-const')
                 and host in ('host32', 'host64') and parts[4] == 'exhaustive-rule',
                 'Invalid shift configuration')
        native = int(host[4:])
        widths = ({'uint64': 64, 'uint': native, 'uint32': 32, 'uint16': 16, 'uint8': 8}
                  if placement == 'var-var' else {'uint64': 64, 'uint32': 32})
        count = sum(2 * len(values) for shift in SHIFTS for width in widths.values()
                    if shift < 1 << width)
        _fields(domain, {
            'left_values': values, 'shift_values': SHIFTS, 'directions': ['<<', '>>'],
            'shift_operand_types': widths, 'instances': count,
            'filter': 'execute typed variant iff shift count fits that unsigned width',
        })
        disposition = 'reject'
    else:
        # '/' is itself the operator, so split('/') is intentionally unsuitable.
        match = re.fullmatch(r'(int64|uint64)/(var-var|const-var|var-const)/([+*/%&|^\-]|&\^)/exhaustive-rule',
                             row['case_id'])
        _require(match is not None, 'Invalid binary configuration')
        _, placement, operator = match.groups()
        excluded = ([[value, 0] for value in values]
                    + ([[MINIMUM, -1]] if signed else [])
                    if operator in ('/', '%') else [])
        _fields(domain, {
            'left_values': values, 'right_values': values,
            'operator': operator, 'placement': placement,
            'exclude_pairs': excluded, 'instances': len(values) ** 2 - len(excluded),
            'oracle': 'exact signed arithmetic with checked overflow; quotient=sign(a*b)*floor(abs(a)/abs(b)), remainder=a-quotient*b',
        })
        disposition = 'adapt' if signed and operator in ('+', '-', '*', '/', '%') else 'reject'
    _disposition(row, domain, disposition, 'generated_artifacts_individually_read')


def _select(row, domain):
    # Optional default: before, after, or none. Four optional dummy/nil cases.
    counts = {'recv': 1 + 3 * 5 * 2 ** 4, 'send': 1 + 3 * 2 ** 4,
              'recvOrder': 2 + 3 * 4 * 2 ** 4, 'sendOrder': 1 + 3 * 2 ** 4,
              'nonblock': 2 * 2 ** 8}
    family = domain.get('family')
    _require(family in counts, 'Invalid select family')
    _same(row['case_id'], family + '/exhaustive-rule', 'select case identifier')
    _fields(domain, {'instances': counts[family]})
    _disposition(row, domain, 'reject', 'generated_artifacts_individually_read')


def validate_inline_domain(row):
    """Return True for a validated known family, False for an unknown schema.

    Contradictions in recognized families raise ValueError. External artifact
    schemas are left to their own validator. Counts describe active source
    instances, not a claim that generated artifacts were individually read.
    """
    domain = row.get('generated_domain')
    if not isinstance(domain, dict) or 'artifact' in domain:
        return False
    path = row.get('path')
    if not isinstance(path, str) or path not in SUPPORTED_DOMAIN_PATHS:
        return False
    validators = {'test/rotate.go': _rotate, 'test/slice3.go': _slice,
                  'test/rangegen.go': _range, 'test/64bit.go': _integer64,
                  'test/chan/select5.go': _select}
    driver = re.fullmatch(r'test/rotate([0-3])\.go', path or '')
    if path not in validators and driver is None:
        return False
    _same(row.get('language'), 'go', 'language')
    _same(row.get('repo'), 'golang/go', 'repository')
    _same(row.get('revision'), REVISION, 'revision')
    _require(type(row.get('case_id')) is str, 'Missing case identifier')
    try:
        if driver:
            mode = int(driver[1])
            _fields(domain, {'generator': 'test/rotate.go', 'mode': mode})
            _same(row['case_id'], f'driver-mode{mode}', 'driver identifier')
            _same(row.get('disposition'), 'covered', 'driver disposition')
            _same(row.get('implementation_needed'), False, 'driver implementation_needed')
        else:
            validators[path](row, domain)
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError(f'Malformed {path} inline domain: {error}') from error
    return True
