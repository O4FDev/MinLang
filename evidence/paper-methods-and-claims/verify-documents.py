"""Verify this synthesis's retained documents; execute no experiment or input code."""

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
OWNED = ROOT / "evidence/paper-methods-and-claims"
BRIEF = ROOT / "research/2026-10-memory/paper-methods-and-claims.md"
COMPANION = BRIEF.with_suffix(".json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ledger = json.loads((OWNED / "reading-ledger.json").read_text())
    record = json.loads(COMPANION.read_text())
    markdown = BRIEF.read_text()
    failures = []

    def require(condition, description):
        if not condition:
            failures.append(description)

    indexed = {row["path"]: row for row in ledger}
    require(len(indexed) == len(ledger), "Input paths must be unique")
    for row in ledger:
        snapshot = ROOT / row["snapshot"]
        require(snapshot.is_file(), "Missing snapshot: " + row["snapshot"])
        if snapshot.is_file():
            require(digest(snapshot) == row["sha256"], "Snapshot hash: " + row["path"])
            require(snapshot.stat().st_size == row["bytes"], "Snapshot size: " + row["path"])
        require(bool(row["reading_extent"]) and row["reading_extent"] != "pending",
                "Unspecified reading extent: " + row["path"])

    def check_refs(value):
        if isinstance(value, dict):
            if all(key in value for key in ("path", "snapshot", "sha256")):
                expected = indexed.get(value["path"])
                require(expected is not None, "Unregistered reference: " + value["path"])
                if expected:
                    require(value["sha256"] == expected["sha256"], "Reference hash: " + value["path"])
                    require(value["snapshot"] == expected["snapshot"], "Reference snapshot: " + value["path"])
            for item in value.values():
                check_refs(item)
        elif isinstance(value, list):
            for item in value:
                check_refs(item)

    check_refs(record)
    expected_ids = [f"C{number:02d}" for number in range(1, 15)]
    require([row["id"] for row in record["claims"]] == expected_ids, "Claim identities/order")
    primary_ids = {row["id"] for row in record["primary_predecessors"]}
    for claim in record["claims"]:
        require(bool(claim["evidence"]), "Claim evidence: " + claim["id"])
        require(bool(claim["source_scope"]), "Claim source scope: " + claim["id"])
        require(set(claim["primary_predecessor_ids"]) <= primary_ids,
                "Claim primary attribution: " + claim["id"])
        require("| " + claim["id"] + " |" in markdown, "Markdown claim row: " + claim["id"])

    joint_path = "research/2026-10-memory/runtime-joint-final-results.json"
    joint = json.loads((ROOT / indexed[joint_path]["snapshot"]).read_text())
    for row in joint["groups"] + joint["supplemental_and_provenance"]:
        require(indexed[row["path"]]["sha256"] == row["sha256"], "Joint referenced hash: " + row["path"])

    expected_source_hashes = {
        "runtime/minyar_runtime.c": "d919f066a0e71c80cb079a22659928541e958b68b81a645d7631f52ec8531a51",
        "runtime/minyar_collections.h": "3b7ce602bc256dc8a42f49d87fd6cccd0eb28132d952e3eb34284614c4725810",
        "tests/cleanup-certificate-research.py": "d2607ac5c8d638b1d25dcd157be7aa459e021d94f7f51dded5fbf736194f96d5",
    }
    for path, expected in expected_source_hashes.items():
        require(indexed[path]["sha256"] == expected, "Frozen source identity: " + path)
        require(digest(ROOT / path) == expected, "Current source identity: " + path)

    certificate_path = "research/2026-10-memory/evidence/local-cleanup-certifier-prototype/actual-certificate-current.json"
    certificate = json.loads((ROOT / indexed[certificate_path]["snapshot"]).read_text())
    require(certificate["work"]["V"] == 2 and certificate["work"]["F"] == 2
            and certificate["work"]["W_full_service_component"] == 4, "Archived local demand")
    require(certificate["catalog_sha256"] == record["source_sets"]["certifier_catalog_sha256"],
            "Frozen certifier catalog identity")
    require(all(row["status"] == "required_not_discharged"
                for row in certificate["external_requirements"]), "Undischarged external protection")
    require(len(certificate["definitions"]) == 13, "Thirteen selected definitions")

    handoff_path = "research/2026-10-memory/evidence/local-cleanup-certifier-prototype/source-stability-handoff-current.json"
    handoff = json.loads((ROOT / indexed[handoff_path]["snapshot"]).read_text())
    counts = handoff["current_counts"]
    require([counts[key] for key in ("cases", "passed", "positive", "negative", "unique_input_hashes")]
            == [131, 131, 20, 111, 118], "Archived certifier count units")
    raw_scalar_path = "research/2026-10-memory/evidence/runtime-list-bulk-production-cpu/run-x3798c1e/results.json"
    scalar = json.loads((ROOT / indexed[raw_scalar_path]["snapshot"]).read_text())
    require(len(scalar["pairs"]) == 192 and len(scalar["pilots"]) == 204,
            "Separate scalar production pair/pilot units")

    running_path = "research/2026-10-memory/evidence/runtime-joint-endurance/run-p52nr6__/results.json"
    running = json.loads((ROOT / indexed[running_path]["snapshot"]).read_text())
    require(running["status"] == "running", "Immutable running checkpoint")
    require(next(row for row in record["claims"] if row["id"] == "C12")["status"] == "pending",
            "No inferred final endurance pass")
    require(record["campaign_complete"] is False and record["novelty_established"] is False,
            "Campaign/novelty remain unestablished")

    local_links = []
    citation_urls = []
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", markdown):
        if target.startswith("https://"):
            citation_urls.append(target)
        else:
            resolved = (BRIEF.parent / target).resolve()
            local_links.append({"target": target, "resolved": str(resolved), "exists": resolved.exists()})
            require(resolved.exists(), "Local Markdown link: " + target)
    require(set(citation_urls) <= {row["url"] for row in record["primary_predecessors"]},
            "Primary citation URLs match retained attribution records")

    abstract = markdown.split("## Candidate abstract\n\n", 1)[1].split("\n\n##", 1)[0]
    body_words = len(markdown.split("## Evidence and claims ledger", 1)[0].split())
    abstract_words = len(abstract.split())
    require(1500 <= body_words <= 2500, "Requested brief length")
    require(abstract_words <= 180, "Abstract length")
    require(not any(line.rstrip() != line for line in markdown.splitlines()), "Markdown whitespace")

    result = {
        "status": "passed" if not failures else "failed",
        "scope": "Document/identity/claim/link checks only; zero new experiment or runtime test execution",
        "brief_sha256": digest(BRIEF),
        "companion_sha256": digest(COMPANION),
        "reading_ledger_sha256": digest(OWNED / "reading-ledger.json"),
        "input_hash_manifest_sha256": digest(OWNED / "inputs.sha256"),
        "brief_words_before_ledger": body_words,
        "abstract_words": abstract_words,
        "claim_ids": expected_ids,
        "local_links": local_links,
        "primary_citation_urls": citation_urls,
        "all_retained_input_hashes_match": not any("Snapshot hash:" in value for value in failures),
        "running_endurance_snapshot_only": True,
        "final_endurance_outcome_inspected": False,
        "statistical_reanalysis": False,
        "failures": failures,
    }
    (OWNED / "documentary-checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "brief_words_before_ledger", "abstract_words", "failures")}))
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
