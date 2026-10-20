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
        check_target(target, machine, False)
        check_target(target, machine, True)


def check_target(target, machine, shared_view):
    source = "ui.min" if shared_view else "main.min"
    extra = ["-o", str(ROOT / "build/mobile" / target / "libminyar-ui.a")] if shared_view else []
    args = mobile.parser().parse_args([str(ROOT / "examples/mobile-hello/android" / source),
                                      "--target", target, "--no-bootstrap", *extra])
    archive = mobile.build(args)
    tools = mobile.android_tools(args)
    library = archive.parent / ("libminyar_ui.so" if shared_view else "libminyar_hello.so")
    provider = ROOT / ("runtime/native/mobileandroid.c" if shared_view else "examples/mobile-hello/android/minyar-jni.c")
    mobile.run([tools["clang"], "-shared", "-fPIC", "-Wl,-z,defs", "-Wl,--exclude-libs,ALL",
                "-Wl,-z,max-page-size=16384", "-O2", "-fvisibility=hidden", "-std=c11", str(provider),
                str(archive), "-lm", "-o", str(library)])
    if shared_view:
        cmake = archive.parent / "cmake-ui"
        abi = "arm64-v8a" if target == "android-arm64" else "x86_64"
        mobile.run(["cmake", "-S", str(ROOT / "examples/mobile-hello/android/ui"), "-B", str(cmake),
                    "-DCMAKE_TOOLCHAIN_FILE=" + str(Path(tools["sdk"]) / "build/cmake/android.toolchain.cmake"),
                    "-DANDROID_ABI=" + abi, "-DANDROID_PLATFORM=android-28", "-DCMAKE_BUILD_TYPE=Release",
                    "-DCMAKE_C_FLAGS_RELEASE=-O2 -DNDEBUG", "-DMINYAR_ROOT=" + str(ROOT), "-DMINYAR_ARCHIVE=" + str(archive)])
        mobile.run(["cmake", "--build", str(cmake), "--parallel", "2"])
        library = cmake / "libminyar_ui.so"
    header = library.read_bytes()[:64]
    if header[:6] != b"\x7fELF\x02\x01" or int.from_bytes(header[18:20], "little") != machine:
        raise RuntimeError(f"{target}: expected a 64-bit ELF shared library for machine {machine}")
    readelf = str(Path(tools["archive"]).with_name("llvm-readelf"))
    report = subprocess.run([readelf, "--dyn-syms", "--wide", str(library)], check=True, capture_output=True, text=True).stdout
    entries = ["Java_org_minyar_hello_MinyarActivity_" + name for name in
               ("nativeRun", "nativeAttach", "nativeDetach", "nativeSnapshot", "nativeEvent")] if shared_view else ["Java_org_minyar_hello_MainActivity_answer"]
    if any(entry not in report for entry in entries):
        raise RuntimeError("JNI entry missing from the dynamic symbol table")
    exported = [parts[-1] for line in report.splitlines() if len(parts := line.split()) >= 8 and parts[-2] != "UND"]
    if any(name == "main" or name.startswith("minyar_") for name in exported):
        raise RuntimeError("a generated/runtime/provider symbol leaked into the JNI dynamic ABI")
    if "Java_org_minyar_hello_MinyarActivity_nativeStop" in report:
        raise RuntimeError("the test-only worker shutdown leaked into the Android ABI")
    summary = {"target": target, "elf_machine": machine, "archive_bytes": archive.stat().st_size,
               "jni_bytes": library.stat().st_size, "ndk": tools["sdk"]}
    summary["shared_view"] = shared_view
    if shared_view:
        metadata = json.loads(archive.with_suffix(".a.json").read_text())
        if "mobileandroid" not in metadata["native_libraries"] or len(metadata.get("required_provider_sources", {})) != 4:
            raise RuntimeError("Android UI archive omitted its required provider provenance")
    (archive.parent / ("ui-jni-check.json" if shared_view else "jni-check.json")).write_text(json.dumps(summary, indent=2) + "\n")
    print(f"{target} {'shared view' if shared_view else 'core'}: PIC archive + JNI shared link passed ({library.stat().st_size} bytes)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, mobile.MobileError) as error:
        print(f"mobile Android check failed: {error}", file=sys.stderr)
        sys.exit(1)
