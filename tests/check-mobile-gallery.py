#!/usr/bin/env python3
"""Run the actual mobile hello model independently of its native renderer."""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bridge_checks", ROOT / "tests/check-mobile-bridge.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def main():
    directory = ROOT / "build/mobile-tests/gallery"
    directory.mkdir(parents=True, exist_ok=True)
    clang = os.environ.get("MINYAR_TEST_CLANG")
    if not clang:
        output, _, _ = checks.run(["sh", "tools/toolchain.sh", "default-clang"], directory / "toolchain", 30)
        clang = output.decode().strip()
    llvm = directory / "model.ll"
    checks.run([str(ROOT / "build/minyarc"), "examples/gallery/mobile-lights.min", str(llvm), "--library", "library"], directory / "frontend", 60)
    expected = (ROOT / "examples/gallery/mobile-lights.stdout").read_bytes()
    for optimization in ("-O0", "-O2"):
        binary = directory / optimization[1:]
        checks.run([clang, optimization, "-Wno-override-module", str(llvm), "tests/ownership-runtime.c", "-iquote", "runtime", "-pthread", "-lm", "-o", str(binary)], directory / (binary.name + "-link"), 120)
        output, error, _ = checks.run([str(binary)], directory / (binary.name + "-run"), 30)
        if output != expected or error:
            raise RuntimeError(f"mobile gallery mismatch: {directory}")
        print(f"mobile hello model gallery {optimization} passed with ownership assertions")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f"mobile gallery failed: {error}", file=sys.stderr)
        sys.exit(1)
