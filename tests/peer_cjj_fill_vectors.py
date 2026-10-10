"""Repeatable Java fill inputs; sampled replay and fixed supplements stay separate.

The 48-bit generator and stream-bounded rejection follow the pinned OpenJDK
Random/RandomSupport methods. This replays isolated positive invocations, not
the global IR-framework schedule. Java char values remain raw numeric units.
"""
import struct

MASK = (1 << 48) - 1
MULTIPLIER = 0x5DEECE66D
SEEDS = (0, 1, -1, 186643064605892)
INVOCATIONS_PER_SEED = 2048


class JavaRandom:
    def __init__(self, seed):
        self.state = (seed ^ MULTIPLIER) & MASK
        self.draws = 0

    def bits(self, width):
        self.state = (self.state * MULTIPLIER + 11) & MASK
        self.draws += 1
        return self.state >> (48 - width)

    def integer(self):
        value = self.bits(32)
        return value - (1 << 32) if value >= 1 << 31 else value

    def length(self):
        rejected = 0
        while True:
            value = (self.integer() % (1 << 32)) >> 1
            residue = value % 1023
            if value + 1022 - residue < 1 << 31:
                return residue + 1, rejected
            rejected += 1


def sampled_rows():
    """All 8192 chosen invocations, preserving unused Boolean/Byte/Float draws."""
    rows = []
    for seed_index, seed in enumerate(SEEDS):
        stream = JavaRandom(seed)
        for iteration in range(INVOCATIONS_PER_SEED):
            before = stream.draws
            length, rejected = stream.length()
            boolean = bool(stream.bits(1))
            byte = stream.integer() % 256
            byte -= 256 if byte >= 128 else 0
            char = stream.integer() % 65536
            short = stream.integer() % 65536
            short -= 65536 if short >= 32768 else 0
            integer = stream.integer()
            float_bits = stream.bits(24)
            float_encoding = struct.unpack('>I', struct.pack('>f', float_bits / (1 << 24)))[0]
            rows.append({
                'seed_index': seed_index, 'seed': seed, 'iteration': iteration,
                'length': length, 'boolean': boolean, 'byte': byte,
                'char_code_unit': char, 'short': short, 'int': integer,
                'float_numerator': float_bits, 'float_encoding': float_encoding,
                'rng_draws': stream.draws - before, 'rng_draw_end': stream.draws,
                'length_rejected_candidates': rejected,
            })
    return rows


def complete_cases(kind):
    field = {'char': 'char_code_unit', 'short': 'short', 'int': 'int'}[kind]
    rows = [{'cohort': 'sampled-positive-replay', 'seed': row['seed'],
             'iteration': row['iteration'], 'length': row['length'], 'value': row[field]}
            for row in sampled_rows()]
    fixed = {'char': 55296, 'short': -32768, 'int': -2147483648}[kind]
    boundaries = {
        'char': (0, 1, 55295, 55296, 57343, 57344, 65535),
        'short': (-32768, -1, 0, 1, 32767),
        'int': (-2147483648, -1, 0, 1, 2147483647),
    }[kind]
    rows += [{'cohort': 'all-lengths-one-explicit-value', 'length': n, 'value': fixed}
             for n in range(1, 1024)]
    rows += [{'cohort': 'boundary-cross-product', 'length': n, 'value': value}
             for n in (1, 2, 1023) for value in boundaries]
    return rows


def fill_case(kind):
    """Return the original program, independently fixed full trace, and domain."""
    cases = complete_cases(kind)
    values = [value for row in cases for value in (row['length'], row['value'])]
    helper = {'char': 'fillRawCodeUnits', 'short': 'fillShortValues', 'int': 'fillIntValues'}[kind]
    source = '''function zeroArray(n: Integer): List<Integer> {
let array: List<Integer> = []; let i = 0
while i < n { array.add(0); i = i + 1 }
return array
}
function ''' + helper + '''(array: List<Integer>, value: Integer): Nothing {
let i = 0
while i < array.length { array[i] = value; i = i + 1 }
}
let cases = [''' + ','.join(map(str, values)) + ''']
let offset = 0; let calls = 0; let cells = 0
while offset < cases.length {
let n = cases[offset]; let value = cases[offset + 1]
let array = zeroArray(n)
''' + helper + '''(array, value)
let i = 0
while i < array.length {
if array[i] != value { print(calls); print(i); fail("filled cell differs from generated value") }
i = i + 1; cells = cells + 1
}
print(calls); print(array.length); print(value)
offset = offset + 2; calls = calls + 1
}
print(calls); print(cells)
'''
    total_cells = sum(row['length'] for row in cases)
    expected = ''.join(str(value) + '\n' for index, row in enumerate(cases)
                       for value in (index, row['length'], row['value']))
    expected += str(len(cases)) + '\n' + str(total_cells) + '\n'
    domain = {'sampled_invocations': 8192, 'seeds': list(SEEDS),
              'invocations_per_seed': INVOCATIONS_PER_SEED,
              'sampled_values_exhaustive': False, 'sampled_distinct_lengths': 1022,
              'sampled_missing_lengths': [497], 'supplemental_invocations': len(cases) - 8192,
              'total_invocations': len(cases), 'checked_cells': total_cells,
              'cohorts': ['sampled-positive-replay', 'all-lengths-one-explicit-value',
                          'boundary-cross-product']}
    return source, expected, domain
