#!/usr/bin/env python3
"""A Minyar interrupt function is the real timer entry on x86-64 and Arm64 (BX only).

Builds os/tests/irq-kernel.min for each architecture and checks the linked
kernel: on x86-64, irq_32 is the compiler's x86_intrcc entry (iretq, cld, no
x87/SSE registers, master-PIC acknowledgement only) rather than the weak stub;
on Arm64, the GIC entry calls the compiled minyar_irq_dispatch, which uses no
FP/SIMD registers. Then it boots each under QEMU; the guest proves delivery,
counting, that the handler reads its interrupt controller (x86 port I/O, Arm64
MMIO) and that interrupted code keeps its registers (see the kernel).
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "os/tests/irq-kernel.min"
SKIP = ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "LLVM_BIN")


def run(command, timeout, cwd=None):
    environment = {key: value for key, value in os.environ.items() if key not in SKIP}
    return subprocess.run([str(part) for part in command], capture_output=True, text=True, timeout=timeout,
                          env=environment, cwd=cwd)


def disassemble(llvm, elf, symbols):
    dump = run([llvm / "llvm-objdump", "-d", "--no-show-raw-insn", "--disassemble-symbols=" + ",".join(symbols), elf], 60)
    blocks = dict(re.findall(r"<([\w.]+)>:\n(.*?)(?=\n\n|\Z)", dump.stdout, re.S))
    return blocks, dump.stdout + dump.stderr


def require(checks, text):
    for passed, message in checks:
        if not passed:
            raise SystemExit(f"{message}\n{text[-3000:]}")


def check_x86(llvm, elf):
    blocks, text = disassemble(llvm, elf, ["irq_32", "irq_33"])
    entry, stub = blocks.get("irq_32", ""), blocks.get("irq_33", "")
    require([
        (entry != "", "the kernel must contain irq_32"),
        (re.search(r"\biretq\b", entry) is not None, "irq_32 must return with iretq"),
        (re.search(r"\bcld\b", entry) is not None, "irq_32 must clear DF before handler code"),
        (re.search(r"%[xyz]mm\d|%st\b|%mm\d", entry) is None, "irq_32 must not touch x87, MMX or SSE registers"),
        (len(re.findall(r"\boutb\b", entry)) == 1, "vector 32 acknowledges only the master PIC"),
        (re.search(r"\bpush", entry) is not None, "irq_32 must save the registers it uses"),
        ("lock" in stub and "iretq" in stub, "unbound vectors keep the weak assembly stub"),
    ], text)


def check_arm(llvm, elf):
    blocks, text = disassemble(llvm, elf, ["minyar_irq_dispatch", "interrupt"])
    dispatch, entry = blocks.get("minyar_irq_dispatch", ""), blocks.get("interrupt", "")
    require([
        (dispatch != "", "the kernel must contain the compiled minyar_irq_dispatch"),
        (re.search(r"\b(?:[qdsh]\d{1,2}|v\d{1,2}\.)", dispatch) is None, "the dispatcher must not touch FP/SIMD registers"),
        (re.search(r"\bblr\b", entry) is not None and re.search(r"\beret\b", entry) is not None,
         "the GIC entry must call the dispatcher and return with eret"),
    ], text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--arch", action="append", choices=("x86_64", "arm64"))
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("run this test on the BX Linux box")
    llvm = Path(shutil.which(args.clang) or args.clang).resolve().parent
    mkimage = ROOT / "build/os/mkimage"
    mkimage.parent.mkdir(parents=True, exist_ok=True)
    built = run([ROOT / "minyar", ROOT / "os/tools/mkimage.min", "-o", mkimage], 600, cwd=ROOT)
    if built.returncode != 0:
        raise SystemExit("could not build build/os/mkimage\n" + built.stderr[-2000:])
    for arch in args.arch or ("x86_64", "arm64"):
        build = run(["make", "-C", ROOT / "os", f"ARCH={arch}", f"LLVM_BIN={llvm}", "-W", SOURCE,
                     f"KERNEL_SOURCE={SOURCE}", "all"], 900)
        if build.returncode != 0:
            raise SystemExit(f"{arch}: kernel build failed\n" + build.stderr[-3000:])
        elf = ROOT / "build/os" / arch / "kernel.elf"
        if arch == "x86_64":
            check_x86(llvm, elf)
        else:
            check_arm(llvm, elf)
        log = ROOT / "build/os" / arch / "osdev-irq-serial.log"
        boot = run([sys.executable, ROOT / "tools/osdev.py", "test", "--no-build", "--arch", arch,
                    "--llvm-bin", llvm, "--expect", "OSDEV IRQ START", "--timeout", "60", "--log", log], 120)
        serial = log.read_text(errors="replace") if log.is_file() else ""
        passed = re.search(r"^OSDEV IRQ PASS ticks during mix (\d+)\r?$", serial, re.M)
        if boot.returncode != 0 or passed is None:
            raise SystemExit(f"{arch}: the IRQ guest failed\nserial:\n{serial[-2000:]}\nosdev:\n{boot.stderr[-2000:]}")
        print(f"{arch}: the Minyar handler is the timer entry and reads its interrupt controller; {passed.group(1)} interrupts landed inside the register mix")
    return 0


if __name__ == "__main__":
    sys.exit(main())
