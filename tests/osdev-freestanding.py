#!/usr/bin/env python3
"""Cross-compile bare-metal runtimes and verify device barriers and sqrt."""

import os
from pathlib import Path
import re
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


def report(label, status, output, elapsed, command):
    print(f"{label}: {'passed' if status == 0 else 'FAILED'} ({elapsed:.2f}s)", flush=True)
    if output:
        print(output, end="" if output.endswith("\n") else "\n", file=sys.stderr)
    if status:
        print("command: " + shlex.join(command), file=sys.stderr)


def barrier_probes(compiler, clang, directory, environment):
    source = directory / "barrier.min"
    source.write_text('use "machine" as machine\nmachine.fence()\n', encoding="utf-8")
    passed = attempted = generation_failures = 0
    for target, cpu in TARGETS:
        arm = target.startswith("aarch64")
        architecture = "arm64" if arm else "x86_64"
        libraries = [ROOT / "os/arch" / architecture]
        if arm:
            libraries.append(ROOT / "library/arch/arm64")
        libraries.append(ROOT / "library")
        llvm = directory / f"{target}-barrier.ll"
        command = [compiler, str(source), str(llvm), "--bounded-owners", "32", "--freestanding"]
        for library in libraries:
            command += ["--library", str(library)]
        status, output, elapsed = invoke(command, environment)
        report(f"{target} barrier LLVM generation", status, output, elapsed, command)
        if status:
            generation_failures += 1
            continue
        expected = "dmb sy" if arm else "mfence or locked stack operation"
        # Match an actual target instruction, never an IR comment or symbol name.
        # LLVM may lower x86 seq_cst to a dummy locked OR on its own stack slot.
        instruction = (r"dmb[ \t]+sy" if arm else
                       r"(?:mfence|lock[ \t]+or[lq][ \t]+\$0,[ \t]*\(%rsp\))")
        pattern = r"^[ \t]*" + instruction + r"(?:[ \t]+(?://|\#).*)?[ \t]*\r?$"
        for optimization in ("-O0", "-O2"):
            assembly = directory / f"{target}-barrier-{optimization[1:]}.s"
            command = [clang, f"--target={target}", *cpu, optimization,
                       "-S", "-x", "ir", "-Wno-override-module", str(llvm), "-o", str(assembly)]
            status, output, elapsed = invoke(command, environment)
            attempted += 1
            if status == 0 and not re.search(pattern, assembly.read_text(), re.MULTILINE | re.IGNORECASE):
                status = 1
                output += f"missing required device barrier instruction: {expected}\n"
            report(f"{target} {optimization} machine.fence => {expected}", status, output, elapsed, command)
            if status == 0:
                passed += 1
    return passed, attempted, generation_failures


def sqrt_probes(clang, flags, directory, environment):
    passed = attempted = 0
    source = ROOT / "runtime/freestanding/freestanding.c"
    for target, cpu in TARGETS:
        arm = target.startswith("aarch64")
        expected = "fsqrt" if arm else "sqrtsd"
        instruction = (r"fsqrt[ \t]+d[0-9]+[ \t]*,[ \t]*d[0-9]+\b" if arm else
                       r"sqrtsd[ \t]+")
        for optimization in ("-O0", "-O2"):
            assembly = directory / f"{target}-sqrt-{optimization[1:]}.s"
            command = [clang, f"--target={target}", *cpu, optimization, *flags,
                       "-S", str(source), "-o", str(assembly)]
            status, output, elapsed = invoke(command, environment)
            attempted += 1
            if status == 0:
                # Inspect only this ELF function, excluding other math functions
                # and comments that happen to mention the desired instruction.
                function = re.search(r"^[ \t]*sqrt:[^\n]*\n(.*?)^[ \t]*\.size[ \t]+sqrt[ \t]*,",
                                     assembly.read_text(), re.MULTILINE | re.DOTALL)
                if function is None:
                    status = 1
                    output += "could not isolate the ELF sqrt function body\n"
                elif not re.search(r"^[ \t]*" + instruction, function[1], re.MULTILINE | re.IGNORECASE):
                    status = 1
                    output += f"sqrt body lacks required native {expected} instruction\n"
                    output += "sqrt assembly:\n" + function[1][:4000]
            report(f"{target} {optimization} C shim sqrt => {expected}", status, output, elapsed, command)
            if status == 0:
                passed += 1
    return passed, attempted


def main():
    selected = os.environ.get("MINYAR_TEST_CLANG", "")
    clang = shutil.which(selected) if selected else None
    if not clang:
        print("osdev freestanding: set MINYAR_TEST_CLANG to the pinned Clang executable", file=sys.stderr)
        return 2
    clang = str(Path(clang).resolve())
    selected = os.environ.get("MINYAR_TEST_COMPILER", str(ROOT / "build/minyarc"))
    compiler = shutil.which(selected)
    if not compiler:
        print("osdev freestanding: build build/minyarc or set MINYAR_TEST_COMPILER", file=sys.stderr)
        return 2
    compiler = str(Path(compiler).resolve())
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
                    report(label, status, output, elapsed, command)
                    if status == 0:
                        passed += 1
        barriers, attempted, generation_failures = barrier_probes(compiler, clang, Path(temporary), environment)
        square_roots, math_attempted = sqrt_probes(clang, flags, Path(temporary), environment)
    elapsed = time.perf_counter() - started
    print(f"osdev freestanding: {passed + barriers + square_roots}/16 checks passed in {elapsed:.2f}s "
          f"({passed}/8 runtime compiles; {barriers}/4 barrier probes; {square_roots}/4 sqrt probes; "
          f"{attempted + math_attempted} assembly compiles, {generation_failures} LLVM generation failures)", flush=True)
    return 0 if passed == 8 and barriers == 4 and square_roots == 4 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError as error:
        print(f"osdev freestanding: {error}", file=sys.stderr)
        raise SystemExit(2)
