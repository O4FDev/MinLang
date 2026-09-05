#!/usr/bin/env python3
"""Independent incoming-SSA identity, alias lifetime and proof-boundary cases."""
import re
import unittest
from regressions import CompilerTestCase


class ProductionReadonlyParameters(CompilerTestCase):
    def test_same_type_arguments_keep_distinct_header_operand_identities(self):
        self.executes('''function combine(first: Integer, second: Integer, third: Integer): Integer {
return first * 100 + second * 10 + third
}
function decorate(first: Text, second: Text): Text { return second + first }
function flags(first: Boolean, second: Boolean): Integer {
if first { return 1 }
if second { return 2 }
return 3
}
print(combine(2, 5, 9))
print(combine(7, 1, 4))
print(decorate("left", "right"))
print(flags(false, true))
''', '259\n714\nrightleft\n2\n')

    def test_indexed_target_survives_mutation_of_its_last_external_owner(self):
        source = '''function replace(holder: List<List<Integer>>): Integer {
holder[0] = [99]
return 0
}
function update(target: List<Integer>, holder: List<List<Integer>>): List<Integer> {
target[replace(holder)] = target[0] + 1
return target
}
let holder = [[41]]
let saved = update(holder[0], holder)
print(saved[0])
print(holder[0][0])
'''
        self.executes(source, '42\n99\n')

    def test_exactly_sixty_four_parameters_keep_their_distinct_values(self):
        parameters = ', '.join(f'a{i}: Integer' for i in range(64))
        source = f'function boundary({parameters}): Integer {{ return a0 + a31 * 100 + a63 * 10000 }}\n'
        source += 'print(boundary(' + ', '.join(str(i) for i in range(64)) + '))\n'
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        body = re.search(r'^define[^\n]*@boundary\([^\n]*\)[^{]*\{(.*?)^}', llvm.read_text(), re.M | re.S)
        self.assertIsNotNone(body)
        self.assertNotIn('%local.', body[1])
        self.executes(source, '633100\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
