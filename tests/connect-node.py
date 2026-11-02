#!/usr/bin/env python3
"""A stock @connectrpc/connect-node client calls a Minyar Connect server.

Builds tests/interop/connect-node/server.min at O0 and with --release, serves
it on loopback through httpserver and runs client.mjs (pinned connect-node,
installed by `npm ci` into build/connect-node) against each build: unary and
server-streaming calls over the binary and JSON codecs, metadata, GET, gzip,
idempotent retries, CORS and the Connect code of every kind of failure. The
Minyar client (minyar-client.min, connectclient) then calls the same server.
Usage: connect-node.py MINYAR_LAUNCHER NODE_PREFIX
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    launcher = Path(sys.argv[1]).resolve()
    prefix = Path(sys.argv[2]).resolve()
    source = launcher.parent / "tests/interop/connect-node"
    shutil.copyfile(source / "client.mjs", prefix / "client.mjs")
    with tempfile.TemporaryDirectory(prefix="minyar-connect-node-") as temporary:
        for mode in ["debug", "release"]:
            binary = Path(temporary) / ("server-" + mode)
            command = [str(launcher)]
            if mode == "release":
                command.append("--release")
            subprocess.run(command + [str(source / "server.min"), "-o", str(binary)], check=True, stdout=subprocess.DEVNULL, timeout=900)
            client = Path(temporary) / ("client-" + mode)
            # connectclient needs the portable http module, which --library selects on macOS too.
            subprocess.run(command + ["--library", str(launcher.parent / "library"), str(source / "minyar-client.min"), "-o", str(client)],
                           check=True, stdout=subprocess.DEVNULL, timeout=900)
            server = subprocess.Popen([str(binary)], stdout=subprocess.PIPE, text=True)
            try:
                line = server.stdout.readline().split()
                assert len(line) == 2 and line[0] == "port", "server did not report its port: " + " ".join(line)
                result = subprocess.run(["node", str(prefix / "client.mjs"), line[1]], cwd=prefix, capture_output=True, text=True, timeout=300)
                sys.stdout.write(mode + ": " + result.stdout)
                if result.returncode != 0:
                    sys.stderr.write(result.stderr)
                    raise SystemExit("connect-node client failed against the " + mode + " server")
                own = subprocess.run([str(client), line[1]], capture_output=True, text=True, timeout=120)
                expected = "echo 14 x-echo-trailer\npermission_denied no minyar.interop.v1.Pong\ndeadline_exceeded\nunimplemented\nunavailable\n"
                if own.returncode != 0 or own.stdout != expected:
                    raise SystemExit("Minyar client against the " + mode + " server:\n" + own.stdout + own.stderr)
                sys.stdout.write(mode + ": Minyar connectclient calls passed\n")
                assert server.poll() is None, "server exited during the calls"
            finally:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
