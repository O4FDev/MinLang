#!/usr/bin/env python3
"""Check or format the migrated C components using the repository's pinned tool."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = "23.1.2"
FILES = (
    "bootstrap/stage0.c", "tools/module-build.c",
    "runtime/minyar_bytes.h", "runtime/minyar_collections.h", "runtime/minyar_numbers.h",
    "runtime/native/net.c", "runtime/native/net_datagrams.h", "runtime/native/net_loop.h",
    "runtime/native/tlsverify.c", "tests/tls-windows-signing.c",
    "runtime/native/update.c", "runtime/native/update_monocypher.c", "runtime/native/update_ed25519.c",
    "tests/update-native.c", "tests/update-sign.c",
    "tests/net-native.c", "tests/net-batch.c", "tests/net-loop.c",
    "tests/runtime-bytes.c", "tests/runtime-traps.c",
    "tests/llvm_symbols.h",
    "tests/stack-limits.c", "experiments/memory/checked-scalars-driver.c",
    "experiments/memory/checked-scalars-cpp.cpp",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="format the maintained files in place")
    args = parser.parse_args()
    candidates = [os.environ.get("CLANG_FORMAT"), shutil.which("clang-format-23"),
                  shutil.which("clang-format"),
                  ROOT / "build/format-tools-23/bin/clang-format",
                  ROOT / "build/format-tools-23/Scripts/clang-format.exe",
                  "/opt/homebrew/opt/llvm@23/bin/clang-format",
                  "/opt/homebrew/opt/llvm/bin/clang-format"]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        version = subprocess.run([candidate, "--version"], capture_output=True, text=True, check=True)
        if f"version {VERSION}" in version.stdout:
            break
    else:
        parser.error(f"ClangFormat {VERSION} is required; set CLANG_FORMAT to its executable")
    options = ["-i"] if args.write else ["--dry-run", "--Werror"]
    subprocess.run([candidate, *options, *FILES], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
