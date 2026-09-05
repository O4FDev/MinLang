#!/usr/bin/env python3
"""Count generic drop work and detect an unsafe shared-child mutation.

Counters are injected into copied headers. Mutants must compile before a
runtime failure can count as detection."""
import argparse,hashlib,json,os,runpy,shutil,subprocess,tempfile
from pathlib import Path

def main():
    here=Path(__file__).resolve().parent
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-source',type=Path,default=here.parent/'runtime/minyar_runtime.c')
    p.add_argument('--clang',default='clang')
    p.add_argument('--output-dir',type=Path)
    args=p.parse_args()
    if args.output_dir:args.output_dir.mkdir(exist_ok=True,parents=True)
    evidence=Path(tempfile.mkdtemp(prefix='minyar-fused-work-',dir=args.output_dir)).resolve()
    original=(args.runtime_source.parent/'minyar_bounded_rc.h').read_text()
    unfuse=runpy.run_path(str(here/'fused-unary-regressions.py'))['without_fusion']
    variants={'counter-reference':unfuse(original),'counter-candidate':original,'unsafe-shared-mutant':original}
    marker='static unsigned rc_drop(void *value) {'
    for name in ['counter-reference','counter-candidate']:
        assert variants[name].count(marker)==1
        variants[name]=variants[name].replace(marker,'static size_t generic_drop_calls;\n'+marker+'\n    generic_drop_calls++;')
    guard='child->ownership == (8 | RC_RECORD)'
    assert variants['unsafe-shared-mutant'].count(guard)==1
    variants['unsafe-shared-mutant']=variants['unsafe-shared-mutant'].replace(guard,'(child->ownership & 7) == RC_RECORD')
    report={'status':'running','checks':[],'runtime_sha256':hashlib.sha256(original.encode()).hexdigest()}
    def save():(evidence/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    def execute(label,command):
        r=subprocess.run(command,capture_output=True,text=True,timeout=120,
                         env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
        (evidence/(label+'.log')).write_text(r.stdout+r.stderr)
        report['checks'].append({'label':label,'command':command,'returncode':r.returncode});save()
        return r
    print(evidence,flush=True);save()
    try:
        for name,header in variants.items():
            directory=evidence/name;shutil.copytree(args.runtime_source.parent,directory/'runtime');(directory/'tests').mkdir()
            (directory/'runtime/minyar_bounded_rc.h').write_text(header)
            fixture='unary-order.c' if name=='unsafe-shared-mutant' else 'fused-drop-work.c'
            shutil.copy2(here/fixture,directory/'tests'/fixture)
            binary=directory/'test'
            r=execute(name+'-compile',[args.clang,'-O2','-fsanitize=address,undefined',str(directory/'tests'/fixture),'-o',str(binary)])
            assert r.returncode==0,(name,'compile failure is not mutation evidence',r.stderr)
            r=execute(name,[str(binary)])
            if name=='counter-candidate':assert r.returncode==0,r.stderr
            elif name=='counter-reference':assert r.returncode!=0 and 'generic_drop_calls-before==1' in r.stderr,r.stderr
            else:assert r.returncode!=0 and 'freed_count' in r.stderr,r.stderr
            print(name,'expected result verified',flush=True)
        report['status']='passed'
    except Exception as error:report.update(status='failed',error=str(error));raise
    finally:save()
    print(evidence/'results.json',flush=True)

if __name__=='__main__':main()
