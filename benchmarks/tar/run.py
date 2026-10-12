#!/usr/bin/env python3
"""Matched complete tar read/full-metadata/payload-copy and roundtrip benchmark.
Build ahead with --prepare; run prebuilt binaries using --measure under Boat flock
and a parent-granted quiet slot. No timed compiler work or extraction.
"""
import argparse, hashlib, io, json, os, platform, statistics, subprocess, sys, tarfile, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT / 'tests'))
from tar import build_program, tar_provider

def call(cmd): return subprocess.check_output([str(x) for x in cmd],text=True).strip()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',action='store_true'); p.add_argument('--measure',action='store_true')
    p.add_argument('--work',type=Path,default=ROOT/'build/tar-native-benchmark')
    p.add_argument('--release',action='store_true'); p.add_argument('--samples',type=int,default=7); p.add_argument('--output',type=Path)
    a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
    if a.prepare and a.measure: p.error('prepare and measure must be separate commands')
    if a.prepare:
        build_program(a.work,ROOT/'benchmarks/tar/minyar.min','minyar',False,release=a.release)
        clang=os.environ.get('MINYAR_TEST_CLANG','clang')
        flags=['-O2', *(['-flto','-fuse-ld=lld'] if a.release and platform.system()=='Linux' else ['-flto'] if a.release else [])]
        cflags,libraries=tar_provider(clang,tuple(flags))
        subprocess.run([clang,*flags,*cflags,ROOT/'benchmarks/tar/libarchive.c',*libraries,'-o',a.work/'libarchive'],check=True)
        for name,count,size in [('metadata',1024,64),('payload',64,65536)]:
            out=io.BytesIO()
            with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as t:
                for i in range(count):
                    e=tarfile.TarInfo(f'root/member-{i:05d}'); e.size=size; e.mode=0o640
                    e.uid=123; e.gid=456; e.mtime=1700000000; e.uname='owner'; e.gname='group'
                    t.addfile(e,io.BytesIO(bytes([i%256])*size))
            (a.work/f'{name}.tar').write_bytes(out.getvalue())
        from format_provider import provider_info
        manifest={'machine':platform.platform(),'compiler':call([clang,'--version']),
                  'release':a.release,'libarchive':call([a.work/'libarchive','version']),'provider':provider_info('tararchive',clang,('-O2',)),'sources':{}}
        compiler=Path(os.environ.get('MINYAR_TEST_COMPILER',ROOT/'build/minyarc'))
        for file in [ROOT/'library/tar.min',ROOT/'runtime/native/tararchive.c',ROOT/'runtime/minyar_native.h',ROOT/'benchmarks/tar/minyar.min',ROOT/'benchmarks/tar/libarchive.c',ROOT/'benchmarks/tar/run.py',ROOT/'tests/tar.py',a.work/'minyar',a.work/'libarchive',a.work/'runtime.o',compiler,ROOT/'runtime/minyar_runtime.c',a.work/'metadata.tar',a.work/'payload.tar']:
            manifest['sources'][str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
        (a.work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if a.measure:
        if a.samples<3 or not a.output: p.error('--measure requires --samples >= 3 and --output')
        data=json.loads((a.work/'manifest.json').read_text())
        for path,digest in data['sources'].items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,('changed prepared input',path)
        for provider in data['provider']['inputs']:
            assert hashlib.sha256(Path(provider['path']).read_bytes()).hexdigest()==provider['sha256'],('changed provider',provider['path'])
        data.update({'started_utc':datetime.now(timezone.utc).isoformat(),'results':[]})
        for workload,repeat in [('metadata',100),('payload',100)]:
            fixture=a.work/f'{workload}.tar'
            data['sources'][str(fixture)]=hashlib.sha256(fixture.read_bytes()).hexdigest()
            for operation in ['read','roundtrip']:
                commands={impl:[a.work/impl,operation,fixture,repeat] for impl in ['minyar','libarchive']}
                values={}; samples={impl:[] for impl in commands}
                for impl,cmd in commands.items(): values[impl]=call(cmd)
                assert values['minyar']==values['libarchive'],values
                for i in range(a.samples):
                    for impl in (['minyar','libarchive'] if i%2==0 else ['libarchive','minyar']):
                        start=time.perf_counter(); value=call(commands[impl]); elapsed=time.perf_counter()-start
                        assert value==values[impl]
                        samples[impl].append(elapsed)
                med={impl:statistics.median(times) for impl,times in samples.items()}
                data['results'].append({'workload':workload,'operation':operation,'repeat':repeat,'samples_seconds':samples,
                    'median_seconds':med,'ratio':med['minyar']/med['libarchive'],'observable':values,'commands':{k:[str(x) for x in v] for k,v in commands.items()}})
        data['finished_utc']=datetime.now(timezone.utc).isoformat()
        text=json.dumps(data,indent=2); print(text)
        if a.output: a.output.write_text(text+'\n')
if __name__=='__main__': main()
