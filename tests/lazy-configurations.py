#!/usr/bin/env python3
"""Correctness/RSS diagnostic for the isolated lazy virtual-heap prototype."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1'}
    records = []
    with tempfile.TemporaryDirectory(prefix='minyar-lazy-validation-') as directory:
        directory = Path(directory)
        for size in (64 << 20, 64 << 30, 1 << 40):
            for sanitized in (False, True):
                exe = directory / f'capacity-{size}-{int(sanitized)}'
                flags = ['-fsanitize=address,undefined'] if sanitized else []
                subprocess.run([args.clang, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                                *flags, f'-DMINYAR_BOUNDED_HEAP_BYTES={size}ULL',
                                str(ROOT / 'tests/lazy-heap.c'), '-o', str(exe)], check=True, timeout=60)
                result = subprocess.run([str(exe)],capture_output=True,text=True,timeout=60,env=env)
                assert result.returncode == 0, result.stdout + result.stderr
                records.append({'capacity':size,'sanitized':sanitized,'output':result.stdout.strip()})
                print(records[-1], flush=True)
                if sanitized and size > 64 << 20:
                    failed = subprocess.run([str(exe), 'sanitizer-limit'],capture_output=True,text=True,timeout=30,env=env)
                    assert failed.returncode != 0 and 'sanitizer block limit' in failed.stderr, failed.stderr
        for failed_mapping in (1,2):
            for sanitized in (False,True):
                exe = directory / f'failure-{failed_mapping}-{int(sanitized)}'
                flags = ['-fsanitize=address,undefined'] if sanitized else []
                subprocess.run([args.clang,'-std=c11','-O1','-g','-Wall','-Wextra','-Werror',*flags,
                                f'-DFAIL_MAPPING={failed_mapping}',str(ROOT/'tests/lazy-mmap-failure.c'),
                                '-o',str(exe)],check=True,timeout=60)
                result = subprocess.run([str(exe)],capture_output=True,text=True,timeout=30,env=env)
                assert result.returncode == 1, result.stderr
                assert 'injected mapping failure rolled back correctly' in result.stderr, result.stderr
                assert ('virtual reservation failed' if failed_mapping==1 else 'metadata reservation failed') in result.stderr
                records.append({'failure_mapping':failed_mapping,'sanitized':sanitized,'output':result.stderr.strip()})
                print(records[-1],flush=True)
    if args.output: args.output.write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
