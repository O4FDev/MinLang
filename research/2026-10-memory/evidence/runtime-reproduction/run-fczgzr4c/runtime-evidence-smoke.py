#!/usr/bin/env python3
"""Reproduce one native result using archived sources and an installed C toolchain."""
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'evidence/runtime'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (240, 240))
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))


def main():
    destination = HERE / 'evidence/runtime-reproduction'
    destination.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='run-', dir=destination))
    index = json.loads((ARCHIVE / 'index.json').read_text())
    entry = next(item for item in index['results'] if item['label'] == 'final-text-matrix')
    record = json.loads((ARCHIVE / entry['path']).read_text())
    expected = next(check['stdout'] for check in record['checks'] if check['label'] == 'system-k1-o2')
    report = {'status': 'running', 'copied_sources': [], 'commands': [],
              'archive_index_sha256': digest(ARCHIVE / 'index.json'),
              'original_record_sha256': digest(ARCHIVE / entry['path']),
              'runner_sha256': digest(Path(__file__)),
              'scope': 'Native system/K1/O2 Unicode fixture only. No build artifacts or live repository sources. '
                       'External prerequisites: Python3, installed Clang, platform C library/SDK and linker. '
                       'Not hermetic toolchain reproduction, generated-code validation or a full matrix.'}
    shutil.copyfile(__file__, evidence / Path(__file__).name)

    def execute(argv, cwd):
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                timeout=240, preexec_fn=limits)
        report['commands'].append({'argv': argv, 'cwd': str(cwd), 'returncode': result.returncode,
                                   'stdout': result.stdout, 'stderr': result.stderr})
        return result

    try:
        with tempfile.TemporaryDirectory(prefix='minyar-archive-replay-') as scratch:
            scratch = Path(scratch)

            def copy(source_record, relative):
                source = ARCHIVE / source_record['path']
                target = scratch / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                assert digest(source) == source_record['sha256']
                shutil.copyfile(source, target)
                assert digest(target) == source_record['sha256']
                report['copied_sources'].append({'archive_path': source_record['path'],
                                                 'copied_relative_path': relative,
                                                 'sha256': digest(target)})

            for source in index['final_runtime']:
                copy(source, 'runtime/' + Path(source['path']).name)
            for name in ['memory-research-text-join-index.c', 'clang_helpers.py']:
                source = next(item['archive_source'] for item in entry['sources']
                              if item['original_snapshot'] == 'tests/' + name)
                copy(source, 'tests/' + name)
            spec = importlib.util.spec_from_file_location('archived_clang_helper', scratch / 'tests/clang_helpers.py')
            helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(helper)
            clang = shutil.which('clang')
            assert clang, 'Installed clang is an external prerequisite.'
            assert execute([clang, '--version'], scratch).returncode == 0
            argv = helper.clang_command([clang, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                         '-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_RC_POLL_BUDGET=1',
                                         'tests/memory-research-text-join-index.c', '-o', 'unicode-smoke'])
            assert execute(argv, scratch).returncode == 0
            result = execute([str(scratch / 'unicode-smoke')], scratch)
            assert result.returncode == 0 and result.stdout == expected
            assert len(result.stdout.splitlines()) == 18
            trap = execute([str(scratch / 'unicode-smoke'), '--invalid-utf8'], scratch)
            assert trap.returncode == 1
            report['summary'] = {'semantic_cases': 18, 'expected_invalid_utf8_traps': 1,
                                 'temporary_binary_removed': True}
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = str(error)
        raise
    finally:
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(evidence / 'results.json')


if __name__ == '__main__':
    main()
