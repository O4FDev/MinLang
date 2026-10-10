#!/usr/bin/env python3
"""Opt-in RED acceptance tests for event scheduling; never an assertion of perfection."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

if not __debug__:
    raise RuntimeError('acceptance checks require Python assertions; do not use -O or PYTHONOPTIMIZE')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OPERATIONS = ('poll', 'allocate', 'text', 'record', 'append', 'replace', 'field',
              'local', 'borrow', 'step', 'frame', 'release', 'stack')
PROFILES = {
    'system': ['-DMINYAR_SYSTEM_HEAP=1'],
    'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
    'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1'],
}


@dataclass(frozen=True)
class Case:
    group: str
    name: str
    budget: int = 0
    extra: int = 0

    @property
    def label(self):
        return f'{self.group}/{self.name}/budget-{self.budget}/extra-{self.extra}'


def cases():
    yield Case('capability', 'event_scope')
    yield Case('capability', 'idle')
    for budget in (0, 1, 7, 32):
        for operation in OPERATIONS:
            yield Case('operation', operation, budget)
        for kind in ('nested', 'nested_tight', 'nested_partial', 'reset', 'outside'):
            yield Case('scope', kind, budget)
    for budget in (0, 1, 7, 32, 97):
        for stop in (0, 1, 2, 5):
            yield Case('idle', 'interrupt', budget, stop)
        yield Case('idle', 'empty', budget, 5)
        yield Case('idle', 'inside', budget, 5)
    for width in (1, 7, 64):
        for burst in (1, 4, 16):
            yield Case('sustained', 'recovery', width, burst)
    for kind in ('shared', 'text', 'zero_poll', 'stack', 'chain', 'dag'):
        for budget in (1, 8, 32):
            yield Case('safety', kind, budget)


def check_result(case, result, runtime_budget):
    """Acceptance policy independent of process execution; used by mutation tests."""
    required = {'work', 'visits', 'extra', 'pending', 'event_scope', 'idle', 'final_bytes'}
    if not isinstance(result, dict) or set(result) != required or any(type(v) is not int or v < 0 for v in result.values()):
        raise AssertionError('missing, extra, noninteger or negative fixture evidence')
    if result['event_scope'] not in (0, 1) or result['idle'] not in (0, 1):
        raise AssertionError('invalid capability marker')
    assert result['final_bytes'] == 0, 'leaked managed memory after full teardown'
    work, visits, extra = (result[k] for k in ('work', 'visits', 'extra'))
    if case.group == 'capability':
        assert result[case.name] == 1, f'{case.name} integration is not implemented; see acceptance_adapter.h'
    elif case.group in ('operation', 'scope'):
        assert visits <= work, 'actual old-object progress exceeds reported queued work'
        assert work <= case.budget, (
            f'event allowed {case.budget} queued units, executed {work}; '
            f'old object advanced {visits} fields (event integration={result["event_scope"]})')
        if case.group == 'scope':
            assert work == case.budget, 'explicit polls failed to use available event allowance'
            if case.name == 'reset':
                assert extra == case.budget, 'next event did not get exactly its own allowance'
            elif case.name == 'outside':
                assert extra == runtime_budget, 'ended event left ordinary polling disabled'
            elif case.name == 'nested_tight':
                assert extra == case.budget // 2, 'child allowance ignored or parent credit lost on child exit'
            elif case.name == 'nested_partial':
                assert extra == max(0, case.budget - 1), 'child refilled a partly spent parent allowance'
    elif case.group == 'idle':
        assert result['idle'] == 1, 'interruptible idle integration is not implemented'
        assert work == visits and work <= case.budget, 'idle work cap/accounting mismatch'
        if case.name in ('inside', 'empty') or case.budget == 0 or case.extra == 0:
            assert work == 0, 'cleanup ran while forbidden, empty, out of budget, or already ready'
        else:
            assert work > 0, 'idle opportunity made no progress despite debt and allowance'
            assert extra > 0, 'readiness callback was never checked'
            assert work <= case.extra * runtime_budget, 'more than one K batch ran per readiness check'
    elif case.group == 'sustained':
        assert result['event_scope'] == result['idle'] == 1, 'event/idle integration is missing'
        assert visits == 0, f'{visits}/128 declared recovery opportunities failed to recover storage'
        demand = 128 * case.extra * (case.budget + 1)
        assert work == demand, f'cleanup shifted outside declared opportunities: {work} != {demand}'
        # All dead storage consists of exactly burst records of this width.
        byte_limit = case.extra * (8 + 8 + 9 * case.budget)
        assert extra <= byte_limit, f'dead managed bytes {extra} exceed finite workload bound {byte_limit}'


def instrument(source):
    """Only a cumulative observer; no scheduling changes or clocks."""
    start = 'size_t minyar_rc_poll(size_t budget) {'
    finish = '    rc_bounded_last_work = work;\n#endif\n    return work;'
    if source.count(start) != 1 or source.count(finish) != 1:
        raise ValueError('poll instrumentation site changed: review the observer before running')
    return source.replace(start, 'static size_t acceptance_queued_work;\n' + start).replace(
        finish, '    rc_bounded_last_work = work;\n#endif\n    acceptance_queued_work += work;\n    return work;')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profiles', choices=PROFILES, nargs='+', default=list(PROFILES))
    p.add_argument('--budgets', type=int, nargs='+', default=[1, 8, 32])
    p.add_argument('--sanitize', action='store_true')
    p.add_argument('--adapter', type=Path)
    p.add_argument('--clang', default='clang')
    p.add_argument('--filter', default='*', help='glob over case labels')
    p.add_argument('--list', action='store_true')
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if any(k < 1 or k > 1024 for k in args.budgets):
        p.error('runtime budgets must be 1..1024')
    if len(set(args.budgets)) != len(args.budgets) or len(set(args.profiles)) != len(args.profiles):
        p.error('duplicate configurations')
    if args.adapter and not args.adapter.is_file():
        p.error('adapter header does not exist')
    selected = [c for c in cases() if fnmatch.fnmatchcase(c.label, args.filter)]
    if not selected:
        p.error('filter selects no tests')
    if args.list:
        for case in selected: print(case.label)
        print(f'{len(selected)} scenarios x {len(args.profiles)} profiles x {len(args.budgets)} budgets')
        return 0
    out = (args.output or ROOT / 'build' / ('reclamation-acceptance-' +
           datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))).resolve()
    out.mkdir(parents=True, exist_ok=False)
    snapshot = out / 'snapshot'
    (snapshot / 'runtime').mkdir(parents=True)
    fixture = snapshot / 'research/reclamation'; fixture.mkdir(parents=True)
    sources = [*sorted((ROOT / 'runtime').glob('*.[ch]')),
               HERE / 'acceptance_runtime.c', HERE / 'acceptance_adapter.h', Path(__file__).resolve()]
    for source in sources:
        dest = snapshot / source.relative_to(ROOT)
        shutil.copy2(source, dest)
    header = snapshot / 'runtime/minyar_bounded_rc.h'
    header.write_text(instrument(header.read_text()))
    adapter = None
    if args.adapter:
        adapter = fixture / 'candidate_adapter.h'; shutil.copy2(args.adapter, adapter)
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    manifest = {'schema': 1, 'status': 'running', 'sanitize': args.sanitize,
                'source_sha256': {str(s.relative_to(ROOT)): sha(s) for s in sources},
                'instrumented_sha256': sha(header), 'adapter_sha256': sha(adapter) if adapter else None,
                'planned_tests': len(selected) * len(args.profiles) * len(args.budgets),
                'builds': [], 'tests': [], 'invocation': sys.argv}

    def save():
        temporary = out / 'results.json.tmp'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(out / 'results.json')

    save()
    for profile in args.profiles:
        for budget in args.budgets:
            name = f'{profile}-k{budget}'
            binary = out / name
            command = [args.clang, '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                       *PROFILES[profile], '-DMINYAR_BOUNDED_HEAP_BYTES=4194304',
                       '-DMINYAR_INTEGER_TEXT_CACHE_LIMIT=0', f'-DMINYAR_RC_POLL_BUDGET={budget}']
            if adapter: command.append(f'-DACCEPTANCE_ADAPTER="{adapter}"')
            if args.sanitize: command += ['-g', '-fsanitize=address,undefined']
            command += [str(fixture / 'acceptance_runtime.c'), '-o', str(binary)]
            print(f'Building {name} ({"ASan/UBSan" if args.sanitize else "native"})', flush=True)
            try:
                compiled = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
            except (OSError, subprocess.TimeoutExpired) as error:
                manifest.update(status='error', reason=str(error)); save()
                print(str(error), file=sys.stderr)
                return 2
            (out / f'{name}.build.stderr').write_text(compiled.stderr)
            manifest['builds'].append({'configuration': name, 'argv': command,
                                       'returncode': compiled.returncode,
                                       'binary_sha256': sha(binary) if compiled.returncode == 0 else None})
            if compiled.returncode:
                manifest['status'] = 'error'; save()
                print(compiled.stderr, file=sys.stderr)
                return 2
            failures = 0
            for case in selected:
                command = [str(binary), case.group, case.name, str(case.budget), str(case.extra)]
                entry = {'name': f'{name}/{case.label}', 'argv': command, 'status': 'passed'}
                try:
                    run = subprocess.run(command, capture_output=True, text=True, env=env, timeout=15)
                    entry.update(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
                    assert run.returncode == 0, f'fixture failed/crashed ({run.returncode}): {run.stderr[-1000:]}'
                    result = json.loads(run.stdout); entry['metrics'] = result
                    check_result(case, result, budget)
                except (AssertionError, ValueError, subprocess.TimeoutExpired) as error:
                    entry.update(status='failed', reason=str(error)); failures += 1
                manifest['tests'].append(entry)
            print(f'{name}: {len(selected) - failures} passed, {failures} failed', flush=True)
            save()
    failed = sum(t['status'] != 'passed' for t in manifest['tests'])
    manifest['status'] = 'failed' if failed else 'passed'; save()
    print(f'{len(manifest["tests"])} tests: {len(manifest["tests"]) - failed} passed, {failed} failed')
    print(f'Evidence: {out / "results.json"}')
    return int(failed != 0)


if __name__ == '__main__':
    sys.exit(main())
