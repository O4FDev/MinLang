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


    def test_exited_parent_does_not_release_descendant_ownership(self):
        destination = self.root/'exited-parent'
        destination.mkdir()
        owner = self.driver.CommandRecords(destination, {'commands': [], 'finalization_errors': []})
        late = destination/'late.txt'
        script = destination/'exit-parent.py'
        script.write_text(
            'import subprocess,sys\n'
            'code="import pathlib,time; time.sleep(1.5); pathlib.Path("+repr(sys.argv[1])+").write_text(\'late\')"\n'
            'subprocess.Popen([sys.executable,"-c",code])\n'
            'print("PARENT_EXIT",flush=True)\n')
        with self.assertRaises(subprocess.TimeoutExpired):
            owner.run([sys.executable, str(script), str(late)],
                      timeout=.3, label='exited-parent')
        row = owner.report['commands'][0]
        self.assertTrue(row['timed_out'])
        self.assertEqual(row['status'], 0)
        self.assertEqual(row['cleanup']['status'], 'completed')
        time.sleep(1.6)
        self.assertFalse(late.exists())

    def test_secondary_kill_close_wait_failures_preserve_timeout(self):
        class Pipe:
            closed = False
            def close(self):
                raise OSError('injected close failure')
        class Process:
            pid = 70001
            returncode = None
            stdout, stderr = Pipe(), Pipe()
            def communicate(self, **kwargs):
                raise subprocess.TimeoutExpired(['owned'], .1)
            def poll(self):
                return None
            def kill(self):
                raise OSError('injected kill failure')
            def wait(self, **kwargs):
                raise OSError('injected wait failure')
        destination = self.root/'secondary-failure'
        destination.mkdir()
        report = {'commands': [], 'finalization_errors': []}
        owner = self.driver.CommandRecords(destination, report)
        with patch.object(self.driver, 'windows_host', return_value=False), \
                patch.object(self.driver.subprocess, 'Popen', return_value=Process()), \
                patch.object(self.driver, 'terminate_process_tree',
                             side_effect=OSError('injected tree failure')):
            with self.assertRaises(subprocess.TimeoutExpired) as captured:
                owner.run([sys.executable, '-c', 'pass'],
                          timeout=.1, label='secondary-failure')
        self.assertTrue(report['commands'][0]['timed_out'])
        self.assertEqual(report['commands'][0]['cleanup']['status'], 'failed')
        messages = '\n'.join(row['message'] for row in report['finalization_errors'])
        for expected in ('kill failure', 'close failure', 'wait failure'):
            self.assertIn(expected, messages)
            self.assertTrue(any(expected in note
                                for note in getattr(captured.exception, '__notes__', [])))


    def test_windows_job_invalid_timeout_refuses_before_creation(self):
        from windows_job_owner import owned_job_run
        class API:
            def create_job(self):
                raise AssertionError('Invalid preparation executed a native API')
            def close(self):
                return []
        for timeout in (0, -1, True, float('inf'), float('nan')):
            request = {'timeout_seconds': timeout}
            report = {}
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, 'positive and finite'):
                    owned_job_run(API(), request, report)
                self.assertFalse(report['started'])
                self.assertFalse(report['resumed'])
                self.assertFalse(report['closed'])

    def test_windows_job_cleanup_failures_preserve_assignment_error(self):
        from windows_job_owner import owned_job_run
        from types import SimpleNamespace
        class API:
            def create_job(self):
                return 'owned'
            def spawn_suspended(self, *args):
                return SimpleNamespace(pid=123, tid=456)
            def verify_assignment(self, *args):
                raise ValueError('original assignment error')
            def terminate(self, *args):
                raise OSError('injected job termination failure')
            def active(self, *args):
                raise OSError('injected accounting failure')
            def close(self):
                self.close_attempted = True
                return [OSError('injected handle closure failure')]
        request = {'argv': ['owned-command'], 'cwd': str(self.root),
                   'stdout_path': str(self.root/'out'), 'stderr_path': str(self.root/'err'),
                   'timeout_seconds': 1}
        api, report = API(), {}
        with self.assertRaisesRegex(ValueError, 'original assignment error') as captured:
            owned_job_run(api, request, report)
        self.assertTrue(api.close_attempted)
        self.assertFalse(report['closed'])
        for message in ('termination failure', 'accounting failure', 'closure failure'):
            self.assertTrue(any(message in note
                                for note in getattr(captured.exception, '__notes__', [])))

    def test_windows_job_assigns_before_resume_and_keeps_descendants_owned(self):
        from windows_job_owner import owned_job_run
        from types import SimpleNamespace
        class API:
            def __init__(self):
                self.calls = []
                self.counts = iter((2, 1, 0))
            def create_job(self):
                self.calls.append('create noninheritable kill-on-close job')
                return 'owned'
            def spawn_suspended(self, *args):
                self.calls.append('atomic job-list suspended spawn')
                return SimpleNamespace(pid=123, tid=456)
            def verify_assignment(self, *args):
                self.calls.append('verify own job')
            def resume(self, *args):
                self.calls.append('resume')
            def active(self, *args):
                count = next(self.counts)
                self.calls.append('active=' + str(count))
                return count
            def status(self, *args):
                self.calls.append('root status')
                return 0
            def close(self):
                self.calls.append('close owned handles')
                return []
        api = API()
        request = {'argv': ['owned-command'], 'cwd': str(self.root),
                   'stdout_path': str(self.root/'out'), 'stderr_path': str(self.root/'err'),
                   'timeout_seconds': 1}
        report = {}
        owned_job_run(api, request, report)
        self.assertEqual(api.calls[:4], [
            'create noninheritable kill-on-close job', 'atomic job-list suspended spawn',
            'verify own job', 'resume'])
        self.assertLess(api.calls.index('active=0'), api.calls.index('close owned handles'))
        self.assertTrue(report['closed'])
        self.assertFalse(report['job_inheritable'])
        self.assertFalse(report['breakaway_allowed'])

    def test_windows_job_exited_root_child_timeout_requires_zero_count(self):
        from windows_job_owner import owned_job_run
        from types import SimpleNamespace
        class API:
            def create_job(self):
                self.terminated = False
                return 'owned'
            def spawn_suspended(self, *args):
                return SimpleNamespace(pid=123, tid=456)
            def verify_assignment(self, *args):
                pass
            def resume(self, *args):
                pass
            def active(self, *args):
                return 0 if self.terminated else 1
            def terminate(self, *args):
                self.terminated = True
            def status(self, *args):
                return 0  # Root exit does not prove its child ended.
            def close(self):
                return []
        request = {'argv': ['owned-command'], 'cwd': str(self.root),
                   'stdout_path': str(self.root/'out'), 'stderr_path': str(self.root/'err'),
                   'timeout_seconds': 1}
        api, report = API(), {}
        with patch('windows_job_owner.time.monotonic', side_effect=(0, 2, 3)):
            with self.assertRaises(subprocess.TimeoutExpired):
                owned_job_run(api, request, report)
        self.assertTrue(api.terminated)
        self.assertEqual(report['active_processes'], 0)
        self.assertTrue(report['closed'])
        self.assertTrue(report['timed_out'])
        self.assertEqual(report['status'], 0)

    def test_windows_assignment_or_close_failure_never_releases_uncontained_code(self):
        from windows_job_owner import owned_job_run
        from types import SimpleNamespace
        class API:
            resumed = False
            def create_job(self):
                self.terminated = False
                return 'owned'
            def spawn_suspended(self, *args):
                return SimpleNamespace(pid=123, tid=456)
            def verify_assignment(self, *args):
                raise ValueError('controlled assignment failure')
            def resume(self, *args):
                self.resumed = True
            def active(self, *args):
                return 0 if self.terminated else 1
            def terminate(self, *args):
                self.terminated = True
            def status(self, *args):
                return 253
            def close(self):
                raise OSError('controlled close failure')
        request = {'argv': ['owned-command'], 'cwd': str(self.root),
                   'stdout_path': str(self.root/'out'), 'stderr_path': str(self.root/'err'),
                   'timeout_seconds': 1}
        api, report = API(), {}
        with self.assertRaisesRegex(ValueError, 'controlled assignment failure') as captured:
            owned_job_run(api, request, report)
        self.assertFalse(api.resumed)
        self.assertFalse(report['closed'])
        self.assertTrue(any('controlled close failure' in note
                            for note in getattr(captured.exception, '__notes__', [])))

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
        self.assertEqual(row['cleanup']['action'],
                         'owned-Windows-job' if self.driver.windows_host() else 'terminate_process_tree')
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
        class Pipe:
            closed = False
            def close(self):
                self.closed = True
        class Process:
            pid = 70002
            returncode = None
            stdout, stderr = Pipe(), Pipe()
            calls = 0
            def communicate(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired(['controlled'], .1)
                return b'', b''
            def kill(self):
                self.returncode = -9
        destination = self.root/'cleanup-error'
        destination.mkdir()
        report = {'commands': [], 'finalization_errors': []}
        owner = self.driver.CommandRecords(destination, report)
        with patch.object(self.driver, 'windows_host', return_value=False), \
                patch.object(self.driver.subprocess, 'Popen', return_value=Process()), \
                patch.object(self.driver, 'terminate_process_tree',
                             side_effect=RuntimeError('controlled cleanup failure')):
            with self.assertRaises(subprocess.TimeoutExpired):
                owner.run([sys.executable, '-c', 'pass'], timeout=.1, label='cleanup-error')
        row = report['commands'][0]
        self.assertTrue(row['timed_out'])
        self.assertEqual(row['cleanup']['status'], 'failed')
        self.assertTrue(any('controlled cleanup failure' in error['message']
                            for error in row['cleanup']['errors']))
        self.assertEqual(row['status'], -9)

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

    def test_windows_helper_launch_never_requests_a_posix_session(self):
        import ast
        tree = ast.parse((ROOT/'tests/windows_job_owner.py').read_text())
        launches = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == 'Popen']
        self.assertEqual(len(launches), 1)
        option = next(value for value in launches[0].keywords if value.arg == 'start_new_session')
        self.assertIs(ast.literal_eval(option.value), False)
        # This source contract alone never certifies a Windows native API call.


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Observability harness requires Python assertions; do not use -O')
    unittest.main()
