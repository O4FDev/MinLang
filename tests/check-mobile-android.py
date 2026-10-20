#!/usr/bin/env python3
"""Compile both real NDK archives and link JNI libraries with no undefined symbols."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mobile", ROOT / "tools/mobile.py")
mobile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile)


def main():
    if not os.environ.get("ANDROID_NDK_HOME"):
        raise RuntimeError("check-mobile-android requires an installed ANDROID_NDK_HOME")
    for target, machine in (("android-arm64", 183), ("android-x86_64", 62)):
        args = mobile.parser().parse_args([str(ROOT / "examples/mobile-hello/android/main.min"),
                                          "--target", target, "--no-bootstrap"])
        archive = mobile.build(args)
        tools = mobile.android_tools(args)
        library = archive.parent / "libminyar_hello.so"
        mobile.run([tools["clang"], "-shared", "-fPIC", "-Wl,-z,defs", "-Wl,--exclude-libs,ALL",
                    "-Wl,-z,max-page-size=16384", str(ROOT / "examples/mobile-hello/android/minyar-jni.c"),
                    str(archive), "-lm", "-o", str(library)])
        header = library.read_bytes()[:64]
        if header[:6] != b"\x7fELF\x02\x01" or int.from_bytes(header[18:20], "little") != machine:
            raise RuntimeError(f"{target}: expected a 64-bit ELF shared library for machine {machine}")
        readelf = str(Path(tools["archive"]).with_name("llvm-readelf"))
        report = subprocess.run([readelf, "--dyn-syms", "--wide", str(library)], check=True, capture_output=True, text=True).stdout
        if "Java_org_minyar_hello_MainActivity_answer" not in report:
            raise RuntimeError("JNI entry missing from the dynamic symbol table")
        if any(line.split()[-1:] == ["main"] for line in report.splitlines()):
            raise RuntimeError("the generated main leaked into the JNI dynamic ABI")
        summary = {"target": target, "elf_machine": machine, "archive_bytes": archive.stat().st_size,
                   "jni_bytes": library.stat().st_size, "ndk": tools["sdk"]}
        (archive.parent / "jni-check.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(f"{target}: PIC archive + JNI shared link passed ({library.stat().st_size} bytes)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, mobile.MobileError) as error:
        print(f"mobile Android check failed: {error}", file=sys.stderr)
        sys.exit(1)
