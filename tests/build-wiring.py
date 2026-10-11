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


class BuildWiring(unittest.TestCase):

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
                commands = result.stdout.split('# GNU Make', 1)[0]
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
                commands = result.stdout.split('# GNU Make', 1)[0]
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
                commands=result.stdout.split('# GNU Make',1)[0]
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
                commands = result.stdout.split('# GNU Make', 1)[0]
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
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('check-quic\n', workflow)
        self.assertIn('check-quic-sanitize\n', workflow)
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
        fragment = source[source.index(marker):]
        expected = {'build/minyarc', 'tests/generated-llvm-sanitizer.py',
                    'tests/generated-llvm-sanitizer.min', 'tests/llvm_sanitizer.py',
                    'tools/sanitizer_llvm.py', 'tools/clang-driver.py'}

        def verify(candidate):
            with tempfile.TemporaryDirectory(prefix='actual sanitizer Make rules ') as folder:
                probe = Path(folder)/'probe.mk'
                probe.write_text(candidate + '\n.PHONY: build build/minyarc\nbuild build/minyarc:\n')
                result = subprocess.run(['make', '-rRnp', '-f', str(probe), 'check'],
                                        cwd=ROOT, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                rules = {}
                for line in result.stdout.splitlines():
                    match = re.match(r'^([A-Za-z][\w/-]*):(?: *)([^#]*)$', line)
                    if match:
                        rules.setdefault(match[1], set()).update(match[2].split())
                for gate in ('check', 'check-portable', 'check-sanitize'):
                    self.assertIn('check-generated-llvm-sanitizer', rules.get(gate,set()), gate)
                self.assertTrue(expected <= rules.get('check-generated-llvm-sanitizer',set()))
                commands = result.stdout.split('# GNU Make',1)[0]
                self.assertIn('python3 tests/generated-llvm-sanitizer.py', commands)
                self.assertIn('--artifacts "$artifacts/run"', commands)
                self.assertIn((ROOT/'build/generated-llvm-sanitizer-').as_posix(),
                              commands.replace('\\','/'))
        verify(fragment)
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
        self.assertEqual(len(rules),5)
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
                commands = result.stdout.split('# GNU Make', 1)[0]
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
                    self.assertIn(f'cmp build/{family}-stage2.ll build/{family}-stage3.ll', commands)

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
                commands = result.stdout.split('# GNU Make', 1)[0]
                self.assertEqual(commands.count('"/selected-pinned/python"'), 6)
                self.assertEqual(commands.count('mktemp -d "'), 6)
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
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        for target in native | sanitize:
            self.assertEqual(targets.count(target), 1)
            self.assertIn(target, workflow)
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
                commands = result.stdout.split('# GNU Make', 1)[0]
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
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('check-quic\n', workflow)
        self.assertIn('check-quic-sanitize\n', workflow)
        format_tree = ast.parse((ROOT / 'scripts/format.py').read_text())
        version = next(ast.literal_eval(node.value) for node in format_tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(x, ast.Name) and x.id == 'VERSION' for x in node.targets))
        self.assertEqual(version, '23.1.2')
        self.assertIn('clang-format==23.1.2', workflow)
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
                commands = result.stdout.split('# GNU Make', 1)[0]
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
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('check-quic\n', workflow)
        self.assertIn('check-quic-sanitize\n', workflow)
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
                commands = result.stdout.split('# GNU Make', 1)[0]
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
            commands = result.stdout.split('# GNU Make', 1)[0]
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



if __name__ == '__main__':
    unittest.main()
