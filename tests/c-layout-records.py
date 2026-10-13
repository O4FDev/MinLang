import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from c_layout_abi import source as c_abi_source
from cycle_runtime import engine_source

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc'))
RUNTIME = Path(os.environ.get('MINYAR_TEST_RUNTIME', ROOT / 'build/minyar-runtime.o'))
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')
FLAGS = shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', ''))
TARGET = shlex.split(os.environ.get('MINYAR_C_LAYOUT_TARGET_FLAGS', ''))
RUNNER = shlex.split(os.environ.get('MINYAR_C_LAYOUT_RUNNER', ''))
MIXED = '''record Mixed native "c" {
    tag: UInt8; delta: Int16; count: UInt32; mask: UInt64
    narrow: Float32; wide: Float64; enabled: Boolean; bytes: Bytes[3]
}
'''
NESTED = '''record Segment native "c" { selector: UInt16; base: UInt64 }
record Outer native "c" { tag: UInt8; segment: Segment; limit: UInt32 }
'''


class CLayoutRecords(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory(prefix='minyar-c-layout-')
        self.addCleanup(work.cleanup)
        self.work = Path(work.name)
        self.serial = 0
        self.control = self.work / 'control.o'
        self.run_checked(clang_command([CLANG, *TARGET, '-O2', *FLAGS, '-Wno-unused-command-line-argument', '-c',
            '-I', ROOT / 'runtime', ROOT / 'tests/c-layout-records.c', '-o', self.control]))

    def run_checked(self, command):
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def compile(self, source):
        self.serial += 1
        path = self.work / f'case{self.serial}.min'
        path.write_text(source)
        llvm = path.with_suffix('.ll')
        result = subprocess.run([str(COMPILER), str(path), str(llvm), '--library', str(ROOT / 'library')],
                                capture_output=True, text=True, timeout=60)
        return result, llvm

    def executes(self, source, stdout, status=0, stderr=''):
        result, llvm = self.compile(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        bridge = self.work / f'bridge{self.serial}.o'
        generated = c_abi_source(llvm.read_text().splitlines())
        objects = [self.control]
        if generated:
            bridge_source = bridge.with_suffix('.c')
            bridge_source.write_text(generated)
            self.run_checked(clang_command([CLANG, *TARGET, '-O2', *FLAGS, '-Wno-unused-command-line-argument', '-c', bridge_source, '-o', bridge]))
            objects.append(bridge)
        runtime = RUNTIME
        raw = llvm.read_text()
        if '; minyar-callback-runtime:' in raw or '; minyar-cycle-runtime:' in raw:
            configured = self.work / f'graph{self.serial}.c'
            contract = (ROOT / 'tests/memory-contracts-runtime.c').read_text()
            configured.write_text(contract.replace('#include "../runtime/minyar_runtime.c"', engine_source(ROOT)))
            runtime = configured.with_suffix('.o')
            self.run_checked(clang_command([CLANG, *TARGET, '-O2', *FLAGS,
                '-DMINYAR_SYSTEM_HEAP=1', '-iquote', ROOT / 'runtime', '-c', configured, '-o', runtime]))
        prepare_llvm_for_link(llvm, FLAGS)
        for optimization in ('-O0', '-O2'):
            executable = llvm.with_suffix('.' + optimization[1:])
            self.run_checked(clang_command([CLANG, *TARGET, optimization, *FLAGS, '-Wno-override-module',
                llvm, runtime, *objects, '-lm', '-o', executable]))
            result = subprocess.run([*RUNNER, str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (status, stdout, stderr))

    def test_native_package_driver_builds_and_reuses_aggregate_adapters(self):
        package = self.work / 'layout.min'
        package.write_text('''public record Pair native "c" { bits: UInt64; value: Float64 }
public function pair(value: Pair, add: Integer, scale: Float): Pair { native "layout" value }
''')
        result, llvm = self.compile('''use "./layout.min" as layout
let value = layout.pair(layout.Pair { bits: 40; value: 1.5 }, 2, 2.0)
print(value.bits); print(value.value); print(sizeOf(layout.Pair))
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        for optimization in ('-O0', '-O2'):
            executable = self.work / ('package-' + optimization)
            environment = dict(os.environ, MINYAR_CLANG=CLANG,
                MINYAR_CLANG_FLAGS=shlex.join([*TARGET, *FLAGS, optimization, '-Wno-override-module']),
                MINYAR_NATIVE_FLAGS=shlex.join([*TARGET, *FLAGS, optimization]))
            environment.pop('MINYAR_LINK_ARTIFACTS', None)
            command = [sys.executable, str(ROOT / 'tools/clang-driver.py'), 'link', str(ROOT),
                str(llvm), str(RUNTIME), str(executable), '0', '0', str(llvm.with_suffix('.min')),
                '--native-source', 'layout=' + str(ROOT / 'tests/c-layout-records.c')]
            for repeat in range(2):
                linked = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=180)
                self.assertEqual(linked.returncode, 0, linked.stdout + linked.stderr)
                executed = self.run_checked([*RUNNER, str(executable)])
                self.assertEqual((executed.stdout, executed.stderr), ('42\n3.0\n16\n', ''))

    def test_storage_owner_counts_and_nested_cleanup(self):
        for optimization in ('-O0', '-O2'):
            executable = self.work / ('storage-' + optimization)
            self.run_checked(clang_command([CLANG, *TARGET, optimization, *FLAGS,
                '-DMINYAR_SYSTEM_HEAP=1', ROOT / 'tests/c-layout-storage.c', '-pthread', '-lm', '-o', executable]))
            result = self.run_checked([*RUNNER, str(executable)])
            self.assertEqual(result.stdout,
                'C-layout roots, nested views, borrowed addresses and ordinary Bytes passed\n')
            self.assertFalse(result.stderr)
            for state in ('pinned', 'shrunk'):
                rejected = subprocess.run([*RUNNER, str(executable), state],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual((rejected.returncode, rejected.stdout, rejected.stderr),
                    (1, '', 'Minyar stopped: these Bytes cannot be detached.\n'))

    def test_c_fields_padding_pointer_calls_and_return_copy(self):
        self.executes(MIXED + '''function verify(value: Mixed): Integer { native "layout" }
function echo(value: Mixed): Mixed { native "layout" }
let bytes = Bytes(3)
bytes[0] = 7; bytes[1] = 8; bytes[2] = 9
let value = Mixed { tag: 255; delta: -32768; count: 4294967295; mask: -1
    narrow: 1.25; wide: -3.5; enabled: true; bytes: bytes }
print(sizeOf(Mixed)); print(alignOf(Mixed)); print(offsetOf(Mixed, "wide"))
print(verify(value)); print(value.delta); print(value.count)
let copied = echo(value)
value.count = 10
print(copied.count); print(copied.mask); print(copied.narrow); print(copied.enabled)
''', '40\n8\n24\n1\n32767\n42\n42\n-1\n1.25\ntrue\n')

    def test_all_integer_widths_pointer_character_and_aliases(self):
        self.executes('''record Widths native "c" {
    s8: Int8; u8: UInt8; s16: Int16; u16: UInt16; s32: Int32; u32: UInt32
    s64: Int64; u64: UInt64; pointer: Pointer; integer: Integer; floating: Float; character: Character
}
function widths(value: Widths): Integer { native "layout" }
function widthsSize(): Integer { native "layout" }
let value = Widths { s8: -128; u8: 255; s16: -32768; u16: 65535; s32: -2147483648
    u32: 4294967295; s64: -9223372036854775808; u64: -1; pointer: 0; integer: 42
    floating: 1.5; character: '🙂' }
print(sizeOf(Widths) == widthsSize()); print(widths(value))
print(value.s8); print(value.s16); print(value.s32); print(value.s64); print(value.character)
''', 'true\n1\n127\n32767\n2147483647\n-9223372036854775808\n🙂\n')

    def test_by_value_integer_sse_hfa_memory_and_register_pressure(self):
        self.executes('''record Pair native "c" { bits: UInt64; value: Float64 }
record HFA native "c" { x: Float64; y: Float64; z: Float64 }
record FloatHFA native "c" { x: Float32; y: Float32; z: Float32; w: Float32 }
record IntPair native "c" { first: Int64; second: Int64 }
function pair(value: Pair, add: Integer, scale: Float): Pair { native "layout" value }
function hfa(value: HFA): HFA { native "layout" value }
function floatHfa(value: FloatHFA): FloatHFA { native "layout" value }
function many(a: Integer, b: Integer, c: Integer, d: Integer, e: Integer, f: Integer,
    value: IntPair, g: Integer, h: Integer): IntPair { native "layout" value }
function zero(): Pair { native "layout" value }
let original = Pair { bits: -1; value: 2.5 }
let shifted = pair(original, 3, 2.0)
print(shifted.bits); print(shifted.value); print(original.bits); print(original.value)
let floats = hfa(HFA { x: 1.0; y: 2.0; z: 3.0 })
print(floats.x); print(floats.y); print(floats.z)
let singles = floatHfa(FloatHFA { x: 1.0; y: 2.0; z: 3.0; w: 4.0 })
print(singles.x); print(singles.y); print(singles.z); print(singles.w)
let integers = many(1, 2, 3, 4, 5, 6, IntPair { first: 10; second: 20 }, 7, 8)
print(integers.first); print(integers.second)
let returned = zero()
print(returned.bits); print(returned.value)
let unaligned = cView(Pair, Bytes(17), 1)
unaligned.bits = 40; unaligned.value = 1.5
let aligned = pair(unaligned, 2, 2.0)
print(aligned.bits); print(aligned.value)
''', '2\n5.0\n-1\n2.5\n4.0\n3.0\n5.0\n4.0\n3.0\n2.0\n1.0\n20\n46\n-1\n4.5\n42\n3.0\n')

    def test_by_value_packed_large_and_nested_results(self):
        self.executes(MIXED + NESTED + '''record Event native "c_packed" { events: UInt32; data: UInt64 }
function packedValue(value: Event): Event { native "layout" value }
function large(value: Mixed): Mixed { native "layout" value }
function nestedValue(value: Outer): Outer { native "layout" value }
let event = packedValue(Event { events: 40; data: -1 })
print(event.events); print(event.data)
let value = large(Mixed { tag: 2; delta: 4; count: 6; mask: -1
    narrow: 1.25; wide: 2.5; enabled: true; bytes: Bytes(3) })
print(value.tag); print(value.delta); print(value.count); print(value.wide); print(value.enabled)
let nested = nestedValue(Outer { tag: 3; segment: Segment { selector: 4; base: 5 }; limit: 6 })
print(nested.tag); print(nested.segment.selector); print(nested.segment.base)
''', '42\n0\n1\n-7\n7\n3.75\nfalse\n3\n4\n11\n')

    def test_packed_epoll_layout(self):
        self.executes('''record Event native "c_packed" { events: UInt32; data: UInt64 }
function event(value: Event): Integer { native "layout" }
let value = Event { events: 4294967295; data: -1 }
print(sizeOf(Event)); print(alignOf(Event)); print(offsetOf(Event, "data")); print(event(value))
''', '12\n1\n4\n1\n')

    def test_nested_views_survive_scope_and_write_through(self):
        self.executes(NESTED + '''function outer(value: Outer): Integer { native "layout" }
function make(): Segment {
    let bytes = Bytes(sizeOf(Outer))
    let value = cView(Outer, bytes, 0)
    value.tag = 3; value.segment.selector = 65535; value.segment.base = 42; value.limit = 99
    print(outer(value))
    return value.segment
}
let segment = make()
print(segment.selector); print(segment.base)
segment.base += 8
print(segment.base)
let alias = cView(Segment, cBytes(segment), 0)
alias.selector = 20
print(segment.selector)
''', '1\n65535\n42\n50\n20\n')

    def test_external_address_is_borrowed(self):
        self.executes(NESTED + '''function address(): Integer { native "layout" }
let value = cAt(Segment, address())
print(value.selector); print(value.base)
value.base = 99
let nested = cView(Segment, cBytes(value), 0)
print(nested.base)
''', '10\n42\n99\n')

    def test_pin_rejects_growth_and_regrowth_after_shrink(self):
        for operation in ('bytes.resize(17)', 'bytes.resize(0); bytes.resize(16)', 'bytes.add(1)'):
            with self.subTest(operation=operation):
                self.executes(NESTED + '''let bytes = Bytes(16)
let value = cView(Segment, bytes, 0)
value.base = 42
''' + operation + '\n', '', 1, 'Minyar stopped: Bytes storage with C-layout views cannot grow.\n')

    def test_native_append_cannot_move_pinned_storage(self):
        self.executes(NESTED + '''function appendZero(bytes: Bytes): Integer { native "layout" }
function append(bytes: Bytes): Integer { native "layout" }
let bytes = Bytes(16)
let value = cView(Segment, bytes, 0)
value.base = 42
print(appendZero(bytes)); print(value.base)
bytes.resize(8)
print(appendZero(bytes)); print(value.base)
print(append(bytes))
''', '1\n42\n1\n42\n', 1, 'Minyar stopped: Bytes storage with C-layout views cannot grow.\n')

    def test_bounds_integer_width_null_return_and_alignment_diagnostics(self):
        for source, diagnostic in (
            ('record R native "c" { value: UInt8 }\nlet value = R { value: 256 }\n',
             'an Integer does not fit in its C-layout field.'),
            (NESTED + 'let value = cView(Segment, Bytes(16), 1)\n',
             'a C-layout view must fit within its backing Bytes.'),
            (MIXED + 'function null(): Mixed { native "layout" }\nlet value = null()\n',
             'a native C-layout record returned a null pointer.'),
            (MIXED + 'function verify(value: Mixed): Integer { native "layout" }\n'
             'let value = cView(Mixed, Bytes(41), 1)\nprint(verify(value))\n',
             'a native C-layout record pointer is not correctly aligned.'),
        ):
            with self.subTest(diagnostic=diagnostic):
                self.executes(source, '', 1, 'Minyar stopped: ' + diagnostic + '\n')

    def test_managed_holders_callbacks_and_results_keep_C_owners(self):
        self.executes(NESTED + '''record Holder { segment: Segment; label: Text }
function make(): Callback<Integer, Segment> {
    let holder = Holder { segment: Segment { selector: 7; base: 40 }; label: "held" }
    return function(delta: Integer): Segment {
        holder.segment.base += delta
        return holder.segment
    }
}
function success(value: Segment): Result<Segment, Text> { return Ok<Segment, Text>(value) }
let callback = make()
let value = callback(2)
let values: List<Segment> = [value, callback(1)]
print(value.base); print(values[1].base)
let result = success(value)
match result { Ok(held) { print(held.base); print(held.selector) } Err(error) { fail(error) } }
''', '43\n43\n43\n7\n')

    def test_recovery_preserves_pointer_and_value_native_ownership(self):
        self.executes('''use "calldepth" as depth
use "errors" as errors
record Single native "c" { bits: UInt64 }
function pendingPointer(): Single { native "layout" }
function pendingValue(): Single { native "layout" value }
let pointer = depth.run(4, function(): Integer { let value = pendingPointer(); return value.bits })
let value = depth.run(4, function(): Integer { let record = pendingValue(); return record.bits })
print(errors.integerOk(pointer)); print(errors.integerOk(value)); print("alive")
''', 'false\nfalse\nalive\n')

    def test_native_layout_past_the_first_thousand_nominal_types(self):
        records = ''.join(f'record R{index} {{}}\n' for index in range(1001))
        self.executes(records + '''record Single native "c" { bits: UInt64 }
function nominal(value: Single): Integer { native "layout" }
print(nominal(Single { bits: 42 }))
''', '1\n')

    def test_ordinary_functions_can_use_layout_builtin_names(self):
        self.executes('''function sizeOf(): Integer { return 42 }
function answer(): Integer { native "c" }
record Plain { value: Integer }
print(sizeOf()); print(answer()); print(Plain { value: 21 }.value)
''', '42\n7\n21\n')

    def test_invalid_layouts_and_managed_record_diagnostics(self):
        for source, diagnostic in (
            ('record R native "c" { value: Text }\n', 'C-layout fields require'),
            ('record R native "c" { value: Bytes }\n', "expected '['"),
            ('record R native "c" {}\n', 'must contain at least one field'),
            ('record R native "c" { value: R }\n', 'recursive inline fields'),
            ('record M { value: Integer }\nrecord R native "c" { value: M }\n', 'cannot contain a managed record'),
            ('record R native "c" { value: UInt8 }\nlet value = R {}\n', "missing field 'value'"),
            ('record R native "c" { value: UInt8 }\nlet value = R { value: true }\n', 'wrong type'),
            ('record R { value: UInt8 }\n', "unknown type 'UInt8'"),
        ):
            with self.subTest(diagnostic=diagnostic):
                result, llvm = self.compile(source)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(diagnostic, result.stderr)
                self.assertFalse(llvm.exists())


if __name__ == '__main__':
    unittest.main()
