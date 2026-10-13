#!/usr/bin/env python3
"""Probe actual Make prerequisites under POSIX and native Windows host names."""
import ast
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
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



def literal(path, name):
    """A module-level literal assignment, read without importing the module."""
    tree = ast.parse((ROOT / path).read_text())
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))


def assert_ci_runs_quic_group(test, *targets):
    """CI gates these targets through the runner's QUIC group, run by a linux-matrix shard."""
    quic = literal('scripts/check-linux.py', 'QUIC_TARGETS')
    workflow = (ROOT / '.github/workflows/ci.yml').read_text()
    test.assertIn('python3 scripts/check-linux.py', workflow)
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
                '.PHONY: build\nbuild:\n\t@:\n')
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
                           'tests/managed-graphs-profiles.py', 'runtime/minyar_runtime.c'):
                self.assertIn(source, rules.get(target, set()))
            commands = dry_run_commands(result.stdout)
            selected = [line for line in commands.splitlines()
                        if 'python3 tests/managed-graphs-profiles.py' in line]
            self.assertEqual(selected, [
                'MINYAR_TEST_CLANG="retained-clang" sanitizer-limit python3 '
                'tests/managed-graphs-profiles.py --quick --fixture managed-graphs-bakeoff.c'])




    def test_event_loop_native_and_sanitizer_keep_distinct_limits(self):
        import argparse
        import contextlib
        import importlib.util
        import io
        import json
        fragment = (ROOT/'build-support/networking.mk').read_text()
        def verify(candidate, host='Linux', operating_system=''):
            with tempfile.TemporaryDirectory(prefix='loop limits Make rules ') as folder:
                directory = Path(folder)
                uname = directory/'uname';uname.write_text(
                    '#!/bin/sh\nprintf "%s\\n" "'+host+'"\n');uname.chmod(0o755)
                makefile = directory/'probe.mk'
                makefile.write_text('LLVM_CC := retained-clang\nLIMITED := ordinary-limit\n'
                    'SANITIZER_LIMITED := sanitizer-limit\n'+candidate
                    +'\n.PHONY: build/minyarc\nbuild/minyarc:\n\t@echo INPUT $@\n')
                env = dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH'],
                           OS=operating_system);env.pop('MAKEFLAGS',None)
                result = subprocess.run(['make','-rRn','-f',str(makefile),'check-net-loop'],
                    cwd=ROOT,env=env,capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr)
                commands=[line for line in result.stdout.splitlines()
                          if 'python3 tests/net-loop.py' in line]
                windows=operating_system=='Windows_NT' or host.startswith(('MSYS','MINGW','CYGWIN'))
                self.assertEqual(len(commands),1 if windows else 2)
                native=next(line for line in commands if '--mode native' in line)
                self.assertIn('ordinary-limit python3 tests/net-loop.py --mode native',native)
                self.assertNotIn('sanitizer-limit',native)
                self.assertIn('--evidence "$evidence"',native)
                self.assertIn(str(ROOT/'build/net-loop.'),native.replace('\\','/'))
                if not windows:
                    sanitize=next(line for line in commands if '--mode sanitize' in line)
                    self.assertIn('sanitizer-limit python3 tests/net-loop.py --mode sanitize',sanitize)
                    self.assertNotIn('ordinary-limit',sanitize)
                    self.assertIn('--evidence "$evidence"',sanitize)
                    self.assertIn(str(ROOT/'build/net-loop-sanitize.'),sanitize.replace('\\','/'))
        verify(fragment)
        for host, operating_system in (('Darwin',''),('Linux','Windows_NT'),
                ('MSYS_NT-10.0',''),('MINGW64_NT-10.0',''),('CYGWIN_NT-10.0','')):
            verify(fragment,host,operating_system)
        native=next(line for line in fragment.splitlines() if 'tests/net-loop.py --mode native' in line)
        sanitize=next(line for line in fragment.splitlines() if 'tests/net-loop.py --mode sanitize' in line)
        for old,new in ((native,''),(sanitize,''),
                (native,native.replace('$(LIMITED)','$(SANITIZER_LIMITED)')),
                (sanitize,sanitize.replace('$(SANITIZER_LIMITED)','$(LIMITED)')),
                (native,native.replace(' --mode native','')),
                (sanitize,sanitize.replace(' --mode sanitize',''))):
            mutant=fragment.replace(old,new,1);self.assertNotEqual(mutant,fragment)
            with self.assertRaises((AssertionError,StopIteration)):verify(mutant)

        spec=importlib.util.spec_from_file_location('loop_mode_contract',ROOT/'tests/net-loop.py')
        driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        definition=next(n for n in ast.parse((ROOT/'tests/net-loop.py').read_text()).body
                        if isinstance(n,ast.FunctionDef) and n.name=='selected_modes')
        source=ast.get_source_segment((ROOT/'tests/net-loop.py').read_text(),definition)
        def verify_modes(candidate):
            for windows,mode,expected in (
                    (False,None,['native','sanitize','app-native','app-sanitize']),
                    (False,'native',['native','app-native']),
                    (False,'sanitize',['sanitize','app-sanitize']),
                    (True,None,['native']),(True,'native',['native'])):
                scope={'WINDOWS':windows};exec(candidate,scope)
                self.assertEqual(scope['selected_modes'](argparse.ArgumentParser(),mode),expected)
            scope={'WINDOWS':True};exec(candidate,scope)
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
                scope['selected_modes'](argparse.ArgumentParser(),'sanitize')
            self.assertEqual(error.exception.code,2)
        verify_modes(source)
        for old,new in (("['native', 'app-native']","['native']"),
                        ("['sanitize', 'app-sanitize']","['sanitize']"),
                        ("['native', 'sanitize', 'app-native', 'app-sanitize']",
                         "['native', 'app-native', 'sanitize', 'app-sanitize']")):
            mutant=source.replace(old,new,1);self.assertNotEqual(mutant,source)
            with self.assertRaises(AssertionError):verify_modes(mutant)
        def verify_inputs(candidate):
            main=next(n for n in ast.parse(candidate).body
                      if isinstance(n,ast.FunctionDef) and n.name=='main')
            sources=next(n.value for n in ast.walk(main) if isinstance(n,ast.Assign)
                         and any(isinstance(target,ast.Name) and target.id=='sources'
                                 for target in n.targets))
            bound={n.right.value for n in sources.elts if isinstance(n,ast.BinOp)
                   and isinstance(n.left,ast.Name) and n.left.id=='ROOT'
                   and isinstance(n.right,ast.Constant)}
            self.assertIn('tests/network_evidence.py',bound)
            self.assertIn('runtime/native/net.c',bound)
        loop_source=(ROOT/'tests/net-loop.py').read_text()
        verify_inputs(loop_source)
        for name in ('tests/network_evidence.py','runtime/native/net.c'):
            old="ROOT/"+repr(name)+","
            mutant=loop_source.replace(old,'',1);self.assertNotEqual(mutant,loop_source)
            with self.assertRaises(AssertionError):verify_inputs(mutant)
        spec=importlib.util.spec_from_file_location('loop_catalogue',ROOT/'tests/suite-catalogue.py')
        catalogue=importlib.util.module_from_spec(spec);spec.loader.exec_module(catalogue)
        data=json.loads((ROOT/'tests/suite-catalogue.json').read_text());catalogue.validate(data,ROOT)
        helper=next(row for row in data['sources'] if row['path']=='tests/network_evidence.py')
        self.assertEqual(helper['role'],'support')
        self.assertEqual(set(helper['consumers']),{'tests/net-native.py','tests/net-loop.py'})
        with self.assertRaises(ValueError):
            catalogue.validate(dict(data,sources=[row for row in data['sources']
                if row['path']!='tests/network_evidence.py']),ROOT)

    def test_network_evidence_preserves_primary_and_finalizes_independently(self):
        import contextlib
        import importlib.util
        import io
        import json
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location(
            'network_evidence_contract', ROOT/'tests/net-native.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        real_write_bytes = Path.write_bytes
        real_write_text = Path.write_text
        with tempfile.TemporaryDirectory(prefix='network evidence controls ') as folder:
            directory = Path(folder)
            records, errors = [], []
            attempted = []
            def one_shot_stream(path, data):
                attempted.append(path.name)
                if path.name.endswith('.stdout') and attempted.count(path.name) == 1:
                    raise OSError('sentinel stream write failure')
                return real_write_bytes(path, data)
            provider = subprocess.CompletedProcess([sys.executable], 37,
                                                   b'provider stdout', b'provider stderr')
            with patch.object(driver.subprocess, 'run', return_value=provider), patch.object(
                    Path, 'write_bytes', one_shot_stream), self.assertRaises(
                        subprocess.CalledProcessError) as failed:
                driver.captured_run(directory, records, errors, [sys.executable],
                                    phase='provider', check=True, capture_output=True)
            self.assertEqual(failed.exception.returncode, 37)
            self.assertEqual((directory/'01-provider.stderr').read_bytes(), b'provider stderr')
            self.assertIn('01-provider.stdout', attempted)
            self.assertIn('01-provider.stderr', attempted)
            manifest_attempts = []
            def one_shot_manifest(path, data, *args, **kwargs):
                manifest_attempts.append(path.name)
                if path.name == 'manifest.json' and manifest_attempts.count(path.name) == 1:
                    raise OSError('sentinel manifest write failure')
                return real_write_text(path, data, *args, **kwargs)
            with patch.object(Path, 'write_text', one_shot_manifest), contextlib.redirect_stderr(
                    io.StringIO()) as raw:
                driver.finalize_evidence(directory, {}, records, errors, ['native'],
                                         'failed', failed.exception)
            self.assertEqual(manifest_attempts, ['manifest.json'])
            self.assertIn('sentinel stream write failure', raw.getvalue())
            self.assertIn('sentinel manifest write failure', raw.getvalue())
            self.assertEqual(records[0]['status'], 37)
            self.assertTrue(any(row['operation'] == 'manifest write' for row in errors))
        with tempfile.TemporaryDirectory(prefix='network tool mutation ') as folder:
            directory = Path(folder)
            tool = directory/'owned-tool'
            tool.write_bytes(b'original')
            records, errors = [], []
            def mutate_tool(*args, **kwargs):
                tool.write_bytes(b'changed')
                return subprocess.CompletedProcess([str(tool)], 0, b'', b'')
            with patch.object(driver.subprocess, 'run', side_effect=mutate_tool), self.assertRaises(
                    RuntimeError):
                driver.captured_run(directory, records, errors, [tool], phase='binding',
                                    check=True, capture_output=True)
            self.assertTrue(any(row['operation'] == 'tool binding' for row in errors))
        with tempfile.TemporaryDirectory(prefix='network source mutation ') as folder:
            directory = Path(folder)
            source = directory/'owned-source'
            source.write_bytes(b'original')
            inputs = {'owned-source': driver.digest(source)}
            source.write_bytes(b'changed')
            errors = []
            with patch.object(driver, 'ROOT', directory), contextlib.redirect_stderr(
                    io.StringIO()), self.assertRaises(RuntimeError):
                driver.finalize_evidence(directory, inputs, [], errors, ['native'], 'passed')
            manifest = json.loads((directory/'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'failed')
            self.assertTrue(any(row['operation'] == 'input binding' for row in errors))


        for modes, expected_scope in (
                (['native'], 'ordinary-launcher-path'),
                (['native', 'sanitize'], 'ordinary-launcher-path'),
                (['sanitize'], None)):
            with tempfile.TemporaryDirectory(prefix='network public scope ') as folder:
                directory = Path(folder)
                driver.finalize_evidence(directory, {}, [], [], modes, 'passed')
                manifest = json.loads((directory/'manifest.json').read_text())
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
                    + '\n.PHONY: build/minyarc\nbuild/minyarc:\n\t@echo INPUT $@\n')
                env = dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH'],
                           OS=operating_system)
                env.pop('MAKEFLAGS', None)
                result = subprocess.run(
                    ['make', '-rRn', '-f', str(makefile), 'check-net'],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                commands = [line for line in result.stdout.splitlines()
                            if 'python3 tests/net-native.py' in line]
                windows = operating_system == 'Windows_NT' or host.startswith(
                    ('MSYS', 'MINGW', 'CYGWIN'))
                self.assertEqual(len(commands), 1 if windows else 2)
                native = next(line for line in commands if '--mode native' in line)
                self.assertIn('ordinary-limit python3 tests/net-native.py --mode native', native)
                self.assertNotIn('sanitizer-limit', native)
                self.assertIn('MINYAR_TEST_CLANG="retained-clang"', native)
                self.assertIn('--evidence "$evidence"', native)
                self.assertIn(str(ROOT/'build/net-native.'), native.replace('\\', '/'))
                if not windows:
                    sanitize = next(line for line in commands if '--mode sanitize' in line)
                    self.assertIn('sanitizer-limit python3 tests/net-native.py --mode sanitize',
                                  sanitize)
                    self.assertNotIn('ordinary-limit', sanitize)
                    self.assertIn('MINYAR_TEST_CLANG="retained-clang"', sanitize)
                    self.assertIn('--evidence "$evidence"', sanitize)
                    self.assertIn(str(ROOT/'build/net-native-sanitize.'),
                                  sanitize.replace('\\', '/'))
                self.assertEqual(result.stdout.count('python3 tests/soak-observer-test.py'), 1)

        verify(fragment)
        for host, operating_system in (
                ('Darwin', ''), ('Linux', 'Windows_NT'), ('MSYS_NT-10.0', ''),
                ('MINGW64_NT-10.0', ''), ('CYGWIN_NT-10.0', '')):
            with self.subTest(host=host, operating_system=operating_system):
                verify(fragment, host, operating_system)
        native = next(line for line in fragment.splitlines()
                      if 'tests/net-native.py --mode native' in line)
        sanitize = next(line for line in fragment.splitlines()
                        if 'tests/net-native.py --mode sanitize' in line)
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


        import argparse
        import contextlib
        import importlib.util
        import io
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location(
            'network_native_mode_contract', ROOT/'tests/net-native.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        parser = argparse.ArgumentParser()
        for windows, mode, expected in (
                (False, None, ['native', 'sanitize']),
                (False, 'native', ['native']), (False, 'sanitize', ['sanitize']),
                (True, None, ['native']), (True, 'native', ['native'])):
            with self.subTest(windows=windows, mode=mode), patch.object(
                    driver, 'WINDOWS', windows):
                self.assertEqual(driver.selected_modes(parser, mode), expected)
        with patch.object(driver, 'WINDOWS', True), contextlib.redirect_stderr(
                io.StringIO()) as error, self.assertRaises(SystemExit) as rejected:
            driver.selected_modes(parser, 'sanitize')
        self.assertEqual(rejected.exception.code, 2)
        self.assertIn('unavailable on Windows', error.getvalue())

    def test_cycle_progress_observability_is_mandatory_without_idle_replay(self):
        import importlib.util
        import json
        import re

        target = 'check-cycle-progress-observability'
        aggregates = {'check', 'check-portable', 'check-sanitize',
                      'check-managed-graphs-profiles', 'check-cycle-progress',
                      'check-cycle-progress-sanitize'}
        inputs = {'tests/cycle-progress-observability.py',
                  'tests/cycle-progress-observability-harness.py', 'tests/cycle-progress.c',
                  'tests/fixtures/cycle-progress-before-observability.c.txt',
                  'tests/clang_helpers.py', 'tests/test_evidence.py',
                  'tests/windows_job_owner.py', 'tools/host_paths.py'}
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
                self.assertEqual(commands.count('python3 tests/cycle-progress-observability.py'), 1)
                self.assertEqual(commands.count('python3 tests/cycle-progress-observability-harness.py'), 1)
                self.assertIn('MINYAR_TEST_CLANG="retained-clang"', commands)
                self.assertIn('retained-limited python3', commands)
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
                ('runtime replay', 'python3 tests/cycle-progress-observability.py',
                 'python3 tests/cycle-progress.py')):
            mutant = fragment.replace(old, new, 1)
            self.assertNotEqual(fragment, mutant)
            with self.subTest(invalid_recipe=name), self.assertRaises(AssertionError):
                verify(mutant)

        tree = ast.parse((ROOT/'scripts/check-linux.py').read_text())
        targets = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(name, ast.Name) and name.id == 'TARGETS'
                               for name in node.targets))
        self.assertEqual(targets.count(target), 1)
        spec = importlib.util.spec_from_file_location(
            'idle_observability_catalogue', ROOT/'tests/suite-catalogue.py')
        catalogue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalogue)
        data = json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for name in sorted(name for name in inputs if name.startswith('tests/')):
            self.assertIn(name, catalogue.discover(ROOT))
            with self.subTest(omitted_source=name), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[row for row in data['sources']
                                                       if row['path'] != name]), ROOT)
        row = next(row for row in data['sources']
                   if row['path'] == 'tests/cycle-progress-observability.py')
        self.assertEqual(row['role'], 'suite')
        self.assertIn('build-support/managed-graphs.mk', row['consumers'])
        historical = next(row for row in data['sources']
                          if row['path'] == 'tests/fixtures/cycle-progress-before-observability.c.txt')
        self.assertEqual(historical['role'], 'fixture')
        self.assertEqual(historical['consumers'], ['tests/cycle-progress-observability.py'])


    def test_quic_ledger_requires_full_offline_controls(self):
        import importlib.util
        import json
        import re
        fragment_path = ROOT / 'build-support/quic-ledger.mk'
        source = fragment_path.read_text()
        target = 'check-quic-amplification-ledger'
        inputs = {'tests/quic-amplification-ledger.py',
                  'tests/quic_amplification_ledger.py'}

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
                self.assertEqual(commands.count('python3 -E tests/quic-amplification-ledger.py'), 1)
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
                ('relative artifact path', '$(abspath build)/quic-ledger.', 'build/quic-ledger.'),
                ('inherited optimization', 'python3 -E ', 'python3 -O ')):
            mutant = source.replace(old, new, 1)
            self.assertNotEqual(mutant, source)
            with self.subTest(invalid_recipe=label), self.assertRaises(AssertionError):
                verify(mutant)
        tree = ast.parse((ROOT / 'scripts/check-linux.py').read_text())
        targets = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(name, ast.Name) and name.id == 'TARGETS'
                               for name in node.targets))
        self.assertEqual(targets.count(target), 1)
        spec = importlib.util.spec_from_file_location('ledger_catalogue',
                                                     ROOT / 'tests/suite-catalogue.py')
        catalogue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalogue)
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        rows = {row['path']: row for row in data['sources']}
        self.assertEqual(rows['tests/quic-amplification-ledger.py']['role'], 'suite')
        self.assertIn('build-support/quic-ledger.mk',
                      rows['tests/quic-amplification-ledger.py']['consumers'])
        self.assertEqual(rows['tests/quic_amplification_ledger.py']['role'], 'support')
        self.assertIn('tests/quic-amplification-ledger.py',
                      rows['tests/quic_amplification_ledger.py']['consumers'])
        for missing in sorted(inputs):
            candidate = dict(data, sources=[row for row in data['sources']
                                           if row['path'] != missing])
            with self.subTest(omitted_source=missing), self.assertRaises(ValueError):
                catalogue.validate(candidate, ROOT)

    def test_quic_rfc_requires_owned_lifecycle_controls(self):
        import json
        import re
        source=(ROOT/'build-support/quic-rfc.mk').read_text()
        helper='check-quic-protocol-artifacts'
        inputs={'tests/quic-protocol-artifacts.py','tests/quic_protocol_artifacts.py',
                'tests/quic-qns-local.py','tests/quic-vn-probe.py','tests/test_evidence.py',
                'tests/clang_helpers.py','tests/tls-local.py','tests/interop/qns/endpoint.py'}
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
                self.assertEqual(commands.count('python3 tests/quic-protocol-artifacts.py'),1)
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
                ('old code oracle','tests/quic-protocol-artifacts.py --artifacts',
                    'tests/quic-protocol-artifacts.py --expect-old-code --artifacts'),
                ('filtered control','tests/quic-protocol-artifacts.py --artifacts',
                    'tests/quic-protocol-artifacts.py --case healthy-shutdown --artifacts'),
                ('relative evidence','$(abspath build)/quic-protocol-artifacts.',
                    'build/quic-protocol-artifacts.')):
            mutant=source.replace(old,new,1)
            self.assertNotEqual(source,mutant)
            with self.subTest(invalid_helper=name),self.assertRaises(AssertionError):verify(mutant)
        catalogue=json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        row=next(row for row in catalogue['sources'] if row['path']=='tests/quic-protocol-artifacts.py')
        self.assertEqual(row['role'],'suite')
        self.assertIn('build-support/quic-rfc.mk',row['consumers'])

    def test_quic_rfc_gates_keep_all_drivers_and_public_frontends(self):
        import importlib.util
        import json
        import re
        source = (ROOT / 'build-support/quic-rfc.mk').read_text()
        native, sanitize = 'check-quic-rfc', 'check-quic-rfc-sanitize'
        frontends = {'build/minyarc', 'build/minyarc-callbacks',
                     'build/minyarc-errors-request', 'build/minyarc-errors'}
        inputs = {'minyar', 'tools/clang-driver.py', 'tools/sanitizer_llvm.py',
                  'tests/quic-rfc.py', 'tests/quic-rfc-harness.py',
                  'tests/test_evidence.py', 'tests/clang_helpers.py',
                  'tests/tls-local.py', 'tests/quic_protocol_artifacts.py', 'tests/quic-protocol-artifacts.py',
                  'tests/interop/qns/endpoint.py', 'library/quic.min', 'library/tls.min',
                  'library/tlsserver.min', 'tests/quic-migration-cids.py',
                  'tests/quic-migration-cids.min', 'tests/quic-cipher-policy.py',
                  'tests/quic-cipher-policy.min', 'tests/quic-qns-local.py',
                  'tests/quic-vn-probe.py', 'tests/interop/qns/client.min',
                  'tests/interop/qns/server.min'}

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='QUIC RFC Make rules ') as folder:
                makefile = Path(folder) / 'probe.mk'
                fixtures = sorted(frontends | inputs | {'build'})
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
                self.assertEqual(commands.count('python3 tests/quic-rfc.py'), 2)
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
        tree = ast.parse((ROOT/'scripts/check-linux.py').read_text())
        targets = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'TARGETS'
                               for target in node.targets))
        for target in (native, sanitize):
            self.assertEqual(targets.count(target), 1)
        assert_ci_runs_quic_group(self, 'check-quic', 'check-quic-sanitize')
        format_tree = ast.parse((ROOT/'scripts/format.py').read_text())
        version = next(ast.literal_eval(node.value) for node in format_tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'VERSION'
                               for target in node.targets))
        self.assertEqual(version, '23.1.2')
        spec = importlib.util.spec_from_file_location(
            'quic_rfc_catalogue', ROOT/'tests/suite-catalogue.py')
        catalogue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalogue)
        data = json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for name in sorted(inputs - {'minyar', 'tools/clang-driver.py',
                                     'tools/sanitizer_llvm.py', 'library/quic.min',
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
        expected = {'build/minyarc', 'tests/generated-llvm-sanitizer.py',
                    'tests/generated-llvm-sanitizer.min', 'tests/llvm_sanitizer.py',
                    'tools/sanitizer_llvm.py', 'tools/clang-driver.py'}

        def verify(candidate, sanitizer=None, selected=None, directory='/clang64/bin'):
            with tempfile.TemporaryDirectory(prefix='actual sanitizer Make rules ') as folder:
                probe = Path(folder)/'probe.mk'
                probe.write_text('LLVM_CC := retained-native-clang\n'
                                 'SANITIZER_LIMITED := sanitizer-limit\n'
                                 'PATH := /retained/native/bin:/usr/bin\n'
                                 'MINYAR_SANITIZER_CLANG := ' + (sanitizer or '') + '\n'
                                 + candidate + '\n.PHONY: build build/minyarc build/yamux-peer\n'
                                 'build build/minyarc build/yamux-peer:\n')
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
                self.assertIn('python3 tests/generated-llvm-sanitizer.py', commands)
                command = next(line for line in commands.splitlines()
                               if 'python3 tests/generated-llvm-sanitizer.py' in line)
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
        rules = re.findall(r'^build/[^:\n]*sanitize\.ll:([^\n]*)',compiler,re.M)
        self.assertEqual(len(rules),1)
        self.assertTrue(all('tests/llvm_sanitizer.py' in r and 'tools/sanitizer_llvm.py' in r for r in rules))
        shim = (ROOT/'tests/llvm_sanitizer.py').read_text()
        self.assertIn('from sanitizer_llvm import',shim)
        self.assertNotIn('def instrument_address_sanitizer',shim)
        loader = {}
        exec(compile((ROOT/'scripts/check-linux.py').read_text(), 'linux driver','exec'),
             {'__name__':'static_linux_driver','__file__':str(ROOT/'scripts/check-linux.py')},loader)
        self.assertEqual(loader['TARGETS'].count('check-generated-llvm-sanitizer'),1)

    def test_private_retirement_gates_execute_actual_operation_contract(self):
        import importlib.util
        import json
        import re
        source = (ROOT/'build-support/managed-graphs.mk').read_text()
        marker = '# Every C command takes N OPERATION [ARGS]'
        self.assertIn(marker,source)
        fragment = source[source.index(marker):]
        pair = {'check-cycle-private-retirement','check-cycle-private-retirement-sanitize'}
        inputs = {'tests/cycle-private-retirement.py','tests/cycle-idle-invalidation.c',
                  'tests/cycle-private-retirement-v5.json','tests/cycle-additive.c',
                  'tests/cycle-additive.py','tests/test_evidence.py','tools/cycle_runtime.py'}

        def verify(candidate):
            with tempfile.TemporaryDirectory(prefix='actual private retirement Make rules ') as folder:
                probe=Path(folder)/'probe.mk'
                probe.write_text(candidate+'\nbuild:\n')
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
                    self.assertEqual(commands.count('python3 tests/cycle-private-retirement.py'),1,target)
                    self.assertEqual(commands.count('--evidence "$evidence/run"'),1,target)
                    self.assertEqual(commands.count('--sanitize --evidence'),int(kind=='sanitize'),target)
                    self.assertNotIn('--profiles',commands)
                    self.assertNotIn('--budgets',commands)
                    self.assertIn((ROOT/'build'/('cycle-private-retirement-'+kind)).as_posix(),
                                  commands.replace('\\','/'))
                commands='\n'.join(private_commands.values())
                self.assertEqual(commands.count('python3 tests/cycle-private-retirement.py'),2)
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
        spec=importlib.util.spec_from_file_location('retirement_operation_contract',
                                                 ROOT/'tests/cycle-private-retirement.py')
        driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        self.assertEqual(driver.HEAP_BYTES,4194304)
        self.assertEqual(len(driver.operation_plan('system',1)),38)
        self.assertEqual(len(driver.operation_plan('fixed',32)),36)
        self.assertEqual(len(driver.operation_plan('eager',32)),16)
        for mode in driver.QUEUED:
            for recent in ('0','1'):
                self.assertIn(['32','queued',mode,recent],driver.operation_plan('fixed',32))
        for mode in ('active-local','active-full'):
            for phase in ('1','2','3'):
                self.assertIn(['32',mode,phase],driver.operation_plan('system',1024))
        for n in (32,256,2048):
            self.assertIn([str(n),'private','assert-local'],driver.operation_plan('system',1))
        self.assertFalse(any(row[1] in ('queued','certificate','reuse','unknown-after-drop')
                             for row in driver.operation_plan('eager',32)))
        self.assertEqual(driver.profile_selection(None,True)[0],['system','fixed','eager'])
        with self.assertRaises(ValueError):driver.profile_selection(['lazy'],True)
        red=b'IDLE label=private n=32 rounds=8 units=1136 epochs=8\nAssertion work <= 16u * rounds + 64u failed\n'
        driver.validate_failure_control(-6,b'',red)
        for status,stdout,stderr,timedout in ((0,b'',red,False),(-6,b'output',red,False),
                (-6,b'',red,True),(-6,b'',red.replace(b'1136',b'128'),False),
                (-6,b'',red.replace(b'work <= 16u * rounds + 64u',b'unrelated assertion'),False)):
            with self.assertRaises(AssertionError):
                driver.validate_failure_control(status,stdout,stderr,timedout)
        spec=importlib.util.spec_from_file_location('retirement_catalogue',ROOT/'tests/suite-catalogue.py')
        catalogue=importlib.util.module_from_spec(spec);spec.loader.exec_module(catalogue)
        data=json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        catalogue.validate(data,ROOT)
        for name in ('tests/cycle-private-retirement.py','tests/cycle-idle-invalidation.c',
                     'tests/cycle-private-retirement-v5.json','tests/generated-llvm-sanitizer.py',
                     'tests/generated-llvm-sanitizer.min'):
            omitted=dict(data,sources=[row for row in data['sources'] if row['path']!=name])
            with self.subTest(source=name),self.assertRaises(ValueError):
                catalogue.validate(omitted,ROOT)
        self.assertIn('tests/cycle-idle-invalidation.c',(ROOT/'scripts/format.py').read_text())
        self.assertIn('VERSION = "23.1.2"',(ROOT/'scripts/format.py').read_text())


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
                    'build/minyar-runtime.o', 'build'}
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
                    self.assertTrue(fixtures | {'tests/parallel-signatures.py',
                                                'tests/regressions.py', 'build/minyar-runtime.o'}
                                    <= rules[target], target)
                self.assertTrue(stage3 <= rules[native])
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('python3 tests/parallel-signatures.py;'), 2)
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
                self.assertIn('tests/compiler-behavior.py', commands)
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

        tree = ast.parse((ROOT / 'scripts/check-linux.py').read_text())
        targets = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(x, ast.Name) and x.id == 'TARGETS' for x in node.targets))
        for target in (native, sanitize):
            self.assertEqual(targets.count(target), 1)
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('check-portable', workflow)
        self.assertIn('scripts/check-linux.py', workflow)
        spec = importlib.util.spec_from_file_location('parallel_catalogue', ROOT / 'tests/suite-catalogue.py')
        catalogue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalogue)
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for name in fixtures | {'tests/parallel-signatures.py'}:
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

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='minyar relay wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                makefile.write_text('PEER_GRPC_PYTHON=/selected-pinned/python\n' + fragment +
                                   '\n.PHONY: build/minyarc build check-peer-grpc-python\n'
                                   'build/minyarc build check-peer-grpc-python:\n\t@echo ARTIFACT $@\n')
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
                    self.assertIn('check-peer-grpc-python', rules.get(target, set()))
                    self.assertIn('tests/peer-edge-relay.py', rules.get(target, set()))
                    if 'lifetime' in target:
                        self.assertIn('tests/peer-edge-relay-lifetime.py', rules[target])
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('"/selected-pinned/python"'), 6)
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
        tree = ast.parse((ROOT / 'scripts/check-linux.py').read_text())
        targets = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(x, ast.Name) and x.id == 'TARGETS' for x in node.targets))
        for target in native | sanitize:
            self.assertEqual(targets.count(target), 1)
        assert_ci_runs_quic_group(self, *sorted(native | sanitize))
        spec = importlib.util.spec_from_file_location('relay_catalogue', ROOT / 'tests/suite-catalogue.py')
        catalogue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalogue)
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for name in ('tests/peer-edge-relay.py', 'tests/peer-edge-relay-lifetime.py', 'tests/peer-edge-soak.py'):
            with self.subTest(missing_source=name), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[x for x in data['sources'] if x['path'] != name]), ROOT)



    def test_ack_scheduling_has_both_optimizations_and_all_mandatory_gates(self):
        import importlib.util
        import json
        import re
        text = (ROOT / 'build-support/checks.mk').read_text()
        begin = text.index('# ACK scheduling gates')
        end = text.index('# Handshake PTO virtual-clock modes', begin)
        source = text[begin:end]
        native, sanitize = 'check-quic-ack', 'check-quic-ack-sanitize'

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='minyar ACK wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                makefile.write_text(fragment + '\n.PHONY: build/minyarc build\n'
                                   'build/minyarc build:\n\t@echo ARTIFACT $@\n')
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
                    self.assertTrue({'tests/quic-ack.py', 'tests/quic-ack.min',
                                     'tests/tls-local.py', 'build/minyarc'}
                                    <= rules.get(target, set()), target)
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('tests/quic-ack.py'), 2)
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
        tree = ast.parse((ROOT / 'scripts/check-linux.py').read_text())
        targets = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(x, ast.Name) and x.id == 'TARGETS' for x in node.targets))
        for target in (native, sanitize):
            self.assertEqual(targets.count(target), 1)
        assert_ci_runs_quic_group(self, 'check-quic', 'check-quic-sanitize')
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        format_tree = ast.parse((ROOT / 'scripts/format.py').read_text())
        version = next(ast.literal_eval(node.value) for node in format_tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(x, ast.Name) and x.id == 'VERSION' for x in node.targets))
        self.assertEqual(version, '23.1.2')
        # The runner's formatting group installs clang-format==VERSION from scripts/format.py.
        self.assertIn('--group formatting', workflow)
        spec = importlib.util.spec_from_file_location('ack_catalogue', ROOT / 'tests/suite-catalogue.py')
        catalogue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalogue)
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for fixture in ('tests/quic-ack.py', 'tests/quic-ack.min'):
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

        def verify(fragment):
            with tempfile.TemporaryDirectory(prefix='minyar PTO wiring ') as folder:
                makefile = Path(folder) / 'probe.mk'
                makefile.write_text(fragment + '\n.PHONY: build/minyarc build\n'
                                   'build/minyarc build:\n\t@echo ARTIFACT $@\n')
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
                    self.assertTrue({'tests/quic-pto.py', 'tests/quic-pto.min', 'build/minyarc'}
                                    <= rules.get(target, set()), target)
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('tests/quic-pto.py'), 3)
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
        namespace = {}
        tree = ast.parse((ROOT / 'scripts/check-linux.py').read_text())
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'TARGETS':
                        namespace['TARGETS'] = ast.literal_eval(node.value)
        for target in (native, sanitize):
            self.assertEqual(namespace['TARGETS'].count(target), 1)
        assert_ci_runs_quic_group(self, 'check-quic', 'check-quic-sanitize')
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        spec = importlib.util.spec_from_file_location('pto_catalogue', ROOT / 'tests/suite-catalogue.py')
        catalogue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalogue)
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for fixture in ('tests/quic-pto.py', 'tests/quic-pto.min'):
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
                                   'build/minyarc-errors build/minyarc-errors-sanitize:\n\t@echo ARTIFACT $@\n')
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
                            'tests/cycle-registration.py', 'tools/cycle_runtime.py'}
                for target in both:
                    self.assertTrue(fixtures <= rules.get(target, set()), target)
                self.assertIn('build/minyarc-errors', rules[native])
                self.assertIn('build/minyarc-errors-sanitize', rules[sanitize])
                commands = dry_run_commands(result.stdout)
                self.assertEqual(commands.count('tests/cycle-registration.py'), 2)
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

        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, ROOT / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        runner = load('registration_linux_runner', 'scripts/check-linux.py')
        for target in (native, sanitize):
            self.assertEqual(runner.TARGETS.count(target), 1)
        formatter = load('registration_formatter', 'scripts/format.py')
        for fixture in ('tests/cycle-registration-exposure.c', 'tests/cycle-late-registration.c'):
            self.assertIn(fixture, formatter.FILES)
        catalogue = load('registration_catalogue', 'tests/suite-catalogue.py')
        data = json.loads((ROOT / 'tests/suite-catalogue.json').read_text())
        catalogue.validate(data, ROOT)
        for fixture in ('tests/cycle-registration-exposure.c', 'tests/cycle-late-registration.c',
                        'tests/cycle-late-registration.min', 'tests/cycle-registration.py'):
            self.assertIn(fixture, catalogue.discover(ROOT))
            with self.subTest(uncatalogued=fixture), self.assertRaises(ValueError):
                catalogue.validate(dict(data, sources=[row for row in data['sources']
                                                       if row['path'] != fixture]), ROOT)
        driver = load('registration_driver', 'tests/cycle-registration.py')
        import inspect
        language = driver.load('registration_inspection_control', 'tests/errors-language.py')
        self.assertEqual(Path(inspect.getsourcefile(language.ErrorsLanguage)),
                         ROOT / 'tests/errors-language.py')
        with patch('clang_helpers.platform.system', return_value='Windows'):
            profiles, unsupported = driver.profile_selection(None, True)
            self.assertEqual(profiles, ['system', 'fixed', 'eager'])
            self.assertEqual(unsupported[0]['profile'], 'lazy')
            with self.assertRaises(ValueError):
                driver.profile_selection(['lazy'], True)
        with patch.object(driver, 'windows_host', return_value=True), \
                patch.object(sys, 'argv', ['cycle-registration.py', '--profiles', 'lazy',
                                         '--evidence', 'unused']), \
                self.assertRaises(SystemExit) as unsupported_exit:
            driver.main()
        self.assertEqual(unsupported_exit.exception.code, 2)
        # These schedules are built into main(void), not runtime graph sizes.
        self.assertFalse(driver.build_parser().parse_args(['--evidence', 'out']).__dict__.get('nodes'))
        with self.assertRaises(SystemExit):
            driver.build_parser().parse_args(['--evidence', 'out', '--nodes', '2048'])

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
            self.assertEqual(commands.count('tests/cycle-additive.py'), 2)
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
                    self.assertIn('tests/tls-validity.py --sanitize', result.stdout)
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
                '\t@echo ARTIFACT $@\n')
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
                    self.assertIn('tests/managed-graphs-launcher.py', result.stdout)


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
                'build/ownership-runtime.o')
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/peer-tests.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: ' + ' '.join(targets) + '\n' +
                ' '.join(targets) + ':\n\t@echo ARTIFACT $@\n')
            for suite in ('tests/peer-rust-go-zig.py', 'tests/peer-regressions.py'):
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
                        needs_driver = (suite == 'tests/peer-rust-go-zig.py'
                                        or gate == 'check-peer-ownership')
                        self.assertEqual(
                            'build/minyarc-errors-request' in artifacts,
                            needs_driver)
                        self.assertEqual(
                            'build/minyar-module-build' in artifacts,
                            needs_driver)


    def test_grpc_gates_verify_external_peers_and_bound_default_builds(self):
        with tempfile.TemporaryDirectory(prefix='minyar grpc wiring ') as folder:
            work = Path(folder)
            for name in ('tests/interop/peergrpc/requirements.txt',
                         'scripts/check-peer-python.py'):
                path = work / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('')
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/peer-grpc.mk').replace(' ', '\\ ') + '\n'
                '.PHONY: build/minyarc\n'
                'build/minyarc:\n\t@echo ARTIFACT $@\n')
            for selected in ('build/peergrpc-venv/bin/python', 'preinstalled-python',
                             'preinstalled Python'):
                for gate in ('check-http2', 'check-peer-grpc', 'check-peer-grpc-sanitize',
                             'check-http2-churn', 'check-peer-grpc-churn',
                             'check-peer-grpc-retire', 'check-peer-edge-cids',
                             'check-peer-edge-cids-sanitize'):
                    with self.subTest(selected=selected, gate=gate):
                        env = dict(os.environ)
                        env.pop('MAKEFLAGS', None)
                        result = subprocess.run(
                            ['make', '-n', '-f', str(makefile),
                             'PEER_GRPC_PYTHON=' + selected, gate],
                            cwd=work, env=env, text=True, capture_output=True, timeout=10)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('scripts/check-peer-python.py', result.stdout)
                        self.assertIn('"' + selected + '" scripts/check-peer-python.py', result.stdout)
                        self.assertIn('"' + selected + '" tests/', result.stdout)
                        setup = selected == 'build/peergrpc-venv/bin/python'
                        self.assertEqual('python3 -m venv' in result.stdout, setup)
                        if setup:
                            self.assertIn('GRPC_PYTHON_BUILD_EXT_COMPILER_JOBS=1', result.stdout)
                            self.assertIn('CMAKE_BUILD_PARALLEL_LEVEL=1', result.stdout)



    def test_successful_empty_pip_cannot_publish_peer_ready_stamp(self):
        # Windows task termination can return zero to the MSYS parent even
        # though wheel installation never completed. Verify actual imports
        # before publishing the cache stamp.
        with tempfile.TemporaryDirectory(prefix='minyar incomplete peer ') as folder:
            work = Path(folder)
            for name in ('tests/interop/peergrpc/requirements.txt',
                         'scripts/check-peer-python.py'):
                path = work / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / name).read_bytes())
            mock = work / 'bin/python3'
            mock.parent.mkdir()
            mock.write_text(
                '#!' + sys.executable + '\nfrom pathlib import Path\n'
                'root=Path("build/peergrpc-venv/bin"); root.mkdir(parents=True)\n'
                'pip=root/"pip"; pip.write_text("#!/bin/sh\\n'
                'echo PIP_JOBS=$GRPC_PYTHON_BUILD_EXT_COMPILER_JOBS\\nexit 0\\n"); pip.chmod(0o755)\n'
                'python=root/"python"; python.write_text(' +
                repr('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n') +
                '); python.chmod(0o755)\n')
            mock.chmod(0o755)
            # No interpreter can satisfy this exact pin; the empty installer
            # must not make that incomplete environment appear ready.
            requirements = work / 'tests/interop/peergrpc/requirements.txt'
            requirements.write_text(requirements.read_text().replace('h2==4.3.0', 'h2==0.0.0'))
            makefile = work / 'probe.mk'
            makefile.write_text(
                'include ' + str(ROOT / 'build-support/peer-grpc.mk').replace(' ', '\\ ') + '\n')
            env = dict(os.environ, PATH=str(mock.parent) + os.pathsep + os.environ['PATH'])
            env.pop('MAKEFLAGS', None)
            result = subprocess.run(
                ['make', '-f', str(makefile), 'build/peergrpc-venv/.ready'],
                cwd=work, env=env, text=True, capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PIP_JOBS=1', result.stdout)
            self.assertIn('peer Python verification failed:', result.stderr)
            self.assertFalse((work / 'build/peergrpc-venv/.ready').exists())

    def test_quic_official_adapter_requires_all_linux_controls(self):
        import importlib.util
        import json
        import re
        fragment = (ROOT/'build-support/quic-official-adapter.mk').read_text()
        target = 'check-quic-official-adapter'
        inputs = {'tests/quic-official-adapter.py',
                  'tests/interop/qns/owned_adapter.py',
                  'tests/interop/qns/controls-requirements.txt',
                  'scripts/check-quic-official-inputs.py',
                  'tests/quic-simulator-shutdown.py',
                  'tests/interop/qns/simulator-shutdown.sh',
                  'tests/quic-qns-endpoint-lifecycle.py',
                  'tests/interop/qns/endpoint.py'}
        aggregates = ('check', 'check-portable', 'check-quic', 'check-quic-sanitize',
                      'check-quic-rfc', 'check-quic-rfc-sanitize', 'check-sanitize')

        def verify(candidate, host='Linux', operating_system='', ready=False):
            with tempfile.TemporaryDirectory(prefix='owned adapter Make rules ') as folder:
                directory = Path(folder)
                for name in inputs:
                    path = directory/name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes((ROOT/name).read_bytes())
                records = []
                if ready:
                    for name in ('build/quic-interop-runner-740c05a.git/.ready.json',
                                 'build/quic-official-controls-venv/.ready.json'):
                        path = directory/name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text('{"mock_ready_not_verification":true}\n')
                        records.append((path, path.read_bytes()))
                uname = directory/'uname'
                uname.write_text('#!/bin/sh\nprintf "%s\\n" "'+host+'"\n')
                uname.chmod(0o755)
                makefile = directory/'probe.mk'
                makefile.write_text('LIMITED := ordinary-limit\n'
                                    'SANITIZER_LIMITED := sanitizer-limit\n'
                                    +candidate+'\n.PHONY: build\nbuild:\n\t@echo INPUT build\n')
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
                    self.assertNotIn('prepare-', commands)
                    self.assertNotIn('check-quic-official-inputs.py controls ', commands)
                    self.assertFalse(rules.get(target, set()))
                    return
                self.assertTrue(inputs <= rules.get(target, set()))
                controls = [line for line in commands.splitlines()
                            if ' -E scripts/check-quic-official-inputs.py controls ' in line]
                self.assertEqual(len(controls), 1)
                command = controls[0]
                self.assertIn('ordinary-limit ', command)
                self.assertNotIn('sanitizer-limit', command)
                self.assertIn('--repository "', command)
                self.assertIn('--artifacts "$artifacts/run"', command)
                self.assertIn(str(directory/'build/quic-official-adapter.'), commands)
                self.assertIn(str(directory/'build/quic-interop-runner-740c05a.git'), command)
                self.assertNotIn(' -E tests/quic-official-adapter.py ', commands)
                for forbidden in ('--case ', '--sanitize', ' -O ', '/home/user/',
                                  'docker ', 'compose ', '--pull ', '--build '):
                    self.assertNotIn(forbidden, command)
                self.assertIn('mktemp -d "$(abspath build)', candidate)
                for preparation in ('prepare-runner', 'prepare-python'):
                    if ready:
                        self.assertNotIn(preparation, commands)
                    else:
                        self.assertIn(preparation, commands)
                for path, data in records:
                    self.assertEqual(path.read_bytes(), data)
                self.assertIn('--requirements "tests/interop/qns/controls-requirements.txt"',
                              commands)

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
                ('ordinary limiter omitted', '$(LIMITED) "$(QUIC_OFFICIAL_PYTHON)" -E scripts/',
                 '"$(QUIC_OFFICIAL_PYTHON)" -E scripts/'),
                ('wrong limiter', '$(LIMITED) "$(QUIC_OFFICIAL_PYTHON)" -E scripts/',
                 '$(SANITIZER_LIMITED) "$(QUIC_OFFICIAL_PYTHON)" -E scripts/'),
                ('optimized Python', '-E scripts/check-quic-official-inputs.py controls',
                 '-O scripts/check-quic-official-inputs.py controls'),
                ('private cache', '$(abspath build)/quic-interop-runner-740c05a.git',
                 '/home/user/private-runner'),
                ('relative artifacts', '$(abspath build)/quic-official-adapter.',
                 'build/quic-official-adapter.'),
                ('existing artifact leaf', '$$artifacts/run', '$$artifacts'),
                ('missing pin argument', 'controls --repository "$(QUIC_OFFICIAL_RUNNER)"', 'controls'),
                ('missing dependency verification', 'scripts/check-quic-official-inputs.py controls',
                 'scripts/check-quic-official-inputs.py ignored')):
            mutant = fragment.replace(old, new, 1)
            self.assertNotEqual(mutant, fragment, label)
            with self.subTest(invalid_recipe=label), self.assertRaises(AssertionError):
                verify(mutant)
        tree = ast.parse((ROOT/'scripts/check-linux.py').read_text())
        targets = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign) and any(
                           isinstance(name, ast.Name) and name.id == 'TARGETS'
                           for name in node.targets))
        self.assertEqual(targets.count(target), 1)
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('build/linux-evidence/**/build/quic-official-adapter.*', workflow)
        # Linux uploads come from the runner's evidence; macOS and Windows from quic-native.
        self.assertEqual(workflow.count('            build/quic-official-adapter.*'), 1)
        driver = ast.parse((ROOT/'tests/quic-official-adapter.py').read_text())
        cases = []
        for node in driver.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(name, ast.Name) and name.id == 'CASES' for name in node.targets):
                cases.extend(ast.literal_eval(node.value))
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == 'CASES':
                if isinstance(node.value, ast.Name):
                    declaration = next(item.value for item in driver.body
                                       if isinstance(item, ast.Assign) and any(
                                           isinstance(name, ast.Name) and name.id == node.value.id
                                           for name in item.targets))
                    cases.extend(ast.literal_eval(declaration))
                else:
                    cases.extend(ast.literal_eval(node.value))
        forwarding_cases = ('raw-forward-incremental', 'raw-forward-stderr-status',
                            'raw-forward-no-duplicate', 'raw-forward-empty',
                            'raw-forward-private-json', 'raw-forward-backpressure')
        self.assertEqual(len(cases), 113)
        self.assertEqual(len(set(cases)), 113)
        self.assertTrue(set(forwarding_cases) <= set(cases))
        original_cases = [case for case in cases if case not in forwarding_cases]
        self.assertEqual(len(original_cases), 107)
        self.assertEqual(len(set(original_cases)), 107)
        main = next(node for node in driver.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'main')
        selection = next(node.value for node in ast.walk(main)
                         if isinstance(node, ast.Assign) and any(
                             isinstance(name, ast.Name) and name.id == 'cases'
                             for name in node.targets))
        self.assertEqual(ast.unparse(selection), 'args.case or CASES')
        spec = importlib.util.spec_from_file_location(
            'official_adapter_catalogue', ROOT/'tests/suite-catalogue.py')
        catalogue = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalogue)
        data = json.loads((ROOT/'tests/suite-catalogue.json').read_text())
        rows = {row['path']: row for row in data['sources']}
        self.assertEqual(rows['tests/quic-official-adapter.py']['role'], 'suite')
        self.assertIn('build-support/quic-official-adapter.mk',
                      rows['tests/quic-official-adapter.py']['consumers'])
        self.assertEqual(rows['tests/interop/qns/owned_adapter.py']['role'], 'support')
        self.assertIn('tests/quic-official-adapter.py',
                      rows['tests/interop/qns/owned_adapter.py']['consumers'])
        for missing in ('tests/quic-official-adapter.py',
                        'tests/interop/qns/owned_adapter.py'):
            candidate = dict(data, sources=[row for row in data['sources']
                                           if row['path'] != missing])
            with self.subTest(omitted_source=missing), self.assertRaises(ValueError):
                catalogue.validate(candidate, ROOT)

    def test_quic_python_preparation_publishes_only_verified_inputs(self):
        import importlib.util
        import json
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location(
            'official_adapter_publication', ROOT/'scripts/check-quic-official-inputs.py')
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        for failure in ('venv', 'pip', 'verify', 'race', ''):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(
                    prefix='controls cache publication ') as folder:
                root = Path(folder).resolve()
                destination = root/'controls'
                stages = []
                def command(argv, timeout=30):
                    self.assertFalse(destination.exists())
                    if 'venv' in argv:
                        stage = Path(argv[-1])
                        stages.append(stage)
                        (stage/'bin').mkdir()
                        (stage/'bin/python').symlink_to(sys.executable)
                        (stage/'pyvenv.cfg').write_text('retained environment\n')
                        if failure == 'venv':
                            raise subprocess.CalledProcessError(1, argv)
                        return b''
                    if 'pip' in argv:
                        if failure == 'pip':
                            raise subprocess.CalledProcessError(1, argv)
                        return b''
                    self.assertIn('verify-python', argv)
                    if failure == 'verify':
                        return b'{}'
                    prefix = Path(argv[5].split('=', 1)[1])
                    checker.require_empty_pycache(prefix)
                    module = checker.binding(stages[-1]/'pyvenv.cfg')
                    report = {'verified': True,
                              'contract': checker.requirements_contract(checker.REQUIREMENTS),
                              'implementation': 'cpython',
                              'python': checker.binding((stages[-1]/'bin/python').resolve()),
                              'module': module, 'packages': [module],
                              'bytecode_route': {'prefix': str(prefix),
                                                 'dont_write_bytecode': True}}
                    if failure == 'race':
                        destination.mkdir()
                        (destination/'sentinel').write_bytes(b'other cache')
                    return json.dumps(report).encode()
                with patch.object(checker, 'require_linux'), \
                        patch.object(checker, 'require_supported_python'), \
                        patch.object(checker.Commands, 'run', side_effect=command):
                    if failure:
                        with self.assertRaises((ValueError, OSError,
                                                subprocess.CalledProcessError)):
                            checker.prepare_python(destination, checker.REQUIREMENTS)
                    else:
                        result = checker.prepare_python(destination, checker.REQUIREMENTS)
                        self.assertTrue(result['verified'])
                self.assertEqual(len(stages), 1)
                self.assertEqual((stages[0]/'pyvenv.cfg').read_text(),
                                 'retained environment\n')
                if failure == 'race':
                    self.assertEqual((destination/'sentinel').read_bytes(), b'other cache')
                    self.assertFalse((destination/'.ready.json').exists())
                elif failure:
                    self.assertFalse(destination.exists())
                    self.assertFalse(destination.is_symlink())
                    self.assertFalse((stages[0]/'.ready.json').exists())
                    original = (stages[0]/'pyvenv.cfg').stat().st_mtime_ns
                    failure = ''
                    with patch.object(checker, 'require_linux'), \
                            patch.object(checker, 'require_supported_python'), \
                            patch.object(checker.Commands, 'run', side_effect=command):
                        self.assertTrue(checker.prepare_python(
                            destination, checker.REQUIREMENTS)['verified'])
                    self.assertEqual(len(stages), 2)
                    self.assertEqual(destination.resolve(), stages[-1])
                    self.assertFalse((stages[0]/'.ready.json').exists())
                    self.assertEqual((stages[0]/'pyvenv.cfg').stat().st_mtime_ns, original)
                else:
                    self.assertTrue(destination.is_symlink())
                    self.assertEqual(destination.resolve(), stages[0])
                    self.assertTrue(json.loads((destination/'.ready.json').read_text())['verified'])
                    with patch.object(checker.Commands, 'run') as launched:
                        with self.assertRaises(ValueError):
                            checker.prepare_python(destination, checker.REQUIREMENTS)
                        launched.assert_not_called()
        with tempfile.TemporaryDirectory(prefix='dangling controls cache ') as folder:
            destination = Path(folder).resolve()/'controls'
            destination.symlink_to(destination.parent/'missing', target_is_directory=True)
            with patch.object(checker, 'require_linux'), \
                    patch.object(checker, 'require_supported_python'), \
                    patch.object(checker.Commands, 'run') as launched:
                with self.assertRaises(ValueError):
                    checker.prepare_python(destination, checker.REQUIREMENTS)
                launched.assert_not_called()
            self.assertTrue(destination.is_symlink())

    def test_quic_official_prerequisites_refuse_false_readiness(self):
        import hashlib
        import importlib.util
        import json
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location(
            'official_adapter_inputs', ROOT/'scripts/check-quic-official-inputs.py')
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory(prefix='owned adapter Git objects ') as folder:
            root = Path(folder)
            repository = root/'repository'
            subprocess.run(['git', 'init', '--bare', str(repository)],
                           check=True, capture_output=True, timeout=15)
            names = sorted(set(checker.PRIMARY_NAMES) |
                           {f'fixture-{i:02}.txt' for i in range(35)})
            self.assertEqual(len(names), 40)
            objects, entries, primary = {}, [], {}
            for name in names:
                data = ('retained source '+name+'\n').encode()
                result = subprocess.run(['git', '-C', str(repository),
                                         'hash-object', '-w', '--stdin'], input=data,
                                        check=True, capture_output=True, timeout=15)
                blob = result.stdout.decode().strip()
                objects[name] = blob
                entries.append(f'100644 blob {blob}\t{name}\n'.encode())
                if name in checker.PRIMARY_NAMES:
                    primary[name] = hashlib.sha256(data).hexdigest()
            tree = subprocess.run(['git', '-C', str(repository), 'mktree'],
                                  input=b''.join(entries), check=True,
                                  capture_output=True, timeout=15).stdout.decode().strip()
            pin = subprocess.run(
                ['git', '-C', str(repository), '-c', 'user.name=Fixture',
                 '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                 'commit-tree', tree], input=b'Owned source fixture\n', check=True,
                capture_output=True, timeout=15).stdout.decode().strip()
            with patch.object(checker, 'load_contract', return_value=(pin, primary)):
                verified = checker.verify_runner(repository)
                self.assertTrue(verified['verified'])
                self.assertEqual(len(verified['files']), 40)
                for name in checker.PRIMARY_NAMES:
                    changed = dict(primary, **{name: '0'*64})
                    with patch.object(checker, 'load_contract', return_value=(pin, changed)):
                        with self.subTest(corrupt_primary=name), self.assertRaises(ValueError):
                            checker.verify_runner(repository)
                with patch.object(checker, 'load_contract', return_value=('0'*40, primary)):
                    with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                        checker.verify_runner(repository)
                graft = repository/'info/grafts'
                graft.write_text(pin+'\n')
                with self.assertRaises(ValueError):
                    checker.verify_runner(repository)
                graft.unlink()
                subprocess.run(['git', '-C', str(repository), 'update-ref',
                                'refs/replace/'+pin, pin], check=True,
                               capture_output=True, timeout=15)
                with self.assertRaises(ValueError):
                    checker.verify_runner(repository)
                subprocess.run(['git', '-C', str(repository), 'update-ref', '-d',
                                'refs/replace/'+pin], check=True,
                               capture_output=True, timeout=15)
                blob = objects[names[-1]]
                (repository/'objects'/blob[:2]/blob[2:]).unlink()
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    checker.verify_runner(repository)
        with tempfile.TemporaryDirectory(prefix='false adapter readiness ') as folder:
            root = Path(folder)
            with patch.object(checker.Commands, 'run', return_value=b''):
                with self.assertRaises((ValueError, OSError)):
                    checker.prepare_runner(root/'runner')
            self.assertFalse((root/'runner/.ready.json').exists())
            with patch.object(checker.Commands, 'run', return_value=b''):
                with self.assertRaises((ValueError, OSError, json.JSONDecodeError)):
                    checker.prepare_python(root/'venv',
                                           ROOT/'tests/interop/qns/controls-requirements.txt')
            self.assertFalse((root/'venv/.ready.json').exists())
            for mode in ('runner', 'venv'):
                poisoned = root/('poisoned-'+mode)
                poisoned.mkdir()
                sentinel = poisoned/'poison'
                sentinel.write_bytes(b'not a verified cache')
                with patch.object(checker.Commands, 'run') as launched:
                    with self.subTest(existing_poison=mode), self.assertRaises(ValueError):
                        if mode == 'runner':
                            checker.prepare_runner(poisoned)
                        else:
                            checker.prepare_python(poisoned, checker.REQUIREMENTS)
                    launched.assert_not_called()
                self.assertEqual(sentinel.read_bytes(), b'not a verified cache')
                self.assertFalse((poisoned/'.ready.json').exists())
            external = root/'provided'
            external.mkdir()
            before = set(external.rglob('*'))
            with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                checker.verify_runner(external)
            self.assertEqual(set(external.rglob('*')), before)
        with tempfile.TemporaryDirectory(prefix='wrong wheel version route ') as folder:
            from types import SimpleNamespace
            version_flags = SimpleNamespace(**{
                name: getattr(sys.flags, name) for name in dir(sys.flags)
                if isinstance(getattr(sys.flags, name), (int, bool))})
            version_flags.safe_path = True
            with patch.object(checker.sys, 'flags', version_flags), \
                    patch.object(checker.sys, 'pycache_prefix', os.path.realpath(folder)), \
                    patch.object(checker.sys, 'dont_write_bytecode', True), \
                    patch.object(checker.importlib.metadata, 'version', return_value='0'):
                with self.assertRaisesRegex(ValueError, 'PyYAML version differs'):
                    checker.verify_python(ROOT/'tests/interop/qns/controls-requirements.txt')
        for version in ((3, 11), (3, 13), (3, 14)):
            with patch.object(checker.sys, 'version_info', version):
                with self.subTest(unverified_abi=version), self.assertRaises(ValueError):
                    checker.require_supported_python()
        from types import SimpleNamespace
        trusted_flags = SimpleNamespace(**{
            name: getattr(sys.flags, name) for name in dir(sys.flags)
            if isinstance(getattr(sys.flags, name), (int, bool))})
        trusted_flags.safe_path = True
        with patch.object(checker.sys, 'implementation', SimpleNamespace(name='pypy')):
            with self.assertRaises(ValueError):
                checker.require_supported_python()
        with tempfile.TemporaryDirectory(prefix='controls wheel byte proof ') as folder:
            import base64
            root = Path(folder).resolve()
            module = root/'yaml/__init__.py'
            module.parent.mkdir()
            module.write_bytes(b'retained module fixture\n')
            expected = base64.urlsafe_b64encode(
                hashlib.sha256(module.read_bytes()).digest()).decode().rstrip('=')
            class Entry:
                hash = SimpleNamespace(mode='sha256', value=expected)
                def __str__(self):
                    return 'yaml/__init__.py'
            distribution = SimpleNamespace(files=[Entry()],
                                           locate_file=lambda item: root/str(item))
            yaml = SimpleNamespace(__file__=str(module), __version__='6.0.2')
            cache = root/'fresh-bytecode'
            cache.mkdir()
            with patch.object(checker.sys, 'flags', trusted_flags), \
                    patch.object(checker.sys, 'pycache_prefix', str(cache)), \
                    patch.object(checker.sys, 'dont_write_bytecode', True), \
                    patch.object(checker.importlib.util, 'find_spec',
                                 return_value=SimpleNamespace(
                                     origin=str(module),
                                     loader=checker.importlib.machinery.SourceFileLoader('yaml', str(module)))), \
                    patch.object(checker.importlib.metadata, 'version', return_value='6.0.2'), \
                    patch.object(checker.importlib.metadata, 'distribution',
                                 return_value=distribution), \
                    patch.object(checker.importlib, 'import_module', return_value=yaml) as imported:
                class AlternateLoader(checker.importlib.machinery.SourceFileLoader):
                    pass
                for origin, loader in (
                        (str(root/'shadow/yaml.py'),
                         checker.importlib.machinery.SourceFileLoader('yaml', str(root/'shadow/yaml.py'))),
                        (str(module), AlternateLoader('yaml', str(module))),
                        (str(module), None)):
                    with patch.object(checker.importlib.util, 'find_spec',
                                      return_value=SimpleNamespace(origin=origin, loader=loader)):
                        with self.subTest(unverified_origin=origin, loader=type(loader).__name__):
                            with self.assertRaisesRegex(ValueError, 'verified source file'):
                                checker.verify_python(checker.REQUIREMENTS)
                        imported.assert_not_called()
                report = checker.verify_python(ROOT/'tests/interop/qns/controls-requirements.txt')
                self.assertTrue(report['verified'])
                self.assertEqual(imported.call_count, 1)
                module.write_bytes(b'changed module fixture\n')
                with self.assertRaises(ValueError):
                    checker.verify_python(ROOT/'tests/interop/qns/controls-requirements.txt')
                self.assertEqual(imported.call_count, 1)
        hostile = {'GIT_DIR': '/wrong/repository', 'GIT_WORK_TREE': '/wrong/worktree',
                   'GIT_REPLACE_REF_BASE': 'refs/hostile', 'GIT_CONFIG_COUNT': '1',
                   'GIT_CONFIG_KEY_0': 'include.path', 'GIT_CONFIG_VALUE_0': '/wrong/config',
                   'GIT_CONFIG_SYSTEM': '/wrong/system', 'GIT_CONFIG_GLOBAL': '/wrong/global',
                   'GIT_CONFIG_NOSYSTEM': '0', 'GIT_NO_REPLACE_OBJECTS': '0'}
        with patch.dict(os.environ, hostile):
            clean = checker.git_environment()
            self.assertEqual({key: value for key, value in clean.items()
                              if key.startswith('GIT_')},
                             {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                              'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_TERMINAL_PROMPT': '0'})
            with tempfile.TemporaryDirectory(prefix='adapter launch routing ') as folder:
                root = Path(folder).resolve()
                repository = root/'trusted-repository'
                repository.mkdir()
                selections = []
                def harmless_child(argv, **kwargs):
                    selections.append((list(argv), kwargs['env']))
                    self.assertEqual(kwargs['env'], clean)
                    self.assertEqual(argv[1:5], ['-E', '-B', '-P', '-X'])
                    self.assertTrue(argv[5].startswith('pycache_prefix='))
                    cache = Path(argv[5].split('=', 1)[1])
                    checker.require_empty_pycache(cache)
                    if len(selections) == 1:
                        self.assertEqual(argv[6:8],
                                         [str(ROOT/'scripts/check-quic-official-inputs.py'),
                                          'verify'])
                        self.assertIn(str(repository), argv)
                        result = {'verified': True, 'runner': {'verified': True},
                                  'python': {'verified': True,
                                             'bytecode_route': {'prefix': str(cache),
                                                                'dont_write_bytecode': True}}}
                        return subprocess.CompletedProcess(argv, 0, json.dumps(result).encode(), b'')
                    self.assertEqual(argv[6], str(ROOT/'tests/quic-official-adapter.py'))
                    self.assertEqual(argv[7:],
                                     ['--pinned-runner', str(repository),
                                      '--artifacts', str(root/'run')])
                    self.assertNotIn('--case', argv)
                    (root/'run').mkdir()
                    return subprocess.CompletedProcess(argv, 0, b'ALL107 mock controls\n', b'')
                with patch.object(checker.subprocess, 'run', side_effect=harmless_child):
                    report = checker.run_controls(repository, checker.REQUIREMENTS, root/'run')
                self.assertTrue(report['verified'])
                self.assertEqual(len(selections), 2)
                self.assertEqual(selections[0][1], selections[1][1])
                self.assertEqual(report['git_environment'],
                                 {key: value for key, value in clean.items() if key.startswith('GIT_')})
                for tamper in ('poisoned route', 'missing route report', 'failed verification'):
                    calls = []
                    def poisoned_preflight(argv, **kwargs):
                        calls.append(list(argv))
                        cache = Path(argv[5].split('=', 1)[1])
                        result = {'verified': True, 'runner': {'verified': True},
                                  'python': {'verified': True,
                                             'bytecode_route': {'prefix': str(cache),
                                                                'dont_write_bytecode': True}}}
                        if tamper == 'poisoned route':
                            (cache/'unexpected.pyc').write_bytes(b'not fresh')
                        elif tamper == 'missing route report':
                            result['python'].pop('bytecode_route')
                        else:
                            result['verified'] = False
                        return subprocess.CompletedProcess(argv, 0, json.dumps(result).encode(), b'')
                    with patch.object(checker.subprocess, 'run', side_effect=poisoned_preflight):
                        with self.subTest(tamper=tamper), self.assertRaises(ValueError):
                            checker.run_controls(repository, checker.REQUIREMENTS,
                                                 root/('refused-'+tamper.replace(' ', '-')))
                    self.assertEqual(len(calls), 1)
                with patch.object(checker.Commands, 'run') as launched:
                    with self.assertRaises(ValueError):
                        checker.run_controls(repository, checker.REQUIREMENTS, root/'run')
                    launched.assert_not_called()
        with tempfile.TemporaryDirectory(prefix='valid altered adapter bytecode ') as folder:
            import base64
            import py_compile
            root = Path(folder).resolve()
            module = root/'yaml/__init__.py'
            module.parent.mkdir()
            module.write_text("__version__='6.0.2'\nSOURCE_MARKER='verified source'\n")
            altered = root/'altered.py'
            altered.write_text("__version__='6.0.2'\nSOURCE_MARKER='altered valid cache'\n")
            with patch.object(sys, 'pycache_prefix', None):
                cached = Path(importlib.util.cache_from_source(str(module)))
            cached.parent.mkdir()
            py_compile.compile(str(altered), cfile=str(cached), doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
            expected = base64.urlsafe_b64encode(
                hashlib.sha256(module.read_bytes()).digest()).decode().rstrip('=')
            class Entry:
                hash = SimpleNamespace(mode='sha256', value=expected)
                def __str__(self):
                    return 'yaml/__init__.py'
            distribution = SimpleNamespace(files=[Entry()],
                                           locate_file=lambda item: root/str(item))
            with patch.dict(sys.modules), patch.object(sys, 'path', [str(root)]+sys.path), \
                    patch.object(checker.importlib.metadata, 'version', return_value='6.0.2'), \
                    patch.object(checker.importlib.metadata, 'distribution', return_value=distribution):
                for name in list(sys.modules):
                    if name == 'yaml' or name.startswith('yaml.'):
                        sys.modules.pop(name)
                with patch.object(sys, 'pycache_prefix', None), \
                        patch.object(sys, 'dont_write_bytecode', False):
                    imported = importlib.import_module('yaml')
                    self.assertEqual(imported.SOURCE_MARKER, 'altered valid cache')
                    sys.modules.pop('yaml')
                    with self.assertRaises(ValueError):
                        checker.verify_python(checker.REQUIREMENTS)
                    self.assertNotIn('yaml', sys.modules)
                cache = root/'exclusive-clean-route'
                cache.mkdir()
                with patch.object(sys, 'flags', trusted_flags), \
                        patch.object(sys, 'pycache_prefix', str(cache)), \
                        patch.object(sys, 'dont_write_bytecode', True):
                    verified = checker.verify_python(checker.REQUIREMENTS)
                    self.assertTrue(verified['verified'])
                    self.assertEqual(sys.modules['yaml'].SOURCE_MARKER, 'verified source')
                    self.assertFalse(list(cache.iterdir()))
                    sys.modules.pop('yaml')
                    (cache/'unexpected.pyc').write_bytes(cached.read_bytes())
                    with self.assertRaises(ValueError):
                        checker.verify_python(checker.REQUIREMENTS)
                    self.assertNotIn('yaml', sys.modules)
                untrusted_flags = SimpleNamespace(**vars(trusted_flags))
                untrusted_flags.safe_path = False
                with patch.object(sys, 'flags', untrusted_flags), \
                        patch.object(sys, 'dont_write_bytecode', True), \
                        patch.object(checker.importlib, 'import_module') as imported:
                    with self.assertRaisesRegex(ValueError, 'safe import path'):
                        checker.verify_python(checker.REQUIREMENTS)
                    imported.assert_not_called()
                for route, no_write in ((None, True), ('relative', True),
                                        (str(root/'absent'), True), (str(cache), False)):
                    with patch.object(sys, 'pycache_prefix', route), \
                            patch.object(sys, 'dont_write_bytecode', no_write), \
                            patch.object(checker.importlib, 'import_module') as imported:
                        with self.subTest(route=route, no_write=no_write), self.assertRaises(ValueError):
                            checker.verify_python(checker.REQUIREMENTS)
                        imported.assert_not_called()
        with tempfile.TemporaryDirectory(prefix='invalid adapter requirements ') as folder:
            requirement = Path(folder)/'requirements.txt'
            for content in ('', 'PyYAML\n', 'PyYAML==6.0.3\n',
                            'PyYAML==6.0.2\nPyYAML==6.0.2\n',
                            'PyYAML==6.0.2\npyshark==0.6\n'):
                requirement.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    checker.requirements_contract(requirement)



    def test_os_tlsverify_sanitizer_selects_override_and_complete_directory(self):
        import json
        fragment = (ROOT / 'build-support/networking.mk').read_text()
        with tempfile.TemporaryDirectory(prefix='os sanitizer dispatch ') as temporary:
            directory = Path(temporary)
            binaries = directory / 'bin'
            binaries.mkdir()
            python = binaries / 'python3'
            python.write_text('#!' + sys.executable + '\n' +
                'import json,os,sys\n'
                'if sys.argv[1:2] == ["tests/os-tlsverify.py"]:\n'
                ' print(json.dumps({"clang":os.environ.get("MINYAR_CLANG"),'
                '"path":os.environ["PATH"],"argv":sys.argv[1:]}));sys.exit(0)\n'
                'if os.environ.get("OS_TLS_PROBE_MSYS") and sys.argv[1:2] == ["-c"]:\n'
                ' sys.path.insert(0,"tools");import host_paths\n'
                ' host_paths.platform.system=lambda:"MSYS_NT-10.0"\n'
                ' code=sys.argv[2];sys.argv=["-c",*sys.argv[3:]]\n'
                ' exec(code,{"__name__":"__main__"});sys.exit(0)\n'
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
                    selected_environment.update(OS_TLS_PROBE_MSYS='1',
                        OS_TLS_PROBE_TRANSLATIONS=json.dumps({sanitizer: selected_compiler}))
                for target, expected_compiler, arguments in (
                        ('check-os-tlsverify', ordinary, []),
                        ('check-os-tlsverify-sanitize', selected_compiler or sanitizer or ordinary,
                         ['--sanitize'])):
                    result = subprocess.run(['make', '--no-print-directory', '-rR', '-s',
                        '-f', str(probe), target], cwd=ROOT, env=selected_environment,
                        capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    selected = json.loads(result.stdout)
                    self.assertEqual(selected['clang'], expected_compiler)
                    self.assertEqual(selected['argv'], ['tests/os-tlsverify.py', *arguments])
                    expected_path = environment['PATH']
                    if sanitizer and arguments:
                        expected_path = (selected_directory or str(Path(sanitizer).parent)) + os.pathsep + expected_path
                    self.assertEqual(selected['path'], expected_path)
                if sanitizer:
                    self.assertIn('tools/host_paths.py', sanitizer_rule)

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
                                    if 'tests/os-tlsverify.py --sanitize' in line)
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
                    fragment.replace(sanitizer_rule, sanitizer_rule.replace('tools/host_paths.py', ''), 1)):
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
        import base64
        tree = ast.parse((ROOT / 'tests/peer-edge-relay.py').read_text())
        run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        request = next(node.elts[1] for node in ast.walk(run)
                       if isinstance(node, ast.Tuple) and len(node.elts) == 4
                       and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == 'wrong-key')
        helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'corrupt_signature']
        namespace = {'base64': base64}
        exec(compile(ast.Module(body=helpers, type_ignores=[]), '<relay helper>', 'exec'), namespace)
        expression = compile(ast.Expression(body=request), '<wrong-key request>', 'eval')
        for last in range(256):
            signature = bytes(range(63)) + bytes([last])
            token = b'e30.e30.' + base64.urlsafe_b64encode(signature).rstrip(b'=')
            if last == 0:
                self.assertTrue(token.endswith(b'AA'))
            class Lab:
                def signed(self, connection):
                    self.assert_connection = connection
                    return token
            lab = Lab()
            changed = eval(expression, namespace, {'lab': lab})
            with self.subTest(last_signature_byte=last):
                self.assertEqual(lab.assert_connection, 'wrong-key')
                self.assertNotEqual(changed, token, 'wrong-key control left a valid grant unchanged')
                prefix, encoded = changed.rsplit(b'.', 1)
                self.assertEqual(prefix, token.rsplit(b'.', 1)[0])
                decoded = base64.urlsafe_b64decode(encoded + b'==')
                self.assertEqual(len(decoded), len(signature))
                self.assertNotEqual(decoded, signature)
                self.assertEqual(encoded, base64.urlsafe_b64encode(decoded).rstrip(b'='))
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
                'if sys.argv[1:2] in (["tests/net-connect.py"],["tests/net-udp-offload.py"]):\n'
                ' key="MINYAR_CLANG" if sys.argv[1]=="tests/net-connect.py" else "MINYAR_TEST_CLANG"\n'
                ' print(json.dumps({"clang":os.environ.get(key),"path":os.environ["PATH"],'
                '"limit":os.environ.get("NET_PROBE_LIMIT"),"argv":sys.argv[1:]}));sys.exit(0)\n'
                'if os.environ.get("NET_PROBE_MSYS") and sys.argv[1:2] == ["-c"]:\n'
                ' sys.path.insert(0,"tools");import host_paths\n'
                ' host_paths.platform.system=lambda:"MSYS_NT-10.0"\n'
                ' code=sys.argv[2];sys.argv=["-c",*sys.argv[3:]]\n'
                ' exec(code,{"__name__":"__main__"});sys.exit(0)\n'
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
            targets = (
                ('check-net-connect', 'tests/net-connect.py', [], {'build/minyarc'}),
                ('check-net-connect-sanitize', 'tests/net-connect.py', ['--sanitize'], {'build/minyarc'}),
                ('check-net-udp-offload', 'tests/net-udp-offload.py',
                 ['--evidence', 'build/net-udp-offload'], {'build/minyarc', 'build/minyar-default-runtime.o'}),
                ('check-net-udp-offload-sanitize', 'tests/net-udp-offload.py',
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
                    selected_environment.update(NET_PROBE_MSYS='1',
                        NET_PROBE_TRANSLATIONS=json.dumps({sanitizer: selected_compiler}))
                for target, script, arguments, prerequisites in targets:
                    result = subprocess.run(['make', '--no-print-directory', '-j1', '-rR', '-s',
                        '-f', str(probe), target], cwd=ROOT, env=selected_environment,
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
                                         ({'tools/host_paths.py'} if sanitize else set()), target)

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
                    (recipe, recipe.replace(('MINYAR_CLANG' if script == 'tests/net-connect.py'
                        else 'MINYAR_TEST_CLANG') + '=$(call NET_SANITIZER_QUOTE,$(NET_SANITIZER_CLANG)) ', '')),
                    (recipe, recipe.replace('PATH="$(NET_SANITIZER_PATH)" ', '')),
                    (rule, rule.replace(' tools/host_paths.py', ''))))
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
