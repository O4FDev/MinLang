#!/usr/bin/env python3
"""A simulator must finish both capture writers before its PID 1 exits."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

def run(source, sig):
    # Adopt only this test's harmless writer children after the shell exits.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0):
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER")
    data=source.read_bytes()
    block=data.decode()
    if "PID=" in block:
        block=block[block.index("PID="):]
    with tempfile.TemporaryDirectory(prefix="minyar-simulator-shutdown-") as temporary:
        root=Path(temporary)
        writer=root/"writer.py"
        writer.write_text(
            "import os,signal,sys,time\n"
            "from pathlib import Path\n"
            "p=Path(sys.argv[1])\n"
            "def flush(sig,frame):\n"
            " time.sleep(.2)\n"
            " p.with_suffix('.flushed').write_text('capture complete')\n"
            " raise SystemExit(0)\n"
            "signal.signal(signal.SIGINT,flush)\n"
            "signal.signal(signal.SIGTERM,flush)\n"
            "p.write_text(str(os.getpid()))\n"
            "while True: signal.pause()\n")
        shell=root/"run.sh"
        import shlex
        command=shlex.join([sys.executable,str(writer)])
        shell.write_text("set -e\n"+command+" "+str(root/"left")+" &\n"+
                         command+" "+str(root/"right")+" &\n"+
                         "PID=$(jobs -p | tr '\\n' ' ')\n"+block)
        process=subprocess.Popen(["/bin/bash",str(shell)],start_new_session=True,
                                 preexec_fn=lambda:signal.signal(signal.SIGINT,signal.SIG_DFL))
        parentfd=os.pidfd_open(process.pid)
        children=[]
        try:
            deadline=time.monotonic()+3
            while not all((root/name).exists() for name in ("left","right")):
                if process.poll() is not None or time.monotonic()>=deadline:
                    raise RuntimeError("capture writers did not become ready")
                time.sleep(.01)
            children=[(int((root/name).read_text()),os.pidfd_open(int((root/name).read_text())))
                      for name in ("left","right")]
            signal.pidfd_send_signal(parentfd,sig)
            status=process.wait(timeout=3)
            flushed=[(root/(name+".flushed")).exists() for name in ("left","right")]
            result={"signal":sig.name,"shell_status":status,"flushed_at_shell_exit":flushed,
                    "source_sha256":hashlib.sha256(data).hexdigest()}
            print(json.dumps(result),flush=True)
            if status != 128+sig or flushed != [True,True]:
                raise AssertionError("simulator exited before both capture writers finished")
        finally:
            if process.poll() is None:
                signal.pidfd_send_signal(parentfd,signal.SIGKILL)
                process.wait(timeout=3)
            os.close(parentfd)
            for pid,fd in children:
                try:signal.pidfd_send_signal(fd,signal.SIGKILL)
                except ProcessLookupError:pass
                finally:os.close(fd)
                try:os.waitpid(pid,0)
                except ChildProcessError:pass

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--script",type=Path,default=Path(__file__).parent/"interop/qns/simulator-shutdown.sh")
    a=p.parse_args()
    for sig in (signal.SIGTERM,signal.SIGINT):run(a.script,sig)
