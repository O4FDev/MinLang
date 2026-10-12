#!/usr/bin/env python3
"""Descriptive stable-sort peers; no change to the existing 1% regression gates.

On WS3 Boat use --lock /home/user/ws3/build.lock. Timings exclude fixture
loading, construction, destruction and independent order-checksum calculation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lock', type=Path, required=True)
    p.add_argument('--swiftc', default='/home/user/.local/share/swiftly/bin/swiftc')
    p.add_argument('--clang', default='clang-22')
    p.add_argument('--repeats', type=int, default=5)
    p.add_argument('--count', type=int, default=262144)
    p.add_argument('--hash-count', type=int, default=2000000)
    args=p.parse_args()
    import fcntl
    with args.lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cpu=min(os.sched_getaffinity(0)); os.sched_setaffinity(0,{cpu})
        ancestors={os.getpid()}; parent=os.getppid()
        while parent:
            ancestors.add(parent)
            try: parent=int(Path(f'/proc/{parent}/stat').read_text().split(') ',1)[1].split()[1])
            except OSError: break
        active=[]
        for proc in Path('/proc').glob('[0-9]*'):
            if int(proc.name) in ancestors: continue
            try:
                cwd=os.readlink(proc/'cwd'); cmd=(proc/'cmdline').read_bytes().split(b'\0'); exe=Path(cmd[0].decode()).name
            except (OSError, IndexError, UnicodeDecodeError): continue
            if cwd.startswith('/home/user/ws3/') and any(exe.startswith(x) for x in ('clang','ld.lld','rustc','swift','minyarc','python')):
                active.append({'pid':int(proc.name),'cwd':cwd,'command':b' '.join(cmd).decode(errors='replace')})
        if active: raise RuntimeError('Other WS3 jobs active: '+json.dumps(active))
        directory=ROOT/'build/sort-peer'; directory.mkdir(parents=True,exist_ok=True)
        commands=[]
        def run(command, timeout=180):
            start=time.monotonic(); result=subprocess.run(list(map(str,command)),capture_output=True,text=True,timeout=timeout)
            commands.append({'command':list(map(str,command)), 'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'wall_seconds':time.monotonic()-start})
            (directory/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
            if result.returncode: raise RuntimeError(result.stderr)
            return result.stdout
        versions={name:run(command) for name,command in {'clang':[args.clang,'--version'],'rust':['rustc','--version'],'swift':[args.swiftc,'--version'],'python':[sys.executable,'--version']}.items()}
        inputs={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT/'benchmarks/list-sort').glob('*') if path.is_file()}
        for name,source in [('ordinary',(ROOT/'runtime/minyar_runtime.c').read_text()),('graph',engine_source(ROOT))]:
            path=directory/(name+'.c'); path.write_text(source)
            run([args.clang,'-O2','-DMINYAR_SYSTEM_HEAP=1','-iquote',ROOT/'runtime','-c',path,'-o',directory/(name+'.o')])
        run(['rustc','-C','opt-level=3',ROOT/'benchmarks/list-sort/peer.rs','-o',directory/'rust'])
        run([args.swiftc,'-O',ROOT/'benchmarks/list-sort/peer.swift','-o',directory/'swift'])
        fixture=directory/'hashes.txt'
        digest=hashlib.sha256()
        with fixture.open('wb') as stream:
            for i in range(args.hash_count):
                line=hashlib.sha256(str((i*1103515245+12345)%1000000).encode()).hexdigest().encode()+b'\n'
                stream.write(line); digest.update(line)
        observations=[]; rng=random.Random(51398)
        for kind in ('integers','records','hashes'):
            count=args.hash_count if kind=='hashes' else args.count
            template=(ROOT/'benchmarks/list-sort'/f'{kind}.min').read_text()
            template=template.replace('let count = '+('2000000' if kind=='hashes' else '262144'),'let count = '+str(count))
            source=directory/(kind+'.min'); source.write_text(template); llvm=source.with_suffix('.ll')
            run([ROOT/'build'/('minyarc-callbacks' if kind=='records' else 'minyarc'),source,llvm,'--library',ROOT/'library'])
            exe=directory/kind
            run([args.clang,'-O2','-Wno-override-module',llvm,directory/('graph.o' if kind=='records' else 'ordinary.o'),ROOT/'runtime/native/system.c','-lm','-o',exe])
            peers={'minyar':[exe]+([fixture] if kind=='hashes' else []),'rust':[directory/'rust',kind,count,fixture],'swift':[directory/'swift',kind,count,fixture],'python':[sys.executable,ROOT/'benchmarks/list-sort/peer.py',kind,count,fixture]}
            expected=int(run(peers['python']).splitlines()[1])
            for iteration in range(args.repeats+1):
                order=list(peers); rng.shuffle(order)
                for peer in order:
                    lines=run(peers[peer]).splitlines(); nanos,checksum=map(int,lines)
                    if checksum!=expected: raise AssertionError((kind,peer,checksum,expected))
                    observations.append(dict(kind=kind,peer=peer,count=count,iteration=iteration,warmup=iteration==0,nanoseconds=nanos,checksum=checksum))
                    print(kind,peer,count,iteration,nanos,checksum,flush=True)
        medians={kind:{peer:statistics.median(o['nanoseconds'] for o in observations if o['kind']==kind and o['peer']==peer and not o['warmup']) for peer in peers} for kind in ('integers','records','hashes')}
        receipt=dict(successful=True,cpu=cpu,lock=str(args.lock),other_ws3_jobs_at_start=active,versions=versions,source_hashes=inputs,fixture_sha256=digest.hexdigest(),observations=observations,median_nanoseconds=medians,scope='Descriptive new API peers. Different object layouts; no pre-sort Minyar API baseline exists. Existing whole-program 1% gates remain separate.')
        (directory/'results.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(medians,indent=2),flush=True)

if __name__=='__main__': main()
