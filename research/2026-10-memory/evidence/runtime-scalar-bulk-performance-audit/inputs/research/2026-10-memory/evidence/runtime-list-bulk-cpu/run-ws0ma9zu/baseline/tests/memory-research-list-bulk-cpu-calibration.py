#!/usr/bin/env python3
"""Only untimed full-value/eligibility calibration; does not acquire CPU pairs."""
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bulk', ROOT / 'tests/memory-research-list-bulk.py')
bulk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bulk)
MASK = (1 << 64) - 1
SEED = 0x51F37
CASES = [(n, 0) for n in [0, 2, 31, 32, 1024, 8193]] + [(31, 1), (31, 2)]


def expected(length, mode):
    words = ([1] * (length + 1)) if mode == 2 else [
        (SEED + i * 0x9e3779b97f4a7c15) & MASK for i in range(length)] + [0xfedcba9876543210]
    checksum = 0xcbf29ce484222325
    for word in words:
        checksum = ((checksum ^ word) * 0x100000001b3) & MASK
    return checksum


def main():
    parent = ROOT/'build/memory-research-list-bulk-cpu-calibration'
    parent.mkdir(parents=True,exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-',dir=parent))
    report = {'status':'running','scope':'Untimed correctness/count calibration only; CPU fields observed but not analyzed','checks':[],'binaries':[]}
    frozen = {str(p):bulk.digest(p) for p in (ROOT/'runtime').glob('minyar_*') if p.is_file()}
    prelude = (ROOT/'tests/memory-research-list-bulk.c').read_text().split('#undef memcpy')[0]
    prelude += '\n#undef memcpy\n#define memcpy research_copy\n'
    shutil.copyfile(ROOT/'research/2026-10-memory/runtime-list-bulk-cpu-proposal.json',evidence/'proposal.json')

    def save():
        (evidence/'results.json').write_text(json.dumps(report,indent=2)+'\n')

    def limits():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU,(30,30))
        resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024*1024,8*1024*1024))

    def execute(label,command):
        process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,preexec_fn=limits)
        timeout=False
        try:
            out,err=process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timeout=True
            os.killpg(process.pid,signal.SIGKILL)
            out,err=process.communicate()
        row={'label':label,'command':command,'returncode':process.returncode,'stdout':out,'stderr':err,'timed_out':timeout}
        report['checks'].append(row); save()
        assert not timeout and process.returncode==0,row
        row['observations']=[json.loads(s) for s in out.splitlines() if s.startswith('{')]
        save(); return row

    try:
        execute('toolchain',['clang','--version'])
        for variant in ['baseline','candidate']:
            directory=evidence/variant
            shutil.copytree(ROOT/'runtime',directory/'runtime',ignore=shutil.ignore_patterns('native'))
            (directory/'tests').mkdir()
            for name in ['memory-research-list-bulk-cpu.c','memory-research-list-bulk-checksum.c',
                         'memory-research-list-bulk.py','memory-research-list-bulk.c',Path(__file__).name,'clang_helpers.py']:
                shutil.copyfile(ROOT/'tests'/name,directory/'tests'/name)
            (directory/'tests/count-prelude.h').write_text(prelude)
            if variant=='candidate':bulk.candidate(directory/'runtime')
            bulk.instrument(directory/'runtime')
            checksum=directory/'checksum.o'
            execute('compile-checksum-'+variant,clang_command(['clang','-std=c11','-O2','-c',
                    str(directory/'tests/memory-research-list-bulk-checksum.c'),'-o',str(checksum)]))
            report['binaries'].append({'path':str(checksum.relative_to(evidence)),'sha256':bulk.digest(checksum)})
            for profile in ['system','fixed']:
                label=variant+'-'+profile
                binary=directory/label
                defines=['-DMINYAR_SYSTEM_HEAP=1'] if profile=='system' else ['-DMINYAR_BOUNDED_HEAP=1','-DMINYAR_BOUNDED_HEAP_BYTES=16777216']
                execute('compile-'+label,clang_command(['clang','-std=c11','-O2',*defines,'-DMINYAR_RC_POLL_BUDGET=32',
                    '-DMINYAR_RESEARCH_COUNT=1','-Wall','-Wextra','-Werror',str(directory/'tests/memory-research-list-bulk-cpu.c'),
                    str(checksum),'-o',str(binary)]))
                report['binaries'].append({'path':str(binary.relative_to(evidence)),'sha256':bulk.digest(binary)})
                for length,mode in CASES:
                    row=execute(f'{label}-n{length}-mode{mode}', ['/usr/sbin/taskpolicy','-m','128',str(binary),
                        str(length),'1',str(mode),f'{SEED:x}',f'{expected(length,mode):x}'])
                    assert len(row['observations'])==2,row
                    counts,result=row['observations']
                    assert bool(counts['guard_pending'])==(mode==1),counts
                    assert counts['adds']==(1 if variant=='candidate' and mode==0 else length+1),counts
                    assert result['checksum']==f'{expected(length,mode):016x}' and result['recovered'],result
        assert all(bulk.digest(Path(p))==v for p,v in frozen.items())
        report.update(status='passed',production_frozen_hashes=frozen)
    except BaseException as error:
        report.update(status='failed',failure=repr(error));raise
    finally:
        save();print('Results: '+str(evidence/'results.json'),flush=True)


if __name__=='__main__':main()
