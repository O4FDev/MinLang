#!/usr/bin/env python3
"""Validate complete-build measurement aggregation without timing thresholds."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('incremental_metrics', ROOT / 'tests/incremental-module-performance.py')
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)
budget_spec = importlib.util.spec_from_file_location('self_compile_metric_budget', ROOT / 'tests/self-compile-budget.py')
budget = importlib.util.module_from_spec(budget_spec)
budget_spec.loader.exec_module(budget)


class PerformanceMetrics(unittest.TestCase):
    def test_phase_totals_and_peak_memory_keep_distinct_units(self):
        phases = [
            {'cpu_ms': 2.5, 'wall_ms': 11, 'peak_rss_mib': 8},
            {'cpu_ms': 7.5, 'wall_ms': 3, 'peak_rss_mib': 23},
            {'cpu_ms': 1, 'wall_ms': 2, 'peak_rss_mib': 5},
        ]
        original = copy.deepcopy(phases)
        self.assertEqual(metrics.combine_phase_measurements(phases),
                         {'cpu_ms': 11, 'wall_ms': 16, 'peak_rss_mib': 23})
        self.assertEqual(phases, original)
        # Repeated samples are summarized by medians for time, maximum for peak
        # memory: neither summing repetitions nor averaging peaks is correct.
        self.assertEqual(metrics.summarize_measurements(phases),
                         {'cpu_ms': 2.5, 'wall_ms': 3, 'peak_rss_mib': 23})

    def test_unavailable_measurements_never_become_zero_or_partial_totals(self):
        for missing in ({'cpu_ms': None, 'wall_ms': 4}, {'wall_ms': 4}):
            for rows in ([missing, {'cpu_ms': 20, 'wall_ms': 8}],
                         [{'cpu_ms': 20, 'wall_ms': 8}, missing]):
                with self.subTest(rows=rows):
                    self.assertEqual(metrics.combine_phase_measurements(rows), {'cpu_ms': None, 'wall_ms': 12})
                    self.assertEqual(metrics.summarize_measurements(rows), {'cpu_ms': None, 'wall_ms': 6})
        rows = [{'cpu_ms': 2, 'wall_ms': 3, 'peak_rss_mib': 8}, {'cpu_ms': 4, 'wall_ms': 5}]
        self.assertEqual(metrics.combine_phase_measurements(rows),
                         {'cpu_ms': 6, 'wall_ms': 8, 'peak_rss_mib': None})
        self.assertEqual(metrics.summarize_measurements(rows)['peak_rss_mib'], None)

    def test_invalid_measurements_cannot_silently_disable_comparisons(self):
        # NaN would make a threshold comparison false; bool is not a timing.
        for aggregate in (metrics.combine_phase_measurements, metrics.summarize_measurements):
            with self.assertRaises(ValueError):
                aggregate([])
            for key in ('cpu_ms', 'wall_ms', 'peak_rss_mib'):
                for invalid in (-1, float('nan'), float('inf'), -float('inf'), True, '3'):
                    with self.subTest(aggregate=aggregate.__name__, key=key, invalid=invalid):
                        row = {'cpu_ms': 1, 'wall_ms': 2, 'peak_rss_mib': 3}
                        row[key] = invalid
                        with self.assertRaises(ValueError):
                            aggregate([row])

    def test_real_measurement_producer_reports_unavailable_cpu(self):
        with patch.object(metrics.graphs, 'resource', None):
            result = metrics.graphs.timed([sys.executable, '-c', 'pass'])
        self.assertIsNone(result['cpu_ms'])
        self.assertGreaterEqual(result['wall_ms'], 0)

    def run_driver(self, *, link, cpu_available, enforce=False, inflated_driver=False):
        """Run the real report/phase orchestration with controlled measurements.

        Fixture artifacts and cache transitions replace actual compilation:
        this checks reporting independently of variable host performance.
        """
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            build = root / 'build'
            build.mkdir()
            for filename in ('minyar-module-build', 'minyarc-modules', 'minyarc', 'minyar-runtime.o'):
                (build / filename).write_bytes(filename.encode())
            output = root / 'report.json'
            count = 400 if enforce else 1

            def timed(command):
                label = Path(command[0]).name
                if label == 'driver':
                    cache = Path(command[-2])
                    cache.mkdir(exist_ok=True)
                    cold = not (cache / 'case.cache').exists()
                    entry = Path(command[2])
                    library = entry.parent / 'm0.min'
                    edited = 'let changed' in entry.read_text() or 'result = result + 2' in library.read_text()
                    counters = (0, count + 1, 0, 0, 0, 0) if cold else (
                        (count + 1, 1, 0, count, 0, 0) if edited else (count + 1, 0, 0, count + 1, 0, 0))
                    (cache / 'case.cache').write_bytes(b'cache')
                    Path(command[-1]).write_text(' '.join(map(str, counters)))
                cpu, wall = {'driver': (100 if inflated_driver else 1, 2),
                             'production': (50 if inflated_driver else 5, 7), 'clang': (2, 3)}[label]
                return {'cpu_ms': cpu if cpu_available else None, 'wall_ms': wall}

            argv = ['metric-control', '--sizes', str(count), '--shapes', 'wide', '--repeats', '2',
                    '--output', str(output)]
            if link:
                argv.append('--link')
            if enforce:
                argv.append('--enforce')
            version = subprocess.CompletedProcess(['clang', '--version'], 0, 'controlled clang version\n', '')
            with patch.object(metrics, 'ROOT', root), patch.object(metrics.graphs, 'timed', side_effect=timed), \
                    patch.object(metrics.subprocess, 'run', return_value=version), \
                    patch.object(metrics.platform, 'platform', return_value='controlled host'), \
                    patch.object(sys, 'argv', argv), patch('sys.stdout', new_callable=io.StringIO):
                metrics.main()
            return json.loads(output.read_text())

    def test_complete_build_report_sums_each_phase_and_retains_inputs(self):
        report = self.run_driver(link=True, cpu_available=True)
        self.assertEqual(len(report['rows']), 5)
        for row in report['rows']:
            self.assertEqual(row['median_ms'], {'driver': {'cpu_ms': 3, 'wall_ms': 5},
                                              'production': {'cpu_ms': 7, 'wall_ms': 10}})
            for sample in row['samples']['driver']:
                self.assertEqual(sample['frontend_ms'], {'cpu_ms': 1, 'wall_ms': 2})
                self.assertEqual(sample['link_ms'], {'cpu_ms': 2, 'wall_ms': 3})
            self.assertEqual(row['cpu_ceiling_status'], 'not-requested')

    def test_complete_build_without_cpu_and_frontend_ceiling_are_reported(self):
        for link, enforce in ((True, False), (False, True)):
            with self.subTest(link=link, enforce=enforce):
                report = self.run_driver(link=link, cpu_available=False, enforce=enforce)
                self.assertEqual(len(report['rows']), 5)
                for row in report['rows']:
                    for label in ('driver', 'production'):
                        self.assertIsNone(row['median_ms'][label]['cpu_ms'])
                    self.assertEqual(row['median_ms']['driver']['wall_ms'], 5 if link else 2)
                    self.assertEqual(row['median_ms']['production']['wall_ms'], 10 if link else 7)
                    self.assertEqual(row['cpu_ceiling_status'], 'unavailable' if enforce else 'not-requested')

    def test_available_cpu_still_enforces_the_regression_ceiling(self):
        with self.assertRaisesRegex(AssertionError, 'incremental CPU ceiling exceeded'):
            self.run_driver(link=False, cpu_available=True, enforce=True, inflated_driver=True)

    def test_profiled_failures_and_stale_or_wrong_output_are_rejected(self):
        for mode, message in (('failure', 'failed with status 1'),
                              ('no-output', 'produced no LLVM'),
                              ('wrong-output', 'differs from the fixed-point')):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as name:
                output, reference = Path(name) / 'output.ll', Path(name) / 'reference.ll'
                reference.write_bytes(b'fixed point\n')
                output.write_bytes(reference.read_bytes())

                def profiled(command, **kwargs):
                    self.assertFalse(output.is_file(), 'stale output was not removed before profiling')
                    if mode == 'wrong-output':
                        output.write_bytes(b'wrong compiler output\n')
                    return subprocess.CompletedProcess(command, 1 if mode == 'failure' else 0,
                                                       '', '42 instructions retired\n')

                with patch.object(budget, 'OUTPUT', output), patch.object(budget, 'REFERENCE', reference), \
                        patch.object(budget.sys, 'platform', 'darwin'), patch.object(budget.Path, 'exists', return_value=True), \
                        patch.object(budget.subprocess, 'run', side_effect=profiled) as run:
                    with self.assertRaisesRegex(SystemExit, message):
                        budget.retired_instructions()
                    self.assertEqual(run.call_count, 1)

    def test_each_profile_sample_requires_fresh_fixed_point_output(self):
        with tempfile.TemporaryDirectory() as name:
            output, reference = Path(name) / 'output.ll', Path(name) / 'reference.ll'
            reference.write_bytes(b'fixed point\n')
            counts = iter((11, 7, 9, 10, 8))

            def profiled(command, **kwargs):
                self.assertFalse(output.is_file())
                output.write_bytes(reference.read_bytes())
                return subprocess.CompletedProcess(command, 0, '', f'{next(counts)} instructions retired\n')

            with patch.object(budget, 'OUTPUT', output), patch.object(budget, 'REFERENCE', reference), \
                    patch.object(budget.sys, 'platform', 'darwin'), patch.object(budget.Path, 'exists', return_value=True), \
                    patch.object(budget.subprocess, 'run', side_effect=profiled) as run:
                self.assertEqual(budget.retired_instructions(), 7)
                self.assertEqual(run.call_count, 5)

    def test_profile_reference_is_required_and_valid_missing_counter_is_unavailable(self):
        with tempfile.TemporaryDirectory() as name:
            output, reference = Path(name) / 'output.ll', Path(name) / 'reference.ll'

            def profiled(command, **kwargs):
                output.write_bytes(reference.read_bytes())
                return subprocess.CompletedProcess(command, 0, '', 'no hardware counter on this host\n')

            with patch.object(budget, 'OUTPUT', output), patch.object(budget, 'REFERENCE', reference), \
                    patch.object(budget.sys, 'platform', 'darwin'), patch.object(budget.Path, 'exists', return_value=True), \
                    patch.object(budget.subprocess, 'run', side_effect=profiled) as run:
                with self.assertRaisesRegex(SystemExit, 'requires the fixed-point'):
                    budget.retired_instructions()
                self.assertEqual(run.call_count, 0)
                reference.write_bytes(b'fixed point\n')
                self.assertIsNone(budget.retired_instructions())
                self.assertEqual(run.call_count, 1)

    def test_later_profile_failure_cannot_reuse_an_earlier_good_sample(self):
        with tempfile.TemporaryDirectory() as name:
            output, reference = Path(name) / 'output.ll', Path(name) / 'reference.ll'
            reference.write_bytes(b'fixed point\n')
            samples = []

            def profiled(command, **kwargs):
                self.assertFalse(output.is_file())
                samples.append(command)
                if len(samples) == 1:
                    output.write_bytes(reference.read_bytes())
                    return subprocess.CompletedProcess(command, 0, '', '7 instructions retired\n')
                return subprocess.CompletedProcess(command, 1, '', '1 instructions retired\n')

            with patch.object(budget, 'OUTPUT', output), patch.object(budget, 'REFERENCE', reference), \
                    patch.object(budget.sys, 'platform', 'darwin'), patch.object(budget.Path, 'exists', return_value=True), \
                    patch.object(budget.subprocess, 'run', side_effect=profiled):
                with self.assertRaisesRegex(SystemExit, 'failed with status 1'):
                    budget.retired_instructions()
            self.assertEqual(len(samples), 2)

    def test_each_timed_sample_requires_fresh_output_outside_timing_interval(self):
        # Warm-up and first measured sample succeed. The second measured sample
        # must not reuse their output or disappear behind the earlier timing.
        for mode, message in ((None, None), ('failure', 'failed with status 1'),
                              ('no-output', 'produced no LLVM'), ('wrong-output', 'differs from the fixed-point')):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as name:
                output, reference, compiler = (Path(name) / file for file in ('output.ll', 'reference.ll', 'compiler'))
                reference.write_bytes(b'fixed point\n')
                compiler.write_bytes(b'controlled fixture')
                output.write_bytes(reference.read_bytes())
                state = {'active': False, 'calls': 0, 'unlinks': 0, 'validations': 0}
                ticks = iter((10, 10.001, 20, 20.002))
                original_unlink = Path.unlink
                original_validate = budget.validate_compile_output

                def unlink(path, *args, **kwargs):
                    if path == output:
                        self.assertFalse(state['active'], 'cleanup entered timed interval')
                        state['unlinks'] += 1
                    return original_unlink(path, *args, **kwargs)

                def clock():
                    state['active'] = not state['active']
                    return next(ticks)

                def compile_once():
                    self.assertFalse(output.is_file(), 'stale output survived into sample')
                    state['calls'] += 1
                    bad = state['calls'] == 3 and mode is not None
                    if not bad or mode == 'wrong-output':
                        output.write_bytes(b'wrong output' if bad else reference.read_bytes())
                    return subprocess.CompletedProcess(['compiler'], 1 if bad and mode == 'failure' else 0, '', '')

                def validate(result, expected, phase='self-compile'):
                    self.assertFalse(state['active'], 'correctness I/O entered timed interval')
                    state['validations'] += 1
                    original_validate(result, expected, phase)

                with patch.object(budget, 'OUTPUT', output), patch.object(budget, 'REFERENCE', reference), \
                        patch.object(budget, 'COMPILER', compiler), patch.object(budget, 'resource', None), \
                        patch.object(budget, 'RUNS', 2), patch.object(budget, 'BATCHES', 1), \
                        patch.object(budget, 'compile_once', side_effect=compile_once), \
                        patch.object(budget, 'validate_compile_output', side_effect=validate), \
                        patch.object(budget, 'retired_instructions', return_value=None), \
                        patch.object(budget.time, 'perf_counter', side_effect=clock), \
                        patch.object(Path, 'unlink', new=unlink), patch('sys.stdout', new_callable=io.StringIO):
                    if message:
                        with self.assertRaisesRegex(SystemExit, message):
                            budget.main()
                    else:
                        budget.main()
                self.assertEqual(state, {'active': False, 'calls': 3, 'unlinks': 3, 'validations': 3})


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Measurement controls require assertions; do not use Python -O')
    unittest.main()
