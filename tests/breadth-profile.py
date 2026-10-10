#!/usr/bin/env python3
"""Bounded Craft build profile with frozen inputs and explicit phase boundaries.

This is opt-in research: no bootstrap, broad integration gate, game execution,
or production source edits. The non-LTO pipeline uses the launcher's default
O2 flags and system runtime; release uses its runtime LLVM and LTO flags.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import resource
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sampled_source_work(text):
    """Attribute each sample once to its deepest named Minyar compiler frame.

    Counts belong to a separate diagnostic invocation, not timing samples.
    Optimized/inlined frames can be absent; this is sampled work, not CPU time.
    """
    graph = text.split('Call graph:', 1)[-1].split('Total number in stack', 1)[0]
    nodes = []
    stack = []
    for line in graph.splitlines():
        match = re.match(r'^([ +!:|]*)(\d+) (.+?)  \(in ', line)
        if not match:
            continue
        depth = len(match[1])
        while stack and nodes[stack[-1]]['depth'] >= depth:
            stack.pop()
        function = match[3]
        owner = stack[-1] if stack else None
        attributed = nodes[owner]['attributed'] if owner is not None else 'entry-or-unresolved'
        if '.minyar.fn.' in function:
            attributed = function.split('.minyar.fn.', 1)[1]
        node = {'depth': depth, 'count': int(match[2]), 'children': 0, 'attributed': attributed}
        if owner is not None:
            nodes[owner]['children'] += node['count']
        nodes.append(node)
        stack.append(len(nodes) - 1)
    counts = {}
    for node in nodes:
        self_samples = max(0, node['count'] - node['children'])
        counts[node['attributed']] = counts.get(node['attributed'], 0) + self_samples
    return [{'function': function, 'attributed_samples': count}
            for function, count in sorted(counts.items(), key=lambda item: item[1], reverse=True) if count]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--total-seconds', type=float, default=180)
    parser.add_argument('--evidence', type=Path, default=ROOT / 'evidence/breadth-profile/craft-pilot')
    parser.add_argument('--output', type=Path, default=ROOT / 'research/2026-10-breadth/profiling-results.json')
    parser.add_argument('--skip-release', action='store_true')
    parser.add_argument('--sample-source', action='store_true', help='One separate macOS stack sample, excluded from timings')
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5 or args.timeout <= 0 or args.total_seconds <= 0:
        parser.error('repeats must be 1..5; time limits must be positive')
    work = args.evidence.resolve()
    work.mkdir(parents=True, exist_ok=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = {'schema': 1, 'status': 'running', 'invocation': sys.argv,
              'scope': 'Craft real source-to-LLVM and native build; game execution skipped',
              'host': {'platform': platform.platform(), 'loadavg': os.getloadavg()},
              'limits': {'repeats': args.repeats, 'process_seconds': args.timeout,
                         'campaign_seconds': args.total_seconds},
              'inputs': {}, 'commands': [], 'phases': [], 'limitations': [
                  'Frontend combines module loading, lexing, declaration/type checking and LLVM emission.',
                  'Cache driver timings include its child frontend; they do not measure driver overhead alone.',
                  'Release Clang combines LLVM optimization, LTO and native linking.',
                  'Filesystem caches are warm; cold means no Minyar module cache.',
                  'Existing compiler binaries are hashed; their exact correspondence to dirty source is unproven.',
                  'Per-command child CPU is summed across child processes; peak RSS is a cumulative child maximum.']}

    def save():
        (work / 'raw-results.json').write_text(json.dumps(report, indent=2) + '\n')
        args.output.write_text(json.dumps(report, indent=2) + '\n')

    def run(label, command, measured=True):
        remaining = args.total_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError('total profile time limit exhausted')
        argv = list(map(str, command))
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        begin = time.perf_counter()
        process = subprocess.Popen(argv, cwd=work, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=min(args.timeout, remaining))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            (work / f'{len(report["commands"]):02d}-{label}.stderr').write_bytes(stderr)
            raise TimeoutError(f'{label}: process time limit exhausted')
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        wall_ms = 1000 * (time.perf_counter() - begin)
        index = len(report['commands'])
        (work / f'{index:02d}-{label}.stdout').write_bytes(stdout)
        (work / f'{index:02d}-{label}.stderr').write_bytes(stderr)
        row = {'label': label, 'argv': argv, 'cwd': str(work), 'measured': measured,
               'returncode': process.returncode, 'wall_ms': wall_ms,
               'cpu_ms': 1000 * (after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime),
               'child_peak_rss_bytes': after.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
               'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
               'stderr_sha256': hashlib.sha256(stderr).hexdigest()}
        report['commands'].append(row)
        save()
        if process.returncode:
            raise RuntimeError(f'{label}: exited {process.returncode}: {stderr.decode(errors="replace")[-1500:]}')
        return row

    def phase(label, command, outputs, prepare=None):
        rows = []
        hashes = []
        for _ in range(args.repeats):
            if prepare:
                prepare()
            row = run(label, command)
            row['outputs'] = {str(path.relative_to(work)): {'sha256': digest(path), 'bytes': path.stat().st_size}
                              for path in outputs}
            hashes.append({str(path.relative_to(work)): digest(path) for path in outputs})
            rows.append(row)
        result = {'label': label, 'samples': len(rows),
                  'median_cpu_ms': statistics.median(row['cpu_ms'] for row in rows),
                  'median_wall_ms': statistics.median(row['wall_ms'] for row in rows),
                  'stable_outputs': all(value == hashes[0] for value in hashes),
                  'outputs': rows[-1]['outputs']}
        report['phases'].append(result)
        print(f'{label}: CPU {result["median_cpu_ms"]:.2f} ms, wall {result["median_wall_ms"]:.2f} ms', flush=True)
        save()
        return result

    try:
        sources = work / 'sources'
        for directory in ('examples/craft', 'library', 'runtime'):
            shutil.copytree(ROOT / directory, sources / directory)
        for relative in ('compiler/compiler.min', 'compiler/module-compiler.min', 'tools/module-build.c',
                         'tools/clang-driver.py', 'minyar'):
            target = sources / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        for path in sorted(sources.rglob('*')):
            if path.is_file():
                report['inputs'][str(path.relative_to(sources))] = digest(path)
        binaries = work / 'binaries'
        binaries.mkdir()
        for name in ('minyarc', 'minyarc-modules', 'minyar-module-build',
                     'minyar-default-runtime.o', 'minyar-default-runtime-release.ll'):
            destination = binaries / name
            shutil.copy2(ROOT / 'build' / name, destination)
            report['inputs']['build/' + name] = digest(destination)
        clang = os.environ.get('MINYAR_CLANG', os.environ.get('LLVM_CC', 'clang'))
        clang_path = Path(shutil.which(clang)).resolve()
        report['clang'] = {'path': str(clang_path), 'sha256': digest(clang_path)}
        run('clang-identity', [clang, '--version'], False)
        spec = importlib.util.spec_from_file_location('clang_driver', sources / 'tools/clang-driver.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        cflags, libraries = driver.glfw_flags()
        if platform.system() == 'Darwin':
            libraries += ['-framework', 'OpenGL', '-framework', 'Cocoa', '-framework', 'IOKit']
        elif platform.system() != 'Windows':
            libraries += ['-lGL', '-lm']
        link_flags = driver.flags('MINYAR_CLANG_FLAGS', '-O2 -Wno-override-module')
        native_flags = driver.flags('MINYAR_NATIVE_FLAGS', shlex.join(link_flags))
        report['flags'] = {'program': link_flags, 'native': native_flags, 'glfw_compile': cflags,
                           'native_libraries': libraries}
        entry = sources / 'examples/craft/main.min'
        llvm = work / 'craft.ll'
        options = ['--bounded-owners', '32', '--library', sources / 'library']
        frontend = [binaries / 'minyarc', entry, llvm, *options]
        phase('frontend', frontend, [llvm])
        text = llvm.read_text()
        assert '; minyar-native-library: graphics' in text
        symbols = re.findall(r'^define [^@\n]*@([^\s(]+)\(', text, re.M)
        assert len(symbols) == len(set(symbols)), 'duplicate LLVM definitions'
        report['llvm_definitions'] = len(symbols)
        native_object = work / 'graphics.o'
        phase('native-graphics-object', [clang, *native_flags, *cflags, '-c', sources / 'runtime/native/graphics.c',
                                       '-o', native_object], [native_object])
        program_object = work / 'craft.o'
        phase('program-llvm-object', [clang, *link_flags, '-c', llvm, '-o', program_object], [program_object])
        executable = work / 'craft-o2'
        phase('native-link', [clang, *link_flags, program_object, binaries / 'minyar-default-runtime.o',
                              native_object, *libraries, '-o', executable], [executable])
        if not args.skip_release:
            release = work / 'craft-release'
            phase('release-clang-lto-link', [clang, *link_flags, *driver.lto_flags(clang, link_flags), llvm,
                                            binaries / 'minyar-default-runtime-release.ll', native_object,
                                            *libraries, '-o', release], [release])
        cache = work / 'cache'
        stats = work / 'cache-stats.txt'
        cached_llvm = work / 'craft-cached.ll'
        cached_command = [binaries / 'minyar-module-build', binaries / 'minyarc-modules', entry,
                          cached_llvm, cache, stats, *options]
        phase('cached-frontend-cold', cached_command, [cached_llvm, stats],
              lambda: shutil.rmtree(cache, ignore_errors=True))
        cold_counts = list(map(int, stats.read_text().split()[:6]))
        assert cold_counts[0] == 0 and cold_counts[1] > 0, cold_counts
        phase('cached-frontend-unchanged', cached_command, [cached_llvm, stats])
        warm_counts = list(map(int, stats.read_text().split()[:6]))
        assert warm_counts[0] == cold_counts[1] and warm_counts[1] == 0, warm_counts
        report['cache_counters'] = {'cold': cold_counts, 'unchanged': warm_counts}
        if args.sample_source:
            if sys.platform != 'darwin':
                raise RuntimeError('--sample-source currently requires macOS sample')
            sampled = binaries / f'bc{os.getpid()}'
            shutil.copy2(binaries / 'minyarc', sampled)
            sample_path = work / 'frontend-sample.txt'
            observer = subprocess.Popen(['/usr/bin/sample', sampled.name, '2', '1', '-wait', '-mayDie',
                                         '-file', str(sample_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                time.sleep(0.25)
                run('frontend-stack-sample', [sampled, entry, work / 'craft-sampled.ll', *options], False)
                observer.communicate(timeout=5)
            finally:
                if observer.poll() is None:
                    observer.kill()
                    observer.communicate()
            report['source_sampling'] = {'returncode': observer.returncode, 'output': str(sample_path),
                                         'available': sample_path.is_file()}
            if sample_path.is_file():
                report['source_sampling']['sha256'] = digest(sample_path)
                report['source_sampling']['ranked_attribution'] = sampled_source_work(sample_path.read_text())
        report['ranked_phases'] = [{'rank': index + 1, 'label': row['label'], 'cpu_ms': row['median_cpu_ms']}
                                   for index, row in enumerate(sorted(report['phases'], key=lambda row: row['median_cpu_ms'], reverse=True))]
        phases = {row['label']: row for row in report['phases']}
        report['o2_complete_build_ms'] = {metric: sum(phases[label]['median_' + metric] for label in
                                                     ('frontend', 'native-graphics-object', 'program-llvm-object', 'native-link'))
                                          for metric in ('cpu_ms', 'wall_ms')}
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic() - started
        save()
    print(args.output)


if __name__ == '__main__':
    main()
