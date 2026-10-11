#!/usr/bin/env python3
"""Persistent-session lifetime regression; every RPC uses a new immutable wire ID."""
import argparse, importlib.util, os, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tls_tests", ROOT / "tests/tls-local.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    if args.sanitize:
        for name in ("MINYAR_CLANG_FLAGS", "MINYAR_NATIVE_FLAGS", "MINYAR_RUNTIME_FLAGS"):
            os.environ[name] = "-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module"
    with tempfile.TemporaryDirectory(prefix="minyar-yamux-churn-") as directory:
        binary = Path(directory) / "churn"
        fixtures.compile_program(ROOT / "tests/yamux-churn.min", binary)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
        print(result.stdout, end="")
if __name__ == "__main__":
    main()
