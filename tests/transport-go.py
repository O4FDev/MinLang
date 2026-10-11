#!/usr/bin/env python3
"""Minyar own TLS/yamux vs pinned independent Go TLS/HashiCorp yamux."""
import argparse,hashlib,importlib.util,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tls_tests',ROOT/'tests/tls-local.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
def main():
    p=argparse.ArgumentParser();p.add_argument('--fin-schedule',action='store_true',help='preempt pinned Go peer after FIN state change before DATA copying');p.add_argument('--sanitize',action='store_true');p.add_argument('--peer-binary',type=Path);p.add_argument('--streams',type=int,default=0);o=p.parse_args()
    if o.streams and not 1<=o.streams<=4096:p.error('sequential stream count must be 1..4096')
    if o.fin_schedule and o.peer_binary:p.error('--fin-schedule builds its own pinned independent peer')
    if o.sanitize:
        for n in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):os.environ[n]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
    with tempfile.TemporaryDirectory(prefix='minyar-yamux-oracle-') as d:
        ca=fixtures.Certificates(d);ca.root('root');ca.leaf('server','root');ca.leaf('client','root',usage='clientAuth')
        go=o.peer_binary.resolve() if o.peer_binary else Path(d)/'go-peer';native=Path(d)/'minyar-peer'
        if not o.peer_binary:
            arguments=['go','build','-p=1','-mod=readonly']
            environment=dict(os.environ,GOMAXPROCS='2')
            if o.fin_schedule:
                module=json.loads(subprocess.check_output(['go','list','-m','-json','github.com/hashicorp/yamux'],cwd=ROOT/'tests/interop/yamux',env=environment,text=True,timeout=30))
                assert module['Version']=='v0.1.2',module['Version']
                source=Path(module['Dir'])/'stream.go';original=source.read_text()
                anchor='\t// Check that our recv window is not exceeded'
                assert original.count(anchor)==1,'pinned peer scheduling anchor changed'
                # A legal scheduler pause exposes FIN before the receive lock is
                # acquired. The peer's parser, state machine and payload oracle
                # remain intact; ordinary unmodified peer runs are separate.
                scheduled=original.replace(anchor,'\ttime.Sleep(25 * time.Millisecond)\n\n'+anchor)
                override=Path(d)/'stream-scheduled.go';override.write_text(scheduled)
                overlay=Path(d)/'go-overlay.json';overlay.write_text(json.dumps({'Replace':{str(source):str(override)}}))
                arguments.append('-overlay='+str(overlay))
                print('Go FIN scheduler original='+hashlib.sha256(source.read_bytes()).hexdigest()+' scheduled='+hashlib.sha256(override.read_bytes()).hexdigest(),flush=True)
            subprocess.run([*arguments,'-o',str(go),'.'],cwd=ROOT/'tests/interop/yamux',env=environment,check=True,timeout=120)
        fixtures.compile_program(ROOT/('tests/transport-churn.min' if o.streams else 'tests/transport-tcp.min'),native)
        for kind in ('minyar','go'):
            cmd=[str(native),'server','0',str(ca.path('server','der')),str(ca.path('server','pk8')),str(ca.path('root','der'))] if kind=='minyar' else [str(go),'server',str(ca.path('root','pem')),str(ca.path('server','pem')),str(ca.path('server','key'))]
            if o.streams:cmd.append(str(o.streams))
            server=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                ready=server.stdout.readline().strip();assert ready.startswith('READY '),ready;port=ready.split()[1]
                cmd=[str(go),port,str(ca.path('root','pem')),str(ca.path('client','pem')),str(ca.path('client','key'))] if kind=='minyar' else [str(native),'client',port,str(ca.path('client','der')),str(ca.path('client','pk8')),str(ca.path('root','der'))]
                if o.streams:cmd.append(str(o.streams))
                client=subprocess.run(cmd,capture_output=True,text=True,timeout=90 if o.streams else 20);out,err=server.communicate(timeout=90 if o.streams else 20)
                assert client.returncode==0 and server.returncode==0,(kind,client.returncode,client.stdout,client.stderr,server.returncode,out,err)
                print(client.stdout,end='');print(out,end='')
            finally:
                if server.poll() is None:server.kill();server.communicate()
if __name__=='__main__':main()
