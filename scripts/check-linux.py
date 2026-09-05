#!/usr/bin/env python3
"""Run Linux correctness checks in an isolated source/build snapshot.

Requires clang, lld, make, python3, zsh, sanitizer runtimes, and libc/C++ headers.
Example: python3 scripts/check-linux.py --source /path/to/project
Run separately on aarch64 and x86_64. Performance tests are excluded."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ['build/minyarc', 'build/compiler-stage3.ll', 'build/minyarc-sanitize',
         'build/minyar-runtime.o', 'build/minyar-runtime-sanitize.o', 'build/ownership-runtime.o',
         'build/runtime-unit', 'build/runtime-unit-sanitize']
TARGETS = ['check-generated-sanitizer', 'check-sanitized-fixed-point',
           'check-smoke', 'check-release-build', 'check-launcher-isolation',
           'check-modules', 'check-regressions', 'check-binary-expressions', 'check-ownership',
           'check-adversarial', 'check-recursive-data', 'check-scalar-record-storage',
           'check-readonly-parameters', 'check-compact-ownership', 'check-integer-text-cache',
           'check-tokenizer-storage']
DIRECTORIES = ('bootstrap', 'src', 'runtime', 'vendor', 'examples', 'tests',
               'experiments', 'scripts', 'tools')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, default=ROOT)
    p.add_argument('--resume', type=Path, help='Resume an existing run after verifying its original source snapshot; completed identical checks are reused.')
    p.add_argument('--output-dir', type=Path, help='Parent for the uniquely named retained run directory.')
    p.add_argument('--clang', default='clang')
    p.add_argument('--cxx', default='clang++')
    p.add_argument('--timeout', type=int, default=1800, help='Maximum seconds for each top-level check.')
    p.add_argument('--dry-run', action='store_true', help='Inspect the plan without copying or executing builds; usable on other hosts.')
    a = p.parse_args()
    source = (a.resume.resolve() / 'source') if a.resume else a.source.resolve()
    if a.timeout < 1:
        p.error('timeout must be positive')
    required = ['Makefile', 'minyar', 'runtime/minyar_heap.h',
                'tests/generated-stack-sanitizer.py', 'tests/llvm_sanitizer.py',
                'tests/binary-expression-ownership.py',
                'tests/integer-text-cache.c', 'tests/integer-text-cache.py',
                'tests/tokenizer-storage.c', 'tests/tokenizer-storage.py',
                'tests/recent-cursors.c', 'tests/memory-profile-regressions.py',
                'experiments/memory/critical-path-study.py']
    missing = [name for name in required if not (source / name).is_file()]
    plan = {'source': str(source), 'build_targets': BUILD,
            'correctness_targets': TARGETS,
            'additional': ['stage2/stage3 LLVM byte equality', 'runtime unit native + ASan/UBSan',
                           'ordinary source regressions with sanitized compiler/runtime',
                           'focused system/fixed/lazy ownership and debt matrix',
                           'critical-path correctness and zero-allocation oracles (no --measure)'],
            'missing_required_sources': missing,
            'excluded': ['check-budget', 'check-performance', 'check-scaling', 'RSS ceilings',
                         'hard real-time claims', 'embedded libc/ABI certification']}
    if a.dry_run:
        print(json.dumps(plan, indent=2))
        return 0 if not missing else 2
    if platform.system() != 'Linux':
        p.error('execution requires Linux; --dry-run is available on this host')
    if platform.machine() not in ('aarch64', 'arm64', 'x86_64', 'amd64'):
        p.error('this runner currently covers Linux aarch64 and x86_64')
    if missing:
        p.error('selected source lacks required profile implementation/fixtures: ' + ', '.join(missing))
    tools = {name: shutil.which(command) for name, command in
             [('clang', a.clang), ('clang++', a.cxx), ('make', 'make'), ('ld.lld', 'ld.lld')]}
    if not all(tools.values()):
        p.error('missing tools: ' + ', '.join(name for name, path in tools.items() if not path))
    if a.output_dir and not a.resume:
        a.output_dir.mkdir(parents=True, exist_ok=True)
    evidence = a.resume.resolve() if a.resume else Path(tempfile.mkdtemp(prefix='minyar-linux-', dir=a.output_dir)).resolve()
    work, logs, bindir = evidence / 'source', evidence / 'logs', evidence / 'bin'
    report_path = evidence / 'results.json'
    if a.resume:
        try:
            previous_bytes = report_path.read_bytes()
            report = json.loads(previous_bytes)
            manifest = report['source_sha256']
            if not manifest:
                raise ValueError('source manifest is empty')
            for name, expected in manifest.items():
                path = (work / name).resolve()
                if not path.is_relative_to(work.resolve()):
                    raise ValueError('source manifest contains an external path: ' + name)
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError('source snapshot changed: ' + name)
            if report['platform']['machine'] != platform.machine():
                raise ValueError('resume requires the original architecture')
            if report['tools'] != tools:
                raise ValueError('resume requires the original tool paths')
        except (OSError, ValueError, KeyError) as error:
            p.error('cannot resume: ' + str(error))
        history = evidence / 'history'
        history.mkdir(exist_ok=True)
        index = len(list(history.glob('results-*.json')))
        (history / f'results-{index:03d}.json').write_bytes(previous_bytes)
        report['status'] = 'running'
        report.pop('error', None)
    else:
        for directory in (work, logs, bindir):
            directory.mkdir()
        report = {'status': 'running', 'plan': plan, 'platform': platform.uname()._asdict(),
                  'invocation': sys.argv, 'tools': tools, 'source_sha256': {}, 'checks': [],
                  'scope': 'Correctness on the recorded Linux host/toolchain. No performance or deadline certification.'}
        # Copy source only: never inherit host binaries, generated IR or .git state.
        for name in DIRECTORIES:
            shutil.copytree(source / name, work / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('Makefile', 'minyar'):
            shutil.copy2(source / name, work / name)
        for path in sorted(work.rglob('*')):
            if path.is_file():
                report['source_sha256'][str(path.relative_to(work))] = hashlib.sha256(path.read_bytes()).hexdigest()
    runner_bytes = Path(__file__).read_bytes()
    runner_hash = hashlib.sha256(runner_bytes).hexdigest()
    runner_history = evidence / 'runners'
    runner_history.mkdir(exist_ok=True)
    (runner_history / (runner_hash + '.py')).write_bytes(runner_bytes)
    execution = {'invocation': sys.argv, 'runner_sha256': runner_hash,
                 'resume': bool(a.resume), 'reused_checks': [], 'plan': plan}
    report.setdefault('executions', []).append(execution)

    def save():
        temporary = report_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(report_path)

    print('Linux correctness evidence: ' + str(evidence), flush=True)
    # Some harnesses invoke clang/clang++ directly. PATH wrappers route their
    # links through lld, which avoids the optional LLVMgold.so plugin.
    for name in ('clang', 'clang++'):
        wrapper = bindir / name
        wrapper.write_text('#!' + sys.executable + '\nimport os,sys\n'
                           'args=sys.argv[1:]\n'
                           'if not any(x in args for x in ("-c","-S","-E","-fsyntax-only","--version","-v")):\n'
                           '    args=["-fuse-ld=lld",*args]\n'
                           'os.execv(' + repr(tools[name]) + ',[' + repr(tools[name]) + ',*args])\n')
        wrapper.chmod(0o755)
    env = dict(os.environ)
    for name in list(env):
        if name.startswith('MINYAR_'):
            del env[name]
    env.update(PATH=str(bindir) + os.pathsep + env.get('PATH', ''),
               ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
               CC='clang', CXX='clang++', CLANG='clang', MINYAR_TEST_CLANG='clang',
               LIMITED='', SANITIZER_LIMITED='')
    make = [tools['make'], 'LIMITED=', 'SANITIZER_LIMITED=', 'CC=clang', 'LLVM_CC=clang',
            'COMPILER_LTO_FLAGS=-flto -fuse-ld=lld']

    def check(label, command, extra_env=None):
        effective_env = {**env, **(extra_env or {})}
        # Hash the inherited environment without recording possible secrets.
        env_hash = hashlib.sha256(json.dumps(effective_env, sort_keys=True).encode()).hexdigest()
        if a.resume:
            for index, previous in enumerate(report['checks']):
                if previous.get('returncode') != 0 or previous.get('command') != command:
                    continue
                known_env = previous.get('environment_sha256')
                same_env = known_env == env_hash if known_env else not extra_env and label != 'regressions-sanitize'
                if same_env:
                    execution['reused_checks'].append({'label': label, 'original_index': index,
                                                       'legacy_environment_unknown': known_env is None})
                    save()
                    print(label + ': reused successful identical check', flush=True)
                    return
        log = logs / (f'{len(report["checks"]):02d}-' + label + '.log')
        row = {'label': label, 'command': command, 'log': str(log), 'timeout_seconds': a.timeout,
               'extra_env': extra_env or {}, 'environment_sha256': env_hash, 'runner_sha256': runner_hash}
        report['checks'].append(row)
        save()
        print(label, flush=True)
        with log.open('w') as output:
            output.write('$ ' + shlex.join(command) + '\n')
            output.flush()
            child = subprocess.Popen(command, cwd=work, env=effective_env,
                                     stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                row['returncode'] = child.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired:
                # Kill the whole compiler/test group; never leave timed-out
                # grandchildren consuming resources during later checks.
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                row.update(returncode=None, timed_out=True)
        save()
        if row['returncode'] != 0:
            raise RuntimeError(label + ' failed; see ' + str(log))

    save()
    try:
        check('toolchain', ['clang', '--version'])
        check('build', make + BUILD)
        check('compiler-fixed-point', [sys.executable, '-c',
              'from pathlib import Path; assert Path("build/compiler-stage2.ll").read_bytes() == Path("build/compiler-stage3.ll").read_bytes(), "compiler fixed point differs"'])
        check('runtime-unit', ['./build/runtime-unit'])
        check('runtime-unit-sanitize', ['./build/runtime-unit-sanitize'])
        for target in TARGETS:
            check(target, make + [target])
        if (work / 'tests/scalar-record-initialization.py').is_file():
            check('scalar-constructor-selection', [sys.executable, 'tests/scalar-record-initialization.py',
                  '--compiler', 'build/minyarc', '--runtime', 'build/ownership-runtime.o', '--sanitize'])
        check('regressions-sanitize', [sys.executable, 'tests/regressions.py'],
              {'MINYAR_TEST_COMPILER': str(work / 'build/minyarc-sanitize'),
               'MINYAR_TEST_RUNTIME': str(work / 'build/minyar-runtime-sanitize.o'),
               'MINYAR_TEST_LINK_FLAGS': '-fsanitize=address,undefined'})
        check('memory-profiles-focused', [sys.executable, 'tests/memory-profile-regressions.py',
              '--runtime-source', str(work / 'runtime/minyar_runtime.c'), '--suite', 'focused',
              '--profiles', 'system', 'fixed', 'lazy', '--clang', 'clang',
              '--output-dir', str(evidence)])
        check('critical-path-correctness', [sys.executable, 'experiments/memory/critical-path-study.py',
              '--compiler', str(work / 'build/minyarc'), '--cc', 'clang', '--cxx', 'clang++',
              '--output', str(evidence / 'critical-path.json')])
        report['status'] = 'passed'
    except (OSError, RuntimeError) as error:
        report.update(status='failed', error=str(error))
        print(str(error), file=sys.stderr)
    finally:
        save()
    print(str(report_path), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
