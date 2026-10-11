#!/usr/bin/env python3
"""Adversarial checks of the independent long-run observer."""
import importlib.util
import ctypes
import json
import os
import selectors
import signal
from pathlib import Path
import subprocess
import sys
import time
import unittest

spec = importlib.util.spec_from_file_location('observer', Path(__file__).with_name('soak_observer.py'))
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

class ObserverTests(unittest.TestCase):
    def child(self, source):
        return subprocess.Popen([sys.executable, '-c', source], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)

    def test_silent_peer_cannot_hold_the_harness(self):
        child = self.child('import time; time.sleep(10)')
        started = time.monotonic()
        try:
            with self.assertRaises(TimeoutError):
                list(observer.observe(child, 0.1, 0.02))
            self.assertIsNotNone(child.poll())
            self.assertLess(time.monotonic() - started, 2)
        finally:
            if child.poll() is None: child.kill(); child.wait()

    def test_fragmented_lines_and_unterminated_eof(self):
        child = self.child('import os,time; os.write(1,b"first"); time.sleep(.03); os.write(1,b"\\nsecond")')
        lines = [event['line'] for event in observer.observe(child, 2, .01) if 'line' in event]
        self.assertEqual(lines, ['first', 'second'])
        self.assertEqual(child.wait(), 0)

    def test_unbounded_output_without_newlines_is_rejected(self):
        child = self.child('import os,time; os.write(1,b"x"*100000); time.sleep(10)')
        with self.assertRaises(ValueError): list(observer.observe(child, 2, .02))
        self.assertIsNotNone(child.poll())

    def test_exited_parent_with_stdout_held_by_descendant_times_out(self):
        child = self.child('import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time; time.sleep(10)"])')
        with self.assertRaises(TimeoutError): list(observer.observe(child, .15, .02))
        self.assertEqual(child.poll(), 0)


    @unittest.skipUnless(sys.platform.startswith('linux'), 'owned orphan reaping uses Linux subreaper')
    def test_interrupt_reaps_isolated_child_and_propagates(self):
        # Scope adoption to this test so the deliberately leaking RED can also
        # be cleaned up and reaped; this is not the production observer.
        libc = ctypes.CDLL(None, use_errno=True)
        previous = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        source = r"""
import json, signal, subprocess, sys
sys.path.insert(0, sys.argv[1])
from soak_observer import observe
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True)
signal.signal(signal.SIGTERM, signal.SIG_DFL)
signal.signal(signal.SIGINT, signal.default_int_handler)
previous = {value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)}
try:
    events = observe(child, 10, .01)
    next(events)
    print(json.dumps({'ready': child.pid}), flush=True)
    list(events)
except BaseException as error:
    print(json.dumps({'interruption': type(error).__name__,
                      'child_status': child.poll(),
                      'restored': all(signal.getsignal(value) == handler
                                      for value, handler in previous.items())}), flush=True)
    raise SystemExit(17)
raise SystemExit('interruption unexpectedly completed')
"""
        try:
            for value in (signal.SIGTERM, signal.SIGINT):
                with self.subTest(signal=value):
                    driver = subprocess.Popen(
                        [sys.executable, '-c', source, str(Path(__file__).parent)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        start_new_session=True)
                    child_pid = None
                    try:
                        with selectors.DefaultSelector() as ready:
                            ready.register(driver.stdout, selectors.EVENT_READ)
                            self.assertTrue(ready.select(2), 'observer did not enter before interruption')
                        child_pid = json.loads(driver.stdout.readline())['ready']
                        self.assertEqual(os.getpgid(child_pid), child_pid)
                        started = time.monotonic()
                        driver.send_signal(value)
                        stdout, stderr = driver.communicate(timeout=2)
                        def exists(target, group=False):
                            try:
                                (os.killpg if group else os.kill)(target, 0)
                                return True
                            except ProcessLookupError:
                                return False
                        print(json.dumps({'signal': value, 'driver_status': driver.returncode,
                                          'child_exists': exists(child_pid),
                                          'group_exists': exists(child_pid, True),
                                          'elapsed_seconds': time.monotonic() - started}), flush=True)
                        self.assertEqual(driver.returncode, 17, stderr)
                        result = json.loads(stdout)
                        self.assertEqual(result['interruption'], 'KeyboardInterrupt')
                        self.assertIsNotNone(result['child_status'])
                        self.assertTrue(result['restored'])
                        self.assertEqual(stderr, '')
                        self.assertLess(time.monotonic() - started, 2)
                        with self.assertRaises(ProcessLookupError): os.kill(child_pid, 0)
                        with self.assertRaises(ProcessLookupError): os.killpg(child_pid, 0)
                    finally:
                        if driver.poll() is None:
                            os.killpg(driver.pid, signal.SIGKILL)
                            driver.communicate(timeout=2)
                        if child_pid is not None:
                            try: os.killpg(child_pid, signal.SIGKILL)
                            except ProcessLookupError: pass
                            try: os.waitpid(child_pid, 0)
                            except ChildProcessError: pass
        finally:
            self.assertEqual(libc.prctl(36, previous.value, 0, 0, 0), 0)

    def test_previous_signal_dispositions_restored_on_success_and_failure(self):
        previous = {value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)}
        def sentinel(signum, frame): raise AssertionError('previous handler unexpectedly invoked')
        try:
            for value in previous: signal.signal(value, sentinel)
            for timeout, expected in ((1, None), (.05, TimeoutError)):
                child = self.child('import time; time.sleep(.2)')
                if expected:
                    with self.assertRaises(expected): list(observer.observe(child, timeout, .01))
                else:
                    list(observer.observe(child, timeout, .01))
                for value in previous: self.assertIs(signal.getsignal(value), sentinel)
        finally:
            for value, handler in previous.items(): signal.signal(value, handler)

    def test_rss_trend_distinguishes_plateau_from_growth(self):
        plateau = [{'elapsed_seconds': n, 'rss_kib': 1000 + n % 3} for n in range(100)]
        growth = [{'elapsed_seconds': n, 'rss_kib': 1000 + n * 100} for n in range(100)]
        self.assertLess(abs(observer.memory_summary(plateau, 10)['rss_slope_kib_per_second']), .01)
        self.assertAlmostEqual(observer.memory_summary(growth, 10)['rss_slope_kib_per_second'], 100)

if __name__ == '__main__': unittest.main()
