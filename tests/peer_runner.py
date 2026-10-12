"""Persist peer-suite outcomes, including skipped cases and partial domains.

These are observations of one invocation, not proof of full manifest coverage.
Failure workspaces remain the responsibility of test_evidence.Evidence.
"""
import inspect
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def peer_configurations(*configurations):
    """Declare a fixed campaign beside its executable method, for manifest lint."""
    if not configurations or len(set(configurations)) != len(configurations):
        raise ValueError('Empty or duplicate campaign configurations')
    if set(configurations) - {'O0', 'O1', 'O2', 'O3', 'Os', 'harness'}:
        raise ValueError('Unknown campaign configuration')

    def decorate(method):
        method.peer_configurations = configurations
        return method
    return decorate


class PeerResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observations = []
        self.started = time.monotonic()
        self.active = {}
        self.fixture_skips = []

    def startTest(self, test):
        super().startTest(test)
        self.active[id(test)] = dict(test=test.id(), outcome='running', skips=[],
                                    started=time.monotonic())

    def addSuccess(self, test):
        super().addSuccess(test)
        row = self.active[id(test)]
        if row['outcome'] == 'running':
            row['outcome'] = 'passed'

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.active[id(test)]['outcome'] = 'failed'

    def addError(self, test, err):
        super().addError(test, err)
        if id(test) in self.active:
            self.active[id(test)]['outcome'] = 'error'

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        parent = getattr(test, 'test_case', test)
        if id(parent) not in self.active:
            self.fixture_skips.append(dict(test=test.id(), reason=reason))
            return
        row = self.active[id(parent)]
        row['skips'].append(dict(test=test.id(), reason=reason))
        if row['outcome'] == 'running':
            row['outcome'] = 'partial' if parent is not test else 'skipped'

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.active[id(test)]['outcome'] = 'failed'

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.active[id(test)]['outcome'] = 'expected-failure'

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.active[id(test)]['outcome'] = 'unexpected-success'

    def stopTest(self, test):
        row = self.active.pop(id(test))
        row['elapsed_seconds'] = time.monotonic() - row.pop('started')
        source = Path(inspect.getsourcefile(type(test))).resolve()
        row['source'] = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else str(source)
        evidence = getattr(test, 'evidence', None)
        row['configurations'] = []
        row['phases'] = []
        row['exclusions'] = []
        row['domain_exclusions'] = []
        if evidence is not None:
            row['inputs'] = evidence.inputs
            row['phases'] = sorted({command['phase'] for command in evidence.commands})
            row['configurations'] = sorted({
                flag[1:] + ('-LTO' if any(arg.startswith('-flto') for arg in command['command']) else '')
                for command in evidence.commands if (command['phase'].startswith('link') or
                    ('-o' in command['command'] and not {'-c', '-S'} & set(command['command'])))
                for flag in command['command'] if flag in ('-O0', '-O1', '-O2', '-O3', '-Os')})
            row['configurations'] = sorted(set(row['configurations']) |
                                           set(evidence.controls.get('campaign_configurations', [])))
            row['exclusions'] = evidence.controls.get('platform_exclusions', [])
            row['domain_exclusions'] = evidence.controls.get('domain_exclusions', [])
            row['domain_coverage'] = evidence.controls.get('domain_coverage', {})
            row['output_references'] = evidence.controls.get('output_references', [])
            row['command_count'] = len(evidence.commands)
            if (row['exclusions'] or row['domain_exclusions']) and row['outcome'] == 'passed':
                row['outcome'] = 'partial'
        method = getattr(test, test._testMethodName)
        if getattr(method, 'peer_configurations', ()) == ('harness',) and row['outcome'] == 'passed':
            row['configurations'] = ['harness']
        self.observations.append(row)
        super().stopTest(test)

    def report(self):
        extended = os.environ.get('MINYAR_TEST_EXTENDED_OPT') == '1'
        flags = shlex.split(os.environ.get('MINYAR_TEST_LINK_FLAGS', ''))
        sanitized = any(flag.startswith('-fsanitize=') for flag in flags)
        gate = os.environ.get('MINYAR_PEER_GATE') or ('check-peer-sanitize' if sanitized else
                'check-peer-optimizations' if extended else 'check-peer-regressions')
        manifest = json.loads((ROOT / 'tests/peer-cases.json').read_text())
        declarations = {(row['source'], row['id']): row for row in manifest['cases']}
        selected = set()
        sources = {row['source'] for row in self.observations}
        for row in self.observations:
            key = row['source'], row['test'].split('.')[-1]
            selected.add(key)
            declaration = declarations.get(key)
            row['declared'] = declaration is not None and gate in declaration['gates']
            row['required_configurations'] = declaration['gates'].get(gate, []) if declaration else []
            observed = set(row['configurations'])
            if any(phase.startswith('compile') for phase in row['phases']):
                observed.add('frontend')
            row['missing_configurations'] = sorted(set(row['required_configurations']) - observed)
        omitted = [dict(source=source, test=name, reason='not selected in this invocation')
                   for (source, name), declaration in declarations.items()
                   if source in sources and gate in declaration['gates'] and (source, name) not in selected]
        return dict(schema_version=1, successful=self.wasSuccessful(), gate=gate,
                    complete_selection=self.wasSuccessful() and not self.fixture_skips and bool(self.observations) and all(
                        row['outcome'] == 'passed' for row in self.observations),
                    required_coverage_observed=self.wasSuccessful() and not self.fixture_skips and bool(self.observations) and not omitted and all(
                        row['declared'] and row['outcome'] == 'passed' and not row['missing_configurations']
                        for row in self.observations),
                    scope='Selected tests only; observed link configurations do not prove every domain cell ran',
                    platform=platform.system(), machine=platform.machine(),
                    extended_optimizations=extended,
                    link_flags=os.environ.get('MINYAR_TEST_LINK_FLAGS', ''),
                    elapsed_seconds=time.monotonic() - self.started,
                    tests_run=self.testsRun, selected=self.observations, omitted=omitted, fixture_skips=self.fixture_skips,
                    errors=[dict(test=test.id(), detail=detail) for test, detail in self.errors],
                    failures=[dict(test=test.id(), detail=detail) for test, detail in self.failures])


def write_report(result, stream):
    directory = Path(os.environ.get('MINYAR_PEER_RESULTS', ROOT / 'build/peer-results'))
    directory.mkdir(parents=True, exist_ok=True)
    # Each invocation owns a separate file, including parallel agent runs.
    with tempfile.NamedTemporaryFile(mode='w', prefix=Path(sys.argv[0]).stem + '-',
                                     suffix='.json', dir=directory, delete=False) as output:
        json.dump(result.report(), output, indent=2)
        output.write('\n')
        path = output.name
    stream.writeln('Peer outcomes: ' + path)


class PeerRunner(unittest.TextTestRunner):
    resultclass = PeerResult

    def run(self, test):
        result = super().run(test)
        write_report(result, self.stream)
        return result


class ShardRunner(unittest.TextTestRunner):
    """Run one shard of a sharded invocation and hand its raw outcomes to the parent."""
    resultclass = PeerResult

    def run(self, test):
        result = super().run(test)
        Path(os.environ['MINYAR_PEER_SHARD']).write_text(json.dumps(dict(
            observations=result.observations, fixture_skips=result.fixture_skips, tests_run=result.testsRun,
            errors=[[test.id(), detail] for test, detail in result.errors],
            failures=[[test.id(), detail] for test, detail in result.failures],
            unexpected_successes=[test.id() for test in result.unexpectedSuccesses])))
        return result


class _Named:
    def __init__(self, name):
        self.name = name

    def id(self):
        return self.name

    def __str__(self):
        return self.name


def _test_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from _test_ids(test)
        else:
            yield test.id()


class ShardedProgram(unittest.TestProgram):
    """Run the selected tests in up to MINYAR_TEST_JOBS processes and write one merged report.

    Each case is independent (its own evidence workspace), so only wall time changes.
    Shards are small and dealt round-robin, so slow neighbouring cases spread out.
    """

    def runTests(self):
        jobs = int(os.environ.get('MINYAR_TEST_JOBS', '2'))
        ids = list(_test_ids(self.test))
        unloadable = [name for name in ids if not name.startswith('__main__.')]
        if jobs <= 1 or len(ids) < 2 or unloadable:
            self.testRunner = PeerRunner
            return super().runTests()
        stream = unittest.runner._WritelnDecorator(sys.stderr)
        result = PeerResult(stream, True, self.verbosity)
        count = min(len(ids), jobs * 4)
        shards = [[name.split('.', 1)[1] for name in ids[index::count]] for index in range(count)]
        flags = ['-v'] if self.verbosity > 1 else []
        with tempfile.TemporaryDirectory(prefix='peer-shards-') as folder:
            pending, running = list(enumerate(shards)), []
            while pending or running:
                while pending and len(running) < jobs:
                    index, names = pending.pop(0)
                    path = Path(folder) / f'shard-{index}.json'
                    log = Path(folder) / f'shard-{index}.log'
                    env = dict(os.environ, MINYAR_PEER_SHARD=str(path), MINYAR_TEST_JOBS='1')
                    with log.open('wb') as output:
                        process = subprocess.Popen([sys.executable, sys.argv[0], *flags, *names], env=env,
                                                   stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
                    running.append((index, path, log, process))
                time.sleep(0.05)
                for entry in [entry for entry in running if entry[3].poll() is not None]:
                    running.remove(entry)
                    index, path, log, process = entry
                    stream.write(log.read_bytes().decode('utf-8', errors='replace'))
                    stream.flush()
                    if not path.is_file():
                        name = f'{sys.argv[0]} shard {index}'
                        result.errors.append((_Named(name), f'shard exited with status {process.returncode} '
                                                            'before writing its outcomes'))
                        continue
                    shard = json.loads(path.read_text())
                    result.observations += shard['observations']
                    result.fixture_skips += shard['fixture_skips']
                    result.testsRun += shard['tests_run']
                    result.errors += [(_Named(name), detail) for name, detail in shard['errors']]
                    result.failures += [(_Named(name), detail) for name, detail in shard['failures']]
                    result.unexpectedSuccesses += [_Named(name) for name in shard['unexpected_successes']]
        order = {name.split('.', 1)[1]: position for position, name in enumerate(ids)}
        result.observations.sort(key=lambda row: order.get(row['test'].split('.', 1)[1], len(order)))
        stream.writeln(unittest.TextTestResult.separator2)
        stream.writeln(f'Ran {result.testsRun} tests in {len(shards)} shards over {jobs} processes '
                       f'({time.monotonic() - result.started:.3f}s)')
        stream.writeln('OK' if result.wasSuccessful() else
                       f'FAILED (failures={len(result.failures)}, errors={len(result.errors)})')
        write_report(result, stream)
        self.result = result
        if self.exit:
            sys.exit(not result.wasSuccessful())


def main():
    if os.environ.get('MINYAR_PEER_SHARD'):
        unittest.main(testRunner=ShardRunner)
    ShardedProgram()
