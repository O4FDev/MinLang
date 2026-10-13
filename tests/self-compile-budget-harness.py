#!/usr/bin/env python3
"""A failed measurement must never look like a cheap successful compilation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('budget', ROOT / 'tests/self-compile-budget.py')
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class BudgetHarness(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.expected = b'define i32 @main(i32 %argc, ptr %argv) { ret i32 0 }\n'
        reference = root / 'reference.ll'
        reference.write_bytes(self.expected)
        for name, value in (('OUTPUT', root / 'output.ll'),):
            patch = mock.patch.object(budget, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_valid_compiler_output_may_change_formatting(self):
        budget.OUTPUT.write_text('define i32 @main(i32 %argc, ptr %argv) {\n  ret i32 0\n}\n')
        budget.validate_compile_output(subprocess.CompletedProcess([], 0, '', ''))

    def test_structural_output_cannot_replace_compiler_behavior(self):
        budget.OUTPUT.write_bytes(self.expected)
        with self.assertRaisesRegex(SystemExit, 'compiler behavior failed'):
            budget.check_compiler_behavior(budget.OUTPUT)

    def counter_runs(self, measurements):
        remaining = iter(measurements)
        def run(*args, **kwargs):
            result = next(remaining)
            if result.returncode == 0:
                budget.OUTPUT.write_bytes(self.expected)
            return result
        return run

    def test_failed_counter_run_cannot_win_the_instruction_budget(self):
        success = subprocess.CompletedProcess([], 0, '', '100000000 instructions retired\n')
        failure = subprocess.CompletedProcess([], 1, '',
            'Minyar stopped: incomplete compilation\n10 instructions retired\n')
        for failed_at in (0, 2, 4):
            measurements = [success] * 5
            measurements[failed_at] = failure
            with self.subTest(failed_at=failed_at), \
                 mock.patch.object(budget.sys, 'platform', 'darwin'), \
                 mock.patch.object(budget.Path, 'exists', return_value=True), \
                 mock.patch.object(budget.subprocess, 'run', side_effect=self.counter_runs(measurements)):
                with self.assertRaisesRegex(SystemExit, 'incomplete compilation'):
                    budget.retired_instructions()

    def test_successful_counter_batch_keeps_existing_minimum_policy(self):
        measurements = [subprocess.CompletedProcess([], 0, '',
            f'{count} instructions retired\n') for count in (91, 87, 93, 89, 90)]
        with mock.patch.object(budget.sys, 'platform', 'darwin'), \
             mock.patch.object(budget.Path, 'exists', return_value=True), \
             mock.patch.object(budget.subprocess, 'run', side_effect=self.counter_runs(measurements)):
            self.assertEqual(budget.retired_instructions(), 87)

    def comparison_fixture(self, root):
        (root / 'build').mkdir()
        paths = {name: root / name for name in ('current', 'previous', 'input', 'clang')}
        paths['runtime'] = root / 'build/minyar-compiler-runtime.ll'
        for name, path in paths.items():
            path.write_text(name)
        toolchain = {'llvm_version': '23.1.2', 'llvm_cc': {'path': str(paths['clang'])},
                     'flags': {'LLVM_FLAGS': '-O2', 'COMPILER_LTO_FLAGS': '-flto=thin'}}
        (root / 'build/.toolchain.json').write_text(json.dumps(toolchain))
        manifest = root / 'configuration.json'
        manifest.write_text(json.dumps({'toolchain': toolchain,
            'clang': budget.file_identity(paths['clang']),
            'artifacts': {name: budget.file_identity(path) for name, path in paths.items() if name != 'clang'}}))
        return paths, manifest, root / 'pairs.json'

    def test_wall_pairs_share_input_alternate_and_retain_every_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths, manifest, report = self.comparison_fixture(root)
            calls = []
            def compile(command, **kwargs):
                calls.append(Path(command[0]).name)
                self.assertEqual(command[1], str(paths['input']))
                Path(command[2]).write_bytes(self.expected)
                return subprocess.CompletedProcess(command, 0, '', '')
            durations = iter(range(20))
            usage = iter(SimpleNamespace(ru_utime=index, ru_stime=0) for index in range(20))
            with mock.patch.object(budget, 'ROOT', root), mock.patch.object(budget, 'COMPILER', paths['current']), \
                 mock.patch.object(budget, 'RUNS', 2), mock.patch.object(budget, 'BATCHES', 2), \
                 mock.patch.object(budget.subprocess, 'run', side_effect=compile), \
                 mock.patch.object(budget.time, 'perf_counter', side_effect=lambda: next(durations)), \
                 mock.patch.object(budget.resource, 'getrusage', side_effect=lambda _: next(usage)), \
                 mock.patch.object(budget, 'check_compiler_behavior') as behavior:
                result = budget.wall_comparison(paths['previous'], paths['input'], manifest, report)
            self.assertEqual(calls, ['current', 'previous', 'current', 'previous', 'previous', 'current',
                                     'current', 'previous', 'previous', 'current'])
            self.assertEqual(len(result['pairs']), 4)
            self.assertEqual([pair['ratios'] for pair in result['pairs']], [{'wall': 1.0, 'cpu': 1.0}] * 4)
            for clock in ('wall', 'cpu'):
                self.assertEqual(result['summaries'][clock]['median'], 1.0)
                self.assertEqual(result['summaries'][clock]['confidence_interval']['upper'], 1.0)
            self.assertEqual(json.loads(report.read_text()), result)
            self.assertEqual(behavior.call_count, 2)

    def test_wall_comparison_rejects_changed_input_runtime_compiler_and_toolchain(self):
        for changed in ('current', 'previous', 'input', 'runtime', 'clang'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                paths, manifest, report = self.comparison_fixture(root)
                paths[changed].write_text('changed')
                with mock.patch.object(budget, 'ROOT', root), mock.patch.object(budget, 'COMPILER', paths['current']), \
                     mock.patch.object(budget.subprocess, 'run') as launched, self.assertRaises(SystemExit):
                    budget.wall_comparison(paths['previous'], paths['input'], manifest, report)
                launched.assert_not_called()

    def test_failed_wall_pair_retains_failure_and_cannot_be_a_fast_measurement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths, manifest, report = self.comparison_fixture(root)
            calls = []
            def compile(command, **kwargs):
                calls.append(command)
                if len(calls) == 4:
                    return subprocess.CompletedProcess(command, 1, '', 'incomplete compilation')
                Path(command[2]).write_bytes(self.expected)
                return subprocess.CompletedProcess(command, 0, '', '')
            usage = iter(SimpleNamespace(ru_utime=index, ru_stime=0) for index in range(8))
            with mock.patch.object(budget, 'ROOT', root), mock.patch.object(budget, 'COMPILER', paths['current']), \
                 mock.patch.object(budget.subprocess, 'run', side_effect=compile), \
                 mock.patch.object(budget.resource, 'getrusage', side_effect=lambda _: next(usage)), \
                 self.assertRaisesRegex(SystemExit, 'incomplete compilation'):
                budget.wall_comparison(paths['previous'], paths['input'], manifest, report)
            retained = json.loads(report.read_text())
            self.assertEqual(retained['status'], 'failed')
            self.assertEqual(len(retained['pairs']), 1)
            self.assertNotIn('ratios', retained['pairs'][0])

    def test_both_paired_upper_limits_are_inclusive_and_independent(self):
        def result(wall, cpu):
            return {'summaries': {clock: budget.paired_cpu_ratio_summary([ratio] * 31, [1] * 31)
                                 for clock, ratio in (('wall', wall), ('cpu', cpu))}}
        budget.enforce_paired_budget(result(1.02, 1.02))
        for wall, cpu in ((1.020001, 1.0), (1.0, 1.020001)):
            with self.subTest(wall=wall, cpu=cpu), self.assertRaisesRegex(SystemExit, 'paired 95% upper'):
                budget.enforce_paired_budget(result(wall, cpu))
        self.assertEqual((budget.RUNS, budget.BATCHES), (100, 3))
        self.assertEqual(budget.MAX_PEAK_RSS_MIB, 17.0)
        self.assertEqual(budget.MAX_INSTRUCTIONS, 75_000_000)

    def test_zero_wall_or_cpu_measurements_cannot_pass(self):
        for clock in ('wall', 'cpu'):
            with self.subTest(clock=clock), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                paths, manifest, report = self.comparison_fixture(root)
                def compile(command, **kwargs):
                    Path(command[2]).write_bytes(self.expected)
                    return subprocess.CompletedProcess(command, 0, '', '')
                wall = [0.0, 0.0] if clock == 'wall' else [0.0, 1.0]
                cpu = [SimpleNamespace(ru_utime=0, ru_stime=0),
                       SimpleNamespace(ru_utime=0 if clock == 'cpu' else 1, ru_stime=0)]
                with mock.patch.object(budget, 'ROOT', root), mock.patch.object(budget, 'COMPILER', paths['current']), \
                     mock.patch.object(budget.subprocess, 'run', side_effect=compile), \
                     mock.patch.object(budget.time, 'perf_counter', side_effect=wall), \
                     mock.patch.object(budget.resource, 'getrusage', side_effect=cpu), \
                     self.assertRaisesRegex(SystemExit, 'invalid same-input compiler duration'):
                    budget.wall_comparison(paths['previous'], paths['input'], manifest, report)


if __name__ == '__main__':
    unittest.main()
