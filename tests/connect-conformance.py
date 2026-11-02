#!/usr/bin/env python3
"""The official Connect conformance suite against the Minyar Connect server.

Builds tests/interop/connect-conformance/server.min (the ConformanceService
over library/connect.min, with Protobuf code from protoc-gen-minyar) at O0 and
with --release, and runs connectrpc/conformance's connectconformance in server
mode against each, with the features in config.yaml. Every selected test case
must pass; there is no known-failing list.
Usage: connect-conformance.py MINYAR_LAUNCHER CONNECTCONFORMANCE
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile


def main():
    launcher = Path(sys.argv[1]).resolve()
    runner = Path(sys.argv[2]).resolve()
    source = launcher.parent / "tests/interop/connect-conformance"
    with tempfile.TemporaryDirectory(prefix="minyar-connect-conformance-") as temporary:
        for mode in ["debug", "release"]:
            binary = Path(temporary) / ("server-" + mode)
            command = [str(launcher)]
            if mode == "release":
                command.append("--release")
            subprocess.run(command + [str(source / "server.min"), "-o", str(binary)], check=True, stdout=subprocess.DEVNULL, timeout=1800)
            # The runner writes the request to stdin, which the server reads as a file.
            shim = ["sh", "-c", 'request=$(mktemp) && cat > "$request" && exec "$0" "$request"', str(binary)]
            result = subprocess.run([str(runner), "--mode", "server", "--conf", str(source / "config.yaml"), "--"] + shim,
                                    capture_output=True, text=True, timeout=1800, env=dict(os.environ, TMPDIR=temporary))
            sys.stdout.write(mode + ": " + result.stdout.strip().splitlines()[-1] + "\n" if result.stdout.strip() else mode + ": no output\n")
            if result.returncode != 0:
                sys.stderr.write(result.stdout + result.stderr)
                raise SystemExit("connect conformance failed against the " + mode + " server")


if __name__ == "__main__":
    main()
