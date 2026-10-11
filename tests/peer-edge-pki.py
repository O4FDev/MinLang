#!/usr/bin/env python3
"""Real intermediate-chain and root-rollover admission at the edge boundary."""
import argparse
import copy
import json
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile

import h2.config
import h2.connection
import h2.events
from peer_edge_support import Lab, admission

def gateway(lab, certificate, accepted):
    context=ssl.create_default_context(cafile=str(lab.certs.path('ca','pem')))
    context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(str(lab.certs.path(certificate,'pem')),str(lab.certs.path(certificate,'key')))
    context.set_alpn_protocols(['h2'])
    try:
        with context.wrap_socket(socket.create_connection(('127.0.0.1',lab.gateway_port),timeout=3),server_hostname='localhost') as connection:
            assert connection.selected_alpn_protocol()=='h2'
            protocol=h2.connection.H2Connection(config=h2.config.H2Configuration(client_side=True))
            protocol.initiate_connection();connection.sendall(protocol.data_to_send())
            while True:
                data=connection.recv(65536)
                if not data:raise ssl.SSLError('edge rejected client identity')
                events=protocol.receive_data(data)
                if any(isinstance(event,h2.events.RemoteSettingsChanged) for event in events):
                    assert accepted, 'untrusted but registry-listed gateway was admitted'
                    return
    except (ssl.SSLError,ConnectionError):
        if accepted:raise

def malformed_configuration(lab):
    cases=0
    for name in ('certificate','device_roots','gateway_roots'):
        for value in ([],[''],[1],[False],[None],[{}],[[]],['root.der']*17,['x'*4096],['root.der','bad\0path']):
            config=copy.deepcopy(lab.config);config[name]=value
            source=lab.directory/'invalid-pki.json';source.write_text(json.dumps(config))
            result=subprocess.run([str(lab.binary),str(source),'1000'],env=lab.env,capture_output=True,timeout=3)
            assert result.returncode==2 and result.stdout==b'invalid edge configuration\n',(name,value,result)
            assert result.stderr==b'',result.stderr
            cases+=1
    for name in ('device_roots','gateway_roots'):
        config=copy.deepcopy(lab.config);config[name]=[config[name][0]]*16
        config['device_port']=config['gateway_port']=0
        source=lab.directory/'bounded-pki.json';source.write_text(json.dumps(config))
        result=subprocess.run([str(lab.binary),str(source),'1'],env=lab.env,capture_output=True,timeout=3)
        assert result.returncode==0 and result.stdout.startswith(b'READY '),(name,result)
        assert result.stderr==b'',result.stderr
    return cases

def unknown_device(lab,certificate='device-untrusted'):
    context=ssl.create_default_context(cafile=str(lab.certs.path('ca','pem')))
    context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(str(lab.certs.path(certificate,'pem')),str(lab.certs.path(certificate,'key')))
    context.set_alpn_protocols(['hearth-peer.yamux/1'])
    try:
        with context.wrap_socket(socket.create_connection(('127.0.0.1',lab.device_port),timeout=3),
                                 server_hostname='localhost') as connection:
            # Rejected client authentication must close/alert. A trusted client
            # would remain established awaiting its first yamux control stream.
            assert not connection.recv(65536),'untrusted device received application protocol data'
    except (ssl.SSLError,ConnectionError):pass


def run(directory,binary,sanitize):
    lab=None
    try:
        lab=Lab(directory,binary,sanitize,duration=15000,maximum=8,pki=True)
        cases=malformed_configuration(lab)
        for certificate in ('gateway','gateway-next'):gateway(lab,certificate,True)
        gateway(lab,'gateway-untrusted',False)
        gateway(lab,'gateway-device-root',False)
        for certificate in ('device','device-next'):
            device,output=lab.start_device(certificate)
            state=json.loads(admission.eventually(lambda:lab.client.command('GET','peer:live:{exit-a}')))
            assert state['capacity_weight']>0 and state['edge_region']=='eu-west',state
            device.stdin.write(b'close\n');device.stdin.flush();device.communicate(timeout=5)
            assert device.returncode==0
            admission.eventually(lambda:lab.client.command('GET','peer:live:{exit-a}') is None)
        unknown_device(lab)
        unknown_device(lab,'device-gateway-root')
        assert lab.client.command('GET','peer:live:{exit-a}') is None
        assert lab.edge.poll() is None,lab.diagnostic()
        assert lab.diagnostic()=='',lab.diagnostic()
        completed=lab.completed(timeout=20)
        counts=dict(part.split('=') for line in completed if line.startswith('EDGE_COUNTS ')
                    for part in line.split()[1:])
        assert int(counts['active'])==0 and int(counts['retained_relays'])==0,counts
        print(f'GREEN peer edge PKI: intermediate server chain, distinct old/new device and gateway roots, omitted/cross-role root rejection, {cases} malformed path-array controls',flush=True)
    finally:
        if lab:lab.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--sanitize',action='store_true')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='minyar-edge-pki-') as directory:
        directory=Path(directory)
        run(directory/'complete-chain',args.binary,args.sanitize)
        lab=None
        try:
            lab=Lab(directory/'missing-chain',args.binary or directory/'complete-chain'/'edge',
                    args.sanitize,duration=3000,maximum=8,pki=True,server_intermediate=False)
            context=ssl.create_default_context(cafile=str(lab.certs.path('ca','pem')))
            context.load_cert_chain(str(lab.certs.path('gateway','pem')),str(lab.certs.path('gateway','key')))
            context.set_alpn_protocols(['h2'])
            try:
                with context.wrap_socket(socket.create_connection(('127.0.0.1',lab.gateway_port),timeout=3),
                                         server_hostname='localhost'):
                    raise AssertionError('server was trusted without its required intermediate')
            except ssl.SSLCertVerificationError:pass
            assert lab.edge.poll() is None,lab.diagnostic()
            lab.completed(timeout=10)
            print('GREEN missing-intermediate control refused TLS authentication',flush=True)
        finally:
            if lab:lab.close()

if __name__=='__main__':main()
