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
from quic_protocol_artifacts import ProtocolArtifacts

ROOT = Path(__file__).resolve().parents[1]
CA_SOURCE = ROOT / "tests/tls-local.py"
SPEC = importlib.util.spec_from_file_location("quic_cid_certificates", CA_SOURCE)
FIXTURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURES)
BASELINE = {
    "client-policy": (32, "semantic failure: client ignored its restricted ChaCha cipher offer"),
    "server-policy": (42, "semantic failure: server ignored its restricted ChaCha cipher policy"),
    "server-ticket": (52, "semantic failure: resumption restored an excluded ticket cipher over server policy"),
    "client-ticket": (62, "semantic failure: client retained an AES ticket and 0-RTT under a ChaCha-only policy"),
    "unoffered": (72, "semantic failure: client accepted a ServerHello cipher excluded by its offer"),
    "chacha-update": (32, "semantic failure: client ignored its restricted ChaCha cipher offer"),
    "default-aes": (0, "cipher policy authenticated"),
    "invalid-policy": (0, "invalid or late policy changes"),
}

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path, help="binary compiled successfully from quic-cipher-policy.min")
    parser.add_argument("--expect-old-code", action="store_true")
    parser.add_argument("--case", action="append", choices=tuple(BASELINE))
    parser.add_argument("--artifacts", type=Path)
    options = parser.parse_args()
    binary = options.binary.resolve(strict=True)
    results = []
    with ProtocolArtifacts("minyar-quic-cipher-policy", options.artifacts, inputs=[Path(__file__), ROOT / "tests/quic-cipher-policy.min", CA_SOURCE, binary, ROOT / "tests/quic_protocol_artifacts.py", ROOT / "tests/test_evidence.py"], declared_cases=options.case or list(BASELINE)) as artifacts:
        artifacts.fixture(FIXTURES)
        certificates = FIXTURES.Certificates(artifacts.workspace)
        certificates.root("root")
        certificates.leaf("server", "root")
        certificates.leaf("client", "root", usage="clientAuth")
        artifacts.certificates_ready()
        inputs = [str(certificates.path("root", "der")), str(certificates.path("server", "der")),
                  str(certificates.path("server", "pk8")), str(certificates.path("client", "der")),
                  str(certificates.path("client", "pk8"))]
        for case in options.case or list(BASELINE):
            completed = artifacts.run([str(binary), *inputs, case], capture_output=True, text=True, timeout=60, case=case)
            expected_code, required_message = BASELINE[case] if options.expect_old_code else (0, "")
            matched = completed.returncode == expected_code and required_message in completed.stdout
            results.append({"case": case, "returncode": completed.returncode, "expected_returncode": expected_code,
                            "matched": matched, "stdout": completed.stdout, "stderr": completed.stderr})
        report = {"test_source_sha256": sha256(ROOT / "tests/quic-cipher-policy.min"),
                  "binary_sha256": sha256(binary), "baseline": options.expect_old_code,
                  "compiler_invoked": False, "results": results}
        artifacts.publish(report, all(row["matched"] for row in results))
    print(json.dumps(report, indent=2))
    if not all(row["matched"] for row in results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
