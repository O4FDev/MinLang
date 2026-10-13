#!/usr/bin/env python3
"""Run the portable suite (`make check-portable`) on macOS, one check at a time or in parallel.

Example: python3 scripts/check-macos.py LIMITED= SANITIZER_LIMITED=
Trailing VAR=VALUE arguments are passed to every make call. Checks keep going
past failures, and the run ends with one summary of every failure (its log
path and last 30 lines). --tier full (the default) leaves out sanitizer
checks (including the two sanitizer checks check-portable lists directly),
--tier sanitize runs only them and --tier all runs everything check-portable
runs. --jobs
defaults to one job per 8 GB of physical memory (2 on a 16 GB laptop), at most
the CPU count. The macOS-only checks CI runs next to check-portable (kqueue and
AppKit networking, native graphics, desktop) run too unless --no-extras; the
Keychain checks need --keychain, because they create temporary keychains.
Logs and results.json go to build/check-macos/<run>/."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_runner  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TIERS = ('full', 'sanitize', 'all')
# Scheduling hints only: seconds measured serially on an M1 Pro laptop; the longest start first.
EXPECTED_SECONDS = {
    'check-peer-regressions-cpp-java-js': 500, 'check-peer-regressions-rust-go-zig': 160,
    'check-peer-regressions-python-swift-ruby-lua': 130, 'check-peer-regressions-regressions': 100,
    'check-peer-regressions': 905, 'check-maps': 312, 'check-text-basics-models': 125, 'check-build-wiring': 63,
    'check-errors-language-bounded': 63, 'check-managed-graphs-launcher': 60, 'check-errors-review-bounded': 57,
    'check-peer-manifest': 53, 'check-cycle-registration-exposure-sanitize': 47,
    'check-cycle-private-retirement-sanitize': 41, 'check-managed-graphs': 39, 'check-peer-semantics': 38,
    'check-tls-handshake-validity': 36, 'check-update-launch-native': 32, 'check-statement-nesting': 31,
    'check-cycle-registration-exposure': 31,
}


def tier_of(label):
    return 'sanitize' if 'sanitiz' in label else 'full'


def in_tier(label, tier):
    return tier == 'all' or tier_of(label) == tier


def default_jobs():
    """One job per 8 GB of physical memory, at least 1 and at most the CPU count."""
    try:
        if platform.system() == 'Darwin':
            memory = int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True).stdout)
        else:
            memory = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    except (OSError, ValueError):
        return 1
    return max(1, min(os.cpu_count() or 1, memory // (8 << 30)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--jobs', type=int, default=default_jobs(), help='Checks run at once (default: one per 8 GB of memory, %(default)s here).')
    p.add_argument('--tier', choices=TIERS, default='full', help='full (default) leaves out sanitizer checks; sanitize runs only them; all runs both.')
    p.add_argument('--only', action='append', default=[], metavar='TARGET', help='Run only these checks (repeatable), with their phony prerequisites.')
    p.add_argument('--target', default='check-portable', help='Aggregate make target whose checks run (default check-portable).')
    p.add_argument('--timeout', type=int, default=1800, help='Maximum seconds for each check.')
    p.add_argument('--retries', type=int, default=1, help='Retry each failed check up to this many times alone; a pass on retry is reported as flaky.')
    p.add_argument('--output-dir', type=Path, default=ROOT / 'build/check-macos', help='Parent for the run directory.')
    p.add_argument('--extras', action=argparse.BooleanOptionalAction, default=True, help='Also run the macOS-only network, graphics and desktop checks (default on).')
    p.add_argument('--keychain', action='store_true', help='Also run the Keychain checks; they create temporary keychains (CI only).')
    p.add_argument('--dry-run', action='store_true', help='Print the planned checks without running them.')
    p.add_argument('make_vars', nargs='*', metavar='VAR=VALUE', help='Variables passed to every make call.')
    a = p.parse_args()
    if a.jobs < 1 or a.timeout < 1:
        p.error('jobs and timeout must be positive')
    if any('=' not in item for item in a.make_vars):
        p.error('trailing arguments must be make variables (VAR=VALUE)')
    if platform.system() != 'Darwin' and not a.dry_run:
        print('note: this runner is meant for macOS; use scripts/check-linux.py on Linux', file=sys.stderr)
    env = {name: value for name, value in os.environ.items() if name not in ('MAKEFLAGS', 'MFLAGS', 'MAKELEVEL')}
    # Each make is serial; concurrency comes from running several checks at once.
    make = ['make', '-j1', *a.make_vars]
    rules = check_runner.make_database(make, ROOT, env)
    if a.target not in rules or not rules[a.target].phony:
        p.error('not a phony make target: ' + a.target)
    aggregate = rules[a.target]
    children = [name for name in dict.fromkeys(aggregate.prerequisites + aggregate.order_only)
                if name in rules and rules[name].phony]
    unknown = [name for name in a.only if name not in children]
    if unknown:
        p.error(f'not a check in {a.target}: ' + ', '.join(unknown))
    # --only names checks explicitly, whatever their tier.
    roots = [name for name in children if name in a.only] if a.only else [name for name in children if in_tier(name, a.tier)]
    checks = check_runner.plan_make_checks(rules, roots, make, tier_of, EXPECTED_SECONDS)
    if a.tier != 'sanitize' and not a.only:
        checks.append(check_runner.aggregate_check(rules, a.target, make, {check.label for check in checks}, 'full'))
    if a.extras and a.target == 'check-portable' and not a.only:
        planned = {check.label for check in checks}
        python = sys.executable
        if a.tier != 'sanitize':
            checks += [check_runner.Check('macos-network', [python, 'tests/macos-network.py'], expected=60),
                       check_runner.Check('desktop-native', [python, 'tests/desktop-native.py'], expected=15)]
            if 'check-native-graphics' not in planned:
                checks += check_runner.plan_make_checks(rules, ['check-native-graphics'], make, tier_of, {})
        if a.tier != 'full' and 'check-net-udp-offload-sanitize' not in planned:
            checks += check_runner.plan_make_checks(rules, ['check-net-udp-offload-sanitize'], make, tier_of, {})
        if a.keychain and a.tier != 'sanitize':
            checks += [check_runner.Check('macos-services', [python, 'tests/macos-services.py']),
                       check_runner.Check('keychain-native', [python, 'tests/keychain-native.py'])]
    if a.dry_run:
        print(json.dumps({'jobs': a.jobs, 'tier': a.tier, 'make': make,
                          'checks': [{'label': c.label, 'goals': c.goals, 'after': list(c.after)} for c in checks]},
                         indent=2))
        return 0
    a.output_dir.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S-'), dir=a.output_dir)).resolve()
    logs = run / 'logs'
    logs.mkdir()
    report_path = run / 'results.json'
    report = {'status': 'running', 'invocation': sys.argv, 'platform': platform.uname()._asdict(),
              'jobs': a.jobs, 'tier': a.tier, 'make': make, 'checks': []}

    def save():
        temporary = report_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(report_path)

    print(f'{len(checks)} checks from {a.target} (tier {a.tier}, jobs {a.jobs}); logs in {logs}', flush=True)
    # Serial runs keep the host TMPDIR; parallel checks each get their own.
    temporary = Path(tempfile.mkdtemp(prefix='mc-')) if a.jobs > 1 else None
    runner = check_runner.Runner(work=ROOT, logs=logs, env=env, make=make, jobs=a.jobs, timeout=a.timeout,
                                 report=report, save=save, retries=a.retries, temporary=temporary,
                                 python=sys.executable)
    save()
    try:
        prebuild = [name for name in (
            "build/minyarc", "build/minyarc-modules", "build/minyar-module-build",
            "build/minyar-default-runtime.o", "build/minyar-default-runtime-release.ll",
            "build/minyar-runtime-eager.o", "build/minyar-runtime-eager-release.ll",
            "build/minyarc-errors-request", "build/minyarc-errors",
            "build/minyarc-callbacks", "build/minyarc-calldepth") if name in rules]
        runner.run_all(checks, prebuild=prebuild)
    except (OSError, RuntimeError) as error:
        report['error'] = str(error)
        print(str(error), file=sys.stderr)
    finally:
        if temporary:
            shutil.rmtree(temporary, ignore_errors=True)
        passed = check_runner.summarise(report, sys.stdout) and 'error' not in report
        report['status'] = 'passed' if passed else 'failed'
        save()
    print(str(report_path), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
