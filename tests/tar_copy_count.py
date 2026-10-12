"""Non-timing copy counters for a prepared tar benchmark; Linux --wrap only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
from tar import ROOT, tar_provider
from clang_helpers import clang_command


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,default=ROOT/'build/tar-native-benchmark')
    parser.add_argument('--artifacts',type=Path,required=True)
    args=parser.parse_args()
    if platform.system()!='Linux': parser.error('this counter requires the Linux --wrap linker')
    args.artifacts.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((args.work/'manifest.json').read_text())
    for path,digest in manifest['sources'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,('changed prepared input',path)
    for entry in manifest['provider']['inputs']:
        assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256']
    clang=os.environ.get('MINYAR_TEST_CLANG','clang')
    cflags,libraries=tar_provider(clang,('-O2',))
    binary=args.artifacts/'copy-count'
    command=clang_command([clang,'-O2','-Wno-override-module',*cflags,args.work/'minyar.ll',args.work/'runtime.o',
        ROOT/'runtime/native/tararchive.c',ROOT/'tests/tar_copy_count.c','-Wl,--wrap=minyar_bytes_slice',
        '-Wl,--wrap=minyar_bytes_extend',*libraries,'-o',binary])
    subprocess.run(command,check=True,timeout=60)
    receipt={'prepared_manifest':manifest,'compile_command':[str(x) for x in command],'runs':{},'counter_source_hashes':{}}
    for path in [ROOT/'tests/tar_copy_count.c',ROOT/'tests/tar_copy_count.py',args.work/'minyar.ll',binary]:
        receipt['counter_source_hashes'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    for operation in ['read','roundtrip']:
        run=[binary,operation,args.work/'payload.tar','1']
        result=subprocess.run(run,text=True,capture_output=True,check=True,timeout=30)
        expected=subprocess.check_output([args.work/'minyar',operation,args.work/'payload.tar','1'],text=True).strip()
        assert result.stdout.strip()==expected
        counts=json.loads(result.stderr)
        receipt['runs'][operation]={'command':[str(x) for x in run],'observable':expected,'counts':counts}
    read=receipt['runs']['read']['counts']; write=receipt['runs']['roundtrip']['counts']
    assert read['large_slices']==read['large_extends']==0
    assert write['large_slices']==write['large_extends']==1
    assert write['large_slice_bytes']==write['large_extend_bytes']==4228096
    (args.artifacts/'results.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({operation:data['counts'] for operation,data in receipt['runs'].items()}))


if __name__=='__main__': main()
