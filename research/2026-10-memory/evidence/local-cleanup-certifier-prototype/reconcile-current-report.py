"""Documentary reconciliation only; read retained JSON, never run the checker."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REPORT = ROOT / "research/2026-10-memory/local-cleanup-certifier-prototype.json"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


green = read(HERE / "independent-review-current-green.log")
gate = read(HERE / "independent-review-current-green.json")
red = read(HERE / "independent-review-expanded-red.log")
certificate = read(HERE / "actual-certificate-current.json")
capture = read(HERE / "actual-certificate-current-gate.json")
source_hashes = {str(p.relative_to(ROOT)): digest(p)
                 for p in sorted((ROOT / "tests").glob("cleanup-certificate-research*.py"))}
assert gate["returncode"] == 0 and gate["violation"] is None
assert green["failed"] == 0 and green["passed"] == green["cases"]
assert capture["returncode"] == 0 and capture["violation"] is None
for path, expected in gate["source_sha256"].items():
    assert digest(Path(path)) == expected
for path, expected in capture["source_sha256"].items():
    assert digest(Path(path)) == expected
counts = dict(cases=green["cases"], passed=green["passed"], failed=green["failed"],
              positive=sum(r["expected"] != "rejected" for r in green["results"]),
              negative=sum(r["expected"] == "rejected" for r in green["results"]),
              unique_input_hashes=len({r["input_sha256"] for r in green["results"]}),
              counts_by_record=dict(Counter(r["record"] for r in green["results"])))
plan = read(ROOT / "research/2026-10-memory/evidence/local-cleanup-certifier-design/tdd-plan.json")
planned = []
for row in plan["cases"]:
    cases = [r for r in green["results"] if r["record"] == row["id"]]
    assert cases and all(r["passed"] for r in cases)
    planned.append(dict(id=row["id"], case_count=len(cases),
                        variants=[r["variant"] for r in cases]))
coverage = dict(schema_version=1, status="current-source bounded gate passed",
                current=counts, source_sha256=source_hashes,
                preregistered_record_count=len(planned), planned_records=planned,
                expanded_preregistered_cases=sum(r["case_count"] for r in planned))
write(HERE / "control-coverage-current.json", coverage)

fault_names = ["assume_application_pure", "permit_parallel_branch",
               "permit_numeric_identifier", "permit_float_label"]
faults = []
for name in fault_names:
    record = read(HERE / ("fault-review-current-calibration-" + name + ".json"))
    retained = HERE / "fault-review-current-mutants" / (name + ".py")
    assert digest(retained) == record["mutant_sha256"]
    assert record["calibrated"] and record["gate"]["violation"] is None
    assert record["unchanged_tests_sha256"] == source_hashes["tests/cleanup-certificate-research-tests.py"]
    record["mutant_retained_path"] = str(retained.relative_to(ROOT))
    record["base_checker_sha256"] = source_hashes["tests/cleanup-certificate-research.py"]
    faults.append(record)
write(HERE / "fault-calibrations-current.json", dict(schema_version=1,
    scope="one affected historical family plus three new parser-check families; not a full historical rerun",
    original_seven_family_checkpoint="fault-calibrations.json",
    source_sha256=source_hashes, records=faults))

histories = []
for path in sorted(HERE.glob("*.json")):
    value = read(path)
    if not isinstance(value, dict) or "command" not in value or "returncode" not in value:
        continue
    if "time_limit_seconds" not in value:
        continue
    item = dict(gate=str(path.relative_to(ROOT)), resource_record=value)
    output = path.with_suffix(".log")
    if output.exists():
        try:
            results = read(output)
            if isinstance(results, dict) and "results" in results and "cases" in results:
                item["assertion_groups"] = {key: results[key] for key in ["cases", "passed", "failed"]}
        except (json.JSONDecodeError, UnicodeError) as error:
            item["output_status"] = "retained incomplete or non-JSON log: " + type(error).__name__
    histories.append(item)
history = dict(schema_version=1, gates=histories,
    interrupted_orchestration=read(HERE / "fault-orchestration-interrupted.json"),
    fixture_corrections=[
        "A trailing-comment edit did not truncate the function; fixture construction corrected without changing rejection expectation.",
        "A signature replacement matched twice; fixture construction corrected without changing semantic expectation.",
        "Independent numeric-ID and Float-label preliminary fixtures had unresolved read calls removed before baseline execution; executed identities are ec42bc9d... and 68c26667..., as pinned in review-subset-narrowing.json."
    ], historical_evidence_rewritten=False)
write(HERE / "validation-history-current.json", history)

report = read(HERE / "review-confirmed/prototype-report-before.json")
report["status"] = "current_source_validated; independent_replay_and_final_review_pending"
report["updated_utc"] = datetime.now(timezone.utc).isoformat()
report["historical_unvalidated_state"] = report.pop("current_unvalidated_sources")
report["checkpoint_actual_inference"] = report["actual_inference"]
report["actual_inference"] = dict(certificate,
    definitions_count=len(certificate["definitions"]),
    instructions_count=sum(r["instructions"] for r in certificate["definitions"]),
    blocks_count=sum(r["blocks"] for r in certificate["definitions"]))
report["current_validated_sources"] = dict(source_sha256=source_hashes, counts=counts,
    resource_gate=gate, certificate_gate=capture,
    red_first=dict(gate=read(HERE / "independent-review-expanded-red.json"),
                   cases=red["cases"], passed=red["passed"], failed=red["failed"],
                   failures=[r for r in red["results"] if not r["passed"]]))
report["proposed_constraints"]["review_repair_narrowing"] = read(HERE / "review-subset-narrowing.json")
report["checker_fault_controls"]["status"] = "seven checkpoint families retained; current affected purity and three new checks calibrated"
report["checker_fault_controls"]["current_records"] = faults
report["unsupported_corpus"] = [r for r in green["results"] if r["record"] == "unsupported_corpus"]
report["provenance"]["current_source_sha256"] = source_hashes
report["validation_history"] = "evidence/local-cleanup-certifier-prototype/validation-history-current.json"
report["residual_review_gates"] = [
    "Independent repaired-source static rereview and five minimal-probe replay outcomes at the exact current checker hash.",
    "O1/O3/O4/O5 subset proof arguments remain conditional; tests are not a mechanized proof.",
    "O2/O6 frozen C summary/cost correspondence, O7 truthful protected external borrowers and fair eventual service, O8 compiler/link/optimizer refinement remain premises or unresolved gates."
]
write(REPORT, report)
write(HERE / "input-manifest-current.json", dict(schema_version=1,
    prior_checkpoint_manifest="input-manifest.json", source_sha256=source_hashes,
    input_sha256=certificate["input_sha256"], catalog_sha256=certificate["catalog_sha256"],
    runtime_source_sha256=certificate["runtime_source_sha256"],
    retained_reviewer_inputs=read(HERE / "review-subset-narrowing.json")["retained_reviewer_inputs"],
    cases=[{key: r[key] for key in ["record", "variant", "entry", "expected", "options", "input_sha256"]}
           for r in green["results"]]))
write(HERE / "source-stability-handoff-current.json", dict(schema_version=1,
    recorded_utc=report["updated_utc"], status=report["status"],
    current_sources=source_hashes, current_counts=counts,
    certificate="actual-certificate-current.json", gate="independent-review-current-green.json",
    fault_controls="fault-calibrations-current.json", historical_handoff="source-stability-handoff.json",
    limits=report["limits"], residual_review_gates=report["residual_review_gates"],
    campaign_complete=False, production_readiness=False, performance_claim=False))
print(json.dumps(dict(counts=counts, fault_family_count=len(faults),
                      current_sources=source_hashes), indent=2))
