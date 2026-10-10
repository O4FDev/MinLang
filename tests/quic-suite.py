#!/usr/bin/env python3
"""Bounded regression runner; records every exit status without masking failure."""
import argparse,importlib.util,json,os,subprocess,sys,time,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts',type=Path,required=True);parser.add_argument('--yamux-peer',type=Path);parser.add_argument('--state-only',action='store_true');options=parser.parse_args()
    commands=[['securecrypto.py'],['quic-crypto.py'],['quic-wire.py'],['quic-dispatch.py'],['tls-server.py']]
    commands += [['quic-transport.py',*([mode] if mode else [])] for mode in ('','--key-update','--migration','--server-protocol','--resumption','--quic-resumption','--early','--fallback','--congestion')]
    commands += [['tls-resumption-expiry.py']]
    if options.yamux_peer:commands += [['transport-go.py','--peer-binary',str(options.yamux_peer.resolve())]]
    results=[];options.artifacts.mkdir(parents=True,exist_ok=True)
    with (options.artifacts/'suite.log').open('w') as log:
        spec=importlib.util.spec_from_file_location('tls_tests',ROOT/'tests/tls-local.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
        for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):os.environ[name]='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
        for source in ('quic-state.min','tls-tickets.min','yamux.min','quic-dispatch.min'):
            with tempfile.TemporaryDirectory(prefix='minyar-quic-state-') as temporary:
                binary=Path(temporary)/'state';fixtures.compile_program(ROOT/'tests'/source,binary)
                result=subprocess.run([str(binary)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
                results.append({'command':[source],'status':result.returncode});log.flush()
                (options.artifacts/'suite.json').write_text(json.dumps(results,indent=2)+'\n')
                if result.returncode:return result.returncode
        if options.state_only:return 0
        for command in commands:
            started=time.monotonic();print('RUN',command,flush=True);log.write('RUN '+str(command)+'\n');log.flush()
            result=subprocess.run([sys.executable,str(ROOT/'tests'/command[0]),*command[1:],'--sanitize'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            row={'command':command,'status':result.returncode,'seconds':time.monotonic()-started};results.append(row);print(json.dumps(row),flush=True)
            (options.artifacts/'suite.json').write_text(json.dumps(results,indent=2)+'\n')
            if result.returncode:return result.returncode
    return 0
if __name__=='__main__':sys.exit(main())
