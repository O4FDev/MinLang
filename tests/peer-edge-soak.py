#!/usr/bin/env python3
"""Real authenticated gateway/device relay soak; target and driver are sampled separately."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import socket
import ssl
import threading
import time
import grpc
import h2.connection
import h2.config
import h2.events
from peer_edge_support import Lab, admission, load
from soak_observer import process_sample, memory_summary, require_remote_lab
relay=load('relay_soak_cases','peer-edge-relay.py')
ROOT=Path(__file__).resolve().parents[1]

def idle_gateways(lab,count):
    context=ssl.create_default_context(cafile=str(lab.certs.path('ca','pem')))
    context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(str(lab.certs.path('gateway','pem')),str(lab.certs.path('gateway','key')))
    context.set_alpn_protocols(['h2'])
    peers=[]
    try:
        for index in range(count):
            raw=socket.create_connection(('127.0.0.1',lab.gateway_port),timeout=5)
            connection=context.wrap_socket(raw,server_hostname='localhost')
            connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            assert connection.selected_alpn_protocol()=='h2'
            protocol=h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True))
            protocol.initiate_connection();connection.sendall(protocol.data_to_send())
            # A real SETTINGS exchange makes these application-ready sockets,
            # rather than incomplete TLS handshakes that expire after ten seconds.
            acknowledged=False
            while not acknowledged:
                data=connection.recv(65536)
                assert data,'idle gateway closed during SETTINGS'
                events=protocol.receive_data(data)
                acknowledged=any(type(event).__name__=='RemoteSettingsChanged' for event in events)
                outgoing=protocol.data_to_send()
                if outgoing:connection.sendall(outgoing)
            peers.append((connection,protocol))
            if (index+1)%256==0:print('CONNECTED',index+1,flush=True)
        return peers
    except BaseException:
        for peer,_ in peers:peer.close()
        raise

def ping_gateways(peers,round_number):
    """Prove every retained TLS/H2 socket remains usable without reconnecting."""
    pending=[]
    for index,(peer,protocol) in enumerate(peers):
        nonce=(round_number*len(peers)+index).to_bytes(8,'big')
        protocol.ping(nonce);peer.sendall(protocol.data_to_send())
        pending.append((peer,protocol,nonce))
    for peer,protocol,nonce in pending:
        acknowledged=False
        deadline=time.monotonic()+5
        while not acknowledged:
            assert time.monotonic()<deadline,'pooled gateway PING deadline'
            data=peer.recv(65536)
            assert data,'pooled gateway closed before PING acknowledgment'
            events=protocol.receive_data(data)
            assert not any(isinstance(event,h2.events.ConnectionTerminated) for event in events),'pooled gateway GOAWAY'
            acknowledged=any(isinstance(event,h2.events.PingAckReceived) and event.ping_data==nonce for event in events)
            outgoing=protocol.data_to_send()
            if outgoing:peer.sendall(outgoing)
    return len(pending)

def cancelled(lab,r,out,identifier):
    stopped=threading.Event()
    def request():
        yield relay.opened(lab.signed(identifier),identifier)
        stopped.wait(5)
    call=r(request(),timeout=6)
    try:
        assert next(call).status.code==0
        call.cancel()
        lab.device_event(out,'CANCELLED '+identifier)
    finally:stopped.set()

def malformed_gateway(lab):
    context=ssl.create_default_context(cafile=str(lab.certs.path('ca','pem')))
    context.load_cert_chain(str(lab.certs.path('gateway','pem')),str(lab.certs.path('gateway','key')))
    context.set_alpn_protocols(['h2'])
    with context.wrap_socket(socket.create_connection(('127.0.0.1',lab.gateway_port),timeout=3),server_hostname='localhost') as connection:
        connection.sendall(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'+b'\0\0\4\3\0'+b'\0\0\0\0'+b'\0\0\0\10')
        # RST_STREAM on stream zero is a connection error; complete authenticated
        # traffic on other sockets must still work after this peer is retired.

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=7200)
    parser.add_argument('--connections',type=int,default=2048)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sanitize',action='store_true')
    parser.add_argument('--startup-budget',type=int,default=None)
    options=parser.parse_args();require_remote_lab()
    if not 30<=options.seconds<=82800 or not 1<=options.connections<=20000:parser.error('seconds30..82800;connections1..20000')
    soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
    required=options.connections+512
    if soft<required:resource.setrlimit(resource.RLIMIT_NOFILE,(min(required,hard),hard))
    assert resource.getrlimit(resource.RLIMIT_NOFILE)[0]>=required
    padding=options.startup_budget if options.startup_budget is not None else (600 if options.seconds>=7200 else 30)
    if not 30<=padding<=3600:parser.error('startup budget must be30..3600 seconds')
    directory=options.output;directory.mkdir(parents=True,exist_ok=False)
    lab=None;peers=[];samples=[];idle=[];failure=None;finished=False;counts={}
    try:
        lab=Lab(directory/'lab',sanitize=options.sanitize,duration=(options.seconds+padding)*1000,maximum=options.connections+32,sanitizer_quarantine=1 if options.sanitize else None)
        lab.env['MINYAR_PEER_DEVICE_HEARTBEAT_MS']='15000'
        device,out=lab.start_device()
        setup_started=time.monotonic()
        peers=idle_gateways(lab,options.connections)
        setup_seconds=time.monotonic()-setup_started
        assert setup_seconds<=padding,('gateway setup exhausted separate startup budget',setup_seconds,padding)
        print('SETUP',json.dumps(dict(seconds=setup_seconds,budget=padding,connections=len(peers))),flush=True)
        ping_round=0;ping_acks=ping_gateways(peers,ping_round)
        source_paths=[path for group in ('library','runtime','compiler','tools','tests') for path in (ROOT/group).rglob('*') if path.is_file() and path.suffix in ('.min','.c','.m','.h','.py','.go','.proto','.mod','.sum')]
        (directory/'sources.json').write_text(json.dumps({str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source_paths)},indent=2)+'\n')
        started=time.monotonic();last_sample=started;last_idle=None;ordinal=0;transactions=0;faults=0
        with relay.channel(lab) as channel,(directory/'samples.jsonl').open('w') as evidence:
            r=relay.rpc(channel)
            while time.monotonic()-started<options.seconds:
                elapsed=time.monotonic()-started
                # Eight signed RPCs/faults followed by forty seconds of connected idle.
                active=int(elapsed)%60<20
                if active:
                    minute=int(elapsed)//60
                    if minute>ping_round:
                        ping_round=minute;ping_acks+=ping_gateways(peers,ping_round)
                    identifier=f'soak-{ordinal}';ordinal+=1
                    payload=bytes(range(256))*(256 if ordinal%31==0 else 1)+ordinal.to_bytes(8,'big')
                    relay.transfer(lab,r,identifier,payload,timeout=10);transactions+=1
                    if ordinal%7==0:cancelled(lab,r,out,f'cancel-{ordinal}');faults+=1
                    if ordinal%11==0:malformed_gateway(lab);faults+=1
                else:time.sleep(.5)
                now=time.monotonic()
                if now-last_sample>=1:
                    target=process_sample(lab.edge.pid);controller=process_sample(os.getpid())
                    assert lab.edge.poll() is None,'edge exited during authenticated soak'
                    assert device.poll() is None,'device exited during authenticated soak'
                    # The authoritative live state must survive real 15-second heartbeats.
                    state=lab.client.command('GET','peer:live:{exit-a}')
                    assert state,'heartbeat live state expired'
                    row={'elapsed_seconds':now-started,'phase':'active' if active else 'connected_idle','target':target,'controller':controller,'device':process_sample(device.pid),'transactions':transactions,'faults':faults,'connections':len(peers),'gateway_ping_acks':ping_acks}
                    samples.append({'elapsed_seconds':row['elapsed_seconds'],**target})
                    if not active:
                        if last_idle is not None:
                            seconds=row['elapsed_seconds']-last_idle['elapsed_seconds']
                            cpu=(target['cpu_seconds']-last_idle['cpu_seconds'])/seconds
                            idle.append(cpu)
                        last_idle={'elapsed_seconds':row['elapsed_seconds'],**target}
                    else:last_idle=None
                    evidence.write(json.dumps(row,sort_keys=True)+'\n');evidence.flush()
                    last_sample=now
                    if int(elapsed)%30==0:print('SAMPLE',json.dumps(row,sort_keys=True),flush=True)
                if active:time.sleep(.2)
            ping_acks+=ping_gateways(peers,ping_round+1)
            relay.transfer(lab,r,'final-health',b'\0\xffhealthy after faults',timeout=10);transactions+=1
        for peer,_ in peers:peer.close()
        peers=[]
        device.stdin.write(b'close\n');device.stdin.flush();device.communicate(timeout=10)
        assert device.returncode==0,'independent device did not exit cleanly'
        lines=lab.completed(timeout=padding+30)
        counts=dict(part.split('=') for part in next(line for line in lines if line.startswith('EDGE_COUNTS ')).split()[1:])
        assert int(counts['active'])==0 and int(counts['retained_relays'])==0,counts
        assert int(counts['calls_opened'])==int(counts['calls_released']),counts
        assert transactions>10 and faults>0,'fault workload did not execute'
        summary=memory_summary(samples,warmup=60 if options.seconds>=7200 else 5)
        assert summary['warm_rss_min_kib'] is not None,'no independent warm RSS samples'
        assert idle,'connected idle was never measured'
        mean_idle=sum(idle)/len(idle)
        assert mean_idle<=.02,('connected idle exceeded 2% of one CPU',mean_idle)
        if options.seconds>=7200:
            assert summary['warm_rss_max_kib']-summary['warm_rss_min_kib']<=16384,summary
            assert summary['rss_slope_kib_per_second']<=.2,summary
        report=dict(status=0,startup_seconds=setup_seconds,startup_budget_seconds=padding,seconds_requested=options.seconds,seconds_observed=time.monotonic()-started,connections=options.connections,gateway_ping_acks=ping_acks,transactions=transactions,faults=faults,counts=counts,mean_connected_idle_cpu=mean_idle,scope='actual certificate-verified mTLS HTTP2 gateway, independent TLS/yamux TCP device fallback, signed-grant relay, cancellation/invalid frames/half-close/binary echo; QUIC is verified separately',sanitized=options.sanitize,**summary)
        (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('GREEN',json.dumps(report),flush=True);finished=True
    except BaseException as error:
        failure=repr(error);(directory/'failure.json').write_text(json.dumps({'failure':failure,'finished':finished,'sample_count':len(samples)},indent=2)+'\n');raise
    finally:
        for peer,_ in peers:peer.close()
        if lab:lab.close()
if __name__=='__main__':main()
