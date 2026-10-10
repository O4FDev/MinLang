#!/usr/bin/env python3
"""Minyar own TLS/yamux vs pinned independent Go TLS/HashiCorp yamux."""
import argparse,importlib.util,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tls_tests',ROOT/'tests/tls-local.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
def main():
    p=argparse.ArgumentParser();p.add_argument('--sanitize',action='store_true');p.add_argument('--peer-binary',type=Path);o=p.parse_args()
    if o.sanitize:
        for n in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):os.environ[n]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    with tempfile.TemporaryDirectory(prefix='minyar-yamux-oracle-') as d:
        ca=fixtures.Certificates(d);ca.root('root');ca.leaf('server','root');ca.leaf('client','root',usage='clientAuth')
        go=o.peer_binary.resolve() if o.peer_binary else Path(d)/'go-peer';native=Path(d)/'minyar-peer'
        if not o.peer_binary:subprocess.run(['go','build','-mod=readonly','-o',str(go),'.'],cwd=ROOT/'tests/interop/yamux',check=True,timeout=120)
        fixtures.compile_program(ROOT/'tests/transport-tcp.min',native)
        for kind in ('minyar','go'):
            cmd=[str(native),'server','0',str(ca.path('server','der')),str(ca.path('server','pk8')),str(ca.path('root','der'))] if kind=='minyar' else [str(go),'server',str(ca.path('root','pem')),str(ca.path('server','pem')),str(ca.path('server','key'))]
            server=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                ready=server.stdout.readline().strip();assert ready.startswith('READY '),ready;port=ready.split()[1]
                cmd=[str(go),port,str(ca.path('root','pem')),str(ca.path('client','pem')),str(ca.path('client','key'))] if kind=='minyar' else [str(native),'client',port,str(ca.path('client','der')),str(ca.path('client','pk8')),str(ca.path('root','der'))]
                client=subprocess.run(cmd,capture_output=True,text=True,timeout=20);out,err=server.communicate(timeout=20)
                assert client.returncode==0 and server.returncode==0,(kind,client.returncode,client.stdout,client.stderr,server.returncode,out,err)
                print(client.stdout,end='');print(out,end='')
            finally:
                if server.poll() is None:server.kill();server.communicate()
if __name__=='__main__':main()
