from pathlib import Path
import hashlib, importlib.util, json, os, shutil, stat, subprocess
ROOT=Path(__file__).resolve().parents[1]
records=[]
manifest=json.loads((ROOT/'build/httpserver-r1-fix-inputs.json').read_text())
def check_inputs():
    for row in manifest['files']:
        p=ROOT/row['path']; assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'] and oct(stat.S_IMODE(p.stat().st_mode))==row['mode'],row['path']
    assert hashlib.sha256((ROOT/'build/minyarc-baseline').read_bytes()).hexdigest()==manifest['compiler_sha256']
    assert hashlib.sha256((ROOT/'build/httpserver-baseline-runtime.ll').read_bytes()).hexdigest()==manifest['runtime_ir_sha256']
def run(command, env=None):
    result=subprocess.run([str(x) for x in command],cwd=ROOT,env=env,text=True,capture_output=True,timeout=90)
    row=dict(command=[str(x) for x in command],exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)
    if env:row['configuration']={k:env[k] for k in ['MINYAR_CLANG_FLAGS','MINYAR_NATIVE_FLAGS','ASAN_OPTIONS','UBSAN_OPTIONS'] if k in env}
    records.append(row); print(result.stdout,end='');print(result.stderr,end='')
    assert result.returncode==0,row

def compile(source,name,release,debug,runtime,env=None):
    ll='build/'+name+'.ll';binary='build/'+name
    run(['build/minyarc-baseline',source,ll,'--bounded-owners','32','--library','library'])
    run(['python3','tools/clang-driver.py','link',ROOT,ll,runtime,binary,str(release),str(debug),source],env)
    return binary

status='failed'
try:
    check_inputs()
    shutil.copyfile('/home/user/ws4/baseline/build/minyar-default-runtime.o',ROOT/'build/httpserver-r1-runtime.o')
    for mode,release,debug in [('debug',0,1),('release',1,0),('sanitize',0,0)]:
        check_inputs();env=None
        runtime='build/httpserver-baseline-runtime.ll' if release else 'build/httpserver-r1-runtime.o'
        if mode=='sanitize':
            flags='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wno-override-module'
            env=os.environ.copy();env.update(MINYAR_CLANG_FLAGS=flags,MINYAR_NATIVE_FLAGS=flags,ASAN_OPTIONS='detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1')
            runtime='build/httpserver-r1-sanitize-runtime.o'
            run(['clang',*flags.split(),'-c','runtime/minyar_default_runtime.c','-o',runtime],env)
        server=compile('tests/httpserver.min','httpserver-r1-'+mode,release,debug,runtime,env)
        observer=compile('tests/httpserver-write-wait.min','httpserver-r1-write-'+mode,release,debug,runtime,env)
        run(['python3','tests/httpserver.py','--binary',server,'--write-binary',observer],env)
    unit=compile('tests/httpserver-cache.min','httpserver-r1-cache',1,0,'build/httpserver-baseline-runtime.ll')
    run([ROOT/unit])
    front=compile('benchmarks/httpserver/front.min','httpserver-r1-front',1,0,'build/httpserver-baseline-runtime.ll')
    spec=importlib.util.spec_from_file_location('cmp',ROOT/'benchmarks/httpserver/compare.py');cmp=importlib.util.module_from_spec(spec);spec.loader.exec_module(cmp)
    queries=['a b','second','third','fourth'];bodies=[json.dumps(dict(query=q,total_us=1000)).encode() for q in queries]
    output=ROOT/'build/httpserver-r1-front-check';output.mkdir(exist_ok=True)
    with cmp.replay(queries,bodies,[0.001]*4) as upstream:
        cmp.verify_lru(ROOT/front,upstream.server_port,queries,bodies,output)
        cmp.verify_hol(ROOT/front,upstream,queries,bodies,output)
    cmp.controls();records.append(dict(command=['actual cache-front independent raw bytes/LRU/causal HoL and gate controls'],exit_code=0))
    run(['python3','tests/suite-catalogue.py'])
    check_inputs();status='passed'
finally:
    paths=['build/minyarc-baseline','build/httpserver-baseline-runtime.ll','runtime/minyar_runtime.c','runtime/minyar_default_runtime.c','runtime/native/net.c','compiler/compiler.min','tools/clang-driver.py']
    paths += [str(p.relative_to(ROOT)) for p in (ROOT/'runtime').rglob('*.h')]
    paths += [str(p.relative_to(ROOT)) for p in (ROOT/'build').glob('httpserver-r1-*.o')]
    paths += [str(p.relative_to(ROOT)) for p in (ROOT/'build/native').glob('*.o')]
    data=dict(source=manifest,status=status,records=records,artifacts={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},tools={t:subprocess.check_output([t,'--version'],text=True) for t in ['clang','python3']})
    (ROOT/'build/httpserver-r1-qualification.json').write_text(json.dumps(data,indent=2)+'\n')
print('R1 exact-source debug/release/ASan/UBSan/LSan plus all prior wire/front controls passed')
