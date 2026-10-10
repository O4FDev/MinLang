#!/usr/bin/env python3
"""Replay completed one-iteration controls against their immutable binaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    source = json.loads((args.evidence / 'results.json').read_text())
    output = args.evidence / 'resource-replay-new.json'
    assert not output.exists(), 'Preserve earlier resource replay'
    report = {'status': 'running', 'executions': [], 'scope': 'Separate native resource replay; no CPU inference'}

    def save():
        output.write_text(json.dumps(report, indent=2) + '\n')

    def limits():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (33554432, 33554432))

    try:
        for row in source['checks']:
            if 'observation' not in row:
                continue
            binary = Path(row['command'][3])
            identity = next(config for config in source['configurations']
                            if config['label'] == binary.name)
            assert digest(binary) == identity['binary_sha256']
            command = ['/usr/bin/time', '-l', *row['command']]
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=limits,
                env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0', 'UBSAN_OPTIONS': 'halt_on_error=1'})
            timed_out = False
            try:
                out, err = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                out, err = process.communicate()
            match = re.search(r'(\d+)\s+maximum resident set size', err)
            peak = int(match.group(1)) if match else None
            observed = json.loads(out) if process.returncode == 0 else None
            result = {'label': row['label'], 'command': command, 'returncode': process.returncode,
                      'stdout': out, 'stderr': err, 'timed_out': timed_out, 'peak_rss_bytes': peak,
                      'binary_sha256': digest(binary)}
            report['executions'].append(result)
            save()
            assert not timed_out and process.returncode == 0 and peak is not None and peak <= 134217728
            assert observed['checksum'] == row['observation']['checksum'] and observed['quiescent']
            assert result['binary_sha256'] == identity['binary_sha256']
        assert len(report['executions']) == 48
        report.update(status='passed', peak_rss_bytes=max(row['peak_rss_bytes'] for row in report['executions']))
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
