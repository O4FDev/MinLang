#!/usr/bin/env python3
"""Run only on the exclusively leased perceus BX primary, never on the laptop.

Preserves matched frozen inputs/runtime and all raw hardware observations.
The product harnesses measure native, warmed in-process batches; counters include
the full child (setup/validation too), and are never labelled pure kernel cost.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='build/perceus-measurement-20261020')
    parser.add_argument('--label', required=True)
    parser.add_argument('--compiler', required=True)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--runtime-root', help='explicit frozen shared runtime root for isolated control/candidate pairs')
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--skip-products', action='store_true')
    parser.add_argument('--reuse-baseline-products', action='store_true',
                        help='baseline only: use already qualified frozen native products')
    args = parser.parse_args()
    if platform.system() != 'Linux' or not Path('/home/user/w/perceus').is_dir():
        raise RuntimeError('requires assigned perceus BX primary')
    if not args.label.replace('-', '').replace('_', '').isalnum():
        raise RuntimeError('simple unique label required')
    root = Path(args.root).resolve()
    frozen = root / 'baseline/tree'
    runtime_root = Path(args.runtime_root).resolve() if args.runtime_root else frozen
    out = root / 'runs' / args.label
    out.mkdir(parents=True, exist_ok=False)
    compiler = Path(args.compiler).resolve()
    bundle = Path(args.bundle).resolve()
    shutil.copy2(compiler, out / 'emitter')
    shutil.copy2(bundle, out / 'compiler.min')
    scope_pass = runtime_root/'compiler/stages/scope-ownership.min'
    if not scope_pass.is_file() or scope_pass.read_bytes() not in bundle.read_bytes():
        raise RuntimeError('shared frozen root must include exact scope pass contained in measured compiler bundle')
    runtime_before = {str(p.relative_to(runtime_root/'runtime')): digest(p)
                      for p in sorted((runtime_root/'runtime').rglob('*')) if p.is_file()}
    commands = []

    def run(argv, cwd=None, env=None, timeout=600):
        argv = [str(a) for a in argv]
        started = time.monotonic()
        result = subprocess.run(argv, cwd=cwd, env=env, text=True,
                                capture_output=True, timeout=timeout)
        index = len(commands)
        (out / ('command-%03d.stdout' % index)).write_text(result.stdout)
        (out / ('command-%03d.stderr' % index)).write_text(result.stderr)
        commands.append({'argv': argv, 'cwd': str(cwd) if cwd else os.getcwd(),
                         'exit': result.returncode, 'seconds': time.monotonic()-started})
        save(out / 'commands.json', commands)
        print(json.dumps({'command': index, 'exit': result.returncode,
                          'argv': argv, 'seconds': commands[-1]['seconds']}), flush=True)
        if result.returncode:
            raise RuntimeError('command failed; retained command-%03d.stderr' % index)
        return result.stdout

    clang = run(['sh', frozen / 'tools/toolchain.sh', 'default-clang'], cwd=frozen).strip()
    run([clang, '--version'])
    flags = ['-O2', '-Wno-override-module', '-flto=thin', '-fuse-ld=lld', '-Wl,--threads=1']
    profiles = {}
    profile_protocol = {'arena': {'lowering': [], 'runtime_defines': ['-DMINYAR_COMPILER_ARENA']},
                        'eager': {'lowering': ['--scope-owners'], 'runtime_defines': []},
                        'bounded': {'lowering': ['--scope-owners'], 'runtime_defines': ['-DMINYAR_SYSTEM_HEAP=1']},
                        'runtime_optimization': '-O2', 'link_flags': flags,
                        'products': 'maintained O2/noLTO default bounded SYSTEM_HEAP APIs'}
    for profile in ['arena', 'eager', 'bounded']:
        switch = profile_protocol[profile]['lowering']
        definitions = profile_protocol[profile]['runtime_defines']
        ir = out / ('compiler-' + profile + '.ll')
        run([out/'emitter', out/'compiler.min', ir, '--library', frozen/'library', *switch])
        runtime = out / ('runtime-' + profile + '.ll')
        run([clang, '-O2', '-S', '-emit-llvm', *definitions,
             runtime_root/'runtime/minyar_runtime.c', '-o', runtime])
        runtime.write_text(re.sub(r'"(target-cpu|target-features|tune-cpu)"="[^\"]*" ?', '', runtime.read_text()))
        executable = out / ('compiler-' + profile)
        run([clang, *flags, ir, runtime, '-lm', '-pthread', '-o', executable])
        profiles[profile] = executable
    # The pinned frames implementation uses perf_event_open directly, with a
    # stopped child, enable-on-exec, pinned user-only instructions, and exact
    # enabled==running verification. Python/hash/link work is excluded.
    driver = out / 'counter-driver.py'
    driver.write_text('''import importlib.util,json,os,sys\nfrom pathlib import Path\nroot=Path(sys.argv[1]); config=json.loads((root/'counter-config.json').read_text())\nspec=importlib.util.spec_from_file_location('counter',config['module']); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nrows=[]\nfor entry in config['commands']:\n row=m.measure(entry['argv'],entry['stdout'],entry['stderr']); row.update(entry);rows.append(row)\n Path(root/'counter-raw.json').write_text(json.dumps(rows,indent=2)+'\\n')\n print(json.dumps({'name':entry['name'],'instructions':row['retired_instructions'],'exit':row['exit']}),flush=True)\n if row['exit']!=0:raise RuntimeError('measured child failed')\n''')
    measured = []

    def add(name, argv, iteration):
        ordinal = len(measured)
        measured.append({'name': name, 'sample': iteration,
                         'warmup': iteration == -1, 'argv': [str(v) for v in argv],
                         'stdout': str(out/('counter-%03d.stdout'%ordinal)),
                         'stderr': str(out/('counter-%03d.stderr'%ordinal))})

    for iteration in range(-1, args.samples):
        order = list(profiles) if iteration % 2 else list(reversed(profiles))
        for profile in order:
            output = out / ('self-%s-%s.ll' % (profile, iteration))
            add('selfcompile-' + profile, [profiles[profile], frozen/'build/compiler.min', output,
                                          '--library', frozen/'library'], iteration)
    if not args.skip_products:
        if args.reuse_baseline_products:
            if args.label != 'baseline':
                raise RuntimeError('candidate cannot silently reuse baseline product binaries')
            product_root = root / 'products'
            safe_report_path = root / 'baseline/safelibs-benchmark.json'
        else:
            # Fresh product copies use the frozen revisions, compiler runtime,
            # library and toolchain. The minimal build root's Make target only
            # preserves the supplied qualified compiler; it cannot rebuild from
            # unrelated moving parent-worktree source.
            product_root = out / 'products'
            for name in ['c2min', 'safelibs']:
                shutil.copytree(root/'products'/name, product_root/name,
                                ignore=shutil.ignore_patterns('build','__pycache__'))
            compiler_root = out / 'product-compiler-root'
            for name in ['runtime', 'library', 'tools']:
                shutil.copytree((runtime_root if name == 'runtime' else frozen)/name, compiler_root/name)
            (compiler_root/'build').mkdir()
            shutil.copy2(out/'emitter', compiler_root/'build/minyarc')
            shutil.copy2(out/'compiler.min', compiler_root/'build/compiler.min')
            (compiler_root/'Makefile').write_text('build/minyarc:\n\t@test -x "$@"\n')
            environment = dict(os.environ, MINYAR_C2MIN_REMOTE='1')
            run(['python3', product_root/'c2min/tools/check.py', '--minyar-root', compiler_root,
                 '--optimizations', '2'], env=environment)
            run(['python3', product_root/'c2min/tools/bench.py', '--minyar-root', compiler_root,
                 '--trials', '5'], env=environment)
            safe = product_root/'safelibs'
            run(['make', '-C', safe, '-j8', 'MINYAR_ROOT='+str(compiler_root),
                 'CLANG='+clang, 'PROFILE=baseline', 'all', 'check', 'build/baseline/benchmark'])
            environment.update(MINYARC=str(compiler_root/'build/minyarc'),
                SAFELIBS_BUILD_OPTIONS='-O2 -DMINYAR_SYSTEM_HEAP=1 -DMINYAR_RC_TESTING=1')
            safe_report_path = out/'safelibs-benchmark.json'
            run(['/usr/bin/python3', safe/'scripts/benchmark.py', safe/'build/baseline/libsafelibs.so',
                 '--runner', safe/'build/baseline/benchmark', '--fixtures-dir', root/'fixtures/safelibs',
                 '--output', safe_report_path, '--samples', '7', '--min-seconds', '0.2'], env=environment)
        c2 = product_root / 'c2min/build/benchmark'
        safe_report = json.loads(safe_report_path.read_text())
        baseline_counts = {row['workload']['name']: row['iterations'] for row in
                           json.loads((root/'baseline/safelibs-benchmark.json').read_text())['workloads']}
        product_commands = []
        for tokens, repeats in [(1024, 2000), (16384, 200)]:
            for implementation in ['reference', 'migrated']:
                product_commands.append(('c2min-%s-%s' % (tokens, implementation),
                                         [c2/implementation, tokens, repeats]))
        for workload in safe_report['workloads']:
            for implementation in ['candidate', 'reference']:
                command = list(workload['pairs'][0][implementation]['argv'])
                # Native timing calibrates independently; retired-instruction
                # comparisons require identical fixed operation counts.
                command[command.index('--iterations') + 1] = str(
                    baseline_counts[workload['workload']['name']][implementation])
                product_commands.append(('safelibs-%s-%s' %
                                         (workload['workload']['name'], implementation), command))
        for iteration in range(-1, args.samples):
            for name, argv in (product_commands if iteration % 2 else list(reversed(product_commands))):
                add(name, argv, iteration)
    config = {'module': str(root/'frames-instructions.py'), 'commands': measured,
              'counter_sha256': digest(root/'frames-instructions.py')}
    save(out/'counter-config.json', config)
    run(['sudo', '-n', 'python3', driver, out], timeout=900)
    raw = json.loads((out/'counter-raw.json').read_text())
    summaries = {}
    for name in dict.fromkeys(row['name'] for row in raw):
        rows = [r for r in raw if r['name']==name and not r['warmup']]
        values = [r['retired_instructions'] for r in rows]
        summaries[name] = {'instructions': values, 'median_instructions': statistics.median(values)}
        if name.startswith(('c2min-', 'safelibs-')):
            native = [json.loads(Path(r['stdout']).read_text()) for r in rows]
            counts = {r['iterations'] for r in native}
            if len(counts) != 1:
                raise RuntimeError('operation count changed within hardware samples')
            count = next(iter(counts))
            summaries[name]['iterations'] = count
            summaries[name]['median_instructions_per_operation_including_setup'] = statistics.median(values)/count
            if name.startswith('c2min-'):
                tokens = int(name.split('-')[1])
                if {r['checksum'] for r in native} != {(4*tokens+1)*count}:
                    raise RuntimeError('C/Minyar tokenizer checksum mismatch')
            else:
                if any(r['live_objects'] != 0 for r in native):
                    raise RuntimeError('codec retained managed objects')
                summaries[name]['output_hashes'] = sorted({r['final_fnv1a64'] for r in native})
                if len(summaries[name]['output_hashes']) != 1:
                    raise RuntimeError('codec output changed across samples')
    outputs = {}
    for profile in profiles:
        hashes = {digest(p) for p in out.glob('self-'+profile+'-*.ll')}
        if len(hashes) != 1:
            raise RuntimeError('nondeterministic self-compile output')
        outputs[profile] = list(hashes)[0]
    if len(set(outputs.values())) != 1:
        raise RuntimeError('arena/eager compiler output differs')
    runtime_after = {str(p.relative_to(runtime_root/'runtime')): digest(p)
                     for p in sorted((runtime_root/'runtime').rglob('*')) if p.is_file()}
    if runtime_before != runtime_after:
        raise RuntimeError('runtime changed during measurement')
    summary = {'label': args.label, 'profiles': summaries, 'selfcompile_outputs': outputs,
               'historical_arena_reference': {'instructions': 171000000,
                 'comparable': False, 'reason': 'different historical Apple-era source/input'},
               'inputs': {'bundle_sha256': digest(out/'compiler.min'),
                         'canonical_input_sha256': digest(frozen/'build/compiler.min'),
                         'emitter_sha256': digest(out/'emitter'),
                         'profile_protocol': profile_protocol,
                         'runtime_tree': runtime_after,
                         'library_tree': {str(p.relative_to(frozen/'library')): digest(p)
                                          for p in sorted((frozen/'library').rglob('*')) if p.is_file()},
                         'source_scope_pass_sha256': digest(scope_pass)},
               'method': 'pinned user-only retired instructions, 100% continuously running; full native child including setup/validation; warmed same-process native API loops for product timings',
               'environment': {k: os.environ.get(k) for k in ['LD_PRELOAD','LD_LIBRARY_PATH','ASAN_OPTIONS','UBSAN_OPTIONS','GLIBC_TUNABLES']}}
    save(out/'summary.json', summary)
    inventory = {str(p.relative_to(out)): {'sha256':digest(p),'bytes':p.stat().st_size}
                 for p in sorted(out.rglob('*')) if p.is_file()}
    save(out/'manifest.json', inventory)
    print('PERCEUS_MEASUREMENT_COMPLETE '+json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
