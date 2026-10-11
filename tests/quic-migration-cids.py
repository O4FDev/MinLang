#!/usr/bin/env python3
"""Run protocol assertions with a separately compiled binary after heavy GO.

This driver never invokes the compiler. A compiler/parser error is a failed
prerequisite, never a semantic baseline red. --expect-old-code requires the
specific protocol failures and a passing NAT-rebinding control.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CA_SOURCE = ROOT / "tests/tls-local.py"
SPEC = importlib.util.spec_from_file_location("quic_cid_certificates", CA_SOURCE)
FIXTURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURES)
BASELINE = {
    "migration-cid": (42, "semantic failure: intentional new path reused the original destination CID"),
    "cid-unavailable": (52, "semantic failure: intentional migration accepted without an unused destination CID"),
    "preferred-address": (62, "semantic failure: a valid preferred_address caused a transport-parameter failure"),
    "nat-rebinding": (0, "NAT rebinding preserved the client's CID"),
    "failed-validation": (82, "semantic failure: expired intentional candidate retained its path and destination CID"),
    "retire-prior": (92, "semantic failure: retiring the active CID left a path transmitting the retired destination"),
    "duplicate-retirement": (102, "semantic failure: reordered duplicate NEW_CONNECTION_ID accumulated retirement state"),
    "successful-retirement": (112, "semantic failure: validated intentional migration retained the abandoned original path"),
    "preferred-api": (0, "authenticated preferred CID"),
    "repeated-migration": (0, "fifty sequential migrations"),
    "cid-rebound": (0, "an authenticated sequence rebound"),
    "preferred-validation": (0, "authenticated preferred CID"),
    "preferred-disabled": (152, "semantic failure: disable_active_migration blocked authenticated preferred-address validation"),
    "preferred-fallback": (0, "failed preferred-address validation"),
    "response-routes": (0, "wrong-route response"),
    "late-response": (0, "late response"),
    "token-reuse": (192, "semantic failure: two live destination CIDs shared a stateless-reset token"),
    "retirement-bound": (0, "unacknowledged retirement state is bounded"),
    "retired-destination": (0, "authenticated packets addressed to a retired CID"),
    "early-routes": (0, "0-RTT used the original destination"),
    "unknown-destination": (0, "unknown destination CID did not allocate a path"),
    "unknown-server-route": (252, "semantic failure: discarded unknown server route changed packet or key-phase state"),
    "candidate-ack-width": (245, "semantic failure: candidate-path ACK used active CID width and exceeded the peer MTU"),
    "reciprocal-cid": (202, "semantic failure: server reused its original destination CID for an intentional peer path"),
    "preferred-reciprocal": (202, "semantic failure: server reused its original destination CID for an intentional peer path"),
    "server-cid-unavailable": (214, "semantic failure: server replied to intentional migration without an unused destination CID"),
    "nat-cid-unavailable": (0, "NAT rebinding preserved the client"),
    "previous-path-probe": (224, "semantic failure: apparent migration did not challenge the previously active route"),
    "previous-path-return": (234, "semantic failure: newer original-route packet retained the spurious migration candidate"),
    "previous-path-timeout": (0, "expired old and candidate validation"),
}

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path, help="binary compiled successfully from quic-migration-cids.min")
    parser.add_argument("--expect-old-code", action="store_true")
    parser.add_argument("--case", action="append", choices=tuple(BASELINE))
    options = parser.parse_args()
    binary = options.binary.resolve(strict=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="minyar-quic-cid-") as directory:
        certificates = FIXTURES.Certificates(directory)
        certificates.root("root")
        certificates.leaf("server", "root")
        certificates.leaf("client", "root", usage="clientAuth")
        inputs = [str(certificates.path("root", "der")), str(certificates.path("server", "der")),
                  str(certificates.path("server", "pk8")), str(certificates.path("client", "der")),
                  str(certificates.path("client", "pk8"))]
        for case in options.case or list(BASELINE):
            completed = subprocess.run([str(binary), *inputs, case], capture_output=True, text=True, timeout=60)
            expected_code, required_message = BASELINE[case] if options.expect_old_code else (0, "")
            matched = completed.returncode == expected_code and required_message in completed.stdout
            results.append({"case": case, "returncode": completed.returncode, "expected_returncode": expected_code,
                            "matched": matched, "stdout": completed.stdout, "stderr": completed.stderr})
    report = {"test_source_sha256": sha256(ROOT / "tests/quic-migration-cids.min"),
              "binary_sha256": sha256(binary), "baseline": options.expect_old_code,
              "compiler_invoked": False, "results": results}
    print(json.dumps(report, indent=2))
    if not all(row["matched"] for row in results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
