#!/usr/bin/env python3
"""Bounded compression contracts, independent interop, fuzz, normal/custom links.

--mode sanitize instruments generated Minyar IR (canonical annotator), runtime,
providers and the guarded native/fuzz binary. Python ctypes oracle fuzz is a
separate unsanitized native cohort. No performance sampling in this test suite.
MINYAR_TEST_COMPILER and MINYAR_TEST_CLANG select existing tools, never rebuild
an explicitly selected compiler. Normal launcher qualification is performed
when that compiler is ROOT/build/minyarc; custom selection is exercised by the
manual compiler + normal link driver + manual custom-link routes.
"""
# Python 3.14 has a stdlib compression package; hide our script directory
# before importing shutil/tempfile/gzip, which may import that package.
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[0] = str(ROOT)
import argparse
import ctypes as C
import gzip
import hashlib
import json
import os
import platform
import random
import re
import shutil
import shlex
import subprocess
import tempfile
import zlib
sys.path.insert(0, str(ROOT / 'tests'))

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from compression_provider import codec_provider
from clang_helpers import asan_leak_options, clang_command, launcher_command
from llvm_sanitizer import instrument_address_sanitizer

INVALID, LIMIT, TRUNCATED, CORRUPT, DICTIONARY, MEMORY, CLOSED, TRAILING = range(-1, -9, -1)


class Evidence:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.commands = []
        self.env = dict(os.environ, ASAN_OPTIONS=asan_leak_options()+':halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')

    def run(self, command, *, env=None, expected=None, timeout=180):
        command = list(map(str, command))
        result = subprocess.run(command, cwd=ROOT, env=env or self.env, capture_output=True, timeout=timeout)
        self.commands.append(dict(argv=command, status=result.returncode,
                                  stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace')))
        self.save()
        if result.returncode or expected is not None and result.stdout != expected:
            raise AssertionError(self.commands[-1])
        return result.stdout

    def save(self):
        (self.directory/'commands.json').write_text(json.dumps(self.commands, indent=2)+'\n')


def bind(library, name, count):
    f = getattr(library, name)
    f.argtypes, f.restype = [C.c_longlong]*count, C.c_longlong
    return f


def buffer(data):
    return C.create_string_buffer(data, max(1, len(data)))


def native_oracles(evidence, clang, cflags, libraries, chunk):
    suffix = '.dylib' if platform.system() == 'Darwin' else '.so'
    path = evidence.directory/f'oracles-{chunk}{suffix}'
    evidence.run([clang, '-std=c11', '-O2', '-fPIC', '-shared', '-Wall', '-Wextra', '-Werror',
                  f'-DMINYAR_COMPRESSION_CHUNK={chunk}', *cflags,
                  *(['-Wl,--exclude-libs,ALL'] if platform.system() == 'Linux' else []),
                  ROOT/'runtime/native/zstd.c', ROOT/'runtime/native/deflate.c', ROOT/'tests/compression-reference.c',
                  *libraries, '-o', path])
    lib = C.CDLL(str(path))
    comp = bind(lib, 'minyar_deflate_rawCompress', 6)
    decomp = bind(lib, 'minyar_deflate_rawDecompress', 5)
    zcomp = bind(lib, 'minyar_zstd_rawCompress', 5)
    zdec = bind(lib, 'minyar_zstd_rawDecompress', 4)
    rcomp = bind(lib, 'reference_zstd_compress', 4)
    rdec = bind(lib, 'reference_zstd_decompress', 4)
    rng = random.Random(5005)
    cases = [b'', b'x', b'hello\0world'*25, bytes(range(256))*16, rng.randbytes(65536)]
    def decode(fn, data, cap, *extra):
        src = buffer(data)
        guarded = C.create_string_buffer(b'\xa5'*(cap+2), cap+2)
        n = fn(C.addressof(src),len(data),C.addressof(guarded)+1,cap,*extra)
        assert guarded.raw[0] == 0xa5 and guarded.raw[-1] == 0xa5, (chunk, n, 'guard')
        assert n <= cap
        return n, guarded.raw[1:1+max(0,n)]
    for data in cases:
        src = buffer(data); dst = C.create_string_buffer(len(data)+512)
        for format, wbits in [(0,31),(1,15),(2,-15)]:
            n = comp(C.addressof(src),len(data),C.addressof(dst),len(dst),format,6)
            assert n > 0
            assert zlib.decompress(dst.raw[:n], wbits) == data
            oracle = zlib.compressobj(6,zlib.DEFLATED,wbits)
            packed = oracle.compress(data)+oracle.flush()
            assert decode(decomp,packed,len(data),format) == (len(data),data)
            if data: assert decode(decomp,packed,len(data)-1,format)[0] == LIMIT
            # Every truncation of small independent valid frames is diagnosed.
            if len(packed) < 500:
                for cut in range(len(packed)):
                    assert decode(decomp,packed[:cut],len(data),format)[0] == TRUNCATED, (format, cut)
            assert decode(decomp,packed+b'xx',len(data),format)[0] == (CORRUPT if format == 0 else TRAILING)
            if format != 2:
                for at in ([-1,-5] if format == 0 else [-1,-4]):
                    broken = bytearray(packed); broken[at] ^= 0x80
                    assert decode(decomp,bytes(broken),len(data),format)[0] == CORRUPT, (format,len(data),at)
        n = rcomp(C.addressof(src),len(data),C.addressof(dst),len(dst))
        packed = dst.raw[:n]
        assert decode(zdec,packed,len(data)) == (len(data),data)
        if data: assert decode(zdec,packed,len(data)-1)[0] == LIMIT
        for cut in range(min(len(packed),100)):
            assert decode(zdec,packed[:cut],len(data))[0] < 0
        n = zcomp(C.addressof(src),len(data),C.addressof(dst),len(dst),3)
        assert decode(rdec,dst.raw[:n],len(data)) == (len(data),data)
    # gzip headers with optional metadata, concatenation, exact cap, empty members.
    empty = gzip.compress(b'',mtime=0)
    packed = gzip.compress(b'abc',mtime=0)+empty*4
    assert decode(decomp,packed,3,0) == (3,b'abc')
    assert decode(decomp,empty*5,0,0) == (0,b'')
    assert decode(decomp,packed+gzip.compress(b'x'),3,0)[0] == LIMIT
    for cut in range(1,len(empty)):
        assert decode(decomp,packed+empty[:cut],3,0)[0] == TRUNCATED
    # Optional gzip fields plus header CRC, with strict CRC/ISIZE completion.
    base=gzip.compress(b'header fields',mtime=0)
    header=bytearray(base[:10]); header[3]=0x1e
    header+=b'\x03\x00abcname\x00comment\x00'
    header+=(zlib.crc32(header)&65535).to_bytes(2,'little')
    optional=bytes(header)+base[10:]
    assert decode(decomp,optional,13,0)==(13,b'header fields')
    broken=bytearray(optional); broken[len(header)-1]^=1
    assert decode(decomp,bytes(broken),13,0)[0]==CORRUPT
    broken=bytearray(base); broken[0]^=1
    assert decode(decomp,bytes(broken),13,0)[0]==CORRUPT
    # zstd checksummed content, exact-cap checksum, and observed-error precedence.
    src=buffer(b'checksum payload'*20); dst=C.create_string_buffer(1024)
    checksum=bind(lib,'reference_zstd_checksum',4)
    n=checksum(C.addressof(src),320,C.addressof(dst),1024)
    packed=dst.raw[:n]
    assert decode(zdec,packed,320)==(320,b'checksum payload'*20)
    broken=bytearray(packed); broken[-1]^=1
    assert decode(zdec,bytes(broken),320)[0]==CORRUPT
    assert decode(zdec,bytes(broken),100)[0]==LIMIT
    assert decode(zdec,packed+packed,640)==(640,b'checksum payload'*40)
    skippable=b'\x50\x2a\x4d\x18'+(3).to_bytes(4,'little')+b'abc'
    assert decode(zdec,skippable+packed+skippable,320)==(320,b'checksum payload'*20)
    # Frame dictionary-ID request is diagnosed; RAW contents have no identity ID.
    src=buffer(b'dictionary request'); n=rcomp(C.addressof(src),18,C.addressof(dst),1024)
    frame=bytearray(dst.raw[:n]); assert frame[4]&3==0
    frame[4]|=1; frame[5:5]=b'\x2a'
    assert decode(zdec,bytes(frame),18)[0]==DICTIONARY
    # Zlib FDICT is a diagnosed dictionary request, not corruption.
    oracle = zlib.compressobj(zdict=b'dictionary')
    packed = oracle.compress(b'dictionary'*20)+oracle.flush()
    assert decode(decomp,packed,200,1)[0] == DICTIONARY
    # Explicit RAW magic-prefix dictionaries and byCopy mutation / close ordering.
    dictionary = b'\x37\xa4\x30\xec'+b'common dictionary record / payload / '*100
    original = bytes(dictionary); db = buffer(dictionary)
    cd = bind(lib,'minyar_zstd_rawCreateCDict',3)(C.addressof(db),len(dictionary),3)
    dd = bind(lib,'minyar_zstd_rawCreateDDict',2)(C.addressof(db),len(dictionary))
    ctx = bind(lib,'minyar_zstd_rawCreateCCtx',0)(); dctx = bind(lib,'minyar_zstd_rawCreateDCtx',0)()
    assert cd and dd and ctx and dctx
    dcompress = bind(lib,'minyar_zstd_rawCompressDict',6)
    ddecompress = bind(lib,'minyar_zstd_rawDecompressDict',6)
    rdc = bind(lib,'reference_dict_compress',6); rdd = bind(lib,'reference_dict_decompress',6)
    payload = original[4:]*2; src=buffer(payload); dst=C.create_string_buffer(len(payload)+512)
    C.memset(C.addressof(db),0,len(dictionary))
    n=dcompress(ctx,cd,C.addressof(src),len(payload),C.addressof(dst),len(dst))
    packed=dst.raw[:n]; orig=buffer(original)
    output=C.create_string_buffer(len(payload)+1)
    assert rdd(C.addressof(dst),n,C.addressof(output),len(payload),C.addressof(orig),len(original)) == len(payload)
    assert output.raw[:len(payload)] == payload
    n=rdc(C.addressof(src),len(payload),C.addressof(dst),len(dst),C.addressof(orig),len(original))
    assert ddecompress(dctx,dd,C.addressof(dst),n,C.addressof(output),len(payload)) == len(payload)
    assert output.raw[:len(payload)] == payload
    # Dictionary decompression failures cannot poison reuse.
    assert ddecompress(dctx,dd,C.addressof(dst),n-1,C.addressof(output),len(payload)) < 0
    assert ddecompress(dctx,dd,C.addressof(dst),n,C.addressof(output),len(payload)) == len(payload)
    for name,h in [('CCtx',ctx),('DCtx',dctx),('CDict',cd),('DDict',dd)]:
        getattr(lib,'minyar_zstd_rawClose'+name)(C.c_longlong(h))
    # Deterministic zstd mutation fuzz compared with the independent complete C decoder.
    src=buffer(bytes(range(64))); n=rcomp(C.addressof(src),64,C.addressof(dst),len(dst))
    seed=dst.raw[:n]
    for _ in range(400):
        changed=bytearray(seed); at=rng.randrange(len(changed)); changed[at]^=1<<rng.randrange(8)
        observed=decode(zdec,bytes(changed),256)
        expected=decode(rdec,bytes(changed),256)
        if expected[0] < 0: assert observed[0] < 0
        else: assert observed==expected
    # Deterministic mutation fuzz: accepted outputs must match independent oracles.
    seeds=[(0,gzip.compress(bytes(range(64)),mtime=0)),(1,zlib.compress(bytes(range(64))))]
    for format,seed in seeds:
        for _ in range(400):
            mutated=bytearray(seed); at=rng.randrange(len(mutated)); mutated[at]^=1<<rng.randrange(8)
            n,data=decode(decomp,bytes(mutated),256,format)
            try: expected=zlib.decompress(mutated,31 if format==0 else 15)
            except zlib.error: assert n < 0
            else: assert (n,data)==(len(expected),expected)
    print(f'ctypes interop/fuzz chunk={chunk}: ok',flush=True)


def provider_contracts(clang, provider):
    flags,libraries=provider
    archive=Path(libraries[0]); assert archive.is_absolute() and archive.name=='libzstd.a'
    include=Path(flags[flags.index('-isystem')+1])
    if platform.system() == 'Windows' or platform.system().startswith(('MSYS','MINGW','CYGWIN')):
        # codec_provider already ran the active-prefix 64-bit/raw-dict probe.
        # Copied temp prefixes cannot satisfy the compiler/CRT-prefix rule.
        print('active MSYS static provider probe: ok; isolated archive negatives in compression-provider.py',flush=True)
        return
    old=os.environ.get('MINYAR_ZSTD_PREFIX')
    try:
        with tempfile.TemporaryDirectory(prefix='minyar-provider-contract-') as tmp:
            prefix=Path(tmp); (prefix/'include').mkdir(); (prefix/'lib').mkdir()
            for name in ['zstd.h','zstd_errors.h']: shutil.copyfile(include/name,prefix/'include'/name)
            os.environ['MINYAR_ZSTD_PREFIX']=str(prefix)
            try: codec_provider('zstd',clang)
            except ValueError as error: assert 'same provider' in str(error)
            else: raise AssertionError('missing absolute archive accepted')
            shutil.copyfile(archive,prefix/'lib/libzstd.a')
            assert codec_provider('zstd',clang)[1][0]==str(prefix/'lib/libzstd.a')
            header=prefix/'include/zstd.h'
            source=header.read_text()
            source=re.sub(r'(#define ZSTD_VERSION_RELEASE\s+)([0-9]+)',lambda m:m[1]+str(int(m[2])+1),source)
            header.write_text(source)
            try: codec_provider('zstd',clang)
            except ValueError as error: assert 'version equality not established' in str(error)
            else: raise AssertionError('mismatched header/archive version accepted')
    finally:
        if old is None: os.environ.pop('MINYAR_ZSTD_PREFIX',None)
        else: os.environ['MINYAR_ZSTD_PREFIX']=old
    print('matched static provider contracts: ok',flush=True)


def qualify(options, evidence):
    clang = options.clang
    providers = [codec_provider(codec,clang) for codec in ('zstd','deflate')]
    provider_contracts(clang,providers[0])
    cflags = sum((p[0] for p in providers),[]); libraries=sum((p[1] for p in providers),[])
    flags = ['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if options.mode=='sanitize' else ['-O2']
    for chunk in [4294967295,7]:
        executable=evidence.directory/f'native-{chunk}'
        evidence.run(clang_command([clang,'-std=c11','-Wall','-Wextra','-Werror',*flags,*cflags,
                                   f'-DMINYAR_COMPRESSION_CHUNK={chunk}',ROOT/'tests/compression-native.c',
                                   ROOT/'runtime/native/zstd.c',ROOT/'runtime/native/deflate.c',*libraries,'-o',executable]))
        evidence.run([executable],expected=b'compression-native: ok\n')
        native_oracles(evidence,clang,cflags,libraries,chunk)
    if options.native_only: return
    compiler=Path(options.compiler).resolve()
    assert compiler.is_file(), f'existing compiler not found: {compiler}'
    runtime=evidence.directory/'runtime.o'
    evidence.run(clang_command([clang,*flags,'-DMINYAR_SYSTEM_HEAP=1','-c',ROOT/'runtime/minyar_runtime.c','-o',runtime]))
    binaries=[]
    for name in ['compression','compression-driver','compression-stream']:
        raw=evidence.directory/(name+'.raw.ll')
        evidence.run([compiler,ROOT/'tests'/(name+'.min'),raw,'--library',ROOT/'library'])
        ir=raw
        if options.mode=='sanitize':
            ir=evidence.directory/(name+'.asan.ll'); ir.write_text(instrument_address_sanitizer(raw.read_text()))
        binary=evidence.directory/(name+'-manual')
        evidence.run(clang_command([clang,*flags,'-Wno-override-module',*cflags,ir,runtime,
                                   ROOT/'runtime/native/zstd.c',ROOT/'runtime/native/deflate.c',*libraries,'-o',binary]))
        binaries.append(binary)
        # Driver uses the canonical generated IR sanitizer when link flags request ASan.
        env=dict(evidence.env,MINYAR_CLANG=clang,MINYAR_CLANG_FLAGS=shlex.join(flags),MINYAR_NATIVE_FLAGS=shlex.join(flags))
        normal=evidence.directory/(name+'-driver')
        evidence.run([sys.executable,ROOT/'tools/clang-driver.py','link',ROOT,raw,runtime,normal,'0'],env=env)
        if name in ('compression', 'compression-stream'):
            expected = (name + ': ok\n').encode()
            evidence.run([binary],expected=expected); evidence.run([normal],expected=expected)
        if compiler == (ROOT/'build/minyarc').resolve():
            launcher=evidence.directory/(name+'-normal')
            env['MINYAR_RUNTIME_FLAGS']=shlex.join(flags)
            evidence.run([*launcher_command(ROOT),ROOT/'tests'/(name+'.min'),'-o',launcher],env=env)
            if name in ('compression', 'compression-stream'): evidence.run([launcher],expected=(name + ': ok\n').encode())
    driver=binaries[1]
    source=evidence.directory/'input.bin'; output=evidence.directory/'output.bin'
    payload=bytes(range(256))*100
    for codec,wbits in [('gzip',31),('zlib',15),('raw',-15)]:
        source.write_bytes(payload)
        evidence.run([driver,codec,'compress',source,output,len(payload)+1024],expected=b'0\n')
        assert zlib.decompress(output.read_bytes(),wbits)==payload
        reference=zlib.compressobj(6,zlib.DEFLATED,wbits)
        packed=reference.compress(payload)+reference.flush()
        source.write_bytes(packed)
        evidence.run([driver,codec,'decompress',source,output,len(payload)],expected=b'0\n')
        assert output.read_bytes()==payload
        evidence.run([driver,codec,'decompress',source,output,len(payload)-1],expected=b'-2\n')
        assert output.read_bytes()==b''
        source.write_bytes(packed[:-1])
        evidence.run([driver,codec,'decompress',source,output,len(payload)],expected=b'-3\n')
    manifest={'mode':options.mode,'compiler':str(compiler),'clang_version':evidence.run([clang,'--version']).decode(),
              'providers':providers,'hashes':{}}
    sources=[compiler,*[ROOT/p for p in ['library/zstd.min','library/deflate.min','runtime/native/zstd.c','runtime/native/deflate.c',
                'runtime/native/compression.h','tools/compression_provider.py','tools/clang-driver.py','tests/compression-codecs.py',
                'tests/compression.min','tests/compression-driver.min','tests/compression-native.c','tests/compression-reference.c',
                'runtime/minyar_runtime.c','runtime/minyar_native.h','tests/llvm_sanitizer.py','tools/sanitizer_llvm.py']],
             *evidence.directory.glob('*.ll')]
    sources += sorted((ROOT/'runtime').rglob('*.h'))
    sources.append(Path(shutil.which(clang) or clang).resolve())
    for flags,libs in providers:
        include=Path(flags[flags.index('-isystem')+1])
        sources += [p for p in [include/'zstd.h',include/'zstd_errors.h',include/'zlib.h',include/'zconf.h'] if p.is_file()]
        sources.extend(Path(p) for p in libs if Path(p).is_file())
    for p in sources: manifest['hashes'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    (evidence.directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['native','sanitize'],default='native')
    parser.add_argument('--native-only',action='store_true')
    parser.add_argument('--compiler',default=os.environ.get('MINYAR_TEST_COMPILER',str(ROOT/'build/minyarc')))
    parser.add_argument('--clang',default=os.environ.get('MINYAR_TEST_CLANG',os.environ.get('MINYAR_CLANG','clang')))
    parser.add_argument('--artifacts',type=Path)
    options=parser.parse_args()
    if options.artifacts: qualify(options,Evidence(options.artifacts.resolve()))
    else:
        with tempfile.TemporaryDirectory(prefix='minyar-compression-tests-') as tmp: qualify(options,Evidence(Path(tmp)))
    print(f'compression {options.mode}: all selected contracts passed',flush=True)

if __name__=='__main__': main()
