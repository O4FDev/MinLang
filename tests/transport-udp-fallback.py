#!/usr/bin/env python3
"""Real UDP blackhole before and after authenticated QUIC, then fresh TCP mTLS."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result
fixtures = module('tls_fallback_fixtures',ROOT/'tests/tls-local.py')
soak = module('quic_fallback_proxy',ROOT/'tests/quic-soak.py')
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def control(listener, proxy, stop, failures, events):
    listener.settimeout(.2)
    try:
        while not stop.is_set():
            try: connection, _ = listener.accept()
            except socket.timeout: continue
            with connection:
                connection.settimeout(3)
                if connection.recv(1) != b'B': raise ValueError('unexpected blackhole control')
                proxy.blocked.set()
                events.append(dict(event='UDP_BLOCKED',monotonic=time.monotonic()))
                connection.sendall(b'B')
            return
    except BaseException as error:
        if not stop.is_set(): failures.append(repr(error))

def case(kind, options, ca, native, quinn, go, directory):
    directory.mkdir()
    result = dict(mode=kind,status='NONPASS',commands={},helper_teardown={})
    owned=[]; opened=[]; proxy=None; listener=None; worker=None; stop=threading.Event()
    failures=[]; events=[]
    try:
        def start(name, command):
            errors=(directory/(name+'.stderr')).open('w'); opened.append(errors)
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=errors,text=True)
            owned.append((name,process)); result['commands'][name]=command
            return process
        quic=None
        if kind=='mid':
            quic=start('quinn',[str(quinn),'server',str(ca.path('root','der')),str(ca.path('server','der')),str(ca.path('server','pk8'))])
            line=soak.ready_line(quic,15)
            assert line.startswith('READY '),line
            udp_port=int(line.split()[1])
        else: udp_port=9
        proxy=soak.FaultProxy(udp_port,0,0)
        if kind=='initial': proxy.blocked.set()
        tcp=start('go',[str(go),'server',str(ca.path('root','pem')),str(ca.path('server','pem')),str(ca.path('server','key'))])
        ready=soak.ready_line(tcp,15); assert ready.startswith('READY '),ready
        tcp_port=int(ready.split()[1])
        control_port=0
        if kind=='mid':
            listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen(1)
            control_port=listener.getsockname()[1]
            worker=threading.Thread(target=control,args=(listener,proxy,stop,failures,events),daemon=True)
            worker.start()
        command=[str(native),kind,str(proxy.front.getsockname()[1]),str(tcp_port),str(control_port),
                 str(ca.path('client','der')),str(ca.path('client','pk8')),str(ca.path('root','der')),str(ca.path('server','der'))]
        result['commands']['native']=command
        began=time.monotonic()
        client=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        owned.append(('native',client))
        out, err=client.communicate(timeout=25)
        (directory/'native.stdout').write_text(out); (directory/'native.stderr').write_text(err)
        result.update(native_status=client.returncode,elapsed_seconds=time.monotonic()-began,
                      proxy=dict(forwarded=proxy.forwarded,dropped=proxy.dropped,blocked_dropped=proxy.blocked_dropped),
                      control_events=events,control_errors=failures)
        assert client.returncode==0 and not err,(client.returncode,out,err)
        lines=out.splitlines()
        assert any(line.startswith('TCP_NEEDED generation=1 elapsed_ms=') for line in lines),out
        assert 'TCP_AUTHENTICATED fresh' in lines and 'TCP_STREAMS_COMPLETE 16 bytes=524288' in lines,out
        assert proxy.blocked.is_set() and proxy.blocked_dropped>0,'no real UDP packet was blackholed'
        if kind=='mid':
            assert 'QUIC_ECHO authenticated' in lines and 'UDP_BLOCKED acknowledged' in lines,out
            assert lines.index('QUIC_ECHO authenticated')<lines.index('UDP_BLOCKED acknowledged')<lines.index('TCP_AUTHENTICATED fresh'),out
            assert len(events)==1 and not failures,(events,failures)
        else:
            assert 'QUIC_ECHO authenticated' not in lines and proxy.forwarded==0,out
        tcp_out,_=tcp.communicate(timeout=10)
        (directory/'go.stdout').write_text(tcp_out)
        assert tcp.returncode==0 and 'Go TLS/yamux: 16 authenticated multiplexed half-closed streams passed' in tcp_out,(tcp.returncode,tcp_out)
        result['helper_teardown']['go']=dict(status=tcp.returncode,method='normal exit')
        if quic is not None:
            # The authenticated QUIC peer deliberately remains behind the
            # blackhole. Do not restore UDP or retain abandoned Minyar keys
            # merely to deliver its close. This uninstrumented oracle gets
            # owned SIGTERM only after normal native and TCP payload proof.
            assert quic.poll() is None,'QUIC oracle exited before expected cleanup'
            quic.terminate(); quic_out,_=quic.communicate(timeout=5)
            (directory/'quinn.stdout').write_text(quic_out)
            assert quic.returncode==-signal.SIGTERM,quic.returncode
            result['helper_teardown']['quinn']=dict(status=quic.returncode,method='owned SIGTERM after native/TCP proof',normal_exit_leak_claim=False)
        for opened_file in opened: opened_file.flush()
        assert not (directory/'go.stderr').read_text(),'Go oracle diagnostics'
        if quic is not None: assert not (directory/'quinn.stderr').read_text(),'Quinn oracle diagnostics'
        result['status']=0
        print('GREEN '+json.dumps(result),flush=True)
        return result
    except BaseException as error:
        result['failure']=repr(error)
        raise
    finally:
        stop.set()
        if worker: worker.join(1)
        if listener: listener.close()
        if proxy: proxy.close()
        for name, process in owned:
            if process.poll() is None:
                process.terminate()
                try: process.communicate(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.communicate()
                result['helper_teardown'].setdefault(name,dict(status=process.returncode,method='failure cleanup'))
            if process.stdout: process.stdout.close()
        for opened_file in opened: opened_file.close()
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize',action='store_true')
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--peer-binary',type=Path)
    parser.add_argument('--go-binary',type=Path)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--mode',choices=['initial','mid','both'],default='both')
    options=parser.parse_args()
    for binary in (options.binary,options.peer_binary,options.go_binary):
        if binary is not None and not binary.is_file(): parser.error('prebuilt binaries must be files')
    options.evidence.mkdir(parents=True,exist_ok=True)
    if any(options.evidence.iterdir()): parser.error('evidence directory must be empty')
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):
            os.environ[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        os.environ['ASAN_OPTIONS']='detect_leaks=1'; os.environ['UBSAN_OPTIONS']='halt_on_error=1'
    native=options.binary.resolve() if options.binary else options.evidence.resolve()/'native'
    quinn=options.peer_binary.resolve() if options.peer_binary else ROOT/'build/interop-quinn/release/minyar-quinn-interop'
    go=options.go_binary.resolve() if options.go_binary else ROOT/'build/yamux-peer'
    builds=[]
    if options.peer_binary is None:
        command=['cargo','build','--release','--locked','--manifest-path',str(ROOT/'tests/interop/quinn/Cargo.toml'),
                 '--target-dir',str(ROOT/'build/interop-quinn'),'--bin','minyar-quinn-interop','-j1']
        subprocess.run(command,check=True,timeout=300,env=dict(os.environ,CARGO_BUILD_JOBS='1'))
        builds.append(command)
    if options.go_binary is None:
        go.parent.mkdir(parents=True,exist_ok=True)
        command=['go','build','-p=1','-mod=readonly','-o',str(go),'.']
        subprocess.run(command,cwd=ROOT/'tests/interop/yamux',check=True,timeout=120,env=dict(os.environ,GOMAXPROCS='1'))
        builds.append(command)
    if options.binary is None:
        fixtures.compile_program(ROOT/'tests/transport-udp-fallback.min',native)
        builds.append([str(ROOT/'minyar'),'--library',str(ROOT/'library'),str(ROOT/'tests/transport-udp-fallback.min'),'-o',str(native)])
    certificate_dir=options.evidence/'certificates'; certificate_dir.mkdir()
    ca=fixtures.Certificates(certificate_dir)
    ca.root('root'); ca.leaf('server','root'); ca.leaf('client','root',usage='clientAuth')
    metadata=dict(build_commands=builds,sanitized_requested=options.sanitize,
        binaries={name:dict(path=str(path),sha256=digest(path)) for name,path in [('native',native),('quinn',quinn),('go',go)]})
    (options.evidence/'inputs.json').write_text(json.dumps(metadata,indent=2)+'\n')
    cases=['initial','mid'] if options.mode=='both' else [options.mode]
    for kind in cases: case(kind,options,ca,native,quinn,go,options.evidence/kind)

if __name__=='__main__': main()
