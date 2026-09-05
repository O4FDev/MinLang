#!/usr/bin/env python3
"""Measure the complete native cache driver against direct production builds."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('graphs',ROOT/'tests/module-performance.py')
graphs=importlib.util.module_from_spec(spec);spec.loader.exec_module(graphs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes',type=int,nargs='+',default=[100,400])
    parser.add_argument('--shapes',nargs='+',choices=['chain','wide','shared'],default=['chain','wide','shared'])
    parser.add_argument('--repeats',type=int,default=5)
    parser.add_argument('--compiler',type=Path,default=ROOT/'build/minyarc-modules',help='Incremental compiler binary to freeze for this measurement')
    parser.add_argument('--output',type=Path,default=ROOT/'build/incremental-module-performance.json')
    parser.add_argument('--link', action='store_true', help='Include native object generation and linking at O0')
    parser.add_argument('--enforce',action='store_true',help='Enforce broad CPU regression ceilings on substantial graphs')
    args=parser.parse_args()
    if args.repeats<1 or any(n<1 for n in args.sizes):parser.error('positive sizes and repeats required')
    report={'platform':platform.platform(),'includes_native_link':args.link,'method':__doc__,'rows':[],'artifacts':{}}
    with tempfile.TemporaryDirectory(prefix='minyar-driver-perf-') as name:
        temp=Path(name)
        for label,file in [('driver','minyar-module-build'),('compiler','minyarc-modules'),('production','minyarc')]:
            source=args.compiler.resolve() if label=='compiler' else ROOT/'build'/file
            report['artifacts'][label]=hashlib.sha256(source.read_bytes()).hexdigest()
            shutil.copy2(source,temp/label)
        shutil.copy2(ROOT/'build/minyar-runtime.o', temp/'runtime.o')
        report['artifacts']['runtime']=hashlib.sha256((temp/'runtime.o').read_bytes()).hexdigest()
        report['clang']=subprocess.run(['clang','--version'],capture_output=True,text=True,check=True).stdout
        for shape in args.shapes:
            for count in args.sizes:
                d=temp/f'{shape}-{count}'
                entry,_=graphs.generate(d,shape,count,4,12)
                original=entry.read_text();library=d/'m0.min';lib_original=library.read_text()
                cache=d/'cache';stats=d/'stats.txt'
                driver=[temp/'driver',temp/'compiler',entry,d/'cached.ll',cache,stats]
                production=[temp/'production',entry,d/'production.ll']
                graphs.timed(driver)
                cache_file=next(cache.glob('*.cache'));baseline=cache_file.read_bytes()
                for scenario in ('unchanged','entry-edit','dependency-edit','interface-edit','cold'):
                    entry.write_text(original);library.write_text(lib_original)
                    if scenario=='entry-edit':entry.write_text(original.replace('    print(','    let changed = 1\n    print('))
                    if scenario=='dependency-edit':library.write_text(lib_original.replace('result = result + 1','result = result + 2',1))
                    if scenario=='interface-edit':library.write_text(lib_original+'\npublic record Added { value: Integer }\n')
                    samples={'production':[],'driver':[]};counts=[]
                    graphs.timed(production)
                    for repeat in range(args.repeats+1):
                        # Each edited repetition starts from the original cache.
                        cache_file.with_suffix('.cache.delta').unlink(missing_ok=True)
                        if scenario=='cold':cache_file.unlink(missing_ok=True)
                        else:cache_file.write_bytes(baseline)
                        order=['production','driver'] if repeat%2 else ['driver','production']
                        for label in order:
                            result=graphs.timed(driver if label=='driver' else production)
                            if args.link:
                                linked=graphs.timed(['clang','-O0','-Wno-override-module',d/('cached.ll' if label=='driver' else 'production.ll'),temp/'runtime.o','-o',d/(label+'-program')])
                                result['frontend_ms']={metric:result[metric] for metric in ('cpu_ms','wall_ms')}
                                result['link_ms']=linked
                                for metric in ('cpu_ms','wall_ms'):result[metric]+=linked[metric]
                            if repeat:samples[label].append(result)
                        counters=stats.read_text().split()
                        if scenario=='unchanged':assert tuple(map(int,counters[:6]))==(count+1,0,0,count+1,0,0),counters
                        if scenario in ('entry-edit','dependency-edit'):assert int(counters[1])==1,counters
                        if scenario=='cold':assert int(counters[0])==0 and int(counters[1])==count+1,counters
                        if repeat:counts.append(' '.join(counters))
                        assert not list(cache.glob('invocation.*'))
                    row={'shape':shape,'modules':count,'scenario':scenario,'samples':samples,'counters':counts,
                         'median_ms':{label:{metric:statistics.median(r[metric] for r in rows) for metric in ('cpu_ms','wall_ms')} for label,rows in samples.items()},'cache_bytes':len(baseline),'result_cache_bytes':sum(p.stat().st_size for p in cache.glob('*.cache*')),'delta_bytes':sum(p.stat().st_size for p in cache.glob('*.delta'))}
                    report['rows'].append(row)
                    args.output.write_text(json.dumps(report,indent=2)+'\n')
                    print(shape,count,scenario,json.dumps(row['median_ms']),flush=True)
                    if args.enforce and not args.link and count>=400 and row['median_ms']['production']['cpu_ms']>=20:
                        ceiling=3.5 if scenario=='cold' else (1.8 if scenario=='interface-edit' else 1.05)
                        assert row['median_ms']['driver']['cpu_ms']<=row['median_ms']['production']['cpu_ms']*ceiling,(shape,count,scenario,'incremental CPU ceiling exceeded')


if __name__=='__main__':main()
