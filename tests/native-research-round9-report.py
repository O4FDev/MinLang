#!/usr/bin/env python3
"""Audit saved round9 bytes/provenance; never compile or create a context."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'research/2026-10-memory/evidence/native-application-round9'
RESEARCH = ROOT/'research/2026-10-memory'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def main():
    spec=importlib.util.spec_from_file_location('saved_round9',BASE/'baseline/sources/tests/native-research-round9.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cohorts=[]; calibrations=[]
    expected=json.loads((BASE/'baseline/expected-pixels.json').read_text())
    baseline=json.loads((BASE/'baseline/results.json').read_text())
    for label in ('baseline','alpha-discard-disabled','translucent-depth-write'):
        folder=BASE/label; result=json.loads((folder/'results.json').read_text())
        assert result['status']==('baseline_passed' if label=='baseline' else 'mutant_detected')
        assert result['expected_sha256']==digest(folder/'expected-pixels.json')==baseline['expected_sha256']
        assert result['input_hashes']==baseline['input_hashes']
        for name in ('tests/native-research-round9.c','tests/native-research-round9.py'):
            assert digest(folder/'sources'/name)==digest(BASE/'baseline/sources'/name)
        assert result['accepted_sources_unchanged']=={k:True for k in module.ACCEPTED}
        assert result['successful_disposables_removed'] and not (folder/'disposable').exists()
        for case,saved in zip(expected['cases'],result['pixel_oracles']):
            payload=(folder/(case['name']+'-rgba8.bin')).read_bytes()
            assert digest(folder/(case['name']+'-rgba8.bin'))==result['output_hashes'][case['name']+'-rgba8.bin']
            assert module.oracle(payload,expected,case)==saved
            assert saved['counts']==case['preregistered_region_counts']
            if not saved['passed']:
                mismatch_count=0; observed=set(); vertices=case['triangle']
                for y in range(64):
                    for x in range(64):
                        ds=[]
                        for a,b in zip(vertices,vertices[1:]+vertices[:1]):
                            dx,dy=b[0]-a[0],b[1]-a[1]
                            ds.append((dx*(y+.5-a[1])-dy*(x+.5-a[0]))/math.hypot(dx,dy))
                        if min(ds)>=2:
                            got=tuple(payload[(y*64+x)*4:(y*64+x+1)*4]);observed.add(got)
                            mismatch_count+=max(abs(a-b) for a,b in zip(got,case['interior']))>2
                calibrations.append({'cohort':label,'case':case['name'],'interior_mismatches':mismatch_count,
                                     'all_interior_observed_rgba':[list(v) for v in sorted(observed)],
                                     'expected_rgba':case['interior'],'maximum_channel_error_codes':saved['maximum_channel_error_codes'],
                                     'other_readbacks_exact':all(r['maximum_channel_error_codes']==0 for r in result['pixel_oracles'] if r['case']!=case['name'])})
        cohorts.append({'label':label,'status':result['status'],'result':str((folder/'results.json').relative_to(ROOT)),
                        'contexts':result['real_context_attempts'],'pixel_oracles':result['pixel_oracles'],'resources':result['commands']})
    frozen=json.loads((BASE/'baseline-frozen-manifest.json').read_text())
    assert all(digest(BASE/'baseline'/p)==sha for p,sha in frozen.items())
    inputs=json.loads((BASE/'input-manifest.json').read_text())
    immutable=[r for r in inputs if 'round4' in r['path'] or 'round6' in r['path'] or 'round8' in r['path']]
    assert all(digest(ROOT/r['path'])==r['sha256'] for r in immutable)
    changes=[]
    for name,sha in json.loads((BASE/'entry-tracked-hashes.json').read_text()).items():
        if not (ROOT/name).is_file() or digest(ROOT/name)!=sha:changes.append(name)
    checks=[]
    formatter='/Users/luke/.cache/uv/archive-v0/qir4EsQDYRgTcgFN/clang_format/data/bin/clang-format'
    for cmd in ([formatter,'--version'],[formatter,'--dry-run','--Werror','tests/native-research-round9.c'],
                ['git','diff','--check','--','tests/native-research-round9.c','tests/native-research-round9.py','tests/native-research-round9-report.py']):
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        checks.append({'argv':cmd,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
        assert proc.returncode==0
    owned=[ROOT/'tests/native-research-round9.c',ROOT/'tests/native-research-round9.py',Path(__file__)]
    for p in owned:
        text=p.read_text();assert text.endswith('\n') and all(line==line.rstrip() for line in text.splitlines())
        if p.suffix=='.py':compile(text,str(p),'exec')
    verification={'baseline_files_unchanged':len(frozen),'selected_historical_files_unchanged':len(immutable),
                  'all_entry_tracked_count':len(json.loads((BASE/'entry-tracked-hashes.json').read_text())),
                  'concurrent_tracked_changes_outside_lane':changes,'checks':checks,'python_syntax':'passed',
                  'owned_whitespace':'passed','accepted_sources_unchanged':{name:digest(ROOT/name)==want for name,want in module.ACCEPTED.items()},
                  'scope':'Only saved manifests are certified; unrelated historical artifacts outside these manifests are not retrospectively certified.'}
    save(BASE/'verification.json',verification)
    summary={'status':'round9_completed','production_defects_observed':0,'production_edits':False,'campaign_finished':False,
             'earliest_campaign_finish_utc':'2026-10-04 06:54:29 UTC','baseline_contract_groups':4,
             'baseline_readbacks':6,'baseline_pixel_observations_checked':21408,'baseline_excluded_pixel_observations':3168,
             'separate_source_mutants_detected':2,'native_contexts_total':3,'native_executions_total':3,'cohorts':cohorts,
             'calibrations':calibrations,'fixture_or_infrastructure_failures_encountered':0,
             'baseline_expected_sha256':baseline['expected_sha256'],'baseline_frozen_files_unchanged':len(frozen),
             'counts_policy':'Four distinct composition groups use six readbacks. Repeated image-pixel observations and mutant cohorts remain separate; no new broad feature/group counts added from post-hoc saved-byte audit.',
             'remaining_gaps':['nonzero yaw/pitch, non-square aspect, arbitrary projection/near/far clipping','varying UV/color/sky/glow and perspective interpolation','fog/light saturation and broader alpha/opacity samples','actual overlays/glyphs/lines','large atlas/noisy texture and cloud occupancy GPU integration','default multisample framebuffer/presentation/events/input','public screenshot/PNG real-driver integration','managed Bytes lifetime, core owner/deferred accounting, whole-game lifecycle and production teardown','driver/GPU allocations, physical reclamation, throughput/latency/HFT/performance']}
    save(RESEARCH/'native-application-round9-results.json',summary)
    print(json.dumps({'status':summary['status'],'verification':verification,'calibrations':calibrations},indent=2))


if __name__=='__main__':
    main()
