"""Run make check targets in parallel, keep going past failures, then summarise.

Shared by scripts/check-linux.py and scripts/check-macos.py. Every check runs
`make <target>` in a work directory, so two makes must never build the same
file at once. The plan comes from the make database:

- every phony prerequisite of a selected target becomes its own check, and the
  parent runs with `make -o <child>`, so each recipe runs once;
- file prerequisites are built by a single builder per work directory, one
  goal per make call, before any check that needs them starts. A check whose
  prerequisites failed to build runs in the builder's lane, so its make never
  races another build;
- every builder make holds build/bootstrap.lock, the lock the `minyar`
  launcher takes before its own nested make, so the two never overlap;
- checks with tight wall-clock assertions (EXCLUSIVE) run only alongside each
  other, never with ordinary checks, and checks sharing a fixed port or path
  (GROUPS) never overlap.

A Variant is one work directory with its own toolchain, environment and make
command (for example a copy of the sources built with LLVM 22). Checks in
different variants share the job slots but never a build directory, so each
variant has its own builder lane and they build concurrently.

A failed check is retried once with nothing else running. If the retry passes,
the check counts as passed and is listed as flaky.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

RULE = re.compile(r'^([^\s#:=][^:=]*?)::?(?![=])\s*(.*)$')
TAIL_LINES = 30
# Wall-clock assertions (a 30 ms readiness window, 400 ms handshake rounds)
# that fail under load: these never run alongside ordinary checks.
EXCLUSIVE = frozenset({'check-net-udp-offload', 'check-net-udp-offload-sanitize',
                       'check-peer-edge-cids', 'check-peer-edge-cids-sanitize'})
# Checks sharing a fixed resource: at most GROUP_LIMITS[group] (default 1) run at once.
# Groups named after a build path are per work directory; the others (ports) are machine-wide.
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
# Build a check's goals holding the lock, then release it before the check
# runs: its harnesses call the launcher, which takes the same lock.
BUILD_THEN_RUN = ('import fcntl, os, subprocess, sys\n'
                  'count = int(sys.argv[2])\n'
                  'build, command = sys.argv[3:3 + count], sys.argv[3 + count:]\n'
                  'os.makedirs(os.path.dirname(sys.argv[1]), exist_ok=True)\n'
                  'lock = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)\n'
                  'fcntl.flock(lock, fcntl.LOCK_EX)\n'
                  'status = subprocess.call(build)\n'
                  'os.close(lock)\n'
                  'if status:\n'
                  '    sys.exit(status)\n'
                  'os.execvp(command[0], command)\n')


def target_of(label):
    """The make target behind a label; other variants prefix it with `variant:`."""
    return label.rsplit(':', 1)[-1]


def group_of(label):
    target = target_of(label)
    if target in GROUPS:
        return GROUPS[target]
    return next((group for prefix, group in GROUP_PREFIXES if target.startswith(prefix)), None)


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
            elif match := RULE.match(line):
                normal, _, order_only = match.group(2).partition('|')
                if rule is None:
                    rule = Rule(match.group(1).strip(), normal.split(), order_only.split(), target)
                elif match.group(1).strip() == rule.name:
                    # Double-colon rules list one rule line per definition.
                    rule.prerequisites += normal.split()
                    rule.order_only += order_only.split()
        if rule:
            if rule.name == '.PHONY':
                phony.update(rule.prerequisites)
            else:
                rules[rule.name] = rule
    for name in phony:
        if name in rules:
            rules[name].phony = True
    return rules


class Variant:
    """One work directory with its own build directory, environment and make command."""

    def __init__(self, name, work, env, make, python='python3'):
        self.name, self.work, self.env, self.make = name, Path(work), env, list(make)
        self.lock = str(self.work / 'build/bootstrap.lock')
        self.locked = [python, '-c', LOCKED, self.lock]
        self.built, self.failed_goals = set(), set()

    def label(self, name):
        return f'{self.name}:{name}' if self.name else name


class Check:
    def __init__(self, label, command, *, goals=(), after=(), extra_env=None, exclusive=None,
                 tier='full', expected=10.0, variant='', group=None, builds=()):
        self.label, self.command, self.goals, self.after = label, command, list(goals), list(after)
        self.extra_env, self.tier, self.expected = extra_env or {}, tier, expected
        self.exclusive = target_of(label) in EXCLUSIVE if exclusive is None else exclusive
        self.resource = group_of(label)
        if self.resource and self.resource.startswith('build/'):
            self.resource = f'{variant}:{self.resource}'
        # variant names the work directory; group is the matrix group it was planned for.
        self.variant, self.group = variant, group
        # builds: goals this check makes; it runs in its variant's builder lane, holding the lock.
        self.builds = list(builds)


def plan_make_checks(rules, roots, make, tier_of, expected, variant=None, group=None):
    """Split roots and their phony prerequisites into checks with build goals."""
    checks, order = {}, []
    name_of = variant.label if variant else (lambda name: name)
    where = variant.name if variant else ''

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
        checks[name] = Check(name_of(name), [*make, *skip, name], goals=goals,
                             after=[name_of(child) for child in dict.fromkeys(children)],
                             tier=tier_of(name), expected=expected.get(name, 10.0), variant=where, group=group)
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


def reap(child):
    """Reap a finished child with its resource usage (CPU of the whole waited-for tree)."""
    if child.returncode is not None:
        return child.returncode, None
    pid, status, usage = os.wait4(child.pid, os.WNOHANG)
    if pid == 0:
        return None, None
    child.returncode = os.waitstatus_to_exitcode(status)
    return child.returncode, usage


class Runner:
    """Schedule checks over `jobs` slots; the report rows stay in report['checks']."""

    def __init__(self, *, work, logs, env, make, jobs, timeout, report, save, retries=1,
                 previous=None, runner_sha256=None, temporary=None, python='python3'):
        self.logs, self.python = logs, python
        self.variants = {'': Variant('', work, env, make, python)}
        self.jobs, self.timeout, self.report, self.save = max(1, jobs), timeout, report, save
        self.retries, self.previous, self.runner_sha256 = retries, previous, runner_sha256
        # Each check gets its own TMPDIR, so tests using fixed names under the
        # temporary directory cannot collide. Keep it short for socket paths.
        self.temporary = temporary
        self.results, self.reused = {}, []
        self.started = time.monotonic()
        # Rows from earlier executions (--resume) are history, not this run's result.
        self.first_row = len(report['checks'])

    # The default variant keeps the attributes callers used before variants existed.
    @property
    def built(self):
        return self.variants[''].built

    def add_variant(self, variant):
        self.variants[variant.name] = variant
        return variant

    def environment(self, check, index):
        env = {**self.variants[check.variant].env, **check.extra_env}
        if self.temporary:
            env['TMPDIR'] = str(self.temporary / str(index))
            shutil.rmtree(env['TMPDIR'], ignore_errors=True)
            Path(env['TMPDIR']).mkdir(parents=True)
        return env

    def environment_sha256(self, check):
        # Hash the inherited environment without recording possible secrets.
        env = {**self.variants[check.variant].env, **check.extra_env}
        return hashlib.sha256(json.dumps(env, sort_keys=True).encode()).hexdigest()

    def reuse(self, check, env_hash):
        for index, previous in enumerate(self.previous or ()):
            if previous.get('returncode') != 0 or previous.get('command') != check.command:
                continue
            known = previous.get('environment_sha256')
            if known == env_hash if known else not check.extra_env and check.label != 'regressions-sanitize':
                return {'label': check.label, 'original_index': index, 'legacy_environment_unknown': known is None}
        return None

    # -- processes -------------------------------------------------------
    def start(self, command, env, log, shown=None, cwd=None):
        output = log.open('a')
        output.write('$ ' + (shown or shlex.join(command)) + '\n')
        output.flush()
        child = subprocess.Popen(command, cwd=cwd or self.variants[''].work, env=env,
                                 stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        return {'child': child, 'output': output, 'started': time.monotonic(), 'log': log}

    def finish(self, process, wait=False):
        child = process['child']
        timed_out = False
        while True:
            code, usage = reap(child)
            if code is not None:
                break
            if time.monotonic() - process['started'] > self.timeout:
                # Kill the whole compiler/test group; never leave timed-out
                # grandchildren consuming resources during later checks.
                os.killpg(child.pid, signal.SIGKILL)
                _, status, usage = os.wait4(child.pid, 0)
                child.returncode = os.waitstatus_to_exitcode(status)
                timed_out = True
                break
            if not wait:
                return None
            time.sleep(0.2)
        process['output'].close()
        status = {'returncode': None if timed_out else child.returncode, 'timed_out': timed_out,
                  'duration_seconds': round(time.monotonic() - process['started'], 3),
                  'started_seconds': round(process['started'] - self.started, 3),
                  'ended_seconds': round(time.monotonic() - self.started, 3)}
        if usage is not None:
            status['cpu_seconds'] = round(usage.ru_utime + usage.ru_stime, 3)
            # ru_maxrss is KiB on Linux and bytes on macOS.
            status['max_rss_mib'] = round(usage.ru_maxrss / (1048576 if sys.platform == 'darwin' else 1024), 1)
        return status

    def kill_all(self, processes):
        for process in processes:
            if process['child'].returncode is None and process['child'].poll() is None:
                os.killpg(process['child'].pid, signal.SIGKILL)
                process['child'].wait()
            process['output'].close()

    # -- one check, run alone ------------------------------------------------
    def run_one(self, check):
        """Run a check with nothing else running; returns its report row."""
        row = self.begin(check)
        if row is None:
            return {'returncode': 0, 'reused': True}
        row.update(self.wait_alone(check, row))
        return self.end(check, row)

    def wait_alone(self, check, row, build_first=False):
        process = self.launch(check, row, build_first)
        try:
            return self.finish(process, wait=True)
        except BaseException:
            self.kill_all([process])
            raise

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
        log = self.logs / f"{index:03d}-{check.label.replace(':', '-')}.log"
        row = {'label': check.label, 'command': check.command, 'log': str(log), 'tier': check.tier,
               'timeout_seconds': self.timeout, 'extra_env': check.extra_env,
               'environment_sha256': env_hash, 'runner_sha256': self.runner_sha256, 'index': index}
        if check.variant:
            row['variant'] = check.variant
        if check.group:
            row['group'] = check.group
        self.report['checks'].append(row)
        self.save()
        print(check.label, flush=True)
        return row

    def launch(self, check, row, build_first=False):
        variant = self.variants[check.variant]
        command, shown = check.command, None
        if check.builds:
            command = [*variant.locked, *command]
            shown = shlex.join(check.command) + '  # holding build/bootstrap.lock'
        elif build_first and check.goals:
            build = [*variant.make, *check.goals]
            command = [self.python, '-c', BUILD_THEN_RUN, variant.lock, str(len(build)), *build, *command]
            shown = f'{shlex.join(build)}  # holding build/bootstrap.lock, then:\n$ {shlex.join(check.command)}'
        return self.start(command, self.environment(check, row['index']), Path(row['log']), shown, variant.work)

    def end(self, check, row):
        passed = row.get('returncode') == 0
        self.results[check.label] = 'passed' if passed else 'failed'
        if passed and check.builds:
            self.variants[check.variant].built.update(check.builds)
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
               'log': str(self.logs / f"{index:03d}-{check.label.replace(':', '-')}.log"),
               'timeout_seconds': self.timeout,
               'extra_env': check.extra_env, 'environment_sha256': self.environment_sha256(check),
               'runner_sha256': self.runner_sha256}
        if check.variant:
            row['variant'] = check.variant
        if check.group:
            row['group'] = check.group
        self.report['checks'].append(row)
        self.results[check.label] = 'failed'
        self.save()
        print(f"{check.label}: FAILED (prerequisite check failed: {', '.join(blockers)})", flush=True)

    # -- many checks ---------------------------------------------------------
    def run_all(self, checks, prebuild=()):
        """Run checks concurrently; failures never stop the others.

        prebuild names artifacts no check declares but harnesses build on
        demand (through the launcher); each variant's builder makes them early.
        Pass (variant, goal) pairs to name another variant's artifacts."""
        by_label = {check.label: check for check in checks}
        pending = sorted(checks, key=lambda c: -c.expected)
        running = []  # (check or goal, process, row, lane, variant name)
        # Each variant's builder first makes the goals that unblock the most expected check time.
        weights = {}
        for item in prebuild:
            key = tuple(item) if isinstance(item, (tuple, list)) else ('', item)
            weights[key] = weights.get(key, 0.0) + 1.0
        for check in pending:
            for goal in check.goals:
                weights[(check.variant, goal)] = weights.get((check.variant, goal), 0.0) + check.expected
        builder_order = {name: [] for name in self.variants}
        for (name, goal), _ in sorted(weights.items(), key=lambda item: -item[1]):
            if goal not in self.variants[name].built:
                builder_order[name].append(goal)
        self.report.setdefault('prerequisites', {})
        # Checks with tight timing run only with each other, a few at a time.
        quiet_jobs = max(1, self.jobs // 4)

        def builder_busy(name):
            return any(lane in ('goal', 'builder') and where == name for _, _, _, lane, where in running)

        def resource_full(check):
            if check.resource is None:
                return False
            members = sum(1 for item, _, _, lane, _ in running if lane != 'goal' and item.resource == check.resource)
            return members >= GROUP_LIMITS.get(check.resource.rsplit(':', 1)[-1], 1)

        def goals_ready(check):
            return (not builder_busy(check.variant) and not builder_order[check.variant]
                    and all(goal in self.variants[check.variant].built for goal in check.goals))

        def goals_failed(check):
            return any(goal in self.variants[check.variant].failed_goals for goal in check.goals)

        def after_state(check):
            states = [self.results.get(name) for name in check.after if name in by_label]
            if any(state is None for state in states):
                return 'waiting'
            failed = [name for name in check.after if self.results.get(name) == 'failed']
            return failed or 'ready'

        def start_check(check, lane, build_first=False):
            pending.remove(check)
            row = self.begin(check)
            if row is not None:
                running.append((check, self.launch(check, row, build_first), row, lane, check.variant))

        try:
            while pending or running:
                # Reap finished work.
                for entry in list(running):
                    item, process, row, lane, where = entry
                    status = self.finish(process)
                    if status is None:
                        continue
                    running.remove(entry)
                    if lane == 'goal':
                        variant = self.variants[where]
                        ok = status['returncode'] == 0
                        (variant.built if ok else variant.failed_goals).add(item)
                        self.report['prerequisites'][variant.label(item)] = {**status, 'log': str(process['log'])}
                        self.save()
                        if not ok:
                            print(f'prerequisite {variant.label(item)}: FAILED to build; see {process["log"]}',
                                  flush=True)
                    else:
                        row.update(status)
                        self.end(item, row)
                # Blocked checks fail without running, as make would.
                for check in list(pending):
                    state = after_state(check)
                    if isinstance(state, list):
                        pending.remove(check)
                        self.block(check, state)
                quiet = any(lane == 'exclusive' for _, _, _, lane, _ in running)
                if not quiet:
                    # Each variant's builder: one make at a time, either a check that builds
                    # shared goals, a check whose goals failed, or the next goal.
                    for name, variant in self.variants.items():
                        if builder_busy(name) or len(running) >= self.jobs:
                            continue
                        ready = [c for c in pending if c.variant == name and not c.exclusive
                                 and after_state(c) == 'ready' and not resource_full(c)]
                        check = next((c for c in ready if c.builds), None) or \
                            next((c for c in ready if goals_failed(c)), None)
                        if check is not None:
                            start_check(check, 'builder', build_first=not check.builds)
                            continue
                        order = builder_order[name]
                        while order and any(c.variant == name for c in pending):
                            goal = order.pop(0)
                            if goal in variant.built or goal in variant.failed_goals:
                                continue
                            print('prerequisite ' + variant.label(goal), flush=True)
                            log = self.logs / f"prerequisites{'-' + name if name else ''}.log"
                            running.append((goal, self.start([*variant.locked, *variant.make, goal], variant.env, log,
                                                             shlex.join([*variant.make, goal]) +
                                                             '  # holding build/bootstrap.lock', variant.work),
                                            None, 'goal', name))
                            break
                    # Ordinary checks fill the remaining slots, longest first.
                    for check in list(pending):
                        if len(running) >= self.jobs:
                            break
                        if (check.exclusive or check.builds or after_state(check) != 'ready'
                                or not goals_ready(check) or resource_full(check)):
                            continue
                        start_check(check, 'check')
                # Timing-sensitive checks start only when nothing else runs, then share the quiet.
                if all(lane == 'exclusive' for _, _, _, lane, _ in running):
                    for check in list(pending):
                        if len(running) >= quiet_jobs:
                            break
                        if (check.exclusive and after_state(check) == 'ready' and not resource_full(check)
                                and (goals_ready(check) or goals_failed(check))):
                            start_check(check, 'exclusive', build_first=goals_failed(check))
                if pending and not running:
                    # Nothing can start and nothing runs: report what is stuck.
                    for check in list(pending):
                        pending.remove(check)
                        self.block(check, [name for name in check.after if self.results.get(name) != 'passed']
                                   or ['unbuilt prerequisites'])
                if running:
                    time.sleep(0.2)
        except BaseException:
            self.kill_all([process for _, process, _, _, _ in running])
            raise
        self.retry_failures(by_label)

    def retry_failures(self, by_label):
        """Retry real failures once, alone, so load-induced timing failures surface as flaky."""
        rows = {row['label']: row for row in self.report['checks'][self.first_row:] if 'label' in row}
        for label, check in by_label.items():
            row = rows.get(label)
            if row is None or row.get('blocked_by'):
                continue
            for attempt in range(self.retries):
                if row.get('returncode') == 0:
                    break
                print(f'{label}: retrying alone', flush=True)
                with open(row['log'], 'a') as log:
                    log.write('\n--- retry with nothing else running ---\n')
                row.setdefault('failed_attempts', []).append(
                    {key: row.get(key) for key in ('returncode', 'timed_out', 'duration_seconds')})
                row.update(self.wait_alone(check, row, build_first=bool(check.goals)))
                if row['returncode'] == 0:
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
                    row.update(self.wait_alone(check, row, build_first=bool(check.goals)))
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


def group_table(rows):
    """Per matrix group: checks, failures, wall span, summed check time and CPU."""
    groups = {}
    for row in rows:
        if 'started_seconds' not in row:
            continue
        name = row.get('group') or row.get('variant') or 'checks'
        entry = groups.setdefault(name, {'checks': 0, 'failed': 0, 'first': row['started_seconds'],
                                         'last': row['ended_seconds'], 'check_seconds': 0.0, 'cpu_seconds': 0.0})
        entry['checks'] += 1
        entry['failed'] += row.get('returncode') != 0
        entry['first'] = min(entry['first'], row['started_seconds'])
        entry['last'] = max(entry['last'], row['ended_seconds'])
        entry['check_seconds'] += row.get('duration_seconds') or 0.0
        entry['cpu_seconds'] += row.get('cpu_seconds') or 0.0
    return groups


def summarise(report, stream, first_row=0):
    """Print one summary of every failure in this execution; return True when everything passed."""
    rows = [row for row in report['checks'][first_row:] if 'label' in row]
    latest = {}
    for row in rows:
        latest[row['label']] = row
    failed = [row for row in latest.values() if row.get('returncode') != 0]
    flaky = [row for row in latest.values() if row.get('flaky')]
    broken = {goal: status for goal, status in report.get('prerequisites', {}).items() if status.get('returncode') != 0}
    print('\n' + '=' * 78, file=stream)
    groups = group_table(latest.values())
    if len(groups) > 1:
        print(f'{"group":<16} {"checks":>6} {"failed":>6} {"wall span s":>11} {"check s":>9} {"cpu s":>9}', file=stream)
        for name, entry in sorted(groups.items(), key=lambda item: item[1]['first']):
            print(f'{name:<16} {entry["checks"]:>6} {entry["failed"]:>6} {entry["last"] - entry["first"]:>11.0f} '
                  f'{entry["check_seconds"]:>9.0f} {entry["cpu_seconds"]:>9.0f}', file=stream)
        print('-' * 78, file=stream)
    report['groups'] = groups
    print(f'{len(latest)} checks: {len(latest) - len(failed)} passed, {len(failed)} failed, '
          f'{len(flaky)} flaky (passed when retried alone)', file=stream)
    for goal, status in broken.items():
        print(f'prerequisite failed to build: {goal} (log {status.get("log")})', file=stream)
    for row in flaky:
        print(f'flaky: {row["label"]} (failed attempts {row["failed_attempts"]}; log {row["log"]})', file=stream)
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
