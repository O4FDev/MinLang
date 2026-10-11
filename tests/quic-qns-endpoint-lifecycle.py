#!/usr/bin/env python3
"""The QNS PID 1 must honor shutdown before network readiness."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys

LAUNCHER = """
import json,pathlib,runpy,signal,sys,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
signal.signal(signal.SIGINT,signal.SIG_IGN)
exists=pathlib.Path.exists
pathlib.Path.exists=lambda p: False if str(p)=='/tmp/network-ready' else exists(p)
sleep=time.sleep
observed=False
def waiting(seconds):
 global observed
 if seconds==.05 and not observed:
  observed=True
  print(json.dumps({'waiting':True,'term_ignored':signal.getsignal(signal.SIGTERM)==signal.SIG_IGN}),flush=True)
 sleep(seconds)
time.sleep=waiting
runpy.run_path(sys.argv[1],run_name='__main__')
"""

def run(source, sig):
    data=source.read_bytes()
    compile(data,str(source),"exec")
    env=dict(os.environ,TESTCASE="handshake",ROLE="server")
    process=subprocess.Popen([sys.executable,"-E","-c",LAUNCHER,str(source)],
                             env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    pidfd=os.pidfd_open(process.pid)
    try:
        ready,_,_=select.select([process.stdout],[],[],3)
        if not ready:raise AssertionError("endpoint did not reach its readiness wait")
        observed=json.loads(process.stdout.readline())
        if observed.get("waiting") is not True:raise AssertionError("missing readiness observation")
        signal.pidfd_send_signal(pidfd,sig)
        try:status=process.wait(timeout=2)
        except subprocess.TimeoutExpired:status=None
        print(json.dumps({"signal":sig.name,"observed":observed,"exit_status":status,
                          "source_sha256":hashlib.sha256(data).hexdigest()}),flush=True)
        if status != 128+sig:raise AssertionError("endpoint ignored shutdown while awaiting network")
    finally:
        if process.poll() is None:
            signal.pidfd_send_signal(pidfd,signal.SIGKILL)
            process.wait(timeout=3)
        os.close(pidfd)
        process.stdout.close();process.stderr.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--endpoint",type=Path,default=Path(__file__).parent/"interop/qns/endpoint.py")
    args=parser.parse_args()
    for sig in (signal.SIGTERM,signal.SIGINT):run(args.endpoint,sig)
