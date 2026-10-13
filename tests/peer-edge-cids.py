#!/usr/bin/env python3
"""Actual mTLS QUIC traffic must route issued IDs and release retired routes."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from peer_edge_support import Lab, ROOT, environment

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def command(argv, directory, env, timeout):
    result = subprocess.run([str(item) for item in argv], env=env, capture_output=True, timeout=timeout)
    records = directory/'commands.jsonl'
    with records.open('a') as output:
        output.write(json.dumps(dict(argv=[str(item) for item in argv], returncode=result.returncode,
            stdout_base64=base64.b64encode(result.stdout).decode(), stderr_base64=base64.b64encode(result.stderr).decode()))+'\n')
    assert result.returncode == 0, (result.returncode, result.stdout.decode(errors='replace'), result.stderr.decode(errors='replace'))
    assert result.stderr == b'', result.stderr.decode(errors='replace')
    return result.stdout

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--client-binary',type=Path)
    parser.add_argument('--sanitize',action='store_true')
    parser.add_argument('--evidence',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='minyar-edge-cids-') as folder:
        if args.evidence:args.evidence.mkdir(parents=True,exist_ok=True)
        directory=Path(tempfile.mkdtemp(prefix='run-',dir=args.evidence)) if args.evidence else Path(folder)
        env=environment(args.sanitize)
        env.update(GOMAXPROCS='1',GOFLAGS='-p=1',MAKEFLAGS='-j1')
        client=args.client_binary or directory/'client'
        if not args.client_binary:command([ROOT/'minyar',ROOT/'tests/peer-edge-cids.min','-o',client],directory,env,240)
        lab=None
        try:
            lab=Lab(directory/'lab',args.binary,args.sanitize,duration=8000,maximum=1)
            for session in range(3):
                output=command([client,lab.certs.path('ca','der'),lab.certs.path('device','der'),
                    lab.certs.path('device','pk8'),lab.udp_port],directory,env,10)
                assert output==b'GREEN actual mTLS QUIC edge: 128 alternate-ID retirements, replacements and duplicate retirements\n',output
                time.sleep(.25)
            lines=lab.completed(timeout=10)
            counts=next(line for line in lines if line.startswith('EDGE_COUNTS ')).split()
            values=dict(part.split('=') for part in counts[1:])
            assert int(values['allocated'])==int(values['retry_validated'])==3,values
            assert int(values['active'])==0 and int(values['peer_slots'])==1,values
            inputs=[ROOT/'library/quic.min',ROOT/'library/peeredge.min',ROOT/'tests/peer-edge-cids.min',Path(__file__),client,lab.binary]
            (directory/'manifest.json').write_text(json.dumps(dict(sanitize=args.sanitize,inputs_sha256={str(p):digest(p) for p in inputs},counts=values),indent=2))
            print(output.decode().strip()+'; three reused sessions, exact three allocated peers and zero active peers')
        finally:
            if lab:lab.close()
if __name__=='__main__':main()
