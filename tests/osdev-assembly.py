#!/usr/bin/env python3
"""Kernel inline assembly: compile checks for both targets, then a live x86 guest (BX only).

Positive programs must lower to exactly the expected LLVM inline-assembly call;
rejections must name the problem; `assembly` stays an ordinary name elsewhere.
Cross-target objects and a host input-mutation regression run at O0 and O2.
The QEMU guest writes a serial line through `outb` written in Minyar assembly.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
KERNEL = ("--freestanding", "--kernel-target")
SKIP = ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "LLVM_BIN")

POSITIVES = [
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "pause" changes(nothing)\n    return 0\n}\n',
     r'call void asm sideeffect "pause", ""\(\)'),
    ("x86_64", 'function send(value: Integer, port: Integer) {\n    assembly for x86_64 "outb %al, %dx" inputs(value in al, port in dx) changes(memory)\n}\n'
     'function main(): Integer {\n    send(65, 0x3F8)\n    return 0\n}\n',
     r'call \{ i8, i16 \} asm sideeffect "outb %al, %dx", "=&\{al\},=&\{dx\},0,1,~\{memory\}"\(i8 %[\w.]+, i16 %[\w.]+\)'),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "movq $1, %rax" changes(rax, flags)\n    return 0\n}\n',
     r'call void asm sideeffect "movq \$\$1, %rax", "~\{rax\},~\{flags\},~\{dirflag\},~\{fpsr\}"\(\)'),
    ("arm64", 'function main(): Integer {\n    assembly for arm64 "isb" changes(memory)\n    return 0\n}\n',
     r'call void asm sideeffect "isb", "~\{memory\}"\(\)'),
    ("arm64", 'function store(address: Integer, value: Integer) {\n    assembly for arm64 "strb w1, [x0]" inputs(address in x0, value in w1) changes(memory)\n}\n'
     'function main(): Integer {\n    store(0x09000000, 65)\n    return 0\n}\n',
     r'call \{ i64, i32 \} asm sideeffect "strb w1, \[x0\]", "=&\{x0\},=&\{w1\},0,1,~\{memory\}"\(i64 %[\w.]+, i32 %[\w.]+\)'),
    ("x86_64", 'function keep(value: Integer): Integer {\n    assembly for x86_64 "xorq %rax, %rax" inputs(value in rax) changes(eax, flags)\n    return value\n}\n'
     'function main(): Integer { return 0 }\n',
     r'call i64 asm sideeffect "xorq %rax, %rax", "=&\{rax\},0,~\{flags\},~\{dirflag\},~\{fpsr\}"\(i64 %[\w.]+\)'),
    ("arm64", 'function keep(value: Integer): Integer {\n    assembly for arm64 "mov x0, #0" inputs(value in x0) changes(w0)\n    return value\n}\n'
     'function main(): Integer { return 0 }\n',
     r'call i64 asm sideeffect "mov x0, #0", "=&\{x0\},0"\(i64 %[\w.]+\)'),
]

REJECTIONS = [
    ("x86_64", 'function main(): Integer {\n    assembly for arm64 "isb" changes(nothing)\n    return 0\n}\n', "this assembly is for arm64"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "pause"\n    return 0\n}\n', "must say what it changes"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "outb %al, %dx" inputs(1 in xmm0) changes(nothing)\n    return 0\n}\n', "is not a general register"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "outb %al, %dx" inputs(256 in al, 1 in dx) changes(nothing)\n    return 0\n}\n', "outside its unsigned 8-bit range"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "nop" inputs(1 in al, 2 in al) changes(nothing)\n    return 0\n}\n', "already holds an input"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "nop" inputs(1 in al, 2 in rax) changes(nothing)\n    return 0\n}\n', "already holds an input"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "nop" inputs(1 in r8d, 2 in r8) changes(nothing)\n    return 0\n}\n', "already holds an input"),
    ("arm64", 'function main(): Integer {\n    assembly for arm64 "nop" inputs(1 in w0, 2 in x0) changes(nothing)\n    return 0\n}\n', "already holds an input"),
    ("arm64", 'function main(): Integer {\n    assembly for arm64 "nop" inputs(1 in x29) changes(nothing)\n    return 0\n}\n', "not a general register"),
    ("arm64", 'function main(): Integer {\n    assembly for arm64 "nop" inputs(1 in w29) changes(nothing)\n    return 0\n}\n', "not a general register"),
    ("arm64", 'function main(): Integer {\n    assembly for arm64 "nop" changes(x29)\n    return 0\n}\n', "not memory, flags or a general register"),
    ("arm64", 'function main(): Integer {\n    assembly for arm64 "nop" changes(w29)\n    return 0\n}\n', "not memory, flags or a general register"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "nop" inputs("one" in al) changes(nothing)\n    return 0\n}\n', "Integer values"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "nop" changes(nothing, memory)\n    return 0\n}\n', "cannot list anything else"),
    ("x86_64", 'function main(): Integer {\n    assembly for x86_64 "nop" changes(memory, memory)\n    return 0\n}\n', "listed twice"),
    ("x86_64", 'interrupt function tick(vector: Integer) handles(32) {\n    assembly for x86_64 "nop" changes(nothing)\n}\n'
     'function main(): Integer { return 0 }\n', "interrupt context"),
    (None, 'function main(): Integer {\n    assembly for x86_64 "pause" changes(nothing)\n    return 0\n}\n', "needs a kernel build"),
]

ORDINARY = 'let assembly = 40\nfunction assemble(assembly: Integer): Integer { return assembly + 2 }\nprint(assemble(assembly))\n'
MUTABLE_INPUT = ('function keep(value: Integer): Integer {\n'
                 '    assembly for x86_64 "xorq %rax, %rax" inputs(value in rax) changes(flags)\n'
                 '    return value\n}\nfunction main(): Integer { return 0 }\n')


def run(command, timeout=120, cwd=None):
    environment = {key: value for key, value in os.environ.items() if key not in SKIP}
    return subprocess.run([str(part) for part in command], capture_output=True, text=True, timeout=timeout,
                          env=environment, cwd=cwd)


def compile_case(compiler, scratch, name, target, source):
    path = scratch / (name + ".min")
    path.write_text(source)
    output = scratch / (name + ".ll")
    options = [*KERNEL, target] if target else []
    result = run([compiler, path, output, "--library", ROOT / "library", *options])
    return result, output


def check_mutable_input(args, scratch, failures):
    result, output = compile_case(args.compiler, scratch, "mutable-input", "x86_64", MUTABLE_INPUT)
    if result.returncode != 0:
        failures.append("mutable input does not compile: " + result.stderr[-1000:])
        return
    text = output.read_text()
    functions = re.findall(r'^define i64 @([^\s(]+)\(i64 %argument\.0\)[^\n]*\{\n(.*?)^\}', text, re.M | re.S)
    symbols = [symbol for symbol, body in functions if '"xorq %rax, %rax"' in body]
    if len(symbols) != 1:
        failures.append("cannot identify the emitted mutable-input function")
        return
    # A separate C translation unit keeps the runtime argument unknown to the
    # Minyar function's optimizer. Its return must preserve the live value even
    # though the assembly overwrites the ABI's return register.
    output.write_text(text.replace("@main(", "@minyar_assembly_fixture_main("))
    symbol = symbols[0].strip('"').replace("\\", "\\\\").replace('"', '\\"')
    driver = scratch / "mutable-input-driver.c"
    driver.write_text('#include <stdint.h>\n'
                      'extern int64_t keep(int64_t) __asm__("' + symbol + '");\n'
                      'int main(void) {\n'
                      '    volatile int64_t values[] = {0, 1, -1, INT64_MAX, INT64_MIN, INT64_C(0x123456789abcdef)};\n'
                      '    for (unsigned i = 0; i < sizeof(values) / sizeof(values[0]); i++) {\n'
                      '        int64_t value = values[i];\n'
                      '        if (keep(value) != value) return 1;\n'
                      '    }\n    return 0;\n}\n')
    for optimization in ("-O0", "-O2"):
        program = scratch / ("mutable-input" + optimization)
        linked = run([args.clang, optimization, "-Wno-override-module", output, driver, args.runtime,
                      "-lm", "-pthread", "-o", program])
        if linked.returncode != 0:
            failures.append(f"mutable input {optimization} does not link: {linked.stderr[-1000:]}")
            continue
        ran = run([program])
        if ran.returncode != 0 or ran.stdout or ran.stderr:
            failures.append(f"mutable input {optimization} changed a live Minyar value: status {ran.returncode}\n{ran.stderr[-1000:]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=os.environ.get("MINYAR_TEST_COMPILER", str(ROOT / "build/minyarc")))
    parser.add_argument("--runtime", default=os.environ.get("MINYAR_TEST_RUNTIME", str(ROOT / "build/minyar-runtime.o")))
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--no-qemu", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("run this test on the BX Linux box")
    failures = []
    scratch = Path(tempfile.mkdtemp(prefix="osdev-assembly-"))
    for index, (target, source, pattern) in enumerate(POSITIVES):
        result, output = compile_case(args.compiler, scratch, f"positive-{index}", target, source)
        text = output.read_text() if output.is_file() else ""
        if result.returncode != 0 or not re.search(pattern, text):
            failures.append(f"positive {index} ({target}): {result.stderr.strip()[:300]}\nexpected /{pattern}/")
            continue
        triple = "x86_64-unknown-none-elf" if target == "x86_64" else "aarch64-unknown-none-elf"
        for optimization in ("-O0", "-O2"):
            assembled = run([args.clang, "--target=" + triple, optimization, "-c", "-x", "ir", "-Wno-override-module", output,
                             "-o", scratch / f"positive-{index}{optimization}.o"])
            if assembled.returncode != 0:
                failures.append(f"positive {index} ({target}, {optimization}) does not assemble: {assembled.stderr.strip()[:300]}")
    for index, (target, source, message) in enumerate(REJECTIONS):
        result, output = compile_case(args.compiler, scratch, f"reject-{index}", target, source)
        if result.returncode == 0 or message not in result.stderr or not re.search(r"\.min:\d+:\d+", result.stderr):
            failures.append(f"rejection {index}: expected '{message}' with a source location\n{result.stderr.strip()[:400]}")
    result, output = compile_case(args.compiler, scratch, "ordinary", None, ORDINARY)
    if result.returncode == 0:
        program = scratch / "ordinary"
        linked = run([args.clang, "-O0", "-Wno-override-module", output, args.runtime, "-lm", "-pthread", "-o", program])
        ran = run([program]) if linked.returncode == 0 else None
        if ran is None or ran.stdout != "42\n":
            failures.append("an ordinary name 'assembly' must keep working")
    else:
        failures.append("an ordinary name 'assembly' must keep working: " + result.stderr.strip()[:300])
    check_mutable_input(args, scratch, failures)
    print(f"assembly: {len(POSITIVES)} lowerings, {len(REJECTIONS)} rejections, ordinary names and O0/O2 input mutation checked", flush=True)
    if not args.no_qemu and not failures:
        llvm = Path(shutil.which(args.clang) or args.clang).resolve().parent
        mkimage = ROOT / "build/os/mkimage"
        mkimage.parent.mkdir(parents=True, exist_ok=True)
        built = run([ROOT / "minyar", ROOT / "os/tools/mkimage.min", "-o", mkimage], 600, cwd=ROOT)
        source = ROOT / "os/tests/assembly-kernel.min"
        build = run(["make", "-C", ROOT / "os", "ARCH=x86_64", f"LLVM_BIN={llvm}", "-W", source,
                     f"KERNEL_SOURCE={source}", "all"], 900) if built.returncode == 0 else built
        if build.returncode != 0:
            failures.append("assembly kernel build failed\n" + build.stderr[-2000:])
        else:
            log = ROOT / "build/os/x86_64/osdev-assembly-serial.log"
            boot = run([sys.executable, ROOT / "tools/osdev.py", "test", "--no-build", "--arch", "x86_64",
                        "--llvm-bin", llvm, "--expect", "OSDEV ASM PASS", "--timeout", "30", "--log", log], 120)
            serial = log.read_text(errors="replace") if log.is_file() else ""
            lines = [line.rstrip("\r") for line in serial.splitlines()]
            if boot.returncode != 0 or "OSDEV ASM WROTE THIS" not in lines:
                failures.append(f"assembly guest failed\n{serial[-1500:]}\n{boot.stderr[-1000:]}")
            else:
                print("x86_64 guest: a line written by Minyar `outb` assembly reached the serial port", flush=True)
    if failures:
        print("\n\n".join(failures), file=sys.stderr)
        print("artifacts: " + str(scratch), file=sys.stderr)
        return 1
    shutil.rmtree(scratch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
