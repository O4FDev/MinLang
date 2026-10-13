#!/usr/bin/env python3
"""Run Linux correctness checks in an isolated source/build snapshot.

Requires clang, lld, make, python3, zsh, sanitizer runtimes, and libc/C++ headers.
Example: python3 scripts/check-linux.py --source /path/to/project --tier all
Run separately on aarch64 and x86_64. Performance tests are excluded.

Checks run in parallel (--jobs, default the CPU count) and keep going past
failures; the run ends with one summary of every failure. Tiers: `full` (the
default, for landing) leaves out sanitizer checks, `sanitize` runs only them,
and `all` runs both. See scripts/check_runner.py for how builds avoid races.

--matrix runs the whole Linux matrix in one go: --tier all plus every group in
GROUPS (LLVM 22 and 23, the clang-18 peer lanes, QUIC, formats, Redis, leaks,
coverage, AFL++ and formatting). --group NAME (repeatable) runs chosen groups,
which is how CI shards the matrix. Toolchain variants build in their own copy of
the source snapshot, so they run concurrently with the main checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_runner  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUILD = ['build/minyarc', 'build/compiler-stage3.ll', 'build/minyarc-sanitize',
         'build/minyar-runtime.o', 'build/minyar-runtime-sanitize.o', 'build/ownership-runtime.o',
         'build/runtime-unit', 'build/runtime-unit-sanitize',
         'build/module-compiler-stage3.ll']
TARGETS = ['check-native-records', 'check-thread-compiler', 'check-thread-effects', 'check-thread-language', 'check-thread-language-sanitize', 'check-thread-tsan-control', 'check-raw-syscall-linux-native', 'check-raw-syscall-sanitize', 'check-raw-syscall-abi', 'check-raw-syscall-frontends', 'check-maps', 'check-maps-sanitize', 'check-octal-literals', 'check-reserved-names', 'check-module-constants', 'check-module-constant-graphs', 'check-foundation-baseline', 'check-quic-official-adapter', 'check-quic-amplification-ledger', 'check-quic-rfc', 'check-quic-rfc-sanitize', 'check-generated-llvm-sanitizer', 'check-linux-snapshot', 'check-cycle-private-retirement', 'check-cycle-private-retirement-sanitize', 'check-parallel-signatures', 'check-parallel-signatures-sanitize', 'check-quic-pto', 'check-quic-pto-sanitize', 'check-quic-ack', 'check-quic-ack-sanitize', 'check-quic-interop-results', 'check-toolchain-stamp', 'check-toolchain-portability', 'check-cold-bootstrap',
           'check-bootstrap-policy', 'check-peer-semantics', 'check-memory-regressions',
           'check-bootstrap-portability', 'check-bootstrap-records',
           'check-measurement-stats', 'check-budget-harness', 'check-stack-limits',
           'check-scalar-study-harness',
           'check-compiler-hardening', 'check-linkage', 'check-source-map', 'check-symbol-order', 'check-list-access', 'check-list-sort', 'check-list-sort-runtime', 'check-list-sort-profiles', 'check-list-sort-sanitize',
           'check-checked-arithmetic', 'check-checked-scalars',
           'check-checked-results', 'check-checked-results-sanitize',
           'check-checked-results-frontends', 'check-checked-results-frontends-sanitize',
           'check-calldepth', 'check-calldepth-sanitize', 'check-calldepth-profiles', 'check-calldepth-launcher',
           'check-calldepth-reporting', 'check-calldepth-reporting-sanitize', 'check-calldepth-hooks', 'check-calldepth-hooks-sanitize',
           'check-runtime-bytes', 'check-runtime-traps', 'check-runtime-numeric',
           'check-shipping', 'check-errors-values', 'check-errors-language', 'check-errors-language-sanitize', 'check-errors-language-bounded', 'check-errors-launcher', 'check-errors-review', 'check-errors-review-sanitize', 'check-errors-review-bounded', 'check-errors-review-bounded-sanitize', 'check-schannel-framing', 'check-schannel-framing-sanitize', 'check-net', 'check-net-loop', 'check-net-udp-offload', 'check-net-udp-offload-sanitize', 'check-tls', 'check-tls-sanitize',
           'check-peer-live', 'check-peer-live-sanitize',
           'check-peer-live-redis', 'check-peer-live-redis-sanitize',
           'check-yamux-churn', 'check-yamux-churn-sanitize',
           'check-transport-cancel', 'check-transport-cancel-sanitize',
           'check-transport-go', 'check-transport-go-sanitize',
           'check-http2-churn', 'check-http2-churn-sanitize',
           'check-peer-grpc-churn', 'check-peer-grpc-churn-sanitize',
           'check-peer-grpc-retire', 'check-peer-grpc-retire-sanitize',
           'check-peer-edge', 'check-peer-edge-sanitize',
           'check-peer-edge-retry', 'check-peer-edge-retry-sanitize',
           'check-peer-edge-cids', 'check-peer-edge-cids-sanitize',
           'check-peer-edge-relay', 'check-peer-edge-relay-sanitize',
           'check-peer-edge-relay-lifetime', 'check-peer-edge-relay-lifetime-sanitize', 'check-json-parser-sanitize',
           'check-cycle-progress-observability', 'check-cycle-progress', 'check-cycle-progress-sanitize', 'check-cycle-witness', 'check-cycle-witness-sanitize', 'check-cycle-additive', 'check-cycle-additive-sanitize', 'check-cycle-registry-growth', 'check-cycle-registry-growth-sanitize', 'check-cycle-registration-exposure', 'check-cycle-registration-exposure-sanitize', 'check-feature-dispatch', 'check-managed-graphs', 'check-managed-graphs-launcher',
           'check-callbacks', 'check-callback-domains', 'check-isolated-workers',
           'check-ownership-policy', 'check-stack-ownership', 'check-runtime-cache',
           'check-generated-sanitizer', 'check-sanitized-fixed-point',
           'check-smoke', 'check-release-build', 'check-launcher-isolation',
           'check-build-wiring', 'check-module-test-driver', 'check-modules', 'check-regressions', 'check-diagnostics', 'check-conformance',
           'check-fuzz', 'check-stack-overflow', 'check-statement-nesting',
           'check-mutation', 'check-mutation-score', 'check-binary-expressions', 'check-ownership',
           'check-adversarial', 'check-recursive-data', 'check-scalar-record-storage',
           'check-readonly-parameters', 'check-compact-ownership', 'check-integer-text-cache',
           'check-tokenizer-storage', 'check-temporary-owner-admission',
           'check-compiler-slice-cache', 'check-memory-contracts-harness',
           'check-ownership-mutation', 'check-scalar-record-initialization',
           'check-incremental-modules', 'check-incremental-modules-sanitize',
           'check-sanitize']
TARGETS += ['check-package-native-inputs', 'check-clang-cache', 'check-mutation-coverage', 'check-list-basics', 'check-list-basics-sanitize', 'check-map-basics', 'check-map-basics-sanitize']
TARGETS += ['check-thread-scaling-protocol', 'check-thread-language-tsan', 'check-thread-generated-recovery', 'check-thread-generated-recovery-sanitize', 'check-thread-generated-recovery-tsan']
TIERS = ('full', 'sanitize', 'all')
# Matrix groups. correctness is the tiered main suite; the others match CI jobs.
GROUPS = ('correctness', 'formatting', 'llvm22', 'llvm23', 'peer-testing', 'peer-semantics', 'quic',
          'formats', 'redis', 'leaks', 'coverage', 'afl')
LLVM_TARGETS = ['check-portable', 'check-release-build', 'check-launcher-isolation', 'check-incremental-modules']
PEER_TESTING_TARGETS = ['check-evidence-harness', 'check-performance-metrics', 'check-peer-ownership',
                        'check-list-literals', 'check-list-literals-sanitize', 'check-list-literal-runtime',
                        'check-stateful-lists', 'check-stateful-lists-sanitize', 'check-allocation-faults',
                        'check-compiler-allocation-faults', 'check-runtime-size-guards',
                        'check-scalar-cleanup-probes', 'check-codegen', 'check-reduction-harness']
PEER_GATES = ['check-peer-optimizations', 'check-peer-sanitize']
QUIC_TARGETS = ['check-quic', 'check-quic-sanitize', 'check-transport-go', 'check-transport-go-sanitize',
                'check-peer-edge-cids', 'check-peer-edge-cids-sanitize', 'check-peer-edge-relay',
                'check-peer-edge-relay-sanitize', 'check-peer-edge-relay-lifetime',
                'check-peer-edge-relay-lifetime-sanitize', 'check-quic-quinn']
# Scheduling hints only: seconds measured serially on an 8-core Linux host.
EXPECTED_SECONDS = {
    'check-mutation-score': 215, 'check-calldepth-profiles': 206, 'check-maps-sanitize': 136,
    'check-transport-go': 131, 'check-transport-go-sanitize': 120, 'check-peer-edge-relay-sanitize': 97,
    'check-peer-edge-relay': 95, 'check-stack-ownership': 93, 'check-quic-rfc-sanitize': 93,
    'check-tls-sanitize': 86, 'check-maps': 79, 'check-peer-edge-cids-sanitize': 69, 'check-quic-rfc': 67,
    'check-managed-graphs-launcher': 62, 'check-tls': 60, 'check-peer-edge-cids': 55,
    'check-cycle-registration-exposure-sanitize': 53, 'check-list-sort-profiles': 52,
    'check-peer-grpc-churn-sanitize': 46, 'check-errors-review-bounded': 46, 'check-errors-language-bounded': 45,
    'check-cycle-progress-sanitize': 40, 'check-errors-language-sanitize': 38,
    # Matrix groups outside the correctness tier.
    'check-quic': 300, 'check-quic-sanitize': 240, 'check-peer-regressions': 340, 'check-peer-optimizations': 200,
    'check-peer-sanitize': 250, 'check-peer-ownership': 140, 'check-coverage': 90, 'check-fuzz-coverage': 75,
    'check-quic-quinn': 150, 'check-quic-native-O0': 150, 'check-quic-native-O2': 150,
    # Per-suite peer children: cpp-java-js holds over half the cases.
    'check-peer-regressions-cpp-java-js': 200, 'check-peer-optimizations-cpp-java-js': 200,
    'check-peer-sanitize-cpp-java-js': 250, 'check-peer-ownership-cpp-java-js': 120,
    'check-peer-regressions-rust-go-zig': 90, 'check-peer-optimizations-rust-go-zig': 90,
    'check-peer-sanitize-rust-go-zig': 120, 'check-peer-sanitize-python-swift-ruby-lua': 110,
}
# Built on demand by the `minyar` launcher inside many harnesses; building them
# early keeps those nested makes no-ops (see scripts/check_runner.py).
LAUNCHER_ARTIFACTS = ['build/minyarc', 'build/minyarc-modules', 'build/minyar-module-build',
                      'build/minyar-default-runtime.o', 'build/minyar-default-runtime-release.ll',
                      'build/minyar-runtime-eager.o', 'build/minyar-runtime-eager-release.ll',
                      'build/minyarc-errors-request', 'build/minyarc-errors', 'build/minyarc-callbacks',
                      'build/minyarc-calldepth']


def tier_of(label):
    return 'sanitize' if 'sanitiz' in label or label in ('check-thread-language-tsan', 'check-thread-generated-recovery-tsan') else 'full'


def in_tier(label, tier):
    return tier == 'all' or tier_of(label) == tier


DIRECTORIES = ('.github', 'benchmarks', 'bootstrap', 'compiler', 'runtime', 'library', 'vendor', 'os', 'examples', 'tests', 'build-support', 'docs',
               'experiments', 'scripts', 'tools')


def copy_source_snapshot(source, work):
    """Copy declared sources without inheriting generated or host artifacts."""
    for name in DIRECTORIES:
        shutil.copytree(source / name, work / name,
                        ignore=shutil.ignore_patterns('build', '.git', '__pycache__', '*.pyc'))
    for name in ('Makefile', 'minyar'):
        shutil.copy2(source / name, work / name)
    # The style the formatting group checks against.
    if (source / '.clang-format').is_file():
        shutil.copy2(source / '.clang-format', work / '.clang-format')



def snapshot_source_key(path, root):
    """Canonical source keys preserve raw bytes across host path providers."""
    return path.relative_to(root).as_posix()


def snapshot_sources(source, work):
    """Copy the correctness inputs without host binaries or repository state."""
    copy_source_snapshot(source, work)
    return {snapshot_source_key(path, work): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(work.rglob('*')) if path.is_file()}


def resolve_toolchain(clang, cxx):
    tools = {name: shutil.which(command) for name, command in
             [('clang', clang), ('clang++', cxx), ('make', 'make'), ('ld.lld', 'ld.lld')]}
    if tools['clang']:
        matching = Path(tools['clang']).resolve().parent / 'ld.lld'
        if matching.is_file():
            tools['ld.lld'] = str(matching)
    return tools


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, default=ROOT)
    p.add_argument('--resume', type=Path, help='Resume an existing run after verifying its original source snapshot; completed identical checks are reused.')
    p.add_argument('--output-dir', type=Path, help='Parent for the uniquely named retained run directory.')
    p.add_argument('--clang', default='clang')
    p.add_argument('--cxx', default='clang++')
    p.add_argument('--timeout', type=int, default=1800, help='Maximum seconds for each top-level check.')
    p.add_argument('--jobs', type=int, default=os.cpu_count() or 1, help='Checks run at once (default: CPU count); use 1 on a memory-constrained laptop.')
    p.add_argument('--tier', choices=TIERS, default='full', help='full (default) leaves out sanitizer checks; sanitize runs only them; all runs both.')
    p.add_argument('--only', action='append', default=[], metavar='TARGET', help='Run only these check targets (repeatable), with their phony prerequisites.')
    p.add_argument('--retries', type=int, default=1, help='Retry each failed check up to this many times alone; a pass on retry is reported as flaky.')
    p.add_argument('--group', action='append', default=[], choices=GROUPS, metavar='GROUP', help='Run these matrix groups (repeatable; default correctness): ' + ', '.join(GROUPS) + '.')
    p.add_argument('--matrix', action='store_true', help='Run the whole Linux matrix: every group, with --tier all.')
    p.add_argument('--dry-run', action='store_true', help='Inspect the plan without copying or executing builds; usable on other hosts.')
    a = p.parse_args()
    source = (a.resume.resolve() / 'source') if a.resume else a.source.resolve()
    if a.timeout < 1:
        p.error('timeout must be positive')
    if a.jobs < 1:
        p.error('jobs must be positive')
    if a.matrix:
        if a.group or a.only:
            p.error('--matrix already selects every group; leave out --group and --only')
        a.group, a.tier = list(GROUPS), 'all'
    groups = [name for name in GROUPS if name in a.group] if a.group else ['correctness']
    if a.only and groups != ['correctness']:
        p.error('--only selects correctness targets; leave out --group')
    unknown = [name for name in a.only if not name.startswith('check-')]
    if unknown:
        p.error('not a check target: ' + ', '.join(unknown))
    required = ['Makefile', 'minyar', '.github/workflows/ci.yml', 'runtime/minyar_heap.h',
                'tests/generated-stack-sanitizer.py', 'tests/llvm_sanitizer.py',
                'tests/binary-expression-ownership.py',
                'tests/integer-text-cache.c', 'tests/integer-text-cache.py',
                'tests/tokenizer-storage.c', 'tests/tokenizer-storage.py',
                'tests/recent-cursors.c', 'tests/memory-profile-regressions.py',
                'experiments/memory/critical-path-study.py',
                'tests/data/peer/implementations.jsonl']
    missing = [name for name in required if not (source / name).is_file()]
    # --only names targets explicitly, whatever their tier.
    # --only may name any phony check, including a child of an aggregate (checked against make later).
    targets = list(dict.fromkeys(a.only)) if a.only else [name for name in TARGETS if in_tier(name, a.tier)]
    if 'correctness' not in groups:
        targets = []
    # Groups other than these run in their own variant snapshots (or need no build).
    main_build = bool(set(groups) & {'correctness', 'quic', 'formats', 'redis', 'leaks', 'coverage', 'afl'})
    build = [name for name in BUILD if (a.tier != 'full' or tier_of(name) == 'full') and main_build]
    plan = {'source': str(source), 'jobs': a.jobs, 'tier': a.tier, 'groups': groups, 'build_targets': build,
            'correctness_targets': targets,
            'additional': ['stage3 compiler and module behavior', 'runtime unit native + ASan/UBSan',
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
    tools = resolve_toolchain(a.clang, a.cxx)
    if not all(tools.values()):
        p.error('missing tools: ' + ', '.join(name for name, path in tools.items() if not path))
    # Fail before any work when a selected group's toolchain is missing; never skip it quietly.
    needs = {'llvm22': ['/usr/lib/llvm-22/bin/clang', '/usr/lib/llvm-22/bin/ld.lld'],
             'llvm23': ['/usr/lib/llvm-23/bin/clang', '/usr/lib/llvm-23/bin/ld.lld'],
             'peer-testing': ['clang-18', 'ld.lld-18', '/usr/lib/llvm-18/bin/FileCheck'],
             'peer-semantics': ['clang-18', 'ld.lld-18'], 'quic': ['cargo', 'go', 'openssl'],
             'redis': ['redis-server'], 'afl': ['afl-fuzz', 'afl-clang-fast'],
             'coverage': ['llvm-profdata', 'llvm-cov']}
    absent = sorted({tool for group in groups for tool in needs.get(group, ())
                     if not (Path(tool).is_file() if tool.startswith('/') else shutil.which(tool))})
    if absent:
        p.error('missing tools for the selected groups: ' + ', '.join(absent))
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
        report['source_sha256'] = snapshot_sources(source, work)
    runner_bytes = Path(__file__).read_bytes()
    runner_hash = hashlib.sha256(runner_bytes).hexdigest()
    runner_history = evidence / 'runners'
    runner_history.mkdir(exist_ok=True)
    (runner_history / (runner_hash + '.py')).write_bytes(runner_bytes)
    previous_checks = list(report['checks']) if a.resume else None
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
                           '    args=[' + repr('--ld-path=' + tools['ld.lld']) + ',*args,"-lm"]\n'
                           'os.execv(' + repr(tools[name]) + ',[' + repr(tools[name]) + ',*args])\n')
        wrapper.chmod(0o755)
    # Nested cold-bootstrap probes inspect the wrapper's sibling linker.
    # Keep that identity aligned with an explicitly selected LLVM release.
    linker = bindir / 'ld.lld'
    if not linker.exists():
        linker.symlink_to(tools['ld.lld'])
    env = dict(os.environ)
    for name in list(env):
        if name.startswith('MINYAR_') or name in ('MAKEFLAGS', 'MFLAGS', 'MAKELEVEL', 'TMPDIR'):
            del env[name]
    # Checks run side by side, so the host is always busy: harnesses must not pause themselves for load.
    env['MINYAR_TEST_SHARED_HOST'] = '1'
    # Toolchain variants get the plain host environment, as their CI jobs do.
    base = dict(env)
    env.update(PATH=str(bindir) + os.pathsep + env.get('PATH', ''),
               ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
               CC='clang', LLVM_CC='clang', CXX='clang++', CLANG='clang', MINYAR_TEST_CLANG='clang',
               COMPILER_LTO_FLAGS='-flto -fuse-ld=lld', MINYAR_TEST_SHARED_HOST='1',
               LIMITED='', SANITIZER_LIMITED='')
    # Each make is serial; concurrency comes from running several checks at once.
    make = [tools['make'], '-j1', 'LIMITED=', 'SANITIZER_LIMITED=', 'CC=clang', 'LLVM_CC=clang',
            'COMPILER_LTO_FLAGS=-flto -fuse-ld=lld']
    temporary = Path(tempfile.mkdtemp(prefix='mc-'))
    runner = check_runner.Runner(work=work, logs=logs, env=env, make=make, jobs=a.jobs, timeout=a.timeout,
                                 report=report, save=save, retries=a.retries, previous=previous_checks,
                                 runner_sha256=runner_hash, temporary=temporary, python=sys.executable)
    execution['reused_checks'] = runner.reused
    Check = check_runner.Check
    python = sys.executable

    def compiler_behavior(prefix):
        return [python, 'tests/compiler-behavior.py', '--profile', 'errors', '--ir',
                'build/' + prefix + '-stage3.ll']

    selected = set(groups)
    full, sanitize = a.tier != 'sanitize' and not a.only, a.tier != 'full' and not a.only
    correctness = 'correctness' in selected
    # Toolchain variants: own snapshot copy and build directory, run concurrently with the main checks.
    variants = {}
    for version in ('22', '23'):
        if 'llvm' + version in selected:
            # As CI's LLVM jobs: the release's bin directory first on PATH, nothing else changed.
            variants['llvm' + version] = ({**base, 'PATH': f'/usr/lib/llvm-{version}/bin' + os.pathsep + base['PATH']},
                                          [tools['make'], *make[1:]])
    if selected & {'peer-testing', 'peer-semantics'}:
        variants['clang18'] = ({**base, 'MINYAR_TEST_CLANG': 'clang-18', 'MINYAR_TEST_LTO_FLAGS': '-flto -fuse-ld=lld-18',
                                'MINYAR_LLVM_BIN': '/usr/lib/llvm-18/bin'},
                               [tools['make'], '-j1', 'LIMITED=', 'SANITIZER_LIMITED=', 'CC=clang-18', 'LLVM_CC=clang-18',
                                'COMPILER_LTO_FLAGS=-flto -fuse-ld=lld-18'])
    plan['variants'] = {name: shlex.join(variant_make) for name, (_, variant_make) in variants.items()}

    save()
    try:
        copies = {name: subprocess.Popen(['cp', '-a', str(work), str(evidence / ('source-' + name))])
                  for name in variants if not (evidence / ('source-' + name)).exists()}
        runner.run_one(Check('toolchain', ['clang', '--version'], group='setup'))
        for name, copy in copies.items():
            if copy.wait():
                raise RuntimeError('cannot copy the source snapshot for ' + name)
        checks, prebuild, labels = [], [], set()

        def add(*new):
            for check in new:
                if check.label not in labels:
                    labels.add(check.label)
                    checks.append(check)

        if build:
            # The shared build runs in the builder lane; checks needing its goals wait for it.
            add(Check('build', make + build, tier=a.tier, builds=build, group='correctness', expected=60))
        if full and correctness:
            add(Check('compiler-bootstrap-behavior', compiler_behavior('compiler'), goals=['build/compiler-stage3.ll'], group='correctness'),
                Check('module-compiler-bootstrap-behavior', compiler_behavior('module-compiler'),
                      goals=['build/module-compiler-stage3.ll'], group='correctness'),
                Check('runtime-unit', ['./build/runtime-unit'], goals=['build/runtime-unit'], group='correctness'),
                Check('bootstrap-portability-gcc', [python, 'tests/bootstrap-portability.py'], group='correctness',
                      extra_env={'MINYAR_TEST_BOOTSTRAP_CC': 'gcc'}))
        # The leak replay reruns the sanitized runtime unit binary and the focused profiles' fixtures.
        if (sanitize and correctness) or 'leaks' in selected:
            add(Check('runtime-unit-sanitize', ['./build/runtime-unit-sanitize'], goals=['build/runtime-unit-sanitize'],
                      tier='sanitize', group='correctness'))
        rules = check_runner.make_database(make, work, env)
        missing_targets = [name for name in a.only if name not in rules or not rules[name].phony]
        if missing_targets:
            raise RuntimeError('not a phony make target: ' + ', '.join(missing_targets))
        main_roots = [('correctness', targets + (['check-native-graphics'] if full and correctness else [])),
                      ('quic', QUIC_TARGETS), ('formats', ['check-formats', 'check-formats-sanitize']),
                      ('redis', ['check-peer-live-redis', 'check-peer-live-redis-sanitize']),
                      ('coverage', ['check-coverage']), ('afl', ['check-fuzz-coverage'])]
        for group, roots in main_roots:
            if group in selected:
                add(*check_runner.plan_make_checks(rules, roots, make, tier_of, EXPECTED_SECONDS, group=group))
        for check in checks:
            if check.label == 'check-fuzz-coverage':
                check.extra_env = {'MINYAR_AFL_SECONDS': '60'}
        if sanitize and correctness:
            add(Check('regressions-sanitize', [python, 'tests/regressions.py'], tier='sanitize', group='correctness',
                      goals=['build/minyarc-sanitize', 'build/minyar-runtime-sanitize.o'],
                      extra_env={'MINYAR_TEST_COMPILER': str(work / 'build/minyarc-sanitize'),
                                 'MINYAR_TEST_RUNTIME': str(work / 'build/minyar-runtime-sanitize.o'),
                                 'MINYAR_TEST_LINK_FLAGS': '-fsanitize=address,undefined'}))
        if (full and correctness) or 'leaks' in selected:
            add(Check('memory-profiles-focused', [python, 'tests/memory-profile-regressions.py',
                      '--runtime-source', str(work / 'runtime/minyar_runtime.c'), '--suite', 'focused',
                      '--profiles', 'system', 'fixed', 'lazy', '--clang', 'clang',
                      '--output-dir', str(evidence)], group='correctness', expected=70))
        if full and correctness:
            add(Check('critical-path-correctness', [python, 'experiments/memory/critical-path-study.py',
                      '--compiler', str(work / 'build/minyarc'), '--cc', 'clang', '--cxx', 'clang++',
                      '--output', str(evidence / 'critical-path.json')], goals=['build/minyarc'], group='correctness'),
                Check('scalar-path-correctness', [python, 'experiments/memory/checked-scalars-study.py',
                      '--compiler', str(work / 'build/minyarc'), '--cc', 'clang', '--cxx', 'clang++',
                      '--output', str(evidence / 'scalar-path.json')], goals=['build/minyarc'], group='correctness'))
        if 'leaks' in selected:
            add(Check('leaks', [python, 'scripts/check-linux-leaks.py', '--run-dir', str(evidence),
                                '--require', 'runtime-unit-sanitize', '--require', 'memory-profiles-focused'],
                      after=['runtime-unit-sanitize', 'memory-profiles-focused'], tier='sanitize', group='leaks',
                      expected=30))
        if 'formatting' in selected:
            version = re.search(r'^VERSION = "([^"]+)"', (work / 'scripts/format.py').read_text(), re.M).group(1)
            add(Check('formatting', ['sh', '-c', 'set -e; tools=build/format-tools-23; '
                                     '[ -x "$tools/bin/clang-format" ] || { "$0" -m venv "$tools"; '
                                     '"$tools/bin/pip" install -q --disable-pip-version-check "clang-format==$1"; }; '
                                     'CLANG_FORMAT="$tools/bin/clang-format" "$0" scripts/format.py', python, version],
                      group='formatting', expected=20))
        if main_build:
            prebuild += [name for name in LAUNCHER_ARTIFACTS if name in rules]
        for name, (variant_env, variant_make) in variants.items():
            variant = runner.add_variant(check_runner.Variant(name, evidence / ('source-' + name), variant_env,
                                                              variant_make, python))
            variant_rules = check_runner.make_database(variant_make, variant.work, variant_env)
            if name.startswith('llvm'):
                add(*check_runner.plan_make_checks(variant_rules, [*LLVM_TARGETS, 'check-module-driver-options',
                                                                   'check-native-graphics'],
                                                   variant_make, tier_of, EXPECTED_SECONDS, variant, name))
                add(Check(variant.label('ir-verify'), ['sh', '-c', 'llvm-as build/compiler-stage3.ll -o /dev/null && '
                                                       'opt -passes=verify -disable-output build/compiler-stage3.ll'],
                          goals=['build/compiler-stage3.ll'], variant=name, group=name))
            else:
                for group, roots in (('peer-testing', PEER_TESTING_TARGETS), ('peer-semantics', PEER_GATES)):
                    if group in selected:
                        add(*check_runner.plan_make_checks(variant_rules, roots, variant_make, tier_of,
                                                           EXPECTED_SECONDS, variant, group))
            prebuild += [(name, goal) for goal in LAUNCHER_ARTIFACTS if goal in variant_rules]
        plan['checks'] = len(checks)
        runner.run_all(checks, prebuild=prebuild)
    except (OSError, RuntimeError) as error:
        report['error'] = str(error)
        print(str(error), file=sys.stderr)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
        passed = check_runner.summarise(report, sys.stdout, runner.first_row) and 'error' not in report
        report['status'] = 'passed' if passed else 'failed'
        save()
    print(str(report_path), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
