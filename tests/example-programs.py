#!/usr/bin/env python3
"""Exercise examples/bytecode-vm (tests and a real program) and
examples/kernel/frames-kernel.min, hosted and compiled freestanding for both
kernel targets. Booting the kernel under QEMU stays with tools/osdev.py."""
import os
from pathlib import Path
import shutil
import subprocess

if not __debug__:
    raise SystemExit("example checks require assertions; remove Python -O")

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "minyar"
COMPILER = ROOT / "build/minyarc"
WORK = ROOT / "build/example-programs"
SCALE = int(os.environ.get("MINYAR_TEST_TIMEOUT_SCALE", "1"))
ENVIRONMENT = dict(os.environ)
for key in ("MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKELEVEL"):
    ENVIRONMENT.pop(key, None)


def run(arguments, cwd=ROOT, status=0, timeout=600):
    result = subprocess.run([str(item) for item in arguments], cwd=cwd, env=ENVIRONMENT, text=True,
                            capture_output=True, timeout=timeout * SCALE)
    assert result.returncode == status, (arguments, result.returncode, result.stdout, result.stderr)
    return result.stdout


shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True)
vm = WORK / "bytecode-vm"
shutil.copytree(ROOT / "examples/bytecode-vm", vm, ignore=shutil.ignore_patterns("target"))
tests = run([LAUNCHER, "test"], vm)
assert "4 passed; 0 failed" in tests, tests
output = run([LAUNCHER, "run", "--", "fib.asm"], vm)
assert output.endswith("0\n1\n1\n2\n3\n5\n8\n13\n21\n34\nhalted after 159 steps\n"), output
(vm / "broken.asm").write_text("push 1\njmp nowhere\n", encoding="utf-8")
assert "unknown label 'nowhere'" in run([LAUNCHER, "run", "--", "broken.asm"], vm, status=1)

kernel = ROOT / "examples/kernel/frames-kernel.min"
hosted = WORK / "frames"
run([LAUNCHER, kernel, "-o", hosted])
assert run([hosted]) == "FRAMES KERNEL START\nposted 86, reclaimed 79, in flight 7, free 54\nFRAMES KERNEL PASS\n"
for target, libraries in (("x86_64", ["library"]), ("arm64", ["library/arch/arm64", "library"])):
    command = [COMPILER, kernel, WORK / f"kernel-{target}.ll"]
    for library in libraries:
        command += ["--library", ROOT / library]
    run(command + ["--bounded-owners", "32", "--freestanding", "--kernel-target", target])
    assert (WORK / f"kernel-{target}.ll").stat().st_size > 0

shutil.rmtree(WORK, ignore_errors=True)
print("example programs: bytecode VM tests and run, frame kernel hosted and freestanding for x86_64 and arm64 passed")
