#!/usr/bin/env python3
"""End-to-end Map lowering vs std HashMap / Dictionary, four timed phases.

Run exclusively under the WS3 Boat build lock with no other WS3 jobs active.
No reserve hints; identical key/permutation/value work; independent equal Text
query objects; text construction excluded. Rust Text keys borrow the fixture
strings, avoiding extra allocations unavailable to the other dictionaries.
Raw repetitions, tool versions, hashes, affinity and median ratios are saved.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repeats', type=int, default=7)
    p.add_argument('--integer-count', type=int, default=2_000_000)
    p.add_argument('--text-count', type=int, default=200_000)
    a = p.parse_args()
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    rustc = os.environ.get('RUSTC', 'rustc')
    swiftc = os.environ.get('SWIFTC', 'swiftc')
    output = ROOT / 'build/maps-bench'
    output.mkdir(parents=True, exist_ok=True)
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    data = {'versions': {}, 'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else [],
            'source_hashes': {}, 'workloads': {}}
    for name, command in [('clang', clang), ('rustc', rustc), ('swiftc', swiftc)]:
        data['versions'][name] = subprocess.check_output([command, '--version'], text=True).strip()
    fixtures = ROOT / 'benchmarks/maps'
    for file in fixtures.iterdir():
        data['source_hashes'][file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    runtime = output / 'runtime.ll'
    subprocess.run([clang, '-O2', '-DMINYAR_SYSTEM_HEAP=1', '-S', '-emit-llvm',
                    str(ROOT / 'runtime/minyar_runtime.c'), '-o', str(runtime)], check=True)
    # Match build-support/runtime.mk's generic program-runtime artifact: target
    # attributes otherwise prevent checked helpers from inlining into user IR.
    runtime.write_text(re.sub(r'"(?:target-cpu|target-features|tune-cpu)"="[^"]*" ?', '', runtime.read_text()))
    for kind, count in [('integer', a.integer_count), ('text', a.text_count)]:
        integer = kind == 'integer'
        specs = {
            'minyar': {'KEY_TYPE': 'Integer' if integer else 'Text', 'KEY_EXPR': 'i' if integer else '"usr/share/images/κ/" + Text(i)'},
            'rust': {'KEY_TYPE': 'i64' if integer else 'String', 'KEY_EXPR': 'i as i64' if integer else 'format!("usr/share/images/κ/{}", i)',
                     'KEY_INSERT': 'keys[i]' if integer else 'keys[i].as_str()',
                     'KEY_LOOKUP': '&queries[k]' if integer else 'queries[k].as_str()',
                     'KEY_MIX_INSERT': 'keys[k]' if integer else 'keys[k].as_str()'},
            'swift': {'KEY_TYPE': 'Int' if integer else 'String', 'KEY_EXPR': 'i' if integer else '"usr/share/images/κ/\\(i)"'},
        }
        binaries = {}
        for language, extension in [('minyar', 'min'), ('rust', 'rs'), ('swift', 'swift')]:
            source = (fixtures / ('operations.' + extension)).read_text().replace('COUNT', str(count))
            for old, new in specs[language].items():
                source = source.replace(old, new)
            path = output / (kind + '-' + language + '.' + extension)
            path.write_text(source)
            exe = path.with_suffix('.exe')
            if language == 'minyar':
                llvm = path.with_suffix('.ll')
                subprocess.run([str(ROOT / 'build/minyarc'), str(path), str(llvm)], check=True)
                subprocess.run([clang, '-O2', '-flto=thin', '-fuse-ld=lld-22', '-Wl,--thinlto-jobs=1', '-Wl,--threads=1',
                                '-Wno-override-module', str(llvm), str(runtime), str(fixtures / 'clock.c'), '-lm', '-o', str(exe)], check=True)
            elif language == 'rust':
                subprocess.run([rustc, '-O', '--crate-name', 'mapbench', str(path), '-o', str(exe)], check=True)
            else:
                subprocess.run([swiftc, '-O', str(path), '-o', str(exe)], check=True)
            binaries[language] = exe
        samples = {language: [] for language in binaries}
        expected = count * (3 * count - 1) // 2
        # Rotate process order, with one untimed warmup for every executable.
        for repetition in range(-1, a.repeats):
            order = list(binaries)
            shift = max(repetition, 0) % len(order)
            for language in order[shift:] + order[:shift]:
                begin = time.monotonic()
                r = subprocess.run([str(binaries[language])], text=True, capture_output=True, check=True, timeout=90)
                total = time.monotonic() - begin
                values = [int(x) for x in r.stdout.splitlines()]
                assert len(values) == 6 and values[-2:] == [expected, 0], (language, r.stdout, r.stderr)
                assert not r.stderr, r.stderr
                if repetition >= 0:
                    samples[language].append({'insert': values[0], 'lookup': values[1], 'mixed': values[2], 'remove': values[3],
                                              'process_seconds': total})
        medians = {language: {op: statistics.median([r[op] for r in rows]) for op in ('insert', 'lookup', 'mixed', 'remove')}
                   for language, rows in samples.items()}
        ratios = {peer: {op: medians['minyar'][op] / medians[peer][op] for op in medians['minyar']}
                  for peer in ('rust', 'swift')}
        data['workloads'][kind] = {'count': count, 'samples': samples, 'median_ns': medians, 'minyar_over_peer': ratios}
        print(kind, json.dumps({'median_ns': medians, 'minyar_over_peer': ratios}), flush=True)
    (output / 'results.json').write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    main()
