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
    "response-padding-client": (35, "semantic failure: PATH_RESPONSE padding or admission violated"),
    "response-padding-server": (35, "semantic failure: PATH_RESPONSE padding or admission violated"),
    "response-padding-width1": (35, "semantic failure: PATH_RESPONSE padding or admission violated"),
    "response-padding-width20": (35, "semantic failure: PATH_RESPONSE padding or admission violated"),
    "response-amp-credit": (35, "semantic failure: PATH_RESPONSE padding or admission violated"),
    "response-amp-limited": (0, "PATH_RESPONSE wire padding, token, route and admission passed"),
    "response-amp-blocked": (35, "semantic failure: PATH_RESPONSE padding or admission violated"),
    "response-pacing": (35, "semantic failure: PATH_RESPONSE padding or admission violated"),
    "response-congestion": (35, "semantic failure: PATH_RESPONSE padding or admission violated"),
    "response-pto-client": (36, "semantic failure: PATH_RESPONSE retransmitted after loss or PTO"),
    "response-pto-server": (36, "semantic failure: PATH_RESPONSE retransmitted after loss or PTO"),
    "response-loss-client": (36, "semantic failure: PATH_RESPONSE retransmitted after loss or PTO"),
    "response-loss-server": (36, "semantic failure: PATH_RESPONSE retransmitted after loss or PTO"),
    "response-mixed-pto": (36, "semantic failure: PATH_RESPONSE retransmitted after loss or PTO"),
    "response-mixed-loss": (36, "semantic failure: PATH_RESPONSE retransmitted after loss or PTO"),
    "response-mixed-path-loss": (36, "semantic failure: PATH_RESPONSE retransmitted after loss or PTO"),
    "cid-stock-single-path": (0, "original-CID traffic retained exactly two drained wire IDs"),
    "cid-stock-first-use": (66, "semantic failure: authenticated CID1 use did not supply wire CID2"),
    "cid-stock-first-use-server": (66, "semantic failure: authenticated CID1 use did not supply wire CID2"),
    "cid-stock-chain": (66, "semantic failure: consumed CID had no fresh wire-observed spare"),
    "cid-stock-loss": (66, "semantic failure: consumed CID had no replacement for loss recovery"),
    "cid-stock-loss-server": (66, "semantic failure: consumed CID had no replacement for loss recovery"),
    "cid-stock-reorder": (66, "semantic failure: first use had no spare before reordering control"),
    "cid-stock-retired-spare": (66, "semantic failure: replacement spare first use did not supply the next wire CID"),
    "cid-stock-retire-order": (66, "semantic failure: later use after retirement had no fresh wire spare"),
    "cid-stock-limit2": (0, "peer limit2 allowed no extra live CID"),
    "cid-stock-limit3": (66, "semantic failure: authenticated CID1 use did not supply wire CID2"),
    "cid-stock-cap8": (66, "semantic failure: newest use did not follow bounded live inventory"),
    "cid-stock-large-limit": (66, "semantic failure: newest use did not follow bounded live inventory"),
    "cid-stock-spoof": (0, "bad-tag, unknown-CID and truncated packets issued no CID"),
    "cid-stock-discarded-route": (0, "authenticated packet on an unaccepted client route"),
    "cid-stock-wrong-response": (0, "real candidate challenge answered on the wrong route"),
    "cid-stock-malformed": (0, "failed or closed authenticated CID1 packet preserved inventory"),
    "cid-stock-forbidden-server": (0, "failed or closed authenticated CID1 packet preserved inventory"),
    "cid-stock-close": (0, "failed or closed authenticated CID1 packet preserved inventory"),
    "cid-stock-retire-current": (0, "failed or closed authenticated CID1 packet preserved inventory"),
    "cid-stock-retire-unissued": (0, "failed or closed authenticated CID1 packet preserved inventory"),
    "cid-stock-stale": (0, "real receive-range pruning discarded an old authenticated unused-CID packet"),
    "current-route-alarm": (0, "old-route validation ACKs and sends preserved current-route loss"),
    "old-high-ack": (179, "semantic failure: old-route high packet ACK triggered loss on the current route"),
    "old-route-alarm": (180, "semantic failure: retained old-route validation sends postponed the current route PTO"),
    "old-high-current-rtt": (182, "semantic failure: old-route high packet ACK suppressed a later current-route RTT sample"),
    "current-packet-threshold": (0, "three real current-route packets triggered packet-threshold loss"),
    "old-probing-return": (181, "semantic failure: probing-only retained old-route packet changed the active route"),
    "old-nonprobing-return": (0, "ordinary authenticated traffic can return to the old route"),
    "old-path-late-ack": (174, "semantic failure: late old-epoch delivery ACK reset the current route PTO backoff"),
    "reused-path-late-ack": (174, "semantic failure: late old-epoch delivery ACK reset the current route PTO backoff"),
    "reused-path-ack": (155, "semantic failure: delayed old-route ACK sampled the new route RTT"),
    "reused-path-loss": (157, "semantic failure: old-route loss reduced the new route congestion window"),
    "mixed-path-ack": (170, "semantic failure: mixed ACK ranges counted an earlier route epoch in the current window"),
    "old-path-ack": (155, "semantic failure: delayed old-route ACK sampled the new route RTT"),
    "old-path-loss": (157, "semantic failure: old-route loss reduced the new route congestion window"),
    "current-path-ack": (0, "current-route ACK/loss still updates"),
    "current-path-loss": (0, "current-route ACK/loss still updates"),
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
    "validation-response-order": (242, "semantic failure: old-route revalidation deferred the admitted candidate response"),
    "validation-first-challenge": (248, "semantic failure: first candidate response omitted its path challenge"),
}

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path, help="binary compiled successfully from quic-migration-cids.min")
    parser.add_argument("--expect-old-code", action="store_true")
    parser.add_argument("--case", action="append", choices=tuple(BASELINE))
    parser.add_argument("--artifacts", type=Path)
    options = parser.parse_args()
    binary = options.binary.resolve(strict=True)
    results = []
    with ProtocolArtifacts("minyar-quic-migration-cids", options.artifacts, inputs=[Path(__file__), ROOT / "tests/quic-migration-cids.min", CA_SOURCE, binary, ROOT / "tests/quic_protocol_artifacts.py", ROOT / "tests/test_evidence.py"], declared_cases=options.case or list(BASELINE)) as artifacts:
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
        report = {"test_source_sha256": sha256(ROOT / "tests/quic-migration-cids.min"),
                  "binary_sha256": sha256(binary), "baseline": options.expect_old_code,
                  "compiler_invoked": False, "results": results}
        artifacts.publish(report, all(row["matched"] for row in results))
    print("QUIC CID/migration cases: " + str(sum(row["matched"] for row in results)) + "/" + str(len(results)) + " passed")
    for row in results:
        if not row["matched"]:
            print(json.dumps(row, indent=2))
    if not all(row["matched"] for row in results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
