"""Independent peer-edge lab; never runs builds on a developer workstation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tests'/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
admission=load('edge_admission','peer-edge.py')
auth=load('edge_signing','peer-auth.py')
def environment(sanitize=False):
    env=dict(os.environ,MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG','clang'),GOMAXPROCS='2',GOFLAGS='-p=2')
    if sanitize:
        for key in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):
            env[key]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS']='detect_leaks=1';env['UBSAN_OPTIONS']='halt_on_error=1'
    return env
def rss(pid):
    text=Path(f'/proc/{pid}/status').read_text()
    return int(next(line.split()[1] for line in text.splitlines() if line.startswith('VmRSS:')))
class Lab:
    def __init__(self,directory,binary=None,sanitize=False,duration=20000,maximum=128,sanitizer_quarantine=None):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.env=environment(sanitize)
        if sanitize and sanitizer_quarantine is not None:
            # A bounded freed-object quarantine leaves temporal checks enabled
            # while allowing the unchanged live RSS ceiling to be measured.
            assert sanitizer_quarantine==1
            self.env['ASAN_OPTIONS']='detect_leaks=1:quarantine_size_mb=1:thread_local_quarantine_size_kb=64'
        self.devices=[];self.device_outputs=[];self.events=[]
        self.edge=None;self.redis=None;self.client=None
        self.binary=Path(binary) if binary else self.directory/'edge'
        if not binary:
            subprocess.run([str(ROOT/'minyar'),str(ROOT/'examples/peer-edge.min'),'-o',str(self.binary)],env=self.env,check=True,timeout=240)
        self.device=self.directory/'device'
        subprocess.run(['go','build','-trimpath','-o',str(self.device),'.'],cwd=ROOT/'tests/interop/peeredge',env=self.env,check=True,timeout=120)
        self.certs=admission.fixtures.Certificates(self.directory)
        self.certs.root('ca');self.certs.leaf('server','ca',ec=True)
        self.certs.leaf('device','ca',san='URI:hearth://device/device-a',usage='clientAuth',ec=True)
        self.certs.leaf('gateway','ca',usage='clientAuth',ec=True)
        self.certs.leaf('unregistered','ca',usage='clientAuth',ec=True)
        self.registry=self.directory/'registry.ndjson'
        self.registry.write_text(json.dumps(dict(role='device',device_id='device-a',exit_id='exit-a',revoked=False,paused=False,quarantined=False,max_concurrent=8))+'\n'+json.dumps(dict(role='gateway',sha256=hashlib.sha256(self.certs.path('gateway','der').read_bytes()).hexdigest()))+'\n')
        (self.directory/'jwks.json').write_bytes(auth.jwks())
        if auth.KEY is None: auth.KEY=auth.OpenSSLSigner(self.directory)
        with socket.socket() as reserved:reserved.bind(('127.0.0.1',0));self.redis_port=reserved.getsockname()[1]
        # The parent fd soak occupies ephemeral TCP tuples. Reserve a distinct
        # TCP+UDP port below that range, because the device shares both protocols.
        import random
        for attempt in range(100):
            selected=random.SystemRandom().randrange(18000,28000)
            try:
                with socket.socket() as tcp,socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as udp:
                    tcp.bind(('127.0.0.1',selected));udp.bind(('127.0.0.1',selected))
                self.listen_port=selected;break
            except OSError:continue
        else:raise AssertionError('no independent TCP/UDP lab port')
        self.redis=subprocess.Popen(['redis-server','--bind','127.0.0.1','--port',str(self.redis_port),'--save','','--appendonly','no','--dir',str(self.directory)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        def connect():
            try:return admission.Redis(self.redis_port)
            except OSError:return None
        self.client=admission.eventually(connect)
        config=dict(host='127.0.0.1',device_port=self.listen_port,gateway_port=0,redis_host='127.0.0.1',redis_port=self.redis_port,edge_instance='localhost:0',edge_region='eu-west',max_connections=maximum,certificate=str(self.certs.path('server','der')),private_key=str(self.certs.path('server','pk8')),device_roots=str(self.certs.path('ca','der')),gateway_roots=str(self.certs.path('ca','der')),registry=str(self.registry),jwks=str(self.directory/'jwks.json'))
        (self.directory/'edge.json').write_text(json.dumps(config))
        self.stderr=open(self.directory/'edge.stderr','wb')
        self.edge=subprocess.Popen([str(self.binary),str(self.directory/'edge.json'),str(duration)],env=self.env,stdout=subprocess.PIPE,stderr=self.stderr)
        self.output=admission.lines(self.edge);line=self.output.get(timeout=15)
        assert line and line.startswith('READY '),(line,self.diagnostic())
        self.udp_port,self.device_port,self.gateway_port=map(int,line.split()[1:])
        self.health=dict(in_flight=0,max_concurrent=8,paused=False,policy_hash='a'*64,public_ip='203.0.113.2',asn=64500,country='GB')
        (self.directory/'source.json').write_text(json.dumps(dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_sha256=hashlib.sha256((ROOT/'library/peeredge.min').read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(self.binary.read_bytes()).hexdigest(),start=time.time(),pid=self.edge.pid,asan_options=self.env.get('ASAN_OPTIONS')),indent=2))
    def diagnostic(self):
        if self.stderr and not self.stderr.closed:self.stderr.flush()
        return (self.directory/'edge.stderr').read_text()
    def start_device(self):
        proc=subprocess.Popen([str(self.device),str(self.device_port),str(self.certs.path('ca','pem')),str(self.certs.path('device','pem')),str(self.certs.path('device','key')),'device-a','exit-a',json.dumps(self.health)],env=self.env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.devices.append(proc);out=admission.lines(proc);self.device_outputs.append(out)
        assert out.get(timeout=10)=='READY'
        admission.eventually(lambda:self.client.command('GET','peer:live:{exit-a}'))
        return proc,out
    def heartbeat(self,proc,**changes):
        self.health.update(changes);proc.stdin.write(json.dumps(self.health).encode()+b'\n');proc.stdin.flush()
    def signed(self,conn,**changes):
        now=int(time.time());claims=dict(iss='proxy-gateway',exit_id='exit-a',conn_id=conn,target_host='echo.example',port=443,iat=now,exp=now+30)
        claims.update(changes);return auth.token(claims=claims)
    def device_event(self,out,prefix,timeout=5):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            line=out.get(timeout=max(.01,end-time.monotonic()));self.events.append(line)
            if line is None:raise AssertionError('device exited')
            if line.startswith(prefix):return line
        raise AssertionError(prefix)
    def completed(self,timeout=30):
        self.edge.wait(timeout=timeout);self.stderr.close()
        lines=[]
        while True:
            line=self.output.get(timeout=3)
            if line is None:break
            lines.append(line)
        (self.directory/'edge.stdout').write_text('\n'.join(lines)+'\n')
        assert self.edge.returncode==0,(self.edge.returncode,self.diagnostic())
        assert self.diagnostic()=='',self.diagnostic()
        return lines
    def close(self):
        for proc in self.devices:
            if proc.poll() is None:proc.terminate()
            proc.communicate(timeout=5)
        if self.edge and self.edge.poll() is None:self.edge.kill();self.edge.wait()
        if self.edge:
            pending=[]
            while True:
                try:line=self.output.get(timeout=.1)
                except queue.Empty:break
                if line is None:break
                pending.append(line)
            if pending:(self.directory/'edge.partial.stdout').write_text('\n'.join(pending)+'\n')
        for at,out in enumerate(self.device_outputs):
            events=[]
            while True:
                try:line=out.get_nowait()
                except queue.Empty:break
                events.append(line)
            (self.directory/f'device-{at}.events.json').write_text(json.dumps(events))
        if self.client:self.client.close()
        if self.redis:
            self.redis.terminate();self.redis.communicate(timeout=5)
        if self.stderr and not self.stderr.closed:self.stderr.close()
