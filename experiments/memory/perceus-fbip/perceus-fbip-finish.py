#!/usr/bin/env python3
"""BX-only alternating native batches and durable FBIP evidence, after PMU runs."""
import hashlib
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import tarfile

root = Path('build/perceus-measurement-20261020').resolve()
out = root/'fbip'
campaigns = {arm:root/'runs'/('fbip-'+arm) for arm in ['control','candidate']}
names = ['c2min-1024-migrated','c2min-16384-migrated',
         'safelibs-zlib-large-candidate','safelibs-png-large-candidate','safelibs-jpeg-large-candidate']
commands = {}
for arm,path in campaigns.items():
    raw = json.loads((path/'counter-config.json').read_text())['commands']
    commands[arm] = {name:next(row['argv'] for row in raw if row['name']==name) for name in names}
allowed = sorted(os.sched_getaffinity(0))
os.sched_setaffinity(0,{allowed[0]})
timing = {'method':'one warmup then nine alternating seeded-random arm pairs; fixed baseline operation counts; native warmed same-process loops; one available CPU; no performance threshold',
          'cpu':allowed[0],'workloads':{},'commands':commands}
rng = random.Random(0x50455243)
for name in names:
    rows = []
    timing['workloads'][name] = {'pairs':rows}
    for sample in range(-1,9):
        order = ['control','candidate']
        rng.shuffle(order)
        row = {'sample':sample,'warmup':sample==-1,'order':order}
        for arm in order:
            process = subprocess.run(commands[arm][name],capture_output=True,text=True,timeout=60)
            row[arm] = {'exit':process.returncode,'stdout':process.stdout,'stderr':process.stderr}
            if process.returncode:
                (out/'timings.json').write_text(json.dumps(timing,indent=2)+'\n')
                raise RuntimeError('native paired worker failed')
            value = json.loads(process.stdout)
            row[arm]['native'] = value
            row[arm]['ns_per_operation'] = (value['seconds']*1e9 if name.startswith('c2min-')
                                             else value['wall_ns'])/value['iterations']
        if row['control']['native']['iterations'] != row['candidate']['native']['iterations']:
            raise RuntimeError('different paired operation counts')
        if name.startswith('c2min-'):
            if row['control']['native']['checksum'] != row['candidate']['native']['checksum']:
                raise RuntimeError('paired tokenizer output mismatch')
        else:
            if (row['control']['native']['final_fnv1a64'] != row['candidate']['native']['final_fnv1a64']
                or any(row[arm]['native']['live_objects'] != 0 for arm in order)):
                raise RuntimeError('paired codec output/cleanup mismatch')
        row['candidate_over_control'] = row['candidate']['ns_per_operation']/row['control']['ns_per_operation']
        rows.append(row)
        (out/'timings.json').write_text(json.dumps(timing,indent=2)+'\n')
    measured = [row for row in rows if not row['warmup']]
    timing['workloads'][name]['medians_ns_per_operation'] = {
        arm:statistics.median(row[arm]['ns_per_operation'] for row in measured) for arm in ['control','candidate']}
    timing['workloads'][name]['median_paired_candidate_over_control'] = statistics.median(
        row['candidate_over_control'] for row in measured)
    (out/'timings.json').write_text(json.dumps(timing,indent=2)+'\n')
    print(name,json.dumps(timing['workloads'][name]['medians_ns_per_operation']),flush=True)
sites = {}
for arm,directory in campaigns.items():
    paths = [directory/('compiler-'+profile+'.ll') for profile in ['arena','eager','bounded']]
    paths += [directory/'products/c2min/build/native-O2/tokenizer.raw.ll',
              directory/'products/safelibs/build/baseline/codecs.original.ll']
    sites[arm] = {str(path.relative_to(directory)): {
        'reuse_calls':len(re.findall(r'^\s*%[^\n=]+ = call ptr @minyar_record_reuse_scalar_take\(',path.read_text(),re.M)),
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths}
(out/'eligible-sites.json').write_text(json.dumps(sites,indent=2)+'\n')
archive = root/'fbip-evidence.tar.gz'
with tarfile.open(archive,'w:gz') as bundle:
    for relative in ['archives.json','frames-instructions.py','perceus-measure-fbip.py',
                     'perceus-compare-measurements.py','fbip/source-control-manifest.json',
                     'fbip/control-bootstrap.log','fbip/control-measurement.log',
                     'fbip/candidate-measurement.log','fbip/comparison.json',
                     'fbip/eligible-sites.json','fbip/timings.json','fbip/synthetic',
                     'runs/fbip-control','runs/fbip-candidate']:
        bundle.add(root/relative,arcname=relative)
print('FBIP_EVIDENCE_ARCHIVE',hashlib.sha256(archive.read_bytes()).hexdigest(),archive,flush=True)
