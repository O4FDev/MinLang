#!/usr/bin/env python3
"""One sustained process; real sockets/faults with independently sampled RSS.
QUIC/TLS composite soak is separate: this measures native socket foundations.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from soak_observer import observe, memory_summary, require_remote_lab

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seconds', type=int, default=7200)
parser.add_argument('--connections', type=int, default=4096)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--sanitize', action='store_true')
args = parser.parse_args()
require_remote_lab()
if not 1 <= args.seconds <= 86400 or not 1 <= args.connections <= 10000:
    parser.error('seconds must be 1..86400 and connections 1..10000')
args.output.mkdir(parents=True, exist_ok=False)
flags = ['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if args.sanitize else ['-O2']
executable = args.output.resolve()/'soak'
command = [os.environ.get('MINYAR_TEST_CLANG','clang'),'-std=c11','-D_GNU_SOURCE',
           '-DMINYAR_SYSTEM_HEAP=1','-Wall','-Wextra','-Werror',*flags,
           str(ROOT/'tests/net-soak.c'),str(ROOT/'runtime/minyar_runtime.c'),'-lm','-o',str(executable)]
subprocess.run(command,check=True)
started = time.time()
samples=[]
failure = None
last_peer = None
complete = False
with (args.output/'stderr.log').open('w') as errors, (args.output/'samples.jsonl').open('w') as evidence:
    process = subprocess.Popen([executable,str(args.seconds),str(args.connections)],stdout=subprocess.PIPE,
                               stderr=errors,start_new_session=True,
                               env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1'))
    try:
        for sample in observe(process, args.seconds + 120):
            if 'line' in sample:
                sample['peer'] = json.loads(sample['line'])
                if sample['peer']['phase'] == 'sample': last_peer = sample['peer']
                if sample['peer']['phase'] == 'complete': complete = True
            sample['wall_time']=time.time()
            evidence.write(json.dumps(sample,sort_keys=True)+'\n'); evidence.flush()
            if 'rss_kib' in sample: samples.append(sample)
    except Exception as error:
        failure = str(error)
    status=process.wait(timeout=15)
report={'seconds_requested':args.seconds,'connections':args.connections,'status':status,
        'samples':len(samples),'wall_seconds':time.time()-started,'sanitized':args.sanitize,
        'last_sample':samples[-1] if samples else None,
        'last_peer':last_peer,'observer_failure':failure,'completed':complete,
        **memory_summary(samples),
        'scope':'native TCP/UDP/readiness/timers; no TLS or QUIC transport'}
(args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
assert status==0 and complete and failure is None, 'soak crashed or timed out; inspect evidence'
assert samples, 'soak emitted no samples'
assert last_peer and last_peer['registry_slots'] <= args.connections+2, 'registry growth'
