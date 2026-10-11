#!/usr/bin/env python3
"""Controlled owned-process failures; no compiler, QUIC peer or Docker."""
import argparse
import contextlib
import io
import importlib.util
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import quic_protocol_artifacts as helper

ROOT=Path(__file__).resolve().parents[1]
class InjectedStartFailure(RuntimeError): pass
class InjectedReadinessFailure(RuntimeError): pass
class InjectedRetentionFailure(RuntimeError): pass

def load(name):
    spec=importlib.util.spec_from_file_location("lifecycle_"+name.replace("-","_"),ROOT/"tests"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Certificates:
    def __init__(self,directory): self.directory=Path(directory)
    def path(self,name,suffix): return self.directory/(name+"."+suffix)
    def root(self,name): self.path(name,"der").write_bytes(b"controlled fixture")
    def leaf(self,name,*args,**kwargs):
        self.path(name,"der").write_bytes(b"controlled fixture")
        self.path(name,"pk8").write_bytes(b"controlled fixture")

LAST_RECORD={}

def controlled(case, artifacts=None):
    original_subprocess,original_threading,original_endpoint=helper.subprocess,helper.threading,helper.EndpointProcess
    original_class,original_os,original_digest=helper.ProtocolArtifacts,helper.os,helper.digest
    start_error=InjectedStartFailure("controlled thread start failure")
    ready_error=InjectedReadinessFailure("controlled readiness failure")
    original_run,original_argv=helper.ProtocolArtifacts.run,sys.argv
    owners=[]
    class RecordedArtifacts(original_class):
        def __init__(self,label,requested,**kwargs):
            super().__init__(label,artifacts/"endpoint-artifacts" if artifacts is not None else requested,**kwargs)
            owners.append(self)
    helper.ProtocolArtifacts=RecordedArtifacts
    processes=[];threads=[];started=0
    exits=case.endswith("unexpected-exit")
    command=[sys.executable,"-u","-c","import time,signal;"+("signal.signal(signal.SIGTERM,signal.SIG_IGN);" if case=="forced-shutdown" else "")+"print('QNS server ready',flush=True);"+("raise SystemExit(43)" if exits else "time.sleep(30)")]
    def popen(_command,**kwargs):
        process=original_subprocess.Popen(command,**kwargs);processes.append(process);return process
    def thread(*args,**kwargs):
        nonlocal started
        number=started;started+=1
        obj=threading.Thread(*args,**kwargs);threads.append(obj)
        if case in ("thread-first","primary-cleanup-error","thread-retention-error") and number==0 or case=="thread-second" and number==1:
            def fail(): raise start_error
            obj.start=fail
        return obj
    class ReadinessEndpoint(original_endpoint):
        def ready_line(self): raise ready_error
    def client_run(owner,argv,**kwargs):
        processes[-1].wait(timeout=5)
        downloads=Path(argv[5]);www=owner.workspace/"chacha20-www"
        for path in www.iterdir(): (downloads/path.name).write_bytes(path.read_bytes())
        return subprocess.CompletedProcess(argv,0,"","")
    class Socket:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def settimeout(self,value): pass
        def sendto(self,packet,address): self.packet=packet
        def recvfrom(self,size):
            processes[-1].wait(timeout=5)
            packet=self.packet
            response=b"\x80"+bytes(4)+bytes([8])+packet[15:23]+bytes([8])+packet[6:14]+bytes([0,0,0,1])
            return response,("127.0.0.1",44300)
    helper.subprocess=SimpleNamespace(**{name:getattr(subprocess,name) for name in ("PIPE","DEVNULL","TimeoutExpired","CompletedProcess","run")},Popen=popen)
    helper.threading=SimpleNamespace(Thread=thread)
    if case=="primary-cleanup-error":
        attempts=[0]
        def killpg(*args):
            attempts[0]+=1
            if attempts[0]==1:raise RuntimeError("controlled termination failure")
            return original_os.killpg(*args)
        helper.os=SimpleNamespace(**{name:getattr(original_os,name) for name in dir(original_os) if name!="killpg"},killpg=killpg)
        class FailedTerminationEndpoint(original_endpoint):
            def _windows_stop(self):
                attempts[0]+=1
                if attempts[0]==1:raise RuntimeError("controlled termination failure")
                return super()._windows_stop()
        helper.EndpointProcess=FailedTerminationEndpoint
    if "readiness" in case or case=="qns-retention-error": helper.EndpointProcess=ReadinessEndpoint
    if "retention-error" in case:
        injected=[False]
        def failing_digest(path):
            if str(path).endswith(".stdout.bin") and not injected[0]:
                injected[0]=True;raise InjectedRetentionFailure("controlled retention failure")
            return original_digest(path)
        helper.digest=failing_digest
    error=None;result=None
    try:
        with tempfile.TemporaryDirectory(prefix="quic-owned-lifecycle-") as directory:
            if case.startswith("thread-") or case in ("healthy-shutdown","forced-shutdown","primary-cleanup-error","context-retention-error"):
                with helper.ProtocolArtifacts("lifecycle",None,declared_cases=[case]) as owner:
                    endpoint=owner.endpoint([sys.executable],"endpoint",case=case,peer_timeout=30)
                    if endpoint.ready_line()!="QNS server ready\n": raise AssertionError("controlled readiness setup failed")
                    if case=="context-retention-error":raise ready_error
                    endpoint.stop()
                result=0
            else:
                name="quic-qns-local" if case.startswith("qns-") else "quic-vn-probe"
                module=load(name)
                fixture=SimpleNamespace(Certificates=Certificates,subprocess=subprocess)
                if case.startswith("qns-"):
                    module.fixtures=fixture
                    sys.argv=[name,"--client",sys.executable,"--server",sys.executable,"--case","chacha20"]
                    if exits: helper.ProtocolArtifacts.run=client_run
                else:
                    original_util=module.importlib.util
                    class Loader:
                        def exec_module(self,target): target.Certificates=Certificates;target.subprocess=subprocess
                    module.importlib=SimpleNamespace(util=SimpleNamespace(spec_from_file_location=lambda *args:SimpleNamespace(loader=Loader()),module_from_spec=lambda spec:SimpleNamespace()))
                    module.socket=SimpleNamespace(AF_INET=2,SOCK_DGRAM=2,socket=lambda *args:Socket())
                    sys.argv=[name,"--server",sys.executable]
                with contextlib.redirect_stdout(io.StringIO()):
                    result=module.main()
    except BaseException as caught:
        error=caught
    finally:
        helper.subprocess=original_subprocess;helper.threading=original_threading;helper.EndpointProcess=original_endpoint
        helper.ProtocolArtifacts=original_class;helper.ProtocolArtifacts.run=original_run;helper.os=original_os;helper.digest=original_digest;sys.argv=original_argv
    alive=any(p.poll() is None for p in processes)
    for process in processes:
        if process.poll() is None: helper.terminate_process_tree(process)
        process.wait(timeout=5)
    for obj in threads:
        if obj.ident is not None: obj.join(timeout=5)
    for process in processes:
        for stream in (process.stdout,process.stderr):
            if stream is not None and not stream.closed: stream.close()
    global LAST_RECORD
    LAST_RECORD={"actual_child_command":command,"children":[{"pid":p.pid,"status":p.returncode} for p in processes],"primary_exception":type(error).__name__ if error else None,"primary_notes":getattr(error,"__notes__",[]),"alive_before_test_cleanup":alive,"endpoint_commands":[row for owner in owners for row in owner.endpoint_commands]}
    expected=InjectedStartFailure if case.startswith("thread-") or case=="primary-cleanup-error" else InjectedReadinessFailure if "readiness" in case or case in ("qns-retention-error","context-retention-error") else None
    if expected and error is not (start_error if expected is InjectedStartFailure else ready_error): return {"thread-retention-error":96,"qns-retention-error":97,"context-retention-error":98}.get(case,90),"primary controlled exception identity was replaced"
    if "retention-error" in case and not any("controlled retention failure" in note for note in getattr(error,"__notes__",[])):return 99,"secondary retention failure was not preserved"
    if alive: return {"thread-first":42,"thread-second":52,"qns-readiness":62,"vn-readiness":72}.get(case,92),"owned endpoint survived primary failure"
    if exits and error is None: return 82 if case.startswith("qns-") else 83,"successful fixture accepted unexpectedly exited server43"
    if case=="primary-cleanup-error" and not any("controlled termination failure" in note for note in getattr(error,"__notes__",[])):return 94,"cleanup error was not retained with primary failure"
    if case=="forced-shutdown" and error is None:
        lifecycle=owners[0].endpoint_commands[0]["lifecycle"]
        if not lifecycle["passed"] or (not helper.windows_host() and (lifecycle["termination_strategy"]!="posix-sigkill-after-grace" or not lifecycle["receipt"]["previous"]["wait_timed_out"])):return 95,"forced owned shutdown receipt failed"
    if case in ("healthy-shutdown","forced-shutdown") and error is not None: return 91,type(error).__name__
    return 0,"controlled primary failure preserved, owned endpoint stopped and unexpected server exit rejected"

BASELINE={"thread-first":42,"thread-second":52,"qns-readiness":62,"vn-readiness":72,"qns-unexpected-exit":82,"vn-unexpected-exit":83,"healthy-shutdown":0,"forced-shutdown":0,"primary-cleanup-error":94,"thread-retention-error":96,"qns-retention-error":97,"context-retention-error":98}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--expect-old-code",action="store_true")
    parser.add_argument("--artifacts",type=Path)
    parser.add_argument("--case",action="append",choices=BASELINE)
    parser.add_argument("--expect-c3",action="store_true")
    args=parser.parse_args()
    if args.artifacts is not None:
        if not args.artifacts.is_absolute() or args.artifacts.exists():
            raise ValueError("--artifacts requires a fresh absolute path")
        args.artifacts.mkdir(parents=True)
    rows=[]
    cases={k:v for k,v in BASELINE.items() if (not args.case or k in args.case) and (not args.expect_old_code or k not in ("forced-shutdown","primary-cleanup-error","thread-retention-error","qns-retention-error","context-retention-error"))}
    for case,red in cases.items():
        directory=args.artifacts/case if args.artifacts is not None else None
        if directory is not None:directory.mkdir()
        code,message=controlled(case,directory);expected=red if args.expect_old_code or args.expect_c3 else 0
        rows.append({"case":case,"status":code,"expected":expected,"matched":code==expected,"message":message,**LAST_RECORD})
    report={"schema_version":1,"scope":"controlled fixture lifecycle only","declared_cases":list(cases),"results":rows,
            "inputs":{str(path):helper.digest(path) for path in (Path(__file__),ROOT/"tests/quic_protocol_artifacts.py",ROOT/"tests/quic-qns-local.py",ROOT/"tests/quic-vn-probe.py",Path(sys.executable).resolve())}}
    passed=all(r["matched"] for r in rows)
    report["status"]="passed" if passed else "failed"
    if args.artifacts is not None:
        (args.artifacts/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        files={p.relative_to(args.artifacts).as_posix():helper.digest(p) for p in args.artifacts.rglob("*") if p.is_file()}
        manifest={"schema_version":1,"scope":report["scope"],"status":report["status"],"inputs":report["inputs"],"declared_cases":list(cases),"files":files,"file_bytes":{name:(args.artifacts/name).stat().st_size for name in files},"case_inventory":[{"case":case,"files":[name for name in files if name.startswith(case+"/")]} for case in cases]}
        (args.artifacts/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return 0 if passed else 1
if __name__=="__main__":raise SystemExit(main())
