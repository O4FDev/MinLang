#!/usr/bin/env python3
"""Ensure ASan's fake stack cannot bypass the native stack guard."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MESSAGE = "Minyar stopped: the program exceeded the maximum call depth.\n"
HARNESS = r"""
void minyar_stack_enter(void);
void minyar_stack_leave(void);

static volatile unsigned long long observed;

__attribute__((noinline)) static void descend(unsigned long long depth) {
    volatile unsigned long long local = depth;
    observed += local;
    minyar_stack_enter();
    if (depth != ~0ULL) descend(depth + 1);
    minyar_stack_leave();
    observed += local;
}

int main(void) {
    descend(0);
    return observed == 0;
}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="minyar-stack-guard-asan-") as directory:
        temporary = Path(directory)
        harness = temporary / "harness.c"
        executable = temporary / "stack-guard"
        harness.write_text(HARNESS, encoding="utf-8")
        built = subprocess.run(
            [
                args.clang,
                "-std=c11",
                "-O1",
                "-g",
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
                "-DMINYAR_SYSTEM_HEAP=1",
                str(harness),
                str(ROOT / "runtime/minyar_runtime.c"),
                "-o",
                str(executable),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        assert built.returncode == 0, built.stderr

        environment = {
            **os.environ,
            "ASAN_OPTIONS": "detect_stack_use_after_return=1:detect_leaks=0:abort_on_error=1",
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1",
        }
        checked = subprocess.run(
            [str(executable)],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
        )
        assert checked.returncode == 1, checked.stderr
        assert checked.stdout == "", checked.stdout
        assert checked.stderr == MESSAGE, checked.stderr

    print("ASan fake-stack mode preserves the native stack guard")


if __name__ == "__main__":
    main()
