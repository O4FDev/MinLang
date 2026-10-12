#!/usr/bin/env python3
"""Real mTLS grpcio -> Minyar edge -> independent signed-grant Go device."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import grpc
from peer_edge_support import Lab,load
peer=load('relay_schema','peer-grpc.py')
BANNER=bytes((0,255,128,1,13,10));TAIL=bytes((0,254,127,0))
def channel(lab,certificate='gateway'):
    credentials=grpc.ssl_channel_credentials(root_certificates=lab.certs.path('ca','pem').read_bytes(),private_key=lab.certs.path(certificate,'key').read_bytes(),certificate_chain=lab.certs.path(certificate,'pem').read_bytes())
    return grpc.secure_channel(f'localhost:{lab.gateway_port}',credentials)
def rpc(ch):
    return ch.stream_stream(peer.PATH,request_serializer=peer.Request.SerializeToString,response_deserializer=peer.Response.FromString)
def opened(token,conn,exit='exit-a'):
    return peer.Request(open=peer.Open(dial_grant=token,exit_id=exit,conn_id=conn))
def corrupt_signature(token):
    signing,encoded=token.rsplit(b'.',1)
    signature=bytearray(base64.urlsafe_b64decode(encoded+b'=='))
    signature[0]^=1
    return signing+b'.'+base64.urlsafe_b64encode(signature).rstrip(b'=')
def transfer(lab,r,conn,payload=b'',target='echo.example',timeout=4):
    token=lab.signed(conn,target_host=target);admitted=threading.Event()
    def outgoing():
        yield opened(token,conn)
        assert admitted.wait(timeout),'edge did not admit independently signed open'
        for at in range(0,len(payload),16384):yield peer.Request(data=payload[at:at+16384])
    call=r(outgoing(),timeout=timeout)
    first=next(call);assert first.WhichOneof('body')=='status' and first.status.code==0,first
    admitted.set();chunks=[]
    try:
        for message in call:chunks.append(message.data)
    except grpc.RpcError:
        print('TRANSFER_FAILURE',conn,'received',sum(map(len,chunks)),'chunks',list(map(len,chunks)),flush=True);raise
    actual=b''.join(chunks)
    assert actual==BANNER+payload+TAIL,(conn,len(actual),len(payload),actual[:30])
    assert call.code()==grpc.StatusCode.OK
    return hashlib.sha256(token).hexdigest()
def run(lab, rounds=1024):
    lab.env['MINYAR_PEER_DEVICE_HEARTBEAT_MS']='15000'
    proc,out=lab.start_device()
    with channel(lab) as ch:
        r=rpc(ch);payload=bytes(range(256))*1024+b'\x00\xffTAIL'
        digest=transfer(lab,r,'valid-1',payload)
        line=lab.device_event(out,'START valid-1 ')
        assert line.split()[-1]==digest,'edge changed independently signed token'
        lab.device_event(out,'CLOSED valid-1')
        print('GREEN real mTLS grpcio signed START/status + 262150 binary bytes both directions + request half-close/tail',flush=True)
        # Replaying a still-valid conn_id is rejected by the edge, before START.
        for conn,token,exit,expected in [
            ('valid-1',lab.signed('valid-1'),'exit-a',1),
            ('wrong-exit',lab.signed('wrong-exit',exit_id='exit-b'),'exit-a',1),
            ('wrong-conn',lab.signed('different'),'exit-a',1),
            ('expired',lab.signed('expired',iat=int(time.time())-40,exp=int(time.time())-10),'exit-a',1),
            ('wrong-key',corrupt_signature(lab.signed('wrong-key')), 'exit-a',1),
            ('offline',lab.signed('offline',exit_id='exit-b'),'exit-b',2),
        ]:
            request_done=threading.Event()
            def still_open():
                yield opened(token,conn,exit)
                request_done.wait(3)
            call=r(still_open(),timeout=3)
            try:
                first=next(call)
                assert first.WhichOneof('body')=='status' and first.status.code==expected,(conn,first)
                assert list(call)==[] and call.code()==grpc.StatusCode.OK
            finally:request_done.set()
        # Signed requests are independently rejected by device destination policy.
        call=r(iter([opened(lab.signed('denied',target_host='deny.example'),'denied')]),timeout=3)
        assert next(call).status.code==3 and list(call)==[]
        # Device DATA before status cannot become an accepted gateway relay.
        call=r(iter([opened(lab.signed('device-early',target_host='early.example'),'device-early')]),timeout=3)
        try:
            first=next(call);assert first.WhichOneof('body')=='status' and first.status.code!=0
        except grpc.RpcError:pass
        # Cancel an established request while preserving the gateway channel.
        stopped=threading.Event()
        def held():
            yield opened(lab.signed('cancel-1'),'cancel-1');stopped.wait(5)
        call=r(held(),timeout=6);assert next(call).status.code==0
        call.cancel();stopped.set();lab.device_event(out,'CANCELLED cancel-1')
        transfer(lab,r,'after-cancel',b'after\x00cancel')
        # Pause races Select: admission checks authoritative current heartbeat.
        lab.heartbeat(proc,paused=True)
        from peer_edge_support import admission
        admission.eventually(lambda:json.loads(lab.client.command('GET','peer:live:{exit-a}'))['capacity_weight']==0)
        call=r(iter([opened(lab.signed('paused'),'paused')]),timeout=3)
        assert next(call).status.code==3 and list(call)==[]
        lab.heartbeat(proc,paused=False)
        admission.eventually(lambda:json.loads(lab.client.command('GET','peer:live:{exit-a}'))['capacity_weight']>0)
        transfer(lab,r,'resumed',b'resumed')
        # Immutable deadline is received with headers, before delayed OPEN admission.
        call=r(iter([opened(lab.signed('deadline',target_host='delay.example'),'deadline')]),timeout=.2)
        try:list(call);raise AssertionError('late device admission exceeded deadline')
        except grpc.RpcError as error:assert error.code()==grpc.StatusCode.DEADLINE_EXCEEDED
        time.sleep(.9)
        transfer(lab,r,'after-deadline',b'deadline survived')
        # More completed RPCs than either physical transport context cap.
        # Stable channel/device connections, fresh authenticated IDs, exact
        # binary responses and a healthy final request expose lifetime debt.
        for index in range(rounds):
            payload=bytes((0,255,index%251))+index.to_bytes(4,'big')+bytes([index%251])*(index%127)
            transfer(lab,r,f'churn-{index}',payload,timeout=5)
        lab.device_event(out,'HEARTBEAT',timeout=16)
        transfer(lab,r,'after-churn',bytes(range(256))*8192+b'\x00\xfflarge-tail',timeout=15)
        print(f'GREEN {rounds} sequential signed RPCs on persistent gateway/device connections and 2 MiB backpressured binary echo',flush=True)
    with channel(lab,'unregistered') as ch:
        call=rpc(ch)(iter([opened(lab.signed('untrusted'),'untrusted')]),timeout=1)
        try:list(call);raise AssertionError('unregistered mTLS leaf admitted')
        except grpc.RpcError:pass
    # Independent agent verifier negative controls: wrong/replayed/expired grants and unsigned echoes.
    token=lab.signed('device-verify');claims=json.loads(__import__('base64').urlsafe_b64decode(token.split(b'.')[1]+b'=='))
    start=dict(dial_grant_bytes=token.decode(),exit_id='exit-a',conn_id='device-verify',target_host=claims['target_host'],port=443,expires=claims['exp'])
    def verify(value,accepted):
        path=lab.directory/'start.json';path.write_text(json.dumps(value))
        result=subprocess.run([str(lab.device),'--verify-start',str(path),'exit-a'],capture_output=True,text=True,timeout=3)
        assert (result.returncode==0)==accepted,(value,result.stdout,result.stderr)
        if accepted:assert 'REPLAY_REJECTED' in result.stdout
    verify(start,True)
    for field,bad in [('exit_id','exit-b'),('conn_id','other'),('target_host','spoof.example'),('port',80),('expires',claims['exp']+1),('dial_grant_bytes',lab.signed('other').decode())]:
        verify(dict(start,**{field:bad}),False)
    expired=lab.signed('device-verify',iat=int(time.time())-40,exp=int(time.time())-10)
    verify(dict(start,dial_grant_bytes=expired.decode(),expires=int(time.time())-10),False)
    print('GREEN edge grant/replay/offline/pause/mTLS policy, independent device signature/echo/replay, cancel and deadline recovery',flush=True)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--binary',type=Path);parser.add_argument('--sanitize',action='store_true');parser.add_argument('--evidence',type=Path);parser.add_argument('--rounds',type=int,default=1024);args=parser.parse_args()
    assert 1<=args.rounds<=4096
    with tempfile.TemporaryDirectory(prefix='minyar-edge-relay-') as folder:
        directory=args.evidence or Path(folder);lab=None
        try:
            lab=Lab(directory,args.binary,args.sanitize,duration=90000);run(lab,args.rounds)
            lines=lab.completed(timeout=95)
            counts=dict(part.split('=') for part in next(line for line in lines if line.startswith('EDGE_COUNTS ')).split()[1:])
            assert int(counts['calls_opened'])==int(counts['calls_released']),counts
            assert int(counts['retained_relays'])==0,counts
            assert int(counts['relays_retired'])>=args.rounds+6,counts
            print('GREEN exact call release and zero retained relay contexts',counts,flush=True)
        finally:
            if lab:lab.close()
if __name__=='__main__':main()
