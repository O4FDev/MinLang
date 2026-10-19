#!/usr/bin/env python3
"""Exercise ELF rejection rules with actual native Clang outputs."""
import importlib.util
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

if not __debug__:
    raise SystemExit("packager checks require Python assertions; remove -O")

root = Path(__file__).resolve().parent.parent
specification = importlib.util.spec_from_file_location("package_linux", root / "scripts/package-linux.py")
packager = importlib.util.module_from_spec(specification)
specification.loader.exec_module(packager)
clang = sys.argv[1]
arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64"
opposite = "x86_64" if arch == "arm64" else "arm64"


def reject(binary, expected, *, cpu=arch, minimum=(2, 39), directory):
    try:
        packager.audit(binary, cpu, minimum, directory)
    except ValueError as error:
        assert expected in str(error), (expected, error)
    else:
        raise AssertionError(f"accepted unsafe ELF: {expected}")


with tempfile.TemporaryDirectory(prefix="minyar ELF audit '") as temporary:
    directory = Path(temporary)
    source = directory / "main.c"
    source.write_text("int main(void) { return 0; }\n")

    def build(name, *arguments):
        target = directory / name
        subprocess.run([clang, str(source), *arguments, "-o", str(target)], check=True, capture_output=True)
        return target

    ordinary = build("ordinary")
    packager.audit(ordinary, arch, (2, 39), directory)
    reject(ordinary, "expected native", cpu=opposite, directory=directory)
    reject(ordinary, "above the declared minimum", minimum=(2, 0), directory=directory)
    absolute = build("absolute", "-Wl,-rpath,/tmp/build-machine-only")
    reject(absolute, "non-relocatable", directory=directory)
    escaped = build("escaped", "-Wl,-rpath,$ORIGIN/../../outside")
    reject(escaped, "escapes the distribution", directory=directory)
    interpreter = build("interpreter", "-Wl,--dynamic-linker=/tmp/build-machine-loader")
    reject(interpreter, "unexpected ELF interpreter", directory=directory)
    relative = build("relative", "-Wl,-rpath,$ORIGIN/lib")
    packager.audit(relative, arch, (2, 39), directory)
print("Linux ELF audit: native CPU, glibc floor, interpreter and relocatable library paths passed")
