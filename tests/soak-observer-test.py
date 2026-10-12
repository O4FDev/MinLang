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


    @unittest.skipUnless(sys.platform.startswith('linux'), 'peer process telemetry uses Linux procfs')
    def test_peer_telemetry_measures_real_live_child_then_normal_exit(self):
        spec = importlib.util.spec_from_file_location('quic_soak_telemetry', Path(__file__).with_name('quic-soak.py'))
        quic = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(quic)
        sample_peer = quic.peer_observation
        source = ('import sys,time; data=bytearray(24*1024*1024); '
                  'start=time.process_time();\n'
                  'while time.process_time()-start<.03: pass\n'
                  'print("ready",flush=True); sys.stdin.buffer.readline()')
        child = subprocess.Popen([sys.executable, '-c', source], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
        try:
            with selectors.DefaultSelector() as ready:
                ready.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(ready.select(2), 'telemetry child did not become ready')
            self.assertEqual(child.stdout.readline(), b'ready\n')
            status, sample = sample_peer(child)
            self.assertIsNone(status)
            self.assertGreaterEqual(sample['rss_bytes'], 24*1024*1024)
            self.assertGreater(sample['cpu_seconds'], 0)
            self.assertNotIn(sample['state'], ('Z', 'X', 'x'))
            child.stdin.write(b'\n'); child.stdin.flush()
            stdout, stderr = child.communicate(timeout=2)
            self.assertEqual((child.returncode, stdout, stderr), (0, b'', b''))
            self.assertEqual(sample_peer(child), (0, None))
            with self.assertRaises(ProcessLookupError): os.kill(child.pid, 0)
            with self.assertRaises(ProcessLookupError): os.killpg(child.pid, 0)
        finally:
            if child.poll() is None: os.killpg(child.pid, signal.SIGKILL)
            child.communicate(timeout=2)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'peer process telemetry uses Linux procfs')
    def test_peer_telemetry_exit_race_and_unexpected_read_failure(self):
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('quic_soak_exit_telemetry', Path(__file__).with_name('quic-soak.py'))
        quic = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(quic)
        sample_peer = quic.peer_observation
        child = subprocess.Popen([sys.executable, '-c',
                                  'import sys; print("ready",flush=True); sys.stdin.buffer.readline()'],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, start_new_session=True)
        original_sample = quic.process_sample
        try:
            with selectors.DefaultSelector() as ready:
                ready.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(ready.select(2), 'telemetry child did not become ready')
            self.assertEqual(child.stdout.readline(), b'ready\n')
            # A missing/denied read while the owned child is still alive must
            # not be converted into successful completion or zero RSS.
            for error in (FileNotFoundError('unexpected live absence'), PermissionError('denied')):
                with patch.object(quic, 'process_sample', side_effect=error):
                    with self.assertRaises(type(error)): sample_peer(child)
            self.assertIsNone(child.poll())
            def exit_between_poll_and_sample(pid):
                self.assertEqual(pid, child.pid)
                child.stdin.write(b'\n'); child.stdin.flush()
                self.assertEqual(child.wait(timeout=2), 0)
                return original_sample(pid)  # Real procfs read after reaping.
            with patch.object(quic, 'process_sample', side_effect=exit_between_poll_and_sample):
                self.assertEqual(sample_peer(child), (0, None))
            stdout, stderr = child.communicate(timeout=2)
            self.assertEqual((stdout, stderr), (b'', b''))
            with self.assertRaises(ProcessLookupError): os.kill(child.pid, 0)
            with self.assertRaises(ProcessLookupError): os.killpg(child.pid, 0)
        finally:
            if child.poll() is None: os.killpg(child.pid, signal.SIGKILL)
            child.communicate(timeout=2)


    def test_streaming_rss_statistics_match_the_retained_reference(self):
        import math
        def reference(rows, warmup):
            warm = [row for row in rows if row.get('elapsed_seconds', 0) >= warmup and 'rss_kib' in row]
            if not warm:
                return {'warm_rss_min_kib': None, 'warm_rss_max_kib': None,
                        'rss_slope_kib_per_second': None}
            xmean = sum(row['elapsed_seconds'] for row in warm) / len(warm)
            ymean = sum(row['rss_kib'] for row in warm) / len(warm)
            numerator = sum((row['elapsed_seconds'] - xmean) * (row['rss_kib'] - ymean) for row in warm)
            denominator = sum((row['elapsed_seconds'] - xmean) ** 2 for row in warm)
            return {'warm_rss_min_kib': min(row['rss_kib'] for row in warm),
                    'warm_rss_max_kib': max(row['rss_kib'] for row in warm),
                    'rss_slope_kib_per_second': numerator / denominator if denominator else 0}
        cases = [[], [{'elapsed_seconds': 59, 'rss_kib': 999}],
                 [{'elapsed_seconds': 60, 'rss_kib': 1000}],
                 [{'elapsed_seconds': 70, 'rss_kib': y} for y in (1000, 1300, 1100)],
                 [{'elapsed_seconds': 59, 'rss_kib': 9000}, {'line': 'progress'},
                  {'elapsed_seconds': 60, 'rss_kib': 1000}, {'elapsed_seconds': 61, 'rss_kib': 1010},
                  {'elapsed_seconds': float('nan'), 'rss_kib': 9999}],
                 [{'elapsed_seconds': x, 'rss_kib': y} for x, y in ((100, 1300), (61, 990), (80, 1100), (62, 1030))],
                 [{'elapsed_seconds': float((i*97)%503 + 60), 'rss_kib': 1000 + (i*53)%997} for i in range(3000)]]
        for rows in cases:
            for warmup in (0, 60, 75, 10000):
                with self.subTest(rows=len(rows), warmup=warmup):
                    expected = reference(rows, warmup)
                    # Iterate distinct dictionaries once: no list contract.
                    actual = observer.memory_summary((dict(row) for row in rows), warmup)
                    self.assertEqual(actual['warm_rss_min_kib'], expected['warm_rss_min_kib'])
                    self.assertEqual(actual['warm_rss_max_kib'], expected['warm_rss_max_kib'])
                    wanted = expected['rss_slope_kib_per_second']
                    if wanted is None: self.assertIsNone(actual['rss_slope_kib_per_second'])
                    else: self.assertTrue(math.isclose(actual['rss_slope_kib_per_second'], wanted,
                                                      rel_tol=1e-9, abs_tol=1e-12), (actual, expected))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'actual retained Python RSS uses Linux procfs')
    def test_rss_summary_does_not_retain_generator_rows(self):
        source = r"""
import json,os,sys
sys.path.insert(0,sys.argv[1])
from soak_observer import memory_summary,process_sample
class Row(dict):
    live=0
    peak=0
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Row.live+=1
        Row.peak=max(Row.peak,Row.live)
    def __del__(self):
        Row.live-=1
baseline=process_sample(os.getpid())['rss_kib']
peak=baseline
count=16000
def rows():
    global peak
    for index in range(count):
        if index%128==0:
            peak=max(peak,process_sample(os.getpid())['rss_kib'])
        # A bounded diagnostic line is irrelevant to the summary and must not
        # keep each independent input dictionary alive. Size stays below64KiB.
        yield Row(elapsed_seconds=float((index*97)%10007+60),
                  rss_kib=1000+(index*53)%997,
                  line=str(index)+':'+('x'*2048))
result=memory_summary(rows(),60)
print(json.dumps({'pid':os.getpid(),'rows':count,'peak_live_rows':Row.peak,
                  'remaining_live_rows':Row.live,'rss_base_kib':baseline,
                  'peak_rss_kib':peak,'retained_growth_kib':peak-baseline,
                  'summary':result}),flush=True)
"""
        run = subprocess.run([sys.executable, '-c', source, str(Path(__file__).parent)],
                             capture_output=True, text=True, timeout=2, start_new_session=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stderr, '')
        result = json.loads(run.stdout)
        print(json.dumps(result), flush=True)
        self.assertEqual(result['rows'], 16000)
        self.assertEqual(result['summary']['warm_rss_min_kib'], 1000)
        self.assertEqual(result['summary']['warm_rss_max_kib'], 1996)
        self.assertEqual(result['remaining_live_rows'], 0)
        with self.assertRaises(ProcessLookupError): os.kill(result['pid'], 0)
        with self.assertRaises(ProcessLookupError): os.killpg(result['pid'], 0)
        self.assertLessEqual(result['peak_live_rows'], 2, 'summary retained independent input dictionaries')
        self.assertLessEqual(result['retained_growth_kib'], 16384, 'summary exceeded unchanged16MiB span')

if __name__ == '__main__': unittest.main()
