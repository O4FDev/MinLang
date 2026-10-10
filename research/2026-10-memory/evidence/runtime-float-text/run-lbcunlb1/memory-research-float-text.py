#!/usr/bin/env python3
"""Bounded public Float conversion counts, alias survival and exact recovery."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import subprocess
import tempfile
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))


def main():
    assert platform.system() == 'Darwin', 'RSS/resource observer requires Darwin time/taskpolicy'
    parent = ROOT / 'build/memory-research-float-text'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    original = {str(p): sha(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()}
    report = {'status': 'running', 'checks': [], 'observations': {},
              'scope': 'Public Float-to-Text allocation and lifetime; no private formatter/libc counts or timing claim.',
              'fixture_limits': {'wall_seconds': 30, 'cpu_seconds': 30, 'rss_bytes': 128 * 1024 * 1024,
                                 'file_bytes': 64 * 1024 * 1024}}
    runtime = out / 'runtime'
    runtime.mkdir()
    for p in (ROOT / 'runtime').glob('minyar_*'):
        if p.is_file():
            shutil.copyfile(p, runtime / p.name)
    shutil.copyfile(ROOT / 'tests/memory-research-float-text.c', out / 'fixture.c')
    for source in (Path(__file__), ROOT / 'tests/clang_helpers.py',
                   ROOT / 'research/2026-10-memory/runtime-float-text-preregister.json'):
        shutil.copyfile(source, out / source.name)
    patches = []

    def observe(name, changes):
        path = runtime / name
        before = path.read_text()
        after = before
        for old, new in changes:
            assert after.count(old) == 1, (name, old)
            after = after.replace(old, new, 1)
        path.write_text(after)
        patches.append(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                  fromfile=name, tofile='observed/' + name)))

    observe('minyar_rc.h', [
        ('static void *rc_allocate_object(size_t size, unsigned kind) {',
         'static void *rc_allocate_object(size_t size, unsigned kind) {\n    float_allocation(1, size + sizeof(RcObject));'),
        ('static void *rc_allocate_data(size_t size) {',
         'static void *rc_allocate_data(size_t size) {\n    float_allocation(0, size + sizeof(RcData));'),
        ('static inline size_t rc_service_pending(size_t budget) {',
         'static inline size_t rc_service_pending(size_t budget) {\n    float_service(budget, rc_pending_count);')])
    observe('minyar_bounded_rc.h', [
        ('size_t minyar_rc_poll(size_t budget) {',
         'size_t minyar_rc_poll(size_t budget) {\n    float_poll(0);'),
        ('    return work;\n}', '    observed_work += work;\n    return work;\n}')])
    (out / 'observer.patch').write_text(''.join(patches))
    report['sources'] = [{'path': str(p.relative_to(out)), 'sha256': sha(p)}
                         for p in sorted(out.rglob('*')) if p.is_file()]

    def save():
        (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def command(label, argv, expected=0, measured=False):
        if measured:
            argv = ['/usr/bin/time', '-l', '/usr/sbin/taskpolicy', '-m', '128', *argv]
        result = subprocess.run(argv, text=True, capture_output=True, timeout=30, preexec_fn=limits,
                                env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=1',
                                     'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        check = {'label': label, 'argv': argv, 'returncode': result.returncode, 'expected_returncode': expected,
                 'stdout': label + '.stdout', 'stderr': label + '.stderr'}
        if measured:
            match = re.search(r'(\d+)\s+maximum resident set size', result.stderr)
            assert match, result.stderr
            check['maximum_rss_bytes'] = int(match.group(1))
        report['checks'].append(check)
        save()
        assert result.returncode == expected, (label, result.stderr)
        if measured:
            assert check['maximum_rss_bytes'] <= report['fixture_limits']['rss_bytes']
        return result

    print('Evidence: ' + str(out), flush=True)
    save()
    try:
        for label, flags, mutant in [('observer-red', ['-O2'], True), ('native', ['-O2'], False),
                                    ('sanitize', ['-O1', '-g', '-fsanitize=address,undefined',
                                                  '-fno-omit-frame-pointer'], False)]:
            binary = out / label
            command(label + '-compile', clang_command(['clang', *flags, '-Wall', '-Wextra', '-Werror',
                *(['-DMINYAR_RESEARCH_OMIT_DATA_EVENT=1'] if mutant else []),
                f'-DMINYAR_RESEARCH_RUNTIME="{runtime / "minyar_runtime.c"}"',
                str(out / 'fixture.c'), '-o', str(binary)]))
            result = command(label, [str(binary)], 70 if mutant else 0, measured=True)
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            report['observations'][label] = rows
            assert len(rows) == (1 if mutant else 10)
            assert all(r['objects_after'] == r['requested_after'] == r['heap_after'] == 0 for r in rows)
            if mutant:
                assert 'public conversion observes both managed allocation edges' in result.stderr
                assert rows[0]['object_allocations'] == 1 and rows[0]['data_allocations'] == 0
            else:
                assert 'Float Text observer assertion' not in result.stderr
                assert 'AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr
            save()
        assert report['observations']['native'] == report['observations']['sanitize']
        report.update(status='passed', source_hashes_unchanged=original ==
                      {str(p): sha(p) for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file()},
                      conclusion='Ten exact public conversion cases per native/sanitized control; omitted data event rejected after full recovery.')
        assert report['source_hashes_unchanged']
        print(report['conclusion'], flush=True)
    except Exception as error:
        report.update(status='failed', failure=str(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
