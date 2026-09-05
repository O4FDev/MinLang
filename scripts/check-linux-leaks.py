#!/usr/bin/env python3
"""Replay completed Linux runtime checks with LeakSanitizer enabled.

A deliberate standalone leak must be detected first. Compiler arena processes
are excluded; only normal-exit runtime fixtures are replayed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--clang', default='clang')
    args = parser.parse_args()
    if platform.system() != 'Linux':
        parser.error('this supplemental check requires Linux LeakSanitizer')
    run = args.run_dir.resolve()
    report = json.loads((run / 'results.json').read_text())
    if report['status'] != 'passed':
        parser.error('the ordinary Linux correctness run must pass first')
    for name, expected in report['source_sha256'].items():
        path = (run / 'source' / name).resolve()
        if not path.is_relative_to(run / 'source') or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            parser.error('original source snapshot changed: ' + name)
    work = Path(tempfile.mkdtemp(prefix='leaks-', dir=run))
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=0',
           'LSAN_OPTIONS': 'exitcode=23', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    source = work / 'detector-control.c'
    source.write_text('#include <stdlib.h>\n__attribute__((noinline)) static void forget(void) {\n'
                      'void *p=malloc(37); if(!p) abort(); *(volatile char *)p=1;\n}\n'
                      'int main(void) { forget(); return 0; }\n')
    binary = work / 'detector-control'
    subprocess.run([args.clang, '-O0', '-g', '-fsanitize=address,undefined', str(source), '-o', str(binary)], check=True)
    control = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
    (work / 'detector-control.log').write_text(control.stdout + control.stderr)
    if control.returncode != 23 or 'LeakSanitizer: detected memory leaks' not in control.stderr:
        raise RuntimeError('LeakSanitizer did not detect the deliberate control leak; see ' + str(work))
    commands = [('eager-runtime-unit', [str(run / 'source/build/runtime-unit-sanitize')])]
    for profile_report in run.glob('minyar-memory-profiles-*/results.json'):
        profile = json.loads(profile_report.read_text())
        if profile['status'] != 'passed':
            continue
        for row in profile['checks']:
            command = row['command']
            if row['label'].startswith('system-') and not row['label'].endswith('-compile'):
                path = Path(command[0]).resolve()
                if not path.is_relative_to(run) or row.get('returncode') != 0:
                    raise RuntimeError('invalid completed fixture: ' + row['label'])
                commands.append((row['label'], command))
    if len(commands) == 1:
        raise RuntimeError('no completed system-allocator fixtures found')
    results = {'status': 'running', 'control_detected': True, 'directory': str(work), 'checks': []}
    for label, command in commands:
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        log = work / (str(len(results['checks'])) + '-' + label + '.log')
        log.write_text(result.stdout + result.stderr)
        results['checks'].append({'label': label, 'command': command, 'returncode': result.returncode,
                                  'binary_sha256': hashlib.sha256(Path(command[0]).read_bytes()).hexdigest(),
                                  'log': str(log)})
        (work / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError('runtime leak check failed: ' + str(log))
        print(label + ': LeakSanitizer passed', flush=True)
    results['status'] = 'passed'
    (work / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(work / 'results.json', flush=True)


if __name__ == '__main__':
    main()
