#!/usr/bin/env python3
"""2048 RPCs plus cancellation on one actual independent grpcio HTTP/2 connection."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import grpc
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('independent_peer',ROOT/'tests/peer-grpc.py'); peer=importlib.util.module_from_spec(spec); spec.loader.exec_module(peer)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--sanitize',action='store_true'); options=parser.parse_args()
    env=dict(os.environ,MINYAR_CLANG=os.environ.get('MINYAR_TEST_CLANG','clang'))
    if options.sanitize:
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'): env[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        env['ASAN_OPTIONS']='detect_leaks=1'; env['UBSAN_OPTIONS']='halt_on_error=1'
    with tempfile.TemporaryDirectory(prefix='minyar-grpc-churn-') as folder:
        binary=Path(folder)/'serve'; subprocess.run([str(ROOT/'minyar'),str(ROOT/'tests/peer-grpc-churn-serve.min'),'-o',str(binary)],env=env,check=True,timeout=240)
        process=subprocess.Popen([str(binary)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            line=process.stdout.readline().strip(); assert line.isdecimal(),line
            with grpc.insecure_channel('127.0.0.1:'+line) as channel:
                rpc=channel.stream_stream(peer.PATH,request_serializer=peer.Request.SerializeToString,response_deserializer=peer.Response.FromString)
                def transfer(index):
                    size=(index*131)%4097
                    if index%257==0: size=65536
                    payload=(bytes(range(256))*257)[:size]+str(index).encode(); ready=threading.Event()
                    def outgoing():
                        yield peer.opened('churn-'+str(index)); assert ready.wait(10)
                        for at in range(0,len(payload),65536): yield peer.Request(data=payload[at:at+65536])
                    call=rpc(outgoing(),timeout=15,metadata=(('x-churn-key',str(index%71)),))
                    first=next(call); assert first.WhichOneof('body')=='status' and first.status.code==0
                    ready.set(); actual=b''.join(item.data for item in call)
                    assert actual==payload and call.code()==grpc.StatusCode.OK,(index,len(actual),len(payload))
                for index in range(1024): transfer(index)
                with ThreadPoolExecutor(max_workers=32) as pool: list(pool.map(transfer,range(1024,2048)))
                for index in range(64):
                    stopped=threading.Event()
                    def stalled():
                        yield peer.opened('cancel-'+str(index)); stopped.wait(3)
                    call=rpc(stalled(),timeout=5); assert next(call).status.code==0
                    assert call.cancel(); stopped.set()
                transfer(2048) # Cancellation must preserve the same connection, compression and flow state.
            process.wait(timeout=15)
            diagnostic=process.stderr.read(); assert process.returncode==0 and diagnostic=='',(process.returncode,diagnostic)
            counts=process.stdout.read().strip().split(); assert counts[0]=='COUNTS',counts
            opened,closed,released,max_calls,max_streams,max_table,final_calls,final_streams=map(int,counts[1:])
            assert opened==closed==released==2113,(opened,closed,released)
            assert 1<=max_calls<=64 and 1<=max_streams<=64 and max_table<=4096
            assert final_calls==final_streams==0,counts
            print(f'gRPC churn: 1024 serial + 1024 mixed concurrent + 64 cancellations + fresh RPC on one connection; retained maxima calls={max_calls} streams={max_streams} table={max_table} bytes; final records=0')
        finally:
            if process.poll() is None: process.kill(); process.wait()
            diagnostic=process.stderr.read()
            if diagnostic: print('Native churn diagnostics:',diagnostic)
if __name__=='__main__': main()
