#!/usr/bin/env python3
"""Explicitly opt-in paired CPU primitive observation; no production modification."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import re
import resource
import shutil
import signal
import statistics
import subprocess
import tempfile
import time
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('calibration', ROOT/'tests/memory-research-list-bulk-cpu-calibration.py')
calibration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibration)
bulk = calibration.bulk
MAX_CPU = 180.0
MAX_WALL = 600.0
CHILD_CPU = 5


def xor_to(value):
    return [value, 1, value + 1, 0][value % 4] if value >= 0 else 0


def combined_checksum(checksum, repetitions):
    end = checksum + repetitions - 1
    if end <= calibration.MASK:
        return xor_to(end) ^ xor_to(checksum - 1)
    return xor_to(calibration.MASK) ^ xor_to(checksum - 1) ^ xor_to(end & calibration.MASK)


def interval(values):
    ordered = sorted(values)
    return [ordered[int((len(ordered)-1)*p)] for p in [0.025, 0.975]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquire', action='store_true', help='Requires coordinator release; no default execution.')
    args = parser.parse_args()
    if not args.acquire:
        parser.error('Acquisition is held unless --acquire is explicitly supplied after coordinator release.')
    parent = ROOT/'build/memory-research-list-bulk-cpu'
    parent.mkdir(parents=True,exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-',dir=parent))
    started = time.monotonic()
    usage_origin = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {'status':'running','checks':[],'pairs':[],'pilots':[],'binaries':[],
              'scope':'Primitive append/checksum/release/drain CPU; debt control includes debt construction; no application/hard-latency claim.',
              'host':'Paced system soak and external loaded host; no quiet-window claim.',
              'limit_scope':'Observed aggregate CPU checks between children, remaining-wall child timeout; last-child overshoot retained as failure.'}
    proposal = ROOT/'research/2026-10-memory/runtime-list-bulk-cpu-proposal.json'
    shutil.copyfile(proposal,evidence/'proposal.json')
    entry = {str(p):bulk.digest(p) for p in (ROOT/'runtime').glob('minyar_*') if p.is_file()}
    frozen = {}

    def save():
        (evidence/'results.json').write_text(json.dumps(report,indent=2)+'\n')

    def aggregate_cpu():
        now=resource.getrusage(resource.RUSAGE_CHILDREN)
        return now.ru_utime+now.ru_stime-usage_origin.ru_utime-usage_origin.ru_stime

    def limits():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU,(CHILD_CPU,CHILD_CPU))
        resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024*1024,8*1024*1024))

    def execute(label,command,native=False,assembly=False):
        elapsed=time.monotonic()-started
        spent=aggregate_cpu()
        assert MAX_CPU-spent>=CHILD_CPU and MAX_WALL-elapsed>0, ('budget-before-child',label,spent,elapsed)
        wrapped=['/usr/bin/time','-l','/usr/sbin/taskpolicy','-m','128',*command] if native else command
        before_cpu=aggregate_cpu(); before=time.monotonic()
        process=subprocess.Popen(wrapped,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                                 preexec_fn=limits,env={**os.environ,'LC_ALL':'C'})
        timeout=False
        try:
            out,err=process.communicate(timeout=min(10.0,MAX_WALL-elapsed))
        except subprocess.TimeoutExpired:
            timeout=True
            os.killpg(process.pid,signal.SIGKILL)
            out,err=process.communicate()
        row={'label':label,'command':wrapped,'returncode':process.returncode,'timed_out':timeout,
             'observer_wall_seconds':time.monotonic()-before,'observed_child_cpu_seconds':aggregate_cpu()-before_cpu,
             'aggregate_child_cpu_seconds':aggregate_cpu(),'runner_elapsed_seconds':time.monotonic()-started,'stdout':out,'stderr':err}
        if assembly:
            path=evidence/(label+'.s')
            path.write_text(out)
            row.update(stdout='',assembly_file=str(path.relative_to(evidence)),assembly_sha256=bulk.digest(path))
        if native:
            peak=re.search(r'(\d+)\s+maximum resident set size',err)
            row['peak_rss_bytes']=int(peak.group(1)) if peak else None
        report['checks'].append(row);save()
        assert not timeout and process.returncode==0,row
        assert row['aggregate_child_cpu_seconds']<=MAX_CPU and row['runner_elapsed_seconds']<=MAX_WALL,('budget-after-child',row)
        if native:
            assert row['peak_rss_bytes'] is not None and row['peak_rss_bytes']<=128*1024*1024,row
            row['observation']=json.loads(out)
            assert row['observation']['kind']=='result' and row['observation']['recovered'],row
        save();return row

    def run_binary(variant,profile,length,mode,repetitions,label):
        binary=evidence/variant/profile
        assert bulk.digest(binary)==frozen[str(binary)]
        checksum=calibration.expected(length,mode)
        row=execute(label,[str(binary),str(length),str(repetitions),str(mode),f'{calibration.SEED:x}',f'{checksum:x}'],True)
        observed=row['observation']
        assert observed['repetitions']==repetitions and observed['cpu_nanoseconds']>0,row
        assert observed['checksum']==f'{combined_checksum(checksum,repetitions):016x}',row
        assert bulk.digest(binary)==frozen[str(binary)]
        return len(report['checks'])-1

    try:
        execute('toolchain',['clang','--version'])
        execute('sdk',['xcrun','--show-sdk-path'])
        execute('linker',['xcrun','--find','ld'])
        report['compiler_executable']={'path':shutil.which('clang'),'sha256':bulk.digest(Path(shutil.which('clang')))}
        for variant in ['baseline','candidate']:
            directory=evidence/variant
            shutil.copytree(ROOT/'runtime',directory/'runtime',ignore=shutil.ignore_patterns('native'))
            (directory/'tests').mkdir()
            for name in ['memory-research-list-bulk-cpu.c','memory-research-list-bulk-checksum.c',
                         'memory-research-list-bulk-cpu-calibration.py','memory-research-list-bulk.py',
                         Path(__file__).name,'clang_helpers.py']:
                shutil.copyfile(ROOT/'tests'/name,directory/'tests'/name)
            if variant=='candidate':bulk.candidate(directory/'runtime')
            checksum=directory/'checksum.o'
            execute('compile-checksum-'+variant,clang_command(['clang','-std=c11','-O2','-c',
                    str(directory/'tests/memory-research-list-bulk-checksum.c'),'-o',str(checksum)]))
            execute('checksum-assembly-'+variant,clang_command(['clang','-std=c11','-O2','-S',
                    str(directory/'tests/memory-research-list-bulk-checksum.c'),'-o','-']),assembly=True)
            for profile in ['system','fixed']:
                binary=directory/profile
                defines=['-DMINYAR_SYSTEM_HEAP=1'] if profile=='system' else ['-DMINYAR_BOUNDED_HEAP=1','-DMINYAR_BOUNDED_HEAP_BYTES=16777216']
                command=['clang','-std=c11','-O2',*defines,'-DMINYAR_RC_POLL_BUDGET=32','-Wall','-Wextra','-Werror',
                         str(directory/'tests/memory-research-list-bulk-cpu.c')]
                execute('compile-'+variant+'-'+profile,clang_command([*command,str(checksum),'-o',str(binary)]))
                execute('fixture-assembly-'+variant+'-'+profile,clang_command([*command,'-S','-o','-']),assembly=True)
                execute('linked-machine-code-'+variant+'-'+profile,['otool','-tvV',str(binary)],assembly=True)
                assembly=(evidence/('fixture-assembly-'+variant+'-'+profile+'.s')).read_text()
                assert re.search(r'\bbl\s+_research_checksum\b',assembly), 'Opaque checksum call eliminated'
                consume=(evidence/('checksum-assembly-'+variant+'.s')).read_text()
                assert re.search(r'\b(?:ldr|ldp)\b',consume), 'Checksum has no observable loads'
                report['binaries'].append({'path':str(binary.relative_to(evidence)),'sha256':bulk.digest(binary)})
        for p in evidence.rglob('*'):
            if p.is_file() and p.name not in ['results.json']:
                frozen[str(p)]=bulk.digest(p)
        cases=[(profile,length,mode) for profile in ['system','fixed'] for length,mode in calibration.CASES]
        repetitions={}
        for profile,length,mode in cases:
            count=128
            while True:
                index=run_binary('baseline',profile,length,mode,count,f'pilot-{profile}-n{length}-mode{mode}-r{count}')
                cpu=report['checks'][index]['observation']['cpu_nanoseconds']/1e9
                report['pilots'].append({'case':[profile,length,mode],'repetitions':count,'check':index,'measured_cpu_seconds':cpu});save()
                if cpu>=0.12:
                    assert cpu<=0.5,('pilot-overshoot',profile,length,mode,count,cpu)
                    repetitions[(profile,length,mode)]=count
                    break
                assert count<1048576,('pilot-target-not-reached-at-cap',profile,length,mode,count,cpu)
                count*=2
        randomizer=random.Random(0x6b17)
        plan=[]
        for block in range(12):
            order=list(cases);randomizer.shuffle(order)
            for case in order:
                variants=['baseline','candidate']
                if randomizer.getrandbits(1):variants.reverse()
                plan.append({'block':block,'case':list(case),'order':variants,'repetitions':repetitions[case]})
        inputs=evidence/'inputs-and-order.json'
        inputs.write_text(json.dumps(plan,indent=2)+'\n');frozen[str(inputs)]=bulk.digest(inputs)
        report['planned_pairs']=plan;save()
        for pair in plan:
            profile,length,mode=pair['case']; indices={}
            for variant in pair['order']:
                indices[variant]=run_binary(variant,profile,length,mode,pair['repetitions'],
                        f'pair{pair["block"]}-{profile}-n{length}-mode{mode}-{variant}')
            ratio=report['checks'][indices['baseline']]['observation']['cpu_nanoseconds']/report['checks'][indices['candidate']]['observation']['cpu_nanoseconds']
            report['pairs'].append({**pair,'checks':indices,'baseline_over_candidate_ratio':ratio});save()
        summaries=[]
        for case in cases:
            values=[p['baseline_over_candidate_ratio'] for p in report['pairs'] if p['case']==list(case)]
            assert len(values)==12
            rng=random.Random(0x6b17)
            geom=[];med=[]
            for _ in range(10000):
                sample=[rng.choice(values) for _ in values]
                geom.append(math.exp(statistics.mean(math.log(v) for v in sample)));med.append(statistics.median(sample))
            ratio=math.exp(statistics.mean(math.log(v) for v in values));median=statistics.median(values)
            row={'case':list(case),'ratios':values,'geometric_ratio':ratio,'geometric_interval95':interval(geom),
                 'median_ratio':median,'median_interval95':interval(med),'worst_paired_slowdown':max(1/v-1 for v in values)}
            profile,length,mode=case
            row['criterion_passed']=(ratio>=1.05 and row['geometric_interval95'][0]>1) if mode==0 and length>=1024 else (
                ratio>=0.97 and median>=0.97 and row['worst_paired_slowdown']<=0.10)
            summaries.append(row)
        assert len(report['pairs'])==192
        assert all(bulk.digest(Path(p))==value for p,value in frozen.items())
        assert all(bulk.digest(Path(p))==value for p,value in entry.items())
        report.update(status='completed-observation',summaries=summaries,criteria_passed=all(r['criterion_passed'] for r in summaries),
                      frozen_artifacts=frozen,production_entry_hashes=entry,aggregate_child_cpu_seconds=aggregate_cpu(),runner_wall_seconds=time.monotonic()-started)
    except BaseException as error:
        report.update(status='failed',failure=repr(error),aggregate_child_cpu_seconds=aggregate_cpu(),runner_wall_seconds=time.monotonic()-started)
        raise
    finally:
        save();print('Results: '+str(evidence/'results.json'),flush=True)


if __name__=='__main__':main()
