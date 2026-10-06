#!/usr/bin/env python3
"""Bounded round9 real GL composition controls; no performance inference."""
import argparse
import datetime
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory/evidence/native-application-round9'
ACCEPTED = {'runtime/native/graphics.c': '736bc64a8bea8edb134d7752cdb9ad9f0f3e8174cbe0ef7f716e4698e8f33eed',
            'runtime/minyar_runtime.c': 'c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def prepare(evidence):
    triangle = [[8, 8], [56, 8], [32, 56]]
    small = [[16, 16], [40, 16], [28, 40]]
    inputs = {}
    def pack(name, z, color, u=.75, reverse=False, positions=None):
        positions = positions or [(-.75, -.75, z), (.75, -.75, z), (0, .75, z)]
        if reverse:
            positions = positions[::-1]
        inputs[name] = b''.join(struct.pack('<10f', *p, u, .5, *color, 1., 0.) for p in positions)
    pack('near-half', -.5, [.5]*3)
    pack('far-full', .5, [1.]*3)
    pack('near-discard', -.5, [1.]*3, u=.25)
    pack('near-full', -.5, [1.]*3)
    pack('far-half', .5, [.5]*3)
    pack('near-reversed', -.5, [1.]*3, reverse=True)
    pack('middle-full', 0, [1.]*3)
    pack('camera-replacement', -2, [1.]*3, positions=[(0, -1, -2), (1.5, -1, -2), (.75, .5, -2)])
    expected = {'fixed_before_compilation': True, 'tolerance_codes': 2, 'edge_exclusion_pixels': 2,
                'origin': 'bottom-left', 'dimensions': [64, 64], 'clear_rgba': [32, 64, 128, 255],
                'atlas_rgba': [[192, 64, 32, 127], [32, 160, 224, 128]],
                'cases': [
                    {'name': 'depth-order', 'triangle': triangle, 'interior': [16, 80, 112, 255], 'hypothesis': 'near half-color at depth.25 wins against later far full-color at depth.75'},
                    {'name': 'alpha-discard-depth', 'triangle': triangle, 'interior': [32, 160, 224, 255], 'hypothesis': 'alpha127/255<.5 discarded near fragments write neither color nor depth; later far alpha128 texel visible'},
                    {'name': 'alpha128-survives', 'triangle': triangle, 'interior': [32, 160, 224, 255], 'hypothesis': 'alpha128/255>.5 survives, writes depth and shader output alpha1; later far half-color rejected'},
                    {'name': 'translucent-blend', 'triangle': triangle, 'interior': [24, 120, 168, 191], 'hypothesis': 'CW near triangle visible with culling disabled; sourceRGB*.5+destinationRGB*.5 and sourceA*.5+destinationA*.5=.75'},
                    {'name': 'translucent-no-depth-write', 'triangle': triangle, 'interior': [32, 160, 224, 255], 'hypothesis': 'later middle depth.5 passes against retained far depth.75; subsequent far draw fails, opaque alpha1 and restored depth write'},
                    {'name': 'camera-replacement', 'triangle': small, 'interior': [32, 160, 224, 255], 'hypothesis': 'public replacement upload on existing handle and setCamera(1,0,0,0,0,90); square aspect, cot45=1, ndc=(x-1,y)/2 gives window(16,16),(40,16),(28,40)'}],
                'derivation': 'Flat UV.25/.75 samples respective base-level texel centers with zero derivatives; light1,sky1,glow0 give brightness1; all fog distances<100. RGBA8 half-color equals(16,80,112,255); blend RGB=(full+half)/2, alpha=.75*255=191.25 quantizes191. Clear(.125,.25,.5,1) quantizes(32,64,128,255). Independent signed half-plane distances classify centers; exclude2px margin; no measured pixels set expectations.'}
    for name, payload in inputs.items():
        (evidence / (name + '.bin')).write_bytes(payload)
    save(evidence / 'expected-pixels.json', expected)
    return expected


def oracle(payload, expected, case):
    assert len(payload) == 16384
    counts = {'interior': 0, 'background': 0, 'excluded': 0}
    errors = []; maximum = 0
    vertices = case['triangle']
    for y in range(64):
        for x in range(64):
            ds = []
            for a, b in zip(vertices, vertices[1:] + vertices[:1]):
                dx, dy = b[0]-a[0], b[1]-a[1]
                ds.append((dx*(y+.5-a[1])-dy*(x+.5-a[0]))/math.hypot(dx, dy))
            if min(ds) >= expected['edge_exclusion_pixels']:
                kind, want = 'interior', case['interior']
            elif min(ds) <= -expected['edge_exclusion_pixels']:
                kind, want = 'background', expected['clear_rgba']
            else:
                counts['excluded'] += 1
                continue
            counts[kind] += 1
            got = list(payload[(y*64+x)*4:(y*64+x+1)*4])
            error = max(abs(a-b) for a, b in zip(got, want))
            maximum = max(maximum, error)
            if error > expected['tolerance_codes']:
                if len(errors) < 4:
                    errors.append({'xy': [x,y], 'got': got, 'want': want, 'error': error})
    return {'case': case['name'], 'passed': not errors, 'counts': counts,
            'maximum_channel_error_codes': maximum, 'first_mismatches': errors}


# Adapted from the frozen round6 monitored helper. Separate compile/native limits,
# durable samples and retention on infrastructure failures are round9 additions.
def monitored(label, argv, work, evidence, report, limit):
    outpath, errpath = evidence/(label+'.stdout'), evidence/(label+'.stderr')
    command = ['/usr/bin/time', '-l', *map(str, argv)]
    start = time.monotonic(); sampled = 0; failure = None; samples = []
    with outpath.open('w') as out, errpath.open('w') as err:
        child = subprocess.Popen(command, cwd=work, stdout=out, stderr=err, start_new_session=True)
        while child.poll() is None:
            try:
                result = subprocess.run(['ps','-axo','pid=,ppid=,rss='], capture_output=True, text=True, timeout=2)
                assert result.returncode == 0
                rows = [tuple(map(int,row.split())) for row in result.stdout.splitlines()]
                descendants = {child.pid}
                while True:
                    more = descendants | {pid for pid,parent,_ in rows if parent in descendants}
                    if more == descendants: break
                    descendants = more
                rss = sum(rss*1024 for pid,_,rss in rows if pid in descendants)
                sampled = max(sampled, rss)
                samples.append({'elapsed': time.monotonic()-start,'rss_bytes':rss,'pids':sorted(descendants)})
            except Exception as error:
                failure = 'sampling_failure:'+repr(error)
            if sampled > limit: failure = 'sampled_rss_limit'
            if time.monotonic()-start > 30: failure = 'wall_limit'
            if failure:
                os.killpg(child.pid, signal.SIGKILL); break
            time.sleep(.05)
        child.wait(timeout=2)
    wall = time.monotonic()-start
    match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', errpath.read_text(), re.M)
    peak = int(match[1]) if match else None
    row = {'label':label,'argv':command,'cwd':str(work),'returncode':child.returncode,
           'wall_seconds':wall,'sampled_process_group_peak_rss_bytes':sampled,
           'darwin_time_child_peak_rss_bytes':peak,'limit_failure':failure,'rss_threshold_bytes':limit,
           'rss_note':'50ms nominal sampling with ps overhead can miss peaks; OS child high-water retained separately; neither measures GPU/driver memory or imposes hard OS cap.',
           'stdout':str(outpath.relative_to(ROOT)),'stderr':str(errpath.relative_to(ROOT))}
    save(evidence/(label+'-samples.json'), samples)
    report['commands'].append(row); save(evidence/'results.json',report)
    assert child.returncode == 0 and not failure and wall <= 30 and peak is not None and peak <= limit, row


def run(args):
    evidence = BASE/args.label; evidence.mkdir(exist_ok=False)
    work = evidence/'disposable'; work.mkdir()
    report = {'status':'preparing','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'commands':[],'sources':[],'real_context_attempts':0,'production_edits':False,'mutation':args.mutant}
    try:
        for name, want in ACCEPTED.items(): assert digest(ROOT/name)==want
        old = json.loads((ROOT/'research/2026-10-memory/evidence/native-application-round6/first-control/results.json').read_text())
        runtime = old['objects'][0]; runtime_path = Path(runtime['path'])
        assert digest(runtime_path)==runtime['sha256']
        dependencies = [row for row in old['sources'] if row['path'].startswith('runtime/')]
        for row in dependencies: assert digest(ROOT/row['path'])==row['sha256'], row
        report['runtime_object']=runtime
        frozen=evidence/'sources'
        names=[r['path'] for r in dependencies]+['tests/native-research-round9.c','tests/native-research-round9.py','LICENSE','library/graphics.min','research/2026-10-memory/native-application-round9-preregistered.json']
        for name in names:
            target=frozen/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/name,target)
            report['sources'].append({'path':name,'sha256':digest(target)})
        if args.mutant:
            baseline=BASE/'baseline'
            assert json.loads((baseline/'results.json').read_text())['status']=='baseline_passed'
            for name in ['tests/native-research-round9.c','tests/native-research-round9.py']:
                assert digest(frozen/name)==digest(baseline/'sources'/name)
            for path in baseline.glob('*.bin'):
                if not path.name.endswith('-rgba8.bin'): shutil.copy2(path,evidence/path.name)
            shutil.copy2(baseline/'expected-pixels.json',evidence/'expected-pixels.json')
            expected=json.loads((evidence/'expected-pixels.json').read_text())
            source=frozen/'runtime/native/graphics.c'; before=source.read_text()
            proposal=json.loads((ROOT/'research/2026-10-memory/native-application-round9-mutations.json').read_text())
            mutant=next(m for m in proposal['mutations'] if m['name']==args.mutant)
            assert before.count(mutant['anchor'])==1
            after=before.replace(mutant['anchor'],mutant['replacement']); source.write_text(after)
            (evidence/'single-source.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='accepted-graphics.c',tofile=args.mutant+'-graphics.c')))
            report['mutant_renderer_sha256']=digest(source)
            report['mutant_proposal_sha256']=digest(ROOT/'research/2026-10-memory/native-application-round9-mutations.json')
        else:
            expected=prepare(evidence)
        for case in expected['cases']:
            proof=oracle(bytes(16384),expected,case)
            case['preregistered_region_counts']=proof['counts']
        if not args.mutant: save(evidence/'expected-pixels.json',expected)
        report['expected_sha256']=digest(evidence/'expected-pixels.json')
        report['input_hashes']={p.name:digest(p) for p in evidence.glob('*.bin')}
        for path in evidence.glob('*.bin'): shutil.copy2(path,work/path.name)
        compiler=Path(shutil.which('clang'))
        report['compiler']={'path':str(compiler),'sha256':digest(compiler),'version':subprocess.check_output([compiler,'--version'],text=True)}
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','glfw3'],text=True))
        libs=shlex.split(subprocess.check_output(['pkg-config','--libs','glfw3'],text=True))
        report['status']='preregistered_before_compile'; save(evidence/'results.json',report)
        obj=work/'fixture.o'; binary=work/'fixture'
        monitored('compile-o2',[compiler,'-std=c11','-Wall','-Wextra','-Werror','-O2',*flags,'-c',frozen/'tests/native-research-round9.c','-o',obj],work,evidence,report,512*1024**2)
        report['fixture_object_sha256']=digest(obj)
        monitored('link-o2',[compiler,'-O2',obj,runtime_path,*libs,'-framework','OpenGL','-lm','-o',binary],work,evidence,report,512*1024**2)
        report['binary_sha256']=digest(binary)
        report['real_context_attempts']=1; report['status']='native_started';save(evidence/'results.json',report)
        monitored('native-o2',[binary,'--bounded-hidden64'],work,evidence,report,256*1024**2)
        observations=[json.loads(line) for line in (evidence/'native-o2.stdout').read_text().splitlines()]
        report['driver_observations']=observations
        cleanup=next(r for r in observations if r['kind']=='cleanup')
        assert cleanup['completed'] and cleanup['context_destroyed'] and cleanup['gl_error']==0
        state_rows=[r for r in observations if r['kind']=='state']
        for row in state_rows:
            assert row['depth_test']==1 and row['cull']==1 and row['blend']==0 and row['depth_write']==1
            assert row['depth_func']==513 and row['cull_mode']==1029 and row['front']==2305
        report['pixel_oracles']=[]
        for case in expected['cases']:
            name=case['name']+'-rgba8.bin'; shutil.copy2(work/name,evidence/name)
            report['pixel_oracles'].append(oracle((evidence/name).read_bytes(),expected,case))
        passed=all(r['passed'] for r in report['pixel_oracles'])
        report['status']=('mutant_detected' if not passed else 'mutant_survived') if args.mutant else ('baseline_passed' if passed else 'production_red_pending_review')
        report['output_hashes']={p.name:digest(p) for p in evidence.glob('*-rgba8.bin')}
        assert (not passed if args.mutant else passed), report['pixel_oracles']
    except Exception as error:
        report['failure']=repr(error)
        if report['status'] not in ('production_red_pending_review','mutant_survived'):
            report['status']='infrastructure_or_fixture_failure'
        raise
    finally:
        for p in work.glob('*-rgba8.bin'):
            if not (evidence/p.name).exists():shutil.copy2(p,evidence/p.name)
        report['accepted_sources_unchanged']={name:digest(ROOT/name)==want for name,want in ACCEPTED.items()}
        report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        if report['status'] in ('baseline_passed','mutant_detected'):
            shutil.rmtree(work);report['successful_disposables_removed']=True
        else:report['failed_disposables_retained']=True
        save(evidence/'results.json',report)
        print(json.dumps({'status':report['status'],'evidence':str(evidence),'pixel_oracles':report.get('pixel_oracles')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--mutant',choices=['alpha-discard-disabled','translucent-depth-write'])
    args=parser.parse_args()
    assert re.fullmatch('[a-z0-9-]+',args.label)
    run(args)
