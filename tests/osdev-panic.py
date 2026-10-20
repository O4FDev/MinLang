#!/usr/bin/env python3
"""A real kernel panic prints a symbolized Minyar call chain (BX only).

Builds os/tests/panic-kernel.min for x86_64 and arm64 with os/Makefile, boots
each under QEMU through tools/osdev.py, and requires the failure to print return
addresses that osdev.py maps back to the recursive Minyar frames and main.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "os/tests/panic-kernel.min"


def clean_environment():
    """Drop an enclosing make's flags: nested ./minyar builds must not inherit
    os/Makefile's LLVM_BIN override, which selects a different host clang."""
    return {key: value for key, value in os.environ.items()
            if key not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "LLVM_BIN")}


def run(command, timeout, cwd=None):
    return subprocess.run([str(part) for part in command], capture_output=True, text=True, timeout=timeout,
                          env=clean_environment(), cwd=cwd)


def prepare_mkimage():
    # Build the image tool once through the checkout's launcher, so the OS
    # make below finds it current and never rebuilds the compiler itself.
    mkimage = ROOT / "build/os/mkimage"
    mkimage.parent.mkdir(parents=True, exist_ok=True)
    result = run([ROOT / "minyar", ROOT / "os/tools/mkimage.min", "-o", mkimage], 600, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit("could not build build/os/mkimage\n" + result.stderr[-2000:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--arch", action="append", choices=("x86_64", "arm64"))
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("run this test on the BX Linux box")
    llvm = Path(shutil.which(args.clang) or args.clang).resolve().parent
    failures = []
    prepare_mkimage()
    for arch in args.arch or ("x86_64", "arm64"):
        build = run(["make", "-C", ROOT / "os", f"ARCH={arch}", f"LLVM_BIN={llvm}", "-W", SOURCE,
                     f"KERNEL_SOURCE={SOURCE}", "all"], 900)
        if build.returncode != 0:
            failures.append(f"{arch}: kernel build failed\n{build.stderr[-2000:]}")
            continue
        log = ROOT / "build/os" / arch / "osdev-panic-serial.log"
        boot = run([sys.executable, ROOT / "tools/osdev.py", "test", "--no-build", "--arch", arch,
                    "--llvm-bin", llvm, "--expect", "OSDEV PANIC UNREACHABLE", "--timeout", "30", "--log", log], 120)
        serial = log.read_text(errors="replace") if log.is_file() else ""
        frames = re.findall(r"^  at (\w+) \(([^:\n]+):(\d+):(\d+)\)$", boot.stderr, re.M)
        descend = [frame for frame in frames if frame[0] == "descend" and frame[1].endswith("os/tests/panic-kernel.min")]
        mains = [frame for frame in frames if frame[0] == "main" and frame[1].endswith("os/tests/panic-kernel.min")]
        checks = [
            (boot.returncode != 0, "the failing guest must fail the test"),
            ("Minyar stopped: OSDEV PANIC EXPECTED" in serial, "the guest must stop with its own message"),
            (re.search(r"^  at 0x[0-9a-f]+$", serial, re.M) is not None, "the guest must print return addresses"),
            ("osdev: Minyar stack trace, symbolized with" in boot.stderr, "osdev.py must symbolize the trace"),
            (len(descend) >= 3, "at least three recursive descend frames"),
            (len(mains) >= 1 and frames.index(mains[0]) > frames.index(descend[0]) if descend and mains else False,
             "main must follow the descend frames"),
        ]
        for passed, message in checks:
            if not passed:
                failures.append(f"{arch}: {message}\nserial:\n{serial[-1500:]}\nosdev:\n{boot.stderr[-1500:]}")
                break
        else:
            print(f"{arch}: panic printed {len(frames)} symbolized frames ({len(descend)} descend, main last)", flush=True)
    if failures:
        print("\n\n".join(failures), file=sys.stderr)
        return 1
    print("kernel panics print symbolized Minyar frames on x86_64 and arm64")
    return 0


if __name__ == "__main__":
    sys.exit(main())
