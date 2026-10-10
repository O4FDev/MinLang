#!/usr/bin/env python3
"""Sustained Minyar mTLS HTTP keep-alive process against independent OpenSSL.
Adversarial peers delay, close, send oversized responses or malformed HTTP.
"""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import ssl
import subprocess
import threading
import time
from soak_observer import observe, memory_summary, require_remote_lab

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seconds',type=int,default=7200)
parser.add_argument('--connections',type=int,default=64)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--sanitize',action='store_true')
args=parser.parse_args()
require_remote_lab()
if not 1<=args.seconds<=86400 or not 1<=args.connections<=512: parser.error('invalid duration or connection count')
args.output.mkdir(parents=True,exist_ok=False)
temp=args.output.resolve()
spec=importlib.util.spec_from_file_location('tls_fixtures',ROOT/'tests/tls-local.py')
fixtures_module=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures_module)
fixtures=fixtures_module.Certificates(temp)
fixtures.root('root'); fixtures.leaf('server','root'); fixtures.leaf('client','root',usage='clientAuth')
context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_3
context.load_cert_chain(fixtures.path('server','pem'),fixtures.path('server','key'))
context.load_verify_locations(fixtures.path('root','pem')); context.verify_mode=ssl.CERT_REQUIRED
context.set_alpn_protocols(['http/1.1'])
ready=threading.Event(); peers=set(); stats={'connections':0,'responses':0,'malformed':0,'oversized':0,'closed':0,'slow':0}; unexpected=[]
async def peer(reader,writer):
    task=asyncio.current_task(); peers.add(task)
    stats['connections']+=1; identity=stats['connections']; requests=0
    try:
        assert writer.get_extra_info('peercert'), 'peer lacked mutual TLS identity'
        while True:
            request=await reader.readuntil(b'\r\n\r\n')
            assert request.startswith(b'GET /heartbeat HTTP/1.1\r\n'), request[:80]
            requests+=1
            if requests==1 and identity%19==0:
                stats['oversized']+=1; writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 70000\r\n\r\n'+b'x'*70000)
            elif requests==1 and identity%11==0:
                stats['malformed']+=1; writer.write(b'HTTP/1.1 nope\r\nMalformed\r\n\r\n'+b'?'*256)
            elif requests==7:
                stats['closed']+=1; break
            else:
                if requests==2 and identity%13==0: stats['slow']+=1; await asyncio.sleep(1)
                response=b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok'
                # Deliberate application fragmentation, with binary TLS records
                # generated entirely by the independent OpenSSL server.
                writer.write(response[:7]); await writer.drain()
                writer.write(response[7:]); stats['responses']+=1
            await writer.drain()
    except (asyncio.IncompleteReadError,ConnectionError,ssl.SSLError,asyncio.CancelledError): pass
    except BaseException as error: unexpected.append(repr(error))
    finally:
        writer.close()
        try: await writer.wait_closed()
        except (ConnectionError,ssl.SSLError): pass
        peers.discard(task)
loop=asyncio.new_event_loop(); server_holder=[]
def serve():
    asyncio.set_event_loop(loop)
    server=loop.run_until_complete(asyncio.start_server(peer,'127.0.0.1',0,ssl=context,ssl_handshake_timeout=10))
    server_holder.append(server); ready.set(); loop.run_forever(); loop.close()
thread=threading.Thread(target=serve,daemon=True); thread.start(); assert ready.wait(15)
port=server_holder[0].sockets[0].getsockname()[1]
environment=os.environ.copy()
if args.sanitize:
    flags='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer'
    for key in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'): environment[key]=flags
    environment['ASAN_OPTIONS']='detect_leaks=1'; environment['UBSAN_OPTIONS']='halt_on_error=1'
program=temp/'client'
compiled=subprocess.run([ROOT/'minyar','--library',ROOT/'library',ROOT/'tests/tls-soak.min','-o',program],capture_output=True,text=True,env=environment)
assert compiled.returncode==0,compiled.stderr
started=time.time(); samples=[]; complete=False; failure=None
with (temp/'stderr.log').open('w') as errors,(temp/'samples.jsonl').open('w') as evidence:
    process=subprocess.Popen([program,str(port),str(args.seconds),str(args.connections),fixtures.path('root','der'),fixtures.path('client','der'),fixtures.path('client','pk8')],stdout=subprocess.PIPE,stderr=errors,start_new_session=True,env=environment)
    try:
        for sample in observe(process,args.seconds+120):
            sample['server']=dict(stats)
            if sample.get('line','').startswith('complete '): complete=True
            evidence.write(json.dumps(sample,sort_keys=True)+'\n'); evidence.flush(); samples.append(sample)
    except Exception as error:
        failure=str(error)
    status=process.wait(timeout=15)
async def shutdown():
    server_holder[0].close(); await server_holder[0].wait_closed()
    active=list(peers)
    for task in active: task.cancel()
    await asyncio.gather(*active,return_exceptions=True)
asyncio.run_coroutine_threadsafe(shutdown(),loop).result(timeout=15)
loop.call_soon_threadsafe(loop.stop); thread.join(15)
report={'status':status,'duration_seconds':time.time()-started,'connections':args.connections,'sanitized':args.sanitize,'server':stats,'unexpected_server_errors':unexpected,'observer_failure':failure,'completed':complete,**memory_summary(samples),'scope':'Minyar TLS1.3 mutual TLS and HTTP keep-alive; QUIC not included'}
(temp/'report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report),flush=True)
assert status==0 and not unexpected and failure is None, 'soak failed; inspect evidence'
assert complete, 'client did not complete'
assert stats['responses']>0,'no authenticated response received'
