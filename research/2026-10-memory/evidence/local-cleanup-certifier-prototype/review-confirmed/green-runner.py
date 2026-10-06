"""Serial 30-second/256-MiB sampled-RSS gate for Python-only research tests."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import resource
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("label")
parser.add_argument("--checker")
args = parser.parse_args()
here = Path(__file__).resolve().parent
evidence = here.parent / "research/2026-10-memory/evidence/local-cleanup-certifier-prototype"
evidence.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
if args.checker:
    env["CLEANUP_RESEARCH_CHECKER"] = str(Path(args.checker).resolve())
command = [sys.executable, str(here / "cleanup-certificate-research-tests.py")]
start = time.monotonic()
rss_peak = 0
violation = None
with (evidence / (args.label + ".log")).open("wb") as log:
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
    while process.poll() is None:
        sample = subprocess.run(["ps", "-o", "rss=", "-p", str(process.pid)], capture_output=True, text=True)
        if sample.stdout.strip():
            rss_peak = max(rss_peak, int(sample.stdout.strip()) * 1024)
        elapsed = time.monotonic() - start
        if rss_peak > 256 * 1024 * 1024 or elapsed > 30:
            violation = "rss_limit" if rss_peak > 256 * 1024 * 1024 else "time_limit"
            process.kill()
            break
        time.sleep(0.05)
    returncode = process.wait()
measured_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
if sys.platform != "darwin":
    measured_peak *= 1024
if measured_peak > 256 * 1024 * 1024:
    violation = "rss_limit"
record = dict(command=command, checker=args.checker, returncode=returncode,
              elapsed_seconds_observed=time.monotonic() - start,
              sampled_rss_peak_bytes=rss_peak, sample_period_seconds=0.05,
              measured_child_maxrss_bytes=measured_peak,
              rss_scope="ps samples plus wait4 child peak; RUSAGE_CHILDREN includes ps subprocesses",
              time_limit_seconds=30, rss_limit_bytes=256 * 1024 * 1024,
              violation=violation, performance_claim=False)
for path in [here / "cleanup-certificate-research-tests.py",
             Path(args.checker) if args.checker else here / "cleanup-certificate-research.py"]:
    record.setdefault("source_sha256", {})[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
(evidence / (args.label + ".json")).write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record))
sys.exit(1 if violation else returncode)
