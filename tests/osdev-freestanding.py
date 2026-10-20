#!/usr/bin/env python3
"""Cross-compile both bare-metal runtime units without host C headers."""

import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 60
TARGETS = (
    ("x86_64-unknown-none-elf", ["-march=x86-64-v2", "-mno-red-zone"]),
    ("aarch64-unknown-none-elf", []),
)
SOURCES = ("runtime/freestanding/runtime.c", "runtime/freestanding/freestanding.c")


def invoke(command, environment):
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=ROOT, env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace",
                               start_new_session=True)
    try:
        output, _ = process.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
        return 124, output + f"\ncommand timed out after {TIMEOUT}s\n", time.perf_counter() - started
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    return process.returncode, output, time.perf_counter() - started


def main():
    selected = os.environ.get("MINYAR_TEST_CLANG", "")
    clang = shutil.which(selected) if selected else None
    if not clang:
        print("osdev freestanding: set MINYAR_TEST_CLANG to the pinned Clang executable", file=sys.stderr)
        return 2
    clang = str(Path(clang).resolve())
    environment = os.environ.copy()
    # -nostdinc excludes default headers; these variables can add host paths back.
    for name in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH", "SDKROOT"):
        environment.pop(name, None)
    command = [clang, "-print-resource-dir"]
    status, output, _ = invoke(command, environment)
    if status:
        print("osdev freestanding: resource directory query failed\n" + output, file=sys.stderr)
        return 1
    resource = Path(output.strip()) / "include"
    shim = ROOT / "runtime/freestanding/include"
    if not resource.is_dir() or not shim.is_dir():
        print(f"osdev freestanding: missing include directory: {resource} or {shim}", file=sys.stderr)
        return 2
    flags = ["-ffreestanding", "-fno-builtin", "-nostdinc",
             "-isystem", str(resource), "-isystem", str(shim),
             "-fno-stack-protector", "-fno-pic", "-Wall", "-Wno-unused-function"]
    started = time.perf_counter()
    passed = 0
    with tempfile.TemporaryDirectory(prefix="minyar-osdev-freestanding-") as temporary:
        for target, cpu in TARGETS:
            for optimization in ("-O0", "-O2"):
                for source in SOURCES:
                    name = f"{target}-{optimization[1:]}-{Path(source).stem}.o"
                    command = [clang, f"--target={target}", *cpu, optimization, *flags,
                               "-c", str(ROOT / source), "-o", str(Path(temporary) / name)]
                    status, output, elapsed = invoke(command, environment)
                    label = f"{target} {optimization} {source}"
                    print(f"{label}: {'passed' if status == 0 else 'FAILED'} ({elapsed:.2f}s)", flush=True)
                    if output:
                        print(output, end="" if output.endswith("\n") else "\n", file=sys.stderr)
                    if status:
                        print("command: " + shlex.join(command), file=sys.stderr)
                    else:
                        passed += 1
    elapsed = time.perf_counter() - started
    print(f"osdev freestanding: {passed}/8 compiles passed in {elapsed:.2f}s", flush=True)
    return 0 if passed == 8 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError as error:
        print(f"osdev freestanding: {error}", file=sys.stderr)
        raise SystemExit(2)
