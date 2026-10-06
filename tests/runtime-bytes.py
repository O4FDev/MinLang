#!/usr/bin/env python3
"""Replay the Bytes model and work bounds across memory implementations."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
from clang_helpers import clang_command, windows_host

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    profiles = {
        "eager": [], "arena": ["-DMINYAR_COMPILER_ARENA"],
        "system": ["-DMINYAR_SYSTEM_HEAP=1"], "fixed": ["-DMINYAR_BOUNDED_HEAP=1"],
    }
    if not windows_host():
        profiles["lazy"] = ["-DMINYAR_BOUNDED_HEAP=1", "-DMINYAR_LAZY_HEAP=1"]
    with tempfile.TemporaryDirectory(prefix="minyar-bytes-") as temporary:
        for name, definitions in profiles.items():
            executable = Path(temporary) / (name + (".exe" if os.name == "nt" else ""))
            flags = ["-O1", "-g", "-fsanitize=address,undefined"] if args.sanitize else ["-O2"]
            command = [args.clang, "-std=c11", "-Wall", "-Wextra", "-Werror", *flags,
                       *definitions, str(ROOT / "tests/runtime-bytes.c"), "-o", str(executable)]
            if not windows_host():
                command += ["-lm"]
            environment = {**os.environ, "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1",
                           "UBSAN_OPTIONS": "halt_on_error=1"}
            subprocess.run(clang_command(command), check=True, timeout=60, env=environment)
            subprocess.run([str(executable)], check=True, timeout=30, env=environment)
            print(f"{name}: 20,000 model transitions and work bounds passed", flush=True)


if __name__ == "__main__":
    main()
