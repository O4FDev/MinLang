#!/usr/bin/env python3
"""Check the legal exact-block edge whose unused capacity crosses the PNG limit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory/evidence/native-application-round4'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--cohorts', nargs='+', required=True)
    args = parser.parse_args()
    out = BASE / args.label
    out.mkdir(exist_ok=False)
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    # Independent integer construction: raw is an exact 65535 multiple, and
    # actual IDAT length is the legal endpoint minus one despite five-byte slack.
    width, height = 1456, 491490
    pixels = 4 * width * height
    raw = (3 * width + 1) * height
    blocks, remainder = divmod(raw, 65535)
    encoded = raw + blocks * 5 + 6
    capacity = encoded + 5
    assert remainder == 0 and encoded == 2147483646 and capacity == 2147483651
    report = dict(status='running', width=width, height=height,
                  expected_requests=[pixels, raw, capacity], encoded=encoded,
                  png_limit=2147483647, large_allocation_or_encoding=False, commands=[])
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    def save():
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    try:
        for cohort in args.cohorts:
            source = BASE / cohort / 'results.json'
            prior = json.loads(source.read_text())
            for mode in ['o2', 'sanitize']:
                argv = next(row['command'] for row in prior['commands'] if row['label'] == mode + '-compile')
                binary = Path(argv[argv.index('-o') + 1])
                command = ['/usr/bin/time', '-l', str(binary), 'dimensions', str(width), str(height)]
                start = time.monotonic()
                result = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                                        capture_output=True, timeout=30)
                row = dict(cohort=cohort, mode=mode, command=command, returncode=result.returncode,
                           stdout=result.stdout, stderr=result.stderr,
                           wall_seconds=time.monotonic() - start,
                           source_sha256=prior['source_sha256'],
                           cohort_results_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
                report['commands'].append(row)
                save()
                assert result.returncode == 1
                program = [line for line in result.stderr.splitlines() if line and not line[0].isspace()]
                assert program == ['Minyar stopped: the computer ran out of memory.']
                stats = json.loads(result.stdout)
                assert stats['malloc_calls'] == 3 and stats['sizes'] == [pixels, raw, capacity]
                assert stats['pending'] and not any(stats[k] for k in ('read_calls', 'open_calls', 'write_calls', 'close_calls'))
                match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', result.stderr, re.M)
                assert match and int(match[1]) <= 128 * 1024 * 1024
                row['measured_peak_rss_bytes'] = int(match[1])
                row['passed'] = True
                save()
        report['status'] = 'passed'
        report['checks'] = len(report['commands'])
        save()
        print(json.dumps({'status': report['status'], 'checks': report['checks']}, indent=2))
    except BaseException as error:
        report['status'] = 'failed'
        report['failure'] = {'type': type(error).__name__, 'message': str(error)}
        save()
        raise


if __name__ == '__main__':
    main()
