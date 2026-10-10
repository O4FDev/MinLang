#!/usr/bin/env python3
"""Independent envelopes verify checked closure notifications and drain-before-retire."""
import argparse
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import h2.events
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('independent_peer',ROOT/'tests/peer-grpc.py'); peer=importlib.util.module_from_spec(spec); spec.loader.exec_module(peer)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--sanitize',action='store_true'); options=parser.parse_args()
    env=dict(os.environ,MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG','clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'): env[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS']='detect_leaks=1'; env['UBSAN_OPTIONS']='halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-grpc-retire-') as folder:
        folder=Path(folder); binary=folder/'probe'; subprocess.run([str(ROOT/'minyar'),str(ROOT/'tests/peer-grpc-retire.min'),'-o',str(binary)],env=env,check=True,timeout=240)
        initial=folder/'initial'; reset=folder/'reset'; output=folder/'output'; reset.write_bytes(b'\0\0\4\3\0'+struct.pack('>II',1,8))
        for mode in ('normal','deadline','cancel','trap'):
            client=peer.client('500m' if mode=='deadline' else None); client.send_data(1,peer.envelope(peer.opened()),end_stream=mode=='normal'); initial.write_bytes(client.data_to_send())
            result=subprocess.run([str(binary),str(initial),str(output),mode,str(reset)],env=env,capture_output=True,text=True,timeout=60)
            if mode=='trap':
                assert result.returncode!=0 and 'cannot read absent gRPC closed notification' in result.stderr
                continue
            assert result.returncode==0 and result.stdout=='RETIRED\n' and result.stderr=='',(mode,result.stdout,result.stderr)
            events=client.receive_data(output.read_bytes())
            if mode=='normal':
                messages=peer.messages(events); assert messages[0].status.code==0 and messages[1].data==b'queued forwarding bytes'
                assert any(isinstance(e,h2.events.TrailersReceived) and ('grpc-status','0') in e.headers for e in events)
            elif mode=='deadline':
                assert not any(isinstance(e,h2.events.DataReceived) for e in events),'deadline forwarded queued data'
                assert any(isinstance(e,h2.events.TrailersReceived) and ('grpc-status','4') in e.headers for e in events)
            else:
                assert not any(isinstance(e,h2.events.DataReceived) for e in events),'cancel forwarded queued data'
        print('gRPC retirement: active/rejected/partial-drain controls, once-only checked normal/cancel/deadline identity, no queued forwarding after cancel/deadline, final records zero passed')
if __name__=='__main__': main()
