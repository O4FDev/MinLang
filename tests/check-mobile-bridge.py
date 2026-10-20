#!/usr/bin/env python3
"""Portable mobile callback/ownership checks; run through bx, never UIKit."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (
    "64 mobile sessions; 448 snapshots; 320 retained events\n"
    "Unicode event copies and captured model updates passed\n"
).encode()


def run(command, evidence, timeout, environment=None):
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.with_suffix(".command.json").write_text(json.dumps(command, indent=2) + "\n")
    start = time.monotonic()
    with evidence.with_suffix(".stdout").open("wb") as output, evidence.with_suffix(".stderr").open("wb") as error:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=output, stderr=error, start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            status = 124
    elapsed = time.monotonic() - start
    evidence.with_suffix(".result.json").write_text(json.dumps({"status": status, "seconds": elapsed}) + "\n")
    stdout = evidence.with_suffix(".stdout").read_bytes()
    stderr = evidence.with_suffix(".stderr").read_bytes()
    if status:
        raise RuntimeError(f"{evidence.name}: status {status}; evidence in {evidence.parent}\n" + stderr.decode("utf-8", "replace"))
    return stdout, stderr, elapsed


def instrument(source):
    """Clang requires this attribute to instrument existing LLVM definitions."""
    result = []
    functions = 0
    for line in source.splitlines(keepends=True):
        if line.startswith("define "):
            if not line.rstrip().endswith("{"):
                raise RuntimeError("unsupported LLVM function header")
            position = line.rfind("{")
            line = line[:position] + "sanitize_address " + line[position:]
            functions += 1
        result.append(line)
    if not functions:
        raise RuntimeError("fixture emitted no LLVM definitions")
    return "".join(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitize", action="store_true", help="run the four ASan/UBSan variants")
    arguments = parser.parse_args()
    evidence = ROOT / "build/mobile-tests" / ("sanitize" if arguments.sanitize else "native")
    evidence.mkdir(parents=True, exist_ok=True)
    clang = os.environ.get("MINYAR_TEST_CLANG")
    if not clang:
        result, _, _ = run(["sh", "tools/toolchain.sh", "default-clang"], evidence / "toolchain", 30)
        clang = result.decode().strip()
    compiler = str(ROOT / "build/minyarc")
    for required in (Path(compiler), ROOT / "build/testing/cycle-runtime.c"):
        if not required.is_file():
            raise RuntimeError(f"missing {required}; first run make -j8 build/minyarc build/testing/cycle-runtime.c on bx")
    flags = ["-g", "-fno-omit-frame-pointer", "-fsanitize=address,undefined"] if arguments.sanitize else []
    environment = dict(os.environ)
    environment["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1"
    environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    measurements = []
    for profile in ("eager", "system"):
        directory = evidence / profile
        directory.mkdir(exist_ok=True)
        llvm = directory / "mobile.ll"
        command = [compiler, "tests/mobile-bridge.min", str(llvm), "--library", "library"]
        if profile == "system":
            command += ["--bounded-owners", "32"]
        run(command, directory / "frontend", 120)
        if arguments.sanitize:
            llvm.write_text(instrument(llvm.read_text()))
        for optimization in ("-O0", "-O2"):
            name = optimization.removeprefix("-")
            binary = directory / name
            command = [clang, optimization, "-std=c11", "-UNDEBUG", "-Wno-override-module", "-iquote", "runtime", *flags]
            if profile == "system":
                command += ["-DMINYAR_SYSTEM_HEAP=1", "-DMINYAR_RC_POLL_BUDGET=32"]
            command += [str(llvm), "tests/mobile-bridge.c", "tests/mobile-cleanup.c", "-pthread", "-lm", "-o", str(binary)]
            run(command, directory / (name + "-link"), 120)
            output, error, elapsed = run([str(binary)], directory / (name + "-run"), 30, environment)
            if output != EXPECTED or error:
                raise RuntimeError(f"{profile} {optimization}: exact output mismatch; see {directory}")
            measurements.append({"profile": profile, "optimization": optimization, "seconds": elapsed})
            print(f"mobile bridge {profile} {optimization} {'ASan/UBSan' if arguments.sanitize else 'native'} passed", flush=True)
    (evidence / "summary.json").write_text(json.dumps(measurements, indent=2) + "\n")
    print("4 mobile bridge variants passed; 256 sessions, 1792 snapshots, 1280 retained events")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f"mobile bridge check failed: {error}", file=sys.stderr)
        sys.exit(1)
