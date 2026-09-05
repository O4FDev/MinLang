#!/usr/bin/env python3
"""Record OS-reported peak RSS for separate compiler/cache-driver processes.

This is the maximum child RSS reported by an isolated resource-usage worker, not the sum
of simultaneous parent/child RSS. Only the stated wide graph is measured.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('graphs', ROOT / 'tests/module-performance.py')
graphs = importlib.util.module_from_spec(spec); spec.loader.exec_module(graphs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules', type=int, default=400)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc-modules', help='Incremental compiler binary to freeze for this measurement')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/incremental-module-memory.json')
    args = parser.parse_args()
    if args.modules < 1: parser.error('positive module count required')
    system = platform.system()
    if system not in ('Darwin', 'Linux'):
        raise SystemExit('requires POSIX resource usage on macOS or Linux')
    report = {'platform': platform.platform(), 'method': __doc__, 'modules': args.modules,
              'shape': 'wide', 'artifacts': {}, 'rows': []}
    with tempfile.TemporaryDirectory(prefix='minyar-module-rss-') as name:
        d = Path(name)
        for label, name in [('driver', 'minyar-module-build'), ('compiler', 'minyarc-modules'), ('production', 'minyarc')]:
            source = args.compiler.resolve() if label == 'compiler' else ROOT / 'build' / name
            report['artifacts'][label] = hashlib.sha256(source.read_bytes()).hexdigest()
            shutil.copy2(source, d / label)
        entry, _ = graphs.generate(d / 'graph', 'wide', args.modules, 4, 12)
        original = entry.read_text(); library = entry.parent / 'm0.min'; lib_original = library.read_text()
        cache = d / 'cache'; stats = d / 'stats'
        commands = {'production': [d / 'production', entry, d / 'base.ll'],
                    'driver': [d / 'driver', d / 'compiler', entry, d / 'cached.ll', cache, stats]}
        graphs.timed(commands['driver'])
        file = next(cache.glob('*.cache')); baseline = file.read_bytes()
        for scenario in ('unchanged', 'entry-edit', 'dependency-edit', 'interface-edit', 'cold'):
            entry.write_text(original); library.write_text(lib_original)
            if scenario == 'entry-edit': entry.write_text(original.replace('    print(', '    let changed = 1\n    print('))
            if scenario == 'dependency-edit': library.write_text(lib_original.replace('result = result + 1', 'result = result + 2', 1))
            if scenario == 'interface-edit': library.write_text(lib_original + '\npublic record Added { value: Integer }\n')
            row = {'scenario': scenario, 'peak_rss_mib': {}}
            for label, command in commands.items():
                if scenario == 'cold': file.unlink(missing_ok=True)
                else: file.write_bytes(baseline)
                file.with_suffix('.cache.delta').unlink(missing_ok=True)
                worker = 'import json,resource,subprocess,sys; r=subprocess.run(sys.argv[1:],capture_output=True,text=True); print(json.dumps({"status":r.returncode,"stderr":r.stderr,"rss":resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}))'
                result = subprocess.run([sys.executable, '-c', worker, *map(str, command)], capture_output=True, text=True, timeout=30, check=True)
                measured = json.loads(result.stdout)
                if measured['status']: raise RuntimeError(measured['stderr'])
                row['peak_rss_mib'][label] = measured['rss'] / (1048576 if system == 'Darwin' else 1024)
            row['cache_bytes'] = sum(p.stat().st_size for p in cache.glob('*.cache*'))
            row['delta_bytes'] = sum(p.stat().st_size for p in cache.glob('*.delta'))
            row['counters'] = stats.read_text().strip()
            report['rows'].append(row)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['rows'], indent=2))


if __name__ == '__main__':
    main()
