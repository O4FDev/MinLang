#!/usr/bin/env python3
"""Six native bit/storage controls against immutable isolated runtime variants."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bulk', ROOT / 'tests/memory-research-list-bulk.py')
bulk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bulk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-dir', type=Path, default=ROOT / 'runtime')
    parser.add_argument('--candidate-dir', type=Path)
    args = parser.parse_args()
    parent = ROOT / 'build/memory-research-list-bulk-bits'
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    report = {'status': 'running', 'checks': [], 'binaries': []}
    frozen = {str(p): bulk.digest(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()}
    shutil.copyfile(ROOT / 'research/2026-10-memory/runtime-list-bulk-bits-preregister.json', evidence / 'preregister.json')

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def limits():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))

    def execute(label, command, native=False):
        wrapped = ['/usr/bin/time', '-l', '/usr/sbin/taskpolicy', '-m', '128', *command] if native else command
        process = subprocess.Popen(wrapped, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}, preexec_fn=limits)
        timeout = False
        try:
            out, err = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(process.pid, signal.SIGKILL)
            out, err = process.communicate()
        row = {'label':label, 'command':wrapped, 'returncode':process.returncode, 'stdout':out, 'stderr':err, 'timed_out':timeout}
        report['checks'].append(row)
        save()
        assert not timeout and process.returncode == 0, row
        if native:
            row['peak_rss_bytes'] = int(re.search(r'(\d+)\s+maximum resident set size', err).group(1))
            assert row['peak_rss_bytes'] <= 128*1024*1024, row
            assert out == '10 raw words, mutation independence, empty backed scalar, empty and immortal/null reference controls recovered\n', row
        save()

    try:
        execute('toolchain',['clang','--version'])
        for variant in ['baseline','candidate']:
            directory = evidence / variant
            source = args.candidate_dir if variant == 'candidate' and args.candidate_dir else args.baseline_dir
            shutil.copytree(source,directory/'runtime',ignore=shutil.ignore_patterns('native'))
            (directory/'tests').mkdir()
            for name in ['memory-research-list-bulk-bits.c',Path(__file__).name,'memory-research-list-bulk.py','clang_helpers.py']:
                shutil.copyfile(ROOT/'tests'/name,directory/'tests'/name)
            if variant == 'candidate':
                if args.candidate_dir:
                    bulk.verify_candidate(directory/'runtime')
                else:
                    bulk.candidate(directory/'runtime')
            for profile,budget,sanitize in [('system',32,False),('fixed',1,False),('system',32,True)]:
                label=f'{variant}-{profile}-K{budget}-san{int(sanitize)}'
                binary=directory/label
                flags=['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitize else ['-O2']
                defines=['-DMINYAR_SYSTEM_HEAP=1'] if profile=='system' else ['-DMINYAR_BOUNDED_HEAP=1','-DMINYAR_BOUNDED_HEAP_BYTES=2097152']
                execute('compile-'+label,clang_command(['clang','-std=c11',*flags,*defines,f'-DMINYAR_RC_POLL_BUDGET={budget}',
                    '-Wall','-Wextra','-Werror',str(directory/'tests/memory-research-list-bulk-bits.c'),'-o',str(binary)]))
                report['binaries'].append({'path':str(binary.relative_to(evidence)),'sha256':bulk.digest(binary)})
                execute(label,[str(binary)],True)
        assert all(bulk.digest(Path(path))==value for path,value in frozen.items())
        report.update(status='passed',production_frozen_hashes=frozen)
    except BaseException as error:
        report.update(status='failed',failure=repr(error))
        raise
    finally:
        save()
        print('Results: '+str(evidence/'results.json'),flush=True)


if __name__=='__main__':
    main()
