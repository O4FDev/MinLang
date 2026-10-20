#!/usr/bin/env python3
"""Exercise C header imports through Clang, Minyar and the native linker."""

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/c-import"
LIBRARY = "fixtureffi"
OUTPUT_SUFFIXES = (".min", ".c", ".json")
CASES = ("constants", "scalars", "records", "ranges", "layouts", "rejections", "ownership", "gallery", "system")
SELECTION = (
    "LanternReading", "LanternPacked", "LanternSeason", "LanternGolden", "LanternCount", "LanternTone",
    "LANTERN_SHIFTED", "LANTERN_COMPOSED", "LANTERN_WINDOW", "LANTERN_CHOICE", "LANTERN_FROM_FLAG",
    "lantern_add", "lantern_narrow", "lantern_byte", "lantern_count", "lantern_u64",
    "lantern_boolean", "lantern_scale", "lantern_warm", "lantern_season", "lantern_reset",
    "lantern_resets", "lantern_measure", "lantern_echo", "lantern_packed", "lantern_span", "lantern_path",
)


def checked(command, *, timeout=60, success=True, env=None):
    command = list(map(str, command))
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)
    assert (result.returncode == 0) == success, (
        shlex.join(command), result.returncode, result.stdout, result.stderr
    )
    return result


class Suite:
    def __init__(self, options, directory):
        self.options = options
        self.directory = directory
        self.serial = 0
        self.compiler = str(Path(options.compiler).resolve())
        self.runtime = Path(options.runtime).resolve()
        self.driver = Path(options.driver).resolve()
        self.link_flags = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))
        self.clang_flags = shlex.split(os.environ.get("MINYAR_C_LAYOUT_TARGET_FLAGS", ""))
        self.prefix = directory / "fixture"
        self.import_header(FIXTURES / "fixtures.h", self.prefix, SELECTION)
        module = self.prefix.with_suffix(".min").read_text()
        assert re.search(r'public\s+record\s+LanternPoint\s+native\s+"c"', module), module
        assert re.search(r'public\s+record\s+LanternPacked\s+native\s+"c_packed"', module), module
        assert "function lantern_pointer" not in module, module
        manifest = json.loads(self.prefix.with_suffix(".json").read_text())
        assert isinstance(manifest, dict) and "LanternReading" in json.dumps(manifest), manifest
        assert manifest["functions"]["lantern_measure"]["result"] == "LanternReading", manifest
        assert manifest["records"]["LanternPath"]["fields"][1]["type"] == "UInt16", manifest

    def import_header(self, header, prefix, selection, *, flags=(), success=True):
        command = [sys.executable, ROOT / "tools/import-c.py", header, "--output", prefix,
                   "--library", LIBRARY, "--clang", self.options.clang]
        for name in selection:
            command.extend(["--include", name])
        if self.clang_flags or flags:
            command.extend(["--", *self.clang_flags, *flags])
        return checked(command, success=success)

    def executes(self, source, expected, *, prefix=None, runtime=None, status=0, diagnostic=None):
        prefix = prefix or self.prefix
        self.serial += 1
        source_path = self.directory / f"case-{self.serial}.min"
        llvm = source_path.with_suffix(".ll")
        # Keep generated imports relative, including when the directory contains quotes/spaces.
        relative = os.path.relpath(prefix.with_suffix(".min"), source_path.parent)
        source_path.write_text(f'use "./{relative}" as c\n' + source)
        checked([self.compiler, source_path, llvm, "--library", ROOT / "library"])
        self.executes_llvm(source_path, llvm, expected, prefix=prefix, runtime=runtime,
                           status=status, diagnostic=diagnostic)

    def executes_llvm(self, source, llvm, expected, *, prefix, runtime=None, status=0, diagnostic=None):
        for optimization in ("-O0", "-O2"):
            executable = llvm.with_suffix("." + optimization.removeprefix("-") + ".exe")
            flags = [*self.clang_flags, *self.link_flags, optimization]
            environment = dict(os.environ, MINYAR_CLANG=self.options.clang,
                               MINYAR_CLANG_FLAGS=shlex.join([*flags, "-Wno-override-module"]),
                               MINYAR_NATIVE_FLAGS=shlex.join(flags))
            # Both sources belong to the same native library. The production linker
            # builds the ABI adapter from metadata emitted by the Minyar compiler.
            checked([self.driver, "link", ROOT, llvm, runtime or self.runtime, executable,
                     "0", "0", source,
                     "--native-source", f"{LIBRARY}={prefix.with_suffix('.c')}",
                     "--native-source", f"{LIBRARY}={FIXTURES / 'fixtures.c'}"],
                    env=environment, timeout=180)
            result = subprocess.run([str(executable)], cwd=ROOT, text=True, capture_output=True, timeout=20)
            assert result.returncode == status and result.stdout == expected, (
                optimization, result.returncode, result.stdout, result.stderr, expected
            )
            if diagnostic is None:
                assert result.stderr == "", (optimization, result.stderr)
            else:
                assert diagnostic in result.stderr and "Minyar stopped:" in result.stderr, (
                    optimization, result.stderr, diagnostic
                )

    def constants(self):
        self.executes("""
print(c.LanternWinter); print(c.LanternSpring); print(c.LanternAutumn)
print(c.LanternGolden); print(c.LANTERN_SHIFTED); print(c.LANTERN_COMPOSED)
print(c.LANTERN_WINDOW); print(c.LANTERN_CHOICE); print(c.LANTERN_FROM_FLAG)
print(c.LanternDim); print(c.LanternBright)
""", "3\n7\n-2\n42\n50\n53\n11\n42\n3\n1\n9\n")
        flagged = self.directory / "flagged"
        self.import_header(FIXTURES / "fixtures.h", flagged, ["LANTERN_FROM_FLAG"], flags=["-DLANTERN_THEME=7"])
        self.executes("print(c.LANTERN_FROM_FLAG)\n", "8\n", prefix=flagged)
        # Repeating an import must produce byte-identical checked artifacts.
        before = [self.prefix.with_suffix(suffix).read_bytes() for suffix in OUTPUT_SUFFIXES]
        self.import_header(FIXTURES / "fixtures.h", self.prefix, SELECTION)
        assert before == [self.prefix.with_suffix(suffix).read_bytes() for suffix in OUTPUT_SUFFIXES]

    def scalars(self):
        self.executes("""
print(c.lantern_add(20, 22))
print(c.lantern_narrow(-128)); print(c.lantern_narrow(127))
print(c.lantern_byte(0)); print(c.lantern_byte(255))
let count: c.LanternCount = 4294967295
print(c.lantern_count(count)); print(c.lantern_u64(-1))
print(c.lantern_boolean(false)); print(c.lantern_boolean(true))
print(c.lantern_scale(1.5)); print(c.lantern_warm(1.5))
print(c.lantern_season(c.LanternAutumn))
c.lantern_reset(); c.lantern_reset(); print(c.lantern_resets())
""", "42\n-128\n127\n0\n255\n4294967295\n-1\ntrue\nfalse\n3.0\n1.75\n-2\n2\n")

    def records(self):
        self.executes("""
let original = c.lantern_measure(c.LanternPoint { east: 3; north: 4 }, 42.0)
let changed = c.lantern_echo(original)
print(original.id); print(original.place.east); print(original.place.north)
print(original.glow); print(original.lit); print(original.trail[2])
print(changed.place.east); print(changed.glow); print(changed.trail[2])
changed.place.north = 99
print(original.place.north)
let packed = c.lantern_packed(c.LanternPacked { tag: 7; value: 40 })
print(packed.tag); print(packed.value)
print(sizeOf(c.LanternPacked)); print(alignOf(c.LanternPacked)); print(offsetOf(c.LanternPacked, "value"))
let span = c.lantern_span(c.LanternSpan { lower: 3; upper: 8 })
let path = c.lantern_path(c.LanternPath { span: span; width: 5 })
print(span.lower); print(span.upper); print(path.span.lower); print(path.width)
""", "7\n3\n4\n42.0\ntrue\n3\n4\n42.5\n4\n4\n8\n42\n5\n1\n1\n2\n9\n7\n5\n")
        # Selecting a function alone recursively imports its record dependencies.
        dependencies = self.directory / "dependencies"
        self.import_header(FIXTURES / "fixtures.h", dependencies, ["lantern_measure", "lantern_measure"])
        assert dependencies.with_suffix(".min").read_text().count("public function lantern_measure(") == 1
        self.executes("""
let light = c.lantern_measure(c.LanternPoint { east: 8; north: 13 }, 2.5)
print(light.place.east); print(light.place.north); print(light.glow)
""", "8\n13\n2.5\n", prefix=dependencies)
        alias_header = self.directory / "record aliases.h"
        alias_header.write_text("typedef struct Pair { int x; } Pair;\ntypedef Pair Alias;\n")
        for position, selection in enumerate((["Pair", "Alias"], ["Alias", "Pair"])):
            alias_prefix = self.directory / f"record-alias-{position}"
            self.import_header(alias_header, alias_prefix, selection)
            alias_module = alias_prefix.with_suffix(".min").read_text()
            record_name, alias_name = selection
            assert re.search(rf'public\s+record\s+{record_name}\s+native\s+"c"', alias_module), alias_module
            assert re.search(rf"public\s+type\s+{alias_name}\s*=\s*{record_name}\b", alias_module), alias_module
            self.executes("""
function number(value: c.Pair): Integer { return value.x }
function aliasNumber(value: c.Alias): Integer { return value.x }
print(number(c.Alias { x: 42 }))
print(aliasNumber(c.Pair { x: 21 }))
""", "42\n21\n", prefix=alias_prefix)

    def ranges(self):
        for call in ("lantern_narrow(-129)", "lantern_narrow(128)", "lantern_byte(-1)",
                     "lantern_byte(256)", "lantern_count(-1)", "lantern_count(4294967296)",
                     "lantern_add(2147483648, 0)", "lantern_add(0, -2147483649)"):
            self.executes(f"print(c.{call})\n", "", status=1, diagnostic="outside its declared range")
        for value in ("3.5e38", "-3.5e38"):
            self.executes(f"let value: Float = {value}\nprint(c.lantern_scale(value))\n", "",
                          status=1, diagnostic="outside its declared range")

    def layouts(self):
        natural_header = self.directory / "layout field names.h"
        natural_header.write_text("typedef struct { int alignment; char size; } LayoutClash;\n")
        natural_prefix = self.directory / "natural-layout"
        self.import_header(natural_header, natural_prefix, ["LayoutClash"])
        self.executes("""
let value = c.LayoutClash { alignment: 42; size: 65 }
print(value.alignment); print(value.size)
print(sizeOf(c.LayoutClash)); print(alignOf(c.LayoutClash)); print(offsetOf(c.LayoutClash, "size"))
""", "42\n65\n8\n4\n4\n", prefix=natural_prefix)
        copied = self.directory / "changed header"
        copied.mkdir()
        header = copied / "fixtures.h"
        shutil.copyfile(FIXTURES / "fixtures.h", header)
        prefix = copied / "bindings"
        self.import_header(header, prefix, ["lantern_measure"])
        command = [self.options.clang, *self.clang_flags, "-std=c11", "-c", prefix.with_suffix(".c"),
                   "-o", copied / "layout.o"]
        checked(command)
        before = header.read_text()
        assert before.count("    uint8_t id;\n") == 1
        header.write_text(before.replace("    uint8_t id;\n", "    uint8_t id;\n    int64_t inserted;\n"))
        result = checked(command, success=False)
        assert "static assertion" in result.stderr.lower() or "layout" in result.stderr.lower(), result.stderr
        type_header = self.directory / "same width type changes.h"
        original_types = "int signature(int value);\ntypedef struct { int value; } TypeClash;\n"
        type_header.write_text(original_types)
        type_prefix = self.directory / "frozen-types"
        self.import_header(type_header, type_prefix, ["signature", "TypeClash"])
        artifacts = {suffix: type_prefix.with_suffix(suffix).read_bytes() for suffix in OUTPUT_SUFFIXES}
        type_command = [self.options.clang, *self.clang_flags, "-std=c11", "-c", type_prefix.with_suffix(".c"),
                        "-o", self.directory / "frozen-types.o"]
        checked(type_command)
        for changed in (original_types.replace("int signature(int value)", "double signature(double value)"),
                        original_types.replace("struct { int value; }", "struct { float value; }")):
            type_header.write_text(changed)
            result = checked(type_command, success=False)
            assert "static assertion" in result.stderr.lower(), result.stderr
            assert all(type_prefix.with_suffix(suffix).read_bytes() == before for suffix, before in artifacts.items())
            type_header.write_text(original_types)

    def rejections(self):
        unsupported = ("LanternUnion", "LanternBitfield", "LanternFlexible", "LanternAligned",
                       "LanternCallback", "lantern_pointer", "lantern_callback", "lantern_variadic",
                       "lantern_extended", "LANTERN_SQUARE", "LANTERN_TEXT", "LANTERN_HALF",
                       "LANTERN_TOO_LARGE", "lantern_missing")
        prefix = self.directory / "preserved"
        sentinels = {suffix: f"preserve existing {suffix}\n".encode() for suffix in OUTPUT_SUFFIXES}
        for suffix, before in sentinels.items():
            prefix.with_suffix(suffix).write_bytes(before)
        for name in unsupported:
            result = self.import_header(FIXTURES / "fixtures.h", prefix, ["lantern_add", name], success=False)
            assert result.stderr and "Traceback" not in result.stderr, (name, result.stderr)
            assert all(prefix.with_suffix(suffix).read_bytes() == before for suffix, before in sentinels.items()), name
        # Field names must never replace the independent total-size/alignment probes.
        clash_header = self.directory / "packed layout field names.h"
        clash_header.write_text("#pragma pack(push,1)\ntypedef struct { int alignment; char size; } LayoutClash;\n#pragma pack(pop)\n")
        result = self.import_header(clash_header, prefix, ["LayoutClash"], success=False)
        assert result.stderr and "Traceback" not in result.stderr, result.stderr
        assert all(prefix.with_suffix(suffix).read_bytes() == before for suffix, before in sentinels.items())
        old_style_header = self.directory / "old style prototype.h"
        old_style_header.write_text("int old_style();\n")
        result = self.import_header(old_style_header, prefix, ["old_style"], success=False)
        assert result.stderr and "Traceback" not in result.stderr, result.stderr
        assert all(prefix.with_suffix(suffix).read_bytes() == before for suffix, before in sentinels.items())
        synthetic = (
            ("array typedef.h", "typedef unsigned char Digest[16];\n", ["Digest"]),
            ("reserved builtin.h", "typedef struct { int value; } ReservedRecord;\nint sizeOf(int value);\n",
             ["ReservedRecord", "sizeOf"]),
        )
        for header_name, source, selection in synthetic:
            header = self.directory / header_name
            header.write_text(source)
            result = self.import_header(header, prefix, selection, success=False)
            assert result.stderr and "Traceback" not in result.stderr, result.stderr
            assert all(prefix.with_suffix(suffix).read_bytes() == before for suffix, before in sentinels.items())
        missing = self.directory / "missing"
        self.import_header(FIXTURES / "fixtures.h", missing, ["lantern_missing"], success=False)
        assert not any(missing.with_suffix(suffix).exists() for suffix in OUTPUT_SUFFIXES)

    def ownership(self):
        ownership = self.directory / "exact-ownership.o"
        checked([self.options.clang, *self.clang_flags, *self.link_flags, "-O2", "-DMINYAR_SYSTEM_HEAP=1",
                 "-c", ROOT / "tests/memory-contracts-runtime.c", "-o", ownership], timeout=180)
        self.executes("""
let total = 0
for index in 0..500 {
    let light = c.lantern_measure(c.LanternPoint { east: index; north: 4 }, 42.0)
    let returned = c.lantern_echo(light)
    let retained: List<c.LanternReading> = [light, returned]
    total += retained[1].place.east
}
print(total)
""", "125250\n", runtime=ownership)

    def gallery(self):
        prefix = ROOT / "build/c-import/gallery"
        prefix.parent.mkdir(parents=True, exist_ok=True)
        self.import_header(FIXTURES / "fixtures.h", prefix, ["lantern_measure", "lantern_echo"])
        source = ROOT / "examples/gallery/header-lantern.min"
        llvm = self.directory / "gallery.ll"
        checked([self.compiler, source, llvm, "--library", ROOT / "library"])
        self.executes_llvm(source, llvm, source.with_suffix(".stdout").read_text(), prefix=prefix)

    def system(self):
        header = Path("/usr/include/linux/kvm.h")
        if sys.platform != "linux" or platform.machine().lower() not in {"x86_64", "amd64"} or not header.is_file():
            print("C header import system: skipped (Linux x86_64 KVM headers unavailable)", flush=True)
            return False
        prefix = self.directory / "linux-kvm"
        self.import_header(header, prefix, ["kvm_userspace_memory_region", "kvm_regs", "KVM_API_VERSION", "KVM_GET_API_VERSION"])
        registers = "rax rbx rcx rdx rsi rdi rsp rbp r8 r9 r10 r11 r12 r13 r14 r15 rip rflags".split()
        fields = "; ".join(f"{name}: {42 if name == 'rax' else 2 if name == 'rflags' else 0}" for name in registers)
        self.executes("""
let memory = c.kvm_userspace_memory_region {
    slot: 7; flags: 0; guest_phys_addr: 4096; memory_size: 8192; userspace_addr: 0
}
""" + f"let registers = c.kvm_regs {{ {fields} }}\n" + """
print(c.KVM_API_VERSION); print(c.KVM_GET_API_VERSION)
print(memory.slot); print(memory.memory_size); print(registers.rax); print(registers.rflags)
print(sizeOf(c.kvm_userspace_memory_region)); print(alignOf(c.kvm_userspace_memory_region))
print(offsetOf(c.kvm_userspace_memory_region, "memory_size"))
print(sizeOf(c.kvm_regs)); print(offsetOf(c.kvm_regs, "rip"))
""", "12\n44544\n7\n8192\n42\n2\n32\n8\n16\n144\n128\n", prefix=prefix)


def main():
    if not __debug__:
        raise SystemExit("C import checks require Python assertions; remove -O")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=os.environ.get("MINYAR_TEST_COMPILER", "./build/minyarc"))
    parser.add_argument("--runtime", default=os.environ.get("MINYAR_TEST_RUNTIME", "./build/minyar-runtime.o"))
    parser.add_argument("--driver", default="./build/tooling/tools/clang-driver")
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--case", action="append", choices=CASES)
    options = parser.parse_args()
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c import ' ", dir=ROOT / "build") as temporary:
        suite = Suite(options, Path(temporary))
        for case in options.case or CASES:
            if getattr(suite, case)() is not False:
                print(f"C header import {case}: passed", flush=True)


if __name__ == "__main__":
    main()
