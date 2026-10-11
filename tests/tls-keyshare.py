#!/usr/bin/env python3
"""Native P-256 ECDH vs independent OpenSSL pkeyutl, plus malformed SEC1 points."""
import argparse, importlib.util, os, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tls_tests", ROOT / "tests/tls-local.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sanitize", action="store_true")
    options = parser.parse_args()
    if options.sanitize:
        for name in ("MINYAR_CLANG_FLAGS", "MINYAR_NATIVE_FLAGS", "MINYAR_RUNTIME_FLAGS"):
            os.environ[name] = "-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module"
    with tempfile.TemporaryDirectory(prefix="minyar-p256-oracle-") as directory:
        directory = Path(directory)
        fixtures.openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", directory / "peer.key")
        fixtures.openssl("pkey", "-in", directory / "peer.key", "-pubout", "-outform", "DER", "-out", directory / "peer.spki")
        # RFC5480 named secp256r1 SubjectPublicKeyInfo; not a Minyar encoder.
        spki_prefix = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d030107034200")
        peer = (directory / "peer.spki").read_bytes()
        assert peer.startswith(spki_prefix) and len(peer) == len(spki_prefix) + 65
        (directory / "peer.point").write_bytes(peer[len(spki_prefix):])
        binary = directory / "p256"
        fixtures.compile_program(ROOT / "tests/tls-keyshare.min", binary)
        result = subprocess.run([str(binary), str(directory / "peer.point")], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
        line = next(line for line in result.stdout.splitlines() if line.startswith("ORACLE "))
        _, point, actual = line.split()
        (directory / "minyar.spki").write_bytes(spki_prefix + bytes.fromhex(point))
        fixtures.openssl("pkeyutl", "-derive", "-inkey", directory / "peer.key", "-peerkey", directory / "minyar.spki",
                         "-peerform", "DER", "-out", directory / "expected")
        assert bytes.fromhex(actual) == (directory / "expected").read_bytes()
        print(result.stdout.splitlines()[-1])
        print("TLS P-256: independent OpenSSL ECDH oracle matched")
if __name__ == "__main__":
    main()
