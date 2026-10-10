#!/usr/bin/env python3
"""Bounded frozen source pairs for renderer slots and prepared craft lighting.

Require an exclusive campaign timing window. Raw CPU observations, count-only
instrumentation, immutable outputs, blocked order, and external load are retained.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, default=ROOT)
    parser.add_argument('--samples', type=int, default=8)
    args = parser.parse_args()
    if not args.label.replace('-', '').isalnum() or not 4 <= args.samples <= 12:
        parser.error('bounded label and 4..12 samples required')
    evidence = ROOT / 'research/2026-10-memory/evidence/native-application' / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    parent = ROOT / 'build/native-research-application'
    parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.label + '-', dir=parent))
    compiler = ROOT / 'build/minyarc'
    report = {'status': 'running', 'invocation': sys.argv, 'work': str(work), 'commands': [],
              'sources': [], 'samples': [], 'warmups': [], 'counts': [], 'instruments': [],
              'host': {'platform': platform.platform(), 'initial_loadavg': os.getloadavg()},
              'scope': 'CPU bookkeeping with typed GL stubs; 32x32x8 prepared craft world; no window or GPU claim.',
              'memory_bounds': {'block_bytes': 8192, 'mesh_slots': 4096, 'output_mesh_bytes': 78000},
              'timing_contract': 'Process CPU clock, prepared buffers, count instrumentation disabled in timing binaries; 8 adjacent pairs by default, alternating order randomized within two-pair blocks.',
              'compiler_sha256': digest(compiler)}
    env = dict(os.environ)

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, command, cwd=ROOT):
        entry = {'label': label, 'command': list(map(str, command)), 'cwd': str(cwd)}
        report['commands'].append(entry)
        save()
        try:
            result = subprocess.run(entry['command'], cwd=cwd, env=env, text=True,
                                    capture_output=True, timeout=60)
        except subprocess.TimeoutExpired as error:
            entry.update(timed_out=True, stdout=str(error.stdout), stderr=str(error.stderr))
            save()
            raise
        entry.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        save()
        if result.returncode: raise RuntimeError(label + ': ' + result.stderr)
        return result.stdout

    try:
        report['clang_version'] = run('clang-version', ['clang', '--version'])
        report['process_load_before'] = run('process-load-before', ['ps', '-Ao', 'pid,pcpu,rss,comm'])
        cflags = shlex.split(run('glfw-cflags', ['pkg-config', '--cflags', 'glfw3']))
        libs = shlex.split(run('glfw-libs', ['pkg-config', '--libs', 'glfw3']))
        libs += ['-framework', 'OpenGL'] if platform.system() == 'Darwin' else ['-lGL']
        common = ['clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                  '-Wno-unused-function', '-Wno-unused-variable', *cflags]
        artifacts = {}
        for variant, origin in [('before', args.before), ('after', args.after)]:
            source = evidence / 'sources' / variant
            paths = list((origin / 'runtime').glob('minyar_*'))
            paths += list((origin / 'runtime/native').glob('*'))
            paths += list((origin / 'examples/craft').glob('*.min'))
            paths += list((origin / 'library').glob('*.min'))
            for path in paths:
                if not path.is_file(): continue
                relative = path.relative_to(origin)
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                report['sources'].append({'variant': variant, 'path': str(relative), 'sha256': digest(target)})
            for name in ['native-research-graphics.c', 'native-research-craft.min', 'native-research-paired.py', 'clang_helpers.py']:
                original = ROOT / 'tests' / name
                target = source / 'tests' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                report['sources'].append({'variant': variant, 'path': 'tests/' + name, 'sha256': digest(target)})
            runtime = work / (variant + '-runtime.o')
            run(variant + '-runtime', clang_command([*common, '-c', source / 'runtime/minyar_runtime.c', '-o', runtime]))
            graphics = work / (variant + '-graphics')
            run(variant + '-graphics', clang_command([*common, '-DNATIVE_RESEARCH_NO_VERTEX_COUNTS=1',
                source / 'tests/native-research-graphics.c', runtime, *libs, '-o', graphics]))
            native = work / (variant + '-native.o')
            run(variant + '-native', clang_command([*common, '-DNATIVE_RESEARCH_LIBRARY_ONLY=1',
                '-DNATIVE_RESEARCH_NO_VERTEX_COUNTS=1', '-c', source / 'tests/native-research-graphics.c', '-o', native]))
            llvm = work / (variant + '-craft.ll')
            run(variant + '-frontend', [compiler, source / 'tests/native-research-craft.min', llvm, '--library', source / 'library'], source)
            app = work / (variant + '-craft')
            run(variant + '-link', clang_command(['clang', '-O2', '-Wno-override-module', llvm,
                                                runtime, native, *libs, '-o', app]))
            artifacts[variant] = {'graphics': graphics, 'app': app, 'source': source, 'runtime': runtime}
            for workload in ['lighting', 'lighting-control']:
                mesh = work / (variant + '-' + workload + '-warmup.bin')
                stdout = run(variant + '-' + workload + '-warmup', [app, workload, mesh])
                rows = stdout.splitlines()
                assert list(map(int, rows[1:])) == [78000, 0, 257 if variant == 'before' and workload == 'lighting' else 1, 0, 0, 0], rows
                report['warmups'].append({'variant': variant, 'workload': workload, 'cpu_seconds': float(rows[0]), 'mesh_sha256': digest(mesh)})
            for count in [128, 4096]:
                row = json.loads(run(variant + f'-mesh-{count}-warmup', [graphics, 'mesh-bench', count, 32]))
                assert row['checksum'] == 32 * count * (count + 1) // 2
                report['warmups'].append({'variant': variant, 'workload': 'meshes-' + str(count), **row})
            # Counter code is introduced only into the frozen count copy after timing artifacts exist.
            renderer = source / 'runtime/native/graphics.c'
            original = renderer.read_text()
            anchor = 'while (slot < mesh_count && meshes[slot].used) slot++;'
            assert original.count(anchor) == 1
            counted = original.replace('long long minyar_graphics_createMesh(void) {',
                                       'static size_t native_research_slot_checks;\nlong long minyar_graphics_createMesh(void) {')
            counted = counted.replace(anchor, 'while (slot < mesh_count && (native_research_slot_checks++, meshes[slot].used)) slot++;')
            renderer.write_text(counted)
            count_graphics = work / (variant + '-count-graphics')
            run(variant + '-count-graphics', clang_command([*common, '-DNATIVE_RESEARCH_SLOT_COUNTS=1', source / 'tests/native-research-graphics.c', runtime, *libs, '-o', count_graphics]))
            report['instruments'].append({'variant': variant, 'path': 'runtime/native/graphics.c', 'sha256': digest(renderer), 'kind': 'occupied-slot predicate increments'})
            renderer.write_text(original)
            for count in [128, 512, 1024, 4096]:
                row = json.loads(run(variant + f'-slot-count-{count}', [count_graphics, 'meshes', count]))
                assert row['initial_slot_checks'] == (count * (count - 1) // 2 if variant == 'before' else 0), row
                assert row['reuse_slot_checks'] == (count * count // 4 if variant == 'before' else count - 1), row
                report['counts'].append({'variant': variant, 'workload': 'mesh-slots', **row})
            meshing = source / 'examples/craft/meshing.min'
            original = meshing.read_text()
            anchor = 'for torch in torches {'
            filter_anchor = 'for torch in world.torches {'
            assert original.count(anchor) == original.count(filter_anchor) == 1
            declarations = '\nfunction lightingVisit() { native "native_research" }\nfunction filteringVisit() { native "native_research" }\n'
            counted = declarations + original.replace(anchor, anchor + '\n        lightingVisit()').replace(filter_anchor, filter_anchor + '\n        filteringVisit()')
            meshing.write_text(counted)
            report['instruments'].append({'variant': variant, 'path': 'examples/craft/meshing.min', 'sha256': digest(meshing), 'kind': 'actual lighting/filter torch iteration increments'})
            count_native = work / (variant + '-count-native.o')
            run(variant + '-count-native', clang_command([*common, '-DNATIVE_RESEARCH_LIBRARY_ONLY=1', '-c', source / 'tests/native-research-graphics.c', '-o', count_native]))
            count_llvm = work / (variant + '-count-craft.ll')
            run(variant + '-count-frontend', [compiler, source / 'tests/native-research-craft.min', count_llvm, '--library', source / 'library'], source)
            count_app = work / (variant + '-count-craft')
            run(variant + '-count-link', clang_command(['clang', '-O2', '-Wno-override-module', count_llvm,
                                                      runtime, count_native, *libs, '-o', count_app]))
            meshing.write_text(original)
            for workload in ['lighting', 'lighting-control']:
                rows = run(variant + '-counts-' + workload, [count_app, workload]).splitlines()
                torches = 257 if variant == 'before' and workload == 'lighting' else 1
                assert list(map(int, rows[1:])) == [78000, 0, torches, 31200, 5120 * torches, 16 * torches], rows
                report['counts'].append({'variant': variant, 'workload': workload, 'torches': torches,
                                        'vertex_extensions': int(rows[4]), 'lighting_visits': int(rows[5]), 'filtering_visits': int(rows[6])})
        hashes = {item['mesh_sha256'] for item in report['warmups'] if 'mesh_sha256' in item}
        assert len(hashes) == 1, 'Repeated torch writes changed geometry/light bytes'
        report['mesh_output_sha256'] = hashes.pop()
        rng = random.Random(20261004)
        orders = []
        while len(orders) < args.samples:
            block = [['before', 'after'], ['after', 'before']]
            rng.shuffle(block)
            orders.extend(block)
        for workload in ['meshes-4096', 'meshes-128', 'lighting', 'lighting-control']:
            for pair, order in enumerate(orders[:args.samples]):
                entry = {'workload': workload, 'pair': pair, 'order': order, 'loadavg_before': os.getloadavg(), 'observations': {}}
                report['samples'].append(entry)
                save()
                for variant in order:
                    if workload.startswith('meshes-'):
                        count = int(workload.split('-')[1])
                        row = json.loads(run(f'{workload}-pair{pair}-{variant}', [artifacts[variant]['graphics'], 'mesh-bench', count, 32]))
                        assert row['checksum'] == 32 * count * (count + 1) // 2
                    else:
                        mesh = work / f'{workload}-pair{pair}-{variant}.bin'
                        rows = run(f'{workload}-pair{pair}-{variant}', [artifacts[variant]['app'], workload, mesh]).splitlines()
                        expected_torches = 257 if variant == 'before' and workload == 'lighting' else 1
                        assert list(map(int, rows[1:])) == [78000, 0, expected_torches, 0, 0, 0]
                        assert digest(mesh) == report['mesh_output_sha256']
                        row = {'cpu_seconds': float(rows[0]), 'mesh_sha256': digest(mesh)}
                    assert row['cpu_seconds'] > 0, 'CPU interval below clock resolution'
                    entry['observations'][variant] = row
                    save()
                entry['after_over_before_cpu'] = entry['observations']['after']['cpu_seconds'] / entry['observations']['before']['cpu_seconds']
                entry['loadavg_after'] = os.getloadavg()
                save()
        report['summary'] = {}
        for workload in ['meshes-4096', 'meshes-128', 'lighting', 'lighting-control']:
            pairs = [item for item in report['samples'] if item['workload'] == workload]
            ratios = [item['after_over_before_cpu'] for item in pairs]
            report['summary'][workload] = {'pairs': len(pairs), 'after_over_before_cpu_median': statistics.median(ratios),
                                         'ratio_min': min(ratios), 'ratio_max': max(ratios),
                                         'before_cpu_median': statistics.median(item['observations']['before']['cpu_seconds'] for item in pairs),
                                         'after_cpu_median': statistics.median(item['observations']['after']['cpu_seconds'] for item in pairs)}
        report['host']['final_loadavg'] = os.getloadavg()
        report['process_load_after'] = run('process-load-after', ['ps', '-Ao', 'pid,pcpu,rss,comm'])
        report.update(status='passed', completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      limitation='Shared-host observations only. External process load is retained; work counts and byte identity support the local changes independently of timing. No latency/HFT/GPU claim.')
        save()
        print(json.dumps({'evidence': str(evidence), 'summary': report['summary']}, indent=2))
    except Exception as error:
        report.update(status='failed', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    main()
