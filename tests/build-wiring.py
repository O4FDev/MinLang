#!/usr/bin/env python3
"""Probe actual Make prerequisites under POSIX and native Windows host names."""
import ast
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def dry_run_commands(stdout):
    """Return `make -np` commands; GNU Make 3.81 prints its banner before them, 4.x after."""
    lines = stdout.split('# Make data base', 1)[0].splitlines(keepends=True)
    start = next((index for index, line in enumerate(lines) if line.startswith('# GNU Make')),
                 len(lines))
    end = start
    while end < len(lines) and (lines[end].startswith('#') or not lines[end].strip()):
        end += 1
    return ''.join(lines[:start] + lines[end:])



def minyar_list(path, function):
    body = (ROOT / path).read_text().split('public function ' + function + '(): List<Text> {', 1)[1].split('\n}', 1)[0]
    return re.findall(r'"([^"]+)"', body)


def formatter_files():
    text = (ROOT / 'scripts/format.min').read_text()
    files = re.findall(r'"([^"]+)"', text.split('for file in [', 1)[1].split(']', 1)[0])
    if 'if fileExists("compiler/stages/c-layout.min") {' in text and (ROOT / 'compiler/stages/c-layout.min').is_file():
        files += re.findall(r'"([^"]+)"', text.split('for file in [', 2)[2].split(']', 1)[0])
    return files


def formatter_version():
    return re.search(r'"version (\d+\.\d+\.\d+)"', (ROOT / 'scripts/format.min').read_text())[1]


def linux_targets():
    optional = (ROOT / 'tools/linux-matrix.min').read_text().split('for target in [', 1)[1].split(']', 1)[0]
    return minyar_list('scripts/linux-plan.min', 'correctness') + re.findall(r'"([^"]+)"', optional)


def native_catalogue():
    tool = str(ROOT / 'build/tooling/tests/suite-catalogue')

    def validate(data, root):
        with tempfile.TemporaryDirectory(prefix='minyar-catalogue-') as directory:
            path = Path(directory) / 'catalogue.json'
            path.write_text(json.dumps(data))
            result = subprocess.run([tool, '--validate', str(path), str(root)], capture_output=True, text=True)
        if result.returncode == 3:
            raise ValueError(result.stderr.strip())
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def discover(root):
        result = subprocess.run([tool, '--discover', str(root)], capture_output=True, text=True, check=True)
        return set(result.stdout.splitlines())

    return types.SimpleNamespace(validate=validate, discover=discover)


def network_tool(name):
    return ROOT / 'build/tooling/tests' / name


def mode_probe(tool, host, arguments):
    with tempfile.TemporaryDirectory(prefix='network mode probe ') as folder:
        uname = Path(folder) / 'uname'
        uname.write_text('#!/bin/sh\nprintf "%s\\n" "' + host + '"\n')
        uname.chmod(0o755)
        environment = dict(os.environ, PATH=folder + os.pathsep + os.environ['PATH'])
        return subprocess.run([str(tool), '--print-modes', *arguments], cwd=ROOT, env=environment,
                              capture_output=True, text=True, timeout=60)


def mode_stub(directory, table):
    path = Path(directory) / 'mode-mutant'
    path.write_text('#!' + sys.executable + '\n'
        'import json,subprocess,sys\n'
        'host=subprocess.run(["uname","-s"],capture_output=True,text=True).stdout.strip()\n'
        'windows=host.startswith(("MSYS","MINGW","CYGWIN","Windows"))\n'
        'mode=sys.argv[sys.argv.index("--mode")+1] if "--mode" in sys.argv else None\n'
        'if windows and mode=="sanitize":\n'
        ' print("error: sanitizer mode is unavailable on Windows",file=sys.stderr);sys.exit(2)\n'
        'print(json.dumps(' + repr({repr(key): value for key, value in table.items()}) + '[repr((windows,mode))]))\n')
    path.chmod(0o755)
    return path


def make_rules(fragment):
    with tempfile.TemporaryDirectory(prefix='make rule probe ') as folder:
        probe = Path(folder) / 'probe.mk'
        probe.write_text(fragment + '\n.PHONY: probe\nprobe:\n')
        environment = dict(os.environ)
        environment.pop('MAKEFLAGS', None)
        result = subprocess.run(['make', '-rRnp', '-f', str(probe), 'probe'], cwd=ROOT, env=environment,
                                capture_output=True, text=True, timeout=15)
    rules = {}
    for line in result.stdout.splitlines():
        match = re.match(r'^([\w./-]+):(?: *)([^#=]*)$', line)
        if match:
            rules.setdefault(match[1], set()).update(match[2].split())
    return rules


def assert_ci_runs_quic_group(test, *targets):
    """CI gates these targets through the runner's QUIC group, run by a linux-matrix shard."""
    quic = minyar_list('scripts/linux-plan.min', 'quic')
    workflow = (ROOT / '.github/workflows/ci.yml').read_text()
    test.assertIn('./build/tooling/scripts/check-linux', workflow)
    test.assertIn('--group quic', workflow)
    for target in targets:
        test.assertIn(target, quic)

class BuildWiring(unittest.TestCase):

    def test_bakeoff_stress_is_mandatory_with_bounded_quick_profiles(self):
        import re
        with tempfile.TemporaryDirectory(prefix='minyar bakeoff wiring ') as folder:
            makefile = Path(folder) / 'probe.mk'
            makefile.write_text(
                'LLVM_CC := retained-clang\nSANITIZER_LIMITED := sanitizer-limit\n'
                'include ' + str(ROOT / 'build-support/managed-graphs.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: build\nbuild:\n\t@:\nbuild/tooling/%:\n\t@echo TOOL $@\n')
            env = dict(os.environ)
            env.pop('MAKEFLAGS', None)
            result = subprocess.run(
                ['make', '-rRnp', '-f', str(makefile), 'check-managed-graphs-bakeoff'],
                cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            rules = {}
            for line in result.stdout.splitlines():
                match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                if match:
                    rules.setdefault(match[1], set()).update(match[2].split())
            target = 'check-managed-graphs-bakeoff'
            for gate in ('check', 'check-portable', 'check-sanitize', 'check-managed-graphs-profiles'):
                self.assertIn(target, rules.get(gate, set()), gate)
            for source in ('tests/managed-graphs-bakeoff.c', 'tests/managed-graphs-runtime.c',
                           'build/tooling/tests/managed-graphs-profiles', 'runtime/minyar_runtime.c'):
                self.assertIn(source, rules.get(target, set()))
            commands = dry_run_commands(result.stdout)
            selected = [line for line in commands.splitlines()
                        if './build/tooling/tests/managed-graphs-profiles' in line]
            self.assertEqual(selected, [
                'MINYAR_TEST_CLANG="retained-clang" sanitizer-limit '
                './build/tooling/tests/managed-graphs-profiles --quick --fixture managed-graphs-bakeoff.c'])




    def test_event_loop_native_and_sanitizer_keep_distinct_limits(self):
        fragment = (ROOT/'build-support/networking.mk').read_text()
        def verify(candidate, host='Linux', operating_system=''):
            with tempfile.TemporaryDirectory(prefix='loop limits Make rules ') as folder:
                directory = Path(folder)
                uname = directory/'uname';uname.write_text(
                    '#!/bin/sh\nprintf "%s\\n" "'+host+'"\n');uname.chmod(0o755)
                makefile = directory/'probe.mk'
                makefile.write_text('LLVM_CC := retained-clang\nLIMITED := ordinary-limit\n'
                    'SANITIZER_LIMITED := sanitizer-limit\n'+candidate
                    +'\n.PHONY: build/minyarc build/tooling/tests/net-loop-test\n'
                    'build/minyarc build/tooling/tests/net-loop-test:\n\t@echo INPUT $@\n')
                env = dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH'],
                           OS=operating_system);env.pop('MAKEFLAGS',None)
                result = subprocess.run(['make','-rRn','-f',str(makefile),'check-net-loop'],
                    cwd=ROOT,env=env,capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr)
                commands=[line for line in result.stdout.splitlines()
                          if './build/tooling/tests/net-loop-test' in line]
                windows=operating_system=='Windows_NT' or host.startswith(('MSYS','MINGW','CYGWIN'))
                self.assertEqual(len(commands),1 if windows else 2)
                native=next(line for line in commands if '--mode native' in line)
                self.assertIn('ordinary-limit ./build/tooling/tests/net-loop-test --mode native',native)
                self.assertNotIn('sanitizer-limit',native)
                self.assertIn('--evidence "$evidence"',native)
                self.assertIn(str(ROOT/'build/net-loop.'),native.replace('\\','/'))
                if not windows:
                    sanitize=next(line for line in commands if '--mode sanitize' in line)
                    self.assertIn('sanitizer-limit ./build/tooling/tests/net-loop-test --mode sanitize',sanitize)
                    self.assertNotIn('ordinary-limit',sanitize)
                    self.assertIn('--evidence "$evidence"',sanitize)
                    self.assertIn(str(ROOT/'build/net-loop-sanitize.'),sanitize.replace('\\','/'))
        verify(fragment)
        for host, operating_system in (('Darwin',''),('Linux','Windows_NT'),
                ('MSYS_NT-10.0',''),('MINGW64_NT-10.0',''),('CYGWIN_NT-10.0','')):
            verify(fragment,host,operating_system)
        native=next(line for line in fragment.splitlines() if 'tests/net-loop-test --mode native' in line)
        sanitize=next(line for line in fragment.splitlines() if 'tests/net-loop-test --mode sanitize' in line)
        for old,new in ((native,''),(sanitize,''),
                (native,native.replace('$(LIMITED)','$(SANITIZER_LIMITED)')),
                (sanitize,sanitize.replace('$(SANITIZER_LIMITED)','$(LIMITED)')),
                (native,native.replace(' --mode native','')),
                (sanitize,sanitize.replace(' --mode sanitize',''))):
            mutant=fragment.replace(old,new,1);self.assertNotEqual(mutant,fragment)
            with self.assertRaises((AssertionError,StopIteration)):verify(mutant)

        def verify_modes(tool):
            for windows,mode,expected in (
                    (False,None,['native','sanitize','app-native','app-sanitize']),
                    (False,'native',['native','app-native']),
                    (False,'sanitize',['sanitize','app-sanitize']),
                    (True,None,['native']),(True,'native',['native'])):
                result=mode_probe(tool,'MSYS_NT-10.0' if windows else 'Linux',['--mode',mode] if mode else [])
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(result.stdout),expected)
            result=mode_probe(tool,'MSYS_NT-10.0',['--mode','sanitize'])
            self.assertEqual(result.returncode,2)
        verify_modes(network_tool('net-loop-test'))
        table={(False,None):['native','sanitize','app-native','app-sanitize'],
               (False,'native'):['native','app-native'],(False,'sanitize'):['sanitize','app-sanitize'],
               (True,None):['native'],(True,'native'):['native']}
        with tempfile.TemporaryDirectory(prefix='loop mode mutants ') as folder:
            for key,value in (((False,'native'),['native']),((False,'sanitize'),['sanitize']),
                              ((False,None),['native','app-native','sanitize','app-sanitize'])):
                mutant=dict(table);mutant[key]=value
                with self.assertRaises(AssertionError):verify_modes(mode_stub(folder,mutant))
        def verify_inputs(candidate):
            start=candidate.index('evidence.create(')
            listing=candidate[candidate.index('[',start):candidate.index(']',start)+1]
            bound=set(re.findall(r'"([^"]+)"',listing))
            self.assertIn('tests/net-evidence.min',bound)
            self.assertIn('runtime/native/net.c',bound)
        loop_source=(ROOT/'tests/net-loop-test.min').read_text()
        verify_inputs(loop_source)
        for name in ('tests/net-evidence.min','runtime/native/net.c'):
            mutant=loop_source.replace('"'+name+'", ','',1);self.assertNotEqual(mutant,loop_source)
            with self.assertRaises(AssertionError):verify_inputs(mutant)
        def verify_helper(candidate):
            rules=make_rules(candidate)
            for tool in ('net-loop-test','net-native-test'):
                self.assertIn('tests/net-evidence.min',rules.get('build/tooling/tests/'+tool+'.ll',set()))
        verify_helper(fragment)
        dependency=next(line for line in fragment.splitlines()
                        if line.startswith('build/tooling/') and line.endswith(': tests/net-evidence.min'))
        with self.assertRaises(AssertionError):verify_helper(fragment.replace(dependency,'',1))

    def test_network_evidence_preserves_primary_and_finalizes_independently(self):
        with tempfile.TemporaryDirectory(prefix='network evidence controls ') as folder:
            result = subprocess.run([str(network_tool('net-native-test')), '--evidence-controls', folder],
                                    cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            def operations(row):
                return [error['operation'] for error in row['errors']]
            stream = next(row for row in rows if row['scenario'] == 'stream')
            self.assertEqual(stream['status'], 37)
            self.assertTrue(stream['failure'].startswith('CalledProcessError'), stream)
            self.assertEqual(stream['finalized'], stream['failure'])
            self.assertEqual(stream['stderr'], 'provider stderr')
            self.assertEqual((Path(stream['directory'])/'01-provider.stderr').read_bytes(), b'provider stderr')
            self.assertIn('stdout write', operations(stream))
            self.assertNotIn('stderr write', operations(stream))
            self.assertEqual(operations(stream).count('manifest write'), 1)
            self.assertIn('stdout write', result.stderr)
            self.assertIn('manifest write', result.stderr)
            self.assertEqual(stream['records'][0]['status'], 37)
            binding = next(row for row in rows if row['scenario'] == 'binding')
            self.assertTrue(binding['failure'].startswith('RuntimeError'), binding)
            self.assertIn('tool binding', operations(binding))
            inputs = next(row for row in rows if row['scenario'] == 'inputs')
            self.assertEqual(inputs['finalized'], 'network evidence finalization failed')
            manifest = json.loads((Path(inputs['directory'])/'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'failed')
            self.assertIn('input binding', operations(inputs))
            scopes = [row for row in rows if row['scenario'] == 'scope']
            self.assertEqual([row['modes'] for row in scopes], [['native'], ['native', 'sanitize'], ['sanitize']])
            for row, expected_scope in zip(scopes, ('ordinary-launcher-path', 'ordinary-launcher-path', None)):
                self.assertEqual(row['finalized'], '')
                manifest = json.loads((Path(row['directory'])/'manifest.json').read_text())
                self.assertFalse(manifest['public_program_sanitizer_enabled_by_suite'])
                self.assertEqual(manifest['public_program_scope'], expected_scope)
                self.assertNotIn('public_program_sanitized', manifest)
                self.assertFalse(manifest['windows_sanitizer_enabled_by_suite'])
                self.assertNotIn('windows_sanitizer_capability', manifest)

    def test_network_native_and_sanitizer_keep_distinct_limits(self):
        import re

        fragment = (ROOT/'build-support/networking.mk').read_text()

        def verify(candidate, host='Linux', operating_system=''):
            with tempfile.TemporaryDirectory(prefix='network limits Make rules ') as folder:
                directory = Path(folder)
                uname = directory/'uname'
                uname.write_text('#!/bin/sh\nprintf "%s\\n" "' + host + '"\n')
                uname.chmod(0o755)
                makefile = directory/'probe.mk'
                makefile.write_text(
                    'LLVM_CC := retained-clang\nLIMITED := ordinary-limit\n'
                    'SANITIZER_LIMITED := sanitizer-limit\n' + candidate
                    + '\n.PHONY: build/minyarc build/tooling/tests/net-native-test build/tooling/tests/soak-observer-test build/testing/cycle-runtime.o\n'
                    'build/minyarc build/tooling/tests/net-native-test build/tooling/tests/soak-observer-test build/testing/cycle-runtime.o:\n\t@echo INPUT $@\n')
                env = dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH'],
                           OS=operating_system)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(
                    ['make', '-rRn', '-f', str(makefile), 'check-net'],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                commands = [line for line in result.stdout.splitlines()
                            if './build/tooling/tests/net-native-test' in line]
                windows = operating_system == 'Windows_NT' or host.startswith(
                    ('MSYS', 'MINGW', 'CYGWIN'))
                self.assertEqual(len(commands), 1 if windows else 2)
                native = next(line for line in commands if '--mode native' in line)
                self.assertIn('ordinary-limit ./build/tooling/tests/net-native-test --mode native', native)
                self.assertNotIn('sanitizer-limit', native)
                self.assertIn('MINYAR_TEST_CLANG="retained-clang"', native)
                self.assertIn('--evidence "$evidence"', native)
                self.assertIn(str(ROOT/'build/net-native.'), native.replace('\\', '/'))
                if not windows:
                    sanitize = next(line for line in commands if '--mode sanitize' in line)
                    self.assertIn('sanitizer-limit ./build/tooling/tests/net-native-test --mode sanitize',
                                  sanitize)
                    self.assertNotIn('ordinary-limit', sanitize)
                    self.assertIn('MINYAR_TEST_CLANG="retained-clang"', sanitize)
                    self.assertIn('--evidence "$evidence"', sanitize)
                    self.assertIn(str(ROOT/'build/net-native-sanitize.'),
                                  sanitize.replace('\\', '/'))
                self.assertEqual(result.stdout.count('ordinary-limit ./build/tooling/tests/soak-observer-test'), 1)

        verify(fragment)
        for host, operating_system in (
                ('Darwin', ''), ('Linux', 'Windows_NT'), ('MSYS_NT-10.0', ''),
                ('MINGW64_NT-10.0', ''), ('CYGWIN_NT-10.0', '')):
            with self.subTest(host=host, operating_system=operating_system):
                verify(fragment, host, operating_system)
        native = next(line for line in fragment.splitlines()
                      if 'tests/net-native-test --mode native' in line)
        sanitize = next(line for line in fragment.splitlines()
                        if 'tests/net-native-test --mode sanitize' in line)
        for name, old, new in (
                ('missing native', native, ''),
                ('missing POSIX sanitizer', sanitize, ''),
                ('sanitizer ordinary limit', sanitize, sanitize.replace(
                    '$(SANITIZER_LIMITED)', '$(LIMITED)')),
                ('native sanitizer limit', native, native.replace(
                    '$(LIMITED)', '$(SANITIZER_LIMITED)')),
                ('sanitizer default mixed modes', sanitize, sanitize.replace(
                    ' --mode sanitize', '')),
                ('native default mixed modes', native, native.replace(
                    ' --mode native', '')),
                ('relative evidence', '$(abspath build)', 'build')):
            mutant = fragment.replace(old, new, 1)
            self.assertNotEqual(mutant, fragment)
            with self.subTest(invalid_recipe=name), self.assertRaises(
                    (AssertionError, StopIteration)):
                verify(mutant)


        tool = network_tool('net-native-test')
        for windows, mode, expected in (
                (False, None, ['native', 'sanitize']),
                (False, 'native', ['native']), (False, 'sanitize', ['sanitize']),
                (True, None, ['native']), (True, 'native', ['native'])):
            with self.subTest(windows=windows, mode=mode):
                result = mode_probe(tool, 'MSYS_NT-10.0' if windows else 'Linux',
                                    ['--mode', mode] if mode else [])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), expected)
        rejected = mode_probe(tool, 'MSYS_NT-10.0', ['--mode', 'sanitize'])
        self.assertEqual(rejected.returncode, 2)
        self.assertIn('unavailable on Windows', rejected.stderr)

    def test_cycle_progress_observability_is_mandatory_without_idle_replay(self):
        import importlib.util
        import json
        import re

        target = 'check-cycle-progress-observability'
        aggregates = {'check', 'check-portable', 'check-sanitize',
                      'check-managed-graphs-profiles', 'check-cycle-progress',
                      'check-cycle-progress-sanitize'}
        inputs = {'build/tooling/tests/cycle-progress-observability',
                  'build/tooling/tests/cycle-progress-observability-harness', 'tests/cycle-progress.c',
                  'tests/fixtures/cycle-progress-before-observability.c.txt'}
        source = (ROOT/'build-support/managed-graphs.mk').read_text()
        marker = '# Mocked idle observability preserves the historical metric.'
        self.assertIn(marker, source)
        fragment = source[source.index(marker):]

        def verify(candidate):
            with tempfile.TemporaryDirectory(prefix='idle observability Make rules ') as folder:
                makefile = Path(folder)/'probe.mk'
                fixtures = sorted(inputs | {'build'})
                makefile.write_text(
                    'LLVM_CC := retained-clang\nLIMITED := retained-limited\n'
                    + candidate + '\n.PHONY: ' + ' '.join(fixtures)
                    + '\n' + ' '.join(fixtures) + ':\n\t@echo INPUT $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(['make', '-rRnp', '-f', str(makefile), target],
                                        cwd=ROOT, env=env, capture_output=True,
                                        text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s*(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                for aggregate in aggregates:
                    self.assertIn(target, rules.get(aggregate, set()), aggregate)
                self.assertTrue(inputs <= rules.get(target, set()))
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./build/tooling/tests/cycle-progress-observability --evidence'), 1)
                self.assertEqual(commands.count('./build/tooling/tests/cycle-progress-observability-harness'), 1)
                self.assertIn('MINYAR_TEST_CLANG="retained-clang"', commands)
                self.assertIn('retained-limited ./build/tooling/tests/cycle-progress-observability', commands)
                self.assertIn('--evidence "$evidence/run"', commands)
                self.assertIn((ROOT/'build/cycle-progress-observability.').as_posix(),
                              commands.replace('\\', '/'))
                for forbidden in ('--sanitize', '--case ', '--nodes ', '--seconds ',
                                  '--expect-old-code', 'tests/cycle-progress.py'):
                    self.assertNotIn(forbidden, commands)

        verify(fragment)
        aggregate_line = next(line for line in fragment.splitlines()
                              if line.split(':', 1)[0].split() == sorted(aggregates))
        for aggregate in sorted(aggregates):
            names, dependency = aggregate_line.split(': ', 1)
            mutant = fragment.replace(aggregate_line, ' '.join(
                name for name in names.split() if name != aggregate) + ': ' + dependency, 1)
            with self.subTest(missing_aggregate=aggregate), self.assertRaises(AssertionError):
                verify(mutant)
        dependency_line = next(line for line in fragment.splitlines()
                               if line.startswith(target + ':'))
        for dependency in sorted(inputs):
            mutant = fragment.replace(dependency_line,
                                      dependency_line.replace(' ' + dependency, '', 1), 1)
            with self.subTest(missing_input=dependency), self.assertRaises(AssertionError):
                verify(mutant)
        for name, old, new in (
                ('relative evidence', '$(abspath build)/cycle-progress-observability.',
                 'build/cycle-progress-observability.'),
                ('filtered controls', '--evidence', '--case zero --evidence'),
                ('runtime replay', './build/tooling/tests/cycle-progress-observability --evidence',
                 './build/tooling/tests/cycle-progress --evidence')):
            mutant = fragment.replace(old, new, 1)
            self.assertNotEqual(fragment, mutant)
            with self.subTest(invalid_recipe=name), self.assertRaises(AssertionError):
                verify(mutant)

        targets = linux_targets()
        self.assertEqual(targets.count(target), 1)
        catalogue = native_catalogue()
        data = json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for name in sorted(name for name in inputs if name.startswith('tests/')):
            self.assertIn(name, catalogue.discover(ROOT))
            with self.subTest(omitted_source=name), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[row for row in data['sources']
                                                       if row['path'] != name]), ROOT)
        row = next(row for row in data['sources']
                   if row['path'] == 'tests/cycle-progress-observability-native.c')
        self.assertEqual(row['role'], 'support')
        self.assertIn('build-support/managed-graphs.mk', row['consumers'])
        historical = next(row for row in data['sources']
                          if row['path'] == 'tests/fixtures/cycle-progress-before-observability.c.txt')
        self.assertEqual(historical['role'], 'fixture')
        self.assertEqual(historical['consumers'], ['tests/cycle-progress-observability.min'])


    def test_quic_ledger_requires_full_offline_controls(self):
        import importlib.util
        import json
        import re
        fragment_path = ROOT / 'build-support/quic-ledger.mk'
        source = fragment_path.read_text()
        target = 'check-quic-amplification-ledger'
        inputs = {'tests/quic-amplification-ledger.min', 'tests/quic-ledger-support.min',
                  'tests/quic-ledger-checker.min', 'tests/quic-ledger-crypto.c',
                  'build/tooling/tests/quic-amplification-ledger', 'build/tooling/tests/quic-ledger-checker',
                  'build/tooling/tools/clang-driver'}

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='QUIC ledger Make rules ') as folder:
                makefile = Path(folder) / 'probe.mk'
                fixtures = sorted(inputs | {'build'})
                makefile.write_text(fragment + '\n.PHONY: ' + ' '.join(fixtures)
                                   + '\n' + ' '.join(fixtures)
                                   + ':\n\t@echo INPUT $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(['make', '-rRnp', '-f', str(makefile), target],
                                        cwd=ROOT, env=env, text=True,
                                        capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s*(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                for gate in ('check', 'check-portable', 'check-quic',
                             'check-quic-sanitize', 'check-quic-rfc',
                             'check-quic-rfc-sanitize', 'check-sanitize'):
                    self.assertIn(target, rules.get(gate, set()), gate)
                self.assertTrue(inputs <= rules.get(target, set()))
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./build/tooling/tests/quic-amplification-ledger --artifacts'), 1)
                self.assertIn('--artifacts "$artifacts/run"', commands)
                self.assertIn((ROOT / 'build/quic-ledger.').as_posix(),
                              commands.replace('\\', '/'))
                self.assertNotIn('--case ', commands)
                self.assertNotIn('--expect-old-code', commands)
                self.assertNotIn('--sanitize', commands)

        verify(source)
        aggregates = ('check', 'check-portable', 'check-quic', 'check-quic-sanitize',
                      'check-quic-rfc', 'check-quic-rfc-sanitize', 'check-sanitize')
        line = next(line for line in source.splitlines()
                    if line.startswith('check check-portable '))
        names, dependency = line.split(': ', 1)
        for gate in aggregates:
            mutant = source.replace(line, ' '.join(
                name for name in names.split() if name != gate) + ': ' + dependency, 1)
            with self.subTest(missing_gate=gate), self.assertRaises(AssertionError):
                verify(mutant)
        for dependency in sorted(inputs):
            mutant = source.replace(dependency, '', 1)
            self.assertNotEqual(mutant, source)
            with self.subTest(missing_source=dependency), self.assertRaises(AssertionError):
                verify(mutant)
        for label, old, new in (
                ('filtered cases', '--artifacts', '--case exact3x --artifacts'),
                ('relative artifact path', '$(abspath build)/quic-ledger.', 'build/quic-ledger.')):
            mutant = source.replace(old, new, 1)
            self.assertNotEqual(mutant, source)
            with self.subTest(invalid_recipe=label), self.assertRaises(AssertionError):
                verify(mutant)
        targets = linux_targets()
        self.assertEqual(targets.count(target), 1)
        catalogue = native_catalogue()
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        rows = {row['path']: row for row in data['sources']}
        self.assertEqual(rows['tests/quic-ledger-crypto.c']['role'], 'support')
        self.assertIn('build-support/quic-ledger.mk',
                      rows['tests/quic-ledger-crypto.c']['consumers'])
        for missing in ('tests/quic-ledger-crypto.c',):
            candidate = dict(data, sources=[row for row in data['sources']
                                           if row['path'] != missing])
            with self.subTest(omitted_source=missing), self.assertRaises(ValueError):
                catalogue.validate(candidate, ROOT)

    def test_quic_rfc_requires_owned_lifecycle_controls(self):
        import json
        import re
        source=(ROOT/'build-support/quic-rfc.mk').read_text()
        helper='check-quic-protocol-artifacts'
        inputs={'build/tooling/tests/quic-protocol-artifacts','build/tooling/tests/quic-qns-local',
                'build/tooling/tests/quic-vn-probe','tests/quic-protocol-artifacts.min',
                'tests/quic-protocol-support.min','tests/quic-qns-local.min','tests/quic-vn-probe.min',
                'tests/interop/qns/endpoint.min'}
        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='QUIC owned lifecycle rules ') as folder:
                makefile=Path(folder)/'probe.mk'
                makefile.write_text(fragment+'\n.PHONY: '+' '.join(sorted(inputs|{'build'}))+
                    '\n'+' '.join(sorted(inputs|{'build'}))+':\n\t@echo INPUT $@\n')
                env=dict(os.environ);env.pop('MAKEFLAGS',None)
                result=subprocess.run(['make','-rRnp','-f',str(makefile),helper],
                    cwd=ROOT,env=env,text=True,capture_output=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr)
                rules={}
                for line in result.stdout.splitlines():
                    match=re.match(r'^([\w./-]+):\s*(.*)$',line)
                    if match:rules.setdefault(match[1],set()).update(match[2].split())
                for gate in ('check-quic-rfc','check-quic-rfc-sanitize'):
                    self.assertIn(helper,rules.get(gate,set()))
                self.assertTrue(inputs<=rules.get(helper,set()))
                commands=dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./build/tooling/tests/quic-protocol-artifacts --artifacts'),1)
                self.assertIn('--artifacts "$artifacts/run"',commands)
                self.assertIn((ROOT/'build/quic-protocol-artifacts.').as_posix(),commands.replace('\\','/'))
                self.assertNotIn('--expect-old-code',commands)
                self.assertNotIn('--case ',commands)
        verify(source)
        for gate in ('check-quic-rfc','check-quic-rfc-sanitize'):
            line=next(line for line in source.splitlines() if line.startswith(gate+':'))
            mutant=source.replace(line,line.replace(' '+helper,'',1),1)
            with self.subTest(missing_helper=gate),self.assertRaises(AssertionError):verify(mutant)
        for dependency in sorted(inputs):
            line=next(line for line in source.splitlines() if line.startswith(helper+':'))
            mutant=source.replace(line,line.replace(' '+dependency,'',1),1)
            with self.subTest(missing_input=dependency),self.assertRaises(AssertionError):verify(mutant)
        for name,old,new in (
                ('old code oracle','tests/quic-protocol-artifacts --artifacts',
                    'tests/quic-protocol-artifacts --expect-old-code --artifacts'),
                ('filtered control','tests/quic-protocol-artifacts --artifacts',
                    'tests/quic-protocol-artifacts --case healthy-shutdown --artifacts'),
                ('relative evidence','$(abspath build)/quic-protocol-artifacts.',
                    'build/quic-protocol-artifacts.')):
            mutant=source.replace(old,new,1)
            self.assertNotEqual(source,mutant)
            with self.subTest(invalid_helper=name),self.assertRaises(AssertionError):verify(mutant)

    def test_quic_rfc_gates_keep_all_drivers_and_public_frontends(self):
        import importlib.util
        import json
        import re
        source = (ROOT / 'build-support/quic-rfc.mk').read_text()
        native, sanitize = 'check-quic-rfc', 'check-quic-rfc-sanitize'
        frontends = {'build/minyarc', 'build/minyarc-callbacks',
                     'build/minyarc-errors-request', 'build/minyarc-errors'}
        inputs = {'minyar', 'build/tooling/tools/clang-driver', 'tools/llvm-sanitizer.min',
                  'build/tooling/tests/quic-rfc', 'tests/quic-rfc.min',
                  'build/tooling/tests/quic-rfc-harness', 'tests/quic-rfc-harness.min',
                  'tests/quic-protocol-artifacts.min',
                  'tests/interop/qns/endpoint.min', 'library/quic.min', 'library/tls.min',
                  'library/tlsserver.min', 'build/tooling/tests/quic-migration-cids-test',
                  'tests/quic-migration-cids-test.min', 'tests/quic-migration-cids.min',
                  'build/tooling/tests/quic-cipher-policy-test', 'tests/quic-cipher-policy-test.min',
                  'tests/quic-cipher-policy.min', 'tests/quic-protocol-support.min',
                  'tests/quic-test-support.min', 'tests/quic-json.min', 'tools/testing.min',
                  'build/tooling/tests/quic-qns-local', 'tests/quic-qns-local.min',
                  'build/tooling/tests/quic-vn-probe', 'tests/quic-vn-probe.min',
                  'tests/interop/qns/client.min', 'tests/interop/qns/server.min'}

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='QUIC RFC Make rules ') as folder:
                makefile = Path(folder) / 'probe.mk'
                fixtures = sorted(frontends | inputs | {'build', 'build/tooling/tests/quic-protocol-artifacts'})
                makefile.write_text(fragment + '\n.PHONY: ' + ' '.join(fixtures)
                                   + '\n' + ' '.join(fixtures)
                                   + ':\n\t@echo INPUT $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(['make', '-rRnp', '-f', str(makefile),
                                         native, sanitize], cwd=ROOT, env=env,
                                        text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s*(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                for gate in ('check', 'check-portable', 'check-quic'):
                    self.assertIn(native, rules.get(gate, set()), gate)
                for gate in ('check-sanitize', 'check-quic-sanitize'):
                    self.assertIn(sanitize, rules.get(gate, set()), gate)
                for target in (native, sanitize):
                    self.assertTrue(frontends | inputs <= rules.get(target, set()), target)
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./build/tooling/tests/quic-rfc --optimization'), 2)
                self.assertEqual(commands.count('--optimization both'), 2)
                self.assertEqual(commands.count('--sanitize'), 1)
                self.assertEqual(commands.count('mktemp -d "'), 3)
                self.assertEqual(commands.count('--artifacts "$artifacts/run"'), 3)
                self.assertNotIn('--case ', commands)
                self.assertNotIn('--expect-old-code', commands)
                for suffix in ('native', 'sanitize'):
                    self.assertIn((ROOT/'build'/('quic-rfc-' + suffix)).as_posix(),
                                  commands.replace('\\', '/'))

        verify(source)
        for gate in ('check', 'check-portable', 'check-quic',
                     'check-sanitize', 'check-quic-sanitize'):
            aggregate = ('check-sanitize check-quic-sanitize: ' + sanitize
                         if gate in ('check-sanitize', 'check-quic-sanitize')
                         else 'check check-portable check-quic: ' + native)
            names, dependency = aggregate.split(': ', 1)
            mutant = source.replace(aggregate, ' '.join(
                name for name in names.split() if name != gate) + ': ' + dependency, 1)
            with self.subTest(missing_gate=gate), self.assertRaises(AssertionError):
                verify(mutant)
        for dependency in sorted(frontends | inputs):
            mutant = source.replace(dependency, '', 1)
            self.assertNotEqual(mutant, source)
            with self.subTest(missing_dependency=dependency), self.assertRaises(AssertionError):
                verify(mutant)
        for name, old, new in (
                ('single optimization', '--optimization both', '--optimization 0'),
                ('missing sanitizer', '--sanitize --artifacts', '--artifacts'),
                ('case filter', '--optimization both', '--optimization both --case migration-cid'),
                ('old-code oracle', '--optimization both', '--optimization both --expect-old-code'),
                ('relative evidence', '$(abspath build)/quic-rfc-', 'build/quic-rfc-')):
            mutant = source.replace(old, new, 1)
            self.assertNotEqual(mutant, source)
            with self.subTest(invalid_recipe=name), self.assertRaises(AssertionError):
                verify(mutant)
        targets = linux_targets()
        for target in (native, sanitize):
            self.assertEqual(targets.count(target), 1)
        assert_ci_runs_quic_group(self, 'check-quic', 'check-quic-sanitize')
        self.assertEqual(formatter_version(), '23.1.2')
        catalogue = native_catalogue()
        data = json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        native = {'build/tooling/tests/quic-migration-cids-test', 'tests/quic-migration-cids-test.min',
                  'build/tooling/tests/quic-cipher-policy-test', 'tests/quic-cipher-policy-test.min',
                  'tests/quic-protocol-support.min', 'tests/quic-test-support.min', 'tools/testing.min',
                  'build/tooling/tests/quic-rfc', 'tests/quic-rfc.min', 'build/tooling/tests/quic-rfc-harness',
                  'tests/quic-rfc-harness.min', 'tests/quic-protocol-artifacts.min', 'tests/quic-json.min',
                  'build/tooling/tests/quic-qns-local', 'tests/quic-qns-local.min',
                  'build/tooling/tests/quic-vn-probe', 'tests/quic-vn-probe.min', 'tests/interop/qns/endpoint.min'}
        for name in sorted(inputs - native - {'minyar', 'build/tooling/tools/clang-driver',
                                              'tools/llvm-sanitizer.min', 'library/quic.min',
                                              'library/tls.min', 'library/tlsserver.min'}):
            self.assertIn(name, catalogue.discover(ROOT))
            with self.subTest(missing_source=name), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[row for row in data['sources']
                                                       if row['path'] != name]), ROOT)


    def test_generated_llvm_sanitizer_is_mandatory_and_tracks_canonical_helper(self):
        import json
        import re
        source = (ROOT / 'build-support/checks.mk').read_text()
        marker = '# Real unsafe generated-program accesses must fail'
        self.assertIn(marker, source)
        aggregate = 'check check-portable check-sanitize: check-generated-llvm-sanitizer'
        begin = source.index(marker)
        end = source.index('\n', source.index(aggregate, begin))
        fragment = source[begin:end + 1]
        expected = {'build/minyarc', 'build/tooling/tests/generated-llvm-sanitizer-test',
                    'tests/generated-llvm-sanitizer.min', 'build/tooling/tools/clang-driver'}

        def verify(candidate, sanitizer=None, selected=None, directory='/clang64/bin'):
            with tempfile.TemporaryDirectory(prefix='actual sanitizer Make rules ') as folder:
                probe = Path(folder)/'probe.mk'
                probe.write_text('LLVM_CC := retained-native-clang\n'
                                 'SANITIZER_LIMITED := sanitizer-limit\n'
                                 'PATH := /retained/native/bin:/usr/bin\n'
                                 'MINYAR_SANITIZER_CLANG := ' + (sanitizer or '') + '\n'
                                 + candidate + '\n.PHONY: build build/minyarc build/yamux-peer build/tooling/tools/clang-driver build/tooling/tests/generated-llvm-sanitizer-test\n'
                                 'build build/minyarc build/yamux-peer build/tooling/tools/clang-driver build/tooling/tests/generated-llvm-sanitizer-test:\n')
                environment = dict(os.environ)
                environment.pop('MAKEFLAGS', None)
                result = subprocess.run(['make', '-rRnp', '-f', str(probe), 'check'],
                                        cwd=ROOT, env=environment, capture_output=True,
                                        text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([A-Za-z][\w/-]*):(?: *)([^#]*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                for gate in ('check', 'check-portable', 'check-sanitize'):
                    self.assertIn('check-generated-llvm-sanitizer', rules.get(gate,set()), gate)
                self.assertTrue(expected <= rules.get('check-generated-llvm-sanitizer',set()))
                commands = dry_run_commands(result.stdout)
                self.assertIn('./build/tooling/tests/generated-llvm-sanitizer-test', commands)
                command = next(line for line in commands.splitlines()
                               if './build/tooling/tests/generated-llvm-sanitizer-test' in line)
                fields = shlex.split(command)
                self.assertIn('MINYAR_TEST_CLANG=' +
                              (selected or sanitizer or 'retained-native-clang'), fields)
                self.assertIn('sanitizer-limit', fields)
                searches = [field[len('PATH='):] for field in fields
                            if field.startswith('PATH=')]
                self.assertEqual(len(searches), 1)
                search = searches[0]
                if sanitizer:
                    suffix = ':/retained/native/bin:/usr/bin'
                    self.assertTrue(search.endswith(suffix), search)
                    self.assertEqual(search[:-len(suffix)].rstrip('/'), directory)
                else:
                    self.assertEqual(search, '/retained/native/bin:/usr/bin')
                self.assertIn('--artifacts "$artifacts/run"', commands)
                self.assertIn((ROOT/'build/generated-llvm-sanitizer-').as_posix(),
                              commands.replace('\\','/'))
        verify(fragment)
        verify(fragment, '/clang64/bin/clang.exe')
        verify(fragment, '/opt/LLVM 23/bin/clang.exe', directory='/opt/LLVM 23/bin')
        verify(fragment, "/opt/LLVM's 23/bin/clang.exe", directory="/opt/LLVM's 23/bin")
        import platform
        if platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
            selected = '/c/MinyarUnify-20261012/LLVM 23/bin/clang.exe'
            for spelling in (selected, 'C:/MinyarUnify-20261012/LLVM 23/bin/clang.exe',
                             r'C:\MinyarUnify-20261012\LLVM 23\bin\clang.exe'):
                verify(fragment, spelling, selected, '/c/MinyarUnify-20261012/LLVM 23/bin')
            selected = '//20.20.20.1/Data/LLVM 23/bin/clang.exe'
            for spelling in (selected, r'\\20.20.20.1\Data\LLVM 23\bin\clang.exe'):
                verify(fragment, spelling, selected, '//20.20.20.1/Data/LLVM 23/bin')
        clang_rule = next(line for line in fragment.splitlines()
                          if line.startswith('GENERATED_SANITIZER_CLANG ='))
        path_rule = next(line for line in fragment.splitlines()
                         if line.startswith('GENERATED_SANITIZER_PATH ='))
        for old, new, sanitizer, directory in (
                (clang_rule, 'GENERATED_SANITIZER_CLANG = $(LLVM_CC)',
                 '/clang64/bin/clang.exe', '/clang64/bin'),
                ('PATH="$(GENERATED_SANITIZER_PATH)" ', '',
                 '/clang64/bin/clang.exe', '/clang64/bin'),
                (path_rule, 'GENERATED_SANITIZER_PATH = $(PATH)',
                 '/clang64/bin/clang.exe', '/clang64/bin'),
                (path_rule, 'GENERATED_SANITIZER_PATH = /wrong/runtime:$(PATH)',
                 '/clang64/bin/clang.exe', '/clang64/bin'),
                (path_rule, 'GENERATED_SANITIZER_PATH = $(dir $(MINYAR_SANITIZER_CLANG)):$(PATH)',
                 '/opt/LLVM 23/bin/clang.exe', '/opt/LLVM 23/bin')):
            mutant = fragment.replace(old, new, 1)
            self.assertNotEqual(mutant, fragment)
            with self.subTest(dispatch=old), self.assertRaises(AssertionError):
                verify(mutant, sanitizer, directory=directory)
        aggregate = 'check check-portable check-sanitize: check-generated-llvm-sanitizer'
        for gate in ('check','check-portable','check-sanitize'):
            missing = fragment.replace(aggregate, ' '.join(x for x in aggregate.split(':')[0].split()
                                                          if x != gate) + ': check-generated-llvm-sanitizer')
            with self.subTest(gate=gate), self.assertRaises(AssertionError):
                verify(missing)
        for dependency in sorted(expected):
            with self.subTest(dependency=dependency), self.assertRaises(AssertionError):
                verify(fragment.replace(dependency+' ', '', 1))
        compiler = (ROOT/'build-support/compiler.mk').read_text()
        rules = re.findall(r'^build/[^:\n]*sanitize\.ll:([^\n]*)\n\t([^\n]*)',compiler,re.M)
        self.assertEqual(len(rules),1)
        self.assertTrue(all('build/tooling/tools/clang-driver' in r and 'clang-driver sanitize-llvm' in c
                            for r, c in rules))
        shim = (ROOT/'tests/llvm_sanitizer.py').read_text()
        self.assertIn('from sanitizer_llvm import',shim)
        self.assertNotIn('def instrument_address_sanitizer',shim)
        self.assertEqual(linux_targets().count('check-generated-llvm-sanitizer'),1)

    def test_private_retirement_gates_execute_actual_operation_contract(self):
        import importlib.util
        import json
        import re
        source = (ROOT/'build-support/managed-graphs.mk').read_text()
        marker = '# Every C command takes N OPERATION [ARGS]'
        self.assertIn(marker,source)
        fragment = source[source.index(marker):]
        pair = {'check-cycle-private-retirement','check-cycle-private-retirement-sanitize'}
        inputs = {'build/tooling/tests/cycle-private-retirement','tests/cycle-idle-invalidation.c',
                  'tests/cycle-private-retirement-v5.json','tests/cycle-additive.c'}

        def verify(candidate):
            with tempfile.TemporaryDirectory(prefix='actual private retirement Make rules ') as folder:
                probe=Path(folder)/'probe.mk'
                probe.write_text(candidate+'\nbuild:\nbuild/tooling/%:\n\t@echo TOOL $@\n')
                result=subprocess.run(['make','-rRnp','-f',str(probe),'check'],
                                      cwd=ROOT,capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr)
                rules={}
                for line in result.stdout.splitlines():
                    match=re.match(r'^([A-Za-z][\w/-]*):(?: *)([^#]*)$',line)
                    if match:rules.setdefault(match[1],set()).update(match[2].split())
                for gate in ('check','check-portable','check-managed-graphs-profiles'):
                    self.assertTrue(pair <= rules.get(gate,set()),gate)
                self.assertIn('check-cycle-private-retirement-sanitize',rules.get('check-sanitize',set()))
                for target in pair:self.assertTrue(inputs <= rules[target],target)
                private_commands={}
                for kind in ('native','sanitize'):
                    target='check-cycle-private-retirement'+('-sanitize' if kind=='sanitize' else '')
                    recipe=subprocess.run(['make','-rRn','-f',str(probe),target],
                                          cwd=ROOT,capture_output=True,text=True,timeout=15)
                    self.assertEqual(recipe.returncode,0,recipe.stderr)
                    commands=recipe.stdout
                    private_commands[kind]=commands
                    self.assertEqual(commands.count('./build/tooling/tests/cycle-private-retirement'),1,target)
                    self.assertEqual(commands.count('--evidence "$evidence/run"'),1,target)
                    self.assertEqual(commands.count('--sanitize --evidence'),int(kind=='sanitize'),target)
                    self.assertNotIn('--profiles',commands)
                    self.assertNotIn('--budgets',commands)
                    self.assertIn((ROOT/'build'/('cycle-private-retirement-'+kind)).as_posix(),
                                  commands.replace('\\','/'))
                commands='\n'.join(private_commands.values())
                self.assertEqual(commands.count('./build/tooling/tests/cycle-private-retirement'),2)
                self.assertEqual(commands.count('--evidence "$evidence/run"'),2)
                self.assertEqual(commands.count('--sanitize --evidence'),1)
        verify(fragment)
        for gate in ('check','check-portable','check-managed-graphs-profiles','check-sanitize'):
            line = next(line for line in fragment.splitlines() if line.startswith(gate+':'))
            for target in set(line.split(':',1)[1].split()) & pair:
                with self.subTest(gate=gate,target=target),self.assertRaises(AssertionError):
                    verify(fragment.replace(line,line.replace(' '+target,'',1),1))
        for dependency in sorted(inputs):
            with self.subTest(input=dependency),self.assertRaises(AssertionError):
                verify(fragment.replace(dependency+' ','',1))
        evidence='--evidence "$$evidence/run"'
        for target in sorted(pair):
            block=re.search(r'(?m)^'+re.escape(target)+r':[^\n]*\n(?:\t[^\n]*(?:\n|$))+',fragment)
            self.assertIsNotNone(block,target)
            recipe=block.group()
            self.assertEqual(recipe.count(evidence),1,target)
            for replacement in ('',evidence+' '+evidence):
                broken=fragment[:block.start()]+recipe.replace(evidence,replacement,1)+fragment[block.end():]
                with self.subTest(target=target,evidence=replacement),self.assertRaises(AssertionError):
                    verify(broken)
        driver=str(ROOT/'build/tooling/tests/cycle-private-retirement')
        windows=dict(os.environ,MINYAR_CYCLE_HOST='Windows')
        def query(*arguments,env=None):
            return subprocess.run([driver,*arguments],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
        def operation_plan(profile,budget):
            result=query('--plan',profile,str(budget))
            self.assertEqual(result.returncode,0,result.stderr)
            return [line.split(' ') for line in result.stdout.splitlines()]
        def validate_failure_control(status,stdout,stderr,timedout=False):
            with tempfile.TemporaryDirectory(prefix='retirement failure control ') as folder:
                out=Path(folder)/'stdout';err=Path(folder)/'stderr'
                out.write_bytes(stdout);err.write_bytes(stderr)
                result=query('--validate-failure-control',str(status),'true' if timedout else 'false',str(out),str(err))
            if result.returncode==1:raise AssertionError(result.stderr)
            self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(query('--heap-bytes').stdout,'4194304\n')
        self.assertEqual(len(operation_plan('system',1)),38)
        self.assertEqual(len(operation_plan('fixed',32)),36)
        self.assertEqual(len(operation_plan('eager',32)),16)
        for mode in ('phase','local-mark','local-sweep','full-mark','full-sweep','transfer','drop','rebuild'):
            for recent in ('0','1'):
                self.assertIn(['32','queued',mode,recent],operation_plan('fixed',32))
        for mode in ('active-local','active-full'):
            for phase in ('1','2','3'):
                self.assertIn(['32',mode,phase],operation_plan('system',1024))
        for n in (32,256,2048):
            self.assertIn([str(n),'private','assert-local'],operation_plan('system',1))
        self.assertFalse(any(row[1] in ('queued','certificate','reuse','unknown-after-drop')
                             for row in operation_plan('eager',32)))
        selected=query('--profile-selection',env=windows)
        self.assertEqual(selected.returncode,0,selected.stderr)
        self.assertEqual(selected.stdout.splitlines()[0],'profiles system fixed eager')
        self.assertEqual(query('--profile-selection','lazy',env=windows).returncode,2)
        red=b'IDLE label=private n=32 rounds=8 units=1136 epochs=8\nAssertion work <= 16u * rounds + 64u failed\n'
        validate_failure_control(-6,b'',red)
        for status,stdout,stderr,timedout in ((0,b'',red,False),(-6,b'output',red,False),
                (-6,b'',red,True),(-6,b'',red.replace(b'1136',b'128'),False),
                (-6,b'',red.replace(b'work <= 16u * rounds + 64u',b'unrelated assertion'),False)):
            with self.assertRaises(AssertionError):
                validate_failure_control(status,stdout,stderr,timedout)
        catalogue=native_catalogue()
        data=json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        catalogue.validate(data,ROOT)
        for name in ('tests/cycle-idle-invalidation.c',
                     'tests/cycle-private-retirement-v5.json','tests/generated-llvm-sanitizer.min'):
            omitted=dict(data,sources=[row for row in data['sources'] if row['path']!=name])
            with self.subTest(source=name),self.assertRaises(ValueError):
                catalogue.validate(omitted,ROOT)
        self.assertIn('tests/cycle-idle-invalidation.c',formatter_files())
        self.assertEqual(formatter_version(),'23.1.2')


    def test_parallel_signature_gates_prepare_every_frontend_and_fixture(self):
        import importlib.util
        import json
        import re
        native = 'check-parallel-signatures'
        sanitize = native + '-sanitize'
        source = (ROOT / 'build-support/parallel.mk').read_text()
        ordinary = {'minyarc', 'minyarc-callbacks', 'minyarc-errors'}
        instrumented = {x + '-sanitize' for x in ordinary}
        fixtures = {(path.relative_to(ROOT)).as_posix()
                    for path in (ROOT / 'tests/parallel-signatures').glob('*.min')}
        self.assertEqual(len(fixtures), 20)
        stage3 = {'build/compiler-stage3.ll', 'build/closure-compiler-stage3.ll',
                  'build/errors-compiler-stage3.ll'}

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='minyar parallel ABI wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                artifacts = {'build/' + x for x in ordinary | instrumented} | stage3 | {
                    'build/minyar-runtime.o', 'build', 'build/testing/cycle-runtime.o',
                    'build/tooling/tests/compiler-behavior', 'build/tooling/tests/parallel-signatures'}
                makefile.write_text(fragment + '\n.PHONY: ' + ' '.join(sorted(artifacts)) +
                                   '\n' + ' '.join(sorted(artifacts)) + ':\n\t@echo ARTIFACT $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(
                    ['make', '-np', '-f', str(makefile), native, sanitize],
                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                for gate in ('check', 'check-portable', 'check-parallel', 'check-callbacks',
                             'check-errors-language'):
                    self.assertIn(native, rules.get(gate, set()), gate)
                for gate in ('check-sanitize', 'check-parallel-sanitize',
                             'check-callbacks-sanitize', 'check-errors-language-sanitize'):
                    self.assertIn(sanitize, rules.get(gate, set()), gate)
                for target, frontends in ((native, ordinary), (sanitize, instrumented)):
                    self.assertTrue({'build/' + x for x in frontends} <= rules[target], target)
                    self.assertTrue(fixtures | {'build/tooling/tests/parallel-signatures',
                                                'build/minyar-runtime.o'}
                                    <= rules[target], target)
                self.assertTrue(stage3 <= rules[native])
                self.assertIn('build/tooling/tests/compiler-behavior', rules[native])
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./build/tooling/tests/parallel-signatures;'), 2)
                self.assertIn('for frontend in minyarc minyarc-callbacks minyarc-errors;', commands)
                self.assertIn('for frontend in minyarc-sanitize minyarc-callbacks-sanitize minyarc-errors-sanitize;', commands)
                self.assertEqual(commands.count('MINYAR_TEST_COMPILER="./build/$frontend"'), 2)
                self.assertEqual(commands.count('MINYAR_PARALLEL_OBSERVATIONS="$evidence/$frontend"'), 2)
                self.assertEqual(commands.count('mktemp -d "'), 2)
                self.assertIn('MINYAR_TEST_LINK_FLAGS=-fsanitize=address,undefined', commands)
                self.assertNotIn('MINYAR_PARALLEL_IR_CONTROL=', commands)
                for suffix in ('native', 'sanitize'):
                    self.assertIn((ROOT / 'build' / ('parallel-signatures-' + suffix)).as_posix(),
                                  commands.replace('\\', '/'))
                for family in ('compiler', 'closure-compiler', 'errors-compiler'):
                    self.assertIn(f'--ir build/{family}-stage3.ll', commands)
                self.assertEqual(commands.count('./build/tooling/tests/compiler-behavior --profile'), 3)
                self.assertNotIn('cmp build/', commands)

        verify(source)
        for aggregate in (
                'check check-portable check-parallel check-callbacks check-errors-language: ' + native,
                'check-sanitize check-parallel-sanitize check-callbacks-sanitize check-errors-language-sanitize: ' + sanitize):
            names, dependency = aggregate.split(': ', 1)
            for gate in names.split():
                mutant = source.replace(aggregate, ' '.join(x for x in names.split() if x != gate)
                                        + ': ' + dependency, 1)
                with self.subTest(missing_gate=gate), self.assertRaises(AssertionError):
                    verify(mutant)
        for declaration in (
                'PARALLEL_SIGNATURE_FRONTENDS = minyarc minyarc-callbacks minyarc-errors',
                'PARALLEL_SIGNATURE_SANITIZER_FRONTENDS = minyarc-sanitize minyarc-callbacks-sanitize minyarc-errors-sanitize'):
            left, frontends = declaration.split(' = ', 1)
            for missing in frontends.split():
                mutant = source.replace(declaration, left + ' = ' +
                                        ' '.join(x for x in frontends.split() if x != missing), 1)
                with self.subTest(missing_frontend=missing), self.assertRaises(AssertionError):
                    verify(mutant)
        for fixture in fixtures:
            mutant = source.replace(fixture, '', 1)
            self.assertNotEqual(mutant, source)
            with self.subTest(missing_fixture_prerequisite=fixture), self.assertRaises(AssertionError):
                verify(mutant)
        for old, new in (('$(abspath build)/parallel-signatures-', 'build/parallel-signatures-'),
                         ('MINYAR_PARALLEL_OBSERVATIONS=', 'UNUSED_OBSERVATIONS=')):
            with self.subTest(recipe=old), self.assertRaises(AssertionError):
                verify(source.replace(old, new, 1))

        targets = linux_targets()
        for target in (native, sanitize):
            self.assertEqual(targets.count(target), 1)
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('check-portable', workflow)
        self.assertIn('build/tooling/scripts/check-linux', workflow)
        catalogue = native_catalogue()
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for name in fixtures:
            self.assertIn(name, catalogue.discover(ROOT))
            with self.subTest(missing_source=name), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[r for r in data['sources'] if r['path'] != name]), ROOT)




    def test_signed_relay_has_pinned_peer_and_all_lifetime_gates(self):
        import importlib.util
        import json
        import re
        text = (ROOT / 'build-support/peer-grpc.mk').read_text()
        source = text[text.index('# Signed relay and independently malformed/abrupt'):]
        native = {'check-peer-edge-relay', 'check-peer-edge-relay-lifetime'}
        sanitize = {name + '-sanitize' for name in native}
        tools = {'build/tooling/tests/peer-edge-relay-test', 'build/tooling/tests/peer-edge-relay-lifetime-test'}

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='minyar relay wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                stubs = 'build/minyarc build build/peergrpc-peer ' + ' '.join(sorted(tools))
                makefile.write_text(fragment + '\n.PHONY: ' + stubs + '\n' + stubs + ':\n\t@echo ARTIFACT $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(['make', '-np', '-f', str(makefile), *sorted(native | sanitize)],
                                        cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                self.assertTrue(native <= rules.get('check', set()))
                self.assertTrue(sanitize <= rules.get('check-sanitize', set()))
                for target in native | sanitize:
                    self.assertIn('build/peergrpc-peer', rules.get(target, set()))
                    tool = 'build/tooling/tests/peer-edge-relay-lifetime-test' if 'lifetime' in target else 'build/tooling/tests/peer-edge-relay-test'
                    self.assertIn(tool, rules.get(target, set()))
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./build/tooling/tests/peer-edge-relay-test '), 2)
                self.assertEqual(commands.count('./build/tooling/tests/peer-edge-relay-lifetime-test '), 4)
                # Six evidence directories plus one program cache per relay-lifetime recipe.
                self.assertEqual(commands.count('mktemp -d "'), 8)
                self.assertEqual(commands.count('MINYAR_TEST_PROGRAM_CACHE='), 2)
                self.assertEqual(commands.count('--sanitize'), 3)
                for mode in ('malformed', 'abrupt'):
                    self.assertEqual(commands.count('--mode ' + mode), 2)
                self.assertNotIn('--rounds', commands)  # Original functional default1024 preserved.
                self.assertIn((ROOT / 'build' / 'peer-edge-relay-').as_posix(),
                              commands.replace('\\', '/'))

        verify(source)
        for gate, targets in (('check', native), ('check-sanitize', sanitize)):
            for missing in targets:
                line = next(line for line in source.splitlines()
                            if line.startswith(gate + ': '))
                mutant = source.replace(line, gate + ': ' +
                                        ' '.join(x for x in line.split(': ', 1)[1].split() if x != missing), 1)
                with self.subTest(missing_gate=missing), self.assertRaises(AssertionError):
                    verify(mutant)
        targets = linux_targets()
        for target in native | sanitize:
            self.assertEqual(targets.count(target), 1)
        assert_ci_runs_quic_group(self, *sorted(native | sanitize))
        catalogue = native_catalogue()
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)



    def test_ack_scheduling_has_both_optimizations_and_all_mandatory_gates(self):
        import importlib.util
        import json
        import re
        text = (ROOT / 'build-support/checks.mk').read_text()
        begin = text.index('# ACK scheduling gates')
        end = text.index('# Handshake PTO virtual-clock modes', begin)
        source = text[begin:end]
        native, sanitize = 'check-quic-ack', 'check-quic-ack-sanitize'
        tool = 'build/tooling/tests/quic-ack-test'

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='minyar ACK wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                makefile.write_text(fragment + '\n.PHONY: build/minyarc build ' + tool + '\n'
                                   'build/minyarc build ' + tool + ':\n\t@echo ARTIFACT $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(['make', '-np', '-f', str(makefile), native, sanitize],
                                        cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                for gate in ('check', 'check-portable', 'check-quic'):
                    self.assertIn(native, rules.get(gate, set()), gate)
                for gate in ('check-sanitize', 'check-quic-sanitize'):
                    self.assertIn(sanitize, rules.get(gate, set()), gate)
                for target in (native, sanitize):
                    self.assertTrue({tool, 'tests/quic-ack.min', 'build/minyarc'}
                                    <= rules.get(target, set()), target)
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./' + tool + ' '), 2)
                self.assertEqual(commands.count('--optimization both'), 2)
                self.assertEqual(commands.count('--sanitize'), 1)
                self.assertEqual(commands.count('mktemp -d "'), 2)
                self.assertEqual(commands.count('--artifacts '), 2)
                self.assertNotIn('--mode ', commands)  # All author-owned modes stay mandatory.
                for suffix in ('native', 'sanitize'):
                    self.assertIn((ROOT / 'build' / ('quic-ack-' + suffix)).as_posix(),
                                  commands.replace('\\', '/'))

        verify(source)
        for gate in ('check', 'check-portable', 'check-quic',
                     'check-sanitize', 'check-quic-sanitize'):
            aggregate = ('check-sanitize check-quic-sanitize: ' + sanitize if
                         gate in ('check-sanitize', 'check-quic-sanitize') else
                         'check check-portable check-quic: ' + native)
            names, dependency = aggregate.split(': ', 1)
            mutant = source.replace(aggregate, ' '.join(x for x in names.split() if x != gate)
                                    + ': ' + dependency, 1)
            with self.subTest(missing_gate=gate), self.assertRaises(AssertionError):
                verify(mutant)
        for name, old, new in (
                ('single optimization', '--optimization both', '--optimization 0'),
                ('no sanitizer', '--sanitize --artifacts', '--artifacts'),
                ('relative evidence', '$(abspath build)/quic-ack-', 'build/quic-ack-'),
                ('selected mode only', '--optimization both', '--optimization both --mode 0')):
            mutant = source.replace(old, new, 1)
            self.assertNotEqual(mutant, source)
            with self.subTest(invalid_recipe=name), self.assertRaises(AssertionError):
                verify(mutant)
        targets = linux_targets()
        for target in (native, sanitize):
            self.assertEqual(targets.count(target), 1)
        assert_ci_runs_quic_group(self, 'check-quic', 'check-quic-sanitize')
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertEqual(formatter_version(), '23.1.2')
        self.assertIn('--group formatting', workflow)
        self.assertIn('build/tooling/scripts/format', (ROOT / 'tools/linux-matrix.min').read_text())
        catalogue = native_catalogue()
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for fixture in ('tests/quic-ack.min',):
            self.assertIn(fixture, catalogue.discover(ROOT))
            with self.subTest(missing_source=fixture), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[x for x in data['sources']
                                                       if x['path'] != fixture]), ROOT)

    def test_handshake_pto_has_native_and_sanitizer_gates(self):
        import importlib.util
        import json
        import re
        text = (ROOT / 'build-support/checks.mk').read_text()
        begin = text.index('# Handshake PTO virtual-clock modes')
        end = text.index('# Pure controller regression', begin)
        source = text[begin:end]
        native, sanitize = 'check-quic-pto', 'check-quic-pto-sanitize'
        tool = 'build/tooling/tests/quic-pto-test'

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='minyar PTO wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                makefile.write_text(fragment + '\n.PHONY: build/minyarc build ' + tool + '\n'
                                   'build/minyarc build ' + tool + ':\n\t@echo ARTIFACT $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(['make', '-np', '-f', str(makefile), native, sanitize],
                                        cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                for gate in ('check', 'check-portable', 'check-quic'):
                    self.assertIn(native, rules.get(gate, set()), gate)
                for gate in ('check-sanitize', 'check-quic-sanitize'):
                    self.assertIn(sanitize, rules.get(gate, set()), gate)
                for target in (native, sanitize):
                    self.assertTrue({tool, 'tests/quic-pto.min', 'build/minyarc'}
                                    <= rules.get(target, set()), target)
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./' + tool + ' '), 3)
                for level in ('0', '1', '2'):
                    self.assertEqual(commands.count('--optimization ' + level), 1)
                self.assertEqual(commands.count('--sanitize'), 1)
                self.assertEqual(commands.count('mktemp -d "'), 3)
                for suffix in ('native-O0', 'native-O2', 'sanitize-O1'):
                    self.assertIn((ROOT / 'build' / ('quic-pto-' + suffix)).as_posix(),
                                  commands.replace('\\', '/'))

        verify(source)
        for gate in ('check', 'check-portable', 'check-quic', 'check-sanitize', 'check-quic-sanitize'):
            aggregate = ('check-sanitize check-quic-sanitize: ' + sanitize if
                         gate in ('check-sanitize', 'check-quic-sanitize') else
                         'check check-portable check-quic: ' + native)
            names, dependency = aggregate.split(': ', 1)
            mutant = source.replace(aggregate, ' '.join(x for x in names.split() if x != gate)
                                    + ': ' + dependency, 1)
            with self.subTest(missing_gate=gate), self.assertRaises(AssertionError):
                verify(mutant)
        namespace = {'TARGETS': linux_targets()}
        for target in (native, sanitize):
            self.assertEqual(namespace['TARGETS'].count(target), 1)
        assert_ci_runs_quic_group(self, 'check-quic', 'check-quic-sanitize')
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        catalogue = native_catalogue()
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for fixture in ('tests/quic-pto.min',):
            self.assertIn(fixture, catalogue.discover(ROOT))
            with self.subTest(missing_source=fixture), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[x for x in data['sources'] if x['path'] != fixture]), ROOT)


    def test_registration_exposure_has_required_native_and_sanitizer_gates(self):
        import importlib.util
        import json
        import re
        from unittest.mock import patch
        native = 'check-cycle-registration-exposure'
        sanitize = native + '-sanitize'
        source = (ROOT / 'build-support/managed-graphs.mk').read_text()

        def verify(text):
            with tempfile.TemporaryDirectory(prefix='minyar registration wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                makefile.write_text(text + '\n.PHONY: build/minyarc-errors build/minyarc-errors-sanitize\n'
                                   'build/minyarc-errors build/minyarc-errors-sanitize:\n\t@echo ARTIFACT $@\n'
                                   'build/tooling/%:\n\t@echo TOOL $@\n')
                env = dict(os.environ)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(
                    ['make', '-np', '-f', str(makefile), native, sanitize],
                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                both = {native, sanitize}
                for gate in ('check', 'check-portable', 'check-managed-graphs-profiles'):
                    self.assertTrue(both <= rules.get(gate, set()), gate)
                self.assertIn(sanitize, rules.get('check-sanitize', set()))
                fixtures = {'tests/cycle-registration-exposure.c', 'tests/cycle-late-registration.c',
                            'tests/cycle-late-registration.min', 'tests/cycle-additive.c',
                            'build/tooling/tests/cycle-registration', 'build/tooling/tests/errors-language'}
                for target in both:
                    self.assertTrue(fixtures <= rules.get(target, set()), target)
                self.assertIn('build/minyarc-errors', rules[native])
                self.assertIn('build/minyarc-errors-sanitize', rules[sanitize])
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('./build/tooling/tests/cycle-registration --'), 2)
                self.assertEqual(commands.count('--sanitize'), 1)
                self.assertNotIn('--nodes', commands)
                self.assertIn('cycle-registration-exposure-native', commands)
                self.assertIn('cycle-registration-exposure-sanitize', commands)

        verify(source)
        # Removing any required aggregate really changes Make's prerequisite
        # database; a source-string reference alone cannot satisfy this gate.
        for gate in ('check', 'check-portable', 'check-managed-graphs-profiles', 'check-sanitize'):
            line = gate + ': ' + (sanitize if gate == 'check-sanitize'
                                  else native + ' ' + sanitize) + '\n'
            self.assertEqual(source.count(line), 1, gate)
            with self.subTest(missing_gate=gate), self.assertRaises(AssertionError):
                verify(source.replace(line, '', 1))

        for target in (native, sanitize):
            self.assertEqual(linux_targets().count(target), 1)
        for fixture in ('tests/cycle-registration-exposure.c', 'tests/cycle-late-registration.c'):
            self.assertIn(fixture, formatter_files())
        catalogue = native_catalogue()
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for fixture in ('tests/cycle-registration-exposure.c', 'tests/cycle-late-registration.c',
                        'tests/cycle-late-registration.min'):
            self.assertIn(fixture, catalogue.discover(ROOT))
            with self.subTest(uncatalogued=fixture), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[row for row in data['sources']
                                                       if row['path'] != fixture]), ROOT)
        selector = 'test_result_callback_cycles_in_both_payload_slots_are_collected'
        registration = (ROOT / 'tests/cycle-registration.min').read_text()
        self.assertIn('"build/tooling/tests/errors-language", "ErrorsLanguage.' + selector + '"', registration)
        self.assertIn('fixtures.selected("ErrorsLanguage", "' + selector + '")',
                      (ROOT / 'tests/errors-language.min').read_text())
        driver = str(ROOT / 'build/tooling/tests/cycle-registration')
        windows = dict(os.environ, MINYAR_CYCLE_HOST='Windows')
        with tempfile.TemporaryDirectory(prefix='minyar registration driver ') as folder:
            selected = subprocess.run([driver, '--profile-selection'], cwd=folder, env=windows,
                                      capture_output=True, text=True, timeout=60)
            self.assertEqual(selected.returncode, 0, selected.stderr)
            lines = selected.stdout.splitlines()
            self.assertEqual(lines[0], 'profiles system fixed eager')
            self.assertEqual(json.loads(lines[1][len('unsupported '):])['profile'], 'lazy')
            refused = subprocess.run([driver, '--profile-selection', 'lazy'], cwd=folder, env=windows,
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(refused.returncode, 2)
            unsupported = subprocess.run([driver, '--profiles', 'lazy', '--evidence', 'unused'],
                                         cwd=folder, env=dict(windows, MINYAR_CYCLE_HOST='MINGW64_NT-10.0'),
                                         capture_output=True, text=True, timeout=60)
            self.assertEqual(unsupported.returncode, 2, unsupported.stderr)
            self.assertFalse((Path(folder) / 'unused').exists())
            # These schedules are built into main(void), not runtime graph sizes.
            nodes = subprocess.run([driver, '--evidence', 'out', '--nodes', '2048'], cwd=folder,
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(nodes.returncode, 2, nodes.stderr)
            self.assertFalse((Path(folder) / 'out').exists())

    def test_registered_growth_is_mandatory_with_native_and_sanitizer_drivers(self):
        import re
        with tempfile.TemporaryDirectory(prefix='minyar registry wiring ') as folder:
            makefile = Path(folder) / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/managed-graphs.mk').replace(' ', '\\ ') + '\n')
            env = dict(os.environ)
            env.pop('MAKEFLAGS', None)
            result = subprocess.run(
                ['make', '-np', '-f', str(makefile), 'check-cycle-registry-growth',
                 'check-cycle-registry-growth-sanitize'],
                cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            rules = {}
            for line in result.stdout.splitlines():
                match = re.match(r'^([\w./-]+):\s+(.*)$', line)
                if match:
                    rules.setdefault(match[1], set()).update(match[2].split())
            both = {'check-cycle-registry-growth', 'check-cycle-registry-growth-sanitize'}
            for gate in ('check', 'check-portable', 'check-managed-graphs-profiles'):
                self.assertTrue(both <= rules.get(gate, set()), gate)
            self.assertIn('check-cycle-registry-growth-sanitize', rules.get('check-sanitize', set()))
            for target in both:
                self.assertIn('tests/cycle-registry-growth.c', rules.get(target, set()), target)
                self.assertIn('tests/cycle-additive.c', rules.get(target, set()), target)
            commands = dry_run_commands(result.stdout)
            self.assertEqual(commands.count('./build/tooling/tests/cycle-additive --fixture'), 2)
            self.assertEqual(commands.count('--fixture cycle-registry-growth.c'), 2)
            self.assertEqual(commands.count('--sanitize'), 1)
            self.assertIn('cycle-registry-growth-native', commands)
            self.assertIn('cycle-registry-growth-sanitize', commands)

    def test_native_sanitizers_use_supported_leak_detection(self):
        from unittest.mock import patch
        from clang_helpers import asan_leak_options
        with tempfile.TemporaryDirectory(prefix='minyar sanitizer wiring ') as folder:
            work = Path(folder)
            uname = work / 'uname'
            uname.write_text('#!' + sys.executable + '\nimport os\nprint(os.environ["TEST_UNAME"])\n')
            uname.chmod(0o755)
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'Makefile').replace(' ', '\\ ') + '\n'
                '.PHONY: probe\nprobe:\n\t@echo "$(NATIVE_SANITIZER_ENV)"\n')
            for system, os_value, leaks in (
                    ('Linux', '', 1), ('Darwin', '', 0),
                    ('Windows', 'Windows_NT', 0), ('Linux', 'Windows_NT', 0),
                    ('MINGW64_NT-10.0', '', 0), ('MSYS_NT-10.0', '', 0),
                    ('CYGWIN_NT-10.0', '', 0)):
                with self.subTest(system=system, os_value=os_value):
                    env = dict(os.environ, PATH=str(work) + os.pathsep + os.environ['PATH'],
                               TEST_UNAME=system)
                    env.pop('MAKEFLAGS', None)
                    result = subprocess.run(
                        ['make', '-n', '-f', str(makefile), 'OS=' + os_value,
                         '-o', 'build/minyarc', 'probe', 'check-tls-validity-sanitize'],
                        cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    expected = f'ASAN_OPTIONS=detect_leaks={leaks} UBSAN_OPTIONS=halt_on_error=1'
                    self.assertEqual(result.stdout.count(expected), 2, result.stdout)
                    self.assertIn('build/tooling/tests/tls-validity-test --sanitize', result.stdout)
                    if not os_value or system == 'Windows':
                        with patch('clang_helpers.platform.system', return_value=system):
                            self.assertEqual(asan_leak_options(), f'detect_leaks={leaks}')

    def test_managed_graph_launcher_builds_only_supported_incremental_driver(self):
        with tempfile.TemporaryDirectory(prefix='minyar build wiring ') as folder:
            work = Path(folder)
            uname = work / 'uname'
            uname.write_text('#!' + sys.executable + '\nimport os\nprint(os.environ["TEST_UNAME"])\n')
            uname.chmod(0o755)
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/managed-graphs.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: build/minyarc build/minyarc-callbacks build/minyarc-modules build/minyar-module-build\n'
                'build/minyarc build/minyarc-callbacks build/minyarc-modules build/minyar-module-build:\n'
                '\t@echo ARTIFACT $@\n'
                '.PHONY: build/tooling/tests/managed-graphs-launcher tests/sha256-test-native.c runtime/native/sha256.c\n'
                'build/tooling/tests/managed-graphs-launcher tests/sha256-test-native.c runtime/native/sha256.c:\n'
                '\t@echo TOOL $@\n')
            for system, os_value, incremental in (
                    ('Linux', '', True), ('Darwin', '', True), ('Windows_NT', 'Windows_NT', False),
                    ('MINGW64_NT-10.0', '', False), ('MSYS_NT-10.0', '', False),
                    ('CYGWIN_NT-10.0', '', False)):
                with self.subTest(system=system):
                    env = dict(os.environ, PATH=str(work) + os.pathsep + os.environ['PATH'],
                               TEST_UNAME=system)
                    env.pop('MAKEFLAGS', None)
                    result = subprocess.run(['make', '-n', '-f', str(makefile),
                                             'OS=' + os_value, 'check-managed-graphs-launcher'],
                                            cwd=work, env=env, text=True, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    artifacts = {line.split('ARTIFACT ', 1)[1] for line in result.stdout.splitlines()
                                 if 'ARTIFACT ' in line}
                    expected = {'build/minyarc', 'build/minyarc-callbacks'}
                    if incremental: expected |= {'build/minyarc-modules', 'build/minyar-module-build'}
                    self.assertEqual(artifacts, expected)
                    self.assertIn('./build/tooling/tests/managed-graphs-launcher', result.stdout)


    def test_peer_driver_gates_prepare_the_request_frontend(self):
        # The real driver runs the request parser after status 1 or 86. Its
        # artifact-only make shim must never trigger a build while testing
        # rejection diagnostics or declaration-cache transitions.
        with tempfile.TemporaryDirectory(prefix='minyar peer wiring ') as folder:
            work = Path(folder)
            makefile = work / 'probe.mk'
            targets = (
                'build/minyarc', 'build/minyarc-modules',
                'build/minyar-default-runtime.o', 'build/minyar-module-build',
                'build/minyarc-errors-request', 'build/minyar-runtime.o',
                'build/minyarc-sanitize', 'build/minyar-runtime-sanitize.o',
                'build/ownership-runtime.o', 'build/tooling/tests/suite-catalogue',
                'build/testing/cycle-runtime.o', 'runtime/native/sha256.c',
                'build/tooling/tests/peer-manifest', 'build/tooling/tools/check-peer-audit',
                'build/tooling/tests/peer-audit-harness', 'build/tooling/tests/peer-go-domains',
                'build/tooling/tests/peer-zig-domains', 'build/tooling/tests/peer-regressions',
                'build/tooling/tests/peer-cpp-java-js', 'build/tooling/tests/peer-rust-go-zig',
                'build/tooling/tests/peer-python-swift-ruby-lua')
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/peer-tests.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: ' + ' '.join(targets) + '\n' +
                ' '.join(targets) + ':\n\t@echo ARTIFACT $@\n')
            for suite in ('tests/peer-rust-go-zig.min', 'tests/peer-regressions.min'):
                for gate in ('check-peer-regressions', 'check-peer-optimizations',
                             'check-peer-sanitize', 'check-peer-ownership'):
                    with self.subTest(suite=suite, gate=gate):
                        env = dict(os.environ)
                        env.pop('MAKEFLAGS', None)
                        result = subprocess.run(
                            ['make', '-n', '-f', str(makefile),
                             'PEER_SUITES=' + suite, gate],
                            cwd=work, env=env, text=True, capture_output=True,
                            timeout=10)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        artifacts = {
                            line.split('ARTIFACT ', 1)[1]
                            for line in result.stdout.splitlines()
                            if 'ARTIFACT ' in line}
                        needs_driver = (suite == 'tests/peer-rust-go-zig.min'
                                        or gate == 'check-peer-ownership')
                        self.assertEqual(
                            'build/minyarc-errors-request' in artifacts,
                            needs_driver)
                        self.assertEqual(
                            'build/minyar-module-build' in artifacts,
                            needs_driver)


    def test_grpc_gates_verify_external_peers_and_bound_default_builds(self):
        tools = ' '.join('build/tooling/tests/' + name for name in (
            'http2-test', 'http2-churn-test', 'peer-grpc-test', 'peer-grpc-churn-test', 'peer-grpc-retire-test',
            'peer-edge-test', 'peer-edge-retry-test', 'peer-edge-cids-test', 'peer-edge-cid-stock-test',
            'peer-edge-relay-test', 'peer-edge-relay-lifetime-test', 'peer-edge-pki-test'))
        with tempfile.TemporaryDirectory(prefix='minyar grpc wiring ') as folder:
            work = Path(folder)
            for name in ('tests/interop/peergrpc/main.go', 'tests/interop/peergrpc/edge.go',
                         'tests/interop/peergrpc/go.mod', 'tests/interop/peergrpc/go.sum', 'runtime/native/net.c'):
                path = work / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('')
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/peer-grpc.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: build/minyarc build build/testing/cycle-runtime.o ' + tools + '\n'
                'build/minyarc build build/testing/cycle-runtime.o ' + tools + ':\n\t@echo ARTIFACT $@\n')
            for gate in ('check-http2', 'check-peer-grpc', 'check-peer-grpc-sanitize',
                         'check-http2-churn', 'check-http2-churn-sanitize', 'check-peer-grpc-churn',
                         'check-peer-grpc-churn-sanitize', 'check-peer-grpc-retire',
                         'check-peer-grpc-retire-sanitize', 'check-peer-edge', 'check-peer-edge-sanitize',
                         'check-peer-edge-retry', 'check-peer-edge-retry-sanitize', 'check-peer-edge-cids',
                         'check-peer-edge-cids-sanitize', 'check-peer-edge-relay', 'check-peer-edge-relay-sanitize',
                         'check-peer-edge-relay-lifetime', 'check-peer-edge-relay-lifetime-sanitize',
                         'check-peer-edge-pki', 'check-peer-edge-pki-sanitize'):
                with self.subTest(gate=gate):
                    env = dict(os.environ)
                    env.pop('MAKEFLAGS', None)
                    result = subprocess.run(['make', '-n', '-f', str(makefile), gate],
                        cwd=work, env=env, text=True, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn('check-peer-python.py', result.stdout)
                    self.assertNotIn('peergrpc-venv', result.stdout)
                    self.assertIn('GOMAXPROCS=2 go build -mod=readonly -trimpath', result.stdout)
                    self.assertIn('.tmp" self-test', result.stdout)
                    self.assertIn('./build/tooling/tests/', result.stdout)

    def test_quic_official_adapter_requires_all_linux_controls(self):
        import json
        import re
        fragment = (ROOT/'build-support/quic-official-adapter.mk').read_text()
        target = 'check-quic-official-adapter'
        inputs = {'tests/quic-official-adapter.min',
                  'tests/quic-official-support.min',
                  'tests/quic-official-inputs.min',
                  'scripts/check-quic-official-inputs.min',
                  'tests/interop/qns/owned-adapter.min',
                  'tests/interop/qns/owned-adapter.c',
                  'tests/interop/qns/owned-common.min',
                  'tests/interop/qns/owned-process.min',
                  'tests/interop/qns/owned-daemon.min',
                  'tests/interop/qns/owned-derive.min',
                  'tests/quic-json.min',
                  'tests/quic-simulator-shutdown.min',
                  'tests/interop/qns/simulator-shutdown.sh',
                  'tests/quic-qns-endpoint-lifecycle.min',
                  'tests/interop/qns/endpoint.min'}
        tools = {'build/tooling/scripts/check-quic-official-inputs',
                 'build/tooling/tests/quic-official-inputs',
                 'build/tooling/tests/quic-official-adapter',
                 'build/tooling/tests/interop/qns/owned-adapter'}
        aggregates = ('check', 'check-portable', 'check-quic', 'check-quic-sanitize',
                      'check-quic-rfc', 'check-quic-rfc-sanitize', 'check-sanitize')

        def verify(candidate, host='Linux', operating_system='', ready=False):
            with tempfile.TemporaryDirectory(prefix='owned adapter Make rules ') as folder:
                directory = Path(folder).resolve()
                for name in inputs | {'runtime/native/sha256.c'}:
                    path = directory/name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes((ROOT/name).read_bytes())
                records = []
                if ready:
                    path = directory/'build/quic-interop-runner-740c05a.git/.ready.json'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('{"mock_ready_not_verification":true}\n')
                    records.append((path, path.read_bytes()))
                uname = directory/'uname'
                uname.write_text('#!/bin/sh\nprintf "%s\\n" "'+host+'"\n')
                uname.chmod(0o755)
                makefile = directory/'probe.mk'
                makefile.write_text('LIMITED := ordinary-limit\n'
                                    'SANITIZER_LIMITED := sanitizer-limit\n'
                                    +candidate+'\n.PHONY: build\nbuild:\n\t@echo INPUT build\n'
                                    'build/%:\n\t@echo TOOL $@\n')
                env = dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH'],
                           OS=operating_system)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(['make', '-rRnp', '-f', str(makefile), target],
                                        cwd=directory, env=env, capture_output=True,
                                        text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([\w./-]+):\s*(.*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                commands = dry_run_commands(result.stdout)
                supported = host == 'Linux' and operating_system != 'Windows_NT'
                for aggregate in aggregates:
                    if supported:
                        self.assertIn(target, rules.get(aggregate, set()), aggregate)
                    else:
                        self.assertNotIn(target, rules.get(aggregate, set()), aggregate)
                if not supported:
                    self.assertIn('Linux adapter controls required', commands)
                    self.assertIn('exit 2', commands)
                    self.assertNotIn('prepare-runner', commands)
                    self.assertNotIn('check-quic-official-inputs controls ', commands)
                    self.assertFalse(rules.get(target, set()))
                    return
                self.assertTrue(inputs <= rules.get(target, set()))
                self.assertTrue(tools <= rules.get(target, set()))
                self.assertNotIn('python', commands)
                controls = [line for line in commands.splitlines()
                            if ' ./build/tooling/scripts/check-quic-official-inputs controls ' in line]
                self.assertEqual(len(controls), 1)
                command = controls[0]
                self.assertIn('ordinary-limit ', command)
                self.assertNotIn('sanitizer-limit', command)
                self.assertIn('--repository "', command)
                self.assertIn('--artifacts "$artifacts/run"', command)
                self.assertIn('--controls "'+str(directory/'build/tooling/tests/quic-official-adapter')+'"', command)
                self.assertIn('--adapter "'+str(directory/'build/tooling/tests/interop/qns/owned-adapter')+'"', command)
                self.assertIn(str(directory/'build/quic-official-adapter.'), commands)
                self.assertIn(str(directory/'build/quic-interop-runner-740c05a.git'), command)
                checks = [line for line in commands.splitlines()
                          if 'ordinary-limit ./build/tooling/tests/quic-official-inputs' in line]
                self.assertEqual(len(checks), 1)
                for forbidden in ('--case ', '--sanitize', '/home/user/',
                                  'docker ', 'compose ', '--pull ', '--build '):
                    self.assertNotIn(forbidden, command)
                self.assertIn('mktemp -d "$(abspath build)', candidate)
                if ready:
                    self.assertNotIn('prepare-runner', commands)
                else:
                    self.assertIn('check-quic-official-inputs prepare-runner', commands)
                for path, data in records:
                    self.assertEqual(path.read_bytes(), data)

        verify(fragment)
        verify(fragment, ready=True)
        for host, operating_system in (('Darwin', ''), ('Linux', 'Windows_NT'),
                                      ('MSYS_NT-10.0', ''), ('MINGW64_NT-10.0', ''),
                                      ('CYGWIN_NT-10.0', '')):
            verify(fragment, host, operating_system)
        edge = next(line for line in fragment.splitlines()
                    if line.startswith('check check-portable '))
        names, dependency = edge.split(': ', 1)
        for aggregate in aggregates:
            mutant = fragment.replace(edge, ' '.join(
                name for name in names.split() if name != aggregate)+': '+dependency, 1)
            with self.subTest(missing_gate=aggregate), self.assertRaises(AssertionError):
                verify(mutant)
        for source in sorted(inputs):
            mutant = fragment.replace(source, '', 1)
            with self.subTest(missing_input=source), self.assertRaises(AssertionError):
                verify(mutant)
        for label, old, new in (
                ('case filter', 'controls --repository', 'controls --case criteria-no-pull --repository'),
                ('ordinary limiter omitted', '$(LIMITED) ./build/tooling/scripts/check-quic-official-inputs controls',
                 './build/tooling/scripts/check-quic-official-inputs controls'),
                ('wrong limiter', '$(LIMITED) ./build/tooling/scripts/check-quic-official-inputs controls',
                 '$(SANITIZER_LIMITED) ./build/tooling/scripts/check-quic-official-inputs controls'),
                ('private cache', '$(abspath build)/quic-interop-runner-740c05a.git',
                 '/home/user/private-runner'),
                ('relative artifacts', '$(abspath build)/quic-official-adapter.',
                 'build/quic-official-adapter.'),
                ('existing artifact leaf', '$$artifacts/run', '$$artifacts'),
                ('missing pin argument', 'controls --repository "$(QUIC_OFFICIAL_RUNNER)"', 'controls'),
                ('missing adapter binary', ' --adapter "$(abspath build/tooling/tests/interop/qns/owned-adapter)"', ''),
                ('missing verifier tests', '$(LIMITED) ./build/tooling/tests/quic-official-inputs; ', ''),
                ('missing dependency verification', 'check-quic-official-inputs controls',
                 'check-quic-official-inputs ignored')):
            mutant = fragment.replace(old, new, 1)
            self.assertNotEqual(mutant, fragment, label)
            with self.subTest(invalid_recipe=label), self.assertRaises(AssertionError):
                verify(mutant)
        targets = linux_targets()
        self.assertEqual(targets.count(target), 1)
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('build/linux-evidence/**/build/quic-official-adapter.*', workflow)
        # Linux uploads come from the runner's evidence; macOS and Windows from quic-native.
        self.assertEqual(workflow.count('            build/quic-official-adapter.*'), 1)
        driver = (ROOT/'tests/quic-official-adapter.min').read_text()

        def declared(name):
            start = driver.index('constant '+name+': List<Text> = [')
            return re.findall(r'"([a-z0-9-]+)"', driver[start:driver.index(']', start)])
        cases = declared('CASES')
        forwarding_cases = declared('FORWARD_CASES')
        self.assertEqual(forwarding_cases, ['raw-forward-incremental', 'raw-forward-stderr-status',
                                            'raw-forward-no-duplicate', 'raw-forward-empty',
                                            'raw-forward-private-json', 'raw-forward-backpressure'])
        self.assertEqual(len(cases), 113)
        self.assertEqual(len(set(cases)), 113)
        self.assertTrue(set(forwarding_cases) <= set(cases))
        original_cases = [case for case in cases if case not in forwarding_cases]
        self.assertEqual(len(original_cases), 107)
        self.assertEqual(len(set(original_cases)), 107)
        self.assertIn('    let cases = all\n    if selected.length > 0 { cases = selected }\n', driver)
        self.assertFalse(list(ROOT.glob('tests/interop/qns/*.py')))
        catalogue = native_catalogue()
        data = json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        rows = {row['path']: row for row in data['sources']}
        self.assertEqual(rows['tests/interop/qns/owned-adapter.c']['role'], 'support')
        self.assertIn('build-support/quic-official-adapter.mk',
                      rows['tests/interop/qns/owned-adapter.c']['consumers'])
        candidate = dict(data, sources=[row for row in data['sources']
                                       if row['path'] != 'tests/interop/qns/owned-adapter.c'])
        with self.subTest(omitted_source='tests/interop/qns/owned-adapter.c'), self.assertRaises(ValueError):
            catalogue.validate(candidate, ROOT)

    def test_os_tlsverify_sanitizer_selects_override_and_complete_directory(self):
        import json
        fragment = (ROOT / 'build-support/networking.mk').read_text()
        with tempfile.TemporaryDirectory(prefix='os sanitizer dispatch ') as temporary:
            directory = Path(temporary)
            binaries = directory / 'bin'
            binaries.mkdir()
            (directory / 'tools').symlink_to(ROOT / 'tools')
            python = binaries / 'python3'
            python.write_text('#!' + sys.executable + '\n' +
                'import json,os,sys\n'
                'os.execv(sys.executable,[sys.executable,*sys.argv[1:]])\n')
            python.chmod(0o755)
            converter = binaries / 'cygpath'
            converter.write_text('#!' + sys.executable + '\n' +
                'import json,os,sys\n'
                'assert len(sys.argv)==3 and sys.argv[1]=="-u",sys.argv\n'
                'print(json.loads(os.environ["OS_TLS_PROBE_TRANSLATIONS"])[sys.argv[2]])\n')
            converter.chmod(0o755)
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'])
            environment.pop('MAKEFLAGS', None)
            environment.pop('MINYAR_SANITIZER_CLANG', None)
            ordinary = str(directory / 'ordinary compiler/bin/clang')
            verifier = 'build/tooling/tests/os-tlsverify-test'
            native = directory / verifier
            native.parent.mkdir(parents=True)
            native.write_text('#!' + sys.executable + '\n' +
                'import json,os,sys\n'
                'print(json.dumps({"clang":os.environ.get("MINYAR_CLANG"),"path":os.environ["PATH"],'
                '"argv":["' + verifier + '",*sys.argv[1:]]}))\n')
            native.chmod(0o755)

            def verify(candidate, sanitizer, selected_compiler=None, selected_directory=None,
                       msys=False):
                self.assertIn('check-sanitize: check-os-tlsverify-sanitize', candidate)
                sanitizer_rule = next(line for line in candidate.splitlines()
                                      if line.startswith('check-os-tlsverify-sanitize:'))
                probe = directory / 'probe.mk'
                probe.write_text('LLVM_CC := ' + ordinary + '\n'
                    'MINYAR_SANITIZER_CLANG := ' + sanitizer + '\n'
                    'LIMITED :=\nSANITIZER_LIMITED :=\n' + candidate +
                    '\n.PHONY: build/minyarc\nbuild/minyarc:\n\t@:\n')
                selected_environment = environment.copy()
                if msys:
                    selected_environment.update(MINYAR_TEST_HOST_SYSTEM='MSYS_NT-10.0',
                        OS_TLS_PROBE_TRANSLATIONS=json.dumps({sanitizer: selected_compiler}))
                for target, expected_compiler, arguments in (
                        ('check-os-tlsverify', ordinary, []),
                        ('check-os-tlsverify-sanitize', selected_compiler or sanitizer or ordinary,
                         ['--sanitize'])):
                    result = subprocess.run(['make', '--no-print-directory', '-rR', '-s',
                        '-f', str(probe), target], cwd=directory, env=selected_environment,
                        capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    selected = json.loads(result.stdout)
                    self.assertEqual(selected['clang'], expected_compiler)
                    self.assertEqual(selected['argv'], [verifier, *arguments])
                    expected_path = environment['PATH']
                    if sanitizer and arguments:
                        expected_path = (selected_directory or str(Path(sanitizer).parent)) + os.pathsep + expected_path
                    self.assertEqual(selected['path'], expected_path)
                if sanitizer:
                    self.assertIn('tools/toolchain.sh', sanitizer_rule)

            for value in ('', str(directory / 'sanitizer/bin/clang'),
                          str(directory / 'LLVM 23/bin/clang'),
                          str(directory / "LLVM's 23/bin/clang")):
                with self.subTest(override=value):
                    verify(fragment, value)
            for native, selected, parent in (
                    ('C:/LLVM 23/bin/clang.exe', '/c/LLVM 23/bin/clang.exe', '/c/LLVM 23/bin'),
                    (r"C:\LLVM's 23\bin\clang.exe", "/c/LLVM's 23/bin/clang.exe", "/c/LLVM's 23/bin"),
                    (r'\\server\LLVM 23\bin\clang.exe', '//server/LLVM 23/bin/clang.exe', '//server/LLVM 23/bin')):
                with self.subTest(msys_native_spelling=native):
                    verify(fragment, native, selected, parent, msys=True)
            sanitizer_recipe = next(line for line in fragment.splitlines()
                                    if 'tests/os-tlsverify-test --sanitize' in line)
            for replacement in (
                    sanitizer_recipe.replace('$(OS_TLS_SANITIZER_CLANG)', '$(LLVM_CC)'),
                    sanitizer_recipe.replace('PATH="$(OS_TLS_SANITIZER_PATH)" ', '')):
                self.assertNotEqual(replacement, sanitizer_recipe)
                with self.assertRaises(AssertionError):
                    verify(fragment.replace(sanitizer_recipe, replacement, 1),
                           str(directory / 'LLVM 23/bin/clang'))
            path_rule = next(line for line in fragment.splitlines()
                             if line.startswith('OS_TLS_SANITIZER_PATH ='))
            for replacement in ('OS_TLS_SANITIZER_PATH = $(PATH)',
                    'OS_TLS_SANITIZER_PATH = /wrong/runtime:$(PATH)',
                    'OS_TLS_SANITIZER_PATH = $(dir $(MINYAR_SANITIZER_CLANG)):$(PATH)'):
                with self.assertRaises(AssertionError):
                    verify(fragment.replace(path_rule, replacement, 1),
                           str(directory / 'LLVM 23/bin/clang'))
            quote_rule = next(line for line in fragment.splitlines()
                              if line.startswith('OS_TLS_SANITIZER_QUOTE ='))
            sanitizer_rule = next(line for line in fragment.splitlines()
                                  if line.startswith('check-os-tlsverify-sanitize:'))
            for mutant in (
                    fragment.replace(quote_rule, 'OS_TLS_SANITIZER_QUOTE = $(1)', 1),
                    fragment.replace('check-sanitize: check-os-tlsverify-sanitize', '', 1),
                    fragment.replace(sanitizer_rule, sanitizer_rule.replace('tools/toolchain.sh', ''), 1)):
                with self.assertRaises(AssertionError):
                    verify(mutant, str(directory / "LLVM's 23/bin/clang"))

    def test_os_freestanding_provider_inputs_invalidate_object(self):
        fragment = (ROOT / 'os/Makefile').read_text()
        inputs = ('runtime/minyar_freestanding_providers.h', 'runtime/minyar_ip_literal.h',
                  'runtime/minyar_native.h', 'runtime/native/securecrypto.c',
                  'vendor/monocypher/monocypher.c', 'vendor/monocypher/monocypher.h')

        def verify(candidate):
            with tempfile.TemporaryDirectory(prefix='minyar-os-invalidation-') as temporary:
                directory = Path(temporary).resolve()
                (directory / 'os').mkdir()
                (directory / 'library').mkdir()
                (directory / 'os/Makefile').write_text(candidate)
                binaries = directory / 'llvm-bin'
                binaries.mkdir()
                clang = binaries / 'clang'
                clang.write_text('#!/bin/sh\nprintf "%s\\n" /unused-resource\n')
                clang.chmod(0o755)
                for name in (*inputs, 'runtime/freestanding/freestanding.c',
                             'runtime/freestanding/include/stdio.h'):
                    path = directory / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'bound input\n')
                    os.utime(path, (100, 100))
                environment = dict(os.environ)
                environment.pop('MAKEFLAGS', None)
                for architecture in ('x86_64', 'arm64'):
                    output = directory / 'build/os' / architecture / 'freestanding.o'
                    output.parent.mkdir(parents=True)
                    output.write_bytes(b'cached object\n')
                    os.utime(output, (200, 200))
                    argv = ['make', '--no-print-directory', '-q', '-C', str(directory / 'os'),
                            'LLVM_BIN=' + str(binaries), 'ARCH=' + architecture, str(output)]
                    def status():
                        result = subprocess.run(argv, env=environment, capture_output=True,
                                                text=True, timeout=15)
                        self.assertIn(result.returncode, (0, 1), result.stderr)
                        return result.returncode
                    self.assertEqual(status(), 0, 'Unchanged inputs must reuse the object')
                    for name in inputs:
                        path = directory / name
                        os.utime(path, (300, 300))
                        self.assertEqual(status(), 1, (architecture, name, 'stale provider object'))
                        os.utime(path, (100, 100))
                        self.assertEqual(status(), 0, (architecture, name, 'restored input'))
        verify(fragment)
        for name in inputs:
            self.assertIn('$(ROOT)/' + name, fragment)
            with self.subTest(missing_dependency=name), self.assertRaises(AssertionError):
                verify(fragment.replace('$(ROOT)/' + name, '', 1))


    def test_relay_wrong_key_changes_decoded_signature_even_with_aa_tail(self):
        result = subprocess.run([str(ROOT / 'build/tooling/tests/peer-edge-relay-test'), '--signature-controls'],
                                cwd=ROOT, text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('GREEN wrong-key control changes every decoded signature, including AA tails', result.stdout)
    def test_network_sanitizers_select_override_and_complete_directory(self):
        import json
        fragment = (ROOT / 'build-support/networking.mk').read_text()
        with tempfile.TemporaryDirectory(prefix='network sanitizer dispatch ') as temporary:
            directory = Path(temporary)
            binaries = directory / 'bin'
            binaries.mkdir()
            python = binaries / 'python3'
            python.write_text('#!' + sys.executable + '\n' +
                'import json,os,sys\n'
                'os.execv(sys.executable,[sys.executable,*sys.argv[1:]])\n')
            python.chmod(0o755)
            converter = binaries / 'cygpath'
            converter.write_text('#!' + sys.executable + '\n' +
                'import json,os,sys\n'
                'assert len(sys.argv)==3 and sys.argv[1]=="-u",sys.argv\n'
                'print(json.loads(os.environ["NET_PROBE_TRANSLATIONS"])[sys.argv[2]])\n')
            converter.chmod(0o755)
            for name, limit in (('ordinary-limit', 'ordinary'), ('sanitizer-limit', 'sanitizer')):
                launcher = binaries / name
                launcher.write_text('#!/bin/sh\nNET_PROBE_LIMIT=' + limit + ' exec "$@"\n')
                launcher.chmod(0o755)
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'])
            for name in ('MAKEFLAGS', 'MINYAR_SANITIZER_CLANG', 'MINYAR_CLANG', 'MINYAR_TEST_CLANG'):
                environment.pop(name, None)
            ordinary = str(directory / 'ordinary UCRT compiler/bin/clang')
            connect = 'build/tooling/tests/net-connect-test'
            offload = 'build/tooling/tests/net-udp-offload-test'
            (directory / 'tools').symlink_to(ROOT / 'tools')
            for tool, key in ((connect, 'MINYAR_CLANG'), (offload, 'MINYAR_TEST_CLANG')):
                native = directory / tool
                native.parent.mkdir(parents=True, exist_ok=True)
                native.write_text('#!' + sys.executable + '\n' +
                    'import json,os,sys\n'
                    'print(json.dumps({"clang":os.environ.get("' + key + '"),"path":os.environ["PATH"],'
                    '"limit":os.environ.get("NET_PROBE_LIMIT"),"argv":["' + tool + '",*sys.argv[1:]]}))\n')
                native.chmod(0o755)
            targets = (
                ('check-net-connect', connect, [], {'build/minyarc'}),
                ('check-net-connect-sanitize', connect, ['--sanitize'], {'build/minyarc'}),
                ('check-net-udp-offload', offload,
                 ['--evidence', 'build/net-udp-offload'], {'build/minyarc', 'build/minyar-default-runtime.o'}),
                ('check-net-udp-offload-sanitize', offload,
                 ['--sanitize', '--evidence', 'build/net-udp-offload-sanitize'],
                 {'build/minyarc', 'build/minyar-default-runtime.o'}))

            def verify(candidate, sanitizer='', selected_compiler=None, selected_directory=None,
                       msys=False):
                probe = directory / 'probe.mk'
                probe.write_text('LLVM_CC := ' + ordinary + '\n'
                    'MINYAR_SANITIZER_CLANG := ' + sanitizer + '\n'
                    'LIMITED := ordinary-limit\nSANITIZER_LIMITED := sanitizer-limit\n' + candidate +
                    '\n.PHONY: build/minyarc build/minyar-default-runtime.o\n'
                    'build/minyarc build/minyar-default-runtime.o:\n'
                    '\t@NET_PROBE_INPUT=$@ LLVM_CC="$(LLVM_CC)" python3 -c '
                    "'import json,os;print(json.dumps({\"input\":os.environ[\"NET_PROBE_INPUT\"],"
                    "\"clang\":os.environ[\"LLVM_CC\"],\"path\":os.environ[\"PATH\"]}))'\n")
                selected_environment = environment.copy()
                if msys:
                    selected_environment.update(MINYAR_TEST_HOST_SYSTEM='MSYS_NT-10.0',
                        NET_PROBE_TRANSLATIONS=json.dumps({sanitizer: selected_compiler}))
                for target, script, arguments, prerequisites in targets:
                    result = subprocess.run(['make', '--no-print-directory', '-j1', '-rR', '-s',
                        '-f', str(probe), target], cwd=directory, env=selected_environment,
                        capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, (target, result.stderr))
                    records = [json.loads(line) for line in result.stdout.splitlines()]
                    inputs, selected = records[:-1], records[-1]
                    self.assertEqual({row['input'] for row in inputs}, prerequisites, target)
                    for row in inputs:
                        self.assertEqual(row['clang'], ordinary, (target, row))
                        self.assertEqual(row['path'], environment['PATH'], (target, row))
                    sanitize = '--sanitize' in arguments
                    expected_compiler = (selected_compiler or sanitizer or ordinary) if sanitize else ordinary
                    expected_path = environment['PATH']
                    if sanitizer and sanitize:
                        expected_path = selected_directory + os.pathsep + expected_path
                    self.assertEqual(selected['clang'], expected_compiler, (target, selected))
                    self.assertEqual(selected['path'], expected_path, (target, selected))
                    self.assertEqual(selected['limit'], 'sanitizer' if sanitize else 'ordinary', target)
                    self.assertEqual(selected['argv'], [script, *arguments], target)
                    rule = next(line for line in candidate.splitlines() if line.startswith(target + ':'))
                    if sanitizer or not sanitize:
                        self.assertEqual(set(rule.split(':', 1)[1].split()), prerequisites |
                                         ({'tools/toolchain.sh'} if sanitize else set()) |
                                         {script}, target)

            # Expected spellings and complete parents are independent of the Make selector.
            verify(fragment)
            for compiler, parent in (
                    ('/clang64/bin/clang.exe', '/clang64/bin'),
                    ('/opt/LLVM 23/bin/clang.exe', '/opt/LLVM 23/bin'),
                    ("/opt/LLVM's 23/bin/clang.exe", "/opt/LLVM's 23/bin")):
                verify(fragment, compiler, selected_directory=parent)
            for native, selected, parent in (
                    ('C:/LLVM 23/bin/clang.exe', '/c/LLVM 23/bin/clang.exe', '/c/LLVM 23/bin'),
                    (r"C:\LLVM's 23\bin\clang.exe", "/c/LLVM's 23/bin/clang.exe", "/c/LLVM's 23/bin"),
                    (r'\\server\LLVM 23\bin\clang.exe', '//server/LLVM 23/bin/clang.exe', '//server/LLVM 23/bin')):
                verify(fragment, native, selected, parent, msys=True)
            compiler, parent = '/opt/LLVM 23/bin/clang.exe', '/opt/LLVM 23/bin'
            mutants = []
            for target, script, arguments, _ in targets:
                if '--sanitize' not in arguments:
                    continue
                recipe = next(line for line in fragment.splitlines() if script in line and '--sanitize' in line)
                rule = next(line for line in fragment.splitlines() if line.startswith(target + ':'))
                mutants.extend((
                    (recipe, recipe.replace('$(NET_SANITIZER_CLANG)', '$(LLVM_CC)')),
                    (recipe, recipe.replace('$(NET_SANITIZER_CLANG)', '/wrong/compiler')),
                    (recipe, recipe.replace(('MINYAR_CLANG' if script == connect
                        else 'MINYAR_TEST_CLANG') + '=$(call NET_SANITIZER_QUOTE,$(NET_SANITIZER_CLANG)) ', '')),
                    (recipe, recipe.replace('PATH="$(NET_SANITIZER_PATH)" ', '')),
                    (rule, rule.replace(' tools/toolchain.sh', ''))))
            clang_rule = next(line for line in fragment.splitlines() if line.startswith('NET_SANITIZER_CLANG ='))
            path_rule = next(line for line in fragment.splitlines() if line.startswith('NET_SANITIZER_PATH ='))
            mutants.extend((
                (clang_rule, 'NET_SANITIZER_CLANG = $(LLVM_CC)'),
                (path_rule, 'NET_SANITIZER_PATH = $(PATH)'),
                (path_rule, 'NET_SANITIZER_PATH = /wrong/runtime:$(PATH)'),
                (path_rule, 'NET_SANITIZER_PATH = $(dir $(MINYAR_SANITIZER_CLANG)):$(PATH)'),
                ('NET_SANITIZER_QUOTE =', 'NET_SANITIZER_QUOTE = $(1) #')))
            for old, new in mutants:
                mutant = fragment.replace(old, new, 1)
                self.assertNotEqual(mutant, fragment)
                with self.subTest(dispatch=old, replacement=new), self.assertRaises(AssertionError):
                    verify(mutant, compiler, selected_directory=parent)
            for assignment in ('LLVM_CC = $(NET_SANITIZER_CLANG)', 'PATH := /wrong/native:$(PATH)'):
                with self.subTest(global_dispatch=assignment), self.assertRaises(AssertionError):
                    verify(fragment + '\n' + assignment + '\n', compiler, selected_directory=parent)


if __name__ == '__main__':
    unittest.main()
