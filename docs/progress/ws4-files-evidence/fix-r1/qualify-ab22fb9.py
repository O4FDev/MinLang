"""Run exact committed files controls inside the assigned immutable-baseline overlay."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

SPACE = Path('/home/user/ws4/files-r2/fix-r1')
ROOT = SPACE/'source'
EVIDENCE = SPACE/'evidence'
manifest = json.loads((SPACE/'manifest.json').read_text())
assert hashlib.sha256((ROOT/'build/minyarc').read_bytes()).hexdigest() == manifest['compiler_sha256']
assert hashlib.sha256((ROOT/'runtime/minyar_runtime.c').read_bytes()).hexdigest() == manifest['unchanged_runtime_sha256']
for row in manifest['files']:
    path = ROOT/row['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], row
    assert oct(path.stat().st_mode&0o777) == row['mode'], row
sys.path.insert(0,str(ROOT/'tests'))
import importlib.util
spec=importlib.util.spec_from_file_location('retained_review',ROOT/'tests/neodb-review.py')
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
environment=dict(os.environ,MINYAR_TEST_CLANG='/usr/bin/clang',ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
records=[]
def run(name,command,timeout=60):
    begin=time.time()
    result=subprocess.run(list(map(str,command)),cwd=ROOT,env=environment,capture_output=True,timeout=timeout)
    (EVIDENCE/(name+'.log')).write_bytes(result.stdout+result.stderr)
    records.append(dict(name=name,command=list(map(str,command)),cwd=str(ROOT),exit_code=result.returncode,
                        started_unix=begin,finished_unix=time.time(),log=name+'.log'))
    (EVIDENCE/'results.json').write_text(json.dumps(dict(source_manifest=manifest,platform=platform.platform(),
          environment={k:environment[k] for k in ('MINYAR_TEST_CLANG','ASAN_OPTIONS','UBSAN_OPTIONS')},commands=records),indent=2)+'\n')
    print(f'{name}: exit {result.returncode}',flush=True)
    if result.returncode:
        print((result.stdout+result.stderr).decode(errors='replace')[-7000:],flush=True)
        raise SystemExit(result.returncode)
run('clang-version',['/usr/bin/clang','--version'])
run('focused-native',['python3','tests/files-focused.py'],timeout=120)
run('focused-sanitize',['python3','tests/files-focused.py','--sanitize'],timeout=120)
for label,flags in (('O0',['-O0']),('O2',['-O2']),('sanitize',['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'])):
    exe=EVIDENCE/('files-review-'+label)
    run('review-build-'+label,['/usr/bin/clang','-std=c11','-D_GNU_SOURCE','-DMINYAR_SYSTEM_HEAP=1',
         '-Wall','-Wextra','-Werror',*flags,ROOT/'tests/files-review.c',ROOT/'runtime/minyar_runtime.c','-pthread','-lm','-o',exe])
    for index,args in enumerate(review.CASES['files-review']):
        run(f'review-{label}-{index}',[exe,*args],timeout=10)
    exe=EVIDENCE/('files-sync-failures-'+label)
    run('sync-build-'+label,['/usr/bin/clang','-std=c11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror',*flags,
         ROOT/'tests/files-sync-failures.c','-pthread','-o',exe])
    run('sync-'+label,[exe],timeout=10)
print('exact R1 fix commit Linux qualification passed',flush=True)
