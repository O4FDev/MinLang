#!/usr/bin/env python3
"""Official runner adapter. Ephemeral test certificates and NSS logs only."""
import os, re, subprocess, sys, tempfile, time
from pathlib import Path
from urllib.parse import urlsplit
case=os.environ.get('TESTCASE','')
if case not in ('handshake','transfer','resumption','zerortt','multiconnect','rebind-port','rebind-addr'):
    sys.exit(127)
while not Path('/tmp/network-ready').exists():time.sleep(.05)
role=os.environ['ROLE']
with tempfile.TemporaryDirectory(prefix='minyar-qns-') as d:
    d=Path(d)
    def openssl(*args):subprocess.run(['openssl',*map(str,args)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    root=d/'root.der';openssl('x509','-in','/certs/ca.pem','-outform','DER','-out',root)
    log=os.environ.get('SSLKEYLOGFILE','/logs/keys.log');Path(log).parent.mkdir(parents=True,exist_ok=True)
    if role=='server':
        key=d/'key.der';openssl('pkcs8','-topk8','-nocrypt','-in','/certs/priv.key','-outform','DER','-out',key)
        chain=re.findall(rb'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----',Path('/certs/cert.pem').read_bytes(),re.S)
        if not chain or len(chain)>16:sys.exit(1)
        certificates=[]
        for n,pem in enumerate(chain):
            source=d/f'{n}.pem';der=d/f'{n}.der';source.write_bytes(pem);openssl('x509','-in',source,'-outform','DER','-out',der);certificates.append(str(der))
        command=['/opt/minyar/server',str(key),str(root),log,'/www',case,*certificates]
    else:
        urls=[urlsplit(u) for u in os.environ.get('REQUESTS','').split()]
        if not urls or len(urls)>16 or any(u.scheme!='https' or u.hostname!=urls[0].hostname or u.port!=urls[0].port or u.query or u.fragment or not re.fullmatch('/[a-zA-Z0-9_-]{1,255}',u.path) for u in urls):sys.exit(1)
        command=['/opt/minyar/client',str(root),urls[0].hostname,str(urls[0].port or 443),log,'/downloads',case,*[u.path[1:] for u in urls]]
    sys.exit(subprocess.run(command).returncode)
