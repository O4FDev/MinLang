#!/usr/bin/env python3
"""Independent cancellation and late-closed-frame controls for persistent HTTP2."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import h2.connection
import h2.config
from hpack import Encoder
ROOT = Path(__file__).resolve().parents[1]
FIELDS = [(':method', 'POST'), (':scheme', 'https'), (':authority', 'peer.test'), (':path', '/PeerEdgeDial/OpenExitStream')]
def frame(kind, stream=0, body=b'', flags=0):
    return len(body).to_bytes(3, 'big') + bytes((kind, flags)) + struct.pack('>I', stream) + body
def frames(raw):
    result=[]
    while raw:
        assert len(raw)>=9, raw.hex()
        size=int.from_bytes(raw[:3],'big'); assert len(raw)>=9+size, (size,len(raw))
        result.append((raw[3], int.from_bytes(raw[5:9],'big') & 0x7fffffff, raw[9:9+size], raw[4]))
        raw=raw[9+size:]
    return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--red',action='store_true'); parser.add_argument('--sanitize',action='store_true'); parser.add_argument('--library',type=Path); options=parser.parse_args()
    env=dict(os.environ, MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG','clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'): env[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS']='detect_leaks=1'; env['UBSAN_OPTIONS']='halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-h2-churn-') as folder:
        folder=Path(folder); binary=folder/'probe'; args=[str(ROOT/'minyar')]
        if options.library: args+=['--library',str(options.library)]
        subprocess.run(args+[str(ROOT/'tests/http2-churn.min'),'-o',str(binary)],env=env,check=True,timeout=240)
        peer=h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True)); peer.initiate_connection(); peer.send_headers(1,FIELDS,end_stream=True)
        initial=folder/'initial'; late=folder/'late'; output=folder/'output'; initial.write_bytes(peer.data_to_send())
        def run(mode, raw):
            late.write_bytes(raw)
            result=subprocess.run([str(binary),str(initial),str(late),mode,str(output)],env=env,capture_output=True,text=True,timeout=60)
            assert result.returncode==0 and result.stderr=='',result.stderr
            return result.stdout, frames(output.read_bytes())
        result, cancelled=run('cancel',frame(3,1,struct.pack('>I',8)))
        result2, closed=run('late',frame(8,1,struct.pack('>I',0)))
        if options.red:
            assert any(kind==0 and stream==1 for kind,stream,_,_ in cancelled)
            assert any(kind==3 and stream==1 for kind,stream,_,_ in closed)
            print('RED: reset forwards queued DATA; late closed WINDOW_UPDATE incorrectly emits RST_STREAM')
            return
        assert result=='OK\n' and not any(stream==1 and kind in (0,1) for kind,stream,_,_ in cancelled),[(k,s,len(b)) for k,s,b,_ in cancelled]
        assert result2=='OK\n' and not any(kind==3 for kind,_,_,_ in closed),[(k,s,len(b)) for k,s,b,_ in closed]
        # A partially drained frame must finish; every later queued DATA/trailer is dropped.
        result, partial=run('partial',frame(3,1,struct.pack('>I',8)))
        payload=[body for kind,stream,body,_ in partial if kind==0 and stream==1]
        assert result=='OK\n' and len(payload)==1 and payload[0]==bytes(range(256))*64, [len(p) for p in payload]
        # All late DATA/HEADERS/WINDOW_UPDATE/RST process minimally and do not poison the connection.
        encoder=Encoder(); encoder.encode(FIELDS)
        dynamic=FIELDS+[('x-late','new-dynamic')]
        raw=frame(8,1,struct.pack('>I',0x7fffffff))+frame(3,1,struct.pack('>I',8))+frame(0,1,b'late')+frame(1,1,encoder.encode(dynamic),4)+frame(1,3,encoder.encode(dynamic),5)
        result, encoded=run('late',raw)
        assert result=='OK\nREOPEN new-dynamic\n' and not any(kind in (3,7) for kind,_,_,_ in encoded),result
        # Removed unsent DATA restores exactly the connection credit it reserved.
        encoder=Encoder(); encoder.encode(FIELDS)
        result, encoded=run('credit',frame(3,1,struct.pack('>I',8))+frame(1,3,encoder.encode(dynamic),5))
        assert result=='OK\nREOPEN new-dynamic\n'
        assert sum(len(body) for kind,stream,body,_ in encoded if kind==0 and stream==3)==40000
        print('HTTP2 churn: queued reset suppression, exact partial-frame completion and minimal late closed frames passed')
if __name__=='__main__': main()
