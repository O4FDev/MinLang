"""Cold/warm module-driver Map equivalence and contained private type changes."""
import unittest
from regressions import CompilerTestCase, ROOT, LINK_FLAGS
from llvm_sanitizer import prepare_llvm_for_link


class MapModuleDriver(CompilerTestCase):
    def test_signed_nested_types_reuse_the_compiled_type_table(self):
        value_type = 'Map<Integer, List<Map<Text, Map<Float, List<Integer>>>>>'
        path = self.directory / 'nested.min'
        path.write_text(f'function size(m: {value_type}): Integer {{ return m.length }}\n'
                        f'let m: {value_type} = Map()\nprint(size(m))\n')
        prior, next_state, stats = (self.directory / name for name in ('prior', 'next', 'stats'))
        prior.write_text('')
        outputs = []
        for phase in ('cold', 'warm'):
            llvm = self.directory / (phase + '.ll')
            result = self.evidence.run([str(ROOT / 'build/minyarc-modules'), str(path), str(llvm),
                                       '--module-state', str(prior), str(next_state), str(stats)],
                                      capture_output=True, text=True, timeout=30, phase='map-table-' + phase)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(llvm.read_bytes())
            if phase == 'cold':
                prior.write_bytes(next_state.read_bytes())
            else:
                fields = stats.read_text().split()
                self.assertEqual(fields[-1], 'true')
                self.assertGreater(int(fields[0]), 0)
                self.assertEqual((int(fields[1]), int(fields[4])), (0, 0))
        self.assertEqual(outputs[0], outputs[1])

    def compile(self, source):
        self.serial += 1
        path = self.directory / f'case{self.serial}.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        command = [str(ROOT / 'build/minyar-module-build'), str(ROOT / 'build/minyarc-modules'),
                   str(path), str(llvm), str(self.directory / 'cache')]
        result = self.evidence.run(command, capture_output=True, text=True, timeout=30, phase='map-module-cold')
        if result.returncode == 0:
            first = llvm.read_bytes()
            warm = self.evidence.run(command, capture_output=True, text=True, timeout=30, phase='map-module-warm')
            self.assertEqual(warm.returncode, 0, warm.stderr)
            self.assertEqual(first, llvm.read_bytes())
            prepare_llvm_for_link(llvm, LINK_FLAGS)
        return result, llvm

    def test_contained_private_record_type_changes_invalidate_importer(self):
        module = self.directory / 'values.min'
        module.write_text('''record Value { value: Text }
public function make(): Map<Text, List<Value>> {
let m = Map<Text, List<Value>>()
m["a"] = [Value { value: "typed" + "!" }]
return m
}
''')
        source = 'use "./values.min" as values\nlet m = values.make()\nprint(m["a"][0].value)\n'
        self.executes(source, 'typed!\n')
        # Keep the importing source path and text identical. Only the reachable
        # record field changes, behind Map and List wrappers in a public return.
        self.serial = 0
        module.write_text('''record Value { value: Integer }
public function make(): Map<Text, List<Value>> {
let m = Map<Text, List<Value>>()
m["a"] = [Value { value: 42 }]
return m
}
''')
        self.executes(source, '42\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
