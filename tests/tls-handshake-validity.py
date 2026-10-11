#!/usr/bin/env python3
"""Delay authentic full/PSK handshake flights across real identity expiry."""
import argparse, importlib.util, os, subprocess, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tls_tests", ROOT / "tests/tls-local.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--mode", choices=("control", "server-resumed-hello", "server-resumed-finished", "server-full-finished", "client-resumed-finished", "client-full-finished"))
    args = parser.parse_args()
    if args.sanitize:
        for name in ("MINYAR_CLANG_FLAGS", "MINYAR_NATIVE_FLAGS", "MINYAR_RUNTIME_FLAGS"):
            os.environ[name] = "-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module"
    results = []
    with tempfile.TemporaryDirectory(prefix="minyar-handshake-validity-") as directory:
        binary = Path(directory) / "validity"
        fixtures.compile_program(ROOT / "tests/tls-handshake-validity.min", binary)
        for mode in ("control", "server-resumed-hello", "server-resumed-finished", "server-full-finished",
                     "client-resumed-finished", "client-full-finished"):
            if args.mode and args.mode != mode:
                continue
            case = Path(directory) / mode
            case.mkdir()
            ca = fixtures.Certificates(case)
            ca.root("root")
            expires = (datetime.now(timezone.utc) + timedelta(seconds=6)).replace(microsecond=0)
            for name, usage in (("server", "serverAuth"), ("client", "clientAuth")):
                expiring = mode.startswith(name)
                validity = (expires - timedelta(hours=1), expires) if expiring else "valid"
                ca.leaf(name, "root", usage=usage, ec=True, validity=validity)
            run = subprocess.run([str(binary), str(ca.path("root", "der")), str(ca.path("server", "der")),
                                  str(ca.path("server", "pk8")), str(ca.path("client", "der")),
                                  str(ca.path("client", "pk8")), mode, str(int(expires.timestamp() * 1000))],
                                 capture_output=True, text=True, timeout=16)
            results.append((mode, run.returncode, run.stdout, run.stderr))
            print(mode, run.returncode, run.stdout.strip(), run.stderr.strip(), flush=True)
    assert all(row[1] == 0 for row in results), results
if __name__ == "__main__":
    main()
