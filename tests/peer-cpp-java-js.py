#!/usr/bin/env python3
"""Original Minyar adaptations of individually reviewed GCC and OpenJDK cases."""
import os
import unittest
from regressions import CompilerTestCase


class PeerCppJavaJs(CompilerTestCase):
    def executes(self, source, expected, status=0, stderr='', arguments=()):
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        return super().executes(source, expected, status, stderr, optimizations=variants, arguments=arguments)

    def _execute_fatal_branches(self, definitions, cases):
        """Compile shared branches once; each failure still gets a fresh process."""
        source = list(definitions) + ['let selected = argument(0)']
        for label, body, _, _ in cases:
            source.append(f'if selected == "{label}" {{ {body} }}')
        source.append('print("ready")')
        self.evidence.controls.setdefault('fatal_branch_oracles', []).extend(
            {'label': label, 'stdout': stdout, 'stderr': stderr, 'status': 1}
            for label, _, stdout, stderr in cases)
        llvm = self.executes('\n'.join(source), 'ready\n', arguments=['probe'])
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for optimization in variants:
            for label, _, stdout, stderr in cases:
                with self.subTest(optimization=optimization, branch=label):
                    run = self.evidence.run([llvm.with_suffix('.' + optimization[1:]), label],
                                            timeout=10, phase='execute-fatal-branch')
                    self.assertEqual((run.returncode, run.stdout, run.stderr),
                                     (1, stdout.encode(), stderr.encode()))

    def _execute_long_workload(self, source, expected, timeout=60):
        """Keep finite upstream stress counts with an explicit process bound."""
        llvm = self.executes(source + '\nif argument(0)=="run" { workload() }; print("ready")',
                             'ready\n', arguments=['probe'])
        variants = ('-O0','-O2','-O3','-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0','-O2')
        self.evidence.controls.setdefault('workload_oracles',[]).append({'stdout':expected+'ready\n','stderr':'','status':0,'timeout':timeout})
        for optimization in variants:
            with self.subTest(optimization=optimization):
                run = self.evidence.run([llvm.with_suffix('.'+optimization[1:]),'run'],timeout=timeout,phase='execute-finite-workload')
                self.assertEqual((run.returncode,run.stdout,run.stderr),(0,(expected+'ready\n').encode(),b''))

    def test_five_fill_loops_all_1024_lengths(self):
        # Generator-derived semantic families: j=n+1024*k, j<500000.
        # Repeated JIT warmups are omitted; every size and method is executed.
        # Shared size cell represents Java's mutable static paddedSize.
        self.executes('''function blank(n: Integer): List<Integer> {
let a: List<Integer> = []
let i = 0
while i < n { a.add(0); i = i + 1 }
return a
}
function oldPositive(cell: List<Integer>): Boolean {
let old = cell[0]
cell[0] = old - 1
return old > 0
}
function fill1(a: List<Integer>): List<Integer> {
let left = [a.length]
let k = 0
while oldPositive(left) { a[k] = -1; k = k + 1 }
print(left[0]); print(k)
return a
}
function fill2(n: Integer): List<Integer> {
let a = blank(n)
let left = [a.length]
let k = 0
while oldPositive(left) { a[k] = -1; k = k + 1 }
print(left[0]); print(k)
return a
}
function fill3(size: List<Integer>): List<Integer> {
let a = blank(size[0])
let left = [a.length]
let k = 0
while oldPositive(left) { a[k] = -1; k = k + 1 }
print(left[0]); print(k)
return a
}
function fill4(size: List<Integer>): List<Integer> {
let a = blank(size[0])
let left = a.length
while left > 0 { let i = a.length - left; a[i] = -1; left = left - 1 }
print(left); print(a.length)
return a
}
function fill5(size: List<Integer>): List<Integer> {
let a = blank(size[0])
let count = a.length
let k = count - 1
let i = 0
while i < count { a[k] = -1; k = k - 1; i = i + 1 }
print(k); print(i)
return a
}
function check(a: List<Integer>, n: Integer): Integer {
let errors = 0
if a.length != n { errors = errors + 1 }
let i = 0
while i < a.length { if a[i] != -1 { errors = errors + 1 }; i = i + 1 }
return errors
}
let size = [0]
while size[0] < 1024 {
let n = size[0]
print(check(fill1(blank(n)), n))
print(check(fill2(n), n))
print(check(fill3(size), n))
print(check(fill4(size), n))
print(check(fill5(size), n))
size[0] = size[0] + 1
}
''', ''.join(f'{last}\n{n}\n0\n' for n in range(1024) for last in [-1, -1, -1, 0, -1]))

    def test_point_orientation_keeps_wide_products(self):
        self.executes('''record Point { x: Integer; y: Integer }
function orientation(base: Point, first: Point, second: Point): Integer {
let cross = (first.x - base.x) * (second.y - base.y) - (first.y - base.y) * (second.x - base.x)
print(cross)
if cross > 0 { return 0 }
if cross < 0 { return 1 }
return 2
}
print(orientation(Point { x: -23250; y: 23250 }, Point { x: 23250; y: -23250 }, Point { x: -23250; y: -23250 }))
''', '-2162250000\n1\n')

    def test_recursive_fibonacci_divide_and_square(self):
        self.executes('''function fib(n: Integer): Integer {
if n >= 2 {
if n % 2 == 0 { let a = fib(n / 2); return (a + 2 * fib(n / 2 - 1)) * a }
let a = fib(n / 2 + 1)
let b = fib(n / 2)
return a * a + b * b
}
return n
}
print(fib(30))
''', '832040\n')

    def test_loop_reset_happens_after_accumulating_call(self):
        self.executes('''function accumulate(total: List<Integer>, value: Integer): Integer {
total[0] = total[0] + value
return total[0]
}
function run(total: List<Integer>, j: Integer): Integer {
let i = 0
while i < 9 { j = j + 1; print(accumulate(total, j)); j = 9; i = i + 1 }
return j
}
let total = [0]
print(run(total, 0))
print(total[0])
''', ''.join(f'{n}\n' for n in [1,11,21,31,41,51,61,71,81,9,81]))

    def test_posttested_doubling_keeps_previous_value(self):
        self.executes('''let x = 2
let y = x
let count = 0
let again = true
while again {
x = y
y = 2 * y
count = count + 1
print(x); print(y)
again = !((y - x) >= 20)
}
print(count)
''', ''.join(f'{n}\n' for n in [2,4,4,8,8,16,16,32,32,64,5]))

    def test_four_stores_reverse_fill_all_cells(self):
        self.executes('''let a: List<Integer> = []
let i = 0
while i < 256 { a.add(0); i = i + 1 }
let cursor = a.length
while cursor != 0 {
cursor = cursor - 1; a[cursor] = 6
cursor = cursor - 1; a[cursor] = 6
cursor = cursor - 1; a[cursor] = 6
cursor = cursor - 1; a[cursor] = 6
}
i = 0
while i < a.length { print(a[i]); i = i + 1 }
print(cursor)
''', '6\n' * 256 + '0\n')

    def test_sequential_assignments_are_not_a_swap(self):
        self.executes('''function choose(x: Integer, y: Integer): Integer {
let a = x
let b = y
if a < 0 { a = -a }
if b < 0 { b = -b }
if a < b { let unused = a; a = b; b = a }
return b
}
print(choose(3, 17))
''', '17\n')

    def test_nested_loop_overshoots_outer_bound(self):
        self.executes('''function run(size: Integer, tries: Integer): Integer {
let count = 0
let outer = 0
while count < size {
let i = 1
while i < tries { count = count + 1; i = i + 1 }
outer = outer + 1
}
print(outer)
return count
}
print(run(5, 10))
''', '1\n9\n')

    def test_grouped_division_and_remainder(self):
        self.executes('''function divide(y: Integer): Integer { return ((y * 8192) - 216) / 16 }
function remainder(y: Integer): Integer { return ((y * 8192) - 216) % 16 }
print(divide(1)); print(remainder(1))
print(((1 * 8192) - 216) / 16)
print(((1 * 8192) - 216) % 16)
''', '498\n8\n498\n8\n')

    def test_hex_digit_fold_mutates_accumulator_in_order(self):
        self.executes('''function fold(cell: List<Integer>, digits: List<Integer>, base: Integer): Integer {
cell[0] = 0
let i = 0
while i < digits.length { cell[0] = cell[0] * base + digits[i]; print(cell[0]); i = i + 1 }
return i
}
let cell = [-1]
print(fold(cell, [10, 11, 12, 13, 14], 16))
print(cell[0])
''', '10\n171\n2748\n43981\n703710\n5\n703710\n')

    def test_min32_stride_exits_before_second_list_access(self):
        self.executes('''function first(limit: Integer): Integer {
let i = 0
let result = 0
while i >= limit + -2147483647 { result = result + 42; i = i + -2147483648 }
print(i)
return result
}
function second(initial: Integer, limit: Integer, flag: Boolean, array: List<Integer>): Integer {
let result = 0
let i = initial
let again = true
while again {
if flag { }
result = result + array[i]
i = i + -2147483648
again = i >= limit + -2147483647
}
print(i)
return result
}
print(first(0))
print(second(0, 0, false, [0]))
''', '-2147483648\n42\n-2147483648\n0\n')

    def test_twenty_call_results_stay_live_across_nested_call(self):
        names = [f'a{i}' for i in range(10)]
        declarations = '\n'.join(f'let {name} = next(cell)' for name in names)
        addition = ' + '.join(names)
        self.executes(f'''function next(cell: List<Integer>): Integer {{ let old = cell[0]; cell[0] = old + 1; return old }}
function inner(cell: List<Integer>, extra: Integer): Integer {{
{declarations}
return {addition} + extra
}}
function outer(cell: List<Integer>): Integer {{
{declarations}
let tail = inner(cell, 17)
return {addition} + tail
}}
let cell = [1]
print(outer(cell))
print(cell[0])
''', '227\n21\n')


    def test_signed_comparison_tables_keep_branch_return_values(self):
        domains = [
            [0, 1, -1, (1 << 63) - 1, -(1 << 63), -(1 << 63) + 1,
             0x1A3F237394D36C58, 0x93850E92CAAC1B04 - (1 << 64)],
            [0, 1, -1, (1 << 31) - 1, -(1 << 31), -(1 << 31) + 1,
             0x1A3F2373, 0x93850E92 - (1 << 32)],
        ]
        operations = [('==', lambda a, b: a == b), ('!=', lambda a, b: a != b),
                      ('<', lambda a, b: a < b), ('>=', lambda a, b: a >= b),
                      ('>', lambda a, b: a > b), ('<=', lambda a, b: a <= b)]
        source = [f'function cmp{k}(a: Integer, b: Integer): Integer {{ if a {op} b {{ return 13 }}; return 140 }}'
                  for k, (op, _) in enumerate(operations)]
        expected = []
        for domain, values in enumerate(domains):
            source += [f'let values{domain} = [' + ', '.join(map(str, values)) + ']',
                       f'let i{domain} = 0', f'while i{domain} < 8 {{',
                       f'let j{domain} = 0', f'while j{domain} < 8 {{']
            source += [f'print(cmp{k}(values{domain}[i{domain}], values{domain}[j{domain}]))'
                       for k in range(6)]
            source += [f'j{domain} = j{domain} + 1', '}', f'i{domain} = i{domain} + 1', '}']
            expected += [str(13 if oracle(a, b) else 140) for a in values for b in values
                         for _, oracle in operations]
        self.assertEqual(len(expected), 768)
        self.executes('\n'.join(source) + '\n', '\n'.join(expected) + '\n')

    def test_large_predicate_body_keeps_reverse_index_and_200_stores(self):
        stores = '\n'.join(f'second[{i}] = 0' for i in range(200))
        source = f'''function run(first: List<Integer>, second: List<Integer>, bounds: List<Integer>, flag: Boolean) {{
let start = bounds[0]
let i = start
let active = true
while active {{
let j = -10
while j < 0 {{ j = j + 1 }}
let stop = bounds[1]
first[stop - i + j] = 0
{stores}
i = i + 1
if i == stop {{ active = false }}
}}
}}
'''
        expected = []
        for mode in ('true', 'false'):
            source += f'let a{mode}: List<Integer> = []\nlet b{mode}: List<Integer> = []\nlet i{mode} = 0\n'
            source += f'while i{mode} < 200 {{ a{mode}.add(73); b{mode}.add(91); i{mode} = i{mode} + 1 }}\n'
            source += f'run(a{mode}, b{mode}, [0, 100], {mode})\ni{mode} = 0\n'
            source += f'while i{mode} < 200 {{ print(a{mode}[i{mode}]); print(b{mode}[i{mode}]); i{mode} = i{mode} + 1 }}\n'
            expected += [value for i in range(200) for value in (0 if 1 <= i <= 100 else 73, 0)]
        self.executes(source, ''.join(f'{n}\n' for n in expected))

    def test_unswitch_predicate_all_indices_and_boolean_modes(self):
        source = '''function values(): List<Integer> {
let a: List<Integer> = []
let i = 0
while i < 100 { a.add(i); i = i + 1 }
return a
}
function before(j: Integer): Integer {
let zero = 34
let limit = 2
while limit < 4 { limit = limit * 2 }
let i = 2
while i < limit { zero = 0; i = i + 1 }
let a = values()
let result = 0
i = 0
while i < a.length { if zero == 0 { result = result + a[j] } else { result = result + a[i] }; i = i + 1 }
return result
}
function after(j: Integer, cond: Boolean): Integer {
let a = values()
let result = 0
let i = 0
while i < a.length { if cond { result = result + a[j] }; result = result + a[i]; i = i + 1 }
return result
}
function uncounted(cond: Boolean): Integer {
let a = values()
let result = 0
let i = 0
while i < a.length { if cond { result = result + 1 }; result = result + a[i]; i = a[i] + 1 }
return result
}
let index = 0
while index < 100 { print(before(index)); print(after(index, false)); print(after(index, true)); index = index + 1 }
print(uncounted(false)); print(uncounted(true))
'''
        self.executes(source, ''.join(f'{n}\n' for i in range(100) for n in (100*i, 4950, 4950+100*i)) + '4950\n5050\n')

    def test_deep_straightline_replacement_releases_all_252_lists(self):
        # Preserve graph depth: generated source contains 252 literal allocations.
        source = 'let x = 0\nlet values: List<Integer> = []\n'
        source += 'values = [x % 2]\n' * 252
        source += 'print(values.length)\nprint(values[0])\n'
        self.executes(source, '1\n0\n')

    def test_sequential_subtracted_index_fills_preserve_untouched_tail(self):
        self.executes('''function first(a: List<Integer>) { let i = 3; while i < 100 { a[i - 3] = 42; i = i + 1 } }
function second(a: List<Integer>) { let i = 4; while i < 100 { a[i - 4] = 42; i = i + 1 } }
function show(a: List<Integer>) { let i = 0; while i < a.length { print(a[i]); i = i + 1 } }
let a: List<Integer> = []
let i = 0
while i < 100 { a.add(0); i = i + 1 }
first(a); show(a)
second(a); show(a)
''', ('42\n' * 97 + '0\n' * 3) * 2)

    def test_partial_peel_aliases_return_before_trailing_large_body(self):
        stores = '\n'.join(f'padding[{i}] = 0' for i in range(200))
        source = f'''function barrier() {{ }}
function helper(i: Integer, three: Integer, four: Integer): Integer {{ if three == 4 {{ return four }}; return i }}
function run(one: List<Integer>, two: List<Integer>, alias: List<Integer>, four: Integer, a: List<Integer>, padding: List<Integer>) {{
let step = 1
let amount = 0
while amount < 10 {{ amount = amount + step }}
amount = amount / 10
let three = 2
while three < 4 {{ three = three * 2 }}
let i = 0
let first = true
barrier()
a[0] = -1
while true {{
alias[0] = 0
alias[1] = 0
if first {{ a[i] = 0 }}
if a[0] != 0 {{ }}
if i >= 10 {{ return }}
i = i + amount
first = false
let selected = helper(i, three, four)
if a[selected] != 0 {{ }}
if two[0] != 0 {{ }}
{stores}
if one[1] >= 20 {{ barrier(); return }}
one[1] = one[1] + 1
}}
}}
let one = [0, 0]
let two = [1, 7]
let a: List<Integer> = []
let padding: List<Integer> = []
let i = 0
while i < 1000 {{ a.add(0); padding.add(91); i = i + 1 }}
run(one, two, two, 0, a, padding)
print(one[1]); print(two[0]); print(two[1]); print(a[0])
i = 0
while i < 1000 {{ print(padding[i]); i = i + 1 }}
i = 0
while i < 20000 {{ if helper(i, 2, i) != i {{ fail("helper branch") }}; i = i + 1 }}
print(i)
'''
        self.executes(source, '10\n0\n0\n0\n' + '0\n'*200 + '91\n'*800 + '20000\n')


    def test_sunk_stores_preserve_constructor_loop_and_four_aliases(self):
        self.executes('''function construct(value: Integer): Integer {
let cell = [0]
let i = 0
while i < 32 { if i < 10 { cell[0] = value }; i = i + 1 }
cell[0] = value
return cell[0]
}
function copy(dst: List<Integer>, offset: Integer) {
let src = [construct(1), 2, 3, 4]
let i = 0
while i < 4 { dst[offset + i] = src[i]; i = i + 1 }
}
function update(a: List<Integer>, v1: List<Integer>, v2: List<Integer>, v3: List<Integer>, v4: List<Integer>) {
let i = 0
while i < a.length {
let old = a[i]
a[i] = old + 1
v1[0] = old + 1
v2[0] = old + 2
v3[0] = old + 3
v4[0] = old + 4
i = i + 1
}
}
let dst = [0, 0, 0, 0, 0]
copy(dst, 1)
let i = 0
while i < 5 { print(dst[i]); i = i + 1 }
let a: List<Integer> = []
i = 0
while i < 1000 { a.add(0); i = i + 1 }
let value = [0]
let round = 1
while round <= 100 {
update(a, value, value, value, value)
i = 0
while i < 1000 { if a[i] != round { fail("array update") }; i = i + 1 }
print(value[0])
round = round + 1
}
''', '0\n1\n2\n3\n4\n' + ''.join(f'{i+3}\n' for i in range(1, 101)))

    def test_negative_loop_limit_and_buffer_output_positions(self):
        self.executes('''function barrier() { }
function simple(flag: Boolean, a: List<Integer>) {
let limit = 3
if flag { limit = -2147483648 }
barrier()
let i = 0
while i < limit { a[i * 2] = 666 + i; i = i + 1 }
}
function encode(src: List<Integer>, dst: List<Integer>, position: List<Integer>): Integer {
let size = 0
let tmp = [0, 0, 0]
let cursor = 0
while cursor < src.length {
let output = tmp
let c = src[cursor]
cursor = cursor + 1
if c % 3 == 0 { size = -2147483648 } else { output[0] = 0; output[1] = 1; output[2] = 2; size = 3 }
if dst.length - position[0] < size { return 102 }
let i = 0
while i < size { dst[position[0]] = output[i]; position[0] = position[0] + 1; i = i + 1 }
print(position[0])
}
return 103
}
let a: List<Integer> = []
let dst: List<Integer> = []
let i = 0
while i < 10000 { a.add(0); dst.add(91); i = i + 1 }
simple(true, a)
i = 0
while i < a.length { if a[i] != 0 { fail("negative limit") }; i = i + 1 }
print(0)
simple(false, a)
i = 0
while i < a.length {
let expected = 0
if i == 0 { expected = 666 }
if i == 2 { expected = 667 }
if i == 4 { expected = 668 }
if a[i] != expected { fail("positive limit") }
i = i + 1
}
print(3)
let src: List<Integer> = []
i = 0
while i < 100 { if i % 31 == 0 { src.add((i % 3) * 3) } else { src.add(1 + (i % 3) * 3) }; i = i + 1 }
let position = [0]
print(encode(src, dst, position))
i = 0
while i < dst.length {
let expected = 91
if i < 288 { expected = i % 3 }
if dst[i] != expected { fail("buffer output") }
i = i + 1
}
print(position[0])
''', '0\n3\n' + ''.join(f'{3 * (i + 1 - (i // 31 + 1))}\n' for i in range(100)) + '103\n288\n')

    def test_counted_backedge_store_between_two_empty_loops(self):
        self.executes('''function fill(a: List<Integer>, increment: Integer) {
let i = 0
while true {
let j = 0
while j < 10 { j = j + 1 }
a[i] = i
i = i + 1
if i >= 100 { return }
j = 0
while j < 10 { j = j + 1 }
}
}
let a: List<Integer> = []
let i = 0
while i < 100 { a.add(-1); i = i + 1 }
fill(a, 1)
i = 0
while i < 100 { print(a[i]); i = i + 1 }
''', ''.join(f'{i}\n' for i in range(100)))

    def test_inner_condition_final_false_increment_survives_100_calls(self):
        self.executes('''function advance(cell: List<Integer>): Boolean { cell[0] = cell[0] + 3; return cell[0] < 5 }
function run(f: Integer, g: Integer, totals: List<Integer>, a: List<Integer>) {
let local = 23
let outer = 7
let limit = 12
let inner = [32901]
let nested = 43741
while outer < 325 {
inner[0] = 1
while advance(inner) {
a[inner[0] - 1] = 906
nested = inner[0]
while nested < 5 { totals[1] = totals[1] + nested; local = local + nested; nested = nested + 2 }
}
outer = outer + 1
}
totals[0] = totals[0] + outer + limit + inner[0] + nested
}
let totals = [0, 0]
let a: List<Integer> = []
let i = 0
while i < 400 { a.add(0); i = i + 1 }
i = 0
while i < 100 { run(3, 5, totals, a); print(totals[0]); print(totals[1]); i = i + 1 }
i = 0
while i < 400 { print(a[i]); i = i + 1 }
''', ''.join(f'{350*i}\n{1272*i}\n' for i in range(1, 101)) + ''.join(f'{906 if i == 3 else 0}\n' for i in range(400)))

    def test_posttested_fills_with_identity_load_store_backedges(self):
        source = []
        expected = []
        for method, start in enumerate((6, 5, 7, 9), 101):
            body = 'a[i] = a[i]' if method < 103 else ('other[i] = other[i]' if method == 103 else 'if i % 2 == 0 { }')
            source.append(f'''function fill{method}(): List<Integer> {{
let a: List<Integer> = []
let other: List<Integer> = []
let j = 0
while j < 25 {{ a.add(0); other.add(0); j = j + 1 }}
let i = {start}
let active = true
while active {{
a[i] = 1
{body}
i = i + 1
active = i < 21
}}
j = 0
while j < 25 {{ if other[j] != 0 {{ fail("identity store") }}; j = j + 1 }}
return a
}}
let a{method} = fill{method}()
let i{method} = 0
while i{method} < 25 {{ print(a{method}[i{method}]); i{method} = i{method} + 1 }}
''')
            expected += [int(start <= i < 21) for i in range(25)]
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_alias_loads_return_and_store_same_nested_loop_value(self):
        source = []
        for method, body in ((2, 'second[0] = 42; owner[0] = first[0]'),
                             (3, 'owner[0] = first[0] + i; second[0] = 42'),
                             (4, 'owner[0] = first[0] + j; second[0] = 42')):
            source.append(f'''function run{method}(first: List<Integer>, second: List<Integer>, owner: List<Integer>): Integer {{
let i = 0
while i < 10 {{
let j = 0
while j < 10 {{ {body}; j = j + 1 }}
j = 0
while j < 10000 {{ j = j + 1 }}
i = i + 1
}}
return owner[0]
}}
''')
        source.append('let value = [42]\nlet owner = [0]\nlet round = 0\nwhile round < 10 {')
        for method in (2, 3, 4):
            source.append(f'print(run{method}(value, value, owner)); print(owner[0])')
        source.append('round = round + 1\n}')
        self.executes('\n'.join(source), '42\n42\n51\n51\n51\n51\n' * 10)

    def test_signed_byte_value_domain_divides_toward_zero(self):
        values = [((i + 128) % 256) - 128 for i in range(258)]
        source = ['function literal(a: Integer): Integer { return a / 2 }',
                  'function parameter(a: Integer, b: Integer): Integer { return a / b }',
                  'let values = [' + ', '.join(map(str, values)) + ']',
                  'let i = 0',
                  'while i < values.length { print(literal(values[i])); print(parameter(values[i], 2)); i = i + 1 }']
        expected = [(-1 if n < 0 else 1) * (abs(n) // 2) for n in values]
        self.assertEqual(len(values), 258)
        self.executes('\n'.join(source), ''.join(f'{n}\n{n}\n' for n in expected))

    def test_signed_absolute_value_small_finite_domain(self):
        self.executes('''function first(value: Integer): Integer { if value < 0 { return -value }; return value }
function third(value: Integer): Integer { if value < 0 { return -value }; return value }
let i = 0
while i <= 10 { print(first(i)); print(first(-i)); print(third(i)); print(third(-i)); i = i + 1 }
''', ''.join(f'{i}\n' * 4 for i in range(11)))

    def test_helper_call_branch_and_disjunction_all_32_iterations(self):
        self.executes('''function first(i: Integer): Integer { return 12 }
function zero(): Integer { return 0 }
let i = 0
while i < 32 {
let value = first(i)
if i == zero() { value = 42 }
if i == 0 || value == 12 { print(value) } else { fail("disjunction") }
i = i + 1
}
''', '42\n' + '12\n' * 31)

    def test_complementary_range_conditions_keep_both_orderings(self):
        source = ['function run(value: Integer) {']
        pairs = [('<', '>='), ('>', '<='), ('>=', '<'), ('<=', '>')]
        expected = []
        for boolean_op in ('&&', '||'):
            for bound in (0, 77):
                for left, right in pairs:
                    source.append(f'print((value {left} {bound}) {boolean_op} (value {right} {bound}))')
                    expected.append('false' if boolean_op == '&&' else 'true')
        source.append('}\nrun(0)\nrun(1)')
        self.executes('\n'.join(source), '\n'.join(expected * 2) + '\n')

    def test_record_argument_reordering_preserves_each_field(self):
        self.executes('''record Triple { a: Integer; b: Integer; c: Integer }
function pair(x: Triple, y: Triple): Integer {
print(x.a); print(x.b); print(x.c)
print(y.a); print(y.b); print(y.c)
return 0
}
function triple(x: Triple, y: Triple, z: Triple): Integer {
let unused = pair(x, y)
print(z.a); print(z.b); print(z.c)
return 0
}
function swap(x: Triple, y: Triple): Integer { return pair(y, x) }
function swapFirst(x: Triple, y: Triple, z: Triple): Integer { return triple(y, x, z) }
function rotate(x: Triple, y: Triple, z: Triple): Integer { return triple(y, z, x) }
let a = Triple { a: 3; b: 4; c: 5 }
let b = Triple { a: 6; b: 7; c: 8 }
let c = Triple { a: 9; b: 10; c: 11 }
print(swap(b, a))
print(swapFirst(b, a, c))
print(rotate(c, a, b))
''', ''.join(f'{n}\n' for n in list(range(3, 9)) + [0] + list(range(3, 12)) + [0] + list(range(3, 12)) + [0]))

    def test_list_length_helper_call_modes_and_text_specialization(self):
        self.executes('''function size(a: List<Integer>): Integer { return a.length }
function textSize(a: Text): Integer { return a.length }
function check(a: List<Integer>, b: List<Integer>, c: List<Integer>) { print(size(a)); print(size(b)); print(size(c)) }
let empty: List<Integer> = []
let two = [1, 2]
let five = [1, 2, 3, 4, 5]
let i = 0
while i < 5 { check(empty, two, five); i = i + 1 }
check(empty, two, five)
check(empty, two, five)
i = 0
while i < 5 { check(empty, two, five); i = i + 1 }
check(empty, two, five)
i = 0
while i < 7 { print(textSize("hest")); i = i + 1 }
''', '0\n2\n5\n' * 13 + '4\n' * 7)

    def test_binding_and_mutable_field_updates_across_helper_scopes(self):
        # Named helpers replace anonymous invocations. Shared parameter cells model
        # mutable module bindings; this does not claim closure or dynamic-object support.
        source = '''function localAnonymous() {
let z = 2
z = z + 4
print(z)
let field = [5]
field[0] = field[0] + 12
print(field[0])
}
function sharedAnonymous(shared: List<Integer>, field: List<Integer>) {
shared[0] = 2
shared[0] = shared[0] + 4
print(shared[0])
field[0] = 5
field[0] = field[0] + 12
print(field[0])
}
function localNamed() {
let z = 3
z = z + 4
print(z)
let field = [5]
field[0] = field[0] + 12
print(field[0])
}
function sharedNamed(shared: List<Integer>, field: List<Integer>) {
shared[0] = 2
shared[0] = shared[0] + 5
print(shared[0])
field[0] = 5
field[0] = field[0] + 12
print(field[0])
}
let shared = [0]
let field = [0]
let z = 2
z = z + 4
print(z)
field[0] = 5
field[0] = field[0] + 12
print(field[0])
localAnonymous()
sharedAnonymous(shared, field)
localNamed()
sharedNamed(shared, field)
let i = 0
while i < 5 {
z = 2
z = z + 4
print(z)
field[0] = 5
field[0] = field[0] + 12
print(field[0])
i = i + 1
}
'''
        for name, args in [('localAnonymous', ''), ('sharedAnonymous', 'shared, field'),
                           ('localNamed', ''), ('sharedNamed', 'shared, field')]:
            # Keep the repetition inside a distinct helper as in each loop wrapper.
            body = source.split(f'function {name}(', 1)[1].split('{', 1)[1].split('}', 1)[0]
            source += f'function {name}Loop(shared: List<Integer>, field: List<Integer>) {{ let j = 0; while j < 5 {{ {body}; j = j + 1 }} }}\n{name}Loop(shared, field)\n'
        outputs = [6, 17, 6, 17, 6, 17, 7, 17, 7, 17]
        for value in (6, 6, 6, 7, 7):
            outputs += [value, 17] * 5
        self.executes(source, ''.join(f'{n}\n' for n in outputs))

    def test_bigint_comparison_in_range_operands_all_call_modes(self):
        pairs = [(1, 2), (0, -1), (-42, -42), (-(1 << 62), -(1 << 63) + 1),
                 (-(1 << 63) + 1, (1 << 63) - 1)]
        extra = (-(1 << 63) + 1, -(1 << 63))
        operations = [('<', lambda a, b: a < b), ('<=', lambda a, b: a <= b),
                      ('>', lambda a, b: a > b), ('>=', lambda a, b: a >= b)]
        source = [f'function compare{k}(a: Integer, b: Integer): Boolean {{ return a {op} b }}'
                  for k, (op, _) in enumerate(operations)]
        expected = []
        for large in (False, True):
            for k, (_, oracle) in enumerate(operations):
                for mode in range(2):
                    for a, b in pairs + ([extra] if large else []):
                        source.append(f'print(compare{k}({a}, {b}))')
                        expected.append(str(oracle(a, b)).lower())
        self.assertEqual(len(expected), 88)
        self.executes('\n'.join(source), '\n'.join(expected) + '\n')

    def test_bigint_same_type_equalities_keep_boundary_operands(self):
        pairs = [(1, 2), (1, -1), (-1, -1), (42, 42),
                 ((1 << 63) - 1, -(1 << 63) + 1)]
        source = ['function equal(a: Integer, b: Integer): Boolean { return a == b }',
                  'function strict(a: Integer, b: Integer): Boolean { return a == b }',
                  'let constant = 42']
        expected = []
        for large in (False, True):
            for helper in ('equal', 'strict'):
                for mode in range(2):
                    for a, b in pairs:
                        args = 'constant, constant' if (a, b) == (42, 42) else f'{a}, {b}'
                        source.append(f'print({helper}({args}))')
                        expected.append(str(a == b).lower())
        self.assertEqual(len(expected), 40)
        self.executes('\n'.join(source), '\n'.join(expected) + '\n')

    def test_nested_index_helpers_and_text_list_getters(self):
        self.executes('''function first(a: List<Integer>): Integer { return a[0] }
function indexed(a: List<Integer>, n: Integer): Integer { return a[n] }
function twiceFirst(a: List<Integer>): Integer { return a[a[0]] }
function twice(a: List<Integer>, n: Integer): Integer { return a[a[n]] }
function thrice(a: List<Integer>, n: Integer): Integer { return a[a[a[n]]] }
function textFirst(a: List<Text>): Text { return a[0] }
function textIndexed(a: List<Text>, n: Integer): Text { return a[n] }
function integers() {
let a = [2, 0, 1]
print(first(a)); print(indexed(a, 0)); print(indexed(a, 1)); print(indexed(a, 2))
print(twiceFirst(a)); print(twice(a, 0)); print(twice(a, 1)); print(twice(a, 2))
print(thrice(a, 0)); print(thrice(a, 1)); print(thrice(a, 2))
}
function texts() {
let a = ["2", "0", "1"]
print(textFirst(a)); print(textIndexed(a, 0)); print(textIndexed(a, 1)); print(textIndexed(a, 2))
}
integers()
let mode = 0
while mode < 6 { integers(); texts(); mode = mode + 1 }
''', '2\n2\n0\n1\n1\n1\n2\n0\n0\n1\n2\n' + ('2\n2\n0\n1\n1\n1\n2\n0\n0\n1\n2\n2\n2\n0\n1\n' * 6))

    def test_index_setters_preserve_all_cells_at_each_stage(self):
        self.executes('''function firstSeven(a: List<Integer>) { a[0] = 7 }
function firstValue(a: List<Integer>, v: Integer) { a[0] = v }
function indexedSeven(a: List<Integer>, n: Integer) { a[n] = 7 }
function indexedValue(a: List<Integer>, n: Integer, x: Integer) { a[n] = x }
function show(a: List<Integer>) { print(a[0]); print(a[1]); print(a[2]) }
let a = [0, 0, 0]
firstSeven(a); show(a)
firstValue(a, 1); show(a)
indexedSeven(a, 2); show(a)
indexedValue(a, 1, 5); show(a)
let i = 0
while i < 3 { indexedValue(a, i, 0); i = i + 1 }
show(a)
''', '7\n0\n0\n1\n0\n0\n1\n0\n7\n1\n5\n7\n0\n0\n0\n')

    def test_repeated_in_bounds_writes_do_not_remove_later_bounds_guard(self):
        self.executes('''function store(a: List<Integer>, i: Integer) { a[i] = 42 }
let a = [1, 2, 3]
let i = 0
while i < 100000 { store(a, 0); i = i + 1 }
print(a[0])
store(a, 4)
print("unreachable")
''', '42\n', 1, 'Minyar stopped: List position 4 is outside its length of 3.\n')

    def test_composite_comparisons_preserve_nested_success_branches(self):
        groups = [(['(x <= y) && (x >= y)', '(x <= y) && (x == y)',
                    '(x <= y) && (y <= x)', '(y == x) && (x <= y)'], lambda x, y: x == y),
                  (['(x < y) || (x > y)'], lambda x, y: x != y),
                  (['(x < y) && (x != y)'], lambda x, y: x < y),
                  (['(x < y) || (x == y)'], lambda x, y: x <= y),
                  (['(x > y) && (x != y)'], lambda x, y: x > y),
                  (['(x > y) || (x == y)'], lambda x, y: x >= y)]
        source = []
        expected = []
        for n, (expressions, oracle) in enumerate(groups):
            source.append(f'function compare{n}(x: Integer, y: Integer, ok: Boolean) {{')
            for expression in expressions:
                source.append(f'if {expression} {{ if !ok {{ fail("unexpected true") }}; print(true) }} else {{ if ok {{ fail("unexpected false") }}; print(false) }}')
            source.append('}')
            for x, y in ((1, 4), (3, 3), (5, 2)):
                result = str(oracle(x, y)).lower()
                source.append(f'compare{n}({x}, {y}, {result})')
                expected.extend([result] * len(expressions))
        self.executes('\n'.join(source), '\n'.join(expected) + '\n')

    def test_empty_loop_exit_index_sums_write_embedded_zero(self):
        self.executes('''function first(a: List<Integer>) {
let i = 0
while i < 2 { i = i + 1 }
a[i + i] = 0
}
function second(a: List<Integer>) {
let i = 0
while i < 2 { i = i + 1 }
a[i + i + i + i] = 0
}
function show(a: List<Integer>) { let i = 0; while i < a.length { print(a[i]); i = i + 1 } }
let a = [73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 0]
first(a); show(a)
a[4] = 77
second(a); show(a)
''', ''.join(f'{n}\n' for n in [73, 74, 75, 76, 0, 78, 79, 80, 81, 82, 0,
                                73, 74, 75, 76, 77, 78, 79, 80, 0, 82, 0]))

    def test_narrow_width_range_boundaries_in_signed64_domain(self):
        source = []
        expected = []
        for bits in (8, 16, 32, 64):
            bound = (1 << (bits - 1)) - 1
            values = [0, 1, bound] + ([bound + 1, (1 << bits) - 1] if bits < 64 else [])
            source.append(f'function inside{bits}(value: Integer, ok: Boolean) {{ if value >= 1 && value <= {bound} {{ if !ok {{ fail("range true") }}; print(true) }} else {{ if ok {{ fail("range false") }}; print(false) }} }}')
            for value in values:
                result = str(1 <= value <= bound).lower()
                source.append(f'inside{bits}({value}, {result})')
                expected.append(result)
        self.assertEqual(len(expected), 18)
        self.executes('\n'.join(source), '\n'.join(expected) + '\n')

    def test_impossible_comparison_branches_have_live_failure_oracle(self):
        expressions = ['(x == y) && (x != y)', '(x < y) && (x > y)', '(x < y) && (y < x)',
                       '(x == y) || (x != y)', '(x >= y) || (x < y)', '(x <= y) || (y < x)']
        source = []
        for n, expression in enumerate(expressions):
            if n < 3:
                body = f'if {expression} {{ fail("contradiction") }}'
            else:
                body = f'if {expression} {{ }} else {{ fail("exhaustive comparison") }}'
            source.append(f'function check{n}(x: Integer, y: Integer) {{ {body}; print({n}) }}')
        source.append('function all(x: Integer, y: Integer) { ' + '; '.join(f'check{n}(x, y)' for n in range(6)) + ' }')
        source.append('all(0, 0); all(1, 2); all(4, 3)')
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in range(6)) * 3)

    def test_record_reconstruction_retains_nested_fields_while_swapping(self):
        self.executes('''record Nested { tag: Integer; values: List<Integer> }
record Whole { a: Integer; b: Integer; cells: List<Integer>; nested: Nested }
function rebuild(old: Whole): Whole { return Whole { a: old.b; b: old.a; cells: [0, 0, 0, 0, 0, 0]; nested: old.nested } }
let value = Whole { a: 6; b: 12; cells: [1, 2, 3, 4, 5, 6]; nested: Nested { tag: 7; values: [8, 9, 10, 11, 12, 13, 14, 15] } }
value = rebuild(value)
print(value.a); print(value.b)
let i = 0
while i < 6 { print(value.cells[i]); i = i + 1 }
print(value.nested.tag)
i = 0
while i < 8 { print(value.nested.values[i]); i = i + 1 }
''', '12\n6\n' + '0\n' * 6 + ''.join(f'{n}\n' for n in range(7, 16)))

    def test_recursive_cursor_refill_returns_record_after_state_change(self):
        self.executes('''record Unit { value: Integer }
function fetch(state: List<Integer>) { state[1] = 128 }
function next(state: List<Integer>, flag: List<Integer>): Unit {
if state[0] >= state[1] {
if flag[0] != 0 { flag[0] = 0; fetch(state); return next(state, flag) }
flag[0] = 1
return Unit { value: 65535 }
}
return Unit { value: 0 }
}
let state = [0, 0]
let flag = [0]
let i = 0
while i < 16 { let result = next(state, flag); print(result.value); i = i + 1 }
print(state[0]); print(state[1]); print(flag[0])
''', '65535\n' + '0\n' * 15 + '0\n128\n0\n')

    def test_descending_adjacent_swaps_preserve_all_duplicate_values(self):
        values = [11, 12, 46, 3, 2, 2, 3, 2, 1, 3, 2, 1, 2]
        self.executes('''let values = [11, 12, 46, 3, 2, 2, 3, 2, 1, 3, 2, 1, 2]
let count = 13
let i = 0
while i < count {
let j = count - 1
while j > i {
if values[j - 1] < values[j] { let old = values[j]; values[j] = values[j - 1]; values[j - 1] = old }
j = j - 1
}
i = i + 1
}
i = 0
while i < count { print(values[i]); i = i + 1 }
''', ''.join(f'{n}\n' for n in sorted(values, reverse=True)))

    def test_computed_store_indices_survive_record_return_calls(self):
        source = '''record Four { p: Integer; q: Integer; r: Integer; s: Integer }
function get(value: Four): Four { return value }
function check(a: List<Integer>, count: Integer) { print(count); let i = 0; while i < count { print(a[i]); i = i + 1 } }
let value = Four { p: 13; q: 14; r: 15; s: 16 }
let a: List<Integer> = []
let i = 0
while i < 40 { a.add(-1); i = i + 1 }
let cursor = 0
'''
        expressions = ['1', '11', '2', '12', '3', 'get(value).p', '4', 'get(value).q', '5', 'get(value).r', '6', 'get(value).s']
        source += '\n'.join(f'a[cursor] = {expression}; cursor = cursor + 1' for expression in expressions)
        source += '\ncheck(a, cursor)\ni = cursor\nwhile i < a.length { if a[i] != -1 { fail("untouched tail") }; i = i + 1 }\n'
        self.executes(source, ''.join(f'{n}\n' for n in [12, 1, 11, 2, 12, 3, 13, 4, 14, 5, 15, 6, 16]))

    def test_division_guard_all_68_stops_and_phi_store_order(self):
        source = '''function run(stop: Integer, a: List<Integer>, previous: Integer): Integer {
let marks: List<Boolean> = []
let k = 0
while k < 400 { marks.add(false); k = k + 1 }
let quotient = 577
let i = 9
while i < 379 {
let divisor = 68
while divisor > stop {
marks[divisor + 1] = true
quotient = -42360 / divisor
a[i + 1] = previous
previous = divisor - 1
divisor = divisor - 1
}
i = i + 1
}
k = 0
while k < 400 {
let expected = k >= stop + 2 && k <= 69
if marks[k] != expected { fail("Boolean domain") }
k = k + 1
}
return quotient
}
let stop = 0
while stop < 68 {
let a: List<Integer> = []
let i = 0
while i < 400 { a.add(0); i = i + 1 }
let round = 0
while round < 10 {
print(run(stop, a, 0))
i = 0
while i < 400 {
let expected = 0
if i >= 10 && i <= 379 {
if stop == 67 { if i > 10 { expected = 67 } } else { expected = stop + 1 }
}
if a[i] != expected { fail("phi store order") }
i = i + 1
}
round = round + 1
}
stop = stop + 1
}
'''
        self.executes(source, ''.join(f'{-(42360 // (stop+1))}\n' * 10 for stop in range(68)))

    def test_peeled_dead_index_paths_and_odd_trip_sum(self):
        self.executes('''function first(a: List<Integer>, index: Integer, increment: Integer): Integer {
let store = -1
while index < 10 {
if increment == 42 { return store }
if store > 0 && a[store] == 42 { return store }
if index == 42 { a[store] = 1; return store }
store = store + 1
index = index + increment
}
return store
}
function second(a: List<Integer>, index: Integer, initial: Integer): Integer {
let store = initial
while index < 10 {
if index == 42 { return a[store - 1] }
store = 0
index = index + 1
}
return a[42]
}
function third(a: List<Integer>, index: Integer, flag: Boolean): Integer {
let store = -2147483648
while index < 10 {
if flag { return 0 }
if index == 42 { return a[store - 1] }
store = 0
index = index + 1
}
return a[42]
}
function empty(limit: Integer): Integer { let i = 0; while i < limit { i = i + 1 }; return i }
function sum(a: List<Integer>): Integer { let result = 0; let i = 0; while i < 5 { result = result + a[i]; i = i + 1 }; return result }
let a: List<Integer> = []
let i = 0
while i < 100 { a.add(0); i = i + 1 }
let mode = 0
while mode < 5 {
print(first(a, 0, 1)); print(second(a, 0, -2147483648)); print(third(a, 0, false))
print(empty(100)); print(sum(a))
i = 0
while i < 100 { if a[i] != 0 { fail("unexpected store") }; i = i + 1 }
mode = mode + 1
}
print(second(a, 0, -9223372036854775808))
print(sum([1, 3, 5, 7, 9, 99]))
''', '9\n0\n0\n100\n0\n' * 5 + '0\n25\n')

    def test_postincrement_and_postdecrement_conditions_precede_body_checks(self):
        self.executes('''function advance(cell: List<Integer>): Boolean { let old = cell[0]; cell[0] = old + 1; return old != 0 }
function retreat(cell: List<Integer>): Boolean { let old = cell[0]; cell[0] = old - 1; return old != 0 }
function first(initial: Integer, limit: Integer): Integer {
let i = [initial]
let result = 0
while advance(i) { if result >= limit { return result }; result = i[0] * 2 }
return result
}
function second(initial: Integer, limit: Integer): Integer {
let i = [initial]
let result = 0
while retreat(i) { if result <= limit { return result }; result = i[0] * 2 }
return result
}
function third(initial: Integer, limit: Integer, a: List<Integer>) {
let i = [initial]
while advance(i) { if a[i[0] - 1] >= limit { return }; a[i[0]] = i[0] * 2 }
}
function fourth(initial: Integer, limit: Integer, a: List<Integer>) {
let i = [initial]
while retreat(i) { if a[a.length + i[0] + 1] <= limit { return }; a[a.length + i[0]] = i[0] * 2 }
}
print(first(1, 10)); print(second(-1, -10))
let a = [0, 0, 0, 0, 0, 0, 0, 0]
third(1, 10, a)
let i = 0
while i < 8 { print(a[i]); a[i] = 0; i = i + 1 }
fourth(-1, -10, a)
i = 0
while i < 8 { print(a[i]); i = i + 1 }
''', '10\n-10\n' + ''.join(f'{n}\n' for n in [0, 0, 4, 6, 8, 10, 0, 0, 0, 0, 0, -10, -8, -6, -4, 0]))

    def test_loop_store_motion_preserves_alias_reads_and_exit_paths(self):
        bodies = {
            'after1': 'let i = 0; while i < 1000 { a[idx] = i; i = i + 1 }',
            'after2': 'let i = 0; while i < 1000 { a[idx] = i; b[i % 10] = i; i = i + 1 }',
            'after3': 'let i = 0; while i < 1000 { a[idx] = i; if a[0] == -1 { return 0 }; i = i + 1 }',
            'after4': 'let i = 0; while i < 1000 { if a[0] == -2 { return 0 }; a[idx] = i; i = i + 1 }',
            'after5': 'let i = 0; while i < 1000 { ' + '; '.join(f'a[idx + {j}] = i' for j in range(6)) + '; i = i + 1 }',
            'after6': 'let i = 0; while i < 1000 { a[idx] = i; if flags[i] { return 0 }; i = i + 1 }',
            'after7': 'let i = 0; while i < 1000 { let j = 0; while j <= 42 { cells[i] = j; j = j + 1 }; i = i + 1 }',
            'stores1': 'a[0] = 0; a[1] = 1; a[2] = 2; a[0] = 0; a[1] = 1; a[2] = 2',
            'stores2': 'a[idx + 0] = 0; a[idx + 1] = 1; a[idx + 2] = 2; a[idx + 0] = 0; a[idx + 1] = 1; a[idx + 2] = 2',
            'stores3': 'bytes[idx + 0] = 0; bytes[idx + 1] = 1; bytes[idx + 2] = 2; bytes[idx + 0] = 0; bytes[idx + 1] = 1; bytes[idx + 2] = 2',
            'before1': 'let i = 0; while i < 1000 { a[idx] = 999; i = i + 1 }',
            'before2': 'let i = 0; while i < 1000 { a[idx] = 999; a[i % 2] = 0; i = i + 1 }',
            'before3': 'let result = 0; let i = 0; while i < 1000 { result = result + a[i % 10]; a[idx] = 999; i = i + 1 }; return result',
            'before4': 'let i = 0; while i < 1000 { if idx / (i + 1) > 0 { return 0 }; a[idx] = 999; i = i + 1 }',
            'before5': 'let i = 0; while i < 1000 { if i % 2 == 0 { a[idx] = 999 }; i = i + 1 }',
        }
        signature = 'a: List<Integer>, b: List<Integer>, flags: List<Boolean>, cells: List<Integer>, bytes: List<Integer>, idx: Integer'
        source = [f'function {name}({signature}): Integer {{ {body}; return 0 }}' for name, body in bodies.items()]
        source += ['function show(a: List<Integer>) { let i = 0; while i < a.length { print(a[i]); i = i + 1 } }',
                   'let a = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]', 'let b = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]',
                   'let bytes = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]',
                   'let flags: List<Boolean> = []; let cells: List<Integer> = []; let i = 0',
                   'while i < 1000 { flags.add(false); cells.add(0); i = i + 1 }']
        a, b, byte_values, cells = [0]*10, [0]*10, [0]*10, [0]*1000
        expected = []
        calls = ['after1', 'after2', 'after3', 'after4', 'after5', 'after6', 'after6last', 'after7',
                 'stores1', 'stores2', 'stores3', 'before1', 'before2', 'before3', 'before4', 'before5']
        for name in calls:
            method = 'after6' if name == 'after6last' else name
            if name.startswith('stores'):
                target = 'bytes' if name == 'stores3' else 'a'
                source += [f'{target}[{i}] = -1' for i in range(3)]
                if target == 'bytes': byte_values[:3] = [-1]*3
                else: a[:3] = [-1]*3
            elif name == 'after5':
                source += [f'a[{i}] = -1' for i in range(6)]; a[:6] = [-1]*6
            else:
                source.append('a[0] = -1'); a[0] = -1
            if name == 'after6last': source.append('flags[999] = true')
            result = 0
            if name == 'after2': b[:] = range(990, 1000)
            if name == 'after5': a[:6] = [999]*6
            elif name == 'after7': cells[:] = [42]*1000
            elif name in ('stores1', 'stores2'): a[:3] = range(3)
            elif name == 'stores3': byte_values[:3] = range(3)
            else:
                if name == 'before2': a[1] = 0
                if name == 'before3': result = a[0] + 99*999 + 100*sum(a[1:])
                a[0] = 999
            source += [f'print({method}(a, b, flags, cells, bytes, 0))', 'show(a); show(b); show(bytes); show(cells)']
            expected += [result] + a + b + byte_values + cells
        # Supplement early exits with nonzero sentinels to expose hoisting.
        source += ['a[0] = -2', 'print(after4(a, b, flags, cells, bytes, 0)); print(a[0])',
                   'a[1] = 73', 'print(before4(a, b, flags, cells, bytes, 1)); print(a[1])']
        expected += [0, -2, 0, 73]
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_alternating_increment_double_traps_before_next_store(self):
        self.executes('''function run(a: List<Integer>, idx: Integer): Integer {
let result = 0
let i = 0
while i < 1000 {
if i == 125 { print(a[idx]); print(result) }
if i % 2 == 1 { result = result * 2 } else { result = result + 1 }
a[idx] = 999
i = i + 1
}
return result
}
let a = [-1, 0, 0, 0, 0, 0, 0, 0, 0, 0]
print(run(a, 0))
''', '999\n9223372036854775807\n', 1, 'Minyar stopped: this Integer calculation is outside the supported range.\n')

    def test_bigint_arithmetic_safe_call_sequences_literal_and_parameter(self):
        minimum, maximum = -(1 << 63), (1 << 63) - 1
        add = [(0, 1), (2, 3), (minimum, 0)] * 2
        add += [(0, 1), (2, 3), (maximum, 0)] * 2
        add += [(0, 1), (2, 3), (4, 5), (-(1 << 62), -(1 << 62)), (0, 1), (2, 3), (4, 5)]
        divide = [(0, 1), (-32, 9), (14, 5)] * 3 + [(minimum, 1)] + [(0, 1), (-32, 9), (14, 5)]
        remainder = [(0, 1), (-32, 9), (14, 5)] * 4
        source, expected = [], []
        for name, operator, values in [('add', '+', add), ('divide', '/', divide), ('remainder', '%', remainder)]:
            source.append(f'function {name}(a: Integer, b: Integer): Integer {{ return a {operator} b }}')
            for a, b in values:
                quotient = 0 if operator == '+' else (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
                result = a + b if operator == '+' else quotient if operator == '/' else a - quotient*b
                source += [f'print(({a}) {operator} ({b}))', f'print({name}({a}, {b}))']
                expected += [result, result]
        self.assertEqual(len(expected), 88)
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_bigint_overflow_and_zero_become_fatal_checked_arithmetic(self):
        cases = [('+', -(1 << 62)-1, -(1 << 62), 'this Integer calculation is outside the supported range.'),
                 ('/', -(1 << 63), -1, 'this Integer division is outside the supported range.'),
                 ('%', -(1 << 63), -1, 'this Integer division is outside the supported range.'),
                 ('/', 42, 0, 'an Integer cannot be divided by zero.'),
                 ('%', 42, 0, 'an Integer cannot be divided by zero.')]
        for operator, a, b, diagnostic in cases:
            for parameter in (False, True):
                with self.subTest(operator=operator, parameter=parameter):
                    source = f'function calculate(a: Integer, b: Integer): Integer {{ return a {operator} b }}\nprint("before")\n'
                    expression = f'calculate({a}, {b})' if parameter else f'({a}) {operator} ({b})'
                    source += f'print({expression})\nprint("unreachable")\n'
                    self.executes(source, 'before\n', 1, 'Minyar stopped: ' + diagnostic + '\n')

    def test_terminal_arithmetic_operand_preserves_exact_effect_prefix(self):
        for operator in ('+', '-', '*', '/', '%'):
            for terminal_left in (True, False):
                with self.subTest(operator=operator, terminal_left=terminal_left):
                    left = 'fail("operand failure"); return 1' if terminal_left else 'return 1'
                    source = f'''function left(): Integer {{ print(1); {left} }}
function right(): Integer {{ print(2); fail("operand failure"); return 1 }}
print(left() {operator} right())
print("unreachable")
'''
                    self.executes(source, '1\n' if terminal_left else '1\n2\n', 1,
                                  'Minyar stopped: operand failure\n')

    def test_typed_push_helpers_return_length_and_preserve_all_elements(self):
        source, expected = [], []
        for kind, starts in [('Integer', (0, 1, 2)), ('Text', (1, 2, 3))]:
            for count in range(4):
                helper = f'push{kind}{count}'
                values = range(1, count+1)
                additions = '; '.join(f'a.add({n})' if kind == 'Integer' else f'a.add("{n}")' for n in values)
                source.append(f'function {helper}(a: List<{kind}>): Integer {{ {additions}; return a.length }}')
                for start in starts:
                    initial = list(range(1, start+1))
                    literal = ', '.join(str(n) if kind == 'Integer' else f'"{n}"' for n in initial)
                    name = f'a{kind}{count}n{start}'
                    source += [f'let {name}: List<{kind}> = [{literal}]', f'print({helper}({name}))',
                               f'let i{name} = 0; while i{name} < {name}.length {{ print({name}[i{name}]); i{name} = i{name} + 1 }}']
                    expected += [start+count] + initial + list(range(1, count+1))
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_shift_derived_divisors_preserve_exact_integer_quotients(self):
        pairs = [(value, divisor) for value in (-1048544, -1048543)
                 for divisor in (1, 16, 262144, 1073741824)]
        pairs += [(value, divisor) for value in (-9007199254740928, -9007199254740927)
                  for divisor in (16, 70368744177664)]
        source = ['function divide(a: Integer, b: Integer): Integer { return a / b }']
        expected = []
        for a, b in pairs:
            source += [f'print(({a}) / {b})', f'print(divide({a}, {b}))']
            expected += [-(abs(a)//b)] * 2
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_unsigned_source_values_divide_as_positive_signed64_integers(self):
        # Exhaustively derive the finite upstream domain, then use representable
        # values; the generated Minyar does not emulate unsigned arithmetic.
        pairs = []
        value = 10
        while value < 139045193:
            unsigned = value % (1 << 32)
            divisor = 8 << ((value ^ 12345) & 15)
            pairs.append((unsigned, divisor))
            value = (value + 1) * -3
        self.assertEqual(len(pairs), 16)
        source = ['function quotient(a: Integer, b: Integer): Integer { return a / b }',
                  'function remainder(a: Integer, b: Integer): Integer { return a % b }']
        expected = []
        for a, b in pairs:
            source += [f'print({a} / {b}); print({a} % {b})', f'print(quotient({a}, {b})); print(remainder({a}, {b}))']
            expected += [a//b, a%b] * 2
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_lexicographic_record_comparison_exact_rectangular_domain(self):
        self.executes('''record Real { significant: Integer; exponent: Integer }
function first(a: Real, b: Real): Integer {
if a.exponent > b.exponent { return 1 }
if a.exponent < b.exponent { return -1 }
if a.significant > b.significant { return 1 }
if a.significant < b.significant { return -1 }
return 0
}
function second(a: Real, b: Real): Integer {
if a.exponent > b.exponent { return 1 }
if a.exponent < b.exponent { return -1 }
if a.significant > b.significant { return 1 }
if a.significant < b.significant { return -1 }
return 0
}
let a = [Real { significant: 0; exponent: 0 }, Real { significant: 1; exponent: 0 }, Real { significant: 0; exponent: 1 }, Real { significant: 1; exponent: 1 }]
let i = 0
while i <= 3 {
let j = 0
while j < 3 { print(first(a[i], a[j])); print(second(a[i], a[j])); j = j + 1 }
i = i + 1
}
''', ''.join(f'{(i > j) - (i < j)}\n' * 2 for i in range(4) for j in range(3)))

    def test_repeated_nested_counter_loops_preserve_both_final_stores(self):
        # Ten independent source cases per process keep the hang detector useful;
        # all 100 reset-and-run invocations from the upstream source are checked.
        for batch in range(10):
            with self.subTest(batch=batch):
                source = f'''function callee(counter: List<Integer>) {{
let i = 0
while i < 100 {{
let j = 0
while j < 10 {{ counter[0] = counter[0] + j; j = j + 1 }}
i = i + 1
}}
}}
function run(first: List<Integer>, second: List<Integer>) {{
let i = 0
while i < 10000 {{
callee(first)
second[0] = 0
let j = 0
while j < 10 {{ second[0] = first[0] + j; j = j + 1 }}
i = i + 1
}}
}}
let first = [0]
let second = [0]
let round = {batch*10}
while round < {(batch+1)*10} {{
first[0] = 0
second[0] = 0
run(first, second)
print(round); print(first[0]); print(second[0])
round = round + 1
}}
'''
                self.executes(source, ''.join(f'{i}\n45000000\n45000009\n' for i in range(batch*10, (batch+1)*10)))

    def test_mathexact_constant_pairs_use_signed64_oracle(self):
        cases = []
        for width in (32, 64):
            minimum, maximum = -(1 << (width-1)), (1 << (width-1))-1
            pairs = [(5, 7), (maximum, 1), (minimum, -1), (maximum, -1),
                     (minimum, 1), (maximum//2, maximum//2),
                     (maximum//2, maximum//2+3), (maximum, minimum)]
            for symbol, oracle in [('+', lambda a, b: a+b), ('-', lambda a, b: a-b), ('*', lambda a, b: a*b)]:
                for a, b in pairs:
                    cases.append((symbol, a, b, oracle(a, b)))
        self.assertEqual(len(cases), 48)
        source = ['function add(a: Integer, b: Integer): Integer { return a + b }',
                  'function subtract(a: Integer, b: Integer): Integer { return a - b }',
                  'function multiply(a: Integer, b: Integer): Integer { return a * b }']
        expected, traps = [], []
        names = {'+': 'add', '-': 'subtract', '*': 'multiply'}
        for symbol, a, b, result in cases:
            expressions = [f'({a}) {symbol} ({b})', f'{names[symbol]}({a}, {b})']
            if -(1 << 63) <= result < (1 << 63):
                source += [f'print({expression})' for expression in expressions]
                expected += [result, result]
            else:
                traps.append((symbol, a, b))
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))
        for symbol, a, b in traps:
            for parameter in (False, True):
                with self.subTest(symbol=symbol, a=a, b=b, parameter=parameter):
                    expression = f'calculate({a}, {b})' if parameter else f'({a}) {symbol} ({b})'
                    self.executes(f'function calculate(a: Integer, b: Integer): Integer {{ return a {symbol} b }}\nprint("before")\nprint({expression})\n',
                                  'before\n', 1, 'Minyar stopped: this Integer calculation is outside the supported range.\n')

    def test_large_safe_products_in_bindings_conditions_returns_and_arguments(self):
        expressions = ['1 * 4608 * 1024 * 1024', '4608 * 1024 * 1024',
                       '(4608 * 1024 * 1024)', '4608 * 1024 * 1024 * i',
                       '(1 * (4608 * (1024 * 1024)) + 2)']
        answers = [4831838208] * 4 + [4831838210]
        source = ['function called(value: Integer): Integer { print("called"); return value }']
        expected = []
        for n, (expression, result) in enumerate(zip(expressions, answers)):
            source += [f'function shape{n}(i: Integer): Integer {{ let bound = {expression}; print(bound); if {expression} != 0 {{ print(true) }}; while {expression} != 0 {{ print("loop"); return bound }}; return -1 }}',
                       f'print(shape{n}(1))']
            expected += [str(result), 'true', 'loop', str(result)]
        source += ['function returned(): Integer { return (4608 * 1024 * 1024) + (4608 * 1024 * 1024) }',
                   'print(returned())', 'called(4608 * 1024 * 1024)', 'let result = called(4608 * 1024 * 1024)', 'print(result)']
        expected += ['9663676416', 'called', 'called', '4831838208']
        self.executes('\n'.join(source), '\n'.join(expected) + '\n')

    def test_overflow_context_stops_before_binding_branch_return_or_callee(self):
        products = ['1 * limit * 1024 * 1024', 'limit * 1024 * 1024',
                    '(limit * 1024 * 1024)', 'limit * 1024 * 1024 * i',
                    '(1 * (limit * (1024 * 1024)) + 2)',
                    '(4608 * 1024 * 1024) * (4608 * 1024 * 1024)']
        definitions, cases = [], []
        error = 'Minyar stopped: this Integer calculation is outside the supported range.\n'
        for index, product in enumerate(products):
            for context in ('binding', 'if', 'while'):
                if context == 'binding': body = f'let value = {product}; print(value)'
                elif context == 'if': body = f'if {product} != 0 {{ print("body") }}'
                else: body = f'while {product} != 0 {{ print("body"); return }}'
                name = f'run{index}{context}'
                definitions.append(f'function {name}(limit: Integer, i: Integer) {{ {body} }}')
                cases.append((name, f'{name}(9223372036854775807, 1)', '', error))
        definitions.append('function called(value: Integer): Integer { print("callee"); return value }')
        for context in ('return', 'argument', 'bound', 'nested'):
            expression = '(limit * 1024 * 1024) + (limit * 1024 * 1024)' if context == 'return' else 'limit * 1024 * 1024'
            if context == 'return': body = f'return {expression}'
            elif context == 'argument': body = f'return called({expression})'
            elif context == 'nested': body = f'return called(called({expression}))'
            else: body = f'let result = called({expression}); return result'
            name = f'run{context}'
            definitions.append(f'function {name}(limit: Integer): Integer {{ {body} }}')
            cases.append((name, f'print({name}(9223372036854775807))', '', error))
        self._execute_fatal_branches(definitions, cases)

    def test_computed_large_index_checks_arithmetic_before_bounds(self):
        for factor, diagnostic in [(4608, 'List position 4831838208 is outside its length of 10.'),
                                   (9223372036854775807, 'this Integer calculation is outside the supported range.')]:
            for kind, initial, replacement in [('Integer', '0', '1'), ('Text', '"old"', '"replacement"')]:
                with self.subTest(factor=factor, kind=kind):
                    source = f'function store(a: List<{kind}>, factor: Integer) {{ a[factor * 1024 * 1024] = {replacement} }}\n'
                    source += 'let a = [' + ', '.join([initial]*10) + ']\n'
                    source += f'store(a, {factor})\nprint("unreachable")\n'
                    self.executes(source, '', 1, 'Minyar stopped: ' + diagnostic + '\n')

    def test_nested_record_arithmetic_initializers_preserve_effect_order(self):
        self.executes('''record Leaf { a4: Integer }
record Middle { a2: Integer; child: Leaf }
record Outer { a0: Integer; child: Middle }
record Pair { y: Integer; x: Integer }
let pair = Pair { y: 5; x: 4 * 1024 * 1024 * 1024 }
let nested = Outer { a0: 4 * 1024 * 1024 * 1024; child: Middle { a2: 4 * 1024 * 1024 * 1024; child: Leaf { a4: 4 * 1024 * 1024 * 1024 } } }
print(pair.y); print(pair.x); print(nested.a0); print(nested.child.a2); print(nested.child.child.a4)
''', '5\n' + '4294967296\n'*4)
        for depth in range(3):
            with self.subTest(depth=depth):
                source = ['record Leaf { earlier: Integer; value: Integer }',
                          'record Middle { earlier: Integer; child: Leaf }',
                          'record Outer { earlier: Integer; child: Middle }',
                          'function mark(i: Integer): Integer { print(i); return i }']
                expression = 'Leaf { earlier: mark(1); value: 9223372036854775807 * 1024 * 1024 * 1024 }'
                expected = [1]
                if depth >= 1:
                    expression = 'Middle { earlier: mark(2); child: ' + expression + ' }'; expected.insert(0, 2)
                if depth == 2:
                    expression = 'Outer { earlier: mark(3); child: ' + expression + ' }'; expected.insert(0, 3)
                source.append('let result = ' + expression)
                self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected), 1,
                              'Minyar stopped: this Integer calculation is outside the supported range.\n')

    def test_dead_loop_shapes_complete_and_release_temporary_allocations(self):
        self.executes('''record Empty { }
function never() { while false { } }
function oldLess(cell: List<Integer>): Boolean { let old = cell[0]; cell[0] = old + 1; return old < 10 }
function post() { let i = [0]; while oldLess(i) { } }
function empty() { let i = 0; while i < 10 { i = i + 1 } }
function unused() { let a = 0; let i = 0; while i < 10 { a = a + 1; i = i + 1 } }
function reads() { let a = [0, 0, 0, 0]; let sum = 0; let i = 0; while i < a.length { sum = sum + a[i]; i = i + 1 } }
function discarded() { let i = 0; while i < 10 { Empty { }; i = i + 1 } }
function bound() { let i = 0; while i < 10 { let value = Empty { }; i = i + 1 } }
let mode = 0
while mode < 3 { never(); print(1); post(); print(2); empty(); print(3); unused(); print(4); reads(); print(5); discarded(); print(7); bound(); print(8); mode = mode + 1 }
''', '1\n2\n3\n4\n5\n7\n8\n' * 3)

    def test_observable_loop_exit_values_survive_dead_loop_optimization(self):
        self.executes('''function immediate() { while true { return } }
function oldLess(cell: List<Integer>): Boolean { let old = cell[0]; cell[0] = old + 1; return old < 10 }
function post(): Integer { let i = [0]; while oldLess(i) { }; return i[0] }
function empty(): Integer { let i = 0; while i < 10 { i = i + 1 }; return i }
function counter(): Integer { let a = 0; let i = 0; while i < 10 { a = a + 1; i = i + 1 }; return a }
function reads(): Integer { let a = [0, 0, 0, 0]; let sum = 0; let i = 0; while i < a.length { sum = sum + a[i]; i = i + 1 }; return sum }
function parameter(limit: Integer): Integer { let i = 0; while i < limit { i = i + 1 }; return i }
let mode = 0
while mode < 4 { immediate(); print("returned"); print(post()); print(empty()); print(counter()); print(reads()); mode = mode + 1 }
print(parameter(3)); print(parameter(7)); print(parameter(11)); print(parameter(9))
''', 'returned\n11\n10\n10\n0\n' * 4 + '3\n7\n11\n9\n')

    def test_increment_old_and_new_values_across_scalar_and_storage_helpers(self):
        self.executes('''function inc1(x: Integer, target: List<Integer>) { x = x + 1; target[0] = x }
function inc2(target: List<Integer>) { target[0] = target[0] + 1 }
function inc3(target: List<Integer>, index: Integer) { target[index] = target[index] + 1 }
function inc4(x: Integer, y: Integer): Integer { let old = x; x = x + 1; return old + y }
function inc5(x: Integer, y: Integer): Integer { x = x + 1; return x + y }
function inc6(target: List<Integer>, y: Integer): Integer { let old = target[0]; target[0] = old + 1; return old + y }
function inc7(target: List<Integer>, y: Integer): Integer { target[0] = target[0] + 1; return target[0] + y }
function inc8(target: List<Integer>, y: Integer): Integer { let old = target[0]; target[0] = old + 1; return old + y }
function inc9(target: List<Integer>, y: Integer): Integer { target[0] = target[0] + 1; return target[0] + y }
function inc10(target: List<Integer>): Integer { let old = target[0]; target[0] = old + 1; return old }
let target = [0]
inc1(1073741823, target); print(target[0])
target[0] = 1073741813
let i = 0
while i < 20 { inc2(target); i = i + 1 }
print(target[0])
target[0] = 1073741813
i = 0
while i < 20 { inc3(target, 0); i = i + 1 }
print(target[0])
i = 0
while i < 5 { print(inc4(2, 1)); i = i + 1 }
inc4(2, 1)
i = 0
while i < 5 { print(inc5(2, 1)); i = i + 1 }
print(inc5(2, 1))
i = 0
while i < 6 { target[0] = 42; print(inc6(target, 1)); print(target[0]); i = i + 1 }
i = 0
while i < 6 { target[0] = 42; print(inc7(target, 1)); print(target[0]); i = i + 1 }
i = 0
while i < 6 { target[0] = 42; print(inc8(target, 1)); print(target[0]); i = i + 1 }
i = 0
while i < 6 { target[0] = 42; print(inc9(target, 1)); print(target[0]); i = i + 1 }
i = 0
while i < 6 { target[0] = 42; print(inc10(target)); print(target[0]); i = i + 1 }
''', '1073741824\n1073741833\n1073741833\n' + '3\n'*5 + '4\n'*6 + '43\n43\n'*6 + '44\n43\n'*6 + '43\n43\n'*6 + '44\n43\n'*6 + '42\n43\n'*6)

    def test_missing_element_increment_fails_after_six_valid_updates(self):
        self.executes('''function increment(a: List<Integer>, index: Integer) { a[index] = a[index] + 1 }
let a = [0]
let i = 0
while i < 5 { increment(a, 0); i = i + 1 }
increment(a, 0)
print(a[0])
increment(a, 1)
print("unreachable")
''', '6\n', 1, 'Minyar stopped: List position 1 is outside its length of 1.\n')

    def test_unswitched_nested_loops_preserve_sequential_global_state(self):
        source = ['record Value { field: Integer }']
        updates = [
            'if state[2] == 42 { state[3] = 34 }',
            'state[3] = b.field; if state[2] == 42 { state[3] = 34 }; state[4] = a.field',
            'state[3] = b.field; if state[2] == 42 { state[3] = 34 }; state[4] = a.field; if state[1] == 22 { state[3] = 55 }; state[0] = c.field',
            'state[3] = state[3] + b.field; if state[2] == 42 { state[3] = 34 }; if state[1] == 22 { state[3] = 55 }; state[0] = c.field; if state[4] == 75 { state[3] = 66 }; state[3] = state[3] + a.field + b.field + c.field',
        ]
        for n, update in enumerate(updates):
            source.append(f'''function run{n}(values: List<Integer>, state: List<Integer>, a: Value, b: Value, c: Value): Integer {{
let scratch = [0, 0, 0, 0, 0, 0, 0, 0]
let result = 0
let i = 0
while i < values.length {{
let j = 5
while j < i {{ {update}; scratch[j] = scratch[j] + values[j]; result = result + values[j]; j = j + 1 }}
i = i + 1
}}
return result
}}
''')
        expected = []
        states = [(1, 2, 3, 4, 5), (1, 2, 3, 6, 6), (6, 2, 3, 6, 6), (6, 2, 3, 78, 6)]
        for mode in range(2):
            source += [f'let values{mode} = [1, 2, 3, 4, 5, 6, 7, 8]', f'let state{mode} = [1, 2, 3, 4, 5]']
            for n, state in enumerate(states):
                source.append(f'print(run{n}(values{mode}, state{mode}, Value {{ field: 6 }}, Value {{ field: 6 }}, Value {{ field: 6 }}))')
                source += [f'print(state{mode}[{i}])' for i in range(5)]
                expected += [19, *state]
            source += [f'print(values{mode}[{i}])' for i in range(8)]
            expected += list(range(1, 9))
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_conditional_negation_selects_all_fifteen_indices(self):
        self.executes('''function run(a: List<Integer>) {
let i = 5
while i > 0 {
let j = 0
while j <= i - 1 {
let step = 2 * j - i
let value = 0
if step < 0 { value = a[-step] } else { value = a[step] }
print(value)
j = j + 1
}
i = i - 1
}
}
let zeros: List<Integer> = []
let marked: List<Integer> = []
let i = 0
while i < 888 { zeros.add(0); marked.add(i + 100); i = i + 1 }
run(zeros); run(marked)
''', '0\n'*15 + ''.join(f'{100+abs(2*j-i)}\n' for i in range(5, 0, -1) for j in range(i)))

    def test_split_loop_forward_reverse_and_early_exit_index_traces(self):
        source = ['function blank(size: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i < size { a.add(0); i = i + 1 }; return a }']
        expected = []
        for variant in range(1, 5):
            reverse = variant in (2, 4)
            initial = 'start - 1' if reverse else 'start'
            condition = 'i >= stop' if reverse else 'i < stop'
            update = 'i - 1' if reverse else 'i + 1'
            index = 'stop - i - 1' if variant == 3 else 'from - i - 1' if variant == 4 else 'i'
            source.append(f'''function helper{variant}(start: Integer, stop: Integer, from: Integer, dst: List<Integer>, src: List<Integer>, exit: Integer): Boolean {{
let i = {initial}
while {condition} {{
let index = {index}
dst[index] = src[index]
print(index)
if i == exit {{ return true }}
i = {update}
}}
return false
}}
function wrapper{variant}(src: List<Integer>, exit: Integer): Boolean {{
let dst = blank({10 if variant < 3 else 5})
let result = helper{variant}({5 if reverse else 0}, {0 if reverse else 5}, 5, dst, src, exit)
let i = 0
while i < dst.length {{ if dst[i] != 0 {{ fail("copy contents") }}; i = i + 1 }}
return result
}}
''')
            source += [f'let large{variant} = blank(1000)', f'let small{variant} = blank(10)',
                       f'print(helper{variant}({1000 if reverse else 0}, {0 if reverse else 1000}, 1000, large{variant}, large{variant}, {1 if reverse else 998}))',
                       f'print(wrapper{variant}(small{variant}, 999))', f'print(wrapper{variant}(small{variant}, {1 if reverse else 4}))']
            helper_indices = list(range(999)) if variant in (1, 4) else list(range(999, 0, -1))
            normal = list(range(5)) if variant in (1, 4) else list(range(4, -1, -1))
            early = normal[:-1] if reverse else normal
            expected += list(map(str, helper_indices)) + ['true'] + list(map(str, normal)) + ['false'] + list(map(str, early)) + ['true']
        self.executes('\n'.join(source), '\n'.join(expected) + '\n')

    def test_unused_literal_text_concat_preserves_typed_parameter_returns(self):
        self.executes('''function integer(a: Integer, b: Integer): Integer { let unused = "a" + "b"; return a }
function boolean(a: Boolean, b: Integer): Boolean { let unused = "a" + "b"; return a }
function text(a: Text, b: Integer): Text { let unused = "a" + "b"; return a }
let mode = 0
while mode < 5 { print(integer(33, 32)); print(integer(31, 30)); print(integer(0, 30)); print(boolean(true, 0)); print(text("true", 0)); mode = mode + 1 }
''', '33\n31\n0\ntrue\ntrue\n' * 5)

    def test_typed_singleton_and_triple_constructors_keep_all_elements(self):
        source = []
        expected = []
        for mode in range(2):
            source += [f'function booleans{mode}(value: Boolean): List<Boolean> {{ return [!!value] }}',
                       f'function texts{mode}(value: Text): List<Text> {{ return ["" + value] }}',
                       f'function triples{mode}(x: Integer, y: Integer, z: Integer): List<Integer> {{ return [x, y, z] }}']
            for index, value in enumerate(('true', 'false', 'true', 'false')):
                name = f'b{mode}n{index}'
                source += [f'let {name} = booleans{mode}({value})', f'print({name}.length); print({name}[0])']
                expected += ['1', value]
            for index, value in enumerate(('a', 'b', 'a', 'b')):
                name = f't{mode}n{index}'
                source += [f'let {name} = texts{mode}("{value}")', f'print({name}.length); print({name}[0])']
                expected += ['1', value]
            for index in range(3):
                name = f'v{mode}n{index}'
                source += [f'let {name} = triples{mode}(1, 2, 3)', f'print({name}.length); print({name}[0]); print({name}[1]); print({name}[2])']
                expected += ['3', '1', '2', '3']
        self.executes('\n'.join(source), '\n'.join(expected) + '\n')

    def test_compound_assignment_returns_updated_shared_storage(self):
        self.executes('''function assign(target: List<Integer>): Integer { target[0] = target[0] + 1; return target[0] }
let target = [0]
let i = 0
while i < 5 { target[0] = 42; print(assign(target)); print(target[0]); i = i + 1 }
target[0] = 42
print(assign(target)); print(target[0])
''', '43\n43\n' * 6)

    def test_positive_width_examples_divide_and_remainder_by_six(self):
        self.executes('''let byte = 7
let short = 14
let integer = 21
let long = 28
let wide = 35
print(byte / 6); print(byte % 6)
print(short / 6); print(short % 6)
print(integer / 6); print(integer % 6)
print(long / 6); print(long % 6)
print(wide / 6); print(wide % 6)
''', ''.join(f'{i}\n{i}\n' for i in range(1, 6)))

    def test_absolute_computed_index_clears_only_descending_prefix(self):
        self.executes('''function absolute(value: Integer): Integer { if value < 0 { return -value }; return value }
function check(a: List<Integer>) {
let i = 0
while i < 5 { print(a[i]); i = i + 1 }
while i < 10 { print(a[i]); i = i + 1 }
}
let a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
let i = -5
while i < 0 { a[absolute(i - 10) - 11] = 0; i = i + 1 }
check(a)
''', '0\n'*5 + ''.join(f'{i}\n' for i in range(6, 11)))

    def test_fresh_loop_record_cells_do_not_reuse_previous_mutation(self):
        self.executes('''record Item { value: List<Integer>; text: Text }
let i = 0
while i < 4 {
let item = Item { value: [3]; text: "hey there" }
print(item.value[0]); print(item.text)
let cell = item.value
cell[0] = 4
print(item.value[0]); print(item.text)
i = i + 1
}
''', '3\nhey there\n4\nhey there\n' * 4)

    def test_four_maximum_branches_and_aliased_comparison_operands(self):
        source = ['function lt(x: Integer, y: Integer): Integer { if x < y { return y }; return x }',
                  'function le(x: Integer, y: Integer): Integer { if x <= y { return y }; return x }',
                  'function ge(x: Integer, y: Integer): Integer { if x >= y { return x }; return y }',
                  'function gt(x: Integer, y: Integer): Integer { if x > y { return x }; return y }',
                  'function same(x: Integer): Integer { if x == x { return 42 }; return -1 }',
                  'function alias(x: Integer): Integer { let y = x; if x == y { return 42 }; return -1 }']
        expected = []
        for x, y in [(0, 1), (1, 0), (3, 4), (4, 3), (-1, 0), (0, -1), (-2, -3), (-3, -2)]:
            source += [f'print({helper}({x}, {y}))' for helper in ('lt', 'le', 'ge', 'gt')]
            expected += [max(x, y)] * 4
        source += ['print(same(0)); print(alias(0))']; expected += [42, 42]
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_record_allocation_before_after_and_across_long_loop(self):
        source = ['record Value { a: Integer }', 'function make(): Value { return Value { a: 23 } }']
        for n in range(1, 4):
            before = 'print(make().a)' if n == 1 else 'let object = make()' if n == 3 else ''
            after = 'print(make().a)' if n == 2 else 'print(object.a)' if n == 3 else ''
            source.append(f'''function run{n}(length: Integer): Integer {{
{before}
let result = 0
let i = 0
while i < length {{ result = (result + i) % 99; i = i + 1 }}
{after}
return result
}}
''')
        expected = []
        for n in range(1, 4):
            for length in (10, 10, 50000):
                source.append(f'print(run{n}({length}))')
                expected += [23, (length*(length-1)//2) % 99]
        self.executes('\n'.join(source), ''.join(f'{n}\n' for n in expected))

    def test_nested_record_temporaries_and_duplicate_aliases_remain_live(self):
        self.executes('''record Leaf { y: Integer }
record Outer { x: Leaf }
record Empty { }
record Dummy { empty: Empty }
record Number { d: Integer }
function leaf(): Leaf { return Leaf { y: 3 } }
function wrap(unused: Dummy): Outer { let result = Outer { x: leaf() }; return result }
function inlineCase() { let left = Dummy { empty: Empty { } }; let right = wrap(left); print(right.x.y) }
function two() { let left = Outer { x: Leaf { y: 111 } }; let right = Outer { x: Leaf { y: 111 } }; print(left.x.y); print(right.x.y) }
function duplicate() { let left = Outer { x: Leaf { y: 111 } }; let dummy = Number { d: 0 }; let alias = left.x; print(left.x.y); print(alias.y); print(dummy.d) }
let i = 0
while i < 4 { inlineCase(); i = i + 1 }
i = 0
while i < 4 { two(); i = i + 1 }
i = 0
while i < 4 { duplicate(); i = i + 1 }
''', '3\n'*4 + '111\n111\n'*4 + '111\n111\n0\n'*4)

    def test_short_circuit_skips_literal_and_parameter_overflow(self):
        self.executes('''function either(flag: Boolean, maximum: Integer): Boolean { return flag || (1 + maximum < 0) }
function both(flag: Boolean, maximum: Integer): Boolean { return flag && (1 + maximum < 0) }
print(true || (1 / 0 != 0))
print(true || (1 + 9223372036854775807 < 0))
print(false && (1 + 9223372036854775807 < 0))
print(either(true, 9223372036854775807))
print(both(false, 9223372036854775807))
''', 'true\ntrue\nfalse\ntrue\nfalse\n')

    def test_constant_overflow_contexts_and_evaluated_boolean_rhs_trap(self):
        error = 'Minyar stopped: this Integer calculation is outside the supported range.\n'
        zero = 'Minyar stopped: an Integer cannot be divided by zero.\n'
        definitions = [
            'function local() { let value = 9223372036854775807 + 1; print(value) }',
            'function returned(): Integer { return 9223372036854775807 + 1 }',
            'function subtract(): Integer { return 9223372036854775807 + 1 - 9223372036854775807 }',
            'function zeroProduct(zero: Integer): Integer { return 0 * (1 / zero) }',
            'function either(flag: Boolean, maximum: Integer): Boolean { return flag || (1 + maximum < 0) }',
            'function both(flag: Boolean, maximum: Integer): Boolean { return flag && (1 + maximum < 0) }',
        ]
        cases = [
            ('leftOne', 'print(1 + 9223372036854775807)', '', error),
            ('global', 'let value = 9223372036854775807 + 1; print(value)', '', error),
            ('local', 'local()', '', error),
            ('return', 'print(returned())', '', error),
            ('subtract', 'print(subtract())', '', error),
            ('zeroOverflow', 'print(0 * (9223372036854775807 + 1))', '', error),
            ('zeroDivideLiteral', 'print(0 * (1 / 0))', '', zero),
            ('zeroDivideParameter', 'print(zeroProduct(0))', '', zero),
            ('eitherLiteral', 'print(false || (1 + 9223372036854775807 < 0))', '', error),
            ('bothLiteral', 'print(true && (1 + 9223372036854775807 < 0))', '', error),
            ('eitherParameter', 'print(either(false, 9223372036854775807))', '', error),
            ('bothParameter', 'print(both(true, 9223372036854775807))', '', error),
        ]
        self._execute_fatal_branches(definitions, cases)

    def test_latin1_literal_bytes_are_rejected_as_invalid_utf8_source(self):
        from regressions import COMPILER, COMPILE_TIMEOUT
        for index, prefix in enumerate((b'', b'foo ')):
            with self.subTest(prefix=prefix):
                path = self.directory / f'latin1-{index}.min'
                llvm = path.with_suffix('.ll')
                path.write_bytes(b'print("' + prefix + bytes.fromhex('c0 e9 ee f5 fc') + b'")\n')
                result = self.evidence.run([COMPILER, path, llvm], timeout=COMPILE_TIMEOUT,
                                           phase='compile-invalid-latin1-literal')
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (1, b'', b'Minyar stopped: Text contained invalid UTF-8.\n'))
                self.assertFalse(llvm.exists())

    def test_load_before_full_fill_preserves_antidependence(self):
        definitions = []
        source, expected = [], []
        for kind, typ, zero, value in [('number', 'Integer', '0', '42'), ('boolean', 'Boolean', 'false', 'true')]:
            combine = 'total + loaded' if kind == 'number' else 'total || loaded'
            definitions.append(f'''function {kind}(pos: Integer, samePos: Integer): {typ} {{
let array: List<{typ}> = [{', '.join([zero]*10)}]
array[pos] = {value}
let total = {zero}
let i = 0
while i < 4 {{
let loaded = array[samePos]
print(loaded)
total = {combine}
let t = 0
while t < array.length {{ array[t] = {zero}; t = t + 1 }}
i = i + 1
}}
let t = 0
while t < array.length {{ print(array[t]); t = t + 1 }}
return total
}}''')
            for pos in (0, 9):
                source.append(f'print({kind}({pos}, {pos}))')
                expected += [value] + [zero]*13 + [value]
        self.executes('\n'.join(definitions + source), '\n'.join(expected)+'\n')

    def test_triangular_signed_index_branches_preserve_each_load(self):
        source = '''function blank(n: Integer): List<Integer> {
let result: List<Integer> = []; let i = 0
while i < n { result.add(0); i = i + 1 }; return result
}
function trace(input: List<Integer>, marked: Boolean) {
let local = blank(777)
if marked { local[0] = 11; local[1] = 22; local[2] = 33; local[3] = 44 }
let i = 4
while i > 0 {
let j = 0
while j <= i - 1 {
let step = 2 * j - i + 1
let adjacent = 0
if step < 0 { adjacent = local[0-step] + input[i-1] } else { adjacent = local[step] + input[i-1] }
print(step); print(adjacent)
j = j + 1
}
i = i - 1
}
}
let input = blank(999)
trace(input, false)
input[0] = 100; input[1] = 200; input[2] = 300; input[3] = 400
trace(input, true)
'''
        expected = []
        for marked in (False, True):
            for i in range(4, 0, -1):
                for j in range(i):
                    step = 2*j-i+1
                    expected += [step, 11*(abs(step)+1)+100*i if marked else 0]
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_early_return_updates_persistent_checksum_once_per_call(self):
        source = '''function preincrement(cell: List<Integer>): Integer {
cell[0] = cell[0] + 1; return cell[0]
}
function update(input: Integer, checksum: List<Integer>) {
let first: List<Integer> = []
let second: List<Integer> = []
let counter = [-36665]
let state = input
while preincrement(counter) < 132 {
if state != 0 { checksum[0] = checksum[0] + counter[0]; return }
let inner = [1]
while preincrement(inner) < 12 { state = state + inner[0] }
}
checksum[0] = checksum[0] + counter[0]
}
let checksum = [0]
let round = 0
while round < 10 { update(3, checksum); print(checksum[0]); round = round + 1 }
update(0, checksum); print(checksum[0])
'''
        expected = [-36664*n for n in range(1, 11)] + [-366640-36663]
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_nested_negation_keeps_inner_sum_and_repeated_calls(self):
        source = '''function negate(x: Integer) {
print(-0); print(-x); print(- -x); print(-(-x + -x))
}
negate(15); negate(15); negate(15); negate(15)
'''
        self.executes(source, '0\n-15\n15\n30\n'*4)

    def test_bigint_subtract_and_multiply_safe_call_sequences(self):
        source = ['function subtract(a: Integer, b: Integer): Integer { return a - b }',
                  'function multiply(a: Integer, b: Integer): Integer { return a * b }']
        expected = []
        for symbol, name, wide in [('-', 'subtract', (-(1 << 62), 1 << 62)),
                                   ('*', 'multiply', (-(1 << 32), 1 << 31))]:
            pairs = [(0, 1), (2, 9), (14, 5), wide, (0, 1), (2, 9), (14, 5)]
            for a, b in pairs:
                result = a-b if symbol == '-' else a*b
                self.assertTrue(-(1 << 63) <= result < (1 << 63))
                source += [f'print(({a}) {symbol} ({b}))', f'print({name}({a}, {b}))']
                expected += [result, result]
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))

    def test_bigint_subtract_multiply_overflow_is_fatal_at_exact_operands(self):
        definitions = ['function subtract(a: Integer, b: Integer): Integer { return a - b }',
                       'function multiply(a: Integer, b: Integer): Integer { return a * b }']
        cases = []
        error = 'Minyar stopped: this Integer calculation is outside the supported range.\n'
        for symbol, name, a, b in [('-', 'subtract', -(1 << 62)-1, 1 << 62),
                                    ('*', 'multiply', -77158673929, 119537721)]:
            self.assertEqual(a-b if symbol == '-' else a*b, -(1 << 63)-1)
            for mode, expression in [('literal', f'({a}) {symbol} ({b})'), ('parameter', f'{name}({a}, {b})')]:
                cases.append((name+mode, f'print("before"); print({expression}); print("after")', 'before\n', error))
        self._execute_fatal_branches(definitions, cases)

    def test_distinct_texts_preserve_computed_zero_offsets(self):
        body = []
        for i in range(8):
            body.append(f'let text{i} = "a111{i+1}"; result.add(text{i}[(values[{i}] - {65536*(i+1)}) * 2])')
        source = 'function read(values: List<Integer>): List<Character> { let result: List<Character> = []; ' + '; '.join(body) + '; return result }\n'
        source += '''let values: List<Integer> = []; let i = 0
while i < 8 { values.add(65536 * (i + 1)); i = i + 1 }
let result = read(values)
i = 0
while i < result.length { print(result[i]); i = i + 1 }
'''
        self.executes(source, 'a\n'*8)

    def test_sign_dependent_adjustment_keeps_zero_unchanged(self):
        source = ['''function adjust(i: Integer, enabled: Boolean): Integer {
let k = i + 1
if enabled { if k > 0 { k = k + 1 } else { if k < 0 { k = k - 1 } } }
return k
}''']
        expected = []
        for enabled in (False, True):
            for i in (-2, -1, 0, 1):
                k = i + 1
                expected.append(k + (1 if k > 0 else -1 if k < 0 else 0) if enabled else k)
                source.append(f'print(adjust({i}, {str(enabled).lower()}))')
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))

    def test_wide_argument_between_variable_fixed_prefix_and_trailer(self):
        source, expected = [], []
        for count in range(1, 9):
            names = [f'arg{i}' for i in range(1, count+1)] + ['wide', 'after']
            values = list(range(1, count+1)) + [81985529216486895, 85]
            source.append(f'function check{count}({", ".join(name+": Integer" for name in names)}) {{ ' + '; '.join('print('+name+')' for name in names) + ' }')
            source.append(f'check{count}({", ".join(map(str, values))})')
            expected += values
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))

    def test_checked_addition_precedes_wrapping_overflow_detector(self):
        definition = '''function checked(a: Integer, b: Integer, error: List<Integer>): Integer {
error[0] = 0
let result = a + b
if a >= 0 { if b < 0 || result >= 0 { return result } } else { if b > 0 || result < 0 { return result } }
error[0] = 1
return 0
}'''
        source = [definition, 'let error = [9]']
        expected = []
        for a, b in [(0, 0), (1, -1), (-1, 1), ((1 << 63)-1, -(1 << 63))]:
            source += [f'print(checked({a}, {b}, error))', 'print(error[0])']
            expected += [a+b, 0]
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))
        cases = []
        for i, (a, b) in enumerate([(-(1 << 63), -(1 << 63)), (-(1 << 63), -1), ((1 << 63)-1, (1 << 63)-1), ((1 << 63)-1, 1)]):
            cases.append((f'overflow{i}', f'let error = [9]; print("before"); print(checked({a}, {b}, error)); print(error[0])', 'before\n', 'Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self._execute_fatal_branches([definition], cases)

    def test_operator_whitespace_distinguishes_cr_lf_and_unicode_separators(self):
        from regressions import COMPILER, COMPILE_TIMEOUT
        # Exact nine separators and their source-order concatenation from Test262.
        separators = ['\t', '\v', '\f', ' ', '\u00a0', '\n', '\r', '\u2028', '\u2029']
        separators.append(''.join(separators))
        operators = [('1', '+', '1', '2'), ('1', '-', '1', '0'), ('1', '/', '1', '1'),
                     ('1', '*', '1', '1'), ('1', '%', '1', '0'),
                     ('true', '&&', 'true', 'true'), ('false', '||', 'true', 'true'),
                     ('', '-', '1', '-1')]
        accepted, expected, rejected = [], [], []
        for left, operator, right, answer in operators:
            for n, separator in enumerate(separators, 1):
                expression = (left+separator if left else '') + operator + separator + right
                source = 'print('+expression+')\n'
                valid = n in (1, 4, 7) or (not left and n == 6)
                if valid:
                    accepted.append(source); expected.append(answer)
                else:
                    rejected.append((operator, n, source))
            # A newline AFTER a binary operator continues; CRLF BEFORE it does not.
            if left:
                accepted.append(f'print({left} {operator}\n{right})\n'); expected.append(answer)
                rejected.append((operator, 'crlf', f'print({left}\r\n{operator}\r\n{right})\n'))
        self.assertEqual(len(accepted), 32)
        self.assertEqual(len(rejected), 62)
        self.executes(''.join(accepted), '\n'.join(expected)+'\n')
        for index, (operator, case, source) in enumerate(rejected):
            with self.subTest(operator=operator, case=case):
                path = self.directory / f'whitespace-{index}.min'
                llvm = self.directory / f'whitespace-{index}.ll'
                path.write_bytes(source.encode('utf-8'))
                result = self.evidence.run([COMPILER, path, llvm], timeout=COMPILE_TIMEOUT,
                                           phase='compile-rejected-whitespace')
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b'')
                self.assertTrue(result.stderr.startswith(b'Minyar stopped: '), result.stderr)
                self.assertNotIn(b'AddressSanitizer', result.stderr)
                self.assertNotIn(b'runtime error:', result.stderr)
                self.assertFalse(llvm.exists())

    def test_copied_list_predicates_preserve_dependent_index_loads(self):
        source = ['''function blank(n: Integer): List<Integer> {
let result: List<Integer> = []; let i = 0
while i < n { result.add(0); i = i + 1 }; return result
}''']
        calls, expected = [], []
        for kind in range(1, 6):
            start = ['0', 'i', 'i + 1', 'i + 1 + state[2]', 'i + 1 + state[2]'][kind-1]
            load = 'state[0] = module[local[19]];' if kind > 1 else ''
            extra = 'state[1] = state[1] + small[3];' if kind == 5 else ''
            source.append(f'''function shape{kind}(flag: Boolean, module: List<Integer>, small: List<Integer>, state: List<Integer>, limit: Integer) {{
let i = 0
while i < {1 if kind == 1 else 'limit'} {{
let local = blank(20)
let copy = 0
while copy < 18 {{ local[state[1] + copy] = module[state[0] + copy]; copy = copy + 1 }}
print(copy)
if flag {{ print(local[19]); return }}
let j = {start}
while j < limit {{ {load} local[19] = local[19] + 1; {extra} j = j + 1 }}
print(local[19])
i = i + 1
}}
}}''')
            for flag in (True, False):
                calls += [f'shape{kind}({str(flag).lower()}, module, small, state, 5)',
                          'print(state[0]); print(state[1]); print(state[2])']
                if flag: expected += [18, 0]
                else:
                    for i in range(1 if kind == 1 else 5):
                        expected += [18, 5 if kind == 1 else 5-i if kind == 2 else 4-i]
                expected += [0, 0, 0]
        source += ['let module = blank(25); let small = blank(5); let state = [0, 0, 0]'] + calls
        source += ['let i = 0; while i < module.length { print(module[i]); i = i + 1 }',
                   'i = 0; while i < small.length { print(small[i]); i = i + 1 }']
        expected += [0]*30
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))

    def test_repeated_nested_stores_keep_each_final_cell_value(self):
        source = '''function fill(values: List<Integer>) {
let i = 0
while i < 10 { let j = 0; while j <= 10 { values[i] = j; j = j + 1 }; i = i + 1 }
}
let values = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
let round = 0
while round < 1000 { fill(values); round = round + 1 }
let i = 0
while i < values.length { print(values[i]); i = i + 1 }
'''
        self.executes(source, '10\n'*10)

    def test_predecrement_loop_traps_before_zero_remainder_store(self):
        definitions = ['''function oldCheck(cell: List<Integer>): Boolean {
cell[0] = cell[0] - 1; return cell[0] > 0
}
function run() {
let values: List<Integer> = []; let i = 0
while i < 400 { values.add(0); i = i + 1 }
values[1] = 2
let counter = [2]
while oldCheck(counter) {
let divisor = values[counter[0]-1] / 56
print(values[1])
values[1] = -139 % divisor
print("after")
}
}''']
        cases = [(f'call{i}', 'run()', '2\n', 'Minyar stopped: an Integer cannot be divided by zero.\n') for i in range(10)]
        self._execute_fatal_branches(definitions, cases)

    def test_high_word_carries_survive_boolean_merges_records_and_indexing(self):
        source = '''record Value { x: Integer }
function positive(flag: Boolean): Integer { let i = 0; if flag { i = 4294967295 }; return i + 1 }
function signed(flag: Boolean): Integer { let i = -1; if flag { i = 4294967295 }; return i + 1 }
function recordArithmetic(value: Value): Integer { return Value { x: (value.x + 11123456789) + -11123456788 }.x }
function index(values: List<Integer>, i: Integer): Integer { let position = i - 4294967295; return values[position] }
'''
        expected = []
        for name, low in [('positive', 1), ('signed', 0)]:
            for flag in (False, False, True, True, False, True):
                source += f'print({name}({str(flag).lower()}))\n'
                expected.append(4294967296 if flag else low)
        for value in (0, 1, 1):
            source += f'print(recordArithmetic(Value {{ x: {value} }}))\n'; expected.append(value+1)
        for value in (1, 2, 3):
            source += f'print(index([{value}], 4294967295))\n'; expected.append(value)
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_explicit_count_lowering_preserves_value_and_loop_condition_order(self):
        source = '''record Cell { x: List<Integer> }
function pre(cell: List<Integer>): Integer { cell[0] = cell[0] + 1; return cell[0] }
function post(cell: List<Integer>): Integer { let old = cell[0]; cell[0] = old + 1; return old }
function f(x: Integer): Integer { let value = x; value = value + 1; return value }
function g(x: Integer): Integer { let value = x; value = value + 1; return value }
function h(x: Integer): Integer { let value = x; let old = value; value = value + 1; return old }
function k(x: Integer): Integer { let value = x; value = value + 1; let updated = value; return updated }
function postDown(cell: List<Integer>): Boolean { let old = cell[0]; cell[0] = old - 1; return old != 0 }
function preDown(cell: List<Integer>): Boolean { cell[0] = cell[0] - 1; return cell[0] != 0 }
let a = [42]
let object = Cell { x: [42] }
let b = object.x
print(pre(a)); print(a[0]); print(post(a)); print(a[0])
print(pre(b)); print(b[0]); print(post(b)); print(b[0])
print(f(42)); print(g(42)); print(h(42)); print(k(42))
let count = [10]; let iterations = 0
while postDown(count) { iterations = iterations + 1 }
print(iterations); print(count[0])
count[0] = 10; iterations = 0
while preDown(count) { iterations = iterations + 1 }
print(iterations); print(count[0])
'''
        expected = [43,43,43,44]*2 + [43,43,42,43,10,-1,9,0]
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_text_index_helper_modes_keep_in_bounds_reads(self):
        self.executes('''function index(i: Integer): Character { let text = "12345"; return text[i] }
function both(text: Text, i: Integer): Character { return text[i] }
print(index(0)); print(index(1)); print(both("12345", 0)); print(both("12345", 1))
''', '1\n2\n1\n2\n')

    def test_text_index_helper_modes_trap_at_exact_length(self):
        definitions = ['function constant(): Character { let text = "12345"; return text[5] }',
                       'function index(i: Integer): Character { let text = "12345"; return text[i] }',
                       'function textParameter(text: Text): Character { return text[5] }',
                       'function both(text: Text, i: Integer): Character { return text[i] }']
        cases = []
        for mode, expression, repetitions in [('constant', 'constant()', 4), ('index', 'index(5)', 2),
                                              ('text', 'textParameter("12345")', 4), ('both', 'both("12345", 5)', 2)]:
            for i in range(repetitions):
                cases.append((mode+str(i), f'print("before"); print({expression}); print("after")', 'before\n', 'Minyar stopped: a Text position was outside the Text.\n'))
        self._execute_fatal_branches(definitions, cases)

    def test_six_point_arguments_keep_signed_fields_after_empty_call(self):
        points = [(0,1),(-1,0),(1,-1),(-1,1),(0,-1),(1,0)]
        source = ['record Point { x: Integer, y: Integer }', 'function empty() {}',
                  'function check('+', '.join(f'p{i}: Point' for i in range(6))+') { '+
                  '; '.join(f'print(p{i}.x); print(p{i}.y)' for i in range(6))+' }', 'empty()']
        source += [f'let p{i} = Point {{ x: {x}, y: {y} }}' for i,(x,y) in enumerate(points)]
        source += ['check('+', '.join(f'p{i}' for i in range(6))+')']
        self.executes('\n'.join(source), ''.join(f'{value}\n' for point in points for value in point))

    def test_subrange_record_copy_overwrites_all_large_initial_fields(self):
        self.executes('''record Input { b: Integer, d: List<Integer> }
record Triple { r: List<Integer> }
function observe(value: Triple, ignored: Integer) { print(value.r[0]); print(value.r[1]); print(value.r[2]); print(ignored) }
function foo(input: Input) {
let copied = Triple { r: [input.d[1], input.d[2], input.d[3]] }
let replacement = copied
observe(replacement, input.b)
}
function baz(input: Input) {
let replacement = Triple { r: [4886718345, 68414056839, 46118400291] }
let copied = Triple { r: [input.d[1], input.d[2], input.d[3]] }
replacement = copied
observe(replacement, input.b)
}
let input = Input { b: 0, d: [0, 21, 22, 23] }
baz(input); foo(input)
''', '21\n22\n23\n0\n'*2)

    def test_nested_record_literal_retains_each_distinct_leaf(self):
        self.executes('''record A { i: Integer, j: Integer }
record B { a: A, b: A }
record C { c: B, d: A }
let value = C { c: B { a: A { i: 1, j: 2 }, b: A { i: 3, j: 4 } }, d: A { i: 5, j: 6 } }
print(value.c.a.i); print(value.c.a.j); print(value.c.b.i); print(value.c.b.j); print(value.d.i); print(value.d.j)
''', '1\n2\n3\n4\n5\n6\n')

    def test_parallel_descriptor_and_buffer_stores_preserve_outer_alias(self):
        self.executes('''record Descriptor { next: List<Integer> }
record Ring { descriptors: List<Descriptor>, buffer: List<Integer> }
function initialize(ring: Ring) {
let descriptors = ring.descriptors
let buffer = ring.buffer
let i = 0
while i < 5 {
let descriptor = descriptors[i]
let next = descriptor.next
next[0] = 10 + (i+1) * 2
buffer[i] = 0
i = i + 1
}
let last = descriptors[i-1]
let next = last.next
next[0] = 10
}
let descriptors: List<Descriptor> = []
let i = 0
while i < 5 { descriptors.add(Descriptor { next: [0] }); i = i + 1 }
let ring = Ring { descriptors: descriptors, buffer: [5,5,5,5,5] }
initialize(ring)
i = 0
while i < 5 { let descriptor = descriptors[i]; print(descriptor.next[0]); print(ring.buffer[i]); i = i + 1 }
''', '12\n0\n14\n0\n16\n0\n18\n0\n10\n0\n')

    def test_multiplicative_folding_keeps_five_groupings(self):
        expressions = ['((x*2 + 4) - 8) / 2', '((x*2 - 4) + 2) / 2',
                       '(((x + 2) * 2) - 8 - 4) / 2', '(((x + 2) * 2) - (8 + 4)) / 2',
                       '((x*4 + 2) - 4) / 2']
        source = ['function calculate(x: Integer) { '+'; '.join(f'print({expression})' for expression in expressions)+' }', 'calculate(924)']
        source += [f'print({expression.replace("x", "924")})' for expression in expressions]
        self.executes('\n'.join(source), '922\n923\n920\n920\n1847\n'*2)

    def test_early_return_sum_helpers_preserve_shared_sequential_updates(self):
        source = '''function blank(): List<Integer> { let a: List<Integer> = []; let i = 0; while i < 400 { a.add(0); i = i + 1 }; return a }
function sumPlain(a: List<Integer>): Integer { let sum = 0; let i = 0; while i < a.length { sum = sum + a[i]; i = i + 1 }; return sum }
function first(): Integer {
let sum = 0; let a = blank(); let warm = 0
while warm < 70 { warm = warm + 1 }
let i = 0
while i < 36 { let j = 0; while j < 3 { a[0] = 7; sum = sum + a[0]; if sum != 0 { return sum + sumPlain(a) }; j = j + 1 }; i = i + 1 }
return 0
}
function sumWhole(a: List<Integer>, flag: Boolean): Integer {
let sum = 0; let i = 0
while i < a.length { let j = 0; while j < 34 { j = j + 1 }; if flag { return 3 }; sum = sum + a[i]; i = i + 1 }; return sum
}
function sumLimit(a: List<Integer>, limit: Integer, flag: Boolean): Integer {
let sum = 0; let i = 0
while i < limit { let j = 0; while j < 34 { j = j + 1 }; if flag { return 3 }; sum = sum + a[i]; i = i + 1 }; return sum
}
function pre(cell: List<Integer>): Integer { cell[0] = cell[0] + 1; return cell[0] }
'''
        for n, called in [(2, 'sumWhole(a, flag)'), (3, 'sumLimit(a, x, flag)')]:
            source += f'''function next{n}(a: List<Integer>, flag: Boolean): Integer {{
let x = 5; let i = 1
while i < 37 {{
let aa = 0
while aa < 2 {{ let b = 0; while b < 300 {{ b = b + 1 }}; aa = aa + 1 }}
let j = [1]; x = x * 12
while pre(j) < 5 {{ a[0] = a[0] + 2; if a[0] > 0 {{ return {called} }} }}
i = i + 1
}}
return 3
}}
'''
        source += '''let i = 1
while i < 1000 { print(first()); i = i + 1 }
let a = blank()
i = 1
while i < 10000 { print(next2(a, false)); i = i + 1 }
i = 1
while i < 10000 { print(next3(a, false)); i = i + 1 }
i = 0
while i < a.length { print(a[i]); i = i + 1 }
'''
        expected = [14]*999 + list(range(2,20000,2)) + list(range(20000,39998,2)) + [39996] + [0]*399
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_posttested_nested_loop_keeps_single_late_outer_store(self):
        source = '''function pre(cell: List<Integer>): Integer { cell[0] = cell[0] + 1; return cell[0] }
function run(values: List<Integer>) {
let i = 56; let inner = 22257; let active = true; let visits = 0
while active {
let repeat = true
while repeat {
let unused = [1]
while pre(unused) < 2 {}
let longIndex = i
while longIndex < 2 { values[0] = values[0] + 5; longIndex = longIndex + 1 }
visits = visits + 1
inner = inner - 2; repeat = inner > 0
}
let empty = 8
while empty < 194 { empty = empty + 1 }
i = i - 1; active = i > 0
}
print(i); print(inner); print(visits); print(values[0])
}
let values: List<Integer> = []; let i = 0
while i < 400 { values.add(0); i = i + 1 }
i = 0
while i < 10 { run(values); i = i + 1 }
i = 1
while i < values.length { print(values[i]); i = i + 1 }
'''
        expected = [value for n in range(1,11) for value in (0,-111,11184,5*n)] + [0]*399
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_fill_backedge_shapes_preserve_all_twenty_two_cells(self):
        source = ['record Data { value: Integer }', '''function blank(): List<Integer> { let a: List<Integer> = []; let i = 0; while i < 22 { a.add(0); i = i + 1 }; return a }
function observe(a: List<Integer>) { let i = 0; let sum = 0; while i < a.length { print(a[i]); sum = sum + a[i]; i = i + 1 }; print(sum) }''']
        expected = []
        # Four numeric representations share the exact self-store shape locally.
        for mode in ('self', 'pre', 'post', 'load', 'conditional'):
            assignment = 'let value = 1; if present { value = data.value }; a[i] = value' if mode == 'conditional' else 'a[i] = 1'
            extra = 'a[i] = a[i]' if mode == 'self' else 'let ignored = a[i]' if mode == 'load' else ''
            if mode == 'pre':
                loop = f'while i < 20 {{ {assignment}; {extra}; i = i + 1 }}'
            else:
                loop = f'let active = true; while active {{ {assignment}; {extra}; i = i + 1; active = i < 20 }}'
            source.append(f'function {mode}(present: Boolean, data: Data) {{ let a = blank(); let i = 6; {loop}; observe(a) }}')
        for mode in ['self']*4 + ['pre', 'post', 'load', 'conditional', 'conditional', 'pre']:
            present = mode == 'conditional' and len(expected) == 7*23
            source.append(f'{mode}({str(present).lower()}, Data {{ value: 1 }})')
            expected += [0]*6+[1]*14+[0]*2+[14]
        # Distinguish the present/default branch beyond the identical source1.
        source += ['conditional(true, Data { value: 7 })', 'conditional(false, Data { value: 7 })']
        expected += [0]*6+[7]*14+[0]*2+[98] + [0]*6+[1]*14+[0]*2+[14]
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))

    def test_stateful_checked_conditions_preserve_all_fifty_thousand_calls(self):
        source, expected = [], []
        totals = []
        for name, symbol, bound, direction in [('add', '+', 89361, 1), ('subtract', '-', -31361, -1), ('multiply', '*', 89361, 1)]:
            compare = '>' if direction < 0 else '<'
            source.append(f'''function {name}(state: List<Integer>, counts: List<Integer>): Integer {{
let i = 7
while i {symbol} state[0] {compare} {bound} {{
if ((i {symbol} i) % 2 + 2) % 2 == 1 {{ i = i + {direction*3}; counts[0] = counts[0] + 1 }} else {{
let low = ((i % 8) + 8) % 8
if low == 4 || low == 6 {{ i = i + {direction*7}; counts[1] = counts[1] + 1 }} else {{
if ((i % 16) + 16) % 16 == 6 {{ i = i + {direction*2}; counts[2] = counts[2] + 1 }} else {{ i = i + {direction}; counts[3] = counts[3] + 1 }}
}}
}}
state[0] = state[0] + 2
}}
return i
}}''')
            source += [f'let state{name} = [0]; let counts{name} = [0,0,0,0]; let round{name} = 0',
                       f'while round{name} < 50000 {{ print({name}(state{name}, counts{name})); print(state{name}[0]); round{name} = round{name} + 1 }}']
            source += [f'print(counts{name}[{j}])' for j in range(4)]
            state, counts = 0, [0,0,0,0]
            operation = {'+': lambda a,b:a+b, '-':lambda a,b:a-b, '*':lambda a,b:a*b}[symbol]
            for _ in range(50000):
                i = 7
                while (operation(i,state) > bound if direction < 0 else operation(i,state) < bound):
                    if operation(i,i) & 1: branch, step = 0, 3
                    elif i & 5 == 4: branch, step = 1, 7
                    elif i & 15 == 6: branch, step = 2, 2
                    else: branch, step = 3, 1
                    counts[branch] += 1; i += direction*step; state += 2
                expected += [i,state]
            expected += counts; totals.append((state,counts))
        self.assertEqual(totals, [(89354,[0,22295,0,22382]),(31368,[0,7842,0,7842]),(12766,[4351,811,0,1221])])
        self.evidence.controls['stateful_condition_calls'] = 50000
        self.evidence.controls['stateful_condition_final_counts'] = totals
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))

    def _exact_increment_decrement_cases(self):
        cases = []
        for width in (32,64):
            lo, hi = -(1 << (width-1)), (1 << (width-1))-1
            increments = [(str(lo),lo+1), (f'{hi}-1',hi), ('0',1), ('values[1]',2),
                          (str(hi),hi+1), (f'{hi}-values[0]+values[3]',hi+1), (f'{hi}-1+values[0]',hi+1)]
            decrements = [(str(lo),lo-1), ('minimums[0]',lo-1), (f'{lo}-values[2]',lo-2),
                          ('0',-1), ('values[2]',0), (str(hi),hi-1),
                          (f'{lo}-values[0]+values[3]',lo-1), (f'{lo}+1-values[0]',lo-1)]
            for name, expressions in [('increment',increments),('decrement',decrements)]:
                for i,(expression,result) in enumerate(expressions):
                    preparation_traps = width == 64 and name == 'decrement' and i in (2,6)
                    cases.append((f'{name}{width}_{i}',name,lo,expression,result,preparation_traps))
        self.assertEqual(len(cases),30)
        return cases

    def test_loaded_increment_decrement_expressions_keep_safe_results(self):
        source = ['function increment(value: Integer): Integer { print("callee"); return value + 1 }',
                  'function decrement(value: Integer): Integer { print("callee"); return value - 1 }']
        expected = []
        for label,name,lo,expression,result,prep in self._exact_increment_decrement_cases():
            if prep or not -(1 << 63) <= result < (1 << 63):continue
            source += [f'function {label}(values: List<Integer>, minimums: List<Integer>) {{ print({name}({expression})) }}',
                       f'{label}([1,1,1,1], [{lo},{lo}])']
            expected += ['callee',str(result)]
        self.assertEqual(len(expected),44)
        self.executes('\n'.join(source), '\n'.join(expected)+'\n')

    def test_loaded_increment_decrement_traps_preserve_helper_entry_order(self):
        definitions = ['function increment(value: Integer): Integer { print("callee"); return value + 1 }',
                       'function decrement(value: Integer): Integer { print("callee"); return value - 1 }']
        cases = []
        for label,name,lo,expression,result,prep in self._exact_increment_decrement_cases():
            if not prep and -(1 << 63) <= result < (1 << 63):continue
            definitions.append(f'function {label}(values: List<Integer>, minimums: List<Integer>) {{ print({name}({expression})) }}')
            body = f'print("before"); {label}([1,1,1,1], [{lo},{lo}]); print("after")'
            cases.append((label,body,'before\n'+('' if prep else 'callee\n'),'Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self.assertEqual(len(cases),8)
        self._execute_fatal_branches(definitions,cases)

    def test_nested_repeated_power_loops_keep_all_hundred_results(self):
        self.executes('''function calculate(value: Integer): Integer {
let sum = 0; let j = 0
while j < 100000 { sum = 1; let i = 0; while i < 5 { sum = sum * value; i = i + 1 }; j = j + 1 }
return sum
}
let results: List<Integer> = []; let i = 0
while i < 100 { results.add(calculate(17)); i = i + 1 }
i = 0
while i < results.length { print(results[i]); i = i + 1 }
''', '1419857\n'*100)

    def test_unused_checked_add_before_loop_cannot_be_eliminated(self):
        definition = '''function run(value: Integer): Integer {
let unused = value + 1
let total = 0; let i = value
while i < 200 { total = total + i; i = i + 1 }
return total
}'''
        self.executes(definition+'\nprint(run(19)); print(run(199)); print(run(200)); print(run(9223372036854775806))\n', '19729\n199\n0\n0\n')
        self._execute_fatal_branches([definition], [('maximum','print("before"); print(run(9223372036854775807)); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n')])

    def test_checked_addition_compares_all_source_cohorts_with_signed_bounds(self):
        source = '''function create(value: Integer, other: Integer): Integer {
if value == 0 && other == 0 { return 0 }
if value < -31557014167219200 || value > 31556889864403199 { fail("outside bounds") }
return value
}
function run(value: Integer, other: Integer, store: List<Integer>) { let result = value + 1231; store[0] = create(result, other % 100000) }
let store = [0]; let i = 0
while i < 20000 { run(i, i, store); print(store[0]); run(i-1, i, store); print(store[0]); i = i + 1 }
print(create(0,0))
print(create(-31557014167219200,1)); print(create(31556889864403199,1))
'''
        expected = [value for i in range(20000) for value in (i+1231,i+1230)] + [0,-31557014167219200,31556889864403199]
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_repeated_checked_common_subexpression_loops_keep_full_input_domain(self):
        source = '''function calculate(value: Integer): Integer {
let v = value + value; let sum = 0
if v < 4032 { let i = 0; while i < 1023 { sum = sum + (value + value); i = i + 1 } } else { let i = 0; while i < 321 { sum = sum + (value + value); i = i + 1 } }
return sum + v
}
let i = 0
while i < 50000 {
let value = 93 + i
print(calculate(value)); print(calculate(value)); print(calculate(value)); print(calculate(value)); print(calculate(value))
i = i + 1
}
'''
        expected = [value*(2048 if value < 2016 else 644) for value in range(93,50093) for _ in range(5)]
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_five_large_repeat_operands_use_widened_integer_results(self):
        source, expected = [], []
        for name,symbol,x in [('add','+',2147483637),('subtract','-',-2147483638),('multiply','*',2147483637)]:
            source.append(f'function {name}(x: Integer, y: Integer): Integer {{ return x {symbol} y }}')
            for k in range(5):
                y = 2147483637+k
                result = x+y if symbol == '+' else x-y if symbol == '-' else x*y
                source += [f'print(({x}) {symbol} ({y}))',f'print({name}({x},{y}))']
                expected += [result,result]
                if symbol != '*':
                    source.append(f'function repeat{name}{k}(x: Integer, y: Integer): Integer {{ let result = 0; result = result + 5; result = {name}(x,y); result = result + 6; result = result + {name}(x,y); result = result + 7; result = result + {name}(x,y); result = result + 8; result = result + {name}(x,y); return result }}')
                    source.append(f'print(repeat{name}{k}({x},{y}))');expected.append(4*result+21)
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))

    def test_third_large_product_accumulation_traps_after_safe_prefix(self):
        definition = '''function multiply(x: Integer, y: Integer): Integer { return x * y }
function repeated(x: Integer, y: Integer) {
let result = 0; result = result + 5; print(result)
result = multiply(x,y); print(result)
result = result + 6; print(result)
result = result + multiply(x,y); print(result)
result = result + 7; print(result)
result = result + multiply(x,y); print(result)
result = result + 8; result = result + multiply(x,y); print(result)
}'''
        cases = []
        for k in range(5):
            x,y=2147483637,2147483637+k; product=x*y
            prefix=[5,product,product+6,2*product+6,2*product+13]
            self.assertLess(prefix[-1],1 << 63);self.assertGreaterEqual(prefix[-1]+product,1 << 63)
            cases.append((f'case{k}',f'repeated({x},{y})',''.join(f'{value}\n' for value in prefix),'Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self._execute_fatal_branches([definition],cases)

    def test_zero_initialized_load_product_domain_keeps_all_five_shapes(self):
        source = '''function multiply(a: Integer, b: Integer): Integer { return a * b }
let values: List<Integer> = []; let i = 0
while i < 256 { values.add(0); i = i + 1 }
i = 0
while i < 50000 {
print(multiply(values[i%256], values[i%256]-i))
print(multiply(values[i%256]+i, values[i%256]-i))
print(multiply(values[i%256], values[i%256]))
if i%2 == 1 && i > 5 { print(multiply(values[i%256]+i, values[i%256]-i)) } else { print(multiply(values[i%256]-i, values[i%256]+i)) }
print(multiply(values[i%256], values[(i+1)%256]))
i = i + 1
}
i = 0
while i < values.length { print(values[i]); i = i + 1 }
'''
        expected = [value for i in range(50000) for value in (0,-i*i,0,-i*i,0)] + [0]*256
        self.executes(source, ''.join(f'{value}\n' for value in expected))

    def test_exact_negation_wrapper_inputs_literal_and_parameter(self):
        values = [5,2147483647,-2147483648,1073741823,5,9223372036854775807,4611686018427387903]
        source = ['function negate(value: Integer): Integer { return -value }']
        expected = []
        for value in values:
            source += [f'print(-({value}))', f'print(negate({value}))'];expected += [-value,-value]
        self.executes('\n'.join(source), ''.join(f'{value}\n' for value in expected))
        cases = [(mode, f'print("before"); print({expression}); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n')
                 for mode,expression in [('literal','-(-9223372036854775808)'),('parameter','negate(-9223372036854775808)')]]
        self._execute_fatal_branches([source[0]],cases)

    def test_unused_large_products_trap_before_following_statement(self):
        definitions = ['function product(a: Integer, b: Integer): Integer { return a * b }']
        self.executes(definitions[0]+'\nprint((9223372036854775807 / 2) * 2)\nprint(product(9223372036854775807 / 2, 2))\n', '9223372036854775806\n'*2)
        expressions = ['-9223372036854775808 * 7', 'product(-9223372036854775808, 7)',
                       '((9223372036854775807 / 2) + 1) * 2', 'product((9223372036854775807 / 2) + 1, 2)']
        cases = []
        for i,expression in enumerate(expressions):
            cases.append((f'case{i}',f'print("before"); let unused = {expression}; print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self._execute_fatal_branches(definitions,cases)

    def test_bigint_unary_zero_and_one_exact_parentheses_and_spacing(self):
        source = '''print(-0 == 0)
print(-(0) == 0)
print(-1 != 1)
print(-(1) == -1)
print(-(1) != 1)
print(-(-1) == 1)
print(-(-1) != -1)
print(- - 1 == 1)
print(- - 1 != -1)
'''
        self.executes(source, 'true\n'*9)

    def test_bigint_division_helper_sequences_end_in_fatal_zero(self):
        definition = 'function divide(a: Integer, b: Integer): Integer { return a / b }'
        pairs = [(3,4),(3,1),(30,7),(3,4),(3,1),(30,7),(30,6),(3,4),(30,7),(30,7)]
        self.executes(definition+'\n'+'\n'.join(f'print(divide({a},{b}))' for a,b in pairs), ''.join(f'{a//b}\n' for a,b in pairs))
        self._execute_fatal_branches([definition],[('zero','print("before"); print(divide(3,0)); print("after")','before\n','Minyar stopped: an Integer cannot be divided by zero.\n')])

    def test_linked_index_walk_preserves_previous_node_at_each_step(self):
        self.executes('''let links = [-1, 0, 1, 2, 3, 4]
let data = [5, 4, 3, 2, 1, 0]
let previous = -1
let current = 5
while current >= 0 {
print(data[current])
if previous >= 0 { print(data[previous]) } else { print(-1) }
previous = current
current = links[current]
}
print(previous); print(current)
''', '0\n-1\n1\n0\n2\n1\n3\n2\n4\n3\n5\n4\n0\n-1\n')

    def test_paired_operand_orders_keep_both_results_and_first_failure(self):
        definitions = []
        source, expected, cases = [], [], []
        for name,symbol,a,b in [('add','+',9223372036854775807,1),('subtract','-',-9223372036854775808,1),('multiply','*',9223372036854775807,2)]:
            definitions.append(f'function {name}(x: Integer, y: Integer, result: List<Integer>) {{ result[0] = x {symbol} y; print("first"); result[1] = y {symbol} x; print("second") }}')
            for x,y in [(7,-3),(0,1),(-5,-7)]:
                source += [f'{name}({x},{y},result)', 'print(result[0]); print(result[1])']
                first = x+y if symbol=='+' else x-y if symbol=='-' else x*y
                second = y+x if symbol=='+' else y-x if symbol=='-' else y*x
                expected += ['first','second',str(first),str(second)]
            cases.append((name,f'let result = [11,22]; print("before"); {name}({a},{b},result); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self.executes('\n'.join(definitions+['let result = [11,22]']+source),'\n'.join(expected)+'\n')
        self._execute_fatal_branches(definitions,cases)

    def test_adjacent_checked_additions_preserve_exact_failing_stage(self):
        maximum, minimum = (1 << 63)-1, -(1 << 63)
        shapes = [('mixed','x + 13','a + -7',[(maximum-13,maximum-7)],[(maximum-10,'')]),
                  ('simple','x + 7','a + 13',[(maximum-20,maximum)],[(maximum-6,''),(maximum-19,'first\n')]),
                  ('combine','x + 100','a + 27',[(maximum-127,maximum)],[]),
                  ('cross','x + 100','a + 28',[],[(maximum-127,'first\n')]),
                  ('subtract','x - -12','a + 30',[(minimum,minimum+42),(maximum-42,maximum)],[(maximum-11,''),(maximum-41,'first\n')])]
        definitions,source,expected,cases=[],[],[],[]
        for name,first,second,safe,bad in shapes:
            definitions.append(f'function {name}(x: Integer): Integer {{ let a = {first}; print("first"); let b = {second}; print("second"); return b }}')
            for x,result in safe:
                source.append(f'print({name}({x}))');expected+=['first','second',str(result)]
                binding = f'a{name}{len(source)}'
                # Literal variant retains separate stages and their observable marker.
                literal_first=first.replace('x',f'({x})')
                source.append(f'let {binding} = {literal_first}; print("first"); print({second.replace("a", binding)}); print("second")')
                expected+=['first',str(result),'second']
            for n,(x,prefix) in enumerate(bad):
                for mode in ('helper','literal'):
                    body=f'print({name}({x}))' if mode=='helper' else f'let a = {first.replace("x",f"({x})")}; print("first"); let b = {second}; print("second"); print(b)'
                    cases.append((name+str(n)+mode,body,prefix,'Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self.executes('\n'.join(definitions+source),'\n'.join(expected)+'\n')
        self._execute_fatal_branches(definitions,cases)

    def test_unsigned_short_source_boundaries_use_exact_positive_integer_values(self):
        self.executes('''function select(x: Integer): Integer { let y = 0; if x > 32767 { y = x - 32768 }; return y }
print(select(0)); print(select(32767)); print(select(32768)); print(select(32769)); print(select(65535))
''', '0\n0\n0\n1\n32767\n')

    def test_delimiter_cursor_advances_past_terminator_before_return(self):
        import json
        source = '''function next(text: Text, cursor: List<Integer>): Character { let value = text[cursor[0]]; cursor[0] = cursor[0] + 1; return value }
function ordinary(value: Character): Boolean { return Text(value) != "@" }
function scan(text: Text, cursor: List<Integer>, single: Boolean, double: Boolean): Text {
let current = next(text,cursor)
let output = ""; let active = true
while active {
output = output + Text(current)
current = next(text,cursor)
if single && Text(current) == "'" { active = false } else {
if double && Text(current) == "\\\"" { active = false } else {
if !single && !double && !ordinary(current) { active = false }
}
}
}
return output
}
'''
        cases = [("abcde'fgh",True,False,'abcde','fgh'),('ABCDEFG"HI',False,True,'ABCDEFG','HI'),
                 ('abcd"e\'fgh',True,True,'abcd',"e'fgh"),('ABCDEF\'G"HI',True,True,'ABCDEF','G"HI'),('abcdef@gh',False,False,'abcdef','gh')]
        expected=[]
        for i,(text,single,double,output,rest) in enumerate(cases):
            source += f'let text{i} = {json.dumps(text)}; let cursor{i} = [0]\n'
            source += f'print(scan(text{i},cursor{i},{str(single).lower()},{str(double).lower()})); print(text{i}.slice(cursor{i}[0],text{i}.length)); print(cursor{i}[0])\n'
            expected += [output,rest,str(len(output)+1)]
        self.executes(source,'\n'.join(expected)+'\n')

    def test_signed_large_threshold_survives_single_iteration_selection(self):
        source = '''function select(x: Integer, y: Integer, value: Integer): Integer {
let result = 0; let i = 0
while i < y { if value >= -1152921504606846976 { result = x } else { result = y }; i = i + 1 }
return result
}
'''
        values=[-1152921504606846976,-1152921504606846977,-1152921504606846975,0,-9223372036854775808]
        source+='\n'.join(f'print(select(-1,1,{value}))' for value in values)
        self.executes(source,'-1\n1\n-1\n-1\n1\n')

    def test_unused_statement_and_nested_scope_shapes_keep_original_parameter(self):
        base = {1:'let x = a + b',3:'let z = 0; if a == 2 { z = a } else { z = b }',
                4:'let z = 3; let i = 0; while i < 3 { z = z + 1; i = i + 1 }',
                5:'let z = 3; let i = 0; while i < 3 { z = z + 1; i = i + 1 }; let w = z + a'}
        discarded = {1:'a + b',3:'if a == 2 { a } else { b }',
                     4:'let z = 3; let i = 0; while i < 3 { z + 3; i = i + 1 }',
                     5:'let z = 3; let i = 0; while i < 3 { z + 3; z = z + 1; i = i + 1 }; let w = z + a'}
        source, expected = [], []
        for mode in ('plain','scoped','discarded'):
            for number in (1,3,4,5):
                body = discarded[number] if mode == 'discarded' else base[number]
                if mode == 'scoped': body = 'if true { '+body+' }'
                params = 'a: Integer, b: Integer' if number < 4 else 'a: Integer'
                source.append(f'function {mode}{number}({params}): Integer {{ {body}; return a }}')
            for a,b in [(33,32),(34,7)]:
                for number in (1,3,4,5):
                    args = f'{a},{b}' if number < 4 else str(a)
                    source.append(f'print({mode}{number}({args}))');expected.append(a)
            source.append(f'print({mode}3(2,99))');expected.append(2)
        self.executes('\n'.join(source),''.join(f'{value}\n' for value in expected))

    def test_consecutive_additions_keep_early_return_boundary(self):
        definitions=['function first(n: Integer): Integer { let a = n + 2; return a + 3 }',
                     'function second(n: Integer, early: Boolean): Integer { let a = n + 2; if early { return a }; return a + 3 }']
        self.executes('\n'.join(definitions)+'''
print(first(1)); print(first(2)); print(first(13)); print(first(14))
print(second(1,true)); print(second(2,false)); print(second(13,true)); print(second(14,false))
print(second(9223372036854775805,true))
''','6\n7\n18\n19\n3\n7\n15\n19\n9223372036854775807\n')
        calls=['first(9223372036854775806)','second(9223372036854775806,true)',
               'second(9223372036854775806,false)','second(9223372036854775805,false)']
        self._execute_fatal_branches(definitions,[(f'case{i}',f'print("before"); print({call}); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n') for i,call in enumerate(calls)])

    def test_zero_divisor_guard_runs_after_first_nested_loop_store(self):
        definitions = ['''function blank(): List<Integer> { let a: List<Integer> = []; let i = 0; while i < 256 { a.add(0); i = i + 1 }; return a }''']
        for n,operator in enumerate(('%','/','%','/'),1):
            definitions.append(f'''function shape{n}(divisor: Integer, values: List<Integer>): Integer {{
let result = 0; let i = 0
while i < 256 {{
let j = 0; let active = true
while active {{
values[i] = i
print(values[i])
result = 1 {operator} divisor
j = j + 1; active = j < 9
}}
i = i + 1
}}
return result
}}''')
        cases=[(f'shape{n}',f'let values = blank(); print(shape{n}(0,values)); print("after")','0\n','Minyar stopped: an Integer cannot be divided by zero.\n') for n in range(1,5)]
        self._execute_fatal_branches(definitions,cases)

    def test_literal_minimum_multiplier_keeps_widening_and_fatal_boundary(self):
        definitions=['function narrow(value: Integer): Integer { return value * -2147483648 }',
                     'function wide(value: Integer): Integer { return value * -9223372036854775808 }']
        self.executes('\n'.join(definitions)+'\nprint(narrow(0)); print(narrow(1)); print(narrow(2)); print(wide(0)); print(wide(1))\n', '0\n-2147483648\n-4294967296\n0\n-9223372036854775808\n')
        self._execute_fatal_branches(definitions,[('wide','print("before"); print(wide(2)); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n')])

    def _peer_integer_distribution_families(self):
        import random
        minimum, maximum = -(1 << 63), (1 << 63)-1
        families = []
        counts = {32: (64,301,1811), 64: (127,616,3890)}
        for width in (32,64):
            powers = {}
            for radius, cardinality in zip((0,2,16),counts[width]):
                domain = sorted({sign*(1 << exponent)+offset for exponent in range(width)
                                 for sign in (-1,1) for offset in range(-radius,radius+1)
                                 if minimum <= sign*(1 << exponent)+offset <= maximum})
                self.assertEqual(len(domain),cardinality)
                powers[radius]=domain
            for choice in range(6):
                seed = 0x5eed0000+width*100+choice
                rng = random.Random(seed)
                trace = []
                if choice in (1,2,3):
                    radius = {1:0,2:2,3:16}[choice]
                    values = powers[radius]
                    scope = f'exhaustive exact signed-power neighborhood radius{radius}; no Java wrapping'
                else:
                    values = []
                    for _ in range(256):
                        # Upstream mixed generators choose a cumulative-weight bucket.
                        uniform = choice == 0 or rng.randrange(2 if choice == 4 else 3) == 0
                        trace.append('uniform' if uniform else 'power')
                        if uniform: values.append(rng.randrange(-(1 << (width-1)),1 << (width-1)))
                        else: values.append(rng.choice(powers[16 if choice == 4 else 2]))
                    self.assertEqual(len(values),256)
                    if choice != 0:self.assertEqual(set(trace),{'uniform','power'})
                    scope = '256 seeded draws; distribution methodology, not exhaustive random value space'
                families.append({'id':f'{width}-choice{choice}','seed':seed,'values':values,'buckets':trace,'scope':scope})
        self.assertEqual(len(families),12)
        self.evidence.controls['integer_distribution_families']=families
        return families

    def test_biased_integer_generator_domains_with_exact_runtime_oracles(self):
        families=self._peer_integer_distribution_families()
        values=sorted({value for family in families for value in family['values']})
        minimum,maximum=-(1 << 63),(1 << 63)-1
        self.assertEqual((values[0],values[-1]),(minimum,maximum))
        self.evidence.controls['unique_generated_integer_operands']=len(values)
        definition='''function calculate(value: Integer) {
print(value / 3); print(value % 3)
if value == 9223372036854775807 { print("increment-overflow") } else { print(value + 1) }
if value == -9223372036854775808 { print("negation-overflow") } else { print(-value) }
}'''
        for start in range(0,len(values),512):
            chunk=values[start:start+512]
            source=definition+'\nlet values = ['+', '.join(map(str,chunk))+']\nlet i = 0\nwhile i < values.length { calculate(values[i]); i = i + 1 }\n'
            expected=[]
            for value in chunk:
                quotient=abs(value)//3*(-1 if value < 0 else 1)
                remainder=value-quotient*3
                expected += [str(quotient),str(remainder),'increment-overflow' if value==maximum else str(value+1),
                             'negation-overflow' if value==minimum else str(-value)]
            with self.subTest(first=start,count=len(chunk)):
                self.executes(source,'\n'.join(expected)+'\n')

    def test_generated_domain_extreme_operations_have_exact_fatal_oracles(self):
        definitions=['function increment(value: Integer): Integer { return value + 1 }',
                     'function negate(value: Integer): Integer { return -value }']
        cases=[]
        for name,expression in [('increment','increment(9223372036854775807)'),('negate','negate(-9223372036854775808)')]:
            cases.append((name,f'print("before"); print({expression}); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self._execute_fatal_branches(definitions,cases)

    def test_computed_minimum_maximum_arguments_in_both_orders(self):
        self.executes('''function maximum(a: Integer,b: Integer): Integer { if a > b { return a }; return b }
function minimum(a: Integer,b: Integer): Integer { if a < b { return a }; return b }
let leftPosition = 32; let leftSize = 32; let rightPosition = 0; let rightSize = 32
print(maximum(leftPosition+leftSize,rightPosition+rightSize))
print(maximum(rightPosition+rightSize,leftPosition+leftSize))
print(minimum(leftPosition+leftSize,rightPosition+rightSize))
print(minimum(rightPosition+rightSize,leftPosition+leftSize))
''','64\n64\n32\n32\n')

    def test_two_store_orders_reload_same_and_distinct_aliases(self):
        self.executes('''function first(global: List<Integer>, parameter: List<Integer>): Integer { global[0] = 1; parameter[0] = 2; return global[0] }
function second(global: List<Integer>, parameter: List<Integer>): Integer { parameter[0] = 2; global[0] = 1; return parameter[0] }
let global = [0]; let other = [0]
print(first(global,global)); print(second(global,global))
print(first(global,other)); print(other[0]); print(second(global,other)); print(other[0]); print(global[0])
''','2\n1\n1\n2\n2\n2\n1\n')

    def test_range_guard_and_nested_selection_keep_all_five_calls(self):
        self.executes('''function select(a: Integer, b: Boolean): Integer {
if a < 0 || a > 30 { fail("outside range") }
let result = a
if b { result = 100 } else { if a != 0 { result = a } else { result = 1 } }
return result
}
print(select(0,false)); print(select(1,false)); print(select(0,true)); print(select(1,false)); print(select(30,false))
''','1\n1\n100\n1\n30\n')

    def test_loop_local_value_survives_readonly_call_before_stateful_check(self):
        self.executes('''function readonly(value: Integer) {}
function check(value: Integer, ignored: Integer, expected: List<Integer>) {
print(value == expected[0]); print(value); expected[0] = expected[0] + 1
}
let expected = [0]; let i = 0
while i < 4 { let local = i; readonly(local); let copied = local; check(copied,copied,expected); i = i + 1 }
print(expected[0])
''','true\n0\ntrue\n1\ntrue\n2\ntrue\n3\n4\n')

    def test_malformed_foreign_binary_numerals_are_rejected(self):
        for token in ('0b1234','0b10010f','0b10010g','0b'):
            with self.subTest(token=token):
                self.rejects(f'let value = {token}\nprint(value)\n','Minyar stopped:')

    def test_foreign_multibyte_character_literals_are_single_scalars(self):
        self.executes("print('ñ')\nprint('ሴ')\nprint('ñ')\nprint('ሴ')\n",'ñ\nሴ\nñ\nሴ\n')

    def test_legacy_octal_spellings_retain_minyar_decimal_values(self):
        self.executes('\n'.join(f'print(0{value})' for value in range(70,78)),''.join(f'{value}\n' for value in range(70,78)))

    def test_large_neighbor_equality_keeps_literal_and_parameter_orders(self):
        low=0x1fffffffffffff01;high=0x1fffffffffffff02
        pairs=[(low,low),(low,high),(high,low),(-low,-low),(-low,-high),(-high,-low)]
        source=['function equal(a: Integer,b: Integer): Boolean { return a == b }'];expected=[]
        for a,b in pairs:
            source += [f'print(({a}) == ({b}))',f'print(equal({a},{b}))'];expected += [str(a==b).lower()]*2
        self.executes('\n'.join(source),'\n'.join(expected)+'\n')

    def test_integer_text_addition_requires_explicit_conversion_in_both_orders(self):
        source=[];expected=[]
        for value in (-1,0,1):
            source += [f'print(Text({value}) + "")',f'print("" + Text({value}))'];expected += [str(value)]*2
        self.executes('\n'.join(source),'\n'.join(expected)+'\n')
        for value in (-1,0,1):
            for expression in (f'({value}) + ""',f'"" + ({value})'):
                with self.subTest(expression=expression):self.rejects(f'print({expression})\n','Minyar stopped:')

    def test_signed_one_and_zero_products_keep_zero_divisor_failure(self):
        expressions=['1 * 1','1 * -1','-1 * 1','-1 * -1','0 * 0','0 * -0','-0 * 0','-0 * -0']
        self.executes('\n'.join(f'print({expression})' for expression in expressions),'1\n-1\n-1\n1\n0\n0\n0\n0\n')
        cases=[(f'zero{i}',f'print("before"); print(1 / ({expression})); print("after")','before\n','Minyar stopped: an Integer cannot be divided by zero.\n') for i,expression in enumerate(expressions[4:])]
        self._execute_fatal_branches([],cases)

    def test_modulus_helper_sequence_and_all_zero_divisor_spellings(self):
        definition='function remainder(a: Integer,b: Integer): Integer { return a % b }'
        pairs=[(3,4),(3,1),(3,4),(3,1),(-32,9),(32,7),(3,4)]
        expected=[]
        for a,b in pairs:
            q=abs(a)//abs(b)*(-1 if (a<0)!=(b<0) else 1);expected.append(a-q*b)
        self.executes(definition+'\n'+'\n'.join(f'print(remainder({a},{b}))' for a,b in pairs),''.join(f'{value}\n' for value in expected))
        spellings=[('-0','0'),('-0','-0'),('0','0'),('0','-0'),('-1','0'),('-1','-0'),('1','0'),('1','-0')]
        cases=[]
        for i,(a,b) in enumerate(spellings):
            for mode,expression in [('literal',f'{a} % {b}'),('helper',f'remainder({a},{b})')]:
                cases.append((f'case{i}{mode}',f'print("before"); print({expression}); print("after")','before\n','Minyar stopped: an Integer cannot be divided by zero.\n'))
        cases.append(('bigint','print("before"); print(remainder(3,0)); print("after")','before\n','Minyar stopped: an Integer cannot be divided by zero.\n'))
        self._execute_fatal_branches([definition],cases)

    def test_parameter_selected_copy_bound_preserves_alias_and_distinct_cells(self):
        self.executes('''function bound(k: Integer, stop: Integer): Integer { let result = 0; if k == 42 { result = stop } else { result = 5 }; return result }
function copy(start: Integer, stop: Integer, source: List<Integer>, target: List<Integer>) {
let j = start; while j < stop { let value = source[j+3]; target[j+3] = value; j = j + 1 }
}
function run(stop: Integer, same: Boolean, first: List<Integer>, second: List<Integer>) {
let source = first; let target = second; if same { target = first }
let k = 2; while k < 4 { k = k * 2 }
let limit = bound(k,stop)
print(k); print(limit); copy(0,limit,source,target)
}
print(bound(0,0)); print(bound(42,0))
let first: List<Integer> = []; let second: List<Integer> = []; let i = 0
while i < 100 { first.add(i); second.add(-1); i = i + 1 }
copy(0,20,first,first)
i = 0; while i < 100 { print(first[i]); i = i + 1 }
run(20,true,first,second)
i = 0; while i < 100 { print(first[i]); print(second[i]); i = i + 1 }
run(20,false,first,second)
i = 0; while i < 100 { print(first[i]); print(second[i]); i = i + 1 }
''','5\n0\n'+''.join(f'{i}\n' for i in range(100))+'4\n5\n'+''.join(f'{i}\n-1\n' for i in range(100))+'4\n5\n'+''.join(f'{i}\n{i if 3<=i<8 else -1}\n' for i in range(100)))

    def test_incremented_condition_preserves_final_false_value_and_outer_state(self):
        self.executes('''function advance(cell: List<Integer>): Boolean { cell[0] = cell[0] + 3; return cell[0] < 5 }
let y = 0; let array = [0]; let i = 0
while i < 10 {
let j = [1]
while advance(j) { array[0] = 0; let k = j[0]; while k < 5 { y = y + 1; k = k + 1 }; print(y) }
y = j[0]
print(i); print(j[0]); print(y); print(array[0])
i = i + 2
}
''','1\n0\n7\n7\n0\n'+''.join(f'8\n{i}\n7\n7\n0\n' for i in (2,4,6,8)))

    def test_large_stride_exits_without_int32_wraparound(self):
        self.executes('''function basic(state: List<Integer>) {
let i = state[0]; let active = true; let iterations = 0
while active { state[0] = state[0] + state[1]; i = i + 1; iterations = iterations + 1; active = i < state[2] }
print(state[0]); print(i); print(iterations)
}
function large(initial: Integer, limit: Integer, one: List<Integer>): Integer {
let iterations = 0; let i = initial
while i < limit {
iterations = iterations + one[0]
if iterations > limit / 100000 + 1 { return -1 }
i = i + 100000
}
print(i); return iterations
}
let mode = 0
while mode < 2 { basic([0,0,0]); print(large(0,10000000,[1])); print(large(0,2147483647,[1])); mode = mode + 1 }
''','0\n1\n1\n10000000\n100\n2147500000\n21475\n'*2)

    def test_profile_predicate_helpers_keep_early_return_visit_traces(self):
        source='''function helper(stop: Integer, flags: List<Boolean>, second: Boolean) {
let i = 0
while i < stop { print(i); if flags[i] { return }; if second {}; i = i + 1 }
}
function outer(stop: Integer, flags: List<Boolean>, second: Boolean, gates: List<Boolean>, increment: Integer) {
let j = 0
while j < 100 { if gates[j] { helper(stop,flags,second) }; j = j + increment }
}
let first = [false,true]; let second = [true,false]
helper(2,first,false); helper(2,second,false); helper(2,second,false)
let gates: List<Boolean> = [false]; let i = 1
while i < 100 { gates.add(true); i = i + 1 }
outer(2,first,false,gates,1); outer(2,second,false,gates,1); outer(2,second,false,gates,1)
'''
        self.executes(source,'0\n1\n0\n0\n'+'0\n1\n'*99+'0\n'*198)

    def test_negative_first_store_into_empty_list_fails_without_recovery(self):
        definitions=['''function run(zero: Integer) {
let values: List<Integer> = []; let i = 0
while i < zero { values.add(0); i = i + 1 }
let outer = 0
while outer < 5 { let index = -400; while index < 1 { print(index); values[index] = 1; index = index + 1 }; outer = outer + 1 }
}''']
        self._execute_fatal_branches(definitions,[(f'outer{i}','run(0)','-400\n','Minyar stopped: List position -400 is outside its length of 0.\n') for i in range(5)])

    def test_predicate_clone_shapes_keep_exact_recurrence_and_dead_loads(self):
        source=[];expected=[]
        x=3;trace=[]
        for _ in range(14):x=6*x-5;trace.append(x)
        self.assertEqual(x,156728328193)
        for mode in ('unswitch','predication','combined'):
            load='let loaded = values[j];' if mode != 'unswitch' else ''
            body='x = 34; '+load
            if mode != 'predication':body+=' let y = 34; if constant == 2 { y = 35 }; if y != state[0] { state[1] = 34 }'
            guard='if !present { return -1 };' if mode=='combined' else ''
            source.append(f'''function {mode}(values: List<Integer>, state: List<Integer>, flag: Boolean, present: Boolean): Integer {{
let x = 3; {guard} let limit = 2; let constant = 2
while limit < 4 {{ limit = limit * 2 }}
let k = 2; while k < limit {{ constant = 6; k = k + 1 }}
let i = 51
while i > 9 {{
if flag {{ x = x * 6 }}
x = x - 5
let j = 1; while j < 10 {{ if !flag {{ {body} }}; j = j + 1 }}
print(x); i = i - 3
}}
i = 0; while i < values.length {{ values[i] = 3; i = i + 1 }}
return x
}}''')
        source+=['let values: List<Integer> = []; let i = 0; while i < 100 { values.add(0); i = i + 1 }; let state = [0,0]']
        for mode in ('unswitch','predication','combined'):
            source += [f'print({mode}(values,state,true,true)); print(state[1])','i = 0; while i < values.length { print(values[i]); i = i + 1 }']
            expected += trace+[x,0]+[3]*100
        self.executes('\n'.join(source),''.join(f'{value}\n' for value in expected))

    def test_guarded_nested_fuzzer_loops_preserve_unchanged_lists_and_counts(self):
        source='''function blank(n: Integer, value: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i < n { a.add(value); i = i + 1 }; return a }
function first(flag: Boolean) {
let x = 0; let values = blank(400,0); let longs = blank(400,0)
let countA = 0; let countB = 0; let position = 0
while position < longs.length {
let item = longs[position]; let i = 63
while i > 1 {
let j = 1; while j < 4 { if !flag { x = x - 5 }; countA = countA + 1; j = j + 1 }
j = 1; while j < 4 { if !flag { x = values[j] }; if i == 0 { item = item + 5 }; countB = countB + 1; j = j + 1 }
i = i - 3
}
print(item); position = position + 1
}
print(x); print(countA); print(countB)
position = 0; while position < 400 { print(values[position]); print(longs[position]); position = position + 1 }
}
function third(values: List<Integer>, flag: Boolean) {
let x = 8; let y = 4; let index = 0
while index < values.length {
let item = values[index]
x = x + 2
if flag { x = 3 } else { y = 2 }
let j = 0
while j < 10 { x = 0; y = y + 5; if !flag { values[1] = 5 }; j = j + 1 }
print(x); print(y); index = index + 1
}
index = 0; while index < values.length { print(values[index]); index = index + 1 }
}
first(true); third(blank(100,3),true)
'''
        expected=[0]*400+[0,25200,25200]+[0]*800+[value for i in range(1,101) for value in (0,4+50*i)]+[3]*100
        self.executes(source,''.join(f'{value}\n' for value in expected))

    def test_record_field_cancellation_preserves_zero_divisor_failure(self):
        definitions=['record A { x: Integer }','record C { x: Integer, y: Integer }','record E { d: A }',
                     'function first(): Integer { let a = A { x: 42 }; return 1 / (a.x - 42) }',
                     'function third(): Integer { let c = C { x: 1, y: -1 }; return 1 / (c.x + c.y) }',
                     'function fourth(): Integer { let c = C { x: 0, y: 0 }; return 1 / (c.x + c.y) }',
                     'function fifth(): Integer { let e = E { d: A { x: 32 } }; return 1 / (e.d.x - 32) }']
        self._execute_fatal_branches(definitions,[(name,f'print("before"); print({name}()); print("after")','before\n','Minyar stopped: an Integer cannot be divided by zero.\n') for name in ('first','third','fourth','fifth')])

    def test_diagonal_only_nested_list_stores_preserve_off_diagonal_zeroes(self):
        self.executes('''function fill(values: List<List<Integer>>) {
let i = 0
while i < 2 { let j = 0; while j < 2 { if i == j { let row = values[i]; row[j] = 1 }; j = j + 1 }; i = i + 1 }
}
let values = [[0,0],[0,0]]
fill(values)
print(values[0][0]); print(values[0][1]); print(values[1][0]); print(values[1][1])
''','1\n0\n0\n1\n')

    def test_four_parenthesized_add_subtract_forms_keep_checked_intermediates(self):
        expressions=['i - (5 - i)','i + (5 + i)','i - (5 + i)','i + (5 - i)']
        definitions=[f'function shape{n}(i: Integer): Integer {{ return {expression} }}' for n,expression in enumerate(expressions)]
        source=[]
        for n,expression in enumerate(expressions):source += [f'print(shape{n}(20))',f'print({expression.replace("i","20")})']
        self.executes('\n'.join(definitions+source),'35\n35\n45\n45\n-5\n-5\n5\n5\n')
        cases=[]
        for n,value in enumerate([9223372036854775807]*3+[-9223372036854775808]):
            for mode,expression in [('helper',f'shape{n}({value})'),('literal',expressions[n].replace('i',f'({value})'))]:
                cases.append((f'case{n}{mode}',f'print("before"); print({expression}); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self._execute_fatal_branches(definitions,cases)

    def test_local_text_lists_return_owned_indexed_values(self):
        self.executes('''function one(i: Integer): Text { let values = ["first"]; return values[i] }
function two(i: Integer): Text { let values = ["first", "second"]; return values[i] }
print(one(0)); print(one(0)); print(one(0))
print(two(0)); print(two(1)); print(two(0)); print(two(1))
''', 'first\nfirst\nfirst\nfirst\nsecond\nfirst\nsecond\n')

    def test_addition_helper_preserves_two_exact_call_sequences(self):
        pairs=[(3,7),(17,-54),(6,2),(30,-50),(23,5),(-7,-12)]
        self.executes('function add(x: Integer, y: Integer): Integer { return x + y }\n'+'\n'.join(f'print(add({x}, {y}))' for x,y in pairs), ''.join(f'{x+y}\n' for x,y in pairs))

    def test_boolean_equality_helper_keeps_repeated_same_type_calls(self):
        self.executes('''function equal(a: Boolean, b: Boolean): Boolean { return a == b }
print(equal(false,false)); print(equal(true,true)); print(equal(true,false))
print(equal(false,false)); print(equal(true,true)); print(equal(true,false))
''', 'true\ntrue\nfalse\ntrue\ntrue\nfalse\n')

    def test_explicit_list_clones_keep_contents_and_independent_mutations(self):
        source='''function cloneFrom(values: List<Integer>, start: Integer): List<Integer> {
let result: List<Integer> = []; let i = start
while i < values.length { result.add(values[i]); i = i + 1 }
return result
}
function clone(values: List<Integer>): List<Integer> { return cloneFrom(values,0) }
function show(values: List<Integer>) { let i = 0; while i < values.length { print(values[i]); i = i + 1 } }
let original = [1,2,3,4,5]
let first = clone(original); show(first)
let independent = clone(original); independent[0] = 99; show(original); show(independent)
'''
        for n, reverse in enumerate([False,True,False,False]):
            left='cloneFrom(original,0)' if reverse else 'clone(original)'
            right='clone(original)' if reverse else 'cloneFrom(original,0)'
            source+=f'let left{n} = {left}; let right{n} = {right}; show(left{n}); show(right{n})\n'
            source+=f'left{n}[4] = {90+n}; show(right{n}); show(original)\n'
        expected=[1,2,3,4,5]*2+[99,2,3,4,5]+[1,2,3,4,5]*16
        self.executes(source,''.join(f'{value}\n' for value in expected))

    def test_discarded_products_keep_original_parameter_after_loops(self):
        self.executes('''function third(a: Integer,b: Integer): Integer { if a == 2 { a * b } else { b * a }; return a }
function fourth(a: Integer): Integer { let z = 3; let i = 0; while i < 3 { z * 3; i = i + 1 }; return a }
function fifth(a: Integer): Integer { let z = 3; let i = 0; while i < 3 { z * 3; z = z + 1; i = i + 1 }; let w = z * a; return a }
print(third(33,32)); print(fourth(33)); print(fifth(33))
print(third(34,7)); print(fourth(34)); print(fifth(34)); print(third(2,7))
''','33\n33\n33\n34\n34\n34\n2\n')

    def test_aliased_flags_preserve_reassigned_counted_loop_limit(self):
        self.executes('''function choose(flag: Boolean,x: Integer,y: Integer): Integer { if flag { return x }; return y }
function run(flags: List<Boolean>,other: List<Boolean>,barrier: List<Integer>): Integer {
let j = choose(other[0],0,1); let i = 1; let limit = 0; let active = true
while active { limit = j; if i >= 100 { active = false } else { if flags[i] { return limit - 3 }; j = choose(other[i],100,101); i = i * 2 } }
let k = 0; while k < limit { barrier[0] = 66; barrier[1] = barrier[1] + 1; k = k + 1 }
return j
}
let no: List<Boolean> = []; let yes: List<Boolean> = []; let i = 0
while i < 100 { no.add(false); yes.add(true); i = i + 1 }
let barrier = [-1,0]
print(run(no,no,barrier)); print(barrier[0]); print(barrier[1])
barrier[0] = -1; barrier[1] = 0
print(run(yes,yes,barrier)); print(barrier[0]); print(barrier[1])
print(choose(true,0,0)); print(choose(false,0,0))
''','101\n66\n101\n-3\n-1\n0\n0\n0\n')

    def test_four_flag_conditional_move_domain_keeps_all_twenty_thousand_calls(self):
        source='''function called(stats: List<Integer>): Integer { stats[1] = stats[1] + 1; return 0 }
function shape(flag1: Boolean,flag2: Boolean,flag3: Boolean,flag4: Boolean,field: List<Integer>,stats: List<Integer>): Integer {
let v3 = 0
if flag4 { let i = 0; let active = true
while i < 10 && active { stats[0] = stats[0] + 1; let v1 = 0
if flag1 { v1 = called(stats) }
let v2 = v1; if flag2 { v2 = field[0] + v1 }
if flag3 { v3 = v2 * 2; active = false }; i = i + 1
} }
return v3
}
let field = [0]; let stats = [0,0]; let groups = [0,0,0,0]; let i = 0
while i < 20000 {
let even = i % 2 == 0; let century = i % 100 == 1; let thousand = i % 1000 == 1
print(shape(even,even,century,thousand,field,stats))
if even { groups[0] = groups[0] + 1 } else { if thousand { groups[3] = groups[3] + 1 } else { if century { groups[2] = groups[2] + 1 } else { groups[1] = groups[1] + 1 } } }
i = i + 1
}
print(stats[0]); print(stats[1]); print(groups[0]); print(groups[1]); print(groups[2]); print(groups[3])
'''
        self.executes(source,'0\n'*20000+'20\n0\n10000\n9800\n180\n20\n')

    def test_ordinary_loop_less_and_not_equal_exits_share_independent_count(self):
        self.executes('''function next(value: Integer): Integer { return value + 1 }
function less(bounds: List<Integer>): Integer { let initial = bounds[0]; let limit = bounds[1]; let sum = 0; let i = initial; while i < limit { sum = next(sum); i = i + 1 }; return sum }
function unequal(bounds: List<Integer>): Integer { let initial = bounds[0]; let limit = bounds[1]; let sum = 0; let i = initial; while i != limit { sum = next(sum); i = i + 1 }; return sum }
let bounds = [11,33]
print(less(bounds)); print(unequal(bounds)); print(less(bounds)); print(unequal(bounds))
''','22\n22\n22\n22\n')

    def test_three_records_between_scalar_arguments_keep_each_field(self):
        self.executes('''record Tiny { c: Integer }
function check(n: Integer,x: Tiny,y: Tiny,z: Tiny,tail: Integer) { print(n); print(x.c); print(y.c); print(z.c); print(tail) }
let values = [Tiny { c: 10 },Tiny { c: 11 },Tiny { c: 12 }]
check(3,values[0],values[1],values[2],123)
''','3\n10\n11\n12\n123\n')

    def test_four_comparison_shapes_keep_positive_int32_boundary(self):
        expressions=['i < 2147483648','i <= 2147483647','i >= 2147483648','i > 2147483647']
        definitions=[]
        for n,expression in enumerate(expressions):
            first,second=(1,0) if n<2 else (0,1)
            definitions.append(f'function shape{n}(i: Integer): Integer {{ if {expression} {{ return {first} }}; return {second} }}')
        values=[2147483648,2147483647,2147483649,0,9223372036854775807]
        self.executes('\n'.join(definitions+[f'print(shape{n}({value}))' for value in values for n in range(4)]),''.join(f'{int(value<2147483648)}\n' for value in values for n in range(4)))

    def test_returned_record_retains_all_four_list_elements(self):
        self.executes('''record Values { elements: List<Integer> }
function build(): Values { let cells = [0,0,0,0]; cells[0] = 10; cells[1] = 20; cells[2] = 30; cells[3] = 40; return Values { elements: cells } }
function check() { let value = build(); let i = 0; while i < 4 { print(value.elements[i]); i = i + 1 } }
check()
''','10\n20\n30\n40\n')

    def test_clamped_radius_index_loop_preserves_all_index_traces(self):
        self.executes('''function scan(i: Integer,j: Integer,radius: Integer,width: Integer,n: Integer) {
let difference = i - radius; let low = 0; if difference > 0 { low = difference }
let k = low
while k <= 2 { let index = ((k - i + radius) * width - j + radius); print(index); k = k + 1 }
k = low; while k <= 2 { k = k + 1 }; print(k)
}
let radius = 2; let n = 8; let i = 1
while i < 4 { scan(i,1,radius,2*radius+1,n); i = i + 1 }
''','6\n11\n16\n3\n1\n6\n11\n3\n1\n6\n3\n')

    def test_identical_text_literal_index_reads_preserve_each_character(self):
        self.executes('''let first = "foo"; let second = "foo"; let i = 0
while i < 3 { print(first[i]); print(second[i]); print(first[i] == second[i]); i = i + 1 }
''','f\nf\ntrue\no\no\ntrue\no\no\ntrue\n')

    def test_false_sentinel_guards_do_not_speculate_invalid_stores(self):
        self.executes('''function zero(sentinel: List<Integer>,invalid: List<Integer>) { if sentinel[0] != 0 { invalid[0] = 0 } }
function negative(sentinel: List<Integer>,invalid: List<Integer>) { if sentinel[0] != 0 { invalid[0] = -1 } }
function positive(sentinel: List<Integer>,invalid: List<Integer>) { if sentinel[0] != 0 { invalid[0] = 1 } }
let sentinel = [0]; let invalid: List<Integer> = []
zero(sentinel,invalid); print(invalid.length)
negative(sentinel,invalid); print(invalid.length)
positive(sentinel,invalid); print(invalid.length); print(sentinel[0])
''','0\n0\n0\n0\n')

    def test_nested_record_projection_alias_survives_five_helper_calls(self):
        self.executes('''record Inner { a: Integer }
record Outer { a: Inner }
function inspect() { let x = Inner { a: 7 }; let y = Outer { a: x }; let z = y.a; print(z.a) }
inspect(); inspect(); inspect(); inspect(); inspect()
''','7\n'*5)

    def test_unary_minus_literal_local_and_record_reference_shapes(self):
        self.executes('''record Value { prop: Integer }
print(-1); print(-(-1)); let x = -1; print(-x); print(-(-x))
let object = Value { prop: 1 }; print(-object.prop)
''','-1\n1\n1\n-1\n-1\n')

    def test_division_literal_local_and_record_reference_shapes(self):
        self.executes('''record Value { prop: Integer }
print(1 / 1); let x = 1; print(x / 1); let y = 1; print(1 / y); print(x / y)
let first = Value { prop: 1 }; let second = Value { prop: 1 }; print(first.prop / second.prop)
print(1 / 1); print(1 / -1); print(-1 / 1); print(-1 / -1)
''','1\n'*6+'-1\n-1\n1\n')

    def test_text_integer_addition_and_division_never_coerce_implicitly(self):
        for operator in ('+','/'):
            for text in ('"1"','"x"'):
                for expression in (f'{text} {operator} 1',f'1 {operator} {text}'):
                    with self.subTest(expression=expression):
                        self.rejects(f'print({expression})\n','Minyar stopped:')

    def test_nested_overunrolling_shapes_preserve_store_and_visit_domains(self):
        source='''function show(values: List<Integer>) { let i = 0; while i < values.length { print(values[i]); i = i + 1 } }
function second(values: List<Integer>,state: List<Integer>) {
let i = 6; while i < 10 { let j = 8; while j > i { let k = 1; let active = true
while active { print(j); values[j] = 0; if k == 1 { state[0] = 0 }; k = k + 1; active = k < 1 }; j = j - 1 }; i = i + 1 }
}
function third(input: List<Integer>,values: List<Integer>,state: List<Integer>) {
let i = 0; while i < input.length { let j = 5; while j < i { let k = 1; let active = true
while active { print(j); values[j] = 0; if k == 1 { state[0] = 0 }; k = k + 1; active = k < 1 }; j = j + 1 }; i = i + 1 }
}
function fourth(input: List<Integer>,values: List<Integer>,state: List<Integer>,store: Boolean) {
let count = 0; let i = -8; while i < 8 { let j = 5; while j > i { let k = 1; let active = true
while active { if store { values[j] = 0 }; if k == 1 { state[0] = 0 }; count = count + 1; k = k + 1; active = k < 1 }; j = j - 1 }; i = i + 1 }; print(count)
}
function fifth(input: List<Integer>,values: List<Integer>): Integer { let result = 0; let i = 0
while i < input.length { let j = 5; while j < i { print(j); values[j] = values[j] + input[j]; result = result + input[j]; j = j + 1 }; i = i + 1 }; return result }
let input = [0,0,0,0,0,0,0,0]; let state = [7]; let ten = [9,9,9,9,9,9,9,9,9,9]
second(ten,state); show(ten); print(state[0])
let eight = [9,9,9,9,9,9,9,9]; state[0] = 7; third(input,eight,state); show(eight); print(state[0])
let unchanged = [9,9,9,9,9,9,9,9]; state[0] = 7; fourth(input,unchanged,state,false); show(unchanged); print(state[0])
let output = [0,0,0,0,0,0,0,0]; print(fifth(input,output)); show(output)
let marked = [1,2,3,4,5,6,7,8]; print(fifth(marked,output)); show(output)
'''
        expected=[8,7,8]+[9]*7+[0,0,9]+[0]+[5,5,6]+[9]*5+[0,0,9]+[0]+[91]+[9]*8+[0]+[5,5,6,0]+[0]*8+[5,5,6,19]+[0]*5+[12,7,0]
        self.executes(source,''.join(f'{v}\n' for v in expected))

    def test_redundant_self_assignment_loops_keep_safe_remainder_counts(self):
        self.executes('''function pre() { let k = 3; let count = 0; let i = 9
while i > 0 { let j = 2; while j < i { k = k; k = 1 % j; count = count + 1; j = j + 1 }; i = i - 1 }; print(k); print(count) }
function post() { let k = 3; let count = 0; let i = 9
while i > 0 { let j = 2; let active = true; while active { k = k; k = 1 % j; count = count + 1; j = j + 1; active = j < i }; i = i - 1 }; print(k); print(count) }
pre(); post(); pre(); post()
''','1\n28\n1\n30\n'*2)

    def test_successive_flag_branches_preserve_replacement_record_and_limit(self):
        self.executes('''record Value { f: Integer }
function first(flag: Boolean,limit: Integer,obj: Value): Integer {
let result = 0; let replacement = Value { f: 42 }; let current = obj
if flag { limit = 100 }; if flag { current = replacement }
let count = 0; let i = 0; while i < 1000 { result = result + current.f; let j = 0; while j <= limit { count = count + 1; j = j + 1 }; i = i + 1 }; print(count); return result
}
function second(flag: Boolean,limit: Integer,obj: Value,array: List<Integer>): Integer {
let result = 0; let replacement = Value { f: 12 }; let current = obj
if flag { limit = 100 }; if flag { current = replacement }
let count = 0; let i = 0; while i < 1000 { result = result + current.f; let j = 0; while j <= limit { array[j] = j; count = count + 1; j = j + 1 }; i = i + 1 }; print(count); return result
}
let obj = Value { f: 42 }; let array: List<Integer> = []; let i = 0; while i < 101 { array.add(-1); i = i + 1 }
print(first(true,50,obj)); print(first(false,100,obj))
print(second(true,50,obj,array)); i = 0; while i < 101 { print(array[i]); array[i] = -1; i = i + 1 }
print(second(false,100,obj,array)); i = 0; while i < 101 { print(array[i]); i = i + 1 }
''','101000\n42000\n101000\n42000\n101000\n12000\n'+''.join(f'{i}\n' for i in range(101))+'101000\n42000\n'+''.join(f'{i}\n' for i in range(101)))

    def test_twenty_thousand_large_list_replacements_keep_every_cell_zero(self):
        self.executes('''function fresh(): List<Integer> { let value: List<Integer> = []; let i = 0; while i < 2047 { value.add(0); i = i + 1 }; return value }
let current: List<Integer> = []; let round = 0; let checked = 0; let failures = 0
while round < 20000 { current = fresh(); if current.length != 2047 { failures = failures + 1 }; let i = 0
while i < current.length { if current[i] != 0 { failures = failures + 1 }; checked = checked + 1; i = i + 1 }
current[0] = 99; current[2046] = -99; round = round + 1 }
print(round); print(checked); print(failures); print(current.length); print(current[0]); print(current[2046])
''','20000\n40940000\n0\n2047\n99\n-99\n')

    def test_reverse_decimal_carry_preserves_terminal_increment(self):
        self.executes('''function increment(digits: List<Integer>,position: List<Integer>): Boolean {
position[0] = position[0] - 1; let index = position[0]; digits[index] = digits[index] + 1; return digits[index] > 57
}
let digits = [49,57,57]; let position = [3]
while increment(digits,position) { digits[position[0]] = 48 }
print(digits[0]); print(digits[1]); print(digits[2]); print(position[0])
''','50\n48\n48\n0\n')

    def test_nested_singleton_rows_preserve_all_nonzero_loads(self):
        self.executes('''let rows = [[71],[71],[71]]; let i = 0
while i < 3 { print(rows[i][0]); print(rows[i][0] != 0); i = i + 1 }
''','71\ntrue\n'*3)

    def test_special_character_scan_keeps_ordered_short_circuit(self):
        self.executes('''function contains(value: Text,needle: Character,calls: List<Integer>): Boolean {
calls[0] = calls[0] + 1; let i = 0; while i < value.length { if value[i] == needle { return true }; i = i + 1 }; return false
}
function special(value: Text,calls: List<Integer>): Boolean { return contains(value,'*',calls) || contains(value,'V',calls) || contains(value,'S',calls) || contains(value,'n',calls) }
let calls = [0]; print(special("ee",calls)); print(calls[0]); calls[0] = 0
print(special("*e",calls)); print(calls[0]); calls[0] = 0
print(special("V",calls)); print(calls[0]); calls[0] = 0
print(special("S",calls)); print(calls[0]); calls[0] = 0
print(special("n",calls)); print(calls[0])
''','false\n4\ntrue\n1\ntrue\n2\ntrue\n3\ntrue\n4\n')

    def test_record_cell_alias_update_does_not_change_independent_record(self):
        self.executes('''record Fields { x1: Integer,x2: Integer,x3: List<Integer> }
function update(x: Integer,y: Integer,z: Integer) {
let a = Fields { x1: x,x2: y,x3: [z] }; let b = Fields { x1: x,x2: y,x3: [z] }; let c = b
let cell = c.x3; cell[0] = cell[0] + (a.x2-a.x1)*c.x2
print(a.x1); print(a.x2); print(a.x3[0]); print(c.x3[0]); print(b.x3[0])
}
update(1,2,3)
''','1\n2\n3\n5\n5\n')

    def test_repeated_divisions_keep_intervening_call_and_toggled_branches(self):
        self.executes('''function empty() {}
function common(x: Integer,y: Integer): Integer { let result = x / y; empty(); return result + x / y }
function toggle(x: Integer,y: Integer,b: Boolean,start: Integer,limit: Integer,step: Integer): Integer {
let result = 0; let i = start
while i < limit { if b { empty(); result = result + x/y } else { result = result - x/y }; print(i); print(result); b = !b; i = i * step }
return result
}
print(common(1,1)); print(toggle(1,1,true,1,4,2)); print(toggle(1,1,false,1,4,2))
''','2\n1\n1\n2\n0\n0\n1\n-1\n2\n0\n0\n')

    def test_descending_division_guard_keeps_full_and_early_exit_domains(self):
        self.executes('''function helper(stop: Integer,result: Integer,early: Boolean,flag: Boolean,stats: List<Integer>): Integer {
let i = stop; let active = true
while i >= 1 && active { result = result / i; stats[0] = stats[0] + 1; stats[1] = stats[1] + i
if early { active = false } else { early = flag; i = i - 1 } }
return result
}
function wrapper(stop: Integer,result: Integer,early: Boolean,stats: List<Integer>): Integer { if stop < 1 { stop = 1 }; return helper(stop,result,early,true,stats) }
let stats = [0,0]; let round = 0; let failures = 0
while round < 20000 { if wrapper(1000,0,false,stats) != 0 { failures = failures + 1 }; if helper(1000,0,false,false,stats) != 0 { failures = failures + 1 }; round = round + 1 }
print(wrapper(1,0,false,stats)); print(failures); print(round); print(stats[0]); print(stats[1])
''','0\n0\n20000\n20040001\n10049980001\n')

    def test_copied_scalar_and_record_lists_survive_delayed_loop_increment(self):
        source='''record Value { f: Integer }
function step(j: Integer): Integer { if j == 10 { return 10 }; return 1 }
function scalar(a: List<Integer>,start: Integer,stop: Integer,flag: Boolean): Integer {
let b = [a[0],a[1]]; let value = 1; let j = 0; while j < 10 { j = j + 1 }; let increment = step(j)
let i = start; while i < stop { value = value * 2; i = i + increment }; if flag { value = value + b[0] + b[1] }; return value
}
function object(a: List<Value>,start: Integer,stop: Integer,flag: Boolean): Integer {
let b = [a[0],a[1]]; let value = 1; let j = 0; while j < 10 { j = j + 1 }; let increment = step(j)
let i = start; while i < stop { value = value * 2; i = i + increment }; if flag { value = value + b[0].f + b[1].f }; return value
}
let integers = [0,0]; let records = [Value { f: 0 },Value { f: 0 }]
print(scalar(integers,0,10,false)); print(step(42)); print(object(records,0,10,false))
print(integers[0]); print(integers[1]); print(records[0].f); print(records[1].f)
print(scalar([7,11],0,10,true)); print(object([Value { f: 7 },Value { f: 11 }],0,10,true)); print(step(10))
'''
        self.executes(source,'2\n1\n2\n0\n0\n0\n0\n20\n20\n10\n')

    def test_primitive_boolean_text_arithmetic_rejects_all_reviewed_orders(self):
        pairs=[('true','true'),('"1"','"1"'),('"x"','"1"'),('"1"','"x"'),('true','1'),('1','true'),('true','"1"'),('"1"','true')]
        expressions=['true + 1','1 + true','true + "1"','"1" + true']
        for operator in ('/','*','%'):
            expressions.extend(f'{left} {operator} {right}' for left,right in pairs)
            if operator != '/':
                expressions.extend(f'{left} {operator} {right}' for left,right in [('"1"','1'),('1','"1"'),('"x"','1'),('1','"x"')])
        self.assertEqual(len(expressions),36)
        for expression in expressions:
            with self.subTest(expression=expression):
                self.rejects(f'print({expression})\n','Minyar stopped:')

    def test_unreachable_expression_and_loop_names_still_require_binding(self):
        sources=['print(false && absent)','print(true || absent)',
                 'let x = 0; while x != 1 { x = 1; abaracadabara }',
                 'let x = 0; while false { x = 1; abaracadabara }']
        for source in sources:
            with self.subTest(source=source):self.rejects(source+'\n','Minyar stopped:')
        self.executes('let absent = true; print(false && absent); print(true || absent)\nlet x = 0; while false { x = 1 }; print(x)\n','false\ntrue\n0\n')

    def test_if_and_while_conditions_require_boolean_even_for_known_values(self):
        sources=[]
        for condition in ('0','""','!(1)','!("1")','!("A")'):
            for tail in ('',' else { print(2) }'):
                sources.append(f'if {condition} {{ print(1) }}{tail}')
        for condition in ('0','""'):
            sources.append(f'let sentinel = 0; while {condition} {{ sentinel = 1 }}; print(sentinel)')
        sources += ['function condition(): Integer { return 0 }; if condition() { print(1) } else { print(2) }',
                    'function condition(): Integer { return 1 }; while condition() {}']
        for source in sources:
            with self.subTest(source=source):self.rejects(source+'\n','Minyar stopped:')
        self.executes('if false {} else { print(2) }; if !true {}\nlet sentinel = 0; while false { sentinel = 1 }; print(sentinel)\n','2\n0\n')

    def test_unary_text_minus_requires_explicit_integer_conversion(self):
        for text in ('""','"1"','"x"'):
            with self.subTest(text=text):self.rejects(f'print(-{text})\n','Minyar stopped:')

    def test_if_while_missing_blocks_and_block_conditions_are_rejected(self):
        for source in ('if true;','if false;','if(1);','while ({1}) {}',
                       'while false function f() {}','while false let x = 1'):
            with self.subTest(source=source):self.rejects(source+'\n','Minyar stopped:')
        self.executes('if true {}; if false {}\nwhile false {}; print("ready")\n','ready\n')

    def test_declarations_require_if_and_else_body_braces(self):
        declarations=['function f() {}','let x = 1']
        sources=[]
        for declaration in declarations:
            other='function g() {}' if declaration.startswith('function') else 'let y = 2'
            sources.extend([f'if true {declaration} else {other}',f'if true {declaration} else {{}}',f'if true {declaration}',f'if false {{}} else {declaration}'])
        for source in sources:
            with self.subTest(source=source):self.rejects(source+'\n','Minyar stopped:')
        self.executes('''function f(): Integer { return 1 }
function g(): Integer { return 2 }
if true { print(f()) } else { print(g()) }
if false { print(f()) } else { print(g()) }
if true { let x = 1; print(x) } else { let y = 2; print(y) }
if false {} else { let x = 1; print(x) }
''','1\n2\n1\n1\n')

    def test_checked_constant_bindings_negations_and_zero_products_keep_traps(self):
        maximum=9223372036854775807
        definitions=['function negate(x: Integer): Integer { return - - - - -x }',
                     'function cancel(x: Integer): Integer { return x + 1 - x }',
                     'function left(x: Integer,m: Integer): Integer { return x * (0 * (m + 1)) }',
                     'function right(x: Integer,m: Integer): Integer { return ((m + 1) * 0) * x }']
        bodies=[f'let value = {maximum} + 1; print(value)',
                'print(- - - - -(-9223372036854775808))','print(negate(-9223372036854775808))',
                f'print({maximum} + 1 - {maximum})',f'print(cancel({maximum}))',
                f'if ({maximum} + 1) != 0 {{ print(1) }} else {{ print(0) }}']
        for x in (0,7):
            bodies += [f'print({x} * (0 * ({maximum} + 1)))',f'print((({maximum} + 1) * 0) * {x})',f'print(left({x},{maximum}))',f'print(right({x},{maximum}))']
        self._execute_fatal_branches(definitions,[(f'case{n}','print("before"); '+body+'; print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n') for n,body in enumerate(bodies)])

    def test_addition_minimum_boundary_preserves_safe_and_failing_neighbor(self):
        definitions=['function sum(value: Integer): Integer { return value + (-9223372036854775808 + 5) }']
        self.executes('\n'.join(definitions+['print(sum(-5))','print(-5 + (-9223372036854775808 + 5))']),'-9223372036854775808\n'*2)
        self._execute_fatal_branches(definitions,[(mode,f'print("before"); print({expression})','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n') for mode,expression in [('helper','sum(-6)'),('literal','-6 + (-9223372036854775808 + 5)')]])

    def test_checked_comparison_offsets_and_product_quotient_keep_each_boundary(self):
        definitions=['function less(i: Integer): Boolean { return i - 5 < 10 }',
                     'function scaled(i: Integer): Integer { return (i * 100) / 10 }',
                     'function compare(i: Integer,j: Integer): Boolean { return i + 100 < j + 1234 }',
                     'function later(j: Integer): Integer { print("right"); return j + 1234 }',
                     'function ordered(i: Integer,j: Integer): Boolean { return i + 100 < later(j) }']
        source=definitions+['print(less(-9223372036854775803))','print(less(14))','print(less(15))','print(scaled(92233720368547758))','print(compare(0,0))','print(compare(1134,0))','print(compare(9223372036854775707,9223372036854774573))']
        self.executes('\n'.join(source),'true\ntrue\nfalse\n922337203685477580\ntrue\nfalse\nfalse\n')
        expressions=['less(-9223372036854775804)','(-9223372036854775804 - 5) < 10','scaled(92233720368547759)','(92233720368547759 * 100) / 10','compare(9223372036854775708,0)','compare(0,9223372036854774574)','9223372036854775708 + 100 < 0 + 1234','0 + 100 < 9223372036854774574 + 1234','ordered(9223372036854775708,9223372036854774574)','ordered(0,9223372036854774574)']
        self._execute_fatal_branches(definitions,[(f'case{n}',f'print("before"); print({expression}); print("after")','before\n'+('right\n' if n==9 else ''),'Minyar stopped: this Integer calculation is outside the supported range.\n') for n,expression in enumerate(expressions)])

    def test_checked_loop_bound_update_and_repeated_doubling_cannot_wrap(self):
        definition='''function count(start: Integer): Integer { let index = start; let result = 0
while index <= start + 4 { result = result + 1; print(index); index = index + 2 }; return result }
'''
        self.executes(definition+'print(count(0))\n','0\n2\n4\n3\n')
        cases=[]
        for value,prefix in [(9223372036854775804,''),(9223372036854775802,'9223372036854775802\n9223372036854775804\n9223372036854775806\n')]:
            cases.append((f'bound{value}',f'print(count({value})); print("after")',prefix,'Minyar stopped: this Integer calculation is outside the supported range.\n'))
        doubling='let i = 1; let bits = 1; while i > 0 { bits = bits + 1; print(i); print(bits); i = i + i }; print("after")'
        expected=''.join(f'{1<<n}\n{n+2}\n' for n in range(63))
        cases.append(('doubling',doubling,expected,'Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self._execute_fatal_branches([definition],cases)

    def test_invalid_encoding_bytes_reject_in_literals_comments_and_bom_sources(self):
        from regressions import COMPILER, COMPILE_TIMEOUT
        windows=bytes.fromhex('80 20 82 83 84 85 86 87 88 89 20 8a 20 8b 20 8c 20 8e')
        sources=[b"print('\xe9')\n",b'print("\xe9")\n',b'let \x82x = 1\n',
                 b'//\x80\nprint(42)\n',b'// '+windows+b'\nprint(42)\n',
                 b'/*\x80*/\nprint(42)\n',b'/*'+windows+b'*/\nprint(42)\n',
                 b'/*\n\x80\n*/\nprint(42)\n',b'// abcd\n// \x80abcd\nprint(42)\n',
                 b'\xff\xfe'+'print(42)\n'.encode('utf-16-le'),b'\xfe\xff'+'print(42)\n'.encode('utf-16-be')]
        self.assertEqual(len(sources),11)
        for index,source in enumerate(sources):
            with self.subTest(index=index):
                path=self.directory/f'invalidencoding{index}.min';llvm=path.with_suffix('.ll');path.write_bytes(source)
                run=self.evidence.run([COMPILER,path,llvm],timeout=COMPILE_TIMEOUT,phase='compile-invalid-encoding')
                self.assertEqual((run.returncode,run.stdout,run.stderr),(1,b'',b'Minyar stopped: Text contained invalid UTF-8.\n'))
                self.assertFalse(llvm.exists())

    def test_unknown_complete_escapes_preserve_current_literal_fallback(self):
        escapes=['q','u123z','x','U','U123','U12345','u123','xyzzy','777','U','z','m']
        source='\n'.join('print("\\'+escape+'")' for escape in escapes)
        source+='\nprint("abc \\m def")\nprint("null\\'+chr(0)+'character")\n'
        source+="print('\\"+chr(0)+"')\nprint('\\m')\n"
        self.executes(source,'\n'.join(escapes)+'\nabc m def\nnull'+chr(0)+'character\n'+chr(0)+'\nm\n')

    def test_literal_escape_eof_and_incomplete_initializer_fail_at_token_start(self):
        cases=[("print('"+chr(92),'Character literal has an unfinished escape'),
               ('print("\\','Text literal is missing its closing quote')]
        for source,message in cases:
            with self.subTest(source=source):
                run,llvm=self.compile(source)
                self.assertEqual((run.returncode,run.stdout,run.stderr),(1,'',f'Minyar stopped: line 1, column 7: {message}\n'))
                self.assertFalse(llvm.exists())
        self.rejects('let c = \\', 'line 1, column 9:')
        self.rejects('<<<<','line 1, column 1:')

    def test_comment_delimiter_overlap_and_final_newline_equivalence(self):
        self.executes('let value = /*/ */ 1\nprint(value)','1\n')
        self.executes('let value = /*/ */ 1\nprint(value)\n','1\n')
        self.rejects('let value = /*/', 'block comment is missing its closing */')
        self.rejects('print(42)\x1a\nI am random garbage after control Z','Minyar stopped:')

    def test_unicode_comment_lengths_and_adjacent_comments_preserve_next_token(self):
        glyphs='§ § § 😀 你好 ©'
        source=[f'//{glyphs}\nprint(1)',f'/*{glyphs}*/\nprint(2)',f'/*\n{glyphs}©©\n*/\nprint(3)',f'/* {glyphs} */\nprint(4)']
        source += ['/*\n'+('-'*52)+'\n'+('α'*22)+' // unicode\n'+('-'*52)+'\n'+('-'*52)+'\n*/\nprint(5)',
                   'let value = 6 /* 01234567890ABCDEF*/\n/*'+('α'*9)+'*/\nprint(value)']
        sizes=[0,1,7,15,16,17,31,32,33,63,64,65,127,128,129,1023,1024]
        for n,size in enumerate(sizes):source.append('/*'+('α😀中'*size)+'*/print('+str(n+7)+')')
        self.executes('\n'.join(source),'\n'.join(map(str,range(1,24)))+'\n')

    def test_merge_marker_families_reject_at_first_marker_column(self):
        sources=['<<<<<<< .mine\nlet x = 4\n|||||||\nlet x = 123\n=======\nlet x = 17\n>>>>>>> .r91107\n',
                 '<<<<<<< .mine\nlet y = 1\n=======\nlet y = 2\n>>>>>>> .r91107\n',
                 '>>>> ORIGINAL conflict-marker.c#6\nlet z = 1\n==== THEIRS conflict-marker.c#7\nlet z = 0\n==== YOURS conflict-marker.c\nlet z = 2\n<<<<\n',
                 '<<<<<<<>>>>>>>']
        for source in sources:
            with self.subTest(source=source):self.rejects(source,'line 1, column 1:')

    def test_comment_token_boundaries_and_star_runs_preserve_live_statements(self):
        self.executes('''/* fail("commented");
*/
let x = 0
/* x = 1; */
print(x)
let /* y = 1; */ y = 7
print(y)
let /* y = 1; */ z = 8
print(z)
/* let x = 1;
if x == 1 { fail("commented") }
*/
let first = "/*var y = 0*/" /* y = 1; */
let second = "/*var y = 0" /* y = 1; */
print(first); print(second)
/** fail("commented");
*/
/* fail("commented");
**/
/****** fail("commented");*********
***********
*


**********
**/
print("ready")
''','0\n7\n8\n/*var y = 0*/\n/*var y = 0\nready\n')
        self.rejects('let /* y = 1; */\ny = 7\n','expected a name after let')
        self.rejects('let x = 0\n/* var */\nx*/\n','line 3, column 3:')
        self.rejects('let x = 0\n// var /*\nx*/\n','line 3, column 3:')

    def test_escaped_whitespace_tokens_are_not_decoded_outside_literals(self):
        for code in ('000A','000D','2028','2029','0009','000B','000C','0020','00A0'):
            with self.subTest(code=code):self.rejects('let\\u'+code+'x = 1\n','line 1, column 4:')

    def test_mongolian_vowel_separator_is_comment_text_not_token_whitespace(self):
        source='let\u180efoo = 1\n'
        run,llvm=self.compile(source)
        expected="Minyar stopped: line 1, column 4: names must use ASCII letters, digits, and '_'; found non-ASCII character '\u180e'\n"
        self.assertEqual((run.returncode,run.stdout,run.stderr),(1,'',expected));self.assertFalse(llvm.exists())
        self.executes('// \u180e\nlet /* \u180e */ foo = 1\nprint(foo)\n','1\n')

    def test_operator_continuations_keep_exact_operands_and_statement_boundaries(self):
        def rejects_boundary(source, line, column, message):
            run, llvm = self.compile(source)
            self.assertEqual((run.returncode, run.stdout, run.stderr),
                             (1, '', f'Minyar stopped: line {line}, column {column}: {message}\n'))
            self.assertFalse(llvm.exists())

        vectors=[('+',2,3,'5'),('-',3,2,'1'),('*',3,2,'6'),('/',12,2,'6'),('%',16,10,'6'),('<',2,3,'true')]
        source=[];expected=[]
        for index,(operator,left,right,result) in enumerate(vectors):
            source += [f'let y{index} = {left}; let z{index} = {right}',f'let x{index} =\ny{index} {operator}\nz{index}\nprint(x{index})',f'print(y{index} {operator}\nz{index})']
            expected += [result,result]
            # The rejected boundary is the LF after 'let' (column4) or
            # after 'print(y' (column8), independently of the next operator.
            rejects_boundary(f'let y = {left}; let z = {right}\nlet\nx\n=\ny\n{operator}\nz\n',
                             2, 4, 'expected a name after let')
            rejects_boundary(f'let y = {left}; let z = {right}\nprint(y\n{operator}\nz)\n',
                             2, 8, "expected an expression, found 'end of line'")
        source += ['let last =\n1\nprint(last)'];expected += ['1']
        rejects_boundary('let\nx\n=\n1\nprint(x)\n', 1, 4, 'expected a name after let')
        self.executes('\n'.join(source),'\n'.join(expected)+'\n')

    def test_multiline_multiplicative_chains_keep_left_association(self):
        source=[];expected=[]
        for index,(operator,middle,last,result) in enumerate([('/',2,9,1),('*',2,9,324),('%',7,3,1)]):
            self.rejects(f'let x = 18\n\n{operator}\n\n{middle}\n\n{operator}\n\n{last}\n;\nprint(x)\n','Minyar stopped:')
            source += [f'let x{index} = 18 {operator}\n\n{middle} {operator}\n\n{last}\nprint(x{index})'];expected.append(str(result))
        self.executes('\n'.join(source),'\n'.join(expected)+'\n')

    def test_cell_compound_update_preserves_rhs_subtraction_grouping(self):
        self.executes('''function update(a: List<Integer>,b: List<Integer>): Boolean { a[0] = a[0] + (b[0] - 8); return a[0] >= 8 }
let x = [0]; let y = [10]; print(update(x,y)); print(x[0]); print(y[0])
let same = [10]; print(update(same,same)); print(same[0])
''','false\n2\n10\ntrue\n12\n')

    def test_alternating_inner_counter_and_single_posttest_keep_exit_state(self):
        self.executes('''function alternating(limit: Integer,inner: Integer,flag: List<Integer>): Integer {
let count = 0
while limit > count { if flag[0] % 2 == 1 { let i = 0; while i < inner { count = count + 1; i = i + 1 } }; flag[0] = flag[0] + 1 }
print(count); return 1
}
let flag = [0]; print(alternating(100,7,flag)); print(flag[0])
let b = 0; let i = -1; let result = -1; let active = true
while active { if b != 0 { fail("unexpected branch") } else { result = 0 }; i = i + 1; b = (i + 2) * 4; active = i < 0 }
print(result); print(i); print(b)
''','105\n1\n30\n0\n0\n8\n')

    def test_complementary_conditions_skip_terminal_boolean_helper(self):
        self.executes('''function terminal(): Boolean { fail("unreachable") }
function check(winds: Integer): Boolean { while winds != 0 { if terminal() { return false } }; return winds == 0 || winds != 0 || terminal() }
print(check(0))
function complementary(winds: Integer): Boolean { return winds == 0 || winds != 0 || terminal() }
print(complementary(1)); print(complementary(-1))
''','true\ntrue\ntrue\n')

    def test_boolean_selected_wide_constant_keeps_high_word(self):
        self.executes('''function value(flag: Boolean): Integer { if flag { return 17179869184 }; return 0 }
let flags = [true,false]; print(value(flags[0])); print(value(flags[1]))
''','17179869184\n0\n')

    def test_two_nested_text_identity_calls_preserve_argument_positions(self):
        self.executes('''function identity(value: Text): Text { return value }
function receive(first: Text,second: Text) { print(first); print(second) }
function forward(name: Text,value: Text) { receive(identity(name),identity(value)) }
forward("arg0","arg1")
''','arg0\narg1\n')

    def test_wide_division_and_subtracted_window_keep_checked_intermediate(self):
        definitions=['function divide(a: Integer,b: Integer): Integer { return a/b }',
                     'function direct(a: Integer,window: Integer,b: Integer): Boolean { return ((a+window)-b)>0 }',
                     'function assigned(a: Integer,window: Integer,b: Integer): Boolean { let result = (a+window)-b; return result>0 }']
        self.executes('\n'.join(definitions+['let a = 85899345920; let b = 2147483648; print(a/b); print(divide(a,b)); print(85899345920/2147483648)','print(direct(2147479553,4096,2147479553)); print(assigned(2147479553,4096,2147479553)); print((2147479553+4096)-2147479553)']), '40\n40\n40\ntrue\ntrue\n4096\n')
        self._execute_fatal_branches(definitions,[(name,f'print("before"); print({name}(9223372036854771713,4096,9223372036854771713)); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n') for name in ('direct','assigned')])

    def test_unmerged_backedge_inputs_skip_dead_states_and_keep_posttest_counts(self):
        definitions=[]
        for variant in range(1,5):
            dead=('let state = 0; while true { if state == 0 { if d == 0 { state = 1 } else { state = 1 } } else { state = 0 } }' if variant==1 else
                  'let counter = 0; while true { if d != counter { counter = counter + 1'+('; if counter != 10001 { counter = counter + 1 }' if variant==4 else '')+' } }')
            if variant<3:
                body=f'if a <= 0 {{ {dead} }}; while b < 0 || c < 0 {{}}; print("returned{variant}")'
                definitions.append(f'function shape{variant}(a: Integer,b: Integer,c: Integer,d: Integer,e: Integer) {{ {body} }}')
            else:
                body=f'''if a <= 0 {{ {dead} }}
let descending = 0; let ascending = 0; let divisible = 0; let boundChecks = 0; let active = true
while active {{ ascending = ascending + 1; descending = descending - 1
if ascending % 7 == 0 {{ divisible = divisible + 1 }} else {{ boundChecks = boundChecks + 1; active = ascending <= 10001 }} }}
print(ascending); print(divisible); print(boundChecks); return descending'''
                definitions.append(f'function shape{variant}(a: Integer,b: Integer,c: Integer,d: Integer,e: Integer): Integer {{ {body} }}')
        calls=['shape1(1,0,0,0,0)','shape2(1,0,0,0,0)','print(shape3(1,0,0,0,0))','print(shape4(1,0,0,0,0))']
        self.executes('\n'.join(definitions+calls),'returned1\nreturned2\n'+'10002\n1428\n8574\n-10002\n'*2)

    def test_line_and_block_comment_delimiters_do_not_nest_or_hide_following_tokens(self):
        comments=['/* var\n*///x*/\n','/* var\n//x\n*/\n','// var /* x / = */ 1 */\n','// var /*\n// x\n// =\n// 1*/\n']
        self.executes('\n'.join(comment+f'print({n})' for n,comment in enumerate(comments)), '0\n1\n2\n3\n')
        self.rejects('/*\nlet\n\n/* x */\n= 1;\n*/\n','line 5, column 1:')
        self.rejects('// single line comment\n ??? (invalid)\n','line 2, column 2:')
        self.rejects('//single\nline comment\n','line 2, column 1:')

    def test_control_scalars_remain_inert_inside_comments_with_live_sentinels(self):
        source=[];expected=[]
        for scalar in ('\x0b','\x0c','\u00a0'):
            for opening,closing,words in [('//','\n','single'),('/*','*/\n','multi')]:
                for suffix in ('',' x = 1;'):
                    source += ['let x = 0',opening+scalar+' '+words+' line '+scalar+' comment '+scalar+suffix+closing,'print(x)']
                    expected += ['0']
                source += ['let x = 0',opening+scalar+words+scalar+'line'+scalar+'comment'+scalar+'x = 1;'+closing,'print(x)'];expected += ['0']
        for scalar in ('\n','\u2028','\u2029'):
            source += ['let x = 0','/*'+scalar+'x = 1;'+scalar+'*/','print(x); print("sentinel")'];expected += ['0','sentinel']
        source += ['let x = 0','/*\nmulti\rline\rcomment\rx = 1;\n*/','print(x)'];expected += ['0']
        for suffix in ('',' x = 1;'):
            source += ['let x = 0','/*\u2029 multi line \u2029 comment \u2029'+suffix+'*/','print(x)'];expected += ['0']
        source += ['print(0 == /*\u180e multi-line comment */ 0)','print(0 == //\u180e single-line comment\n0)'];expected += ['true','true']
        # Independent lexical blocks avoid illegal repeated bindings in one scope.
        self.executes('\n'.join('if true {\n'+part+'\n}' for part in self._comment_program_sections(source)), '\n'.join(expected)+'\n')

    @staticmethod
    def _comment_program_sections(lines):
        sections=[];current=[]
        for line in lines:
            if line=='let x = 0' and current:
                sections.append('\n'.join(current));current=[]
            current.append(line)
        if current:sections.append('\n'.join(current))
        return sections

    def test_control_and_line_separator_text_preserves_all_characters_and_lengths(self):
        source=[];expected=[]
        for n,scalar in enumerate(('\x0b','\x0c','\u00a0','\u2028','\u2029')):
            value=scalar+'str'+scalar+'ing'+scalar if n<3 else '66'+scalar+'123'
            source += [f'let text{n} = "{value}"',f'print(text{n})',f'print(text{n}.length)']
            expected += [value,str(len(value))]
            for index,character in enumerate(value):source.append(f'print(text{n}[{index}])');expected.append(character)
        self.executes('\n'.join(source),'\n'.join(expected)+'\n')

    def test_line_break_inside_block_comment_does_not_separate_statements(self):
        for scalar,location in [('\r','line 1, column 14'),('\n','line 2, column 3')]:
            with self.subTest(scalar=scalar):
                run,llvm=self.compile('print(1)/*'+scalar+'*/print(2)')
                self.assertEqual((run.returncode,run.stdout,run.stderr),(1,'',f"Minyar stopped: {location}: unexpected 'print'; start the next statement on a new line\n"));self.assertFalse(llvm.exists())
                self.executes('print(1);/*'+scalar+'*/print(2)\n','1\n2\n')

    def test_terminal_left_operand_suppresses_right_for_all_reviewed_operators(self):
        definitions=['function left(): Integer { print("left"); fail("left failure") }','function right(): Integer { print("right"); fail("right failure") }',
                     'function leftBoolean(): Boolean { print("left"); fail("left failure") }','function rightBoolean(): Boolean { print("right"); fail("right failure") }']
        cases=[]
        for n,operator in enumerate(('+','-','*','/','%','==','&&','||')):
            lhs,rhs=('leftBoolean()','rightBoolean()') if operator in ('&&','||') else ('left()','right()')
            cases.append((f'operator{n}',f'print({lhs} {operator} {rhs}); print("after")','left\n','Minyar stopped: left failure\n'))
        self._execute_fatal_branches(definitions,cases)

    def test_exact_malformed_radix_and_identifier_suffix_spellings_reject(self):
        tokens=['0x','0X','0xG','0xg','0b2','00b0','0b','0\\u00620','3in []','0o8','00o0','0o','0\\u006f0']
        self.assertEqual(len(tokens),13)
        for token in tokens:
            with self.subTest(token=token):self.rejects(token+'\n','Minyar stopped:')

    def test_equality_continuation_distinguishes_lf_cr_and_crlf(self):
        self.executes('print(1 ==\n1)\nprint(1\r==\r1)\n','true\ntrue\n')
        # Parentheses now permit line breaks before the operator too.
        self.executes('print(1\n==\n1)\nprint(1\r\n==\r\n1)\n','true\ntrue\n')
        self.rejects('let value = 1\n==\n1\n','Minyar stopped:')
        self.rejects('let value = 1\r\n==\r\n1\n','Minyar stopped:')

    def test_independent_record_fields_feed_addition_and_subtraction(self):
        self.executes('''record Value { prop: Integer }
let first = Value { prop: 1 }; let second = Value { prop: 1 }
print(first.prop + second.prop); print(first.prop - second.prop)
''','2\n0\n')

    def test_addition_parentheses_preserve_maximum_intermediate_trap(self):
        definitions=['function left(x: Integer): Integer { return -x + x + x }',
                     'function grouped(x: Integer): Integer { return (-x + x) + x }',
                     'function right(x: Integer): Integer { return -x + (x + x) }']
        maximum=9223372036854775807
        self.executes('\n'.join(definitions+[f'print(left({maximum}))',f'print(grouped({maximum}))',f'print(-{maximum} + {maximum} + {maximum})',f'print((-{maximum} + {maximum}) + {maximum})']),f'{maximum}\n'*4)
        self._execute_fatal_branches(definitions,[(mode,f'print("before"); print({expression}); print("after")','before\n','Minyar stopped: this Integer calculation is outside the supported range.\n') for mode,expression in [('helper',f'right({maximum})'),('literal',f'-{maximum} + ({maximum} + {maximum})')]])

    def test_arithmetic_missing_names_and_boolean_negation_reject_statically(self):
        for operator in ('/','*','%'):
            for expression in (f'x {operator} 1',f'1 {operator} y'):
                with self.subTest(expression=expression):self.rejects('print('+expression+')\n','Minyar stopped:')
        self.rejects('print(-x)\n','Minyar stopped:')
        self.rejects('print(-false)\n','Minyar stopped:')

    def test_multiplication_remainder_reference_shapes_and_adjacent_division(self):
        self.executes('''record Value { prop: Integer }
print(1*1); let x = 1; print(x*1); let y = 1; print(1*y); print(x*y)
let first = Value { prop: 1 }; let second = Value { prop: 1 }; print(first.prop*second.prop)
print(1%2); let numerator = 1; print(numerator%2); let divisor = 2; print(1%divisor); print(numerator%divisor)
let third = Value { prop: 2 }; print(first.prop%third.prop); print(1%1)
let instance = 60; let of = 6; let g = 2; let notRegExp = instance/of/g; print(notRegExp)
print(-(1))
''','1\n'*10+'0\n5\n-1\n')

    def test_zero_divisor_literals_and_bigint_sized_numerators_stop_exactly(self):
        definitions=['function divide(a: Integer,b: Integer): Integer { return a/b }','function remainder(a: Integer,b: Integer): Integer { return a%b }']
        cases=[]
        for left,right in [('0','0'),('-0','0'),('0','-0'),('-0','-0')]:
            cases.append((f'zero{len(cases)}',f'print("before"); print({left}/{right}); print("after")','before\n','Minyar stopped: an Integer cannot be divided by zero.\n'))
        for operator,helper in [('/','divide'),('%','remainder')]:
            for value in (1,10,0,1000000000000000000):
                for expression in (f'{value}{operator}0',f'{helper}({value},0)'):
                    cases.append((f'big{len(cases)}',f'print("before"); print({expression}); print("after")','before\n','Minyar stopped: an Integer cannot be divided by zero.\n'))
        self._execute_fatal_branches(definitions,cases)

    def test_zero_quotients_remainders_and_negations_remain_invalid_reciprocals(self):
        definitions=['function divide(a: Integer,b: Integer): Integer { return a/b }','function remainder(a: Integer,b: Integer): Integer { return a%b }']
        cases=[]
        groups=[('/', 'divide',[('-0','1'),('-0','-1'),('0','1'),('0','-1')]),
                ('%','remainder',[('1','1'),('-1','-1'),('-1','1'),('1','-1'),('0','1'),('0','-1'),('-0','1'),('-0','-1')])]
        for operator,helper,pairs in groups:
            for left,right in pairs:
                for expression in (f'{left}{operator}{right}',f'{helper}({left},{right})'):
                    cases.append((f'case{len(cases)}',f'print({expression}); print(1/({expression})); print("after")','0\n','Minyar stopped: an Integer cannot be divided by zero.\n'))
        for value in ('0','-0'):
            cases.append((f'negation{len(cases)}',f'let x = {value}; x = -x; print(x); print(1/x); print("after")','0\n','Minyar stopped: an Integer cannot be divided by zero.\n'))
        self.assertEqual(len(cases),26)
        self._execute_fatal_branches(definitions,cases)

    def test_nested_if_branch_associations_keep_all_sixteen_source_paths(self):
        def body(mode,a,b,c):
            if mode==0:return f'if {a} {{ if {b} {{ result = 1 }} else {{ result = 2 }} }} else {{ if {c} {{ result = 3 }} else {{ result = 4 }} }}'
            if mode==1:return f'if {a} {{ if {b} {{ result = 1 }} }} else {{ if {c} {{ result = 3 }} }}'
            if mode==2:return f'if {a} {{ if {b} {{ result = 1 }} else {{ result = 2 }} }}'
            return f'if {a} {{ if {b} {{ result = 2 }} }}'
        source=[f'function mode{mode}(a: Boolean,b: Boolean,c: Boolean): Integer {{ let result = 0; {body(mode,"a","b","c")}; return result }}' for mode in range(4)]
        inputs=[('true','false','true'),('true','true','true'),('false','true','true'),('false','true','false')]
        results=[[2,1,3,4],[0,1,3,0],[2,1,0,0],[0,2,0,0]];expected=[]
        for mode in range(4):
            for (a,b,c),result in zip(inputs,results[mode]):
                source += [f'print(mode{mode}({a},{b},{c}))',f'if true {{ let result = 0; {body(mode,a,b,c)}; print(result) }}'];expected += [str(result)]*2
        self.executes('\n'.join(source),'\n'.join(expected)+'\n')

    def test_condition_and_statement_terminal_failures_preserve_execution_order(self):
        definitions=['function condition(): Boolean { print("condition"); fail("condition failure") }']
        cases=[('ifNoElse','if condition() { print("then") }; print("after")','condition\n','Minyar stopped: condition failure\n'),
               ('ifElse','if condition() { print("then") } else { print("else") }; print("after")','condition\n','Minyar stopped: condition failure\n'),
               ('while','while condition() { print("reached") }; print("after")','condition\n','Minyar stopped: condition failure\n'),
               ('posttest','print("reached"); while condition() {}; print("after")','reached\ncondition\n','Minyar stopped: condition failure\n'),
               ('then','if true { fail("instatement") }; print("after")','','Minyar stopped: instatement\n'),
               ('skipped','if false { fail("truebranch") }; fail("missbranch"); print("after")','','Minyar stopped: missbranch\n')]
        self._execute_fatal_branches(definitions,cases)

    def test_pretested_and_explicit_posttested_counters_keep_all_five_visits(self):
        self.executes('''let counter = 0; let visits = 0
while counter < 5 { counter = counter + 1; visits = visits + 1; print(counter) }
print(counter); print(visits)
let post = 0; let postVisits = 0; post = post + 1; postVisits = postVisits + 1; print(post)
while post < 5 { post = post + 1; postVisits = postVisits + 1; print(post) }
print(post); print(postVisits)
''','1\n2\n3\n4\n5\n5\n5\n'*2)

    def test_if_empty_and_block_valued_conditions_reject_before_execution(self):
        for source in ('if({1}) {} else {}','if() {}','if();'):
            with self.subTest(source=source):self.rejects(source+'\n','Minyar stopped:')

    def test_explicit_captured_cell_is_reloaded_for_each_loop_addition(self):
        self.executes('''record Capture { value: List<Integer> }
function add(capture: Capture): Integer { let sum = 0; let i = 0; while i < 3 { sum = capture.value[0] + sum; i = i + 1 }; return sum }
let cell = [0]; let capture = Capture { value: cell }; cell[0] = 3
print(add(capture)); print(add(capture)); print(add(capture)); print(add(capture)); cell[0] = 5; print(add(capture))
''','9\n9\n9\n9\n15\n')

    def test_integer_helper_products_aliases_and_identity_comparisons(self):
        self.executes('''function multiply(a: Integer,b: Integer): Integer { return a*b }
function distinct(x: Integer,y: Integer): Integer { return x+y }
function same(x: Integer,y: Integer): Integer { return x+x }
function assigned(x: Integer,y: Integer): Integer { x = y; return x+y }
function identity(x: Integer): Boolean { return 1*x == x+0 }
print(multiply(3,4)); print(multiply(5,6)); print(multiply(7,8)); print(multiply(7,8))
print(distinct(2,3)); print(same(2,3)); print(assigned(2,3))
print(identity(121)); print(identity(122)); print(identity(123))
''','12\n30\n56\n56\n5\n4\n6\ntrue\ntrue\ntrue\n')

    def test_fresh_list_constructor_and_alias_mutation_preserve_each_read(self):
        self.executes('''function build(): List<Integer> { return [1,2,3] }
function read(values: List<Integer>): Integer { return values[0] }
let result = build(); print(result[0]); print(result[1]); print(result[2]); result = build(); print(result[0]); print(result[1]); print(result[2])
let values = [1,2,3]; let alias = values; print(read(values)); print(read(values)); print(read(values)); alias[0] = 42; print(read(values)); print(values[1]); print(values[2])
''','1\n2\n3\n1\n2\n3\n1\n1\n1\n42\n2\n3\n')

    def test_explicit_list_predicate_searches_keep_match_absence_and_early_return(self):
        source='''record Target { x: Integer }
record Found { exists: Boolean,value: Integer }
function every(values: List<Integer>,target: Target,count: List<Integer>): Boolean { let i = 0; while i < values.length { count[0] = count[0] + 1; if values[i] != target.x { return false }; i = i + 1 }; return true }
function find(values: List<Integer>,target: Target,count: List<Integer>): Found { let i = 0; while i < values.length { count[0] = count[0] + 1; if values[i] == target.x { return Found { exists: true,value: values[i] } }; i = i + 1 }; return Found { exists: false,value: 0 } }
function index(values: List<Integer>,target: Target,count: List<Integer>): Integer { let i = 0; while i < values.length { count[0] = count[0] + 1; if values[i] == target.x { return i }; i = i + 1 }; return -1 }
function some(values: List<Integer>,target: Target,count: List<Integer>): Boolean { let i = 0; while i < values.length { count[0] = count[0] + 1; if values[i] == target.x { return true }; i = i + 1 }; return false }
let target = Target { x: 3 }; let count = [0]
'''
        expected=[]
        for method in ('every','find','index','some'):
            values=('[3,3,3]','[3,3,2]') if method=='every' else ('[1,2,3]','[0,1,2]')
            for n in range(4):
                source+=f'count[0] = 0\n'
                call=f'{method}({values[n%2]},target,count)'
                if method=='find':source+=f'let found{n} = {call}; print(found{n}.exists); print(found{n}.value)\n';expected += ['true','3'] if n%2==0 else ['false','0']
                else:source+=f'print({call})\n';expected += [str(2 if n%2==0 else -1) if method=='index' else ('true' if n%2==0 else 'false')]
                source+='print(count[0])\n';expected+=['3']
        source+='count[0] = 0; print(every([2,3,3],target,count)); print(count[0])\ncount[0] = 0; print(index([3,1,2],target,count)); print(count[0])\n'
        expected+=['false','1','0','1']
        self.executes(source,'\n'.join(expected)+'\n')

    def test_append_argument_side_effects_finish_before_callee_appends_results(self):
        self.executes('''function bar(values: List<Integer>,x: Integer): Integer { values.add(x); return x }
function both(values: List<Integer>,first: Integer,second: Integer) { values.add(first); values.add(second) }
function foo(values: List<Integer>,x: Integer) { both(values,bar(values,x),bar(values,x)) }
function next(values: List<Integer>,counter: List<Integer>): Integer { counter[0] = counter[0] + 1; values.add(counter[0]); return counter[0] }
let values: List<Integer> = []; foo(values,1); foo(values,2); foo(values,3)
print(values.length); let i = 0; while i < values.length { print(values[i]); i = i + 1 }
let ordered: List<Integer> = []; let counter = [0]; both(ordered,next(ordered,counter),next(ordered,counter)); i = 0; while i < ordered.length { print(ordered[i]); i = i + 1 }
''','12\n'+'1\n'*4+'2\n'*4+'3\n'*4+'1\n2\n1\n2\n')

    def test_false_conditional_values_preserve_surrounding_addition_grouping(self):
        self.executes('''function first(): Integer { let choice = 0; if 0 == 1 { choice = 1 } else { choice = 2 }; return 42 + choice }
function second(x: Integer): Integer { let choice = 0; if 0 == 1 { choice = 1 } else { choice = 2 }; return x + choice }
function third(x: Integer): Integer { let left = x + 1; let choice = 0; if 0 == 1 { choice = 1 } else { choice = 2 }; return left + choice }
print(first()); print(second(43)); print(third(44))
''','44\n45\n47\n')

    def test_repeated_dead_products_and_double_diamonds_keep_selected_values(self):
        self.executes('''function dead(a: Integer,b: Integer): Integer { if a == 2 { a*b } else { b*a }; return a }
function diamond(condition: Integer,first: Integer,second: Integer) { let selected = 0; if condition == 1 { selected = first } else { selected = second }; if condition == 1 { print(selected == first) } else { print(selected == second) }; print(selected) }
print(dead(35,12)); print(dead(35,12)); print(dead(35,12))
diamond(1,10,20); diamond(2,30,40); diamond(1,10,20); diamond(2,30,40)
''','35\n35\n35\n'+'true\n10\ntrue\n40\n'*2)

    def test_boolean_locals_survive_nested_checks_and_guarded_list_comparisons(self):
        self.executes('''function nested(a: Integer,b: Integer): Boolean { let passed = a == 3; if passed { if passed { passed = b == 4 } }; return passed }
function equal(expected: List<Integer>,actual: List<Integer>): Boolean {
let passed = expected.length == actual.length; let i = 0
while i < expected.length { if passed { passed = expected[i] == actual[i] }; i = i + 1 }
print("a"); print(passed); print("b"); print(passed); return passed
}
print(nested(3,4)); print(nested(3,4)); print(nested(3,4)); print(nested(3,4)); print(nested(2,4)); print(nested(3,5))
print(equal([0,1],[0,1])); print(equal([0,2],[0,2])); print(equal([0,1],[0,1])); print(equal([0,2],[0,2]))
print(equal([0,1],[0,2])); let empty: List<Integer> = []; print(equal([0,1],empty))
''','true\n'*4+'false\nfalse\n'+('a\ntrue\nb\ntrue\ntrue\n'*4)+('a\nfalse\nb\nfalse\nfalse\n'*2))

    def test_nested_calls_reload_replaced_record_and_both_mutated_cells(self):
        self.executes('''record Value { x: Integer,y: Integer }
function g(flag: Boolean,state: List<Value>) { if flag { state[0] = Value { x: 536,y: 0 } } }
function h(flag: Boolean,state: List<Value>): Integer { g(flag,state); return state[0].x }
function f(flag: Boolean,state: List<Value>): Integer { let middle = h(flag,state); print(middle); return state[0].x }
let original = Value { x: 0,y: 1 }; let state = [original]
print(f(false,state)); print(f(false,state)); print(f(false,state)); print(f(true,state)); print(original.x); print(original.y); print(state[0].y)
function set(value: Integer,x: List<Integer>,y: List<Integer>) { x[0] = value; y[0] = value }
function sum(value: Integer,x: List<Integer>,y: List<Integer>): Integer { set(value,x,y); return x[0]+y[0] }
let x = [1]; let y = [1]; let argument = 1; print(sum(argument,x,y)); print(sum(argument,x,y)); argument = 2; print(sum(argument,x,y)); print(x[0]); print(y[0])
''','0\n'*6+'536\n536\n0\n1\n0\n2\n2\n4\n2\n2\n')

    def test_first_positive_store_precedes_unreachable_negative_index_loop(self):
        definitions=['''function shape(values: List<Integer>) { let x = 8; let i = 0
while i < 8 { print("first store"); values[1] = 9; let j = -400
while 1 > j { print("inner"); values[j] = 4; x = x - 2; j = j + 1 }; i = i + 1 }; print(x)
}''']
        self._execute_fatal_branches(definitions,[(f'call{n}','let values: List<Integer> = []; shape(values); print("after")','first store\n','Minyar stopped: List position 1 is outside its length of 0.\n') for n in range(3)])

    def test_reassociated_invariants_keep_multiplicative_and_thousand_index_domains(self):
        source='''function first(a: Integer,b: Integer): Integer { let value = a+b; let i = 1
while i < 100 { value = value + (a+(b+i)); print(i); print(value); i = i*2 }; return value }
function longShape(a: Integer,b: Integer,bounds: List<Integer>) { let i = bounds[0]; while i < bounds[1] { let index = a+(b+i); print(index); print(index >= 0 && index < 9223372036854775807); i = i + 1 } }
function intShape(a: Integer,b: Integer,bounds: List<Integer>) { let i = bounds[0]; while i < bounds[1] { let index = a+(b+i); print(index); print(index >= 0 && index < 9223372036854775807); i = i + 1 } }
print(first(42,42)); let longBounds = [0,1000]; let intBounds = [0,1000]; longShape(42,42,longBounds); intShape(42,42,intBounds)
'''
        expected=[];value=84
        for i in (1,2,4,8,16,32,64):value+=84+i;expected += [str(i),str(value)]
        self.assertEqual(value,799);expected += ['799']
        expected += [item for _ in range(2) for i in range(1000) for item in (str(84+i),'true')]
        self.executes(source,'\n'.join(expected)+'\n')

    def test_nested_empty_loops_keep_conditional_helper_limits_observable(self):
        source='''function helper(i: Integer,flag: Boolean,values: List<Integer>,visits: List<Integer>): Integer {
let stop = 1000; if i == 2 { if flag { stop = 2 } else { stop = 1 } }
let result = 0; let j = 0; while j < stop { result = result + values[0]; visits[0] = visits[0] + 1; j = j + 1 }; return result
}
function test(flag: Boolean,values: List<Integer>,state: List<Integer>,visits: List<Integer>) {
let before = 0; let after = 0; let i = 0
while i < 2 { let j = 0; while j < 10 { let k = 0; while k < 10 { before = before + 1; k = k + 1 }; j = j + 1 }; i = i + 1 }
state[0] = helper(i,flag,values,visits)
let j = 0; while j < 10 { let k = 0; while k < 10 { let l = 0; while l < 10 { let m = 0; while m < 10 { after = after + 1; m = m + 1 }; l = l + 1 }; k = k + 1 }; j = j + 1 }
print(before); print(after); print(state[0]); print(visits[0])
}
let state = [-1]; let visits = [0]
'''
        expected=[]
        for n,value in enumerate([0,7]):
            source+=f'let values{n} = [{value}]; visits[0] = 0; test(true,values{n},state,visits); visits[0] = 0; test(false,values{n},state,visits); visits[0] = 0; print(helper(1000,false,values{n},visits)); print(visits[0]); print(state[0])\n'
            expected += [200,10000,2*value,2,200,10000,value,1,1000*value,1000,value]
        self.executes(source,''.join(f'{v}\n' for v in expected))

    def test_negative_offset_and_prefix_subtraction_keep_exact_list_bounds(self):
        self.executes('''function last(values: List<Integer>,offset: Integer): Integer { return values[207+offset] }
function subtract(value: Integer,values: List<Integer>,end: Integer): Integer { let i = 0; while i < end { value = value - values[i]; print(value); i = i + 1 }; return value }
let words: List<Integer> = []; let i = 0; while i < 207 { words.add(i); i = i + 1 }; print(last(words,-1)); print(words.length)
let values = [1,4,16,64,256]; print(subtract(512,values,3)); print(values[3]); print(values[4])
''','206\n207\n511\n507\n491\n491\n64\n256\n')

    def test_recursive_frames_keep_distinct_parent_cells_alive(self):
        self.executes('''function descend(a: Integer,parent: List<Integer>): Integer { let local = [a]; if a == 0 { return parent[0] }; let result = descend(a-1,local); if local[0] != a { return -1000 }; return result }
let sentinel = [-777]; print(descend(100,sentinel)); print(sentinel[0]); print(descend(0,sentinel)); print(descend(1,sentinel))
''','1\n-777\n-777\n1\n')

    def test_single_record_list_and_forwarded_field_comparison_preserve_arguments(self):
        self.executes('''record Node { node: Integer,kind: Integer }
record Triple { a: Integer,b: Integer,c: Integer }
function brother(equal: Boolean,b: Integer,c: Integer) { print(equal); print(b); print(c) }
function sister(value: Triple,b: Integer,c: Integer) { brother(value.b == b,b,c); print(value.a); print(value.b); print(value.c) }
let nodes = [Node { node: 0,kind: 1 }]; print(nodes[0].node); print(nodes[0].kind); print(nodes.length)
sister(Triple { a: 7,b: 8,c: 9 },1,2)
''','0\n1\n1\nfalse\n1\n2\n7\n8\n9\n')

    def test_clamped_difference_and_negative_one_cell_comparison_keep_zero_results(self):
        self.executes('''function clampedDifference(a: Integer): Integer { let chosen = 0; if 0 > a-2 { chosen = 0 } else { chosen = a-2 }; return chosen*8 }
function different(state: List<Integer>): Boolean { let value = state[0] != -1; return value }
print(clampedDifference(0)); print(clampedDifference(1)); print(clampedDifference(2)); print(clampedDifference(3)); let state = [-1]; print(different(state)); state[0] = 0; print(different(state)); state[0] = -1; print(different(state))
''','0\n0\n0\n8\nfalse\ntrue\nfalse\n')

    def test_wide_scaled_nine_division_keeps_literal_and_parameter_precision(self):
        quotient = (9 * (2**55)) // 255
        self.assertEqual(quotient,1271604600669316)
        self.executes('''function scaled(n: Integer): Integer { return (n*36028797018963968)/255 }
let n = 9; print(scaled(n)); print((9*36028797018963968)/255); print(324259173170675712/255)
''',f'{quotient}\n'*3)

    def test_record_field_loop_reload_and_fresh_record_loop_exit(self):
        self.executes('''record Cell { i: List<Integer> }
record Pair { x: Integer,y: Integer }
function advance(x: Cell,y: Cell): Integer { let timeout = 0; let xc = x.i; let yc = y.i; while xc[0] < yc[0] { timeout = timeout + 1; if timeout > 5 { return -99 }; xc[0] = xc[0] + 1 }; return timeout }
function fresh(): Integer { let timeout = 0; let x = 0; while true { let item = Pair { x: x,y: 0 }; x = x + 1; print(item.x); print(item.y); if item.x > 0 { print(x); return timeout }; timeout = timeout + 1; if timeout > 5 { return -99 } }; return -100 }
let x = Cell { i: [0] }; let y = Cell { i: [1] }; print(advance(x,y)); let xc = x.i; let yc = y.i; print(xc[0]); print(yc[0]); print(fresh())
''','1\n1\n1\n0\n0\n1\n0\n2\n1\n')

    def test_nested_call_preserves_saved_and_middle_record_arguments(self):
        self.executes('''record Triple { a: Integer,b: Integer,c: Integer }
function check(a: Integer,b: Integer,c: Integer) { print(a); print(b); print(c) }
function bar(a: Integer,b: Integer): Integer { print(a); return b }
function baz(a: Integer,b: Integer,c: Integer) { let d = c; check(d,bar(a,1),b) }
function forward(value: Triple,b: Integer,c: Integer) { check(value.b,b,c) }
baz(10,11,12); forward(Triple { a: 3,b: 4,c: 5 },1,2)
''','10\n12\n1\n11\n4\n1\n2\n')

    def test_five_field_record_survives_first_and_middle_argument_positions(self):
        self.executes('''record Five { a: Integer,b: Integer,c: Integer,d: Integer,e: Integer }
function bar(value: Five,f: Integer,g: Integer,h: Integer,i: Integer,j: Integer) { print(value.a); print(value.b); print(value.c); print(value.d); print(value.e); print(f); print(g); print(h); print(i); print(j) }
function first(value: Five,unused: Text) { bar(value,6,7,8,9,10) }
function middle(left: Text,value: Five,right: Text) { bar(value,6,7,8,9,10) }
let value = Five { a: 1,b: 2,c: 3,d: 4,e: 5 }; first(value,"unused"); middle("left",value,"right")
''',''.join(f'{n}\n' for _ in range(2) for n in range(1,11)))

    def test_local_cell_and_record_references_survive_intervening_calls(self):
        self.executes('''record Triple { a: Integer,b: Integer,c: Integer }
function baz(local: List<Integer>,state: List<Integer>) { state[0] = local[0] }
function check(state: List<Integer>,b: Integer) { print(state[0]); print(b) }
function copy(a: Integer,b: Integer,state: List<Integer>) { let local = [a]; baz(local,state); check(state,b) }
function readAlias(state: List<List<Integer>>,b: Integer) { let local = state[0]; print(local[0]); print(b) }
function alias(a: Integer,b: Integer,state: List<List<Integer>>) { let local = [a]; state[0] = local; readAlias(state,b) }
function readRecord(state: List<Triple>,b: Integer) { let item = state[0]; print(item.a); print(item.b); print(item.c); print(b) }
function aliasRecord(a: Triple,b: Integer,state: List<Triple>) { state[0] = a; readRecord(state,b) }
let state = [0]; copy(1,2,state); let aliases = [[0]]; alias(1,2,aliases); let records = [Triple { a: 0,b: 0,c: 0 }]; aliasRecord(Triple { a: 1,b: 2,c: 3 },4,records)
''','1\n2\n1\n2\n1\n2\n3\n4\n')

    def test_scalar_record_argument_reordering_keeps_every_field(self):
        self.executes('''record Triple { a: Integer,b: Integer,c: Integer }
function one(i: Integer,t: Triple) { print(t.a != t.b && t.a != t.c); print(t.a); print(t.b); print(t.c); print(i) }
function first(t: Triple,i: Integer) { one(i,t) }
function three(i: Integer,j: Integer,k: Integer,t: Triple) { print(t.a); print(t.b); print(t.c); print(i); print(j); print(k) }
function second(t: Triple,i: Integer,j: Integer,k: Integer) { three(i,j,k,t) }
let t = Triple { a: 1,b: 2,c: 3 }; first(t,4); second(t,4,5,6)
''','true\n1\n2\n3\n4\n1\n2\n3\n4\n5\n6\n')

    def test_wide_comparison_and_saved_value_survive_shared_cell_reload(self):
        self.executes('''function compare(value: Integer): Boolean { return value >= 4294967297 }
function update(p: List<Integer>,state: List<Integer>): Integer { let a = p[0]; let x = a + 5; a = state[0]; p[0] = x - 15; return a }
print(compare(8589934591)); print(compare(4294967296)); print(compare(4294967297)); let state = [-1]; let b = [1]; print(update(b,state)); print(b[0]); print(state[0])
''','true\nfalse\ntrue\n-1\n-9\n-1\n')

    def test_mixed_ten_argument_positions_preserve_supported_kinds(self):
        # LLVM ManyArguments: replace unsupported floats/pointers with distinct
        # supported kinds, retaining ten heterogeneous argument positions.
        self.executes('''record Box { value: Integer }
function receive(a: Integer, b: Boolean, c: Character, d: Text, e: Box, f: List<Integer>, g: Integer, h: Text, i: Boolean, j: Integer) {
print(a); print(b); print(c); print(d); print(e.value); print(f[0]); print(g); print(h); print(i); print(j)
}
receive(12, true, "Q"[0], "four", Box { value: -12 }, [23], 123456, "eight", false, 123124124124)
''', '12\ntrue\nQ\nfour\n-12\n23\n123456\neight\nfalse\n123124124124\n')

    def test_checked_wide_arithmetic_preserves_square_and_high_word_results(self):
        self.executes('''function product(x: Integer, y: Integer): Integer { return x * y }
function minimum(x: Integer): Boolean { return x + 1 < 0 }
function booleanValue(x: Integer): Boolean { return x != 0 }
function compare(x: Integer, y: Integer) { let sum = x * x + y * y; print(sum); print(sum < 4194304) }
function divide(x: Integer, y: Integer) { let difference = x * x - y * y; print(difference); print(difference / 262144) }
function subtract(x: Integer, y: Integer) { let sum = x * x + y * y; print(2147483648 - sum) }
print(product(65535, -32768)); print(65535 * -32768)
print(minimum(-9223372036854775808)); print(booleanValue(1230098424783699968))
compare(2097152,2097152); print(2097152 * 2097152 + 2097152 * 2097152 < 4194304)
divide(2097153,2097154); subtract(2097153,2097154)
''', '-2147450880\n-2147450880\ntrue\ntrue\n8796093022208\nfalse\nfalse\n-4194307\n-16\n-8793958121477\n')

    def test_large_negative_product_traps_after_quotient_and_offset(self):
        self.executes('''function product(x: Integer, y: Integer): Integer { return x * y }
let factor = -(9223372036854775807 / 65535 + 32768)
print(factor)
print(product(65535, factor))
print("unreachable")
''', '-140739635904512\n', 1, 'Minyar stopped: this Integer calculation is outside the supported range.\n')

    def test_constructor_product_and_computed_index_preserve_overflow_precedence(self):
        self._execute_fatal_branches(['record Box { value: Integer }'], [
            ('field', 'let box = Box { value: 1024 * 1024 * 1024 * 1024 * 1024 * 1024 * 1024 }; print(box.value)', '', 'Minyar stopped: this Integer calculation is outside the supported range.\n'),
            ('index', 'let values = [1,2,3]; print(values[1024 * 1024 * 1024 * 1024 * 1024 * 1024 * 1024])', '', 'Minyar stopped: this Integer calculation is outside the supported range.\n'),
        ])

    def test_nested_record_paths_rebinding_and_constant_initializers(self):
        self.executes('''record Item { w: Integer; x: Text; y: Boolean; z: Integer }
record Pair { a: Item; b: Item }
function show(item: Item) { print(item.w); print(item.z) }
let pair = Pair { a: Item { w: 1; x: "first"; y: true; z: 123455678902 }; b: Item { w: 2; x: "second"; y: false; z: 23455678902 } }
show(pair.a); show(pair.b)
record Point { b: Integer; c: Integer }
function copy(point: Point): Point { return point }
let d = Point { b: -7988785259004943837; c: -7 }
let s = Point { b: -7988785259004943837; c: -6 }
let e = -7
let h = Point { b: 0; c: 9 }
s = h; e = h.c; d = copy(h)
print(d.b); print(d.c); print(s.b); print(s.c); print(e)
record Small { a: Integer; b: Integer }
record Container { value: Small; reference: Small; values: List<Integer> }
let global = Small { a: 1; b: 2 }
let container = Container { value: Small { b: 2; a: 1 }; reference: global; values: [1,1+1] }
print(container.value.b); print(container.reference.b); print(container.values[1])
''', '1\n123455678902\n2\n23455678902\n0\n9\n0\n9\n9\n2\n2\n2\n')

    def test_dead_nested_loop_paths_keep_fuzzed_state_and_short_circuit(self):
        self.executes('''function coverage002(a: Integer, c: Integer, d: Integer, e: Integer, state: List<Integer>) {
let g = 0; state[0] = g
while g < 5 { g = g + 1 }
while g < 3 { while true { fail("dead inner") } }
let active = true
while active {
if a != 0 { fail("unexecuted goto") }
if d != 0 { if e != 0 { return }; active = false } else { if c != 0 { print("unexpected continue") } }
}
state[1] = 0; state[2] = state[1]; print(g)
}
function coverage004(i: Integer, a: Integer): Boolean { return i != 0 && 2036854775807 / a != 0 && i != 0 }
function coverage007(a: Integer) { let f = 4294967295 / a; let g = f; print(f); print(g < 0) }
let state = [4,0,0]; coverage002(0,-2,10,0,state); print(state[0]); print(state[1]); print(state[2])
print(coverage004(0,251)); print(coverage004(-7,251)); print(coverage004(0,0)); coverage007(3)
let a = 0; let f = 20; let g = 1; let j = 1; let i = 8
while f != 0 { g = 5; let active = true; while active && g <= 32 { i = 6; while i < -4 { fail("dead inner") }; if j != 0 { active = false } else { g = g + 1 } }; f = a }
let e = 0; while e != 0 { fail("dead second loop") }
print(i); print(g); print(f); print(e)
''', '5\n0\n0\n0\nfalse\ntrue\nfalse\n1431655765\nfalse\n6\n5\n0\n0\n')

    def test_zero_iteration_helper_preserves_state_and_empty_argument_loop(self):
        self.executes('''function update(state: List<Integer>): Integer {
let h = 5; state[3] = h
while state[0] != 0 { state[8] = 0; while state[8] <= 9 { state[1] = 0; print("dead effect"); state[8] = state[8] + 1 }; state[0] = 0 }
state[9] = state[2]; return state[9]
}
function forward(state: List<Integer>) { state[7] = update(state) }
let state = [0,0,0,0,0,0,0,0,0,0]; forward(state)
let i = 0; while i < state.length { print(state[i]); i = i + 1 }
print("#Args = " + Text(argumentCount()) + ". They are:")
i = 0; while i < argumentCount() { print(argument(i)); i = i + 1 }
''', '0\n0\n0\n5\n0\n0\n0\n0\n0\n0\n#Args = 0. They are:\n')

    def test_fresh_record_temporaries_and_returned_list_fields(self):
        self.executes('''record Temporary { text: Text; cell: List<Integer> }
function mutate(value: Temporary) { print(value.text); print(value.cell[0]); let cell = value.cell; cell[0] = 2; print(value.cell[0]) }
function construct() { mutate(Temporary { text: "hi"; cell: [1] }) }
construct(); construct()
record Fields { v: Integer; w: Integer }
record Pair { c: Fields; d: Fields }
let first = Fields { v: 0; w: 250000 }
let pair = Pair { c: first; d: first }
print(pair.c.v); print(pair.c.w); print(pair.d.v); print(pair.d.w)
record Values { r: List<Integer> }
record Arguments { value: Values }
function values(count: Integer): Values { let r: List<Integer> = []; let i = 0; while i < count { r.add(-1); i = i + 1 }; return Values { r: r } }
let args = Arguments { value: Values { r: [] } }
args = Arguments { value: values(5) }; print(args.value.r.length); print(args.value.r[0])
args = Arguments { value: values(3) }; print(args.value.r.length); print(args.value.r[0])
''', 'hi\n1\n2\nhi\n1\n2\n0\n250000\n0\n250000\n5\n-1\n3\n-1\n')

    def test_aliased_cell_arithmetic_buffer_reloads_and_recursive_store(self):
        self.executes('''record Coefficients { xx: Integer; xy: Integer; x: Integer; z: Integer }
function adjust(x: List<Integer>, y: List<Integer>, coefficients: Coefficients) { x[0] = coefficients.xx * x[0] + coefficients.xy * y[0] + coefficients.x }
let x = [1]; let y = [1]; adjust(x,y,Coefficients { xx: 0; xy: 0; x: 1; z: 1 }); print(x[0]); print(y[0])
let p = x; let i = 0; p[i] = 2; print(x[0])
function noop() { }
function buffer(state: List<Integer>, offset: Integer): Integer {
let i = state[1]; if i != 0 { return i * 52783 }; let current = state[0]
i = 0; while i < 2 { noop(); i = i + 1 }; current = state[0]; return current * 52783 + offset
}
let state = [0,0]; print(buffer(state,3)); state[0] = 1; print(buffer(state,2))
function one(): Integer { return 1 }
function recurse(x: Integer, memory: List<Integer>): Integer {
if x != 0 { return x }; let index = x; x = x + 1; memory[index] = recurse(one(),memory); print(x); return 0
}
let memory = [0,0,0]; print(recurse(0,memory)); print(memory[0]); print(memory[1]); print(memory[2])
function poly(sum: Integer, x: Integer): Integer { sum = sum + sum * x; return sum }
print(poly(2,-3)); print(poly(2,3)); i = 1; i = i * 2 + 1; print(i)
''', '1\n1\n2\n3\n52785\n1\n0\n1\n0\n0\n-4\n8\n3\n')

    def test_disjunction_doubling_reverse_cells_and_forwarded_arguments(self):
        self.executes('''let i = 1; let j = 0
while i != 1024 || j <= 0 { i = i * 2; j = j + 1 }; print(i); print(j)
function reverse(a: List<Integer>) {
let base = 0; while base < a.length { let last = base + 3; let value = a[last]; a[last] = a[base]; a[base] = value; base = base + 1; last = base + 1; value = a[last]; a[last] = a[base]; a[base] = value; base = base + 3 }
}
function show(a: List<Integer>) { let i = 0; while i < a.length { print(a[i]); i = i + 1 } }
let cells = [1,0,0,0]; reverse(cells); show(cells); reverse(cells); show(cells)
function paired(i: Integer, j: Integer) { print(i); print(j) }
function forward(i: Integer) { paired(i,i) }
function load(values: List<Integer>, index: Integer) { forward(values[index]) }
let values = [0,1,2]; i = values.length - 1; while i >= 0 { load(values,i); i = i - 1 }
function references(leading: Integer, a: List<Integer>, b: List<Integer>, c: List<Integer>) { print(leading); print(a[0]); print(b[0]); print(c[0]) }
references(0,[1],[2],[3])
function observeArgument(value: Integer) { print(value) }
function small(): Integer { let i = 4096; observeArgument(i + 4); return i }
function wide(): Integer { let i = 4096; observeArgument(i + 2147483647); return i }
print(small()); print(wide())
''', '1024\n10\n0\n0\n0\n1\n1\n0\n0\n0\n2\n2\n1\n1\n0\n0\n0\n1\n2\n3\n4100\n4096\n2147487743\n4096\n')

    def test_short_circuit_invalidation_and_two_input_loop_forms(self):
        self.executes('''record Entry { inMemory: Boolean; inStruct: Boolean }
record Writes { all: Boolean; nonscalar: Boolean }
function varies(calls: List<Integer>): Boolean { calls[0] = calls[0] + 1; return false }
function invalidate(table: List<List<Entry>>, writes: Writes, calls: List<Integer>) {
let bucket = 0; while bucket < 31 { let values = table[bucket]; let i = 0; while i < values.length { let value = values[i]; if value.inMemory && (writes.all || (writes.nonscalar && value.inStruct) || varies(calls)) { fail("removed") }; i = i + 1 }; bucket = bucket + 1 }
}
let table: List<List<Entry>> = []; table.add([Entry { inMemory: true; inStruct: false }]); let i = 1; while i < 32 { table.add([]); i = i + 1 }
let calls = [0]; invalidate(table,Writes { all: false; nonscalar: true },calls); print(calls[0]); print(table[0].length)
function input(visits: List<Integer>): Integer { visits[0] = visits[0] + 1; return 0 }
function alnum(ch: Integer): Boolean { return (ch >= 65 && ch <= 90) || (ch >= 97 && ch <= 122) || (ch >= 48 && ch <= 48) }
function scan(visits: List<Integer>): Integer { while true { let ch = input(visits); if alnum(ch) { fail("grow") } else { if ch != 95 { return ch } } }; return -1 }
function post(visits: List<Integer>): Integer { let ch = input(visits); if alnum(ch) { fail("grow") }; while ch == 95 { ch = input(visits); if alnum(ch) { fail("grow") } }; return ch }
let visits = [0]; print(scan(visits)); print(visits[0]); visits[0] = 0; print(post(visits)); print(visits[0])
record Ordered { a: Integer; b: Integer }
function compare(p: Ordered, y: Integer): Boolean { return y < 0 || y > 255 || -p.b >= p.a }
print(compare(Ordered { a: -4028; b: 4096 },10))
''', '1\n1\n0\n1\n0\n1\nfalse\n')

    def test_inclusive_last_cell_can_exit_before_caller_failure(self):
        self.executes('''function scan(values: List<Integer>, end: Integer, count: Integer) {
let index = end - count
while index <= end { print(values[index]); if values[index] < 2 { exit(0) }; index = index + 1 }
}
scan([2,0],1,1)
fail("caller")
''', '2\n0\n')

    def test_returned_bounds_preserve_size_and_nested_list_initializers(self):
        self.executes('''record Bounds { low: Integer; high: Integer }
record Type { length: Integer; fields: Integer }
function bounds(): Bounds { return Bounds { low: 0; high: 2 } }
function construct(result: List<Type>, element: Type) { let b = bounds(); result[0] = Type { length: element.length * (b.high - b.low + 1); fields: 1 } }
let result = [Type { length: 0; fields: 0 }]; construct(result,Type { length: 4; fields: 0 }); print(result[0].length); print(result[0].fields)
let first = [1]; let second = [[1],[0]]; print(first[0]); print(second[0][0]); print(second[1][0])
''', '12\n1\n1\n1\n0\n')

    def test_prefix_sums_and_indexed_accumulator_keep_dependent_loads(self):
        self.executes('''function prefix(values: List<Integer>, length: Integer): Integer {
let i = 0; while i < length { let previous = 0; if i > 0 { previous = values[i-1] }; values[i] = i + previous; i = i + 1 }; return values[length-1]
}
let values = [0,0,0,0,0,0]; print(prefix(values,6)); let i = 0; while i < values.length { print(values[i]); i = i + 1 }
function add(a: List<Integer>, ai: Integer, b: List<Integer>, bi: Integer): Integer { return a[ai] + b[bi] }
function compute(start: Integer, mask: List<Integer>, psd: List<Integer>, output: List<Integer>) {
let j = start; let k = mask[start]; output[k] = psd[j]; j = j + 1; let i = j; while i < 4 { output[k] = add(output,k,psd,j); j = j + 1; i = i + 1 }
}
let mask = [1,2,3,4,5,0]; let psd = [50,40,30,20,10,0]; let output = [1,2,3,4,5,0]
compute(0,mask,psd,output); i = 0; while i < 6 { print(output[i]); print(psd[i]); print(mask[i]); i = i + 1 }
''', '15\n0\n1\n3\n6\n10\n15\n' + ''.join(f'{a}\n{b}\n{c}\n' for a,b,c in zip([1,140,3,4,5,0],[50,40,30,20,10,0],[1,2,3,4,5,0])))

    def test_conditional_assignment_saved_scalar_and_lagging_induction(self):
        self.executes('''let n = 2; let i = 0; let x = 45
while i < n { if i != 0 { if i > 0 { x = i } else { x = 0 } }; print(x); i = i + 1 }
function linear(values: List<Integer>): Integer { return (-3 * values[0] - 3 * values[1]) / 12 }
print(linear([18,6])); print((-3*18 - 3*6)/12)
function mutate(y: List<Integer>) { y[0] = y[0] + 1 }
function compare(x: Integer, y: Integer) { print(x); print(y); print(x != y) }
function forward(x: Boolean, initial: Integer, e: Integer) { let f = 0; if x { f = e }; let y = [initial]; let z = y[0]; mutate(y); compare(z,y[0]); print(f) }
forward(false,0,17)
function choose(x: Integer): Integer { if x < 5 { x = 4 } else { x = 8 }; return x }
print(choose(8))
let biv = 0; let giv = 0; while giv != 8 { giv = biv * 8; print(giv); biv = biv + 1 }; print(biv); print(giv)
let s = 1; if s < 0 { s = -2147483648 } else { s = 2147483647 }; print(s); print(s < 0)
function plusTwo(base: Integer): Integer { return base + 2 }
function offset(base: Integer): Integer { return plusTwo(base) - 1 - base }
print(offset(0)); print(offset(4294967296))
''', '45\n1\n-6\n-6\n0\n1\ntrue\n0\n8\n0\n8\n2\n8\n2147483647\nfalse\n1\n1\n')

    def test_thirteen_integer_and_seven_mixed_arguments_preserve_positions(self):
        names = [f'v{i}' for i in range(1,14)]
        source = 'function add(' + ', '.join(f'{name}: Integer' for name in names) + '): Integer {\n'
        source += '; '.join(f'print({name})' for name in names) + '\nreturn ' + ' + '.join(names) + '\n}\n'
        source += 'print(add(' + ','.join(str(i) for i in range(1,14)) + '))\n'
        source += '''function mixed(a: Integer, b: Integer, c: Integer, d: Boolean, e: Boolean, f: Boolean, g: Character): Integer {
print(a); print(b); print(c); print(d); print(e); print(f); print(g == "\u0001"[0]); return a+b+c
}
print(mixed(1,2,-3,true,true,true,"\u0001"[0]))
'''
        self.executes(source, ''.join(f'{i}\n' for i in range(1,14))+'91\n1\n2\n-3\ntrue\ntrue\ntrue\ntrue\n0\n')

    def test_module_bound_boolean_guard_exits_before_failure(self):
        self.executes('''let bound = 1
let i = 0
let deleted = true
if i < bound && deleted { print("selected"); exit(0) }
fail("wrong branch")
''', 'selected\n')

    def test_scanner_helpers_and_partial_redundancy_preserve_all_visits(self):
        self.executes('''record Match { found: Boolean; end: Integer }
function scan(text: Text, calls: List<Integer>): Match { print(text); calls[0] = calls[0]+1; if calls[0] > 2 { fail("too many scans") }; return Match { found: false; end: 1 } }
function remaining(text: Text, count: List<Integer>): Boolean { print(text); count[0] = count[0] + 1; return true }
function run(args: List<Text>, state: List<Integer>, count: List<Integer>): Integer {
let matched = scan(args[state[0]],count); if matched.found { fail("unexpected match") }
let second = scan(args[state[0]],count); if second.end == 0 { fail("unexpected start") }
let visits = [0]; state[0] = state[0] + 1
while state[0] < args.length { if !remaining(args[state[0]],visits) { return 1 }; state[0] = state[0] + 1 }; print(visits[0]); return 0
}
let state = [0]; let count = [0]; print(run(["a","b","c","d","e"],state,count)); print(count[0]); print(state[0])
function partial(text: Text, output: List<Character>): Integer {
let input = 0
while true { if text[input] == "a"[0] { let p = input + 1; while text[p] == "x"[0] { p = p + 1 }; if text[p] == "b"[0] { return p }; while input < p { output.add(text[input]); input = input + 1 } } }
return -1
}
let output: List<Character> = []; print(partial("aab",output)); print(output.length); print(output[0])
function inspect(value: List<Text>) { print(value[0]) }
let text = [""]; text[0] = "abc"; inspect(text); text[0] = "abcdefgh"; print(text[0])
function second(text: Text): Character { return text[1] }; print(second("xy"))
''', 'a\na\nb\nc\nd\ne\n4\n0\n2\n5\n2\n1\na\nabc\nabcdefgh\ny\n')

    def test_nested_transfer_and_record_minimum_keep_prior_field_values(self):
        self.executes('''record Inner { value: Integer }
record Content { inner: Inner; c3: Integer; c4: Integer }
record Owner { content: List<Content>; links: List<Integer> }
function transfer(x: Owner, y: Owner) {
if x.links.length == 0 { if y.links.length != 0 { fail("unexpected chain") } }
let xv = x.content; let yv = y.content
if xv[0].c3 == -1 { xv[0] = Content { inner: xv[0].inner; c3: yv[0].c3; c4: yv[0].c4 }; yv[0] = Content { inner: yv[0].inner; c3: -1; c4: 0 } }
}
let x = Owner { content: [Content { inner: Inner { value: 0 }; c3: -1; c4: 0 }]; links: [] }
let y = Owner { content: [Content { inner: Inner { value: 6 }; c3: 145; c4: 2448 }]; links: [] }
transfer(x,y); print(x.content[0].c3); print(x.content[0].c4); print(y.content[0].c3); print(y.content[0].c4); print(y.content[0].inner.value)
record Value { ignored: Integer; a2: Integer }
function bar(x: Integer): Integer { return 2241 }
let a = Value { ignored: 1; a2: 0 }; let bound = 3384
a = Value { ignored: a.ignored; a2: bar(a.ignored) }
let selected = bound - 1; if a.a2 < bound - 1 { selected = a.a2 }; a = Value { ignored: a.ignored; a2: selected }
print(a.a2); print(a.a2 < bound - 1)
''', '145\n2448\n-1\n0\n6\n2241\ntrue\n')

    def test_unsorted_smallest_pair_and_binary_block_search(self):
        self.executes('''let elements = [30,2,10,5]; let small = [0,0]; let greatest = -1; let position = -1; let i = 0
while i < 2 { small[i] = elements[i]; if elements[i] > greatest { position = i; greatest = elements[i] }; i = i + 1 }
while i < 4 { if elements[i] < greatest { small[position] = elements[i]; position = 0; greatest = small[0]; let j = 1; while j < 2 { if small[j] > greatest { position = j; greatest = small[j] }; j = j + 1 } }; i = i + 1 }
print(small[0]); print(small[1]); print(greatest); print(position)
record Block { start: Integer; end: Integer }
function find(blocks: List<Block>, pc: Integer): Integer {
let bottom = 0; let top = blocks.length
while top - bottom > 1 { let half = (top - bottom + 1) / 2; let block = blocks[bottom+half]; if block.start <= pc { bottom = bottom+half } else { top = bottom+half } }
while bottom >= 0 { let block = blocks[bottom]; if block.end > pc { return bottom }; bottom = bottom - 1 }; return -1
}
print(find([Block { start: 0; end: 65536 },Block { start: 65536; end: 131072 }],1280))
''', '5\n2\n5\n0\n0\n')

    def test_recursive_record_swap_returns_full_selected_polynomial(self):
        self.executes('''record Polynomial { max: Integer; degree: Integer; coefficients: List<Integer> }
function gcd(f: Polynomial, g: Polynomial): Polynomial {
print(f.degree); print(g.degree)
if f.degree < g.degree { return gcd(g,f) }
if f.degree != 2 || g.degree != 1 { fail("degrees") }
if f.coefficients[0] == 0 { return f }
fail("unreachable")
}
let f = Polynomial { max: 1; degree: 1; coefficients: [0,1] }
let g = Polynomial { max: 2; degree: 2; coefficients: [0,0,1] }
let result = gcd(f,g); print(result.max); print(result.degree); print(result.coefficients[0]); print(result.coefficients[1]); print(result.coefficients[2])
''', '1\n2\n2\n1\n2\n2\n0\n0\n1\n')

    def test_posttested_guard_digit_sign_and_store_before_second_helper(self):
        self.executes('''function guard(value: List<Integer>) { if value[0] < 52 { fail("unlikely") }; value[0] = value[0]+1; while value[0] >= 62 { value[0] = value[0]+1 } }
let value = [53]; guard(value); print(value[0])
function digits(i: Integer): Text { let ui = i; if i < 0 { ui = -ui }; let result = Text(ui % 10); ui = ui / 10; while ui != 0 { result = Text(ui % 10) + result; ui = ui / 10 }; if i < 0 { result = "-" + result }; return result }
print(digits(-1))
record Item { a: Integer; c: List<Integer> }
function visited(item: Item, calls: List<Integer>): Boolean { print(item.c[0]); calls[0] = calls[0]+1; if calls[0] > 2 { fail("too many") }; return calls[0] > 1 }
function loop(item: Item, b: Boolean, c: Boolean, d: Integer, calls: List<Integer>): Integer {
while true { let a = visited(item,calls); if a { return 0 }; if !b { let field = item.c; field[0] = d; if item.a != 0 || c { fail("dead branch") }; d = item.c[0] } }; return d
}
let item = Item { a: 0; c: [23] }; let calls = [0]; print(loop(item,false,false,0,calls)); print(item.a); print(item.c[0]); print(calls[0])
''', '54\n-1\n23\n0\n0\n0\n0\n2\n')

    def test_comparison_reuse_nested_scopes_and_independent_assignments(self):
        self.executes('''function reused(n: Integer) { let h = n <= 30; let p = 0; let k = 0; if h { p = 1 } else { p = 0 }; if h { k = 1 } else { k = 0 }; print(p); print(k) }
reused(30)
function identity(value: Integer): Integer { return value }
function nested(value: Integer): Integer { let flag = false; if true { let t1 = value; if true { let t2 = t1; if true { flag = identity(t2) == 0 } } }; if flag { return 5046272 }; return 0 }
print(nested(1))
function positive(a: Integer): Integer { let x = 0; if a > 0 { x = 1 }; if a < 0 { x = 1 }; return x }
print(positive(1))
function status(value: Integer): Integer { let s = 0; if value == 1 { s = 1 }; if value == 3 { s = 3 }; if value == 4 { s = 4 }; return s }
print(status(3))
function observe(x: Integer) { print(x) }
let z = 0; let start = 0; let end = 2; let selected = end-start-1; if z > 0 { selected = end-start }; observe(selected)
''', '1\n1\n0\n1\n3\n1\n')

    def test_nested_record_call_return_clamp_and_eighth_argument(self):
        self.executes('''record Part { x: Integer }
record Whole { a: Part; b: Part }
function consume(r: Whole) { print(r.a.x); print(r.b.x) }
function retrieve(r: Whole): Whole { return r }
let original = Whole { a: Part { x: 100 }; b: Part { x: 200 } }; consume(original); let returned = retrieve(original); print(returned.a.x); print(returned.b.x)
record Inner { x: Integer; y: Integer }
record Outer { z: Integer; b: Inner }
function make(): Outer { let b = Inner { x: 0; y: 1 }; let a = Outer { z: 2; b: b }; return a }
let made = make(); print(made.z); print(made.b.x); print(made.b.y)
record Bounds { minx: Integer; maxx: Integer; miny: Integer; maxy: Integer }
let global = Bounds { minx: 75; maxx: 175; miny: 75; maxy: 175 }
let bound = Bounds { minx: 100; maxx: 150; miny: 100; maxy: 150 }
let save = Bounds { minx: global.minx; maxx: global.maxx; miny: global.miny; maxy: global.maxy }
if save.minx < bound.minx { save = Bounds { minx: bound.minx; maxx: save.maxx; miny: save.miny; maxy: save.maxy } }
if save.maxx > bound.maxx { save = Bounds { minx: save.minx; maxx: bound.maxx; miny: save.miny; maxy: save.maxy } }
print(save.maxx-save.minx); print(global.minx); print(global.maxx)
record Array { values: List<Integer> }
function eighth(s: Array, x1: Integer, x2: Integer, x3: Integer, x4: Integer, x5: Integer, x6: Integer, x7: Integer): Integer { print(x1); print(x2); print(x3); print(x4); print(x5); print(x6); print(x7); return s.values[3]+x7 }
print(eighth(Array { values: [1,2,3,4] },100,200,300,400,500,600,700))
''', '100\n200\n100\n200\n2\n0\n1\n50\n75\n175\n100\n200\n300\n400\n500\n600\n700\n704\n')

    def test_nested_false_calls_and_recursive_sentinel_keep_call_counts(self):
        self.executes('''function falseCall(count: List<Integer>): Boolean { count[0] = count[0]+1; return false }
let count = [0]; let bad = false; let i = 0
while i < 10 { let j = 0; while j < 10 { if falseCall(count) { bad = true }; j = j+1 }; let k = bad != false; print(k); if k { fail("bad") }; i = i+1 }; print(count[0])
function handler(session: Integer, connected: Boolean, family: Integer, kind: Integer, count: List<Integer>): Integer {
if !connected { return 0 }; if kind == 65535 { return 0 }; if count[0] >= 1 { fail("too many") }; count[0] = count[0]+1; return handler(session,connected,family,65535,count)
}
count[0] = 0; print(handler(0,true,0,0,count)); print(count[0])
''', 'false\n'*10+'100\n0\n1\n')

    def test_division_chains_boundary_ranges_and_mean_calls(self):
        self.executes('''function divide(y: Integer): Integer { return 255/y }
print(divide(2))
let c = 32768; print(c-32768); print(c-32768<0); print(c-32768>32767); print(c-32768<0 || c-32768>32767)
function sequential(max: Integer): Integer { let a = 16; if a/max/16 == 0 { return 0 }; return a/max/16 }
print(sequential(2147483647)); print(sequential(9223372036854775807))
function negative(x: Integer): Integer { print(-x-100); if x == -2 || -x-100 >= 0 { fail("wrong range") }; return 0 }
print(negative(-3)); print(negative(-99))
function truncated(i: Integer): Integer { return (80-4*i)/20 }
print(truncated(1)); print((80-4*1)/20)
function equalBranches(x: Integer) { let y = 0; if x != 0 { y = 793 } else { y = 793 }; print(7930/y); print(7930/x) }
equalBranches(793)
function mean(x: Integer, y: Integer, z: Integer): Integer { return (x+y+z)/3 }
function squareMean(x: Integer, y: Integer, z: Integer): Integer { return mean(x*x,y*y,z*z) }
print(mean(5,10,21)); print(squareMean(9,12,15))
''', '127\n0\nfalse\nfalse\nfalse\n0\n0\n-97\n0\n-1\n0\n3\n3\n10\n10\n12\n150\n')

    def test_callee_updates_sentinel_and_loads_between_module_stores(self):
        self.executes('''function update(next: List<Integer>, index: Integer, length: Integer) { print(length); next[index] = 0 }
let list = [1]; let index = 0; let length = 100; let count = 0
while list[index] != 0 { let previous = index; update(list,index,length); length = length-(index-previous); count = count+1 }
print(count); print(list[0]); print(length)
function noop() { }
function loads(rs1: Integer, rs2: Integer, rd: Integer, registers: List<Integer>, control: List<Integer>): Integer { control[0] = 1; let sum = registers[rs1]+registers[rs2]; control[0] = 2; noop(); registers[rd] = 1; return sum }
let registers: List<Integer> = []; let i = 0; while i < 64 { registers.add(0); i = i+1 }; registers[4] = 47; registers[8] = 11
let control = [0]; print(loads(4,8,15,registers,control)); print(control[0]); print(registers[15])
function invalidate(value: List<Integer>) { value[0] = 10 }
let value = [5]; invalidate(value); print(value[0])
function localSum(): Integer { let values = [0,1,2,3,4,5,6,7]; let i = 0; let sum = 0; while i < values.length { sum = sum+values[i]; i = i+1 }; return sum }
print(localSum())
function barrier(text: Text, position: List<Integer>) { }
let text = "foo { xx }"; let position = [5]; barrier(text,position)
while position[0] < text.length && (text[position[0]] == "\r"[0] || text[position[0]] == " "[0]) { position[0] = position[0]+1 }
print(position[0]); print(text.slice(position[0],text.length))
''', '100\n1\n0\n100\n58\n2\n1\n10\n28\n6\nxx }\n')

    def test_wide_section_count_survives_record_setup_calls(self):
        self.executes('''record File { value: Integer }
record Section { address: Integer; load: Integer; user: Boolean; alignment: Integer; size: Integer }
function openFile(): File { return File { value: 0 } }
function makeSection(file: File, name: Text): Section { return Section { address: 0; load: 0; user: false; alignment: 0; size: 0 } }
function setSize(file: File, section: Section, count: Integer): Boolean { print(count); return true }
function flags(file: File, section: Section, value: Integer) { print(value) }
function contents(file: File, section: Section, data: Text, offset: Integer, count: Integer) { print(count); print(section.address); print(section.load); print(section.user); print(section.alignment); print(section.size); print(data); print(offset) }
function dump(address: Integer, data: Text, count: Integer) {
let file = openFile(); let section = makeSection(file,".newsec"); let good = setSize(file,section,count)
section = Section { address: address; load: address; user: true; alignment: 0; size: section.size }; flags(file,section,515)
section = Section { address: section.address; load: section.load; user: section.user; alignment: section.alignment; size: 0 }; contents(file,section,data,0,count)
}
dump(3735928559,"hello",514703087)
''', '514703087\n515\n514703087\n3735928559\n3735928559\ntrue\n0\n0\nhello\n0\n')

    def test_saved_selection_and_boolean_result_survive_helper_calls(self):
        self.executes('''function noop(value: Integer) { }
function stereo(single: Integer): Integer { let selected = 0; if single >= 0 { selected = 1 } else { selected = 2 }; noop(single); return selected }
print(stereo(-1))
function last(fd: Integer, op: Integer, offset: Integer, count: Integer, kind: Integer): Integer { print(fd); print(op); print(offset); print(count); return kind }
function forward(unused: Text, fd: Integer, op: Integer, offset: Integer, count: Integer, kind: Integer): Integer { return last(fd,op,offset,count,kind) }
print(forward("",1,2,3,4,5))
let j = 1073741824; print(1073741824+j); print(1073741824+j<0)
function bar(count: List<Integer>): Boolean { count[0] = count[0]+1; return true }
function saved(x: Integer, count: List<Integer>) { let error = false; error = x == 0 || bar(count); if !error { bar(count) }; print(error); if !error { fail("error") } }
let count = [0]; saved(1,count); print(count[0]); let small = 8; print(small>2147483647)
function compare(x: Integer) { print(x>=1024) }; compare(-9223372036854775808); compare(-9223372036854765808)
function absolute(value: Integer): Integer { if value >= 0 { return 1 }; let foo = value; if value < 0 { foo = -value }; return foo }
print(absolute(-1))
''', '2\n1\n2\n3\n4\n5\n2147483648\nfalse\ntrue\n1\nfalse\nfalse\nfalse\n1\n')

    def test_nested_rows_length_capture_and_conditional_store_positions(self):
        self.executes('''let rows: List<List<Integer>> = []; let i = 0
while i < 100 { let row: List<Integer> = []; let j = 0; while j < 100 { row.add(0); j = j+1 }; rows.add(row); i = i+1 }
i = 99; let row = rows[i]; row[0] = 42; print(rows[99][0]); print(rows[98][0]); print(rows[99][1])
let chars: List<Character> = []; let text = "1234567890"; i = 0; while i < text.length { chars.add(text[i]); i = i+1 }
let cursor = 0; let count = chars.length; chars[cursor] = "\n"[0]; cursor = cursor+1; print(count); print(cursor); print(chars[0]=="\n"[0]); i = 1; while i < chars.length { print(chars[i]); i = i+1 }
function store(a: List<Integer>, b: Integer): Integer { let cursor = 0; a[cursor] = 55; cursor = cursor+1; if b != 0 { a[cursor] = b; cursor = cursor+1 }; return cursor }
function show(a: List<Integer>) { let i = 0; while i < a.length { print(a[i]); i = i+1 } }
let cells = [17,17,17,17,17]; print(store(cells,0)); show(cells); cells = [17,17,17,17,17]; print(store(cells,2)); show(cells)
let values: List<Integer> = [1024]; i = 1; while i < 1025 { values.add(0); i = i+1 }; let d = 0; let oldIndex = d; let oldValue = values[oldIndex]; values[oldIndex] = oldValue+1; d = oldValue; print(values[0]); print(d); print(values[1024])
''', '42\n0\n0\n10\n1\ntrue\n2\n3\n4\n5\n6\n7\n8\n9\n0\n1\n55\n17\n17\n17\n17\n2\n55\n2\n17\n17\n17\n1025\n1024\n0\n')

    def test_copied_record_lives_after_loop_and_nested_flag_swap(self):
        self.executes('''record Pair { x: Integer; y: Integer }
function copy(x: Pair): Pair { return Pair { x: x.x; y: x.y } }
function power(x: Pair, y: Integer): Pair { let a = x; y = y-1; while y>0 { a = copy(a); y = y-1 }; return a }
function compare(x: Pair): Boolean { let a = power(x,2); let b = copy(power(a,2)); print(b.x); print(b.y); return b.x==b.y }
print(compare(Pair { x: -7; y: -7 }))
function diff(ct: Integer, cf: Integer, p1: Boolean, p2: Boolean, p3: Boolean): Integer { let difference = ct-cf; if p1 { if p2 { if p3 { let temporary = ct; ct = cf; cf = temporary }; difference = ct-cf }; return difference }; fail("flag") }
print(diff(2,3,true,true,true))
function barrier(j: Integer) { print(j) }
let values = [1,2]; let k = 0; let j = 0; while j<2 { if k<=values[j] { k = values[j] }; j = j+1 }; k = k+1; barrier(j); print(k)
''', '-7\n-7\ntrue\n1\n2\n3\n')

    def test_text_command_else_branch_and_single_entry_circular_search(self):
        self.executes('''function context(flags: Integer): Boolean { return false }
function command(arg: Text, state: List<Integer>): Boolean { if context(31) { return false }; if arg=="inetd" { state[0] = 0 } else { if arg=="standalone" { state[0] = 1 } else { return false } }; return true }
let state = [0]; print(command("standalone",state)); print(state[0])
record Entry { b3: Integer; b4: Integer }
function absolute(value: Integer): Integer { if value<0 { return -value }; return value }
function search(entries: List<Entry>, start: Integer, size: Integer, amount: Integer, target: Integer): Integer {
let selected = start; let b = amount/512; let d = selected; let best = absolute(target-entries[d].b4); let again = true
while again { if d<=0 { d = size }; d = d-1; let error = absolute(target-entries[d].b4); if error<best { selected = d }; again = d!=start }
entries[selected] = Entry { b3: entries[selected].b3; b4: target+b }; return selected
}
let entries = [Entry { b3: 424242; b4: 0 }]; print(search(entries,0,1,512,4242)); print(entries[0].b4); print(entries[0].b3)
''', 'true\n1\n0\n4243\n424242\n')

    def test_escaped_local_interior_alias_and_selected_cell_reloads(self):
        self.executes('''let global = [0]
let holder: List<List<Integer>> = [[]]
function bind(holder: List<List<Integer>>, global: List<Integer>) { holder[0] = global }
function storeThroughHolder(holder: List<List<Integer>>, global: List<Integer>) { bind(holder,global); let p = holder[0]; p[0] = 42 }
storeThroughHolder(holder,global); print(global[0])
function bar(p: List<Integer>): Integer { return p[0]+1 }
let local = [5]; let p = local; print(bar(p))
record Code { code: Integer }
let r = Code { code: 39 }; let tmp = [0,0]; let q = tmp; let index = 1; q[index] = 0; tmp[1] = 39; print(q[index]); print(r.code)
function selected(i: Integer, constant: Boolean): Integer {
let a = [0]; let b = [0]; let c = [0]; let p = c; if i<5 { p = a } else { if i>8 { p = b } }
if constant { p[0] = 10; b[0] = 3; return p[0]+2 }
p[0] = i; b[0] = i+1; return p[0]
}
print(selected(10,true)); print(selected(9,false))
function inner(value: List<Integer>) { value[0] = -10 }
function outer(value: List<Integer>) { inner(value) }
let value = [10]; outer(value); print(value[0])
''', '42\n6\n39\n39\n5\n10\n-10\n')

    def test_four_octet_scanner_preserves_suffix_and_final_cursor(self):
        self.executes('''function address(text: Text): Integer { print(text); return 168496141 }
function parse(name: Text) {
let octets = 0; let cp = 0; let cq = 0; let scanning = true
while scanning && octets<4 {
while cp<name.length && name[cp]>="0"[0] && name[cp]<="9"[0] { cp = cp+1 }
if cp==cq || cp-cq>3 { scanning = false } else { if name[cp]=="."[0] || octets==3 { octets = octets+1 }; if octets<4 { cp = cp+1 }; cq = cp }
}
if octets==4 && (cp==name.length || name[cp]==":"[0]) { let end = cp; if cp<name.length && name[cp]==":"[0] { cp = cp+1 }; print(address(name.slice(0,end))); print(name.slice(cp,name.length)); print(cp) } else { fail("invalid address") }
}
parse("10.11.12.13:/hello")
''', '10.11.12.13\n168496141\n/hello\n12\n')

    def test_large_local_buffer_keeps_saved_value_across_two_mutating_calls(self):
        self.executes('''function bar(x: Integer, buffer: List<Integer>, global: List<Integer>): Integer { global[0] = global[0]+1; print(buffer.length); return x }
function run(x: Integer, global: List<Integer>): Integer {
let buffer: List<Integer> = []; let i = 0; while i<65536 { buffer.add(0); i = i+1 }
let y = global[0]; global[1] = y; x = bar(x,buffer,global); y = bar(y,buffer,global); return x+y
}
let global = [2,3]; print(run(100,global)); print(global[0]); print(global[1])
''', '65536\n65536\n102\n4\n2\n')

    def test_terminal_helper_observes_store_before_successful_exit(self):
        self.executes('''function terminal(value: List<Integer>) { print(value[0]); if value[0]==0 { fail("stale value") }; exit(0) }
let value = [0]; let shared = value; value[0] = 1; terminal(shared); fail("returned")
''', '1\n')

    def test_loop_snapshots_computed_minimum_and_zero_remainder_side_effect(self):
        self.executes('''function snapshots(i: Integer) { let next = 1; let j = 0; while i!=0 { let n = next; while j<n { next = next+1; j = j+1 }; print(j); print(n); print(next); i = i-1 } }
snapshots(2)
function minimum(): Integer { return -9223372036854775807-1 }
function bounds(j: Integer) { print(j>10 || j<minimum()) }; bounds(10)
function old(value: List<Integer>): Integer { let result = value[0]; value[0] = value[0]+1; return result }
function remainder(a: Integer): Integer { let value = [a]; let unused = 0 % old(value); return value[0] }; print(remainder(9))
function cancel(a: Integer): Integer { return (a-1)+ -9223372036854775808 }; print(cancel(1))
function divide(value: Integer): Integer { return value/32768 }; print(divide(-990000000))
function negative(value: Integer): Integer { return value/ -2147483648 }; print(negative(2147483648))
''', '1\n1\n2\n2\n2\n3\nfalse\n10\n-9223372036854775808\n-30212\n-1\n')

    def test_short_circuit_error_and_prefix_piece_offsets_remain_observable(self):
        self.executes('''function next(text: Text, state: List<Integer>): Character { let index = state[0]; state[0] = state[0]+1; return text[index] }
function error(state: List<Integer>, value: Integer): Boolean { state[2] = value; return false }
function bracket(text: Text, state: List<Integer>) { if (state[0]<state[1] && next(text,state)=="]"[0]) || error(state,7) { } }
let state = [0,0,0]; bracket("",state); print(state[0]); print(state[2])
function pieces(text: Text, separator: Text, hasSeparator: Boolean, count: Integer): Integer {
let parts = ["a","bc","de","fgh"]; let i = 0; let j = 0; print(j)
while i<count { if text.slice(j,j+parts[i].length)!=parts[i] { return 2 }; j = j+parts[i].length; if hasSeparator { j = j+separator.length }; print(j); i = i+1 }; return 0
}
print(pieces("abcde","",false,3))
''', '0\n7\n0\n1\n3\n5\n0\n')

    def test_exact_page_ranges_and_guarded_row_visits(self):
        bounds = [int(x,16) for x in ('c0000000','d0000000','c01bb958','c0264000','c0288000','c02d4378')]
        source = '\n'.join(f'let {name} = {value}' for name,value in zip('abcdef',bounds))
        source += '''
let g = a; let h = 0; let i = 0; let j = 0
while g<b { if g<c { h = h+1 } else { if g>=d && g<e { j = j+1 } else { if g<f { i = i+1 } } }; g = g+4096 }
print(i); print(j); print(h)
function dummy(a: Integer, value: List<Integer>) { value[0] = a }
let rows: List<List<Integer>> = []; i = 0; while i<256 { rows.add([0,0,0]); i = i+1 }
let value = [-1]; i = 0; let visits = 0
while i<256 { if i>=128 && i<256 { dummy(rows[i-128][0],value); visits = visits+1 }; i = i+1 }; print(visits); print(value[0])
function disabled(x: Integer, y: Integer, present: Boolean, values: List<Integer>): Integer { let a = 0; let b = 0; let d = 0; while d<y { if present { b = d*values[0] }; let c = 0; while c<x { a = a+b; c = c+1 }; d = d+1 }; return a }
let empty: List<Integer> = []; print(disabled(3,2,false,empty))
'''
        self.executes(source, '245\n36\n444\n128\n0\n0\n')

    def test_conditional_reads_keep_six_cursor_updates_and_one_clamped_call(self):
        self.executes('''function complicated(): Integer { fail("unexpected fallback") }
function header(values: List<Integer>, state: List<Integer>): Boolean {
let len = 0; while len<6 { let value = 0; if state[0]<state[1] { value = values[state[0]]; state[0] = state[0]+1 } else { value = complicated() }; if value<0 { return false }; len = len+1 }; return true
}
let state = [0,6]; print(header([0,0,0,0,0,0],state)); print(state[0])
function observe(a: Integer, b: Integer) { print(a); print(b) }
function negative(e: Integer, n: Integer) { if e>0 { e = -e }; let i = 0; while i<n { let first = 0; let second = 0; if e>=0 { second = 0; first = 0 } else { first = -e; second = first }; observe(first,second); i = i+1 } }; negative(1,1)
function tar(value: Integer, count: List<Integer>): Integer { print(value); count[0] = count[0]+1; return -1 }
function clamped(q: Integer, count: Integer, calls: List<Integer>) { let j = 0; let outgo = 0; while j != -1 { outgo = outgo+1; if outgo>q-1 { outgo = q-1 }; j = tar(outgo*count,calls) }; print(outgo) }
let calls = [0]; clamped(5,36863,calls); print(calls[0])
''', 'true\n6\n1\n1\n36863\n1\n1\n')

    def test_selected_field_aliases_keep_cached_and_fresh_reads(self):
        self.executes('''function field(i: Integer, condition: Boolean, ff: List<Integer>, p: List<Integer>): Integer { let local = [i]; let selected = ff; if condition { selected = local }; p[0] = 0; return selected[0] }
let ff = [1]; print(field(5,false,ff,ff))
function local(k: Boolean, i1: Integer, j1: Integer): Integer { let i = [i1]; let j = [j1]; let selected = j; if k { selected = i }; i[0] = 0; return selected[0] }; print(local(true,1,2))
function cached(k: List<Integer>, k2: Integer, f: Boolean, f2: Boolean): Integer { let position = 1; if f { position = 0 }; let p = k; let result = p[position]; k[0] = 1; let q = [k2]; let qposition = 0; if f2 { q = p; qposition = position }; return result+q[qposition] }; print(cached([0,1],1,true,true))
function reload(p: List<Integer>) { let x = p[0]; p[0] = 0; let y = p[0]; print(x); print(y); if x!=y { return }; fail("stale") }; let p = [1]; reload(p); print(p[0])
function nested(p: List<List<Integer>>, q: List<List<Integer>>) { let left = p[0]; left[0] = 1; let right = q[0]; right[0] = 2; print(p[0][0]) }
let inner = [0]; let first = [inner]; let second = [inner]; nested(first,second)
function indexed(i: Integer): Integer { let a: List<Integer> = []; let j = 0; while j<32 { a.add(0); j = j+1 }; a[1] = 3; a[0] = 1; a[i] = 2; return a[0] }; print(indexed(0)); print(indexed(1))
function store(y: Integer, global: List<Integer>): Integer { global[0] = y; return global[0] }; let global = [0]; print(store(1,global)); print(global[0])
function load(values: List<Integer>, index: Integer): Integer { return values[index] }; function forward(values: List<Integer>, index: Integer): Integer { return load(values,index) }; print(forward([-1,42],1))
''', '0\n0\n1\n1\n0\n0\n2\n2\n1\n1\n1\n42\n')

    def test_table_selection_and_nested_disjunction_keep_selected_values(self):
        table = [sum(255 << (8*bit) for bit in range(4) if index & (1 << bit)) for index in range(16)]
        source = 'function table(bits: Integer): List<Integer> {\n'
        source += 'if bits==8 { return [' + ','.join(map(str,table)) + '] }\n'
        source += '''if bits==16 { return [0,65535,4294901760,4294967295] }; return [0,4294967295]
}
let values = table(8); let i = 0; while i<values.length { print(values[i]); i = i+1 }
function kind(value: Integer): Integer { return value }
function call(): Integer { return 0 }
function example(arg: Integer) { let k = kind(arg); if k==9 || k==10 || k==5 { if call()==0 { if k==9 || k==10 { print(arg) } else { fail("bad kind") } } } }; example(10)
'''
        self.executes(source, ''.join(f'{value}\n' for value in table)+'10\n')

    def test_terminal_helper_prevents_all_following_failure_paths(self):
        self.executes('''function done() { print("done"); exit(0) }
function run(x: Integer, a: Integer) { if x<a { fail("first") }; done(); if x!=a { fail("second") }; fail("last") }
run(1,0)
''', 'done\n')

    def test_unused_zero_division_assignment_still_traps(self):
        self.executes('''let i = 0
let j = 0
let k = i/j
print("unreachable")
''', '', 1, 'Minyar stopped: an Integer cannot be divided by zero.\n')

    def test_offset_outparam_nested_call_and_cursor_minus_one(self):
        self.executes('''record Marker { value: Text }
function base(marker: Marker, offset: List<Integer>): Marker { offset[0] = 0; return marker }
function build(marker: Marker, offset: Integer): Marker { print(offset); return marker }
function reference(marker: Marker, offset: Integer): Marker { let position = [-1]; marker = base(marker,position); return build(marker,position[0]+offset/8) }
print(reference(Marker { value: "marker" },32).value)
function load(p: List<Integer>): Integer { return p[0] }
function result(i: Integer, state: List<Integer>) { state[0] = i }
function forwarded(global: List<Integer>, state: List<Integer>): Integer { let alias = global; alias[0] = 1; result(load(global),state); return 0 }
let global = [0]; let state = [0]; print(forwarded(global,state)); print(state[0])
function cursor(a: Integer): Character { let text = "0123456789"; let output = 0; output = output+a; output = output-1; return text[output] }; print(cursor(2))
''', '4\nmarker\n0\n1\n1\n')

    def test_early_returns_and_false_guards_do_not_speculate_invalid_reads(self):
        self.executes('''function early(i: Integer) { if i==12 { return }; if i!=17 { if i==15 { return }; fail("bad value") } }; early(15); print("continued")
function huge(a: Integer): Integer { let values = [0,0]; let f = 0; if a==131072 { f = values[a] }; return f }; print(huge(0))
let a = 0; let b = 0; let c = 0; let d = 0; let values = [0]
while b<2 { a = 0; if b==28378 { a = values[b] }; if !(d!=0 || b!=0) { while c!=0 { } }; b = b+1 }; print(a); print(b)
record Descriptor { sign: Integer; used: Integer; digits: List<Integer> }
function used(a: Descriptor, b: Integer): Integer { if a.sign==1 { return -1 }; if a.used>1 { return 1 }; if a.digits[0]>b { return 1 }; if a.digits[0]<b { return -1 }; return 0 }
print(used(Descriptor { sign: -1; used: 2; digits: [] },0))
function optional(self: List<Integer>, present: Boolean) { print("foo\n"); if present { let again = true; while again { self[0] = self[0]+1; if self[0]==6 { again = false }; if self[0]==7 { fail("unreachable") } } } }
let y = [0]; optional(y,false); print(y[0])
''', 'continued\n0\n0\n2\n1\nfoo\n\n0\n')

    def test_division_before_alias_decrement_and_linear_combination(self):
        self.executes('''record Descriptor { divisor: Integer; target: List<Integer> }
function divide(s: Descriptor): Integer { let a = 1; a = a/s.divisor; let target = s.target; target[a] = target[a]-1; print(target[a]); return a }
let val = [1]; let s = Descriptor { divisor: 2; target: val }; val[0] = divide(s); print(val[0])
record Coefficients { x: Integer; y: Integer }
function adjust(x: List<Integer>, y: List<Integer>, coefficient: Coefficients) { x[0] = coefficient.x*x[0]+coefficient.y*y[0] }
let x = [1]; let y = [1]; adjust(x,y,Coefficients { x: 1; y: 1 }); print(x[0]); print(y[0])
function decrement(a: Integer): Boolean { a = a-1; print(a); return a>0 }; print(decrement(2147483648))
function local(p: List<Integer>): Boolean { let x = p[0]; x = x-1; print(x); return x<0 }; let p = [-10]; print(local(p)); print(p[0])
let c = 2863311530; let c3 = 2863311530*3; print(c*3); print(c3)
''', '0\n0\n2\n1\n2147483647\ntrue\n-11\ntrue\n-10\n8589934590\n8589934590\n')

    def test_matrix_derived_stores_preserve_last_collision_and_all_cells(self):
        self.executes('''let first: List<List<Integer>> = []; let second: List<List<Integer>> = []; let i = 0
while i<4 { let a: List<Integer> = []; let b: List<Integer> = []; let j = 0; while j<4 { a.add(i*4+j); b.add(i*4+j); j = j+1 }; first.add(a); second.add(b); i = i+1 }
let row = second[1]; row[0] = second[0][1]
let data: List<Integer> = []; i = 0; while i<64 { data.add(-1); i = i+1 }
i = 0; while i<3 { let j = 0; while j<4 { if first[i+1][j]>first[i][j] { data[second[i][j]] = i }; j = j+1 }; i = i+1 }
i = 0; while i<64 { print(data[i]); i = i+1 }; print(data[second[0][1]])
''', ''.join(f'{value}\n' for value in [0,1,0,0,-1,1,1,1,2,2,2,2]+[-1]*52)+'1\n')

    def test_outparam_dispatch_self_store_and_condition_assignment_effects(self):
        self.executes('''function flag(position: Integer, state: List<Integer>): Integer { state[0] = 1; if position<=0 { return 1 }; return 0 }
let flagState = [0]; print(flag(1,flagState)); print(flagState[0])
function selfStore(s: List<Integer>): Integer { if s[0]==0 { s[1+s[1]] = s[1]; return 1 }; return 0 }; let s = [0,0]; print(selfStore(s)); print(s[0]); print(s[1])
function oldDepth(value: List<Integer>) { value[0] = 8 }
function depth(): Integer { let old = [0]; oldDepth(old); let new = 17; if old[0]==8 || old[0]==500 { new = 8 } else { if old[0]==5000 { new = 500 } }; return new-old[0] }; print(depth())
function branch(y: Integer): Integer { if y==1 { return 1 }; return 0 }; print(branch(1))
function zero(s: List<Integer>) { s[0] = 0 }
function index(c: List<Integer>): Integer { c[0] = 0; print("index"); return c[0] }
function selected(s: List<Integer>, x: List<Integer>): Character { print("value"); if s[0]==0 { x[0] = 1; return "a"[0] }; x[0] = 2; return "b"[0] }
let s2 = [-1]; let c = [-1]; let x = [0]; let a = ["c"[0]]; zero(s2); a[index(c)] = selected(s2,x); print(a[0]); print(c[0]); print(x[0])
''', '0\n1\n1\n0\n0\n0\n1\nindex\nvalue\na\n0\n1\n')

    def test_mutated_loop_bound_flat_row_views_and_generated_stride(self):
        self.executes('''function mutate(bar: List<Integer>, output: List<Integer>) { let foo = 2; let index = 0; while foo>bar[0] { foo = foo-bar[0]; output[index] = foo; index = index+1; bar[0] = 1 }; print(foo); print(index) }
let bar = [0]; let output = [0,0]; mutate(bar,output); print(output[0]); print(output[1]); print(bar[0])
record View { values: List<Integer>; offset: Integer }
function rows(stride: Integer) { let m: List<Integer> = []; let i = 0; while i<175 { m.add(17); i = i+1 }; let p: List<View> = []; i = 0; while i<25 { p.add(View { values: m; offset: stride*i }); i = i+1 }; let row = p[1]; let values = row.values; values[row.offset] = 0; print(m[7]); print(m[6]); print(m[8]) }; rows(7)
function generate(out: List<Integer>, size: Integer, low: Integer, high: Integer) { let j = 0; while j<size { out[j] = j*(high-low); j = j+1 } }
function run() { let a = [-1,-1]; generate(a,2,0,1); print(a[0]); print(a[1]) }; run()
''', '1\n2\n2\n1\n1\n0\n17\n17\n0\n1\n')

    def test_record_text_and_fresh_returns_preserve_values_across_calls(self):
        self.executes('''record TextFlag { text: Text; flag: Integer }
function check(p: TextFlag): Boolean { if p.flag!=99 { return false }; return p.text=="0123456789" }; print(check(TextFlag { text: "0123456789"; flag: 99 }))
record Field { x: Integer }
function replace(original: Field): Field { return Field { x: 17 } }
let original = Field { x: 13 }; let result = replace(original); print(original.x); print(result.x)
function copy(original: Field): Field { return Field { x: original.x } }; print(copy(Field { x: 100 }).x)
function empty(): Text { print("unreachable"); return "" }
function text(v: Integer): Text { if v==0 { return empty() }; return "abc" }; print(text(1))
function conjunction(b: Integer, c: Integer): Integer { if b!=0 && b!=1 && c!=0 { b = 0 }; return b }; print(conjunction(1,2))
function observe(v: Integer) { print(v) }; let v = 3735928559; observe(v); observe(v)
function g(calls: List<Integer>): Integer { calls[0] = calls[0]+1; return 0 }
function update(a: List<Integer>, b: Integer, calls: List<Integer>): Integer { if g(calls)== -1 { return 0 }; a[0] = g(calls); if b>=1 { print(a[0]) }; return 0 }
let a = [1]; let calls = [0]; print(update(a,0,calls)); print(a[0]); print(calls[0])
''', 'true\n13\n17\n100\nabc\n1\n3735928559\n3735928559\n0\n0\n2\n')

    def test_old_index_remainders_and_signed_comparison_combinations(self):
        self.executes('''function next(values: List<Integer>, cursor: List<Integer>): Integer { let index = cursor[0]; cursor[0] = cursor[0]+1; return values[index] }
let cursor = [0]; print(next([3,4],cursor)%8); print(cursor[0])
function boundary(value: Integer): Integer { let bound = -4611686016279904256; if value<bound { return 1 }; return 2 }; print(boundary(-4611686018427387903))
function repeated(): Integer { let value = 7; if value/7==1 { return value/7 }; return 0 }; print(repeated())
function zero(x: Integer): Integer { let y = 0; if x==0 { y = -y }; return y }; print(zero(0))
function difference(values: List<Integer>): Integer { let j = values[1]; let i = values[0]-j; let x = 0; let y = 0; if i<0 { x = 1; y = -i } else { x = 0; y = i }; return x+y }; print(difference([8,9]))
function remainder(a: Integer): Integer { let value = a%2%2%2%2%2%2%2%2; if value==0 { return 0 }; if value==1 { return 1 }; return -1 }; print(remainder(1))
function wide(x: Integer): Boolean { return x>4294967295 || x< -2147483648 }; print(wide(0))
function positive(x: Integer): Integer { if x>0 || x==0 { return 0 }; return -1 }; print(positive(0)); print(positive(-1))
function complementary(x: Integer): Integer { if x!=0 || x==0 { return 0 }; return 1 }; print(complementary(3))
function contradictory(a: Integer): Boolean { return (a>=0 && a<=10) && !(a>=0) }; print(contradictory(0))
function narrow(a: Integer): Integer { if a<1000 && a>2000 { return 1 }; return 0 }; print(narrow(0)); print(narrow(0))
''', '3\n1\n1\n1\n0\n2\n1\nfalse\n0\n-1\n0\nfalse\n0\n0\n')

    def test_postdecrement_and_alternating_conditions_preserve_call_counts(self):
        self.executes('''function call(count: List<Integer>) { count[0] = count[0]+1 }
function old(value: List<Integer>): Boolean { let before = value[0]; value[0] = value[0]-1; return before!=0 }
function run(i: Integer) { let value = [i]; let calls = [0]; call(calls); while old(value) { call(calls) }; print(calls[0]); print(value[0]) }; run(10)
function toggle(state: List<Integer>): Boolean { state[0] = 1-state[0]; state[1] = state[1]+1; return state[0]!=0 }
function trap(): Boolean { fail("unreachable") }
function alternating(fname: Integer, part: Boolean, nparts: Boolean, state: List<Integer>) {
if fname!=0 { if nparts { fail("initial") } } else { fname = 2 }
while toggle(state) { if nparts && trap() { fail("body") } }; if nparts { fail("final") }; print(fname)
}
let state = [0,0]; alternating(0,true,false,state); print(state[0]); print(state[1])
function gf(count: List<Integer>): Integer { count[0] = count[0]+1; return 0 }
function oldLess(k: List<Integer>, i: Integer): Boolean { let old = k[0]; k[0] = old+1; return old<i }
let count = [0]; let i = gf(count); i = i+1; let k = 0; if i==0 { k = -0 } else { k = i+0 }; print(i)
let cell = [1]; let j = -1; if cell[0]<=i { j = gf(count); while oldLess(cell,i) { j = gf(count) } }; print(j); print(cell[0]); print(count[0])
''', '11\n-1\n2\n0\n2\n1\n0\n2\n2\n')

    def test_character_alias_reloads_and_delimiter_scan_offsets(self):
        self.executes('''function store(x: List<Character>) { x[0] = "x"[0] }
let x = ["\u0000"[0]]; let i = 0; while i<100 { store(x); print(x[0]); i = i+1 }
function access(text: Text, i: Integer): Character { return text[i-2000000000] }; print(access("deadbeef",2000000000))
function old(value: List<Integer>): Boolean { let before = value[0]; value[0] = before-1; return before!=0 }
function beginning(tab: Character, text: Text, limit: Integer, words: List<Integer>, chars: Integer): Integer {
let position = 0; while position<limit && old(words) { while position<limit && text[position]!=tab { position = position+1 }; if position<limit { position = position+1 } }; if position+chars<=limit { position = position+chars }; return position
}
let words = [1]; print(beginning(":"[0],":ab",3,words,1)); print(words[0])
function chosen(buf: List<Character>): Character { let x = 80; let c = "b"[0]; if x!=0 { c = "a"[0] }; buf[0] = c; return c }; let buf = ["z"[0]]; print(chosen(buf)); print(buf[0])
function text(flag: Boolean): Text { let selected = "\u0000right\n"; if flag { selected = "\u0000wrong\n" }; return selected.slice(1,selected.length) }; let result = text(false); print(result[0]); print(result[1]); print(result)
''', 'x\n'*100+'d\n2\n-1\na\na\nr\ni\nright\n\n')

    def test_full_prefix_sentinel_and_preincrement_fill_domains(self):
        self.executes('''function fill(a: List<Integer>, b: List<Integer>, n: Integer) { let i = 0; while i<n { a[i] = -1; i = i+1 }; i = 0; while i<32767 { b[i+1] = -1; i = i+1 } }
let a: List<Integer> = []; let b: List<Integer> = []; let i = 0; while i<32768 { a.add(91); b.add(93); i = i+1 }; b[0] = 0; fill(a,b,32768)
print(b[0]); i = 0; while i<32768 { if a[i]!= -1 { fail("first fill") }; if i>0 && b[i]!= -1 { fail("offset fill") }; i = i+1 }; print(i)
function lookup(pattern: Text, table: List<Integer>): Integer { let m = pattern.length-1; m = m+1; let i = 0; while i<257 { table[i] = m; i = i+1 }; return m }
let table: List<Integer> = []; i = 0; while i<257 { table.add(-1); i = i+1 }; print(lookup("bind",table)); i = 0; while i<257 { print(table[i]); i = i+1 }
''', '0\n32768\n4\n'+'4\n'*257)

    def test_loop_carried_values_and_empty_body_exit_state(self):
        self.executes('''function effect(value: List<Integer>) { value[0] = 1 }
function empty(value: List<Integer>) { let flag = 0; if flag==0 { }; effect(value) }; let value = [0]; empty(value); print(value[0])
let k = 0; let j = -1; let i = 0; while i<2 { if k!=0 { print(j); if j!=2 { fail("lost value") } } else { j = 2; k = k+1 }; i = i+1 }; print(k)
function identity(x: Integer): Integer { return x }; let x = 1; let first = identity(x); x = 2; let second = identity(x); print(first); print(second)
i = 1; while i<100 { i = i+1 }; print(i)
function check(n: Integer) { print(n) }; let n = 1000; check(n); i = 0; while i<1 { check(n); n = 666; i = i+1 }; print(n)
let b = [0]; i = 0; if b[0]==0 { b[0] = i; i = i+1; while i<10 { b[0] = i; i = i+1 } }; print(b[0]); print(i)
function chooseLast(result: List<Integer>): Integer { let i = 0; while i<7 { if i==7-1 { result[0] = 4044 } else { result[0] = 4078 }; print(result[0]); i = i+1 }; return result[0] }
let result = [0]; print(chooseLast(result)); print(result[0])
''', '1\n2\n1\n1\n2\n100\n1000\n1000\n666\n9\n10\n'+'4078\n'*6+'4044\n4044\n4044\n')

    def test_iterative_maximum_clear_and_incremented_record_store(self):
        self.executes('''let x = [0,1,2,3,4,5,6,7,8,9]; let iterations = 0; let scans = 0; let active = true
while active { let maximum = 0; let selected = -1; let i = 0; while i<10 { if x[i]>maximum { maximum = x[i]; selected = i }; i = i+1 }; scans = scans+1; if maximum==0 { active = false } else { x[selected] = 0; iterations = iterations+1; if iterations>10 { fail("limit") } } }
print(iterations); print(scans); let i = 0; while i<10 { print(x[i]); i = i+1 }
record Pair { first: Integer; second: Integer }
function store(arg: Pair) { let buffer = [Pair { first: 0; second: 0 }]; let i = 0; while i<1 { buffer[i] = arg; i = i+1 }; print(buffer[0].first); print(buffer[0].second); print(i) }; store(Pair { first: 1; second: 2 })
''', '9\n10\n'+'0\n'*10+'1\n2\n1\n')

    def test_palette_three_stores_preserve_all_48_positions(self):
        self.executes('''record Data { palette: List<Integer> }
record Console { data: Data }
function reset(consoles: List<Console>, selected: Integer, red: List<Integer>, green: List<Integer>, blue: List<Integer>) {
let j = 0; let k = 0; let palette = consoles[selected].data.palette
while j<16 { palette[k] = red[j]; k = k+1; palette[k] = green[j]; k = k+1; palette[k] = blue[j]; k = k+1; j = j+1 }; print(k)
}
let palette: List<Integer> = []; let red: List<Integer> = []; let green: List<Integer> = []; let blue: List<Integer> = []; let i = 0
while i<48 { palette.add(17); i = i+1 }; i = 0; while i<16 { red.add(0); green.add(0); blue.add(0); i = i+1 }
reset([Console { data: Data { palette: palette } }],0,red,green,blue)
i = 0; while i<48 { print(palette[i]); i = i+1 }
''', '48\n'+'0\n'*48)

    def test_boundary_division_pairs_match_independent_constant_and_parameter_oracles(self):
        import shlex
        from regressions import CLANG, ROOT
        minimum, maximum = -(1 << 63), (1 << 63)-1
        magnitudes = [1,2,3,7,31,32,33,(1<<31)-1,1<<31,(1<<31)+1,
                      (1<<32)-1,1<<32,(1<<32)+1,(1<<62)-1,1<<62,(1<<62)+1,maximum]
        divisors = [minimum] + [sign*n for n in magnitudes for sign in (-1,1)]
        values = sorted({minimum,minimum+1,maximum,maximum-1,0,*(sign*n+delta for n in magnitudes for sign in (-1,1) for delta in (-1,0,1) if minimum<=sign*n+delta<=maximum)})
        source = ['function paired(a: Integer, b: Integer) { print(a/b); print(a%b) }']
        expected = []
        for index, divisor in enumerate(divisors):
            source.append(f'function constant{index}(a: Integer) {{ print(a/({divisor})); print(a%({divisor})) }}')
            safe = [a for a in values if (a,divisor)!=(minimum,-1)]
            source.append(f'let values{index} = ['+','.join(map(str,safe))+']')
            source.append(f'let i{index} = 0; while i{index}<values{index}.length {{ constant{index}(values{index}[i{index}]); paired(values{index}[i{index}],{divisor}); i{index} = i{index}+1 }}')
            for value in safe:
                quotient = (abs(value)//abs(divisor))*(-1 if (value<0)!=(divisor<0) else 1)
                remainder = value-quotient*divisor
                expected.extend([quotient,remainder,quotient,remainder])
        output = ''.join(f'{value}\n' for value in expected)
        llvm = self.executes('\n'.join(source),output)
        if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1':
            executable = llvm.with_suffix('.lto')
            linked = self.evidence.run([CLANG,'-O2',*shlex.split(os.environ.get('MINYAR_TEST_LTO_FLAGS','-flto')),
                '-DMINYAR_SYSTEM_HEAP=1','-Wno-override-module',llvm,ROOT/'runtime/minyar_runtime.c','-o',executable],timeout=60,phase='link-lto')
            self.assertEqual(linked.returncode,0,linked.stderr)
            actual = self.evidence.run([executable],timeout=10,phase='execute-lto')
            self.assertEqual((actual.returncode,actual.stdout,actual.stderr),(0,output.encode(),b''))
        definitions = ['function divide(a: Integer,b: Integer): Integer { return a/b }',
                       'function remainder(a: Integer,b: Integer): Integer { return a%b }']
        self._execute_fatal_branches(definitions,[(name,f'print({expression})','', 'Minyar stopped: this Integer division is outside the supported range.\n') for name,expression in [
            ('divide','divide(-9223372036854775808,-1)'),('remainder','remainder(-9223372036854775808,-1)'),
            ('literalDivide','-9223372036854775808 / -1'),('literalRemainder','-9223372036854775808 % -1')]])

    def test_nested_zero_divisions_preserve_prior_stores_and_failure_precedence(self):
        definitions = ['function zeros(n: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i<n { a.add(0); i = i+1 }; return a }',
'''function split(first: Boolean) { let x = 20; let y = 0; let z = 10; let values = zeros(10); let i = 9
while i<99 { let j = 3; while j<100 { let k = 1; while k<2 {
if first { print("first"); x = -65229/y; print("index"); z = values[5]/8 } else { print("second"); y = -38077/y; print("after"); z = y/9 }
y = 8; z = z+k; k = k+1 }; j = j+1 }; i = i+2 } }
function invariant() { let values = zeros(100); let i1 = 0; let index = 0; while index<values.length { let i4 = values[index]; i4 = i1; print("divide"); values[0] = 1/i4; print("index"); i4 = values[2/i4]; index = index+1 } }
function stored() { let x = 0; let y = 0; let values = zeros(400); let flags: List<Boolean> = []; let at = 0; while at<400 { flags.add(false); at = at+1 }
let i = 0; while i<10000 { let j = 1; while j<13 { let k = 1; while k<2 { values[1] = 7; print(values[1]); x = 3/y; flags[x/30] = true; print("flag"); k = k+1 }; j = j+1 }; i = i+1 } }
function rangeRemainder() { let a = zeros(400); let warm = 0; while warm<50000 { warm = warm+1 }; let zero = a[5]; let i = 1; while i<3 { let j = 1; while j<3 { let k = 2; while k>i { let value = a[i+1]%k; print(value); value = a[i-1]%zero; print("late index"); value = a[k-1]; k = k-3 }; j = j+1 }; i = i+1 } }
''']
        self._execute_fatal_branches(definitions,[(name,call,prefix,'Minyar stopped: an Integer cannot be divided by zero.\n') for name,call,prefix in [
            ('first','split(true)','first\n'),('second','split(false)','second\n'),('invariant','invariant()','divide\n'),('store','stored()','7\n'),('remainder','rangeRemainder()','0\n')]])

    def test_countdown_division_and_remainder_stop_before_zero_exit(self):
        expected = []
        for division in (True,False):
            for i in range(5,25):
                for j in range(50,1,-2):expected.append(20//j if division else 20%j)
            expected.extend([0,10 if division else 0])
        self.executes('''function run(division: Boolean) { let accumulator = 2; let x = 0; let i = 5
while i<25 { let j = 50; while j>1 { if division { x = 20/j } else { x = 20%j }; print(x); accumulator = accumulator/i; let k = 3; while k>1 { if i%4+22==22 { if j%10==83 { x = x+5 } }; k = k-1 }; j = j-2 }; i = i+1 }; print(accumulator); print(x)
}
run(true); run(false)
''', ''.join(f'{value}\n' for value in expected))

    def test_square_boundary_signs_and_constant_multipliers_keep_checked_traps(self):
        source = ['function product(a: Integer,b: Integer): Integer { return a*b }',
                  'function maxProduct(a: Integer): Integer { return a*9223372036854775807 }']
        expected = []
        for left in (-3037000499,3037000499):
            for right in (-3037000499,3037000499):
                source += [f'print(product({left},{right}))',f'print(({left})*({right}))']
                expected.extend([left*right]*2)
        source.append('print(maxProduct(1))'); expected.append((1<<63)-1)
        self.executes('\n'.join(source),''.join(f'{value}\n' for value in expected))
        cases=[]
        for left in (-3037000500,3037000500):
            for right in (-3037000500,3037000500):
                for shape,expression in [('runtime',f'product({left},{right})'),('literal',f'({left})*({right})')]:
                    cases.append((f'{left}-{right}-{shape}',f'print({expression})','','Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self._execute_fatal_branches(source[:1],cases)

    def test_scaled_negative_index_fails_bounds_before_later_overflow(self):
        self.executes('''let a = [0,0,0,0,0,0,0,0,0,0]
let i = 1
while i<100 { print(i); print(a[(-9223372036854775808+2)*i]); i = i+2 }
''', '1\n',1,'Minyar stopped: List position -9223372036854775806 is outside its length of 10.\n')

    def test_even_range_stores_and_early_limit_return_preserve_full_domains(self):
        self.executes('''function zeros(n: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i<n { a.add(0); i = i+1 }; return a }
function fill(stop: Integer, array: List<Integer>, barrier: List<Integer>) { let i = 8; while i<stop { if i%2==0 { array[i] = 42 } else { barrier[0] = 66 }; i = i+1 } }
let large = zeros(1000); let barrier = [-1]; fill(1000,large,barrier); let i = 0; while i<1000 { print(large[i]); i = i+1 }; print(barrier[0])
let small = zeros(10); barrier[0] = -1; let j = 0; while j<11 { fill(j,small,barrier); j = j+1 }; i = 0; while i<10 { print(small[i]); i = i+1 }; print(barrier[0])
function limit(flag: Boolean): Integer { let bound = 1000; if flag { bound = 9223372036854775807 }; let i = 0; let count = 0; while i<bound { i = i+3; count = count+1; if flag { print(i); return count } }; print(i); return count }; print(limit(true)); print(limit(false))
''', ''.join(f'{42 if i>=8 and i%2==0 else 0}\n' for i in range(1000))+'66\n'+''.join(f'{42 if i==8 else 0}\n' for i in range(10))+'66\n3\n1\n1002\n334\n')

    def test_unreachable_divisor_branch_and_sinking_division_trace(self):
        self.executes('''function top(flag: Boolean,d: Integer,f: Integer): Integer { let a: List<Integer> = []; let j = 0; while j<400 { if j%2==0 { a.add(8+j) } else { a.add(8-j) }; j = j+1 }; let b = 4; let c = 4
if flag { } else { if flag { if flag { if flag { let i = 7; while i>1 { if flag { c = b/i; b = 9/i }; i = i-1 } } } } else { a[d] = a[d]*16 } }
let sum = 0; j = 0; while j<a.length { sum = sum+a[j]/(j+1)+a[j]%(j+1); j = j+1 }; print(sum); return f+c+sum }
let repeat = 0; while repeat<10 { print(top(false,3,0)); repeat = repeat+1 }
let field = 1; let x = 1; let q = 0; let a: List<Integer> = []; let j = 0; while j<100 { a.add(0); j = j+1 }; let y = 1; let i = 1
while i<10 { j = 1; while j<88 { a[1] = x; j = j+1 }; y = field-q; print(y); y = a[2]/y; y = 5/field; print(y); field = field-8; if y==3 { }; i = i+1 }; print(field); print(a[1])
function peeled(stop: Integer,res: Integer,first: Boolean,never: Boolean): Integer { if stop<1 { stop = 1 }; let i = stop; while i>=1 { print(i); res = res/i; if never { }; if first { return res }; first = true; i = i-1 }; return res }
print(peeled(1000,0,false,false)); print(peeled(1,0,false,false))
''', '-36802\n-36798\n'*10+''.join(f'{1-8*i}\n{5 if i==0 else 0}\n' for i in range(9))+'-71\n1\n1000\n999\n0\n1\n0\n')

    def test_derived_zero_remainders_and_negated_zero_products_keep_first_trap(self):
        definitions = ['function remainder(x: Integer): Integer { return 1%(x%x) }',
                       'function product(a: Integer,b: Integer): Integer { return (-a)*(-b) }']
        cases = [('runtimeRemainder','print(remainder(1))','','Minyar stopped: an Integer cannot be divided by zero.\n'),
                 ('literalRemainder','print(1%(1%1))','','Minyar stopped: an Integer cannot be divided by zero.\n')]
        for name,expression in [('left','product(-9223372036854775808,0)'),('right','product(0,-9223372036854775808)'),
                                ('literalLeft','(-(-9223372036854775808))*(-0)'),('literalRight','(-0)*(-(-9223372036854775808))')]:
            cases.append((name,f'print({expression})','','Minyar stopped: this Integer calculation is outside the supported range.\n'))
        self._execute_fatal_branches(definitions,cases)

    def test_dead_modulo_body_and_early_return_preserve_module_state(self):
        self.executes('''function dead(field: List<Integer>, skip: Boolean) { let a: List<Integer> = []; let i = 0; while i<400 { a.add(-13265); i = i+1 }; let divisor = -14; i = 13
while i<315 { if !skip { let d = 5; while d<83 { d = d+1 }; let j = 4; while j<83 { let l = 1; while l<2 { l = l+1 }; skip = skip; field[0] = field[0]%(divisor+1); divisor = d; j = j+1 } }; i = i+1 }
}
let field = [-189]; let i = 0; while i<10 { dead(field,true); print(field[0]); i = i+1 }
function constant(): Integer { return 65 }
function guarded(field: List<Integer>): Integer { if field[0]<=0 { return -109 }; field[0] = 4; while constant()>=0 { field[0] = 4 }; return -109 }
field[0] = -1; print(guarded(field)); print(field[0]); print(constant())
''', '-189\n'*10+'-109\n-1\n65\n')

    def test_array_store_domain_and_last_element_overwrite(self):
        self.executes('''let values: List<Integer> = []; let i = 0; while i<400 { values.add(0); i = i+1 }
i = 1; values[i] = i; i = i+1; while i<355 { values[i] = i; i = i+1 }; i = 0; while i<400 { print(values[i]); i = i+1 }
function last(values: List<Integer>): Integer { let result = 0; let i = 0; while i<values.length { result = values[i]; i = i+1 }; return result }
print(last([0,0,0,0,0,0,0,0,0])); print(last([1,2,3,4,5,6,7,8,91]))
''', ''.join(f'{i if 1<=i<355 else 0}\n' for i in range(400))+'0\n91\n')

    def test_negative_search_result_guards_both_reads_and_mutation(self):
        self.executes('''function index(i: Integer, array: List<Integer>): Integer { if i==0 { return 0 }; let n = 0; while n<array.length { if i<array[n] { return n }; n = n+1 }; return -1 }
function run(i: Integer,array: List<Integer>): Integer { let result = 0; i = index(i,array); if i>=0 { if array[i]!=0 { result = result+1 } }; if i != -1 { array[i] = array[i]+1 }; return result }
let array = [0,0,0,0,0,0,0,0,0,0,0,0]; let total = 0; let i = 0; while i<100000 { total = total+run(10,array); i = i+1 }; print(total); i = 0; while i<array.length { print(array[i]); i = i+1 }
''', '0\n'*13)

    def test_nested_multiply_add_loop_stops_at_first_checked_overflow(self):
        expected = []
        value = 17
        for j in range(1,11):
            expected.extend([17,j,value])
            if j<10:value = value*17*(j+1)
        self.executes('''function run(field: Integer): Integer { let v = 0; let k = 0; let i = 17
while i<311 { v = field; let j = 1; let active = true; while active { print(i); print(j); print(v); v = v*i; v = v+j*v; k = k+1; while k<1 { k = k+1 }; j = j+1; active = j<13 }; i = i+3 }; return v
}
print(run(17))
''', ''.join(f'{n}\n' for n in expected),1,'Minyar stopped: this Integer calculation is outside the supported range.\n')

    def test_zero_trip_division_bodies_keep_arrays_and_counters_unchanged(self):
        self.executes('''function zeros(n: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i<n { a.add(0); i = i+1 }; return a }
let a = zeros(400); let i7 = 9; let i9 = 138; let i6 = 7
while i6>1 { let i8 = i6; while i8<4 { a[i8] = 52691/i8; i7 = a[i8+1]%i9; i7 = 412419036/a[i8]; i9 = i9+13; i8 = i8+1 }; i6 = i6-3 }; print(i7)
let at = 0; while at<400 { print(a[at]); at = at+1 }
function zeroTrip(values: List<Integer>,count: List<Integer>): Integer { let i2 = 2; let i17 = 3; let i15 = 1
while i15<100000 { let i16 = i15; while i16<1 { values[i16] = 5/values[6]; i17 = values[5]/i2; i2 = i15; count[0] = count[0]-i15; i16 = i16+1 }; i15 = i15+1 }; return i17 }
let values = zeros(10); let count = [0]; print(zeroTrip(values,count)); print(count[0]); at = 0; while at<10 { print(values[at]); at = at+1 }
function absent(i: Integer,index: Integer,buffer: List<Integer>) { while i>=65536 { i = i/100; index = index-1; buffer[index] = 0; index = index-1; buffer[index] = 1 }; print(i); print(index) }
let empty: List<Integer> = []; absent(0,0,empty)
''', '9\n'+'0\n'*400+'3\n0\n'+'0\n'*12)

    def test_repeated_fills_and_zero_limit_strides_preserve_field(self):
        self.executes('''function fill(a: List<Integer>, value: Integer) { let i = 0; while i<a.length { a[i] = value; i = i+1 } }
function noop() { }
let i = 1; let repeat = 0; while repeat<200000 { let a = [0,0]; let b = i; fill(a,1); fill(a,1+b); if a[0]!=2 || a[1]!=2 { fail("fill") }; noop(); repeat = repeat+1 }; print(repeat)
record Field { value: List<Integer> }
function zero(limit: Integer,stride: Integer,a: Field) { let i = 0; while i<100 { let j = 0; let active = true; while active && j<limit { let cell = a.value; cell[0] = cell[0]+34; if j>0 { active = false } else { j = j+stride } }; i = i+1 } }
let a = Field { value: [0] }; zero(0,2147483648,a); print(a.value[0]); zero(0,1,a); print(a.value[0])
''', '200000\n0\n0\n')

    def test_empty_allocations_and_checksums_precede_exact_bounds_failure(self):
        self.executes('''function checksum(a: List<Integer>): Integer { let sum = 0; let j = 0; while j<a.length { sum = sum+a[j]/(j+1)+a[j]%(j+1); j = j+1 }; return sum }
function nested(a: List<List<Integer>>): Integer { let sum = 0; let j = 0; while j<a.length { sum = sum+checksum(a[j]); j = j+1 }; return sum }
function make(size: Integer,seed: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i<size { a.add(0); i = i+1 }; i = 0; while i<a.length { if i%2==0 { a[i] = seed+i } else { a[i] = seed-i }; i = i+1 }; return a }
function helper(size: Integer): Integer { let values = make(size,0); let rows: List<List<Integer>> = []; let i = 0; while i<size { rows.add(make(size,0)); i = i+1 }; return nested(rows) }
let p = make(0,0); let empty: List<List<Integer>> = []; print(checksum(p)); print(nested(empty))
let d = 5; let allocations = 0; while d<388 { if helper(0)!=0 { fail("checksum") }; let s = 3; while s<66 { make(0,9); allocations = allocations+1; s = s+1 }; d = d+1 }; print(d); print(allocations)
let o = 6; while o>2 { p[o] = 0; o = o-1 }
''', '0\n0\n388\n24129\n',1,'Minyar stopped: List position 6 is outside its length of 0.\n')

    def test_inequality_loop_exits_preserve_both_start_ranges(self):
        self.executes('''function increasing(a: List<Integer>): Integer { let j = 0; let result = 0; let i = 0; while i<2 { let active = true; while active && j!=5 { if j>=20 { active = false } else { print(j); result = result+a[j]; j = j+1 } }; j = 10; i = i+1 }; return result }
function decreasing(a: List<Integer>): Integer { let j = 10; let result = 0; let i = 0; while i<2 { let active = true; while active && j!=5 { if j<0 { active = false } else { print(j); result = result+a[j]; j = j-1 } }; j = 1; i = i+1 }; return result }
let a: List<Integer> = []; let i = 0; while i<20 { a.add(i); i = i+1 }; print(increasing(a)); print(decreasing(a))
''', ''.join(f'{n}\n' for n in [*range(5),*range(10,20),155,*range(10,5,-1),1,0,41]))

    def test_zero_arguments_bypass_infinite_loops_across_helper_boundaries(self):
        self.executes('''function counted(a: Integer,b: Integer,c: Integer,d: Integer) { if a==0 { return }; while b==0 || c<=0 { }; while true { d = d-1; while d>0 { d = d-1 } } }
function inner(a: Integer,b: Integer,c: Integer) { if a==0 { return }; if b<0 { while b<0 { } }; while true { if c==0 { return } } }
function outer(a: Integer,b: Integer,c: Integer) { inner(a,b,c) }
counted(0,0,0,0); print("counted returned")
let i = 0; while i<10000 { outer(0,0,0); i = i+1 }; print(i)
function nested(flag: Boolean) { if flag { while true { let i = 1; while i<100 { i = i*2 } } } }; nested(false); print("nested returned")
''', 'counted returned\n10000\nnested returned\n')

    def test_counted_loop_cannot_wrap_past_signed_maximum(self):
        self.executes('''let value = 9223372036854775806
while value != -9223372036854675808 { print(value); if value==0 { fail("unexpected zero") }; value = value+1 }
''', '9223372036854775806\n9223372036854775807\n',1,'Minyar stopped: this Integer calculation is outside the supported range.\n')

    def test_posttest_one_visit_and_divisor_assignment_preserve_all_cells(self):
        self.executes('''function zeros(n: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i<n { a.add(0); i = i+1 }; return a }
function run(b: Boolean,integers: List<Integer>,longs: List<Integer>) {
let outer = 9; let active = true; while active { if !b { let divisor = 1; integers[1] = integers[1]/divisor; let middle = true; while middle { let inner = 1; let once = true; while once { integers[0] = divisor; integers[inner-1] = 8; inner = inner+1; once = inner<1 }; longs[1] = 8; divisor = divisor+1; middle = divisor<145 } }; outer = outer+1; active = outer<173 }; print("")
}
let integers = zeros(400); let longs = zeros(400); let count = 0; while count<10 { run(false,integers,longs); count = count+1 }
let i = 0; while i<400 { print(integers[i]); print(longs[i]); i = i+1 }
integers[1] = 139; run(false,integers,longs); print(integers[1])
''', '\n'*10+''.join(f'{8 if i==0 else 0}\n{8 if i==1 else 0}\n' for i in range(400))+'\n139\n')

    def test_negative_backbranch_and_allocation_lengths_preserve_load_guards(self):
        self.executes('''function backbranch(array: List<Character>,pattern0: List<Character>,pattern1: List<Character>) { let i = 0; let position = 0; let c = array[position]; while i>=0 && (c==pattern0[i] || c==pattern1[i]) { i = i-1; position = position-1; if position != -1 { c = array[position] } }; print(i); print(position); print(array[0]=="\u0000"[0]) }
backbranch(["\u0000"[0]],["\u0000"[0]],["\u0001"[0]])
function counted(flag: Boolean,array2: List<Integer>,flag2: Boolean,start: Integer,stop: Integer): Integer { let array = [0,0]; if flag { array = [0] }; let len = array.length; let value = 1; let j = start; while j<stop { let i = 0; let active = true; while active && i<len { if i>0 { if flag2 { active = false } else { value = value*array2[i+j] } }; i = i+1 }; j = j+1 }; return value }
print(counted(true,[0,0,0,0,0,0,0,0,0,0],false,0,1)); print(counted(false,[0,0,0,0,0,0,0,0,0,0],false,0,1))
''', '-1\n-1\ntrue\n1\n0\n')

    def test_optional_record_checks_preserve_both_load_paths(self):
        self.executes('''record Item { field: Integer }
function run(obj: List<Item>,first: List<Integer>,second: List<Integer>) {
let x = first[17]; print("first17")
if obj.length>0 { let y = 0; let i = 0; while i<1 { y = y+1; i = i+1 }; x = first[y]; print("first1") } else { x = second[18]; print("second18") }
if obj.length>0 { x = second[obj[0].field]; print("second0") }; print(x)
}
let a: List<Integer> = []; let b: List<Integer> = []; let i = 0; while i<20 { a.add(0); b.add(0); i = i+1 }
let empty: List<Item> = []; run(empty,a,b); run([Item { field: 0 }],a,b)
''', 'first17\nsecond18\n0\nfirst17\nfirst1\nsecond0\n0\n')

    def test_false_guards_and_unused_accumulation_keep_exact_exit_state(self):
        self.executes('''function guarded(flag: Boolean,sink: List<Integer>) { let x = 8; let j = 0; let active = true; while active && j<100 { let k = 0; while k<100 { if flag { x = x+k; sink[0] = 42 }; k = k+1 }; if flag { active = false }; j = j+1 }; print(x); print(sink[0]) }
let sink = [0]; guarded(false,sink)
function unused() { let sum = 0; let i = 100000; while i>=0 { sum = sum + -2147483648; i = i-1 } }
function observed(): Integer { let sum = 0; let i = 100000; while i>=0 { sum = sum + -2147483648; i = i-1 }; return sum }
unused(); print(observed())
function falseCall(calls: List<Integer>): Boolean { calls[0] = calls[0]+1; return false }
function split(flag: Boolean,calls: List<Integer>) { while flag { while falseCall(calls) { } }; falseCall(calls); while flag { while true { } } }
let calls = [0]; split(false,calls); print(calls[0])
''', '8\n0\n-214750512283648\n1\n')

    def test_return_before_infinite_nest_releases_fresh_empty_records(self):
        self.executes('''record Empty { }
function guarded(b: Boolean,field: List<Integer>) { if b { let object = Empty { }; return }; let active = true; while active { field[0] = field[0]+1; while field[0]!=1 { field[0] = field[0]-1 }; field[0] = 9; active = field[0]!=5 } }
let field = [0]; let i = 524; while i<19710 { guarded(true,field); i = i+1 }; print(field[0]); print(i-524)
''', '0\n19186\n')

    def test_nested_multiply_add_overwrites_preserve_final_induction_values(self):
        self.executes('''function run(condition: Boolean) { let a = 1; let b = 0; let c = 1; let d = 51
while b<100 { a = a+b*342; c = 0; let active = true; while active && c<100 { d = 0; while d<1 { a = d; d = d+1 }; if condition { active = false } else { c = c+1 } }; a = d*a; b = b+1 }; print(a); print(b); print(c); print(d)
}
let i = 0; while i<10 { run(false); i = i+1 }
''', '0\n100\n100\n1\n'*10)

    def test_million_element_maximum_guard_preserves_alias_over_100_calls(self):
        self._execute_long_workload('''function run(arr: List<Integer>): List<Integer> { let maximum = 0; let at = 0; while at<arr.length { let value = arr[at]; if value>maximum { maximum = value }; at = at+1 }
let counts = [0,0,0,0,0,0,0,0,0,0]; let i = 0; while i<counts.length { let j = 0; while j<counts[i] { j = j+1 }; i = i+1 }
while i<maximum { let j = 0; while j<counts[i] { arr[0] = i; j = j+1 } }; return arr
}
function workload() { let array: List<Integer> = []; let i = 0; while i<1000000 { array.add(0); i = i+1 }; let result = array; i = 0; while i<100 { result = run(array); i = i+1 }; print(i); i = 0; while i<array.length { if array[i]!=0 || result[i]!=0 { fail("changed array") }; i = i+1 }; print(i); result[0] = 42; print(array[0]) }
''', '100\n1000000\n42\n')

    def test_previous_allocation_escapes_while_latest_list_is_replaced(self):
        self.executes('''record State { value: Integer }
function zeros(): List<Integer> { return [0,0,0,0,0,0,0,0,0,0] }
function run(state: State,escaped: List<List<Integer>>,sentinel: Boolean): Integer { let array = zeros(); let count = 1; let j = 0; while j<10 { let i = 1; while i<10 { escaped[0] = array; array = zeros(); count = count+1; if sentinel { array[1] = count }; i = i*2 }; j = j+1 }; let value = state.value; array[0] = value; print(count); print(array[0]); print(array[1]); return value+value }
let escaped: List<List<Integer>> = [[]]; print(run(State { value: 0 },escaped,false)); let old = escaped[0]; print(old.length); print(old[0]); print(old[1])
print(run(State { value: 0 },escaped,true)); print(escaped[0][1]); print(old[1]); let previous = escaped[0]; previous[0] = 73; print(escaped[0][0])
''', '41\n0\n0\n0\n10\n0\n0\n41\n0\n41\n0\n40\n0\n73\n')

    def test_false_wrapper_guards_preserve_infinite_companion_loop_state(self):
        self.executes('''record Empty { }
function longLoop(obj: Empty) { let i = 0; while i<10 { if i>1 { i = i+1 } else { let j = 0; while j<=2 { j = j+1 } } } }
function longWrapper(flag: Boolean,obj: Empty) { if flag { longLoop(obj) } }
function malformed(flag: Integer) { let i = 1; let j = 1; while true { i = 1; if i!=1 { i = i*2; j = j*2; if j>=2 { return } } } }
function malformedWrapper(flag: Boolean) { let i = 1; while i<2 { i = i*2 }; if flag { malformed(i) }; print(i) }
function stores(state: List<Integer>) { while true { let i = 0; while i<10 { state[0] = state[2]; let j = 0; while j<2 { state[2] = state[1]; j = j+1 }; i = i+1 } } }
function storeWrapper(flag: Boolean,state: List<Integer>) { if flag { stores(state) } }
longWrapper(false,Empty { }); print("long returned"); malformedWrapper(false); let state = [0,0,0]; storeWrapper(false,state); print(state[0]); print(state[1]); print(state[2])
''', 'long returned\n2\n0\n0\n0\n')

    def test_self_assignment_and_empty_nests_reach_exact_100000_limit(self):
        self._execute_long_workload('''record Owner { values: List<Integer> }
function zeros(): List<Integer> { let a: List<Integer> = []; let i = 0; while i<400 { a.add(0); i = i+1 }; return a }
function run(owner: List<Owner>,counter: List<Integer>): Boolean { let unused = zeros(); let current = owner[0].values; current[2] = 0; owner[0] = owner[0]; let i = 301; while i>2 { let j = 1; let active = true; while active { let k = i; while k<1 { k = k+1 }; j = j+1; active = j<4 }; i = i-2 }; counter[0] = counter[0]+1; return counter[0]==100000 }
function workload() { let original = zeros(); original[2] = 42; let owner = [Owner { values: original }]; let counter = [0]; let done = false; while !done { done = run(owner,counter) }; print(counter[0]); print(original[2]); let values = owner[0].values; values[3] = 91; print(original[3]) }
''', '100000\n0\n91\n')

    def test_quadratic_guard_and_divisor_loop_preserve_all_store_ranges(self):
        source = '''function zeros(n: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i<n { a.add(0); i = i+1 }; return a }
function fill(flag: Boolean,a: List<Integer>) { let limit = 2147483647; if flag { limit = 1000 }; let i = 0; while i<limit { if i*i>1000000 { return }; a[i] = 34; i = i+4 } }
function show(a: List<Integer>) { let i = 0; while i<a.length { print(a[i]); i = i+1 } }
let a = zeros(1005); fill(true,a); show(a); fill(false,a); show(a); fill(true,a); show(a)
let integers = zeros(400); let booleans: List<Boolean> = []; let at = 0; while at<400 { booleans.add(false); at = at+1 }; let i = 9; let quotient = 577
while i<379 { let divisor = 68; while divisor>3 { booleans[divisor+1] = true; quotient = -42360/divisor; integers[i+1] = 12%15384; divisor = divisor-1 }; i = i+1 }; print(quotient); at = 0; while at<400 { print(integers[at]); print(booleans[at]); at = at+1 }
'''
        expected = ''.join(f'{34 if i%4==0 and i<=end else 0}\n' for end in (996,1000,1000) for i in range(1005))
        expected += '-10590\n'+''.join(f'{12 if 10<=i<=379 else 0}\n'+('true\n' if 5<=i<=69 else 'false\n') for i in range(400))
        self.executes(source,expected)

    def test_empty_delay_loops_and_zero_trip_counts_keep_load_guards(self):
        self.executes('''record Object { field: Integer }
function delayed(obj: Object,stop: Integer,invariant: Integer,unused: List<Integer>): Integer { let result = 0; let i = 0; let active = true
while active && i<stop { let j = 0; while j<10 { let k = 0; while k<10 { k = k+1 }; j = j+1 }; let value = obj.field; let second = value+invariant; if i>1000 { unused[0] = second }; let third = value+(i+invariant); if third>1000 { active = false } else { i = i+1 } }; print(i); return result
}
let unused = [91]; print(delayed(Object { field: 0 },1000,0,unused)); print(unused[0])
let x = 0; let y = 0; let outer = 0; let writes = 0; let i = 6; while i<43 { let j = i; while j<11 { x = y; writes = writes+1; j = j+1 }; outer = outer+1; i = i+1 }; print(outer); print(writes); print(x)
function first(value: Integer,state: List<Integer>) { state[0] = 0; let i = 0; let active = true; while active && i<1 { state[1] = state[1]+1; if value==0 { active = false } else { value = 0; state[2] = state[2]+1; i = i+1 } } }
function third(value: Integer,state: List<Integer>) { let i = 0; let active = true; while active && i<1 { state[1] = state[1]+1; if value==0 { active = false } else { value = 0; state[2] = state[2]+1; i = i+1 } } }
let state = [73,0,0]; first(0,state); print(state[0]); print(state[1]); print(state[2]); state[0] = 91; third(0,state); print(state[0]); print(state[1]); print(state[2])
''', '1000\n0\n91\n37\n15\n0\n0\n1\n0\n91\n2\n0\n')

    def test_post_loop_values_and_two_sided_partial_peel_conditions(self):
        self.executes('''function first(): Integer { let b = 6; let l = 1; while l<9 { b = b+1; l = l+1 }; let x = 0; let i = 1; while i<1000 { let j = 1; while j<2 { x = b+1; j = j+1 }; i = i*2 }; return x }
function second(): Integer { let b = 6; let l = 60; while l<3000 { b = b+33; l = l+3 }; let x = 0; let i = 1; while i<1000 { let j = 1; while j<2 { x = b+1; j = j+1 }; i = i*2 }; return x }
print(first()); print(second())
function increasing(i: Integer): Integer { let condition = true; let count = 0; while condition { i = i+1000; condition = 0<=i && i<10000; count = count+1 }; print(count); return i }
function decreasing(i: Integer): Integer { let condition = true; let count = 0; while condition { i = i-1000; condition = 0<=i && i<10000; count = count+1 }; print(count); return i }
print(increasing(0)); print(decreasing(9999))
''', '15\n32347\n10\n10000\n10\n-1\n')

    def test_reverse_copy_distinguishes_self_alias_from_independent_destination(self):
        self._execute_long_workload('''function zeros(n: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i<n { a.add(0); i = i+1 }; return a }
function copy(src: List<Integer>,dst: List<Integer>) { let i = 0; while i<src.length { dst[dst.length-1-i] = src[i]; i = i+1 } }
function workload() { let large = zeros(1000); let source = zeros(16); let iteration = 0; while iteration<20000 { copy(large,large); let destination = zeros(16); copy(source,destination); let j = 0; while j<16 { if destination[j]!=0 { fail("zero copy") }; j = j+1 }; iteration = iteration+1 }; print(iteration)
let i = 0; while i<1000 { if large[i]!=0 { fail("large zero") }; large[i] = i; i = i+1 }; copy(large,large); i = 0; while i<1000 { let expected = i; if i>=500 { expected = 999-i }; if large[i]!=expected { fail("self copy") }; i = i+1 }; print(large[0]); print(large[999]); print(large[499]); print(large[500])
i = 0; while i<16 { source[i] = i+1; i = i+1 }; let destination = zeros(16); copy(source,destination); i = 0; while i<16 { print(source[i]); print(destination[i]); i = i+1 }
}
''', '20000\n0\n0\n499\n499\n'+''.join(f'{i+1}\n{16-i}\n' for i in range(16)))

    def test_nested_parentheses_preserve_unknown_reference_and_type_error_columns(self):
        for depth in range(4):
            with self.subTest(depth=depth):
                source = 'print('+'('*depth+'missing'+')'*depth+')\n'
                result,llvm = self.compile(source)
                self.assertEqual((result.returncode,result.stdout,result.stderr),
                    (1,'',f"Minyar stopped: line 1, column {7+depth}: I can't find a value named 'missing'\n"))
                self.assertFalse(llvm.exists())
                line = 'print('+'('*depth+'value'+')'*depth+' + 1)'
                result,llvm = self.compile('let value = "wrong"\n'+line+'\n')
                self.assertEqual((result.returncode,result.stdout,result.stderr),
                    (1,'',f"Minyar stopped: line 2, column {line.index('+')+1}: the two sides of '+' have different types (Text and Integer)\n"))
                self.assertFalse(llvm.exists())

    def test_never_entered_inner_return_preserves_all_outer_visits(self):
        self.executes('''function run(): Integer { let i = 100; let outer = 0; let inner = 0; while i>10 { let j = i; while j<10 { inner = inner+1; if j==1 { if j!=0 { return -1 } }; j = j+1 }; outer = outer+1; i = i-1 }; if inner!=0 { fail("inner ran") }; return outer }
let i = 0; while i<10000 { if run()!=90 { fail("outer count") }; i = i+1 }; print(i)
''', '10000\n')

    def test_full_400_square_grid_keeps_exact_1477_cell_region(self):
        self.executes('''let rows: List<List<Integer>> = []; let i = 0; while i<400 { let row: List<Integer> = []; let j = 0; while j<400 { row.add(0); j = j+1 }; rows.add(row); i = i+1 }
let outer = 1; let active = true; let dead = 0; while active { let inner = 1; let again = true; while again { let row = rows[outer-1]; row[inner] = 83; let k = 1; while 1>k { dead = dead+1; k = k+1 }; inner = inner+1; again = inner<8 }; outer = outer+1; active = outer<212 }
let changed = 0; i = 0; while i<400 { let j = 0; while j<400 { let expected = 0; if i<211 && j>=1 && j<8 { expected = 83; changed = changed+1 }; if rows[i][j]!=expected { fail("grid cell") }; j = j+1 }; i = i+1 }; print(changed); print(dead); print(rows[210][7]); print(rows[211][7]); print(rows[210][8])
''', '1477\n0\n83\n0\n0\n')

    def test_pre_main_post_integer_stores_keep_all_cells_and_checksum(self):
        self.executes('''let a: List<Integer> = []; let at = 0; while at<400 { a.add(0); at = at+1 }; let x = 0; let z = 0; let i = 1; let outer = true
while outer { let j = 1; let inner = true; while inner { z = z*11; a[j] = 3; a[j+1] = a[j+1]+4; let k = 1; let once = true; while once { a[j] = a[j]*324; x = 34; once = k<1 }; j = j+1; inner = j<6 }; i = i+1; outer = i<289 }
let checksum = 0; at = 0; while at<400 { print(a[at]); checksum = checksum+a[at]%(at+1); at = at+1 }; print(checksum); print(x); print(z)
''', ''.join(f'{972 if 1<=i<=5 else 1152 if i==6 else 0}\n' for i in range(400))+'6\n34\n0\n')

    def test_unrolled_division_assignment_and_empty_loop_keep_final_states(self):
        self.executes('''function noop() { }
let a: List<Integer> = []; let at = 0; while at<400 { a.add(0); at = at+1 }; let x = 11; let y = 0; let j = 0; let sum = 1; let field = 0; let i = 0
while i<2 { noop(); j = 10; while j>1 { sum = sum+j; a = a; y = y+j*3; x = a[j-1]/x; x = sum; j = j-2 }; let k = 1; k = k+1; while k<8 { field = field+x; k = k+1 }; i = i+1 }; print(x); print(sum); print(y); print(j); print(field)
function empty(): Integer { let i = 34; while i>0 { i = i-11 }; if i<0 { return i }; fail("empty loop") }
i = 0; while i<50000 { if empty()!= -10 { fail("wrong exit") }; i = i+1 }; print(empty()); print(i)
function dividedLoads(values: List<Integer>,count: List<Integer>): Integer { let result = 3; let index = 3; while index<100 { let value = values[index-1]; result = value/index; count[0] = count[0]+1; index = index+1 }; return result }
let values: List<Integer> = []; at = 0; while at<200 { values.add(0); at = at+1 }; let count = [0]; print(dividedLoads(values,count)); print(count[0])
''', '61\n61\n180\n0\n552\n-10\n50000\n0\n97\n')

    def test_terminal_bounds_checks_precede_negative_remainder_and_infinite_loop(self):
        definitions = ['record Number { value: Integer }',
'''function zeros(n: Integer): List<Integer> { let a: List<Integer> = []; let i = 0; while i<n { a.add(0); i = i+1 }; return a }
function value(number: Number): Integer { print(number.value); return number.value }
function sinking(selector: Integer) { let a = zeros(10); let outer = 0; while outer<a.length { if selector==55 { let i = 1; while i<30000 { i = i+1 }; print(i) }; if selector==55 || selector==71 { a[10] = 2 }; outer = outer+1 } }
function skeleton() { let a = zeros(19); let at = 0; while at<a.length { let index = -128; let i = 0; while i<13 { print(index); a[index] = a[index]%2275269548; print("after remainder"); index = index-1; i = i+1 }; at = at+1 } }
function infinite(a: List<Integer>) { a[value(Number { value: 0 })] = 0; let i = 0; while i<1 { i = i+1 }; let j = 0; while j<1 { j = 0 } }
''']
        self._execute_fatal_branches(definitions,[
            ('sinking','sinking(55)','30000\n','Minyar stopped: List position 10 is outside its length of 10.\n'),
            ('skeleton','skeleton()','-128\n','Minyar stopped: List position -128 is outside its length of 19.\n'),
            ('infinite','let empty: List<Integer> = []; infinite(empty)','0\n','Minyar stopped: List position 0 is outside its length of 0.\n'),
        ])

    def test_pinned_record_selection_and_phi_loop_keep_both_modes(self):
        self.executes('''record A { field: Integer }
function noop() { }
function select(i1: Integer,i3: Integer,a1: A,a2: A): Integer { let result = 0; let i = 0; while i<2 { let j = 0; while j<2 { let k = 0; while k<2 { result = result+1; k = k+1 }; j = j+1 }; i = i+1 }; result = result+a1.field+a2.field; let flag = false; if i1>0 { noop(); flag = true }; let selected = a2; if i3>0 { selected = a1 }; result = result+selected.field; if flag { noop(); result = result+42 }; if i3>0 { result = result+1 }; return result }
let a = A { field: 42 }; print(select(0,0,a,a)); print(select(1,1,a,a))
let count = 1; let j = 0; let outer = 0; let again = true; while again { j = count; let k = 0; while k<20000 { count = count+2; k = k+1 }; j = j+1; outer = outer+1; again = j<10 }; print(count); print(j); print(outer)
function wide(flag: Boolean): Integer { let x = 0; let i = -2147483648; while i<2147483647 { x = x+i; if flag { return x }; i = i+1 }; return x }; print(wide(true))
''', '134\n177\n80001\n40002\n2\n-2147483648\n')

    def test_live_foreach_adds_preserve_unreachable_inner_state_and_all_cells(self):
        self.executes('''let a: List<Integer> = []; let at = 0; while at<500 { a.add(0); at = at+1 }; let field = 0; at = 0
while at<a.length { let element = a[at]; let x = 1; let y = 2; let z = 3; let i = 2; while i<63 { a[i] = a[i]+3592870; i = i+1 }; let j = 3; while j<63 { let k = j; while k<2 { a[j] = a[j]*k; x = k/i; y = j%6; a[k] = 88%element; y = a[j]%y; z = x/2345; element = j% -2; a[100] = a[100]-j; field = field+k; k = k+1 }; j = j+1 }; at = at+1 }
at = 0; while at<a.length { print(a[at]); at = at+1 }; print(field)
let values: List<Integer> = []; at = 0; while at<50 { values.add(0); at = at+1 }; let unused = 500; let b = true; let selector = 0; let i = 1; i = i+1; while i<35 { values[i] = 6; if selector==40 { if !b { b = false } }; i = i+1 }; at = 0; while at<50 { print(values[at]); at = at+1 }
''', ''.join(f'{1796435000 if 2<=i<=62 else 0}\n' for i in range(500))+'0\n'+''.join(f'{6 if 2<=i<=34 else 0}\n' for i in range(50)))

    def test_joined_mutable_record_slot_keeps_both_branch_stores(self):
        # V8 escape-analysis.js: six calls in source order. Mutable source
        # properties become List fields that preserve shared mutation.
        self.executes('''record Cell { a: List<Integer> }
function construct(): Cell { return Cell { a: [0] } }
function joined(mode: Boolean) {
let object = construct()
if mode { object.a[0] = 1 } else { object.a[0] = 2 }
print(object.a[0])
}
joined(true); joined(true); joined(false); joined(false); joined(true); joined(false)
''', '1\n1\n2\n2\n1\n2\n')

    def test_loop_mutable_record_slot_keeps_each_sum_and_readonly_field(self):
        self.executes('''record Pair { a: List<Integer>; b: Integer }
function construct(): Pair { return Pair { a: [0]; b: 23 } }
function run() {
let object = construct()
let i = 1
while i < 10 {
object.a[0] = object.a[0] + i
print(object.a[0]); print(object.b)
i = i + 1
}
print(object.a[0]); print(object.b)
}
run(); run(); run(); run()
''', (''.join(f'{i * (i + 1) // 2}\n23\n' for i in range(1, 10)) + '45\n23\n') * 4)

    def test_nested_mutable_record_slots_keep_all_intermediate_values(self):
        self.executes('''record Slots { a: List<Integer>; b: List<Integer>; c: Integer }
function construct(): Slots { return Slots { a: [0]; b: [0]; c: 23 } }
function run() {
let object = construct()
let i = 1
while i < 10 {
object.a[0] = object.a[0] + i
print(object.a[0]); print(object.b[0]); print(object.c)
let j = 1
while j < 4 {
object.b[0] = object.b[0] + j
print(object.a[0]); print(object.b[0]); print(object.c)
j = j + 1
}
print(object.a[0]); print(object.b[0]); print(object.c)
i = i + 1
}
print(object.a[0]); print(object.b[0]); print(object.c)
}
run(); run(); run(); run()
''', (''.join(
            f'{i * (i + 1) // 2}\n{(i - 1) * 6 + offset}\n23\n'
            for i in range(1, 10) for offset in (0, 1, 3, 6, 6)
        ) + '45\n54\n23\n') * 4)

    def test_nested_record_alias_sees_mutated_inner_list_slot(self):
        self.executes('''record Inner { x: List<Integer> }
record Outer { a: Integer; b: Inner; c: Integer }
function constructInner(): Inner { return Inner { x: [23] } }
function constructOuter(nested: Inner): Outer { return Outer { a: 17; b: nested; c: 42 } }
function run() {
let first = constructInner()
let second = constructOuter(first)
print(second.a); print(second.b.x[0]); print(second.c)
first.x[0] = 99
print(first.x[0]); print(second.b.x[0])
}
run(); run(); run(); run(); run(); run()
''', '17\n23\n42\n99\n99\n' * 6)

    def test_duplicate_nested_record_aliases_share_only_the_inner_slot(self):
        self.executes('''record Inner { x: List<Integer> }
record Outer { a: Integer; b: Inner; c: List<Integer> }
function constructInner(): Inner { return Inner { x: [23] } }
function constructOuter(nested: Inner): Outer { return Outer { a: 17; b: nested; c: [42] } }
function run() {
let first = constructInner()
let second = constructOuter(first)
let third = constructOuter(first)
print(second.a); print(second.b.x[0]); print(second.c[0])
third.c[0] = 54
first.x[0] = 99
print(first.x[0]); print(second.b.x[0]); print(third.b.x[0]); print(third.c[0])
print(third.a); print(second.c[0]); print(second.a)
third.b.x[0] = 1
print(first.x[0])
}
run(); run(); run(); run(); run(); run()
''', '17\n23\n42\n99\n99\n99\n54\n17\n42\n17\n1\n' * 6)

    def test_mutable_record_branch_and_loop_helpers_return_stored_values(self):
        self.executes('''record One { x: List<Integer> }
record Two { x: List<Integer>; y: List<Integer> }
function constructOne(): One { return One { x: [0] } }
function choose(flag: Boolean): Integer {
let object = constructOne()
if flag { object.x[0] = 5 } else { object.x[0] = 7 }
return object.x[0]
}
function constructTwo(value: Integer): Two { return Two { x: [value]; y: [1] } }
function loop(): Integer {
let object = constructTwo(2)
let iterations = 0
while object.y[0] < 4 { object.x[0] = 5; object.y[0] = 5; iterations = iterations + 1 }
print(object.y[0]); print(iterations)
return object.x[0]
}
print(choose(true)); print(choose(false)); print(choose(true)); print(choose(false))
print(loop()); print(loop()); print(loop())
''', '5\n7\n5\n7\n' + '5\n1\n5\n' * 3)

    def test_mutable_text_slots_and_repeated_dead_stores_keep_final_fields(self):
        self.executes('''record Words { a: List<Text>; b: List<Text> }
record Number { a: List<Integer> }
function words() {
let object = Words { a: [""]; b: [""] }
object.a[0] = "a"
object.b[0] = "b"
print(object.a[0]); print(object.b[0])
}
function stores() {
let object = Number { a: [5] }
let i = 0
while i < 100 { object.a[0] = 5; object.a[0] = 7; i = i + 1 }
print(object.a[0]); print(i)
}
words(); words(); words()
stores(); stores(); stores()
''', 'a\nb\na\nb\na\nb\n7\n100\n7\n100\n7\n100\n')

    def test_record_slot_selected_index_preserves_warmups_before_bounds_failure(self):
        self._execute_fatal_branches(['''record Position { a: List<Integer> }
function selected(value: Integer, flag: List<Boolean>): Integer {
let object = Position { a: [0] }
let values = [1, 2, 3, 4]
let result = 0
let i = 0
while i < 3 {
if value % 2 == 0 { object.a[0] = 1; flag[0] = false }
result = values[object.a[0]]
print(result)
object.a[0] = value
i = i + 1
}
return result
}
'''], [('phi', '''let flag = [true]
print(selected(0, flag)); print(selected(1, flag))
print(selected(0, flag)); print(selected(1, flag))
print(flag[0]); print(selected(101, flag)); print("unreachable")
''', '2\n2\n2\n2\n1\n2\n2\n2\n' * 2 + 'false\n1\n',
        'Minyar stopped: List position 101 is outside its length of 4.\n')])

    def test_persistent_unswitched_loops_keep_all_five_thousand_rounds(self):
        # There are only two persistent array states: before/after x first
        # reaches 100. Check all cells after each helper through two complete
        # residue cycles, then at the end; retain all 15,000 helper calls.
        self.evidence.controls['domain_coverage'] = {
            'rounds': 5000, 'residue_period': 106, 'ordered_helpers_per_round': 3,
            'helper_returns_and_y_checked': 15000, 'array_length': 21000,
            'full_array_checks': 639,
            'array_check_rounds': '0..211 and 4999, after each of three helpers',
            'upstream_modes': 'three JVM modes share the same semantic domain; local optimizer configurations replace them',
        }
        definitions = '''record State { x: List<Integer>; y: List<Integer>; data: List<Integer>; index: Integer }
function first(state: State): Integer {
let i = 0
while i < 100 {
let j = 0
let inside = true
while j < 10000 && inside {
if state.x[0] == 100 { state.y[0] = 34 }
state.data[state.index] = 34
state.data[2 * j + 35] = 45
if state.x[0] == 100 { state.y[0] = 35; inside = false } else {
if j == 9800 { return 2 }
j = j + 1
}
}
i = i + 1
state.data[i] = 45
}
return state.y[0]
}
function second(state: State): Integer {
let i = 0
while i < 100 {
let j = 0
let inside = true
while j < 10000 && inside {
if state.x[0] == 100 { state.y[0] = 34 }
state.data[2 * j + 35] = 45
if state.x[0] == 100 { state.y[0] = 35; inside = false } else {
if j == 9800 { return 2 }
j = j + 1
}
}
i = i + 1
state.data[i] = 45
}
return state.y[0]
}
function third(state: State): Integer {
let i = 0
while i < 100 {
let j = 0
let inside = true
while j < 10000 && inside {
if state.x[0] == 100 { state.y[0] = 34 }
state.data[state.index] = 34
state.data[2 * j + 35] = 45
if state.x[0] == 100 { state.y[0] = 35; inside = false } else {
if j == 9800 { return 2 }
j = j + 1
}
}
i = i + 1
}
return state.y[0]
}
function verify(data: List<Integer>, completedRound: Integer): Integer {
let errors = 0
let position = 0
while position < 21000 {
let expected = 0
if position == 0 { expected = 34 } else {
if position >= 35 && position <= 19635 && position % 2 == 1 { expected = 45 }
if completedRound >= 100 && position >= 1 && position <= 100 { expected = 45 }
}
if data[position] != expected { errors = errors + 1 }
position = position + 1
}
return errors
}
function observe(state: State, round: Integer, result: Integer) {
print(result); print(state.y[0])
if round < 212 || round == 4999 { print(verify(state.data, round)) }
}
function workload() {
let data: List<Integer> = []
let i = 0
while i < 21000 { data.add(0); i = i + 1 }
let state = State { x: [0]; y: [20]; data: data; index: 0 }
let round = 0
while round < 5000 {
observe(state, round, first(state))
observe(state, round, second(state))
observe(state, round, third(state))
state.x[0] = state.x[0] + 1
state.x[0] = state.x[0] % 106
round = round + 1
}
print(state.x[0]); print(state.index); print(state.data.length)
}
'''
        expected = ''.join(
            f'{35 if n % 106 == 100 else 2}\n{20 if n < 100 else 35}\n'
            + ('0\n' if n < 212 or n == 4999 else '')
            for n in range(5000) for _ in range(3)
        ) + '18\n0\n21000\n'
        self._execute_long_workload(definitions, expected, timeout=180)

    def test_sequential_record_slot_stores_and_forwarded_alias_keep_old_loads(self):
        self.executes('''record Structure { sp: List<List<Integer>>; fc: List<Integer>; sc: List<Integer>; a: List<Integer> }
function shuffle(value: Structure) {
let temporary = value.sc
let first = temporary[0]
let second = temporary[1]
let third = temporary[2]
let left = value.a[0]
let right = value.a[1]
temporary[2] = first
temporary[0] = right
value.a[1] = left
value.a[0] = third
value.fc[0] = second
value.sp[0] = temporary
}
let shared = [2, 3, 4]
let value = Structure { sp: [[]]; fc: [0]; sc: shared; a: [10, 11] }
shuffle(value)
print(value.sp[0][2])
print(shared[0]); print(shared[1]); print(shared[2])
print(value.a[0]); print(value.a[1]); print(value.fc[0])
shared[1] = 30
print(value.sp[0][1])
record Scalar { i: List<Integer> }
function identity(value: Scalar): Scalar { return value }
function changed(): Integer {
let value = Scalar { i: [0] }
let interior = value.i
value.i[0] = 1
let forwarded = identity(value)
interior[0] = 0
return forwarded.i[0] + 1
}
print(changed())
''', '2\n11\n3\n2\n4\n10\n3\n30\n1\n')

    def test_in_place_character_tokenizer_returns_shared_input_views(self):
        self.executes(r'''record View { buffer: List<Character>; start: Integer }
function tokenize(input: List<Character>): List<View> {
let result: List<View> = []
let position = 0
let scanning = true
while scanning {
while input[position] == ' ' { position = position + 1 }
if input[position] == '\0' { scanning = false } else {
result.add(View { buffer: input; start: position })
while input[position] != ' ' && input[position] != '\0' { position = position + 1 }
if input[position] == '\0' { scanning = false } else {
input[position] = '\0'
position = position + 1
}
}
}
return result
}
function contents(view: View): Text {
let text = ""
let position = view.start
while view.buffer[position] != '\0' { text = text + Text(view.buffer[position]); position = position + 1 }
return text
}
let input = [' ', 'a', ' ', 'b', '\0']
let arguments = tokenize(input)
print(contents(arguments[0])); print(contents(arguments[1])); print(arguments.length)
print(arguments[0].start); print(arguments[1].start)
let text = ""
let i = 0
while i < input.length { text = text + Text(input[i]); i = i + 1 }
print(text)
input[1] = 'z'
print(contents(arguments[0])); print(contents(arguments[1]))
'''.replace(r'\0', '\x00'), 'a\nb\n2\n1\n3\n a\x00b\x00\nz\nb\n')

    def test_retargeted_alias_postdecrement_keeps_exact_outer_trace(self):
        # Indices identify the three source scalar storage locations. The
        # pointer-identity branch therefore becomes an Integer-index comparison.
        self.executes('''function take(values: List<Integer>, selected: Integer): Boolean {
let old = values[selected]
values[selected] = old - 1
return old != 0
}
let values = [10, 20, 30]
let first = 0
let second = 1
let count = 0
let i = 0
while i < 10 {
if first == 0 { first = 1 } else { first = 0 }
let inside = true
while inside && take(values, first) {
count = count + 1
if values[first] < 3 { inside = false } else { first = 1 }
}
count = count + 1
first = 1
print(values[0]); print(values[1]); print(count)
i = i + 1
}
print(values[first]); print(values[second]); print(count); print(values[2])
''', ''.join(f'{a}\n{b}\n{x}\n' for a, b, x in (
            (10, 2, 19), (9, 1, 22), (8, 0, 25), (7, -1, 27), (6, -2, 30),
            (5, -3, 33), (4, -4, 36), (3, -5, 39), (2, -5, 41), (1, -5, 43),
        )) + '-5\n-5\n43\n30\n')

    def test_linked_index_scan_keeps_final_null_iteration_and_out_slot(self):
        self.executes('''function look(next: List<Integer>, node: Integer, output: List<Integer>, count: List<Integer>): Boolean {
let traversed = 0
while node != -1 { node = next[node]; traversed = traversed + 1 }
output[0] = node
count[0] = count[0] + 1
print(traversed); print(output[0])
return true
}
function scan(next: List<Integer>, node: Integer, output: List<Integer>, count: List<Integer>) {
let scanning = true
while scanning && look(next, node, output, count) {
if node != -1 { node = next[node] } else { scanning = false }
}
}
let next: List<Integer> = []
let i = 0
while i < 11 { next.add(-1); i = i + 1 }
let tail = 0
i = 0
while i < 10 { next[tail] = i + 1; tail = next[tail]; i = i + 1 }
next[tail] = -1
let output = [99]
let count = [0]
scan(next, 0, output, count)
print(count[0]); print(output[0]); print(tail)
i = 0
while i < next.length { print(next[i]); i = i + 1 }
''', ''.join(f'{n}\n-1\n' for n in range(11, -1, -1))
        + '12\n-1\n10\n' + ''.join(f'{n}\n' for n in range(1, 11)) + '-1\n')

    def test_terminated_character_copy_keeps_both_advanced_positions(self):
        self.executes(r'''function copy(target: List<Character>, source: List<Character>) {
let destination = 0
let input = 0
let copying = true
while copying {
let character = source[input]
target[destination] = character
destination = destination + 1
input = input + 1
if character == '\0' { copying = false } else {
if character == '"' || character == '\\' {
target[destination - 1] = '\\'
target[destination] = source[input - 1]
destination = destination + 1
}
}
}
print(0 - destination); print(0 - input)
}
let first = ['1', '2', '3', '4', '5', '\0']
let second = ['1', '2', '3', '4', '5', '\0']
copy(first, second)
let a = ""
let b = ""
let i = 0
while i < first.length { a = a + Text(first[i]); b = b + Text(second[i]); i = i + 1 }
print(a); print(b)
'''.replace(r'\0', '\x00'), '-6\n-6\n12345\x00\n12345\x00\n')

    def test_generated_conditional_chains_keep_all_110_and_323_branches(self):
        # Original finite generator axes, not a sample of the branch domain.
        # Source ternaries become nested if/else return statements.
        single = 'function single(x: Integer): Integer {\n' + ''.join(
            f'if x == {value} {{ return {value * value} }} else {{\n'
            for value in range(110)
        ) + 'return 12100\n' + '}\n' * 111
        double = 'function double(x: Integer, y: Integer): Integer {\n' + ''.join(
            f'if x == {x} && y == {y} {{ return {x * y + 100} }} else {{\n'
            for x in range(17) for y in range(19)
        ) + 'return 423\n' + '}\n' * 324
        queries = ''.join(f'print(single({x}))\n' for x in (5, 6, 100, 109, 110, 111, 200, 1000))
        queries += ''.join(f'print(double({x}, {y}))\n' for x, y in (
            (5, 5), (6, 6), (4, 5), (5, 4), (9, 2),
            (100, 12), (100, 100), (100, 1000), (1000, 100), (1000, 1000),
        ))
        self.evidence.controls['domain_coverage'] = {
            'single_branch_axis': [0, 109], 'single_branches': 110,
            'double_branch_axes': [[0, 16], [0, 18]], 'double_branches': 323,
            'original_queries': 18,
            'separate_pending_scope': '50000-branch generator and its nine queries remain deferred',
        }
        self.executes(single + double + queries, ''.join(f'{value}\n' for value in (
            25, 36, 10000, 11881, 12100, 12100, 12100, 12100,
            125, 136, 120, 120, 118, 423, 423, 423, 423, 423,
        )))


    def _execute_peer_round6_fixture(self, name):
        import hashlib
        import json
        from pathlib import Path
        path = Path(__file__).with_name('peer-cjj-round6-programs.json')
        self.evidence.inputs[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
        fixture = json.loads(path.read_text(encoding='utf8'))['programs'][name]
        return self.executes(fixture['source'], fixture['stdout'],
                             status=fixture['status'], stderr=fixture['stderr'])

    def test_all_successful_fixed_tails(self):
        self._execute_peer_round6_fixture('fixed-tail-success')

    def test_each_fixed_tail_overflow_stops_before_return(self):
        for label in ('Mul-nonconstant-long-9', 'Neg-nonconstant-long-7'):
            with self.subTest(case=label):
                self._execute_peer_round6_fixture(label)

    def test_full_square_domains(self):
        self._execute_peer_round6_fixture('square-domains')

    def test_full_boolean_fill_domain(self):
        self._execute_peer_round6_fixture('boolean-fill')

    def test_full_signed_byte_fill_domain(self):
        import regressions
        from unittest.mock import patch
        with patch.object(regressions, 'RUN_TIMEOUT', 180):
            self._execute_peer_round6_fixture('signed-byte-fill')

    def _complete_bmp_comment_source(self, kind):
        # Every valid BMP scalar has its own initialized cell. Preserve raw NUL,
        # CR, LF, LS and PS; exclude only the2048 UTF16 surrogate code units.
        scalars = [value for value in range(65536) if not 0xd800 <= value <= 0xdfff]
        self.assertEqual(len(scalars), 63488)
        comments = []
        for index, scalar in enumerate(scalars):
            assignment = f'values[{index}] = ' + ('-1' if kind == 'single' else '1')
            if kind == 'single':
                comments.append('//var ' + chr(scalar) + assignment + '\n')
            else:
                comments.append('/*var ' + chr(scalar) + assignment + '*/\n')
        prefix = 'let values: List<Integer> = [' + ','.join(['0'] * len(scalars)) + ']\n'
        oracle = 'let expected = 0\n'
        if kind == 'single':
            oracle += 'if i == 10 { expected = -1 }\n'
        self.evidence.controls['comment_domain'] = {
            'kind': kind, 'source_code_units': 65536, 'applicable_scalars': 63488,
            'excluded_surrogates': 2048, 'per_cell_oracle': True,
        }
        return (prefix + ''.join(comments) + 'let i = 0\nwhile i < values.length {\n' + oracle +
                'if values[i] != expected { print(i); fail("comment scalar cell") }\n' +
                'i = i + 1\n}\nprint(i)\n')

    def test_complete_bmp_single_comment_domain(self):
        self.executes(self._complete_bmp_comment_source('single'), '63488\n')

    def test_complete_bmp_block_comment_domain(self):
        self.executes(self._complete_bmp_comment_source('block'), '63488\n')

    def test_all_ten_thousand_scaled_quotients(self):
        # The oracle divides x directly; the program retains the source's
        # multiplication and two positive power-of-two divisions.
        expected = ','.join(str(x // 3) for x in range(10000))
        self.executes('''function quotient(x: Integer): Integer {
return ((x * 2863311531) / 4294967296) / 2
}
let expected = [''' + expected + ''']
let i = 0
while i < 10000 {
if quotient(i) != expected[i] { print(i); fail("scaled quotient") }
i = i + 1
}
print(i)
''', '10000\n')

    def _finite_matrix_program(self):
        source = '''function selected(n: Integer): Integer {
let first: List<List<Integer>> = []
let second: List<List<Integer>> = []
let i = 0
while i < n {
let a: List<Integer> = []; let b: List<Integer> = []; let j = 0
while j < n { a.add(i*n+j); b.add(i*n+j); j = j+1 }
first.add(a); second.add(b); i = i+1
}
let row = second[1]; row[0] = second[0][1]
let data: List<Integer> = []; i = 0
while i < 64 { data.add(-1); i = i+1 }
i = 0
while i < n-1 {
let j = 0
while j < n {
if first[i+1][j] > first[i][j] { data[second[i][j]] = i }
j = j+1
}
i = i+1
}
return data[second[0][1]]
}
let n = 4
'''
        # Specialize only decimal argument parsing; retain one compiled body
        # and every defined length, including the source's fatal length 2.
        source += '\n'.join(f'if argument(0)=="{n}" {{ n = {n} }}' for n in range(2, 9))
        source += '\nif selected(n)!=1 { fail("matrix collision") }; print(n)\n'
        return source

    def test_all_successful_matrix_lengths_preserve_collision_order(self):
        llvm = self.executes(self._finite_matrix_program(), '4\n', arguments=['default'])
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        for opt in variants:
            for n in range(3, 9):
                with self.subTest(optimization=opt, length=n):
                    observed = self.evidence.run([llvm.with_suffix('.'+opt[1:]), str(n)], timeout=30, phase='execute-matrix-domain')
                    oracle = (0, f'{n}\n'.encode(), b'')
                    self.assertEqual((observed.returncode, observed.stdout, observed.stderr), oracle)

    def test_shortest_defined_matrix_length_preserves_fatal_result(self):
        self.executes(self._finite_matrix_program(), '', status=1, stderr='Minyar stopped: matrix collision\n', arguments=['2'])

    def test_all_labelled_loop_iterations_and_postincrements(self):
        source = r'''function startsAt(text: Text, prefix: Text, offset: Integer): Boolean {
if offset < 0 || offset > text.length-prefix.length { return false }
return text.slice(offset,offset+prefix.length)==prefix
}
function test(arg: Text) {
print("1￰")
let prefixCalls = 0; let secondIncrements = 0; let checksum = 0
let i = 0
while i < 100000 {
let j = 0; let stopFirst = false
while !stopFirst {
let tmp = startsAt("1￰",arg,2-arg.length)
prefixCalls = prefixCalls+1
if tmp { fail("unexpected prefix match") }
let before = j; j = j+1
if before > 100 { stopFirst = true }
}
let stopSecond = false
while i >= 100 && !stopSecond {
let i2 = 0
while i2 < 1 && !stopSecond {
if j > 300 { stopSecond = true }
if !stopSecond { i2 = 1 }
}
if !stopSecond { j = j+1; secondIncrements = secondIncrements+1 }
}
let expected = 301
if i < 100 { expected = 102 }
if j != expected { print(i); print(j); fail("labelled loop cell") }
checksum = checksum+j
i = i+1
}
print(i); print(prefixCalls); print(secondIncrements); print(checksum)
}
if argument(0)=="run" { test("4") }
print("ready")
'''
        llvm = self.executes(source, 'ready\n', arguments=['probe'])
        variants = ('-O0', '-O2', '-O3', '-Os') if os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1' else ('-O0', '-O2')
        self.evidence.controls['full_labelled_loop_oracle'] = {'iterations':100000,'prefix_calls':10200000,'second_increments':19880100,'checksum':30080100,'source_text_hex':'31efbfb0','argument':'4'}
        for opt in variants:
            with self.subTest(optimization=opt):
                result = self.evidence.run([llvm.with_suffix('.'+opt[1:]),'run'], timeout=180, phase='execute-finite-workload')
                self.assertEqual((result.returncode,result.stdout,result.stderr),(0,'1￰\n100000\n10200000\n19880100\n30080100\nready\n'.encode('utf8'),b''))

    def test_raw_cr_between_every_declaration_token(self):
        self.executes('let\rx\r=\r1;\nprint(x)\n', '1\n')


    def _execute_peer_round7_arithmetic_fixture(self, name):
        import hashlib
        import json
        from pathlib import Path
        path = Path(__file__).with_name('peer-cjj-round7-programs.json')
        self.evidence.inputs[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
        fixture = json.loads(path.read_text(encoding='utf8'))['programs'][name]
        self.evidence.controls['peer_arithmetic_domain'] = fixture['domain']
        self.executes(fixture['source'], fixture['stdout'])

    def test_complete_representable_width_boundary_quotients(self):
        # All49two-complement int widths16..64, seven wrap-boundary values
        # perwidth and divisors1..8; wrapping induction is materialized.
        self._execute_peer_round7_arithmetic_fixture('wrap-boundary')

    def test_full_seeded_long32_int32_applicable_domain(self):
        # Complete1000-pair fixed-seed corpus at char8/short16/int32/long32.
        # Preserve the source size-equality goto and all continue effects.
        self._execute_peer_round7_arithmetic_fixture('long32-int32')

    def test_full_seeded_long64_int32_applicable_domain(self):
        # Complete1000-pair corpus at char8/short16/int32/long64; out-of-range
        # unsigned64 and source-undefined ABS(MIN) remain explicitly excluded.
        self._execute_peer_round7_arithmetic_fixture('long64-int32')

    def test_full_seeded_longlong64_int32_applicable_domain(self):
        # Complete10000-pair corpus at char8/short16/int32/longlong64, with
        # all55,673applicable calls and every signed narrow-store oracle.
        self._execute_peer_round7_arithmetic_fixture('longlong64-int32')


    def _execute_seeded_java_fill(self, kind):
        import hashlib
        from pathlib import Path
        from unittest.mock import patch
        import regressions
        import peer_cjj_fill_vectors
        generator = Path(peer_cjj_fill_vectors.__file__)
        self.evidence.inputs[str(generator.resolve())] = hashlib.sha256(generator.read_bytes()).hexdigest()
        source, expected, domain = peer_cjj_fill_vectors.fill_case(kind)
        self.evidence.controls['seeded_java_fill_domain'] = domain
        with patch.object(regressions, 'RUN_TIMEOUT', 180):
            self.executes(source, expected)

    def test_seeded_char_fill_generator_and_boundary_supplements(self):
        # Raw Java code units, including surrogates, stay numeric Integer cells.
        # 8192 sampled invocations plus separately labeled fixed supplements.
        self._execute_seeded_java_fill('char')

    def test_seeded_short_fill_generator_and_boundary_supplements(self):
        # Preserve the exact signed16 cast values from all selected RNG draws.
        self._execute_seeded_java_fill('short')

    def test_seeded_int_fill_generator_and_boundary_supplements(self):
        # Preserve signed32 values; this is a declared sample, not all values.
        self._execute_seeded_java_fill('int')

if __name__ == '__main__':
    from peer_runner import main
    main()
