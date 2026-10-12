"""Run make check targets in parallel, keep going past failures, then summarise.

Shared by scripts/check-linux.py and scripts/check-macos.py. Every check runs
`make <target>` in one shared work directory, so two makes must never build the
same file at once. The plan comes from the make database:

- every phony prerequisite of a selected target becomes its own check, and the
  parent runs with `make -o <child>`, so each recipe runs once;
- file prerequisites are built by a single builder, one goal per make call,
  before any check that needs them starts. A check whose prerequisites failed
  to build runs in the builder's lane, so its make never races another build;
- every builder make holds build/bootstrap.lock, the lock the `minyar`
  launcher takes before its own nested make, so the two never overlap;
- checks with tight wall-clock assertions (EXCLUSIVE) run with nothing else
  running, and checks sharing a fixed port or path (GROUPS) never overlap.

A failed check is retried once with nothing else running. If the retry passes,
the check counts as passed and is listed as flaky.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time

RULE = re.compile(r'^([^\s#:=][^:=]*?)::?(?![=])\s*(.*)$')
TAIL_LINES = 30
# Wall-clock assertions (a 30 ms readiness window, 400 ms handshake rounds)
# that fail under load: these run with nothing else running.
EXCLUSIVE = frozenset({'check-net-udp-offload', 'check-net-udp-offload-sanitize',
                       'check-peer-edge-cids', 'check-peer-edge-cids-sanitize'})
# Checks sharing a fixed resource: at most GROUP_LIMITS[group] (default 1) run at once.
GROUPS = {'check-quic-rfc': 'udp-port-44300', 'check-quic-rfc-sanitize': 'udp-port-44300',
          'check-modules': 'build/module-tests', 'check-sanitize': 'build/module-tests'}
# peer-edge and redis harnesses pick a free port, close it, then reuse it.
GROUP_PREFIXES = (('check-peer-edge', 'reused-ports'), ('check-peer-live-redis', 'reused-ports'))
GROUP_LIMITS = {'reused-ports': 3}
LOCKED = ('import fcntl, os, sys\n'
          'os.makedirs(os.path.dirname(sys.argv[1]), exist_ok=True)\n'
          'lock = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)\n'
          'fcntl.flock(lock, fcntl.LOCK_EX)\n'
          'os.set_inheritable(lock, True)\n'
          'os.execvp(sys.argv[2], sys.argv[2:])\n')


def group_of(label):
    if label in GROUPS:
        return GROUPS[label]
    return next((group for prefix, group in GROUP_PREFIXES if label.startswith(prefix)), None)


class Rule:
    def __init__(self, name, prerequisites, order_only, target):
        self.name, self.prerequisites, self.order_only = name, prerequisites, order_only
        self.target, self.phony, self.recipe = target, False, False


def make_database(make, cwd, env):
    """Parse `make -pq` without running any recipe."""
    output = subprocess.run([*make, '-pq', 'FORCE'], cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, errors='replace').stdout
    if '\n# Files\n' not in output:
        raise RuntimeError('make -p printed no file database')
    files = output.split('\n# Files\n', 1)[1].split('\n# files hash-table stats', 1)[0]
    rules, phony = {}, set()
    for block in files.split('\n\n'):
        target, rule = True, None
        for line in block.split('\n'):
            if line == '# Not a target:':
                target = False
            elif line.startswith('\t'):
                if rule:
                    rule.recipe = True
            elif line.startswith('#'):
                if rule and line.startswith('#  Phony target'):
                    rule.phony = True
            elif rule is None and (match := RULE.match(line)):
                normal, _, order_only = match.group(2).partition('|')
                rule = Rule(match.group(1).strip(), normal.split(), order_only.split(), target)
        if rule:
            if rule.name == '.PHONY':
                phony.update(rule.prerequisites)
            else:
                rules[rule.name] = rule
    for name in phony:
        if name in rules:
            rules[name].phony = True
    return rules


class Check:
    def __init__(self, label, command, *, goals=(), after=(), extra_env=None, exclusive=None,
                 tier='full', expected=10.0):
        self.label, self.command, self.goals, self.after = label, command, list(goals), list(after)
        self.extra_env, self.tier, self.expected = extra_env or {}, tier, expected
        self.exclusive = label in EXCLUSIVE if exclusive is None else exclusive
        self.group = group_of(label)


def plan_make_checks(rules, roots, make, tier_of, expected):
    """Split roots and their phony prerequisites into checks with build goals."""
    checks, order = {}, []

    def visit(name):
        if name in checks:
            return
        rule = rules.get(name)
        if rule is None:
            raise RuntimeError('make has no rule for check target ' + name)
        prerequisites = rule.prerequisites + rule.order_only
        children = [p for p in prerequisites if p in rules and rules[p].phony]
        goals = [p for p in prerequisites if p not in children and p in rules and rules[p].target]
        skip = [arg for child in dict.fromkeys(children) for arg in ('-o', child)]
        checks[name] = Check(name, [*make, *skip, name], goals=goals, after=dict.fromkeys(children),
                             tier=tier_of(name), expected=expected.get(name, 10.0))
        for child in children:
            visit(child)
        order.append(name)

    for root in roots:
        visit(root)
    return [checks[name] for name in order]


def aggregate_check(rules, name, make, planned, tier, expected=1.0):
    """Run an aggregate's own recipe after its planned children; skip all of its children."""
    rule = rules[name]
    prerequisites = rule.prerequisites + rule.order_only
    children = [p for p in dict.fromkeys(prerequisites) if p in rules and rules[p].phony]
    goals = [p for p in prerequisites if p not in children and p in rules and rules[p].target]
    skip = [arg for child in children for arg in ('-o', child)]
    return Check(name, [*make, *skip, name], goals=goals, after=[c for c in children if c in planned],
                 tier=tier, expected=expected)


class Runner:
    """Schedule checks over `jobs` slots; the report rows stay in report['checks']."""

    def __init__(self, *, work, logs, env, make, jobs, timeout, report, save, retries=1,
                 previous=None, runner_sha256=None, temporary=None, python='python3'):
        self.work, self.logs, self.env, self.make = work, logs, env, make
        self.locked = [python, '-c', LOCKED, str(Path(work) / 'build/bootstrap.lock')]
        self.jobs, self.timeout, self.report, self.save = max(1, jobs), timeout, report, save
        self.retries, self.previous, self.runner_sha256 = retries, previous, runner_sha256
        # Each check gets its own TMPDIR, so tests using fixed names under the
        # temporary directory cannot collide. Keep it short for socket paths.
        self.temporary = temporary
        self.built, self.failed_goals = set(), set()
        self.results, self.reused = {}, []

    def environment(self, check, index):
        env = {**self.env, **check.extra_env}
        if self.temporary:
            env['TMPDIR'] = str(self.temporary / str(index))
            Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
        return env

    def environment_sha256(self, check):
        # Hash the inherited environment without recording possible secrets.
        return hashlib.sha256(json.dumps({**self.env, **check.extra_env}, sort_keys=True).encode()).hexdigest()

    def reuse(self, check, env_hash):
        for index, previous in enumerate(self.previous or ()):
            if previous.get('returncode') != 0 or previous.get('command') != check.command:
                continue
            known = previous.get('environment_sha256')
            if known == env_hash if known else not check.extra_env and check.label != 'regressions-sanitize':
                return {'label': check.label, 'original_index': index, 'legacy_environment_unknown': known is None}
        return None

    # -- processes -------------------------------------------------------
    def start(self, label, command, env, log):
        output = log.open('a')
        output.write('$ ' + shlex.join(command) + '\n')
        output.flush()
        child = subprocess.Popen(command, cwd=self.work, env=env,
                                 stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        return {'child': child, 'output': output, 'started': time.monotonic(), 'log': log}

    def finish(self, process, wait=False):
        child = process['child']
        if wait:
            try:
                child.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                pass
        timed_out = child.poll() is None and time.monotonic() - process['started'] > self.timeout
        if timed_out:
            # Kill the whole compiler/test group; never leave timed-out
            # grandchildren consuming resources during later checks.
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        elif child.poll() is None:
            return None
        process['output'].close()
        return {'returncode': None if timed_out else child.returncode, 'timed_out': timed_out,
                'duration_seconds': round(time.monotonic() - process['started'], 3)}

    def kill_all(self, processes):
        for process in processes:
            if process['child'].poll() is None:
                os.killpg(process['child'].pid, signal.SIGKILL)
                process['child'].wait()
            process['output'].close()

    # -- one check, run alone ------------------------------------------------
    def run_one(self, check):
        """Run a check with nothing else running; returns its report row."""
        row = self.begin(check)
        if row is None:
            return {'returncode': 0, 'reused': True}
        process = self.launch(check, row)
        row.update(self.finish(process, wait=True))
        return self.end(check, row)

    def begin(self, check):
        """Record a new report row, or return None when an identical success is reused."""
        env_hash = self.environment_sha256(check)
        reused = self.reuse(check, env_hash)
        if reused is not None:
            self.results[check.label] = 'passed'
            self.reused.append(reused)
            self.save()
            print(check.label + ': reused successful identical check', flush=True)
            return None
        index = len(self.report['checks'])
        log = self.logs / f'{index:03d}-{check.label}.log'
        row = {'label': check.label, 'command': check.command, 'log': str(log), 'tier': check.tier,
               'timeout_seconds': self.timeout, 'extra_env': check.extra_env,
               'environment_sha256': env_hash, 'runner_sha256': self.runner_sha256, 'index': index}
        self.report['checks'].append(row)
        self.save()
        print(check.label, flush=True)
        return row

    def launch(self, check, row, locked=False):
        command = [*self.locked, *check.command] if locked else check.command
        return self.start(check.label, command, self.environment(check, row['index']), Path(row['log']))

    def end(self, check, row):
        passed = row.get('returncode') == 0
        self.results[check.label] = 'passed' if passed else 'failed'
        self.save()
        if passed:
            print(f"{check.label}: passed ({row['duration_seconds']:.3f}s)", flush=True)
        else:
            reason = 'timed out' if row.get('timed_out') else f"exit {row.get('returncode')}"
            print(f"{check.label}: FAILED ({reason}, {row['duration_seconds']:.3f}s); see {row['log']}", flush=True)
        return row

    def block(self, check, blockers):
        index = len(self.report['checks'])
        row = {'label': check.label, 'command': check.command, 'tier': check.tier, 'returncode': None,
               'blocked_by': blockers, 'duration_seconds': 0.0, 'index': index,
               'log': str(self.logs / f'{index:03d}-{check.label}.log'), 'timeout_seconds': self.timeout,
               'extra_env': check.extra_env, 'environment_sha256': self.environment_sha256(check),
               'runner_sha256': self.runner_sha256}
        self.report['checks'].append(row)
        self.results[check.label] = 'failed'
        self.save()
        print(f"{check.label}: FAILED (prerequisite check failed: {', '.join(blockers)})", flush=True)

    # -- many checks ---------------------------------------------------------
    def run_all(self, checks, prebuild=()):
        """Run checks concurrently; failures never stop the others.

        prebuild names artifacts no check declares but harnesses build on
        demand (through the launcher); the builder makes them early."""
        by_label = {check.label: check for check in checks}
        pending = sorted(checks, key=lambda c: -c.expected)
        running = []  # (check or goal, process, row, lane)
        # Build first the goals that unblock the most expected check time.
        weights = {goal: 1.0 for goal in prebuild}
        for check in pending:
            for goal in check.goals:
                weights[goal] = weights.get(goal, 0.0) + check.expected
        builder_order = sorted((goal for goal in weights if goal not in self.built), key=lambda goal: -weights[goal])
        prerequisite_log = self.logs / 'prerequisites.log'
        self.report.setdefault('prerequisites', {})

        def busy(lane=None):
            return [entry for entry in running if lane is None or entry[3] == lane]

        def group_full(check):
            if check.group is None:
                return False
            members = sum(1 for item, _, _, lane in running if lane != 'goal' and item.group == check.group)
            return members >= GROUP_LIMITS.get(check.group, 1)

        def goals_ready(check):
            return all(goal in self.built for goal in check.goals)

        def goals_failed(check):
            return any(goal in self.failed_goals for goal in check.goals)

        def after_state(check):
            states = [self.results.get(name) for name in check.after if name in by_label]
            if any(state is None for state in states):
                return 'waiting'
            failed = [name for name in check.after if self.results.get(name) == 'failed']
            return failed or 'ready'

        try:
            while pending or running:
                # Reap finished work.
                for entry in list(running):
                    item, process, row, lane = entry
                    status = self.finish(process)
                    if status is None:
                        continue
                    running.remove(entry)
                    if lane == 'goal':
                        ok = status['returncode'] == 0
                        (self.built if ok else self.failed_goals).add(item)
                        self.report['prerequisites'][item] = {**status, 'log': str(prerequisite_log)}
                        self.save()
                        if not ok:
                            print(f'prerequisite {item}: FAILED to build; see {prerequisite_log}', flush=True)
                    else:
                        row.update(status)
                        self.end(item, row)
                exclusive_running = any(lane == 'exclusive' for _, _, _, lane in running)
                # Blocked checks fail without running, as make would.
                for check in list(pending):
                    state = after_state(check)
                    if isinstance(state, list):
                        pending.remove(check)
                        self.block(check, state)
                if exclusive_running:
                    time.sleep(0.2)
                    continue
                # The builder: one make at a time, either a goal or a check whose goals failed.
                if not busy('goal') and not busy('builder') and len(running) < self.jobs:
                    started = False
                    for check in pending:
                        if (after_state(check) == 'ready' and goals_failed(check) and not check.exclusive
                                and not group_full(check)):
                            pending.remove(check)
                            row = self.begin(check)
                            if row is not None:
                                running.append((check, self.launch(check, row, locked=True), row, 'builder'))
                            started = True
                            break
                    while not started and builder_order:
                        goal = builder_order.pop(0)
                        if goal in self.built or goal in self.failed_goals:
                            continue
                        print('prerequisite ' + goal, flush=True)
                        running.append((goal, self.start('prerequisite', [*self.locked, *self.make, goal], self.env,
                                                         prerequisite_log), None, 'goal'))
                        started = True
                # Ordinary checks fill the remaining slots, longest first.
                for check in list(pending):
                    if len(running) >= self.jobs:
                        break
                    if check.exclusive or after_state(check) != 'ready' or not goals_ready(check) or group_full(check):
                        continue
                    pending.remove(check)
                    row = self.begin(check)
                    if row is not None:
                        running.append((check, self.launch(check, row), row, 'check'))
                # Exclusive checks start only when nothing else runs.
                if not running:
                    for check in pending:
                        if check.exclusive and after_state(check) == 'ready' and (goals_ready(check) or goals_failed(check)):
                            pending.remove(check)
                            row = self.begin(check)
                            if row is not None:
                                running.append((check, self.launch(check, row), row, 'exclusive'))
                            break
                    else:
                        if pending and not builder_order:
                            # Nothing can start and nothing runs: report what is stuck.
                            for check in list(pending):
                                pending.remove(check)
                                self.block(check, [name for name in check.after if self.results.get(name) != 'passed']
                                           or ['unbuilt prerequisites'])
                if running:
                    time.sleep(0.2)
        except BaseException:
            self.kill_all([process for _, process, _, _ in running])
            raise
        self.retry_failures(by_label)

    def retry_failures(self, by_label):
        """Retry real failures once, alone, so load-induced timing failures surface as flaky."""
        rows = {row['label']: row for row in self.report['checks'] if 'label' in row}
        for label, check in by_label.items():
            row = rows.get(label)
            if self.retries < 1 or row is None or row.get('returncode') == 0 or row.get('blocked_by'):
                continue
            print(f'{label}: retrying alone', flush=True)
            with open(row['log'], 'a') as log:
                log.write('\n--- retry with nothing else running ---\n')
            process = self.launch(check, row)
            status = self.finish(process, wait=True)
            row['first_attempt'] = {key: row.get(key) for key in ('returncode', 'timed_out', 'duration_seconds')}
            row.update(status)
            if status['returncode'] == 0:
                row['flaky'] = True
            self.end(check, row)
        # A check blocked only by checks that passed on retry now runs alone.
        progress = True
        while progress:
            progress = False
            for label, check in by_label.items():
                row = rows.get(label)
                if not row or not row.get('blocked_by') or self.results.get(label) == 'passed':
                    continue
                if all(self.results.get(name) == 'passed' for name in row['blocked_by']):
                    print(f"{label}: prerequisites passed on retry; running alone", flush=True)
                    row['was_blocked_by'] = row.pop('blocked_by')
                    row.update(self.finish(self.launch(check, row), wait=True))
                    self.end(check, row)
                    progress = True


def tail(path, lines=TAIL_LINES):
    try:
        with open(path, 'rb') as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - 65536))
            text = stream.read().decode('utf-8', 'replace')
    except OSError as error:
        return f'(cannot read log: {error})'
    return '\n'.join(text.splitlines()[-lines:])


def summarise(report, stream):
    """Print one summary of every failure; return True when everything passed."""
    rows = [row for row in report['checks'] if 'label' in row]
    latest = {}
    for row in rows:
        latest[row['label']] = row
    failed = [row for row in latest.values() if row.get('returncode') != 0]
    flaky = [row for row in latest.values() if row.get('flaky')]
    broken = {goal: status for goal, status in report.get('prerequisites', {}).items() if status.get('returncode') != 0}
    print('\n' + '=' * 78, file=stream)
    print(f'{len(latest)} checks: {len(latest) - len(failed)} passed, {len(failed)} failed, '
          f'{len(flaky)} flaky (passed when retried alone)', file=stream)
    for goal, status in broken.items():
        print(f'prerequisite failed to build: {goal} (log {status.get("log")})', file=stream)
    for row in flaky:
        print(f'flaky: {row["label"]} (first attempt {row["first_attempt"]}; log {row["log"]})', file=stream)
    for row in failed:
        print('-' * 78, file=stream)
        if row.get('blocked_by'):
            blockers = [name for name in row['blocked_by'] if latest.get(name, {}).get('returncode') != 0]
            print(f'FAILED {row["label"]}: not run; prerequisite check failed: {", ".join(blockers)}', file=stream)
            continue
        reason = 'timed out' if row.get('timed_out') else f'exit {row.get("returncode")}'
        print(f'FAILED {row["label"]} ({reason}); log {row["log"]}', file=stream)
        print('$ ' + shlex.join(row['command']), file=stream)
        print(tail(row['log']), file=stream)
    if failed:
        print('=' * 78, file=stream)
        print('Failed checks: ' + ' '.join(row['label'] for row in failed), file=stream)
    stream.flush()
    return not failed
