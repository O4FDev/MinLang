from pathlib import Path
import hashlib,json,os,subprocess,time
root=Path('/home/user/ws3/constants')
out=root/'build/module-constant-matrix'; out.mkdir(parents=True,exist_ok=True)
profiles={'eager':[], 'system-k1':['-DMINYAR_SYSTEM_HEAP=1','-DMINYAR_RC_POLL_BUDGET=1'], 'system-k32':['-DMINYAR_SYSTEM_HEAP=1'], 'fixed':['-DMINYAR_BOUNDED_HEAP=1'], 'lazy':['-DMINYAR_BOUNDED_HEAP=1','-DMINYAR_LAZY_HEAP=1']}
report={'status':'running','profiles':list(profiles),'checks':[],'inputs':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['compiler/compiler.min','runtime/minyar_runtime.c','tests/module-constants.py','tests/module-constant-graphs.py']}}
def run(label,argv,env=None):
    began=time.monotonic()
    with (out/(label+'.log')).open('w') as log: r=subprocess.run(argv,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
    report['checks'].append({'label':label,'argv':list(map(str,argv)),'status':r.returncode,'seconds':time.monotonic()-began})
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    if r.returncode: raise SystemExit(label+' failed: '+str(out/(label+'.log')))
contract=(root/'tests/memory-contracts-runtime.c').read_text()
for mode in ('native','sanitize'):
    flags=['-O2'] if mode=='native' else ['-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer']
    for name,profile in profiles.items():
        wrapper=out/(name+'-'+mode+'.c'); runtime=wrapper.with_suffix('.o')
        wrapper.write_text(contract.replace('#include "../runtime/minyar_runtime.c"', '#include "'+str(root/'runtime/minyar_runtime.c')+'"'))
        run('build-'+name+'-'+mode,['clang-22',*flags,*profile,'-c',str(wrapper),'-o',str(runtime)])
        for frontend in ('minyarc','minyarc-modules','minyarc-callbacks','minyarc-errors'):
            env=dict(os.environ,MINYAR_TEST_COMPILER=str(root/'build'/frontend),MINYAR_TEST_RUNTIME=str(runtime),MINYAR_TEST_CLANG='clang-22',MINYAR_TEST_LINK_FLAGS='-fsanitize=address,undefined' if mode=='sanitize' else '',ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1')
            run(frontend+'-'+name+'-'+mode,['python3','tests/module-constants.py'],env)
env=dict(os.environ,MINYAR_TEST_CLANG='clang-22')
run('traced-module-root',['python3','tests/module-constant-graphs.py'],env)
run('self-fixed-point',['cmp','build/compiler-stage2.ll','build/compiler-stage3.ll'])
report['status']='pass'; (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'pass','checks':len(report['checks']),'evidence':str(out/'results.json')}))
