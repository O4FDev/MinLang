#!/usr/bin/env python3
"""Bounded actual-module atlas/sky pilot. No fresh core build or renderer linkage."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory/evidence/native-application-round8'
MATRIX = ROOT / 'research/2026-10-memory/evidence/native-application-round2/final-matrix'
FLAGS = {'o2': ['-O2'], 'o0': ['-O0'], 'sanitize': ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--modes', nargs='+', choices=FLAGS, default=['o2'])
    parser.add_argument('--approval-file', type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z0-9-]+', args.label)
    assert args.approval_file.is_file()
    evidence = BASE / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix='minyar-native-round8-'))
    sources = evidence / 'sources'
    sources.mkdir()
    report = {'status': 'preparing', 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'invocation': sys.argv, 'work': str(work), 'sources': [], 'commands': [], 'cohorts': [],
              'limits': {'children': 1, 'wall_seconds': 30, 'native_bytes': 128 * 1024**2, 'compiler_bytes': 512 * 1024**2},
              'scope': 'CPU capture seam only; private scalar symbol probes distinct from public generated module calls; no GPU, whole-game, allocation-accounting or performance claim.'}
    def save():
        write_json(evidence / 'results.json', report)
    def run(label, command, cwd, native=False, expected_rc=0):
        argv = ['/usr/bin/time', '-l', *map(str, command)]
        limit = report['limits']['native_bytes' if native else 'compiler_bytes']
        outpath, errpath = evidence / (label + '.stdout'), evidence / (label + '.stderr')
        start, samples, failure = time.monotonic(), [], None
        environment = dict(os.environ)
        environment.update(ASAN_OPTIONS='detect_leaks=0:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        with outpath.open('w') as stdout, errpath.open('w') as stderr:
            process = subprocess.Popen(argv, cwd=cwd, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
            while process.poll() is None:
                output = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], text=True, capture_output=True, timeout=2)
                rows = [tuple(map(int, line.split())) for line in output.stdout.splitlines() if line.strip()]
                children = {process.pid}
                while True:
                    expanded = children | {pid for pid, parent, rss in rows if parent in children}
                    if expanded == children:
                        break
                    children = expanded
                rss = [rss * 1024 for pid, parent, rss in rows if pid in children]
                samples.append({'wall_seconds': time.monotonic() - start, 'group_bytes': sum(rss), 'largest_process_bytes': max(rss, default=0)})
                if sum(rss) > limit:
                    failure = 'sampled_group_rss_limit'
                if time.monotonic() - start > 30:
                    failure = 'wall_limit'
                if failure:
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(.025)
            process.wait(timeout=2)
        elapsed = time.monotonic() - start
        stderr = errpath.read_text()
        peak = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', stderr, re.M)
        row = {'label': label, 'argv': argv, 'cwd': str(cwd), 'returncode': process.returncode,
               'supervised_wall_seconds': elapsed, 'sampled_group_peak_bytes': max((s['group_bytes'] for s in samples), default=0),
               'darwin_time_child_peak_bytes': int(peak[1]) if peak else None, 'limit_failure': failure,
               'native': native, 'stdout': outpath.name, 'stderr': errpath.name,
               'environment': {key: environment[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS')}}
        report['commands'].append(row)
        write_json(evidence / (label + '-rss-samples.json'), samples)
        save()
        assert not failure and peak and int(peak[1]) <= limit and elapsed <= 30, row
        assert process.returncode == expected_rc, row
        return row
    try:
        shutil.copyfile(args.approval_file, evidence / 'authorization.txt')
        paths = [ROOT / 'examples/craft' / name for name in ('textures.min', 'atmosphere.min', 'blocks.min', 'noise.min')]
        paths += [p for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()]
        paths += [ROOT / 'runtime/native/graphics.c'] + list((ROOT / 'library').glob('*.min'))
        paths += list((ROOT / 'tests').glob('native-research-round8*'))
        paths += [ROOT / 'tests/llvm_sanitizer.py']
        paths += [ROOT / p for p in ('README.md', 'docs/architecture.md', 'docs/testing.md', 'docs/performance.md', 'docs/runtime-memory.md', 'docs/toolchain.md', 'research/2026-10-memory/README.md', 'research/2026-10-memory/native-application-round8-preregistered.json')]
        for path in paths:
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            target = sources / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            report['sources'].append({'path': str(relative), 'sha256': digest(target)})
        report['historical_hashes'] = [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p)} for p in sorted((ROOT / 'research/2026-10-memory').glob('native-application*')) if p.is_file() and 'round8' not in p.name]
        (evidence / 'entry-status.txt').write_text(subprocess.run(['git', 'status', '--porcelain=v1'], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        (evidence / 'entry-production.patch').write_bytes(subprocess.run(['git', 'diff', '--binary', '--', 'examples/craft', 'runtime/native/graphics.c'], cwd=ROOT, capture_output=True, check=True).stdout)
        prior = json.loads((MATRIX / 'results.json').read_text())
        report['compiler_sha256'] = digest(ROOT / 'build/minyarc')
        assert report['compiler_sha256'] == prior['compiler_sha256']
        for row in prior['sources']:
            if row['path'].startswith('runtime/minyar_'):
                assert digest(ROOT / row['path']) == row['sha256'], row
        oracle = load_module('round8_oracle', sources / 'tests/native-research-round8-oracle.py')
        expected = oracle.expected_inputs()
        write_json(evidence / 'expected-inputs.json', expected)
        report['expectations_saved_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['expectations_sha256'] = digest(evidence / 'expected-inputs.json')
        report['source_inventory'] = [{'path': str(p.relative_to(sources)), 'sha256': digest(p),
            'functions': [{'name': m[1], 'line': p.read_text()[:m.start()].count('\n') + 1} for m in re.finditer(r'^(?:public )?function (\w+)\(', p.read_text(), re.M)]} for p in sorted((sources / 'examples/craft').glob('*.min'))]
        save()
        run('clang-identity', ['clang', '--version'], sources)
        llvm = work / 'application.ll'
        run('frontend', [ROOT / 'build/minyarc', sources / 'tests/native-research-round8.min', llvm, '--library', sources / 'library'], sources)
        shutil.copyfile(llvm, evidence / 'application.ll')
        headers = re.findall(r'^define [^\n]*', llvm.read_text(), re.M)
        tiled = [h for h in headers if re.fullmatch(r'define double @\.minyar\.fn\.\w+_tiled\(i64 %argument\.0, i64 %argument\.1, i64 %argument\.2, i64 %argument\.3, i64 %argument\.4\) \{', h)]
        assert len(tiled) == 1, tiled
        symbol = re.search(r'@(\S+)\(', tiled[0])[1]
        alias = sources / 'tests/native-research-round8-alias.h'
        alias.write_text('double round8_actual_tiled(long long, long long, long long, long long, long long)\n    __asm__("_' + symbol + '");\n')
        report['private_probe'] = {'emitted_signature': tiled[0], 'alias_sha256': digest(alias),
            'runtime_setup': 'Called only by scalar native wrapper during compiler-generated main, after emitted minyar_stack_enter, minyar_rc_enter(11), minyar_initialize_arguments, and argument read. Scalar arguments/return. Not a public-module call/ownership proof.'}
        text = (sources / 'runtime/native/graphics.c').read_text()
        signatures = re.findall(r'^(?:void|bool|long long|double) minyar_graphics_\w+\([^)]*\)', text, re.M)
        allowed = {'createMesh', 'addVertex', 'updateMesh', 'setLight', 'setFog', 'drawMesh'}
        fatal = [s for s in signatures if re.search(r'minyar_graphics_(\w+)\(', s)[1] not in allowed]
        assert len(signatures) == 39 and len(fatal) == 33
        seam = sources / 'tests/native-research-round8-fatal.c'
        seam.write_text('#include "runtime/minyar_native.h"\n' + '\n'.join(s + ' { fputs("unexpected graphics seam reached\\n", stderr); exit(91); }' for s in fatal) + '\n')
        report['capture'] = {'allowed_symbols': sorted(allowed), 'fatal_symbols': len(fatal), 'fatal_sha256': digest(seam), 'packing': 'Fixture converts eight double arguments to float32 and appends1/0 sky/glow; production native vertex packer not linked.'}
        report['generated_llvm'] = {'sha256': digest(llvm), 'definitions': len(headers)}
        for mode in args.modes:
            runtime = Path(prior['work']) / ('system-' + mode + '-runtime.o')
            original_compile = next(r for r in prior['commands'] if r['label'] == 'system-' + mode + '-runtime')
            expected_hashes = {'o2': 'becb749c61f922ea103e3e3276bd196c73bd3d3e0665bf9132eca336ebaaad0f', 'o0': '6cb53aca240971c57e918cc93644377ef201f0059a8686c270d3a1dc3f05fb24', 'sanitize': '59fc70be500587ea89ac46dc4e435f7dbbefb386f7fd7761b5781e5e3fb934df'}
            assert digest(runtime) == expected_hashes[mode]
            ir = work / (mode + '.ll')
            shutil.copyfile(llvm, ir)
            sanitizer = None
            if mode == 'sanitize':
                helper = load_module('llvm_sanitizer', sources / 'tests/llvm_sanitizer.py')
                helper.prepare_llvm_for_link(ir, FLAGS[mode])
                definitions = re.findall(r'^define [^\n]*', ir.read_text(), re.M)
                annotated = [h for h in definitions if re.search(r'\bsanitize_address\b', h[h.rfind(')') + 1:])]
                assert len(annotated) == len(definitions)
                sanitizer = {'definitions': len(definitions), 'sanitize_address': len(annotated), 'sha256': digest(ir), 'generated_UBSan': False, 'LSan': False, 'quarantine': 'default unchanged'}
                shutil.copyfile(ir, evidence / 'application-asan.ll')
            binary = work / mode
            run(mode + '-link', ['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', *FLAGS[mode], '-Wno-override-module', '-I', sources, ir, sources / 'tests/native-research-round8.c', seam, runtime, '-lm', '-o', binary], sources)
            directory = work / (mode + '-outputs')
            directory.mkdir()
            run(mode + '-native', [binary, 'contracts'], directory, native=True)
            validations = oracle.validate(directory, expected)
            counts = json.loads((evidence / (mode + '-native.stdout')).read_text())
            assert counts == validations['atmosphere']['capture_api_counts'], counts
            output = evidence / (mode + '-outputs')
            shutil.copytree(directory, output)
            cohort = {'mode': mode, 'final_flags': FLAGS[mode], 'runtime_sha256': digest(runtime), 'runtime_original_compile': original_compile,
                      'runtime_dependencies_verified': 11, 'generated_sanitizer': sanitizer, 'binary_sha256': digest(binary),
                      'validations': validations, 'groups': sum(r['groups'] for r in validations.values()),
                      'outputs': [{'name': p.name, 'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(output.iterdir())]}
            report['cohorts'].append(cohort)
            save()
        report['protected_changed'] = [r['path'] for r in report['sources'] + report['historical_hashes'] if digest(ROOT / r['path']) != r['sha256']]
        assert all(p == 'research/2026-10-memory/README.md' for p in report['protected_changed'])
        assert digest(ROOT / 'build/minyarc') == report['compiler_sha256']
        report['status'] = 'passed_bounded_cohorts'
        report['completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
        shutil.rmtree(work)
        report['disposable_outputs_removed'] = True
        save()
        print(json.dumps({'status': report['status'], 'groups': sum(c['groups'] for c in report['cohorts']), 'evidence': str(evidence)}))
    except Exception as error:
        report.update(status='failed_preserved', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    main()
