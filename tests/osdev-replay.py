#!/usr/bin/env python3
"""Record a real Arm64 kernel run under QEMU and replay it exactly (BX only).

The IRQ kernel's output depends on when timer interrupts land ("ticks during
mix N"), the least deterministic thing a kernel does. Two recordings may
differ; a replay of one recording must reproduce its serial log byte for byte.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "os/tests/irq-kernel.min"
SKIP = ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "LLVM_BIN")


def run(command, timeout, cwd=None):
    environment = {key: value for key, value in os.environ.items() if key not in SKIP}
    return subprocess.run([str(part) for part in command], capture_output=True, text=True, timeout=timeout,
                          env=environment, cwd=cwd)


def main():
    if sys.platform != "linux":
        raise SystemExit("run this test on the BX Linux box")
    clang = os.environ.get("MINYAR_TEST_CLANG", "clang")
    llvm = Path(shutil.which(clang) or clang).resolve().parent
    mkimage = ROOT / "build/os/mkimage"
    mkimage.parent.mkdir(parents=True, exist_ok=True)
    if run([ROOT / "minyar", ROOT / "os/tools/mkimage.min", "-o", mkimage], 600, cwd=ROOT).returncode != 0:
        raise SystemExit("could not build build/os/mkimage")
    build = run(["make", "-C", ROOT / "os", "ARCH=arm64", f"LLVM_BIN={llvm}", "-W", SOURCE,
                 f"KERNEL_SOURCE={SOURCE}", "all"], 900)
    if build.returncode != 0:
        raise SystemExit("kernel build failed\n" + build.stderr[-2000:])
    scratch = Path(tempfile.mkdtemp(prefix="osdev-replay-"))
    journal = scratch / "run.replay"
    logs = {}
    for mode in ("record", "replay"):
        log = scratch / (mode + ".log")
        result = run([sys.executable, ROOT / "tools/osdev.py", "test", "--no-build", "--arch", "arm64",
                      "--llvm-bin", llvm, "--expect", "OSDEV IRQ START", "--timeout", "120",
                      f"--{mode}", journal, "--log", log], 180)
        logs[mode] = log.read_bytes() if log.is_file() else b""
        if result.returncode != 0:
            raise SystemExit(f"{mode} failed\n{logs[mode][-1500:].decode(errors='replace')}\n{result.stderr[-1500:]}")
    ticks = re.search(rb"OSDEV IRQ PASS ticks during mix (\d+)", logs["record"])
    if ticks is None or logs["record"] != logs["replay"]:
        raise SystemExit("the replay differs from its recording")
    refused = run([sys.executable, ROOT / "tools/osdev.py", "test", "--no-build", "--arch", "x86_64",
                   "--expect", "x", "--record", scratch / "x86.replay"], 30)
    if refused.returncode == 0 or "arm64 only" not in refused.stderr:
        raise SystemExit("x86 record/replay must be refused explicitly")
    shutil.rmtree(scratch)
    print(f"arm64 replay reproduced its recording byte for byte, including {ticks.group(1).decode()} interrupt-timed ticks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
