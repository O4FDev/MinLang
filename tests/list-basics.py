import os
from pathlib import Path
import shlex
import sys
import unittest
from regressions import CompilerTestCase, ROOT, CLANG, LINK_FLAGS
from clang_helpers import clang_command

sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source


class ListBasics(CompilerTestCase):
    def test_scalar_types_and_aliases(self):
        self.executes('''let values = [1, 2, 3]
let alias = values
let copy = values.slice(1, 3)
copy[0] = 9
print(values.pop()); print(alias.length); print(copy[0]); print(values[1])
values.truncate(0)
print(alias.length)
values.add(7)
print(alias.pop())
let floats = [1.5, -0.0]
print(floats.slice(0, 1).pop()); print(floats.pop())
let flags = [true, false]
print(flags.pop())
let characters = ['a', '🙂']
print(characters.pop())
let empty: List<Text> = []
print(empty.slice(0, 0).length)
empty.truncate(0)
''', '3\n2\n9\n2\n0\n7\n1.5\n-0.0\nfalse\n🙂\n0\n')

    def test_reference_transfer_shallow_copy_and_cycles(self):
        self.executes('''record Node { text: Text; links: List<Node> }
let node = Node { text: Text(123); links: [] }
let nodes = [node]
node.links = nodes
let copy = nodes.slice(0, 1)
let removed = nodes.pop()
print(nodes.length)
copy[0].text = Text(456)
copy.truncate(0)
print(removed.text)
removed.links = []
function take(): Text { let values = [Text(789)]; return values.pop() }
print(take())
print([Text(321)].pop())
''', '0\n456\n789\n321\n')

    def test_receiver_capture_and_argument_order(self):
        self.executes('''record Holder { values: List<Text> }
function start(holder: Holder): Integer { holder.values = [Text(9)]; print("start"); return 0 }
function end(alias: List<Text>): Integer { alias.add(Text(3)); print("end"); return alias.length }
let holder = Holder { values: [Text(1), Text(2)] }
let alias = holder.values
let copy = holder.values.slice(start(holder), end(alias))
alias.truncate(0)
print(copy.pop()); print(copy.pop()); print(copy.pop())
print(holder.values.pop())
let lonely = Holder { values: [Text(4)] }
print(lonely.values.slice(start(lonely), 1).pop())
''', 'start\nend\n3\n2\n1\n9\nstart\n4\n')

    def test_invalid_bounds_have_controlled_exact_errors(self):
        for operation, diagnostic in (
                ('values.pop()', 'List position -1 is outside its length of 0.'),
                ('values.truncate(-1)', 'List truncate length is outside its length.'),
                ('values.truncate(1)', 'List truncate length is outside its length.'),
                ('values.slice(-1, 0)', 'List slice positions are outside its length.'),
                ('values.slice(1, 0)', 'List slice positions are outside its length.'),
                ('values.slice(0, 9223372036854775807)', 'List slice positions are outside its length.')):
            with self.subTest(operation=operation):
                self.executes('let values: List<Text> = []\n' + operation + '\n', '', 1,
                              'Minyar stopped: ' + diagnostic + '\n')

    def test_argument_types_and_arity(self):
        self.rejects('let values = [1]\nvalues.truncate(true)\n', 'List.truncate positions must be Integers')
        self.rejects('let values = [1]\nvalues.slice(0, false)\n', 'List.slice positions must be Integers')
        self.rejects('let values = [1]\nvalues.pop(0)\n', "expected ')'")


class RuntimeBasics(CompilerTestCase):
    def test_allocation_and_collector_profiles(self):
        cycle = self.directory / 'cycle.c'
        cycle.write_text(engine_source(ROOT))
        profiles = [('eager', []), ('system', ['-DMINYAR_SYSTEM_HEAP=1']),
                    ('bounded', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=1']),
                    ('lazy', ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=1'])]
        environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
        for traced in (False, True):
            for name, flags in profiles:
                for optimization in ('-O0', '-O2'):
                    with self.subTest(traced=traced, profile=name, optimization=optimization):
                        executable = self.directory / f'{traced}-{name}-{optimization[1:]}'
                        definitions = flags + ([f'-DMINYAR_LIST_TEST_ENGINE="{cycle}"'] if traced else [])
                        result = self.evidence.run(clang_command([CLANG, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            optimization, *LINK_FLAGS, *definitions, '-iquote', str(ROOT / 'runtime'),
                            str(ROOT / 'tests/list-basics.c'), '-lm', '-o', str(executable)]), timeout=60, phase='runtime-link')
                        self.assertEqual(result.returncode, 0, result.stderr)
                        result = self.evidence.run([str(executable)], env=environment, timeout=30, phase='runtime-execute')
                        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'list basics ownership passed\n', b''))
                        for mode in ('empty-pop', 'negative-truncate', 'long-truncate', 'negative-slice', 'reversed-slice', 'long-slice'):
                            diagnostic = ('List position -1 is outside its length of 0.' if mode == 'empty-pop' else
                                          'List truncate length is outside its length.' if 'truncate' in mode else
                                          'List slice positions are outside its length.')
                            result = self.evidence.run([str(executable), mode], env=dict(environment, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'), timeout=30, phase='runtime-error')
                            self.assertEqual((result.returncode, result.stdout, result.stderr),
                                             (1, b'', ('Minyar stopped: ' + diagnostic + '\n').encode()))


if __name__ == '__main__':
    unittest.main()
