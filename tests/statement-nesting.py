#!/usr/bin/env python3
"""Deep statement compilation succeeds without consuming the native call stack.

Expression and generated-program recursion retain the separate stack-overflow
checks. The 50,000-branch domain comes from V8's conditional-chain regression;
its nested control structure and all nine successful queries are preserved.
Upstream: v8/v8, revision 7dce5a4a324258ba51b2a6f5dee7a1fa18c7671d,
test/mjsunit/compiler/conditional-chain.js, final 50,000-branch cohort.
"""
import os
import re
from textwrap import dedent
from pathlib import Path
import unittest

from regressions import CompilerTestCase, ROOT, CLANG, COMPILER, RUNTIME, LINK_FLAGS
from llvm_sanitizer import prepare_llvm_for_link
from test_evidence import digest

MODULE_COMPILER = Path(os.environ.get('MINYAR_TEST_MODULE_COMPILER', ROOT / 'build/minyarc-modules')).resolve()
# Keep the complete deep input in both routine backend lanes. O3/Os are also
# validated in the fix's focused release evidence. Exact pure selectors lower
# to a bounded binary-search CFG after complete source validation.
OPTIMIZATIONS = ('-O0', '-O2')
QUERIES = (0, 1, 101, 102, 50099, 50100, 50101, 50200, 51100)
# Independently fixed results: matching branches return x*x; every other query
# returns (100 + 50000)**2. Keep the oracle separate from source generation.
EXPECTED = '2510010000\n2510010000\n10201\n10404\n2509909801\n2510010000\n2510010000\n2510010000\n2510010000\n'


def deep_chain():
    return ('function longChain(x: Integer): Integer {\n'
            + ''.join(f'if x == {i} {{ return {i*i} }} else {{\n' for i in range(100, 50100))
            + 'return 2510010000\n' + '}\n' * 50001)


# Independent semantic controls cover all continuation kinds and scoped owners.

SUCCESS = []
DIAGNOSTICS = []

def success(name, source, stdout, status=0, stderr=''):
    SUCCESS.append(dict(name=name, source=dedent(source).lstrip('\n'), stdout=stdout,
                        status=status, stderr=stderr, ownership=status==0))

def located(source, token, explanation, occurrence=0):
    start=0
    for _ in range(occurrence+1):
        position=source.index(token,start);start=position+len(token)
    line=source.count('\n',0,position)+1
    column=position-(source.rfind('\n',0,position)+1)+1
    return f'Minyar stopped: line {line}, column {column}: {explanation}\n'

def diagnostic(name, source, message=None, token=None, explanation=None, occurrence=0):
    source=dedent(source).lstrip('\n')
    stderr=message if message is not None else located(source,token,explanation,occurrence)
    DIAGNOSTICS.append(dict(name=name,source=source,stderr=stderr))

success('branch_scope_restores_types_and_owners', '''
function branch(flag: Boolean): Text {
let result = "base"
if flag {
let holder = ["left", "copy"]
if holder.length == 2 { let result = holder[0] + "!"; print(result) }
result = holder[1] + "?"
} else {
let holder = 42
result = Text(holder)
}
return result
}
print(branch(true)); print(branch(false))
''', 'left!\ncopy?\n42\n')

success('short_circuit_conditions_and_reference_effects', '''
function checked(count: List<Integer>, answer: Boolean): Boolean {
count[0] = count[0] + 1
let temporary = Text(count[0]) + "checked"
return temporary.length > 0 && answer
}
let calls = [0]
if checked(calls,false) && checked(calls,true) { print("wrong") } else {
if checked(calls,true) || checked(calls,false) { print("taken") } else { print("wrong") }
}
let index = 0
while checked(calls,index < 2) && checked(calls,true) {
if index == 0 { print("first") } else { print("second") }
index = index + 1
}
print(calls[0])
''', 'taken\nfirst\nsecond\n7\n')

success('nested_loops_release_scoped_lists_and_text', '''
let saved: List<Text> = []
let outer = 0
while outer < 3 {
let part = Text(outer) + ":"
let inner = 0
while inner < 2 {
let scoped = [part + Text(inner)]
if inner == 0 { saved.add(scoped[0]) } else { let alias = scoped; saved.add(alias[0]) }
inner = inner + 1
}
outer = outer + 1
}
let index = 0
while index < saved.length { print(saved[index]); index = index + 1 }
''', '0:0\n0:1\n1:0\n1:1\n2:0\n2:1\n')

success('record_list_returns_cross_nested_scopes', '''
record Box { values: List<Text> }
function make(flag: Boolean): Box {
let seed = ["seed"]
if flag {
if seed.length == 1 {
let alias = seed; alias.add("left")
return Box { values: alias }
} else { return Box { values: ["unreachable"] } }
} else {
while true {
let alias = seed; alias.add("right")
return Box { values: alias }
}
}
}
let left = make(true); let right = make(false)
print(left.values[0]); print(left.values[1]); print(right.values[0]); print(right.values[1])
''', 'seed\nleft\nseed\nright\n')

success('terminal_blocks_still_lower_unreachable_statements', '''
function choose(flag: Boolean): Integer {
if flag {
return 11
let dead = ["unreachable"]
print(dead[0])
} else {
return 22
while false { let ignored = "unreachable" + "body"; print(ignored) }
}
let tail = ["unreachable tail"]
print(tail[0])
}
print(choose(true)); print(choose(false))
''', '11\n22\n')

success('literal_true_nested_loops_are_terminal', '''
function value(flag: Boolean): Text {
while true {
if flag { return "one" + "!" } else { while true { return "two" + "?" } }
}
let dead = ["unreachable"]
print(dead[0])
}
print(value(true)); print(value(false))
''', 'one!\ntwo?\n')

success('variable_and_false_loops_keep_fallthrough', '''
function value(flag: Boolean): Integer {
if flag { while false { return 100 }; let scope = ["local"]; print(scope[0]) } else { while false {} }
while flag { if flag { return 7 } else { return 8 } }
return 9
}
print(value(true)); print(value(false))
''', 'local\n7\n9\n')

success('loop_cleanup_debt_and_reused_frame_kinds', '''
function discarded(n: Integer): List<Text> { return [Text(n) + "temporary", "tail"] }
let count = 0
while count < 80 {
discarded(count)
if count % 2 == 0 { let temporary = [Text(count)]; temporary.add("x") } else { while false { print("wrong") } }
if count == 0 {} else {}
count = count + 1
}
print(count)
''', '80\n')

success('nested_returns_balance_function_frames', '''
function descend(n: Integer): Integer {
while n >= 0 {
if n == 0 { return 0 } else { if n > 0 { return 1 + descend(n - 1) } else { return 90 } }
}
return -1
}
print(descend(300)); print(descend(-1))
''', '300\n-1\n')

success('empty_blocks_and_adjacent_siblings', '''
if true {} else { print("wrong") }
while false {}
if false { print("wrong") } else { if true {} else {}; print("empty works") }
let value = "outer"
if false { let value = ["hidden"]; print(value[0]) }
print(value)
''', 'empty works\nouter\n')

success('nested_exit_terminates_function_without_return', '''
function stop(): Integer {
if true { while true { print("before exit"); exit(7) } } else { return 0 }
}
print(stop())
print("wrong")
''', 'before exit\n',7)

success('nested_fail_terminates_block_without_fallthrough', '''
function stop(): Integer {
while true {
if true { print("before failure"); fail("nested failure") } else { return 0 }
}
}
print(stop())
print("wrong")
''', 'before failure\n',1,'Minyar stopped: nested failure\n')

diagnostic('else_after_newline_is_not_attached','''
function f() {
if true {}
else {}
}
''',token='else',explanation="'else' belongs on the same line as the closing brace of its if")
diagnostic('else_after_semicolon_is_not_attached','function f() { if true {}; else {} }\n',token='else',explanation="'else' belongs on the same line as the closing brace of its if")
diagnostic('nested_statement_needs_terminator','function f() { if true {} print(2) }\n',token='print',explanation="unexpected 'print'; start the next statement on a new line")
diagnostic('while_cannot_consume_else','function f() { while false {} else {} }\n',token='else',explanation="unexpected 'else'; start the next statement on a new line")
diagnostic('then_local_not_visible_in_else','''
function f() {
if true { let hidden = "then" } else { print(hidden) }
}
''',token='hidden',occurrence=1,explanation="I can't find a value named 'hidden'")
diagnostic('closed_block_local_not_visible_after_if','''
function f() {
if true { let hidden = ["inside"] }
print(hidden)
}
''',token='hidden',occurrence=1,explanation="I can't find a value named 'hidden'")
diagnostic('dead_source_still_checks_unknown_name','''
function f(): Integer {
while true { return 1 }
print(missing)
}
''',token='missing',explanation="I can't find a value named 'missing'")
diagnostic('both_terminal_branches_still_check_later_source','''
function f(flag: Boolean): Integer {
if flag { return 1 } else { return 2 }
if false { print(missing) }
}
''',token='missing',explanation="I can't find a value named 'missing'")
diagnostic('false_loop_does_not_satisfy_return','function f(): Integer { while false { return 1 } }\n',message="Minyar stopped: function 'f' must return a value on every path\n")
diagnostic('variable_loop_does_not_satisfy_return','function f(flag: Boolean): Integer { while flag { return 1 } }\n',message="Minyar stopped: function 'f' must return a value on every path\n")
diagnostic('missing_outer_else_does_not_satisfy_return','function f(flag: Boolean): Integer { if flag { if true { return 1 } else { return 2 } } }\n',message="Minyar stopped: function 'f' must return a value on every path\n")
diagnostic('wrong_if_condition_points_at_open_brace','function f() { if 1 { print(0) } }\n',token='{',occurrence=1,explanation='an if condition must be Boolean')
diagnostic('wrong_while_condition_points_at_open_brace','function f() { if true { while 1 { print(0) } } }\n',token='{',occurrence=2,explanation='a while condition must be Boolean')


def deep_then(depth):
    source='function value(flag: Boolean): Text {\nlet result = "outer"\n'
    source += 'if flag {\n'*depth
    source += 'let local = ["kept"]\nresult = local[0] + "!"\n'
    source += '}\n'*depth
    source += 'return result\n}\nprint(value(true)); print(value(false))\n'
    return dict(name=f'deep_then_{depth}',source=source,stdout='kept!\nouter\n',status=0,stderr='',ownership=True)


def deep_while(depth):
    source='function value(flag: Boolean): Integer {\n'
    source += 'while flag {\n'*depth
    source += 'return 7\n'
    source += '}\n'*depth
    source += 'return 9\n}\nprint(value(true)); print(value(false))\n'
    return dict(name=f'deep_while_{depth}',source=source,stdout='7\n9\n',status=0,stderr='',ownership=True)


def moderate_nested(depth=128):
    """Mixed continuation kinds with branch and loop locals, independently counted."""
    source='function value(flag: Boolean): Integer {\nlet result = 0\n'
    for level in range(depth):
        source+='if flag {\nlet local = ["'+str(level)+'"]\nwhile local.length > 0 {\n'
    source+='return '+str(depth)+'\n'
    for _ in range(depth):source+='}\n} else { return -1 }\n'
    source+='return result\n}\nprint(value(true)); print(value(false))\n'
    return dict(name=f'moderate_mixed_{depth}',source=source,stdout=f'{depth}\n-1\n',status=0,stderr='',ownership=True)

SUCCESS.append(moderate_nested())

success('asymmetric_branch_returns_preserve_fallthrough', '''
function thenReturns(flag: Boolean): Text {
let result = "outer"
if flag { return "early then" } else {
let scoped = ["else", " tail"]
result = scoped[0] + scoped[1]
}
return result
}
function elseReturns(flag: Boolean): Text {
let result = "outer"
if flag {
let scoped = ["then", " tail"]
result = scoped[0] + scoped[1]
} else { return "early else" }
return result
}
print(thenReturns(true)); print(thenReturns(false))
print(elseReturns(true)); print(elseReturns(false))
''', 'early then\nelse tail\nthen tail\nearly else\n')


class StatementNesting(CompilerTestCase):
    def test_moderate_scopes_loops_and_owned_results(self):
        for case in SUCCESS:
            if case['status'] == 0:
                with self.subTest(case=case['name']):
                    self.executes(case['source'], case['stdout'], optimizations=OPTIMIZATIONS)

    def test_terminal_exit_and_failure_keep_exact_trace(self):
        for case in SUCCESS:
            if case['status'] != 0:
                with self.subTest(case=case['name']):
                    self.executes(case['source'], case['stdout'], status=case['status'],
                                  stderr=case['stderr'], optimizations=OPTIMIZATIONS)

    def test_scope_and_control_diagnostics_are_exact(self):
        for case in DIAGNOSTICS:
            with self.subTest(case=case['name']):
                result, llvm = self.compile(case['source'])
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (1, '', case['stderr']))
                self.assertFalse(llvm.exists())

    def test_deep_then_scopes_and_while_returns_execute(self):
        for case in (deep_then(20000), deep_while(2000)):
            with self.subTest(case=case['name']):
                result, llvm = self.compile(case['source'])
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
                self.link_and_run(llvm, case['stdout'], ('-O0',))

    def test_twenty_thousand_while_bodies_compile(self):
        # Preserve this full frontend domain. LLVM's native code generator for
        # 20,000 nested loops exceeded 120 seconds in the focused investigation;
        # the separate 2,000-loop test executes both true and false paths.
        result, llvm = self.compile(deep_while(20000)['source'])
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        ir = llvm.read_text()
        self.assertEqual(len(re.findall(r'^while\.condition\.[0-9]+:', ir, re.M)), 20000)
        self.assertEqual(len(re.findall(r'^while\.body\.[0-9]+:', ir, re.M)), 20000)
        self.assertEqual(len(re.findall(r'^while\.end\.[0-9]+:', ir, re.M)), 20000)
        # Parse the entire emitted module through the portable LLVM frontend
        # without LLVM's optimizer pipeline or native nested-loop code generation.
        parsed = self.directory / 'nested-while-parsed.ll'
        result = self.evidence.run([CLANG, '-O0', '-S', '-emit-llvm', '-Xclang', '-disable-llvm-passes',
                                    '-Wno-override-module',
                                    llvm, '-o', parsed], timeout=30, phase='parse-llvm')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        self.assertTrue(parsed.is_file())

    def test_large_function_inline_budget_boundaries(self):
        # Every if reserves three labels, even when its end block is unused.
        # The terminating chain below reserves 4095. Unreachable statements
        # deliberately add one and two dead labels to test 4096 exactly.
        source = ''
        for name, dead in (('belowBudget', ''), ('atBudget', 'print(999)\n'),
                           ('aboveBudget', 'return -2\nprint(999)\n')):
            source += f'function {name}(x: Integer): Integer {{\n'
            source += ''.join(f'if x == {i} {{ return {i} }} else {{\n' for i in range(1365))
            source += 'return -1\n' + '}\n' * 1365 + dead + '}\n'
        source += 'function smallEligible(x: Integer): Integer { return x }\n'
        for name in ('belowBudget', 'atBudget', 'aboveBudget'):
            for value in (0, 1364, 1365):
                source += f'print({name}({value}))\n'
        source += 'print(smallEligible(42))\n'
        llvm = self.executes(source, '0\n1364\n-1\n' * 3 + '42\n', optimizations=OPTIMIZATIONS)
        ir = llvm.read_text()
        for name, guarded in (('belowBudget', False), ('atBudget', True),
                              ('aboveBudget', True), ('smallEligible', False)):
            header = re.search(r'^define i64 @\.minyar\.user\.' + name + r'\([^\n]+', ir, re.M)
            self.assertIsNotNone(header, name)
            self.assertEqual('noinline' in header[0], guarded, header[0])

    def test_sorted_literal_dispatch_preserves_every_value_and_signed_boundaries(self):
        maximum = 9223372036854775807
        keys = [2 * i for i in range(1365)] + [maximum]
        values = [17 * i + 9 for i in range(1365)] + [maximum]
        source = 'function sparse(x: Integer): Integer {\n'
        # Leading zeros must normalize before ordering and global emission.
        for key, value in zip(keys, values):
            source += f'if x == 00{key} {{ /* pure case */ return 00{value} }} else {{\n'
        source += f'return {maximum - 1}\n' + '}\n' * (len(keys) + 1)
        queries = keys + [-9223372036854775808, -1, 1, 2729, 2730, maximum - 1]
        expected = values + [maximum - 1] * 6
        source += 'let queries = [' + ','.join(map(str, queries)) + ']\n'
        source += 'let i = 0\nwhile i < queries.length { print(sparse(queries[i])); i = i + 1 }\n'
        llvm = self.executes(source, ''.join(f'{v}\n' for v in expected), optimizations=OPTIMIZATIONS)
        ir = llvm.read_text()
        tables = re.findall(r'^@\.dispatch\.\d+ = private unnamed_addr constant \[1366 x \{ i64, i64 \}\] \[\n(.*?)\n\]', ir, re.M | re.S)
        self.assertEqual(len(tables), 1)
        pairs = [(int(a), int(b)) for a, b in re.findall(r'\{ i64, i64 \} \{ i64 (\d+), i64 (\d+) \}', tables[0])]
        self.assertEqual(pairs, list(zip(keys, values)))
        self.assertIn('dispatch.search:', ir)
        self.assertNotIn('if.then.', ir)

    def test_dispatch_declines_effects_nonliteral_and_noncanonical_shapes(self):
        def chain(name, *, keys=None, first='return 10', fallback='return 99',
                  prefix='', suffix='', parameters='x: Integer', condition=None):
            keys = list(range(1366)) if keys is None else keys
            body = f'function {name}({parameters}): Integer {{\n' + prefix
            for i, key in enumerate(keys):
                test = condition if i == 0 and condition else f'x == {key}'
                body += f'if {test} {{ ' + (first if i == 0 else f'return {i + 10}') + ' } else {\n'
            return body + fallback + '\n' + '}\n' * len(keys) + suffix + '}\n'
        cases = [
            ('duplicate', dict(keys=[0, 0] + list(range(2, 1366))), '0', '10\n'),
            ('leadingZeroDuplicate', dict(keys=[0, '00'] + list(range(2, 1366))), '0', '10\n'),
            ('unordered', dict(keys=[1, 0] + list(range(2, 1366))), '0', '11\n'),
            ('effectInBody', dict(first='print(44); return 10'), '0', '44\n10\n'),
            ('effectInCondition', dict(condition='noisy(x) == 0'), '0', '44\n10\n'),
            ('mutableSelector', dict(prefix='x = x + 1\n'), '0', '11\n'),
            ('extraParameter', dict(parameters='x: Integer, y: Integer', condition='y == 0'), '5, 0', '10\n'),
            ('trailingBody', dict(suffix='print(44)\n'), '0', '10\n'),
            ('negativeKey', dict(keys=[-1] + list(range(1, 1366))), '-1', '10\n'),
            ('negativeResult', dict(first='return -3'), '0', '-3\n'),
            ('computedFallback', dict(fallback='return 1 + 2'), '2000', '3\n'),
            ('negativeFallback', dict(fallback='return -99'), '2000', '-99\n'),
            ('nestedThen', dict(first='if true { return 10 } else { return 11 }'), '0', '10\n'),
        ]
        for name, options, arguments, expected in cases:
            with self.subTest(shape=name):
                source = 'function noisy(x: Integer): Integer { print(44); return x }\n'
                source += chain(name, **options) + f'print({name}({arguments}))\n'
                llvm = self.executes(source, expected, optimizations=OPTIMIZATIONS)
                self.assertNotIn(' = private unnamed_addr constant [1366 x { i64, i64 }]', llvm.read_text())
                self.assertIn('if.then.', llvm.read_text())
        # The ordinary compiler must reject the original source before a table
        # recognizer could discard a malformed body or unreachable statement.
        source = chain('invalid', suffix='let bad: Integer = "wrong"\n')
        result, llvm = self.compile(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, '', located(source, 'bad:', "the value for 'bad' does not match its declared type")))
        self.assertFalse(llvm.exists())
        source = chain('invalidFallback', fallback='return 9223372036854775808')
        result, llvm = self.compile(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, '', located(source, '9223372036854775808', 'Integer literal is outside the supported range')))
        self.assertFalse(llvm.exists())

    def test_imported_dispatch_tables_have_distinct_stable_names(self):
        self.evidence.inputs[str(MODULE_COMPILER)] = digest(MODULE_COMPILER)
        for name, offset in (('left', 100), ('right', 200)):
            # Identical token positions and declaration names in separate
            # modules require the stable module prefix, not just bodyStart.
            source = 'public function choose(x: Integer): Integer {\n'
            source += ''.join(f'if x == {i} {{ return {i + offset} }} else {{\n' for i in range(1366))
            source += f'return {offset + 9000}\n' + '}\n' * 1367
            (self.directory / f'{name}.min').write_text(source)
        entry = self.directory / 'main.min'
        entry.write_text('use "./left.min" as left\nuse "./right.min" as right\n'
                         'print(left.choose(0)); print(right.choose(0))\n'
                         'print(left.choose(1365)); print(right.choose(1365))\n'
                         'print(left.choose(-1)); print(right.choose(-1))\n')
        llvm = self.directory / 'distinct-tables.ll'
        empty = self.directory / 'empty-state'
        empty.write_text('')
        state = self.directory / 'cold-state'
        stats = self.directory / 'module-stats'
        result = self.evidence.run([MODULE_COMPILER, entry, llvm, '--module-state',
                                    empty, state, stats], timeout=60, phase='compile-module')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        ir = llvm.read_text()
        names = re.findall(r'^(@"minyar\.literal\|[^\n]+\|dispatch\|\d+") = private unnamed_addr constant', ir, re.M)
        self.assertEqual(len(names), 2)
        self.assertEqual(len(set(names)), 2)
        warm = self.directory / 'warm-tables.ll'
        result = self.evidence.run([MODULE_COMPILER, entry, warm, '--module-state',
                                    state, self.directory / 'warm-state', stats],
                                   timeout=60, phase='reuse-module')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        self.assertEqual(warm.read_bytes(), llvm.read_bytes())
        self.assertEqual(stats.read_text().split()[:2], ['3', '0'])
        prepare_llvm_for_link(llvm, LINK_FLAGS)
        self.link_and_run(llvm, '100\n200\n1465\n1565\n9100\n9200\n', OPTIMIZATIONS)

    def link_and_run(self, llvm, expected, optimizations):
        self.evidence.controls.setdefault('execution_oracles', []).append({
            'llvm': str(llvm), 'stdout': expected, 'stderr': '', 'status': 0,
            'optimizations': list(optimizations),
        })
        for opt in optimizations:
            with self.subTest(optimization=opt):
                exe = llvm.with_suffix('.' + opt[1:])
                result = self.evidence.run([CLANG, opt, *LINK_FLAGS, '-Wno-override-module',
                                            llvm, RUNTIME, '-o', exe], timeout=180, phase='link')
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
                result = self.evidence.run([exe], timeout=30, phase='execute')
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected.encode(), b''))

    def test_fifty_thousand_nested_else_branches(self):
        source = deep_chain() + ''.join(f'print(longChain({x}))\n' for x in QUERIES)
        result, llvm = self.compile(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        self.link_and_run(llvm, EXPECTED, OPTIMIZATIONS)

    def test_fifty_thousand_nested_branches_in_imported_function(self):
        self.evidence.inputs[str(MODULE_COMPILER)] = digest(MODULE_COMPILER)
        (self.directory / 'chain.min').write_text('public ' + deep_chain())
        entry = self.directory / 'main.min'
        entry.write_text('use "./chain.min" as chain\n'
                         + ''.join(f'print(chain.longChain({x}))\n' for x in QUERIES))
        llvm = self.directory / 'modules.ll'
        result = self.evidence.run([MODULE_COMPILER, entry, llvm], timeout=60, phase='compile-module')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        prepare_llvm_for_link(llvm, LINK_FLAGS)
        self.link_and_run(llvm, EXPECTED, ('-O0',))

    def test_imported_nested_scopes_and_owned_returns(self):
        self.evidence.inputs[str(MODULE_COMPILER)] = digest(MODULE_COMPILER)
        (self.directory / 'branches.min').write_text('public function choose(flag: Boolean): List<Text> {\nlet seed = ["seed"]\nif flag {\nwhile true { let owned = seed; owned.add("left"); return owned }\n} else {\nwhile false { return ["wrong"] }\nif seed.length == 1 { return [seed[0], "right"] } else { return ["wrong"] }\n}\n}\n')
        entry = self.directory / 'main.min'
        entry.write_text('use "./branches.min" as branches\nlet first = branches.choose(true)\nlet second = branches.choose(false)\nprint(first[0]); print(first[1]); print(second[0]); print(second[1])\nfirst[0] = "changed"\nprint(second[0])\n')
        llvm = self.directory / 'module-scopes.ll'
        result = self.evidence.run([MODULE_COMPILER, entry, llvm], timeout=30, phase='compile-module')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
        prepare_llvm_for_link(llvm, LINK_FLAGS)
        self.link_and_run(llvm, 'seed\nleft\nseed\nright\nseed\n', OPTIMIZATIONS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
