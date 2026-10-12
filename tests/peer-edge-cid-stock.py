#!/usr/bin/env python3
"""Actual authenticated edge routing for enlarged bounded CID inventories."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
from peer_edge_support import Lab, ROOT, environment
from importlib.util import spec_from_file_location, module_from_spec
spec=spec_from_file_location('edge_cid_commands',ROOT/'tests/peer-edge-cids.py')
commands=module_from_spec(spec);spec.loader.exec_module(commands)
CASES=('limit3','limit8','maximum32768')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sanitize',action='store_true');parser.add_argument('--binary',type=Path)
    parser.add_argument('--case',choices=CASES,action='append');parser.add_argument('--evidence',type=Path);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='minyar-edge-cid-stock-') as folder:
        directory=args.evidence or Path(folder);directory.mkdir(parents=True,exist_ok=True)
        env=environment(args.sanitize);env['MAKEFLAGS']='-j1';client=directory/'client'
        client_env=dict(env,MINYAR_LINK_ARTIFACTS=str(directory/'client-link'))
        commands.command([ROOT/'minyar',ROOT/'tests/peer-edge-cid-stock.min','-o',client],directory,client_env,240)
        results=[]
        for case in args.case or CASES:
            maximum=32768 if case=='maximum32768' else 1;limit=3 if case=='limit3' else 8
            lab=None
            try:
                previous=os.environ.get('MINYAR_LINK_ARTIFACTS')
                os.environ['MINYAR_LINK_ARTIFACTS']=str(directory/case/'edge-link')
                try:lab=Lab(directory/case,args.binary,args.sanitize,duration=8000,maximum=maximum)
                finally:
                    if previous is None:os.environ.pop('MINYAR_LINK_ARTIFACTS',None)
                    else:os.environ['MINYAR_LINK_ARTIFACTS']=previous
                for session in range(3):
                    output=commands.command([client,lab.certs.path('ca','der'),lab.certs.path('device','der'),
                        lab.certs.path('device','pk8'),lab.udp_port,limit],directory,env,10)
                    assert output==f'authenticated edge with peer limit {limit} and wire CID0/CID1\nGREEN actual edge stock limit {limit}: all live IDs route, retired CID0 is silent and replacement remains bounded\n'.encode(),output
                    time.sleep(.25)
                lines=lab.completed(timeout=10)
                values=dict(part.split('=') for part in next(line for line in lines if line.startswith('EDGE_COUNTS ')).split()[1:])
                assert int(values['allocated'])==int(values['retry_validated'])==3,values
                assert int(values['active'])==0 and int(values['peer_slots'])==1,values
                assert int(values['routes'])==0,values
                results.append(dict(case=case,maximum=maximum,limit=limit,counts=values))
            finally:
                if lab:lab.close()
        (directory/'results.json').write_text(json.dumps(dict(sanitize=args.sanitize,results=results),indent=2)+'\n')
        print(json.dumps(results))
if __name__=='__main__':main()
