#!/usr/bin/env python3
"""Prove Android copied transport and real JNI/model execution without a device."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mobile_checks", ROOT / "tests/check-mobile-bridge.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("transport", "java", "jni", "all"), default="all")
    parser.add_argument("--android-api", action="store_true", help="also compile actual Activity against ANDROID_JAR")
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    evidence = ROOT / "build/mobile-tests" / ("android-host-sanitize" if args.sanitize else "android-host")
    evidence.mkdir(parents=True, exist_ok=True)
    clang = os.environ.get("MINYAR_TEST_CLANG")
    if not clang:
        output, _, _ = checks.run(["sh", "tools/toolchain.sh", "default-clang"], evidence / "toolchain", 30)
        clang = output.decode().strip()
    flags = ["-g", "-fno-omit-frame-pointer", "-fsanitize=address,undefined"] if args.sanitize else []
    environment = dict(os.environ)
    environment["ASAN_OPTIONS"] = "detect_leaks=1:halt_on_error=1"
    environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    if args.stage in ("transport", "all"):
        for optimization in ("-O0", "-O2"):
            name = "transport-" + optimization[1:]
            binary = evidence / name
            checks.run([clang, optimization, "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-UNDEBUG",
                        "-Wall", "-Wextra", "-Werror", *flags, "tests/mobile-android-transport.c", "-pthread", "-o", str(binary)],
                       evidence / (name + "-link"), 120)
            output, error, _ = checks.run([str(binary)], evidence / (name + "-run"), 30, environment)
            if b"Android transport" not in output or error:
                raise RuntimeError(f"Android transport output mismatch; see {evidence}")
            print(output.decode().strip(), flush=True)
    if args.stage == "transport":
        return
    javac, java = shutil.which("javac"), shutil.which("java")
    if not javac or not java:
        raise RuntimeError("Android host qualification requires a JDK with javac and java")
    java_home = Path(os.environ.get("JAVA_HOME", str(Path(javac).resolve().parents[1])))
    classes = evidence / "classes"
    classes.mkdir(exist_ok=True)
    sources = ["examples/mobile-hello/android/MinyarSnapshot.java", "tests/MobileAndroidSnapshotTest.java",
               "tests/mobile-android-jvm/MinyarActivity.java"]
    checks.run([javac, "--release", "8", "-d", str(classes), *sources], evidence / "javac", 60)
    java_flags = [java, "-Xmx64m", "-XX:ReservedCodeCacheSize=32m", "-XX:MaxMetaspaceSize=96m",
                  "-XX:CompressedClassSpaceSize=32m", "-Xcheck:jni", "-cp", str(classes)]
    output, error, _ = checks.run([*java_flags, "org.minyar.hello.MobileAndroidSnapshotTest"], evidence / "java-parser", 30)
    if b"event-watermark checks passed" not in output or error:
        raise RuntimeError(f"Android snapshot checks failed; see {evidence}")
    print(output.decode().strip(), flush=True)
    if args.android_api:
        android_jar = Path(os.environ.get("ANDROID_JAR", ""))
        if not android_jar.is_file():
            raise RuntimeError("set ANDROID_JAR to an installed official Android API 28+ android.jar")
        android_classes = evidence / "android-classes"
        android_classes.mkdir(exist_ok=True)
        checks.run([javac, "--release", "8", "-cp", str(android_jar), "-d", str(android_classes),
                    "examples/mobile-hello/android/MinyarSnapshot.java", "examples/mobile-hello/android/MinyarActivity.java"],
                   evidence / "android-api-javac", 60)
        print("Actual Android Activity compiled against " + str(android_jar), flush=True)
    if args.stage == "java":
        return
    if args.sanitize:
        # The JVM is not an instrumented executable; preload the same compiler's
        # shared ASan runtime before loading instrumented JNI/Minyar code.
        asan = None
        for name in ("libclang_rt.asan.so", "libclang_rt.asan-x86_64.so"):
            output, _, _ = checks.run([clang, "--print-file-name=" + name], evidence / name, 30)
            candidate = Path(output.decode().strip())
            if candidate.is_file():
                asan = candidate
                break
        if asan is None:
            raise RuntimeError("JNI sanitizer qualification requires the Linux x86_64 shared ASan runtime")
        environment["LD_PRELOAD"] = str(asan)
        environment["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1:handle_segv=0:use_sigaltstack=0"
    for profile in ("eager", "system"):
        directory = evidence / profile
        directory.mkdir(exist_ok=True)
        llvm = directory / "app.ll"
        command = [str(ROOT / "build/minyarc"), "examples/mobile-hello/android/ui.min", str(llvm), "--library", "library"]
        if profile == "system":
            command += ["--bounded-owners", "32"]
        checks.run(command, directory / "frontend", 120)
        if args.sanitize:
            llvm.write_text(checks.instrument(llvm.read_text()))
        for optimization in ("-O0", "-O2"):
            native = directory / optimization[1:]
            native.mkdir(exist_ok=True)
            library = native / "libminyar_ui_test.so"
            command = [clang, optimization, "-shared", "-fPIC", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-UNDEBUG",
                       "-DMINYAR_ANDROID_TESTING=1", "-Wno-override-module", *flags,
                       "-I", str(java_home / "include"), "-I", str(java_home / "include/linux"), "-iquote", "runtime"]
            if profile == "system":
                command += ["-DMINYAR_SYSTEM_HEAP=1", "-DMINYAR_RC_POLL_BUDGET=32"]
            command += [str(llvm), "runtime/native/mobileandroid.c", "tests/mobile-android-runtime.c", "-pthread", "-lm", "-o", str(library)]
            checks.run(command, native / "link", 120)
            output, error, _ = checks.run([*java_flags, "-Djava.library.path=" + str(native), "org.minyar.hello.MinyarActivity"],
                                          native / "run", 60, environment)
            if b"real JNI model, Unicode, event-copy, rebinding and worker checks passed" not in output \
                    or b"Android model worker ownership cleanup passed" not in output or error:
                raise RuntimeError(f"Android JNI {profile} {optimization} failed; see {native}")
            print(f"Android actual JNI + model {profile} {optimization} passed with worker ownership cleanup", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f"Android host check failed: {error}", file=sys.stderr)
        sys.exit(1)
