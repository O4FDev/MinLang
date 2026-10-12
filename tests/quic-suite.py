#!/usr/bin/env python3
"""Bounded regression runner; records every exit status without masking failure."""
import argparse,concurrent.futures,importlib.util,json,os,shutil,subprocess,sys,threading,time,tempfile
import program_cache
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts',type=Path,required=True);parser.add_argument('--yamux-peer',type=Path);parser.add_argument('--state-only',action='store_true');parser.add_argument('--sanitize',action='store_true');parser.add_argument('--optimization',choices=('0','2'),default='0');options=parser.parse_args()
    commands=[['securecrypto.py'],['quic-crypto.py'],['quic-wire.py'],['quic-dispatch.py'],['tls-server.py'],['tls-server.py','--curve','prime256v1'],['tls-keyshare.py'],['tls-signing-usage.py'],['tls-validity.py'],['yamux-churn.py'],['transport-cancel.py']]
    commands += [['quic-transport.py',*([mode] if mode else [])] for mode in ('','--key-update','--migration','--migration-cids','--server-protocol','--resumption','--quic-resumption','--early','--fallback','--congestion','--stream-control','--stream-churn','--closing','--persistent','--retry','--rtt')]
    commands += [['tls-resumption-expiry.py'],['tls-handshake-validity.py']]
    if options.yamux_peer:commands += [['transport-go.py','--peer-binary',str(options.yamux_peer.resolve()),*extra] for extra in ([],['--streams','1536'])]
    if options.yamux_peer:commands += [['transport-go.py','--fin-schedule']]
    options.artifacts.mkdir(parents=True,exist_ok=True);logs=options.artifacts/'logs';shutil.rmtree(logs,ignore_errors=True);logs.mkdir()
    spec=importlib.util.spec_from_file_location('tls_tests',ROOT/'tests/tls-local.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
    flags='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module' if options.sanitize else '-O'+options.optimization+' -Wno-override-module'
    for name in ('MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','MINYAR_RUNTIME_FLAGS'):os.environ[name]=flags
    os.environ['ASAN_OPTIONS']='detect_leaks=1' if sys.platform.startswith('linux') else 'detect_leaks=0'
    os.environ['UBSAN_OPTIONS']='halt_on_error=1'
    def state(index,source):
        with tempfile.TemporaryDirectory(prefix='minyar-quic-state-') as temporary,(logs/f'{index:02}.log').open('w') as log:
            binary=Path(temporary)/'state';fixtures.compile_program(ROOT/'tests'/source,binary)
            result=subprocess.run([str(binary)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
            return {'command':[source],'status':result.returncode}
    def run(index,command):
        started=time.monotonic();print('RUN',command,flush=True)
        with (logs/f'{index:02}.log').open('w') as log:
            log.write('RUN '+str(command)+'\n');log.flush()
            result=subprocess.run([sys.executable,str(ROOT/'tests'/command[0]),*command[1:],*(['--sanitize'] if options.sanitize else [])],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=360 if options.sanitize and '--rtt' in command else 240 if '--streams' in command else 180)
        row={'command':command,'status':result.returncode,'seconds':time.monotonic()-started};print(json.dumps(row),flush=True);return row
    # Cases are independent (own temporaries, ephemeral ports), so they run
    # MINYAR_TEST_JOBS at a time. Results and logs keep suite order, and the
    # first failure in that order is returned after started cases finish.
    def phase(cases):
        results=[];failed=threading.Event()
        def guarded(index,case):
            if failed.is_set():return None
            try:row=case(index)
            except BaseException:failed.set();raise
            if row['status']:failed.set()
            return row
        with program_cache.scope(options.artifacts),concurrent.futures.ThreadPoolExecutor(program_cache.jobs()) as pool:
            futures=[pool.submit(guarded,index,case) for index,case in cases]
            for future in futures:
                row=future.result()
                if row is not None:results.append(row)
        return results
    cases=[(index,lambda index,source=source:state(index,source)) for index,source in enumerate(('quic-state.min','tls-tickets.min','yamux.min','quic-dispatch.min'))]
    results=[]
    try:
        results+=phase(cases)
        if not options.state_only and not any(row['status'] for row in results):
            results+=phase([(len(cases)+index,lambda index,command=command:run(index,command)) for index,command in enumerate(commands)])
    finally:
        with (options.artifacts/'suite.log').open('w') as log:
            for path in sorted(logs.glob('*.log')):log.write(path.read_text(errors='replace'))
        (options.artifacts/'suite.json').write_text(json.dumps(results,indent=2)+'\n')
    return next((row['status'] for row in results if row['status']),0)
if __name__=='__main__':sys.exit(main())
