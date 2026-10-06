"""Capture the current research CLI result in one bounded serial worker.

The saved LLVM is text input only. This runner never compiles or executes it.
Historical certificate files are preserved; current output has separate names.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
checker = ROOT / "tests/cleanup-certificate-research.py"
source_paths = sorted((ROOT / "tests").glob("cleanup-certificate-research*.py"))
source_paths.append(Path(__file__).resolve())
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
saved_ir = ROOT / "research/2026-10-memory/evidence/local-cleanup-certifier-design/inputs/application/application.ll"
command = [sys.executable, str(checker), str(saved_ir), ".minyar.fn.minyar_module_1_snow"]
start, rss_peak, violation = time.monotonic(), 0, None
with (HERE / "actual-certificate-current.log").open("wb") as log, \
        (HERE / "actual-certificate-current-stderr.log").open("wb") as errors:
    worker = subprocess.Popen(command, stdout=log, stderr=errors,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    while worker.poll() is None:
        sample = subprocess.run(["ps", "-o", "rss=", "-p", str(worker.pid)],
                                capture_output=True, text=True)
        if sample.stdout.strip():
            rss_peak = max(rss_peak, int(sample.stdout.strip()) * 1024)
        if rss_peak > 256 * 1024 * 1024 or time.monotonic() - start > 30:
            violation = "rss_limit" if rss_peak > 256 * 1024 * 1024 else "time_limit"
            worker.kill()
            break
        time.sleep(0.05)
    returncode = worker.wait()
measured_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
if sys.platform != "darwin":
    measured_peak *= 1024
if measured_peak > 256 * 1024 * 1024:
    violation = "rss_limit"
after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
if after != hashes:
    violation = "source_drift"
gate = dict(command=command, returncode=returncode,
            elapsed_seconds_observed=time.monotonic() - start,
            sampled_rss_peak_bytes=rss_peak, measured_child_maxrss_bytes=measured_peak,
            sample_period_seconds=0.05, time_limit_seconds=30, rss_limit_bytes=268435456,
            rss_scope="ps samples plus child peak; RUSAGE_CHILDREN includes ps subprocesses",
            source_sha256=hashes, source_sha256_after=after,
            input_sha256=hashlib.sha256(saved_ir.read_bytes()).hexdigest(),
            violation=violation, performance_claim=False, llvm_execution=False)
(HERE / "actual-certificate-current-gate.json").write_text(json.dumps(gate, indent=2) + "\n")
print(json.dumps(gate))
if returncode == 0 and violation is None:
    certificate = json.loads((HERE / "actual-certificate-current.log").read_text())
    certificate["capture_provenance"] = dict(source_sha256=hashes,
        resource_gate="actual-certificate-current-gate.json",
        raw_cli_output="actual-certificate-current.log")
    (HERE / "actual-certificate-current.json").write_text(json.dumps(certificate, indent=2) + "\n")
raise SystemExit(1 if violation else returncode)
