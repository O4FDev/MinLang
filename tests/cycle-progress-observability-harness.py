#!/usr/bin/env python3
"""Owned subprocess and failure-retention controls for mocked idle observation."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT/'tests/cycle-progress-observability.py'


def load_driver():
    spec = importlib.util.spec_from_file_location('idle_observability_control', DRIVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ObservabilityHarness(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='idle observation control ')
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.driver = load_driver()

    def test_optimized_python_refuses_before_compilation_or_evidence(self):
        for mode in ('flag', 'environment'):
            destination = self.root/mode
            command = [sys.executable]
            env = dict(os.environ)
            env.pop('PYTHONOPTIMIZE', None)
            if mode == 'flag':
                command.append('-O')
            else:
                env['PYTHONOPTIMIZE'] = '1'
            command += [str(DRIVER), '--evidence', str(destination)]
            result = subprocess.run(command, env=env, capture_output=True, timeout=5)
            with self.subTest(mode=mode):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'requires Python assertions', result.stderr)
                self.assertFalse(destination.exists())

    def test_raw_streams_are_retained_without_text_normalization(self):
        destination = self.root/'raw'
        destination.mkdir()
        report = {'commands': [], 'finalization_errors': []}
        owner = self.driver.CommandRecords(destination, report)
        command = [sys.executable, '-c',
                   "import os; os.write(1,b'raw\\r\\n\\xff'); os.write(2,b'err\\r\\n\\xfe')"]
        result = owner.run(command, timeout=5, label='raw')
        self.assertEqual(result.stdout, b'raw\r\n\xff')
        self.assertEqual(result.stderr, b'err\r\n\xfe')
        row = report['commands'][0]
        for name, expected in (('stdout', result.stdout), ('stderr', result.stderr)):
            self.assertEqual((destination/row[name+'_path']).read_bytes(), expected)
            self.assertEqual(row[name+'_bytes'], len(expected))
        self.assertFalse(row['timed_out'])
        self.assertEqual(row['status'], 0)
        self.assertTrue(row['executable_sha256'])

    def test_owned_timeout_ends_descendant_then_next_command_runs(self):
        destination = self.root/'timeout'
        destination.mkdir()
        report = {'commands': [], 'finalization_errors': []}
        owner = self.driver.CommandRecords(destination, report)
        child_pid = destination/'child.pid'
        late = destination/'late.txt'
        script = destination/'parent.py'
        script.write_text(
            'import json,os,subprocess,sys,time\n'
            'code="import pathlib,time; time.sleep(1.5); pathlib.Path("+repr(sys.argv[2])+").write_text(\'late\')"\n'
            'child=subprocess.Popen([sys.executable,"-c",code])\n'
            'open(sys.argv[1],"w").write(str(child.pid))\n'
            'print("OWNED_CHILD",child.pid,flush=True)\n'
            'time.sleep(30)\n')
        with self.assertRaises(subprocess.TimeoutExpired):
            owner.run([sys.executable, str(script), str(child_pid), str(late)],
                      timeout=.3, label='owned-timeout')
        row = report['commands'][0]
        self.assertTrue(row['timed_out'])
        self.assertEqual(row['cleanup']['action'], 'terminate_process_tree')
        self.assertEqual(row['cleanup']['status'], 'completed')
        self.assertIsNotNone(row['status'])
        self.assertTrue(child_pid.is_file())
        pid = int(child_pid.read_text())
        time.sleep(1.6)
        self.assertFalse(late.exists(), 'timed-out descendant remained executable')
        if sys.platform.startswith('linux'):
            stat = Path('/proc')/str(pid)/'stat'
            if stat.exists():
                state = stat.read_text().split(') ', 1)[1].split()[0]
                self.assertEqual(state, 'Z', 'owned descendant is still live')
        result = owner.run([sys.executable, '-c', 'print("next case")'],
                           timeout=5, label='next-case')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.rstrip(b'\r\n'), b'next case')
        self.assertEqual(report['commands'][1]['status'], 0)

    def test_cleanup_failure_is_recorded_and_never_a_pass(self):
        destination = self.root/'cleanup-error'
        destination.mkdir()
        report = {'commands': [], 'finalization_errors': []}
        owner = self.driver.CommandRecords(destination, report)
        with patch.object(self.driver, 'terminate_process_tree',
                          side_effect=RuntimeError('controlled cleanup failure')):
            with self.assertRaises(subprocess.TimeoutExpired):
                owner.run([sys.executable, '-c', 'import time; time.sleep(30)'],
                          timeout=.1, label='cleanup-error')
        row = report['commands'][0]
        self.assertTrue(row['timed_out'])
        self.assertEqual(row['cleanup']['status'], 'failed')
        self.assertIn('controlled cleanup failure', row['cleanup']['exception'])
        self.assertIsNotNone(row['status'])

    def test_finalization_preserves_primary_exception(self):
        report = {'passed': False, 'finalization_errors': []}
        primary = ValueError('original failure')
        with patch.object(Path, 'write_text', side_effect=OSError('manifest blocked')):
            self.driver.finalize(self.root, report, primary)
        self.assertEqual(str(primary), 'original failure')
        self.assertFalse(report['passed'])
        self.assertTrue(any('manifest blocked' in row['message']
                            for row in report['finalization_errors']))
        self.assertTrue(any('manifest blocked' in note
                            for note in getattr(primary, '__notes__', [])))
        with patch.object(Path, 'write_text', side_effect=OSError('manifest blocked')):
            with self.assertRaisesRegex(OSError, 'manifest blocked'):
                self.driver.finalize(self.root, report, None)

    def test_setup_failure_has_durable_nonpassing_manifest(self):
        destination = self.root/'setup-failure'
        with patch.object(self.driver, 'contract', side_effect=ValueError('contract setup red')):
            with self.assertRaisesRegex(ValueError, 'contract setup red'):
                self.driver.main(['--evidence', str(destination)])
        report = json.loads((destination/'manifest.json').read_text())
        self.assertFalse(report['passed'])
        self.assertIn('contract setup red', report['exception'])
        self.assertEqual(report['cases'], [])

    def test_windows_mode_never_requests_a_posix_session(self):
        destination = self.root/'native-mode'
        destination.mkdir()
        report = {'commands': [], 'finalization_errors': []}
        owner = self.driver.CommandRecords(destination, report)
        real_popen = subprocess.Popen
        options = []
        def spawn(*args, **kwargs):
            options.append(kwargs['start_new_session'])
            return real_popen(*args, **kwargs)
        with patch.object(self.driver, 'windows_host', return_value=True), \
                patch.object(self.driver.subprocess, 'Popen', side_effect=spawn):
            result = owner.run([sys.executable, '-c', 'print(42)'],
                               timeout=5, label='no-posix-session')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(options, [False])


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Observability harness requires Python assertions; do not use -O')
    unittest.main()
