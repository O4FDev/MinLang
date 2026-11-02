#!/usr/bin/env python3
"""A stock @grpc/grpc-js client against library/grpc.min over h2c and TLS.

Builds tests/grpc-interop.min, makes a throwaway CA and localhost leaf with
openssl, installs the pinned client from tests/interop/grpc-js into
build/grpc-js (npm ci, lockfile only), and runs tests/interop/grpc-js/client.js
in both modes: unary and server-streaming calls, handler errors with details,
deadline expiry and client cancellation.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "tests/interop/grpc-js"


def run(command, **options):
    return subprocess.run(command, check=True, timeout=600, **options)


def install(build):
    target = build / "grpc-js"
    stamp = target / "package-lock.json"
    lock = (PACKAGE / "package-lock.json").read_bytes()
    if not stamp.exists() or stamp.read_bytes() != lock or not (target / "node_modules/@grpc/grpc-js").exists():
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy(PACKAGE / "package.json", target / "package.json")
        shutil.copy(PACKAGE / "package-lock.json", target / "package-lock.json")
        run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=target, stdout=subprocess.DEVNULL)
    return target / "node_modules"


def authority(directory):
    def openssl(*arguments):
        run(["openssl", *arguments], cwd=directory, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    openssl("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-days", "2",
            "-subj", "/CN=grpc test root", "-keyout", "root.key", "-out", "root.pem")
    openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", "leaf.key")
    openssl("req", "-new", "-key", "leaf.key", "-subj", "/CN=localhost", "-out", "leaf.csr")
    (directory / "leaf.ext").write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n")
    openssl("x509", "-req", "-in", "leaf.csr", "-CA", "root.pem", "-CAkey", "root.key", "-CAcreateserial", "-days", "2",
            "-extfile", "leaf.ext", "-out", "leaf.pem")
    openssl("x509", "-in", "leaf.pem", "-outform", "DER", "-out", "leaf.der")
    openssl("pkcs8", "-topk8", "-nocrypt", "-in", "leaf.key", "-outform", "DER", "-out", "leaf.pk8")


def main():
    launcher = Path(sys.argv[1]).resolve()
    modes = sys.argv[2:] or ["--debug", "--release"]
    if not shutil.which("node") or not shutil.which("npm"):
        raise SystemExit("grpc interop needs Node.js and npm for the stock @grpc/grpc-js client")
    modules = install(ROOT / "build")
    with tempfile.TemporaryDirectory(prefix="minyar-grpc-") as temporary:
        directory = Path(temporary)
        authority(directory)
        for mode in modes:
            binary = directory / ("server" + mode)
            run([str(launcher), mode, str(ROOT / "tests/grpc-interop.min"), "-o", str(binary)], stdout=subprocess.DEVNULL)
            server = subprocess.Popen([str(binary), str(directory / "leaf.der"), str(directory / "leaf.pk8")],
                                      stdout=subprocess.PIPE, text=True)
            try:
                plain, secure = server.stdout.readline().split()
                environment = dict(os.environ, NODE_PATH=str(modules))
                for kind, port in (("h2c", plain), ("tls", secure)):
                    result = subprocess.run(["node", str(PACKAGE / "client.js"), kind, port, str(directory / "root.pem")],
                                            env=environment, capture_output=True, text=True, timeout=120)
                    sys.stdout.write("".join(mode + " " + line + "\n" for line in result.stdout.splitlines()))
                    assert result.returncode == 0, result.stdout + result.stderr
                quit = subprocess.run(["node", "-e", QUIT, plain], env=environment, capture_output=True, text=True, timeout=60)
                assert quit.returncode == 0, quit.stderr
                assert server.wait(timeout=30) == 0, "server exit status"
            finally:
                server.kill()
                server.wait()
    print("grpc interop: @grpc/grpc-js unary, streaming, errors, deadlines and cancellation over h2c and TLS")


QUIT = """
const grpc = require("@grpc/grpc-js");
const raw = (buffer) => buffer;
const Probe = grpc.makeGenericClientConstructor({ quit: { path: "/test.Probe/Quit", requestStream: false, responseStream: false,
    requestSerialize: raw, requestDeserialize: raw, responseSerialize: raw, responseDeserialize: raw } }, "Probe");
new Probe("127.0.0.1:" + process.argv[1], grpc.credentials.createInsecure()).quit(Buffer.alloc(0), (error) => process.exit(error ? 1 : 0));
"""

if __name__ == "__main__":
    main()
