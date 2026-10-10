"""Read-only documentary/hash checks. Does not import research implementations."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/campaign-delivery-audit"
BASE = Path("research/2026-10-memory")
manifest = json.loads((OUT / "checkpoint-manifest.json").read_text())
supplement_path = OUT / "supplemental-manifest.json"
supplement = json.loads(supplement_path.read_text()) if supplement_path.exists() else []
checks = []
derived = {}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def record(name, actual, expected):
    checks.append({"name": name, "actual": actual, "expected": expected,
                   "passed": actual == expected})

def capture(path):
    path = Path(path)
    target = OUT / "checkpoint" / path
    if not target.exists():
        data = (ROOT / path).read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        supplement.append({"path": str(path), "sha256": sha(data),
                           "bytes": len(data), "snapshot": str(target.relative_to(ROOT)),
                           "captured_utc": datetime.now(timezone.utc).isoformat()})
    return target

def load(path):
    return json.loads(capture(path).read_text())

def report(name):
    return load(BASE / (name + ".json"))

def pointer(obj, value):
    for part in value.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj

for item in manifest["files"]:
    record("frozen hash: " + item["path"],
           sha((ROOT / item["snapshot"]).read_bytes()), item["sha256"])

abi = report("runtime-abi-evidence-map")
funcs = abi["functions"]
derived["abi"] = {"names": len({f["name"] for f in funcs}),
    "direct_correctness": sum(bool(f["direct_correctness_evidence"]) for f in funcs),
    "count_profiles": sum(bool(f["count_profile_evidence"]) for f in funcs),
    "workload_timing": sum(bool(f["workload_timing_evidence"]) for f in funcs)}
record("ABI separate mapped sets", derived["abi"],
       {"names": 105, "direct_correctness": 30, "count_profiles": 14, "workload_timing": 5})

peer = report("peer-evidence-reconciliation")
integration = report("peer-provenance-integration")
groups = peer["round2_through9_groups"]
dispositions = Counter(g["original_disposition"] for g in groups)
derived["peer"] = {"groups": len(groups), "group_ids": len({g["id"] for g in groups}),
    "by_historical_disposition": dict(dispositions),
    "source_entries": len(peer["sources"]),
    "selected_whole_files": sum(s["complete_selected_round_file"] for s in peer["sources"]),
    "raw_entries": len(integration["raw_source_verification"])}
record("peer groups", len(groups), 646)
record("peer dispositions", dict(dispositions), integration["counts"]["source_group_dispositions"])
record("selected whole files", derived["peer"]["selected_whole_files"], 30)
record("raw source entry count", len(integration["raw_source_verification"]), 197)
for item in integration["raw_source_verification"]:
    raw = item["verified_raw"]
    record("peer source bytes: " + item["source_id"],
           sha((ROOT / raw["path"]).read_bytes()), item["expected_sha256"])

ledger = report("peers-review-ledger")
counts = Counter(r["status"] for r in ledger["combined_bounded_inventory_paths"])
derived["peer"]["central_bounded_statuses"] = dict(counts)
record("central reviewed", counts["authored_review_record_available"] +
       counts["authored_review_record_available_with_explicit_extent"], 70)
for status, expected in [("not_semantically_reviewed_in_campaign_manifests", 753),
                         ("listed_not_semantically_reviewed", 3526),
                         ("directory_pending_recursive_enumeration", 9)]:
    record("central " + status, counts[status], expected)
record("whole/partial entry counts", [sum(x["whole_read_credit"] for x in integration["raw_source_verification"]),
       sum(x["partial_companion_only"] for x in integration["raw_source_verification"])], [174, 23])

selected_ids = integration["selected_saved_execution_ids"]
records = peer["archived_execution_records"] + peer["round9_execution_addendum"]["archived_execution_records"]
by_id = {r["id"]: r for r in records}
selected = [by_id[key] for key in selected_ids]
derived["peer"]["selected_records"] = len(selected)
derived["peer"]["selected_methods"] = len({r["method"] for r in selected})
derived["peer"]["selected_matrix_partition"] = dict(Counter(r["run"] for r in selected))
record("selected unique execution ids", len(set(selected_ids)), 78)
record("selected method identities", derived["peer"]["selected_methods"], 13)
for r in selected:
    obj = load(r["coverage"]["snapshot"])
    record("coverage hash: " + r["id"], sha(capture(r["coverage"]["snapshot"]).read_bytes()), r["coverage"]["sha256"])
    actual = pointer(obj, r["coverage"]["json_pointer"])
    record("selected executed exit/output: " + r["id"],
           [actual["returncode"], actual["stdout_sha256"]], [0, r["expected_stdout_sha256"]])
    link = pointer(obj, r["link"]["json_pointer"])
    flags = [f for f in link["argv"] if re.fullmatch(r"-O[0123szg]", f)]
    record("selected effective generated optimization: " + r["id"], flags[-1], r["effective_last_optimization"])

native = BASE / "evidence"
derived["native"] = {}
for label, file, expected in [
    ("round1", "native-application/final-expanded/results.json", 504),
    ("round2_matrix", "native-application-round2/final-matrix/results.json", 108),
    ("round4", "native-application-round4/final1/results.json", 75),
    ("round5", "native-application-round5/final-matrix/results.json", 36)]:
    d = load(native / file)
    derived["native"][label] = {"contract_rows": len(d["contracts"]), "status": d["status"]}
    record(label + " contract rows", len(d["contracts"]), expected)
soak2 = load(native / "native-application-round2/sustained/results.json")
derived["native"]["round2_sustained"] = {
    "cohorts": len(soak2["cohorts"]),
    "mixed_iterations": sum(r["final"]["mixed_iterations"] for r in soak2["cohorts"]),
    "mesh_api_calls": sum(r["actual_mesh_api_calls"] for r in soak2["cohorts"]),
    "wall_seconds_per_cohort": [r["final"]["wall_seconds"] for r in soak2["cohorts"]]}
record("round2 mixed iterations", derived["native"]["round2_sustained"]["mixed_iterations"], 12817408)
record("round2 actual API calls", derived["native"]["round2_sustained"]["mesh_api_calls"], 31274038)
r8 = [load(native / "native-application-round8/pilot2/results.json"),
      load(native / "native-application-round8/followup/results.json")]
derived["native"]["round8"] = {"configuration_groups": sum(c["groups"] for r in r8 for c in r["cohorts"])}
record("round8 configuration groups", derived["native"]["round8"]["configuration_groups"], 30)
r9 = load(native / "native-application-round9/baseline/results.json")
derived["native"]["round9"] = {"readbacks": len(r9["pixel_oracles"]),
    "image_pixel_observations": sum(sum(v for k,v in c["counts"].items() if k != "excluded") for c in r9["pixel_oracles"])}
record("round9 readbacks", derived["native"]["round9"]["readbacks"], 6)
record("round9 image pixels", derived["native"]["round9"]["image_pixel_observations"], 21408)
for f in ["native-application-round6/first-control/results.json",
          "native-application-round6/color-oracle-calibration/results.json",
          "native-application-round7/first-o2/results.json",
          "native-application-round7/one-sanitizer/results.json",
          "native-application-round7/one-sanitizer/abort-disposition.json",
          "native-application-round9/alpha-discard-disabled/results.json",
          "native-application-round9/translucent-depth-write/results.json"]:
    load(native / f)

for run in ["run-h2hs4wqq", "run-s9b7q1ep"]:
    d = load(native / "runtime-soak" / run / "results.json")
    long = next(r for r in d["runs"] if "two-hour" in r["label"])
    derived[run] = {"result_status": d["status"], "run_status": long.get("status"),
        "returncode": long.get("returncode"), "summary": long["latest_summary"],
        "source_hashes_unchanged": d.get("source_hashes_unchanged")}
    for source in d["sources"]:
        if source["path"].startswith("runtime/"):
            record("live frozen source: " + run + "/" + source["path"],
                   sha((ROOT / source["path"]).read_bytes()), source["sha256"])
    metric = native / "runtime-soak" / run / "metric-scope.json"
    if (ROOT / metric).exists(): load(metric)
record("fixed final duration", derived["run-h2hs4wqq"]["summary"]["elapsed_monotonic_seconds"], 7200.008299)
record("fixed normal exit/final", [derived["run-h2hs4wqq"]["returncode"], derived["run-h2hs4wqq"]["summary"]["final"]], [0,1])
record("system checkpoint unfinished", [derived["run-s9b7q1ep"]["result_status"], derived["run-s9b7q1ep"]["summary"]["final"]], ["running",0])

cert = native / "local-cleanup-certifier-prototype"
for label in ["independent-review-current-green", "independent-review-expanded-red"]:
    d = load(cert / (label + ".log"))
    rows = d["results"]
    v = {"assertion_groups": len(rows), "positive": sum(isinstance(r["expected"], int) for r in rows),
         "rejections": sum(not isinstance(r["expected"], int) for r in rows),
         "passed": sum(r["passed"] for r in rows), "input_hashes": len({r["input_sha256"] for r in rows})}
    derived[label] = v
record("certifier exact green counts", derived["independent-review-current-green"],
       {"assertion_groups":131,"positive":20,"rejections":111,"passed":131,"input_hashes":118})
record("certifier expanded red passes", derived["independent-review-expanded-red"]["passed"], 127)
replay = load(native / "local-cleanup-certifier-implementation-review/repaired-probe-output.json")
record("independent repaired replay", [sum(r["expectation_met"] for r in replay["results"]), len(replay["results"])], [5,5])
current = load(cert / "source-stability-handoff-current.json")
for p, expected in current["current_sources"].items():
    record("certifier current source hash: " + p, sha((ROOT / p).read_bytes()), expected)

lit = report("literature-proof-depth-round3")
derived["literature"] = []
for source in lit["sources"]:
    derived["literature"].append({"register_id":source["register_id"], "authors":source["authors"],
        "artifact_pages":source["artifact"]["pages"], "reading":source["reading"]["coverage"]})
    for k in ["artifact", "text"]:
        item=source[k]
        record("literature preserved bytes: " + source["id"] + "/" + k,
               sha((ROOT / item["path"]).read_bytes()), item["sha256"])
for p in [Path("research/novelty/sources.md"),Path("research/novelty/snapshot.json")]: capture(p)

inventory = load(native / "runtime/core-production/index.json")
record("accepted own core patch bytes", sha((ROOT / native / "runtime/core-production/own-production.patch").read_bytes()), inventory["patch_sha256"])
for item in inventory["files"]:
    record("accepted own core final: " + item["path"], sha((ROOT / item["path"]).read_bytes()), item["final_sha256"])
record("accepted graphics hash", sha((ROOT / "runtime/native/graphics.c").read_bytes()),
       "736bc64a8bea8edb134d7752cdb9ad9f0f3e8174cbe0ef7f716e4698e8f33eed")
scalar_fixtures = []
for variant in ["baseline", "candidate"]:
    p = native / "runtime-list-bulk-cpu/run-ws0ma9zu" / variant / "tests/memory-research-list-bulk-cpu.c"
    snapshot = capture(p)
    lines = snapshot.read_text().splitlines()
    matches = [{"line": i+1, "text": s} for i,s in enumerate(lines) if "MINYAR_RC_TESTING" in s]
    scalar_fixtures.append({"path":str(p),"sha256":sha(snapshot.read_bytes()),"extent":"macro definition only; no timing reanalysis", "matches":matches})
    record("scalar test accounting macro: " + variant, any(s["text"] == "#define MINYAR_RC_TESTING 1" for s in matches), True)
derived["scalar_fixture_accounting"] = scalar_fixtures

result = {"kind":"documentary/hash/count checks only; zero native/test/compiler executions",
          "checkpoint":manifest["captured_utc"], "checked_utc":datetime.now(timezone.utc).isoformat(),
          "derived":derived,"checks":checks,"failed":[c for c in checks if not c["passed"]]}
(OUT / "supplemental-manifest.json").write_text(json.dumps(supplement,indent=2)+"\n")
(OUT / "documentary-checks.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"checks":len(checks),"failed":len(result["failed"]),"supplemental_files":len(supplement),"derived":derived},indent=2))
