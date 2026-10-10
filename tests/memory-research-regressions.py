#!/usr/bin/env python3
"""Small maintained regressions for append, owner debt and indexed Text join.

No archived baseline, peer corpus or research manifest is required. The C
fixtures retain their independent contents, allocation and ownership assertions.
Larger profile matrices and timing experiments remain separate opt-in tools.
"""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    cases = [
        ("append-system-o0", "memory-research-list-reserve.c", "-O0",
         ["-DMINYAR_SYSTEM_HEAP=1", "-DMINYAR_RC_POLL_BUDGET=32"]),
        ("append-system-o2", "memory-research-list-reserve.c", "-O2",
         ["-DMINYAR_SYSTEM_HEAP=1", "-DMINYAR_RC_POLL_BUDGET=32"]),
        ("append-pressure-k1", "memory-research-list-debt-pressure.c", "-O2",
         ["-DMINYAR_RC_POLL_BUDGET=1"]),
        ("append-pressure-k32", "memory-research-list-debt-pressure.c", "-O2",
         ["-DMINYAR_RC_POLL_BUDGET=32"]),
        ("append-owner-debt-k1", "memory-research-list-owner-debt.c", "-O2",
         ["-DMINYAR_RC_POLL_BUDGET=1"]),
        ("indexed-text-system", "memory-research-text-join-index.c", "-O2",
         ["-DMINYAR_SYSTEM_HEAP=1", "-DMINYAR_RC_POLL_BUDGET=32"]),
    ]
    environment = {**os.environ, "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1",
                   "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"}
    with tempfile.TemporaryDirectory(prefix="minyar-memory-regressions-") as temporary:
        for name, fixture, optimization, definitions in cases:
            executable = Path(temporary) / (name + (".exe" if os.name == "nt" else ""))
            flags = ["-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if args.sanitize else []
            command = clang_command([args.clang, "-std=c11", "-Wall", "-Wextra", "-Werror",
                                     optimization, *flags, *definitions,
                                     str(ROOT / "tests" / fixture), "-o", str(executable)])
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
            assert compiled.returncode == 0, (name, command, compiled.stdout, compiled.stderr)
            modes = ("frame", "chunk") if fixture == "memory-research-list-owner-debt.c" else (None,)
            for mode in modes:
                result = subprocess.run([str(executable), *([mode] if mode else [])], env=environment,
                                        capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, (name, mode, result.returncode, result.stdout, result.stderr)
            if fixture == "memory-research-text-join-index.c":
                invalid = subprocess.run([str(executable), "--invalid-utf8"], env=environment,
                                         capture_output=True, text=True, timeout=10)
                assert (invalid.returncode, invalid.stdout, invalid.stderr) == (
                    1, "", "Minyar stopped: Text contained invalid UTF-8.\n"), invalid
            print(name + ": contents, ownership and focused invariants passed", flush=True)


if __name__ == "__main__":
    main()
