#!/usr/bin/env python3
"""Cache-driver identity, integrity, atomic publication and overlap tests."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DRIVER=Path(os.environ.get('MINYAR_MODULE_DRIVER',ROOT/'build/minyar-module-build')).resolve()
COMPILER=ROOT/'build/minyarc-modules'


def run(command,success=True):
    result=subprocess.run(list(map(str,command)),capture_output=True,text=True,timeout=60)
    assert (result.returncode==0)==success,result.stderr
    return result


with tempfile.TemporaryDirectory(prefix='minyar-native-cache-') as name:
    temp=Path(name)
    compiler=temp/'compiler';shutil.copy2(COMPILER,compiler)
    entry=temp/'main.min';library=temp/'library.min';cache=temp/'cache';output=temp/'program.ll';stats=temp/'stats.txt'
    library.write_text('public function answer(): Integer { return 40 }\n')
    source='use "./library.min" as library\nprint(library.answer() + 2)\n'
    entry.write_text(source)
    def build(*,tool=compiler,target=output,counters=stats,success=True):
        result=run([DRIVER,tool,entry,target,cache,counters],success=success)
        assert not list(cache.glob('invocation.*')),'invocation files leaked'
        if success:
            return tuple(map(int,counters.read_text().split()[:6]))
        return result
    assert build()==(0,2,2,0,1,1)
    assert build()==(2,0,0,2,0,0)
    original=output.read_bytes()
    cache_file=next(cache.glob('*.cache'))
    before=compiler.stat();os.utime(compiler,ns=(before.st_atime_ns,before.st_mtime_ns+1))
    assert build()==(2,0,0,2,0,0),'mtime changed compiler identity'
    before=library.stat();library.write_text(library.read_text().replace('40','41'));os.utime(library,ns=(before.st_atime_ns,before.st_mtime_ns))
    assert build()==(1,1,1,1,1,0)
    run(['clang','-O0','-Wno-override-module',output,ROOT/'build/minyar-runtime.o','-o',temp/'program'])
    assert run([temp/'program']).stdout=='43\n'

    good=cache_file.read_bytes()
    for bad in (b'',b'not an artifact',good[:100],good[:-1],bytes([good[0]^1])+good[1:],good[:-40]+bytes([good[-40]^1])+good[-39:]):
        cache_file.write_bytes(bad)
        assert build()==(0,2,2,0,1,1)
    with cache_file.open('wb') as stream:stream.truncate(64*1024*1024+1)
    assert build()==(0,2,2,0,1,1)
    # Valid outer checksums must not turn malformed compiler metadata into
    # reusable state. The compiler rejects it and the driver retries cold.
    checksum=temp/'checksum'
    run(['clang','-std=c11','-O2',ROOT/'tests/module-cache-checksum.c','-o',checksum])
    def unpack(text):
        fields=[]
        while text:
            count,text=text.split('\n',1);count=int(count)
            fields.append(text[:count]);text=text[count:]
        return fields
    def pack(fields):return ''.join(str(len(field))+'\n'+field for field in fields)
    for payload in ('broken state', 'table'):
        envelope=unpack(cache_file.read_text())
        if payload=='table':
            state=unpack(envelope[4]);state[2]='invalid checked type table';payload=pack(state)
        file=temp/'payload';file.write_text(payload)
        envelope[3]=run([checksum,file]).stdout.strip();envelope[4]=payload
        cache_file.write_text(pack(envelope))
        assert build()==(0,2,2,0,1,1)
    # Corrupt or non-executable immutable compiler images lose a hit rather
    # than preventing a build or causing a different compiler to execute.
    images=cache/'compiler-images'
    image=next(images.iterdir());image.write_bytes(b'corrupt executable')
    assert build()==(2,0,0,2,0,0)
    valid=next(p for p in images.iterdir() if p.read_bytes()==compiler.read_bytes())
    valid.chmod(0o600)
    assert build()==(2,0,0,2,0,0)
    good=cache_file.read_bytes();last_output=output.read_bytes()
    build(tool=ROOT/'build/minyarc',success=False)
    assert cache_file.read_bytes()==good and output.read_bytes()==last_output
    entry.write_text(source.replace('library.answer()','library.missing()'))
    failure=build(success=False)
    assert 'has no function named' in failure.stderr
    assert cache_file.read_bytes()==good
    assert output.read_bytes()==last_output,'failed build replaced a successful output'
    entry.write_text(source)
    assert build()==(2,0,0,2,0,0)
    # A publication failure must not publish new program state or leak the
    # generated program, candidate state or compiler snapshot.
    entry.write_text(source+'\nprint(5)\n')
    build(target=temp/'absent-directory'/'out.ll',success=False)
    assert cache_file.read_bytes()==good
    entry.write_text(source)

    def overlapping(index):
        target=temp/f'parallel-{index}.ll';counters=temp/f'parallel-{index}.stats'
        run([DRIVER,compiler,entry,target,cache,counters])
        return target.read_bytes(),counters.read_text()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results=list(executor.map(overlapping,range(4)))
    assert all(data==last_output for data,_ in results)
    assert not list(cache.glob('invocation.*'))
    assert build()==(2,0,0,2,0,0)

    # A distinct compiler binary changes cache identity even though it
    # implements the same language and emits equivalent output.
    alternative=temp/'compiler-O1'
    run(['clang','-O1','-Wno-override-module','-flto',ROOT/'build/module-compiler-stage2.ll',ROOT/'build/minyar-compiler-runtime.ll','-o',alternative])
    assert alternative.read_bytes()!=compiler.read_bytes()
    assert build(tool=alternative)==(0,2,2,0,1,1)
    assert build(tool=alternative)==(2,0,0,2,0,0)
    assert build(tool=compiler)==(0,2,2,0,1,1)
    def mixed(index):
        tool=compiler if index%2 else alternative
        target=temp/f'mixed-{index}.ll';counter=temp/f'mixed-{index}.stats'
        run([DRIVER,tool,entry,target,cache,counter])
        return target.read_bytes()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(mixed,range(2)))
    assert all(data==last_output for data in results)
    assert not list(cache.glob('invocation.*'))

    odd=temp/'space λ "quote" | suffix';odd.mkdir()
    odd_source=odd/'main.min';odd_source.write_text('print("héllo λ")\n')
    odd_cache=odd/'cache';odd_output=odd/'program.ll';odd_stats=odd/'stats'
    run([DRIVER,compiler,odd_source,odd_output,odd_cache,odd_stats])
    run([DRIVER,compiler,odd_source,odd_output,odd_cache,odd_stats])
    assert tuple(map(int,odd_stats.read_text().split()[:6]))==(1,0,0,1,0,0)
    run(['clang','-O0','-Wno-override-module',odd_output,ROOT/'build/minyar-runtime.o','-o',odd/'program'])
    assert run([odd/'program']).stdout=='héllo λ\n'

print('native module driver: identity, same-time source edits, corruption, failure atomicity, overlapping builds and Unicode paths verified')
