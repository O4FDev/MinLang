#!/usr/bin/env python3
"""Compare unary batching against a copied runtime with batching removed.

Native and ASan/UBSan runs check exact queue/count/cursor/turn transcripts for
requested budgets 1..33 and configured budgets 1/32/1024. They also check
allocation-reverse free order with retained aliases."""
import argparse, hashlib, json, os
from pathlib import Path
import shutil, subprocess, tempfile

def main():
    here=Path(__file__).resolve().parent
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-source',type=Path,default=here.parent/'runtime/minyar_runtime.c')
    p.add_argument('--clang',default='clang')
    p.add_argument('--output-dir',type=Path)
    args=p.parse_args()
    runtime=args.runtime_source.resolve()
    if args.output_dir: args.output_dir.mkdir(parents=True,exist_ok=True)
    evidence=Path(tempfile.mkdtemp(prefix='minyar-unary-pair-tests-',dir=args.output_dir)).resolve()
    for version in ['candidate','reference']:
        shutil.copytree(runtime.parent,evidence/version/'runtime')
        (evidence/version/'tests').mkdir()
        for name in ['unary-order.c','pair-transcript.c']:
            shutil.copy2(here/name,evidence/version/'tests'/name)
    reference=evidence/'reference/runtime/minyar_bounded_rc.h'
    s=reference.read_text()
    begin=s.index('            /* With one unvisited unary record, locality makes its field visit')
    end=s.index('            /* A ready recent task',begin)
    # Fusion has a carried pair and a terminal pair; remove both together.
    # Runtime transcripts still verify exact charged work at every boundary.
    assert s[begin:end].count('work += 2;') in (1, 2)
    reference.write_text(s[:begin]+s[end:])
    report={'status':'running','checks':[],'source_sha256':{},
            'reference_transformation':'Remove only the sole-unvisited-unary pair fast path; retain the unary locality scheduler.',
            'requested_budgets':list(range(1,34)),'configured_budgets':[1,32,1024]}
    for path in evidence.rglob('*'):
        if path.is_file(): report['source_sha256'][str(path.relative_to(evidence))]=hashlib.sha256(path.read_bytes()).hexdigest()
    def save(): (evidence/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(label,command):
        checked=subprocess.run(command,capture_output=True,timeout=120,
                               env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:abort_on_error=1',
                                    'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'})
        (evidence/(label+'.stdout')).write_bytes(checked.stdout)
        (evidence/(label+'.stderr')).write_bytes(checked.stderr)
        report['checks'].append({'label':label,'command':command,'returncode':checked.returncode});save()
        assert checked.returncode==0,(label,checked.stderr.decode(errors='replace')[-5000:])
        return checked.stdout
    save();print(evidence,flush=True)
    try:
        for mode,flags in [('native',[]),('sanitize',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
            for budget in [1,32,1024]:
                outputs=[]
                for version in ['reference','candidate']:
                    label=f'{mode}-k{budget}-{version}'
                    binary=evidence/label
                    run(label+'-compile',[args.clang,'-O2',*flags,f'-DMINYAR_RC_POLL_BUDGET={budget}',
                        str(evidence/version/'tests/pair-transcript.c'),'-o',str(binary)])
                    outputs.append(run(label,[str(binary)]))
                assert outputs[0]==outputs[1],(mode,budget,'scheduler transcript mismatch')
                label=f'{mode}-k{budget}-free-order';binary=evidence/label
                run(label+'-compile',[args.clang,'-O2',*flags,f'-DMINYAR_RC_POLL_BUDGET={budget}',
                    str(evidence/'candidate/tests/unary-order.c'),'-o',str(binary)])
                run(label,[str(binary)])
                print(mode,budget,'exact transcript/free order/2N units passed',flush=True)
        report['status']='passed'
    except Exception as error:
        report.update(status='failed',error=str(error));raise
    finally:save()
    print(evidence/'results.json',flush=True)

if __name__=='__main__':main()
