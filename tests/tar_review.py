"""Completed-review regressions, also invoked by the full tar suite.

--artifacts retains source hashes, exact commands and all per-case outcomes.
No extraction, timing, compiler bootstrap or provider installation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from tar import ROOT, FOOTER, header, pax_record, oracle, build_program
from tar_support import strict_scan
from clang_helpers import asan_leak_options


def bound_fixtures():
    def x(pairs, global_=False):
        return header('metadata',b''.join(pax_record(k,v) for k,v in pairs),b'g' if global_ else b'x')
    first=x([('A',b'a'*80)],True)+header('first')
    cases=[]
    for value,label in [(b'','delete'),(b'a','replace')]:
        for pairs,order in [([('B',b'b'*20),('A',value)],'add-first'),([('A',value),('B',b'b'*20)],'override-first')]:
            cases.append((label+'-'+order,first+x(pairs)+header('second')+FOOTER,100,True))
            cases.append(('global-'+label+'-'+order,first+x(pairs,True)+header('second')+FOOTER,100,True))
    for size,success in [(18,True),(19,False)]:
        cases.append(('effective-bytes-'+str(81+1+size),first+x([('B',b'b'*size)])+header('second')+FOOTER,100,success))
    globals=[('K'+str(i),b'v') for i in range(4096)]
    first=x(globals,True)+header('first')
    for pairs,label,success in [([('NEW',b'v'),('K0',b'')],'count-add-first',True),
                                ([('K0',b''),('NEW',b'v')],'count-delete-first',True),
                                ([('NEW',b'v')],'count-overflow',False)]:
        cases.append((label,first+x(pairs)+header('second')+FOOTER,131072,success))
        cases.append(('global-'+label,first+x(pairs,True)+header('second')+FOOTER,131072,success))
    return cases


def run(work,sanitize=False,environment=None):
    work=Path(work); work.mkdir(parents=True,exist_ok=True)
    environment=environment or {**os.environ,'ASAN_OPTIONS':asan_leak_options()+':halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
    binary=build_program(work,ROOT/'tests/tar-review.min','review-contract',sanitize)
    cases=[]
    for count in [99,100,101]:
        path=b'/'+b'a'*count
        source=header('pax',pax_record('path',path),b'x')+header('fallback')+FOOTER
        cases.append(('absolute-'+str(len(path)),source,['path'],True))
    cases.append(('empty-hardlink',header('empty-hardlink',kind=b'1')+FOOTER,['hardlink'],True))
    bounds={}
    for name,source,maximum,success in bound_fixtures():
        spans,reason=strict_scan(source,max_metadata=maximum)
        assert (reason is None)==success,(name,'independent final bound',reason)
        assert len(spans)==(2 if success else 1),(name,'independent complete spans')
        bounds[name]=spans[-1][4] if success else None
        cases.append((name,source,['bound',str(maximum),'accept' if success else 'reject'],success))
    cases.append(('fresh-finish',None,['finish'],True))
    cases.append(('owned-finish',None,['owned'],True))
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in
            [ROOT/'library/tar.min',ROOT/'runtime/native/tararchive.c',ROOT/'tests/tar-review.min',ROOT/'tests/tar_review.py',ROOT/'tests/tar_support.py',ROOT/'tests/tar.py',ROOT/'runtime/minyar_runtime.c']}
    compiler=Path(os.environ.get('MINYAR_TEST_COMPILER',ROOT/'build/minyarc'))
    hashes[str(compiler)]=hashlib.sha256(compiler.read_bytes()).hexdigest()
    for file in [binary,work/'review-contract.ll',work/'runtime.o']:
        if file.is_file(): hashes[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
    receipt={'started_utc':datetime.now(timezone.utc).isoformat(),'sanitize':sanitize,'source_hashes':hashes,'cases':[]}
    failures=[]
    for name,source,arguments,success in cases:
        input=work/(name+'.tar')
        if source is not None: input.write_bytes(source)
        prefix=work/(name+'-out-')
        if arguments[0]=='bound': command=[binary,'bound',input,*arguments[1:]]
        elif arguments[0] in ('finish','owned'): command=[binary,arguments[0]]
        else: command=[binary,arguments[0],input,prefix]
        result=subprocess.run(command,text=True,capture_output=True,env=environment,timeout=30)
        problem=None
        if result.returncode or result.stderr: problem='public API regression'
        elif name in bounds and success:
            attrs={bytes.fromhex(k):bytes.fromhex(v) for line in result.stdout.splitlines() if line.startswith('ATTR|') for _,k,v in [line.split('|')]}
            if attrs!=bounds[name]: problem='independent effective attribute map'
        elif arguments[0] in ('path','hardlink'):
            for rewrite in range(2):
                output=Path(str(prefix)+str(rewrite)+'.tar').read_bytes()
                if oracle(output)!=oracle(source): problem='Python writer metadata roundtrip'
        case={'name':name,'command':[str(x) for x in command],'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'problem':problem}
        if source is not None: case['fixture_sha256']=hashlib.sha256(source).hexdigest()
        receipt['cases'].append(case)
        if problem: failures.append(name)
        print('tar review '+name+(': FAIL' if problem else ': PASS'),flush=True)
    receipt['finished_utc']=datetime.now(timezone.utc).isoformat(); receipt['failures']=failures
    (work/'results.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert not failures,('completed-review regressions',failures,work/'results.json')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize',action='store_true')
    parser.add_argument('--artifacts',type=Path,required=True)
    args=parser.parse_args(); run(args.artifacts,args.sanitize)
