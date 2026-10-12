#!/usr/bin/env python3
"""Actual Minyar full operations vs maintained C; separate preparation/timing.

Prepare first (--prepare-only). Request a quiet Boat slot from the parent, then
run PREBUILT binaries with --run-only under flock /tmp/ws5-benchmark.lock.
Native bindings are compared, not a pure implementation: no pure timing claim.
References use rawContent/byCopy CDict/DDict and usingCDict/usingDDict, and report
construction separately. Buffer style includes output allocation and release;
Into/raw styles reuse output. Contexts/dictionaries reuse on both sides.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[0]=str(ROOT)  # Do not shadow Python 3.14's stdlib compression package.
import argparse
import gzip
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import zlib
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tests'))
from compression_provider import codec_provider
from clang_helpers import clang_command


def run(command):
    result=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,timeout=600)
    if result.returncode: raise AssertionError((command,result.returncode,result.stdout,result.stderr))
    return result.stdout


def prepare(options):
    work=options.artifacts.resolve(); work.mkdir(parents=True,exist_ok=True)
    providers=[codec_provider(c,options.clang) for c in ('zstd','deflate')]
    cflags=sum((p[0] for p in providers),[]); libs=sum((p[1] for p in providers),[])
    commands=[]
    def build(args): commands.append(list(map(str,args))); return run(args)
    raw=work/'minyar.ll'; runtime=work/'runtime.o'
    build([options.compiler,ROOT/'benchmarks/compression.min',raw,'--library',ROOT/'library'])
    build([options.clang,'-O2','-DMINYAR_SYSTEM_HEAP=1','-c',ROOT/'runtime/minyar_runtime.c','-o',runtime])
    build(clang_command([options.clang,'-O2','-Wno-override-module',*cflags,raw,runtime,
                          ROOT/'runtime/native/zstd.c',ROOT/'runtime/native/deflate.c',ROOT/'runtime/native/system.c',
                          *libs,'-o',work/'minyar']))
    build([options.clang,'-std=c11','-O2','-Wall','-Wextra','-Werror',*cflags,ROOT/'benchmarks/compression-reference.c',
           *libs,'-o',work/'reference'])
    # Independent maintained-codec fixture builder, deliberately no production binding calls.
    helper=work/'fixtures.c'
    helper.write_text('''#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv) {
 assert(argc==4); FILE *f=fopen(argv[1],"rb"); assert(f); fseek(f,0,SEEK_END); size_t n=(size_t)ftell(f); rewind(f);
 unsigned char *in=malloc(n+1),*out=malloc(ZSTD_compressBound(n)); assert(in&&out); assert(fread(in,1,n,f)==n); fclose(f);
 f=fopen(argv[2],"rb"); assert(f); fseek(f,0,SEEK_END); size_t dn=(size_t)ftell(f); rewind(f);
 unsigned char *dict=malloc(dn+1); assert(dict); assert(fread(dict,1,dn,f)==dn); fclose(f);
 ZSTD_CCtx *c=ZSTD_createCCtx(); assert(c);
 size_t r=ZSTD_compressCCtx(c,out,ZSTD_compressBound(n),in,n,3); assert(!ZSTD_isError(r));
 f=fopen(argv[3],"wb"); assert(f); fwrite(out,1,r,f); fclose(f);
 ZSTD_CDict *cd=ZSTD_createCDict_advanced(dict,dn,ZSTD_dlm_byCopy,ZSTD_dct_rawContent,ZSTD_getCParams(3,0,dn),ZSTD_defaultCMem); assert(cd);
 r=ZSTD_compress_usingCDict(c,out,ZSTD_compressBound(n),in,n,cd); assert(!ZSTD_isError(r));
 f=fopen("dict.zst","wb"); assert(f); fwrite(out,1,r,f); fclose(f);
 ZSTD_freeCDict(cd); ZSTD_freeCCtx(c); free(in); free(out); free(dict);
}''')
    build([options.clang,'-O2',*providers[0][0],helper,*providers[0][1],'-o',work/'fixtures'])
    rng=random.Random(5005)
    record=b'{"timestamp":1720000000,"path":"/layers/chunks","status":200,"bytes":65536}\n'
    plain=((record*100)+rng.randbytes(2048))*((options.bytes+len(record)*100+2047)//(len(record)*100+2048))
    plain=plain[:options.bytes]; (work/'plain.bin').write_bytes(plain)
    dictionary=b'\x37\xa4\x30\xec'+(record*100)[:4092]; (work/'dictionary.bin').write_bytes(dictionary)
    subprocess.run([str(work/'fixtures'),str(work/'plain.bin'),str(work/'dictionary.bin'),str(work/'zstd.bin')],cwd=work,check=True)
    (work/'dict.bin').write_bytes((work/'dict.zst').read_bytes())
    for codec,wbits in [('gzip',31),('zlib',15),('raw',-15)]:
        compressor=zlib.compressobj(6,zlib.DEFLATED,wbits)
        (work/(codec+'.bin')).write_bytes(compressor.compress(plain)+compressor.flush())
    sources=[ROOT/p for p in ['benchmarks/compression.min','benchmarks/compression.py','benchmarks/compression-reference.c',
                             'library/zstd.min','library/deflate.min','runtime/native/zstd.c','runtime/native/deflate.c',
                             'runtime/native/compression.h','runtime/minyar_runtime.c','runtime/native/system.c','tools/compression_provider.py']]
    sources += [Path(options.compiler),raw,work/'minyar',work/'reference',helper,*work.glob('*.bin')]
    for flags, libraries in providers:
        sources += [Path(p) for p in libraries if Path(p).is_file()]
        include=Path(flags[flags.index('-isystem')+1])
        sources += [p for p in [include/'zstd.h',include/'zstd_errors.h',include/'zlib.h',include/'zconf.h'] if p.is_file()]
    manifest=dict(provider=providers,clang_version=run([options.clang,'--version']).decode(),architecture=platform.machine(),
                  bytes=len(plain),commands=commands,hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (work/'prepare.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('compression benchmark: prepared (no timings)',flush=True)


def sample(options):
    work=options.artifacts.resolve(); manifest=json.loads((work/'prepare.json').read_text())
    # Refuse changes to the prepared implementation, executables, providers or corpus.
    for p,digest in manifest['hashes'].items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest, ('prepared input changed',p)
    cases=[]
    for codec in ['zstd','dict','gzip','zlib','raw']:
        for op in ['compress','decompress']:
            for style in (['into','raw','buffer'] if codec=='zstd' else ['into'] if codec=='dict' else ['into','buffer']):
                cases.append((codec,op,style))
    cases.append(('dict','build','into'))
    rows=[]
    for codec,op,style in cases:
        input_path=work/('plain.bin' if op!='decompress' else codec+'.bin')
        cap=manifest['bytes']+1024 if op=='compress' else manifest['bytes']
        rounds=max(options.rounds,1000) if op=='build' else options.rounds
        args=[codec,op,style,input_path,work/'dictionary.bin',str(cap),str(rounds)]
        row=dict(codec=codec,operation=op,style=style,rounds=rounds,input=str(input_path),samples=[])
        for index in range(options.samples):
            pair={}
            # Alternate order to expose warm/cache/order sensitivity in raw results.
            order=['minyar','reference'] if index%2==0 else ['reference','minyar']
            for name in order:
                command=[work/name,*args]
                values=run(command).decode().splitlines(); assert len(values)==2
                pair[name]=dict(nanoseconds=int(values[0]),result_total=int(values[1]),argv=list(map(str,command)))
            assert pair['minyar']['result_total']==pair['reference']['result_total'], pair
            row['samples'].append(pair)
        mn=statistics.median(s['minyar']['nanoseconds'] for s in row['samples'])
        cn=statistics.median(s['reference']['nanoseconds'] for s in row['samples'])
        row.update(minyar_median_ns=mn,c_median_ns=cn,minyar_over_c=mn/cn)
        rows.append(row)
        (work/'results.json').write_text(json.dumps(dict(schema=1,kind='native binding / maintained C full operation',pure_candidate=None,
                              preparation=manifest,rows=rows),indent=2)+'\n')
        print(f'{codec} {op} {style}: Minyar/C {mn/cn:.3f}x, {mn/rounds:.0f}/{cn/rounds:.0f} ns/op',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path,required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare-only',action='store_true'); group.add_argument('--run-only',action='store_true')
    parser.add_argument('--samples',type=int,default=5); parser.add_argument('--rounds',type=int,default=128)
    parser.add_argument('--bytes',type=int,default=65536)
    parser.add_argument('--compiler',default=os.environ.get('MINYAR_TEST_COMPILER',str(ROOT/'build/minyarc')))
    parser.add_argument('--clang',default=os.environ.get('MINYAR_TEST_CLANG',os.environ.get('MINYAR_CLANG','clang')))
    options=parser.parse_args()
    assert options.samples>0 and options.rounds>0 and 0<options.bytes<=16777216
    if options.prepare_only: prepare(options)
    else: sample(options)

if __name__=='__main__': main()
