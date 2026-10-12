import subprocess
import unittest

from clang_helpers import clang_command
from regressions import CLANG, ROOT, CompilerTestCase


class NativeRecords(CompilerTestCase):
    def test_owned_returns_and_borrowed_arguments_preserve_aliases(self):
        source = self.directory / 'runtime.c'
        contract = (ROOT / 'tests/memory-contracts-runtime.c').read_text()
        source.write_text(contract.replace('../runtime/minyar_runtime.c',
                                           str(ROOT / 'runtime/minyar_runtime.c')) + '''
void *minyar_record_abi_make(void) {
    MinyarRecord *record = minyar_record_new(2);
    minyar_record_set_take(record, 0, (long long)(intptr_t)minyar_integer_text(42));
    minyar_record_set(record, 1, 42);
    return record;
}
long long minyar_record_abi_read(MinyarRecord *record) {
    return minyar_record_get(record, 1);
}
void *minyar_record_abi_echo(MinyarRecord *record) {
    minyar_rc_retain(record);
    return record;
}
''')
        runtime = source.with_suffix('.o')
        built = subprocess.run(clang_command([CLANG, '-O2', '-DMINYAR_SYSTEM_HEAP=1',
                                              '-c', source, '-o', runtime]),
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(built.returncode, 0, built.stderr)
        result, llvm = self.compile('''record Box { label: Text; value: Integer }
function make(): Box { native "record_abi" }
function read(box: Box): Integer { native "record_abi" }
function echo(box: Box): Box { native "record_abi" }
let original = make()
let values: List<Box> = [original, echo(original)]
let index = 0
while index < 1000 { let held = echo(values[0]); index = index + 1 }
print(read(values[1]))
print(original.label)
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        for optimization in ('-O0', '-O2'):
            executable = llvm.with_suffix('.' + optimization[1:])
            linked = subprocess.run(clang_command([CLANG, optimization, '-Wno-override-module',
                                                   llvm, runtime, '-o', executable]),
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(linked.returncode, 0, linked.stderr)
            executed = subprocess.run([executable], capture_output=True, text=True, timeout=30)
            self.assertEqual((executed.returncode, executed.stdout, executed.stderr),
                             (0, '42\n42\n', ''))

    def test_lists_remain_outside_the_native_abi(self):
        self.rejects('function read(values: List<Integer>): Integer { native "record_abi" }\n',
                     'not List')
        self.rejects('function make(): List<Integer> { native "record_abi" }\n',
                     'not List')


if __name__ == '__main__':
    unittest.main()
