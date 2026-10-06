"""Own-evidence stdlib serial Python probe gate, 30s and 256MiB observed peaks."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
command = [sys.executable, str(HERE / 'probe.py')]
start = time.monotonic()
rss_peak = 0
violation = None
with (HERE / 'probe-output.json').open('wb') as log:
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    while process.poll() is None:
        elapsed = time.monotonic() - start
        if elapsed > 30:
            violation = 'time_limit'
            process.kill()
            break
        sample = subprocess.run(['ps', '-o', 'rss=', '-p', str(process.pid)],
            capture_output=True, text=True, timeout=1)
        if sample.stdout.strip():
            rss_peak = max(rss_peak, int(sample.stdout.strip()) * 1024)
        if rss_peak > 256 * 1024 * 1024:
            violation = 'rss_limit'
            process.kill()
            break
        time.sleep(0.025)
    returncode = process.wait()
measured = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
if sys.platform != 'darwin':
    measured *= 1024
elapsed = time.monotonic() - start
if measured > 256 * 1024 * 1024:
    violation = 'rss_limit'
if elapsed > 30:
    violation = 'time_limit'
record = dict(command=command, returncode=returncode,
    elapsed_seconds_observed=elapsed, sampled_rss_peak_bytes=rss_peak,
    measured_child_maxrss_bytes=measured, sample_period_seconds=0.025,
    time_limit_seconds=30, rss_limit_bytes=256 * 1024 * 1024, violation=violation,
    performance_claim=False, llvm_execution=False,
    source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [HERE / 'probe.py', HERE / 'inputs/cleanup-certificate-research.py']})
(HERE / 'probe-resource.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
sys.exit(1 if violation else returncode)
