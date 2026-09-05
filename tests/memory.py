#!/usr/bin/env python3
"""Check reference lifetimes and memory reclamation."""
import json
import subprocess
import sys
import unittest
from regressions import CompilerTestCase, CLANG, RUNTIME, LINK_FLAGS

class Memory(CompilerTestCase):
    def test_discarded_text_is_reclaimed(self):
        source = 'let original = "' + 'x' * 32768 + '"\nlet index = 0\nwhile index < 4000 {\nlet copy = original.slice(0, original.length)\nindex = index + 1\n}\nprint(index)\n'
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        for optimization in ('-O0', '-O2'):
            with self.subTest(optimization=optimization):
                exe = llvm.with_suffix('.' + optimization[1:])
                subprocess.run([CLANG, optimization, *LINK_FLAGS, '-Wno-override-module', str(llvm), str(RUNTIME), '-o', str(exe)], check=True, capture_output=True, timeout=30)
                # Measure only the program in a fresh parent; the linker must not
                # contaminate RUSAGE_CHILDREN's maximum resident set size.
                measurement = subprocess.run([sys.executable, '-c', 'import json,resource,subprocess,sys; p=subprocess.run([sys.argv[1]],capture_output=True); print(json.dumps([p.returncode,p.stdout.decode(),resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss]))', str(exe)], text=True, capture_output=True, check=True, timeout=30)
                status, stdout, rss = json.loads(measurement.stdout)
                self.assertEqual(status, 0)
                self.assertEqual(stdout, '4000\n')
                mib = rss / (1024 * 1024 if sys.platform == 'darwin' else 1024)
                print(f'discarded Text {optimization}: {mib:.1f} MiB peak resident memory')
                self.assertLess(mib, 48, f'discarded Text retained {mib:.1f} MiB')

    def test_shared_returned_and_nested_values(self):
        churn = 'function churn(): Text {\nlet original = "' + 'x' * 32768 + '"\nlet index = 0\nwhile index < 100 {\nlet copy = original.slice(0, original.length)\nindex = index + 1\n}\nreturn "tail" + "!"\n}\n'
        source = '''record Pair { first: Text; second: Text }
record Leaf { label: Text }
record Node { children: List<Leaf>; label: Text }
function pair(left: Text, right: Text): Pair {
return Pair { first: left; second: right }
}
function node(): Node {
let children: List<Leaf> = []
let result = Node { children: children; label: "retained" + "!" }
children.add(Leaf { label: result.label })
return result
}
''' + churn + '''let retained = node()
let alias = retained.children
let result = pair("head" + "!", churn())
let constructed = Pair { first: "field" + "!"; second: churn() }
print(result.first)
print(result.second)
print(constructed.first)
print(constructed.second)
print(alias[0].label)
let index = 0
while index < 1000 {
let discarded = node()
index = index + 1
}
print(alias[0].label)
'''
        self.executes(source, 'head!\ntail!\nfield!\ntail!\nretained!\nretained!\n')

if __name__ == '__main__':
    unittest.main(verbosity=2)
