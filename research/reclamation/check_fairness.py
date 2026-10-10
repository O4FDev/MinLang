#!/usr/bin/env python3
"""Retain actual C scheduler evidence with competing owner queues and arrivals."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from variants import transform

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', checks=[], source_sha256={})
    for src in [*sorted((ROOT / 'runtime').glob('*.[ch]')),
                *[Path(__file__).parent / name for name in ['arrival_fairness.c', 'check_fairness.py', 'variants.py']]]:
        relative = src.relative_to(ROOT); dest = out / 'snapshot' / relative
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(src.read_bytes())
        report['source_sha256'][str(relative)] = hashlib.sha256(dest.read_bytes()).hexdigest()
    def save(): (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    print(out, flush=True); save()
    try:
        original = (out / 'snapshot/runtime/minyar_bounded_rc.h').read_text()
        for policy in ['current', 'fair-unit', 'fifo', 'lifo']:
            directory = out / policy
            shutil.copytree(out / 'snapshot/runtime', directory / 'runtime')
            header = directory / 'runtime/minyar_bounded_rc.h'; header.write_text(transform(original, policy))
            fixture = directory / 'research/reclamation/arrival_fairness.c'; fixture.parent.mkdir(parents=True)
            fixture.write_bytes((out / 'snapshot/research/reclamation/arrival_fairness.c').read_bytes())
            for sanitized in [False, True]:
                label = f'{policy}-{sanitized}'; binary = directory / label
                flags = ['-fsanitize=address,undefined', '-g'] if sanitized else []
                if policy == 'lifo': flags += ['-DRESEARCH_LIFO=1']
                commands = [['clang', '-O2', '-DMINYAR_RC_POLL_BUDGET=1', *flags, str(fixture), '-o', str(binary)], [str(binary)]]
                for phase, command in zip(['build', 'run'], commands):
                    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
                    (out / f'{label}-{phase}.stdout').write_text(result.stdout)
                    (out / f'{label}-{phase}.stderr').write_text(result.stderr)
                    report['checks'].append(dict(label=label, phase=phase, argv=command, returncode=result.returncode))
                    save()
                    if result.returncode: raise RuntimeError(f'{label} {phase} failed: {result.stderr}')
                report['checks'][-1]['observation'] = json.loads(result.stdout)
                report['checks'][-1]['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
                print(label, result.stdout.strip(), flush=True)
        report['status'] = 'passed'
    except Exception as e:
        report.update(status='failed', error=str(e)); raise
    finally: save()


if __name__ == '__main__': main()
