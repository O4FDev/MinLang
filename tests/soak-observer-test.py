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

    @unittest.skipUnless(sys.platform.startswith('linux'), 'fixture birth receipts use Linux procfs')
    def test_tls_peer_releases_membership_on_all_close_outcomes(self):
        # Compile ONLY the literal maintained peer function, not the public
        # argparse/certificate/server/soak body. No rewritten peer algorithm.
        # Outcomes exercise real Tasks with deterministic reader/writer doubles;
        # they do not claim an authenticated TLS connection or a soak result.
        source = r'''
import ast, asyncio, hashlib, json, os, ssl
from pathlib import Path

def birth():
    pid = os.getpid()
    fields = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': pid, 'pgid': int(fields[2]), 'start_ticks': int(fields[19])}

driver = birth()
print(json.dumps({'driver_birth': driver, 'helpers': []}, sort_keys=True), flush=True)
source_path = Path(__TLS_SOURCE__)
raw = source_path.read_bytes()
tree = ast.parse(raw, filename=str(source_path))
definitions = [node for node in tree.body
               if isinstance(node, ast.AsyncFunctionDef) and node.name == 'peer']
if len(definitions) != 1:
    raise RuntimeError('maintained peer extraction was not unique')
definition = definitions[0]
fragment = ast.get_source_segment(raw.decode(), definition)
code = compile(fragment, str(source_path), 'exec')

class Reader:
    def __init__(self, mode):
        self.mode = mode
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.reads = 0
    async def readuntil(self, separator):
        if separator != b'\r\n\r\n':
            raise AssertionError('unexpected maintained separator')
        self.reads += 1
        self.entered.set()
        if self.mode == 'cancel_body':
            await self.release.wait()
            raise asyncio.IncompleteReadError(b'', None)
        if self.mode == 'reset_body':
            raise ConnectionResetError('fixture body reset')
        if self.mode == 'ssl_body':
            raise ssl.SSLError('fixture body SSL error')
        if self.mode == 'unexpected_body':
            raise RuntimeError('fixture body failed')
        if self.mode == 'seven_requests':
            return b'GET /heartbeat HTTP/1.1\r\nHost: fixture\r\n\r\n'
        raise asyncio.IncompleteReadError(b'', None)

class Writer:
    def __init__(self, mode):
        self.mode = mode
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.close_calls = 0
        self.wait_calls = 0
        self.writes = []
    def get_extra_info(self, name):
        return {'fixture': True} if name == 'peercert' else None
    def write(self, data):
        self.writes.append(data)
    async def drain(self):
        await asyncio.sleep(0)
    def close(self):
        self.close_calls += 1
        if self.mode == 'unexpected_close':
            raise RuntimeError('fixture close failed')
    async def wait_closed(self):
        self.wait_calls += 1
        self.entered.set()
        if self.mode == 'cancel_wait':
            await self.release.wait()
        elif self.mode == 'reset_wait':
            raise ConnectionResetError('fixture close reset')
        elif self.mode == 'ssl_wait':
            raise ssl.SSLError('fixture close SSL error')
        elif self.mode == 'timeout_wait':
            raise TimeoutError('fixture close timed out')

async def run_case(name, reader_mode, writer_mode, cancellation):
    peers = set()
    stats = dict.fromkeys(('connections', 'responses', 'malformed',
                           'oversized', 'closed', 'slow'), 0)
    unexpected = []
    namespace = {'asyncio': asyncio, 'ssl': ssl, 'peers': peers,
                 'stats': stats, 'unexpected': unexpected}
    exec(code, namespace)
    reader, writer = Reader(reader_mode), Writer(writer_mode)
    task = asyncio.create_task(namespace['peer'](reader, writer), name=name)
    outcome, cause = None, None
    membership_before_cancel = None
    try:
        if cancellation:
            entered = reader.entered if cancellation == 'body' else writer.entered
            await asyncio.wait_for(entered.wait(), .5)
            membership_before_cancel = task in peers
            task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), .5)
            outcome = 'returned'
        except BaseException as error:
            outcome, cause = type(error).__name__, str(error)
            if not task.done():
                raise RuntimeError('fixture task exceeded its useful bound') from error
        return {'name': name, 'outcome': outcome, 'cause': cause,
                'cancelled': task.cancelled(), 'task_done': task.done(),
                'membership_before_cancel': membership_before_cancel,
                'retained_peers': len(peers),
                'retained_done_peers': sum(value.done() for value in peers),
                'close_calls': writer.close_calls, 'wait_calls': writer.wait_calls,
                'read_calls': reader.reads, 'write_hex': [value.hex() for value in writer.writes],
                'stats': stats, 'unexpected': unexpected,
                'diagnostic_nonpass': bool(unexpected) or outcome in ('TimeoutError', 'RuntimeError')}
    finally:
        reader.release.set()
        writer.release.set()
        if not task.done():
            task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), .5)

async def main():
    cases = (
        ('normal', 'seven_requests', 'normal', None),
        ('eof', 'eof', 'normal', None),
        ('reset_body', 'reset_body', 'normal', None),
        ('ssl_body', 'ssl_body', 'normal', None),
        ('reset_wait', 'eof', 'reset_wait', None),
        ('ssl_wait', 'eof', 'ssl_wait', None),
        ('timeout_wait', 'eof', 'timeout_wait', None),
        ('cancel_body', 'cancel_body', 'normal', 'body'),
        ('cancel_wait', 'eof', 'cancel_wait', 'wait'),
        ('unexpected_close', 'eof', 'unexpected_close', None),
        ('unexpected_body', 'unexpected_body', 'normal', None),
    )
    rows = []
    for case in cases:
        rows.append(await run_case(*case))
    pending = [task.get_name() for task in asyncio.all_tasks()
               if task is not asyncio.current_task() and not task.done()]
    return {'driver': driver, 'helpers': [], 'helper_process_scope': 'no helper processes spawned',
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'peer_fragment_sha256': hashlib.sha256(fragment.encode()).hexdigest(),
            'peer_span': [definition.lineno, definition.end_lineno],
            'cases': rows, 'pending_tasks': pending,
            'scope': 'actual peer coroutine lifecycle with bounded doubles; no TLS/protocol/RSS claim'}

result = asyncio.run(main())
print(json.dumps(result, sort_keys=True), flush=True)
'''.replace('__TLS_SOURCE__', repr(str(Path(__file__).with_name('tls-soak.py'))))
        fields = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
        print(json.dumps({'runner': {'pid': os.getpid(), 'pgid': int(fields[2]),
                                      'start_ticks': int(fields[19])}}), flush=True)
        child = self.child(source)
        try:
            stdout, stderr = child.communicate(timeout=8)
            # self.child uses binary pipes. Publish all available raw output
            # before any outer status, stderr, parsing or lifecycle assertion.
            sys.stdout.buffer.write(stdout)
            sys.stdout.buffer.flush()
            self.assertEqual(child.returncode, 0, stderr)
            self.assertEqual(stderr, b'')
            output = [json.loads(line) for line in stdout.splitlines()]
            self.assertEqual(len(output), 2)
            result = output[1]
            self.assertEqual(output[0], {'driver_birth': result['driver'], 'helpers': []})
            self.assertEqual(result['driver']['pid'], child.pid)
            self.assertEqual(result['driver']['pgid'], child.pid)
            self.assertEqual(result['helpers'], [])
            self.assertEqual(result['pending_tasks'], [])
            expected = {
                'normal': ('returned', None, False, False),
                'eof': ('returned', None, False, False),
                'reset_body': ('returned', None, False, False),
                'ssl_body': ('returned', None, False, False),
                'reset_wait': ('returned', None, False, False),
                'ssl_wait': ('returned', None, False, False),
                'timeout_wait': ('TimeoutError', 'fixture close timed out', False, True),
                'cancel_body': ('returned', None, False, False),
                'cancel_wait': ('CancelledError', '', True, False),
                'unexpected_close': ('RuntimeError', 'fixture close failed', False, True),
                'unexpected_body': ('returned', None, False, True),
            }
            self.assertEqual([row['name'] for row in result['cases']], list(expected))
            for row in result['cases']:
                with self.subTest(case=row['name']):
                    outcome, cause, cancelled, nonpass = expected[row['name']]
                    self.assertEqual(row['outcome'], outcome)
                    self.assertEqual(row['cause'], cause)
                    self.assertEqual(row['cancelled'], cancelled)
                    self.assertEqual(row['diagnostic_nonpass'], nonpass)
                    self.assertTrue(row['task_done'])
                    self.assertEqual(row['close_calls'], 1)
                    self.assertEqual(row['wait_calls'], 0 if row['name'] == 'unexpected_close' else 1)
                    self.assertEqual(row['stats']['connections'], 1)
                    self.assertEqual(row['unexpected'], ["RuntimeError('fixture body failed')"]
                                     if row['name'] == 'unexpected_body' else [])
                    if row['name'].startswith('cancel_'):
                        self.assertTrue(row['membership_before_cancel'])
                    if row['name'] == 'normal':
                        self.assertEqual(row['read_calls'], 7)
                        self.assertEqual(row['stats'], {'connections': 1, 'responses': 6,
                                                       'malformed': 0, 'oversized': 0,
                                                       'closed': 1, 'slow': 0})
                        fragments = (b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok',)
                        self.assertEqual(row['write_hex'],
                                         [part.hex() for response in fragments * 6
                                          for part in (response[:7], response[7:])])
                    else:
                        self.assertEqual(row['write_hex'], [])
                    # These follow all outcome/counter assertions so baseline
                    # RED identifies retained completed tasks, not a new API.
                    self.assertEqual(row['retained_peers'], 0)
                    self.assertEqual(row['retained_done_peers'], 0)
            with self.assertRaises(ProcessLookupError): os.kill(child.pid, 0)
            with self.assertRaises(ProcessLookupError): os.killpg(child.pid, 0)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.communicate(timeout=2)

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
        self.assertEqual(child.wait(timeout=5), 0)
        with self.assertRaises(TimeoutError): list(observer.observe(child, .15, .02))
        self.assertEqual(child.poll(), 0)

    def test_interrupt_between_samples_reaps_child_and_restores_handlers(self):
        for value in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=value):
                child = self.child('import time; time.sleep(10)')
                previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
                events = observer.observe(child, 2, .01)
                try:
                    next(events)
                    with self.assertRaises(KeyboardInterrupt): signal.raise_signal(value)
                    self.assertIsNotNone(child.poll())
                    self.assertTrue(all(signal.getsignal(sig) == handler
                                        for sig, handler in previous.items()))
                finally:
                    events.close()
                    if child.poll() is None: child.kill(); child.wait()


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

    @unittest.skipUnless(sys.platform.startswith('linux'), 'QUIC adapter retention uses actual Linux RSS')
    def test_quic_observer_adapter_bounds_long_sample_history(self):
        # Exercise the driver adapter with real quiet processes. Virtual sample
        # times accelerate history only; this is not transport/performance proof.
        source = 'TEST_DIR=' + repr(str(Path(__file__).parent)) + '\n' + r'''
import contextlib,importlib.util,json,os,subprocess,sys,tempfile,types
from pathlib import Path
sys.path.insert(0,TEST_DIR)
spec=importlib.util.spec_from_file_location('quic_adapter',Path(TEST_DIR)/'quic-soak.py')
quic=importlib.util.module_from_spec(spec);spec.loader.exec_module(quic)
own_fields=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()
driver_identity={'pid':os.getpid(),'pgid':int(own_fields[2]),'start_ticks':int(own_fields[19])}
class Row(dict):
    live=peak=0
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);Row.live+=1;Row.peak=max(Row.peak,Row.live)
    def __del__(self):Row.live-=1
children=[];births=[]
def child():
    p=subprocess.Popen([sys.executable,'-c','import sys; data=bytearray(24*1024*1024); print("ready",flush=True); sys.stdin.buffer.readline()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    children.append(p)
    fields=Path(f'/proc/{p.pid}/stat').read_text().rsplit(')',1)[1].split()
    births.append({'pid':p.pid,'pgid':int(fields[2]),'start_ticks':int(fields[19])})
    assert p.stdout.readline()=='ready\n'
    return p
try:
    server=child();peer=child();original=quic.process_sample
    base=original(os.getpid())['rss_bytes']//1024;peak=base
    count=0;checkpoints=0;clock={'now':100.0}
    proxy=types.SimpleNamespace(forwarded=0,dropped=0,delayed=0)
    def sample(pid):
        global count,peak
        result=original(pid)
        if pid==server.pid:
            count+=1;clock['now']=100.0+count*10
            proxy.forwarded=count*5;proxy.dropped=count;proxy.delayed=(count+1)//2
            # Independent bounded future diagnostic field; not a shared string.
            return Row(result,detail=str(count)+':'+('x'*2048))
        if pid==os.getpid():
            peak=max(peak,result['rss_bytes']//1024)
            if count==16000:
                for p in (server,peer):p.stdin.write('\n');p.stdin.flush()
                for p in (server,peer):assert p.wait(timeout=2)==0
        return result
    def checkpoint(*unused):
        global checkpoints
        checkpoints+=1
    quic.process_sample=sample
    quic.time=types.SimpleNamespace(monotonic=lambda:clock['now'],sleep=lambda delay:None)
    # Suppress repeated whole-history checkpoint serialization in this stress
    # control only. The actual adapter's sample ownership remains untouched.
    quic.write_report=checkpoint
    with tempfile.TemporaryDirectory() as directory,open(os.devnull,'w') as silent:
        path=Path(directory)/'report.json';report={'samples':[]}
        with contextlib.redirect_stdout(silent):
            quic.observe_samples(server,peer,proxy,0,200000,1,path,report)
            quic.finish_observations(server,peer,proxy,path,report)
        result={'pid':os.getpid(),'driver_identity':driver_identity,'births':births,'rows':count,'checkpoints':checkpoints,
                'peak_live_rows':Row.peak,'remaining_live_rows':Row.live,
                'rss_base_kib':base,'peak_rss_kib':peak,'retained_growth_kib':peak-base,
                'server_status':report['server_status'],'client_status':report['client_status'],
                'server_stderr':report['server_stderr'],'client_stderr':report['client_stderr'],
                'role_summaries':report.get('memory_summary_by_role')}
        print(json.dumps(result),flush=True)
finally:
    for p in children:
        if p.poll() is None:p.kill()
        p.communicate(timeout=2)
'''
        child = self.child(source)
        try:
            stdout, stderr = child.communicate(timeout=12)
            sys.stdout.buffer.write(stdout); sys.stdout.buffer.flush()
            self.assertEqual(child.returncode, 0, stderr)
            self.assertEqual(stderr, b'')
            result = json.loads(stdout)
            self.assertEqual(result['rows'], 16000)
            self.assertEqual(result['checkpoints'], 16001)
            self.assertEqual((result['server_status'], result['client_status']), (0, 0))
            self.assertEqual((result['server_stderr'], result['client_stderr']), ('', ''))
            for target in [child.pid] + [row['pid'] for row in result['births']]:
                with self.assertRaises(ProcessLookupError): os.kill(target, 0)
            with self.assertRaises(ProcessLookupError): os.killpg(child.pid, 0)
            self.assertLessEqual(result['peak_live_rows'], 2, 'QUIC observer retained sample dictionaries')
            self.assertLessEqual(result['remaining_live_rows'], 1, 'QUIC report retained history')
            self.assertLessEqual(result['retained_growth_kib'], 16384, 'observer exceeded unchanged16MiB span')
            self.assertEqual(set(result['role_summaries']), {'server','controller','peer'})
            for role, summary in result['role_summaries'].items():
                self.assertLessEqual(summary['warm_rss_max_kib']-summary['warm_rss_min_kib'], 16384, role)
                self.assertLessEqual(summary['rss_slope_kib_per_second'], .2, role)
        finally:
            if child.poll() is None: os.killpg(child.pid, signal.SIGKILL)
            child.communicate(timeout=2)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'QUIC report roles use actual Linux procfs')
    def test_quic_observer_adapter_preserves_raw_roles_counters_and_exit_status(self):
        source = 'TEST_DIR=' + repr(str(Path(__file__).parent)) + '\n' + r'''
import contextlib,importlib.util,json,math,os,subprocess,sys,tempfile,types
from pathlib import Path
sys.path.insert(0,TEST_DIR)
spec=importlib.util.spec_from_file_location('quic_adapter',Path(TEST_DIR)/'quic-soak.py')
quic=importlib.util.module_from_spec(spec);spec.loader.exec_module(quic)
own_fields=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()
driver_identity={'pid':os.getpid(),'pgid':int(own_fields[2]),'start_ticks':int(own_fields[19])}
original=quic.process_sample;births=[];outcomes=[]
def reference(rows,role):
    points=[(r['elapsed_seconds'],(r if role=='server' else r[role])['rss_bytes']/1024)
            for r in rows if r['elapsed_seconds']>=60 and (role=='server' or r[role] is not None)]
    if not points:return {'warm_rss_min_kib':None,'warm_rss_max_kib':None,'rss_slope_kib_per_second':None}
    x=sum(p[0] for p in points)/len(points);y=sum(p[1] for p in points)/len(points)
    denominator=sum((a-x)**2 for a,b in points)
    return {'warm_rss_min_kib':min(b for a,b in points),'warm_rss_max_kib':max(b for a,b in points),
            'rss_slope_kib_per_second':sum((a-x)*(b-y) for a,b in points)/denominator if denominator else 0}
for peer_exit in (0,7,None):
    children=[]
    def child(status=0):
        p=subprocess.Popen([sys.executable,'-c',f'import sys; data=bytearray(24*1024*1024); print("ready",flush=True); sys.stdin.buffer.readline(); sys.exit({status})'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        children.append(p)
        fields=Path(f'/proc/{p.pid}/stat').read_text().rsplit(')',1)[1].split()
        births.append({'pid':p.pid,'pgid':int(fields[2]),'start_ticks':int(fields[19])})
        assert p.stdout.readline()=='ready\n';return p
    try:
        server=child();peer=child(peer_exit) if peer_exit is not None else None
        clock={'now':100.0};counter={'rows':0}
        proxy=types.SimpleNamespace(forwarded=0,dropped=0,delayed=0)
        def sample(pid):
            row=original(pid)
            if pid==server.pid:
                counter['rows']+=1;clock['now']=100+10*counter['rows']
                proxy.forwarded=counter['rows']*5;proxy.dropped=counter['rows'];proxy.delayed=(counter['rows']+1)//2
            if pid==os.getpid():
                if peer and counter['rows']==3:
                    peer.stdin.write('\n');peer.stdin.flush();assert peer.wait(timeout=2)==peer_exit
                if counter['rows']==(3 if peer_exit==7 else 8):
                    server.stdin.write('\n');server.stdin.flush();assert server.wait(timeout=2)==0
            return row
        quic.process_sample=sample
        quic.time=types.SimpleNamespace(monotonic=lambda:clock['now'],sleep=lambda delay:None)
        with tempfile.TemporaryDirectory() as directory,open(os.devnull,'w') as silent:
            path=Path(directory)/'report.json';metadata={'samples':[],'server_pid':server.pid,'controller_pid':os.getpid(),'peer_pid':peer.pid if peer else None}
            failed=False
            with contextlib.redirect_stdout(silent):
                quic.observe_samples(server,peer,proxy,0,1000,1,path,metadata)
                try:quic.finish_observations(server,peer,proxy,path,metadata)
                except AssertionError:failed=True
            report=json.loads(path.read_text());rows=report['samples']
            assert failed==(peer_exit==7)
            assert report['server_status']==0 and report['client_status']==peer_exit
            assert report['server_stderr']==report['client_stderr']==''
            assert len(rows)==counter['rows'] and len(rows)==(3 if peer_exit==7 else 8)
            assert report['faults']=={'forwarded':len(rows)*5,'dropped':len(rows),'reordered':(len(rows)+1)//2}
            for index,row in enumerate(rows):
                assert row['elapsed_seconds']==110+index*10
                assert row['rss_bytes']>=24*1024*1024 and row['controller']['rss_bytes']>0
                if index:assert row['interval_cpu_percent']==100*(row['cpu_seconds']-rows[index-1]['cpu_seconds'])/10
                if peer and index<2:assert row['peer_status'] is None and row['peer']['rss_bytes']>=24*1024*1024
                else:assert row['peer'] is None and row['peer_status']==peer_exit
                assert row['proxy_forwarded']==(index+1)*5 and row['proxy_dropped']==index+1
            raw=path.with_name('samples.jsonl')
            if raw.exists():
                assert [json.loads(line) for line in raw.open()]==rows
                assert report['sample_count']==len(rows) and report['last_sample']==rows[-1]
                for role in ('server','controller','peer'):
                    expected=reference(rows,role);actual=report['memory_summary_by_role'][role]
                    assert actual['warm_rss_min_kib']==expected['warm_rss_min_kib'] and actual['warm_rss_max_kib']==expected['warm_rss_max_kib']
                    wanted=expected['rss_slope_kib_per_second'];got=actual['rss_slope_kib_per_second']
                    assert got is None if wanted is None else math.isclose(got,wanted,rel_tol=1e-9,abs_tol=1e-12)
                    if wanted is not None:
                        assert expected['warm_rss_max_kib']-expected['warm_rss_min_kib']<=16384
            outcomes.append({'peer_exit':peer_exit,'rejected':failed,'rows':len(rows),'statuses':[report['server_status'],report['client_status']]})
    finally:
        for p in children:
            if p.poll() is None:p.kill()
            p.communicate(timeout=2)
print(json.dumps({'pid':os.getpid(),'driver_identity':driver_identity,'births':births,'cases':outcomes}),flush=True)
'''
        child = self.child(source)
        try:
            stdout, stderr = child.communicate(timeout=12)
            sys.stdout.buffer.write(stdout); sys.stdout.buffer.flush()
            self.assertEqual(child.returncode, 0, stderr)
            self.assertEqual(stderr, b'')
            result=json.loads(stdout)
            self.assertEqual(result['cases'], [
                {'peer_exit':0,'rejected':False,'rows':8,'statuses':[0,0]},
                {'peer_exit':7,'rejected':True,'rows':3,'statuses':[0,7]},
                {'peer_exit':None,'rejected':False,'rows':8,'statuses':[0,None]}])
            for target in [child.pid]+[row['pid'] for row in result['births']]:
                with self.assertRaises(ProcessLookupError): os.kill(target,0)
            with self.assertRaises(ProcessLookupError): os.killpg(child.pid,0)
        finally:
            if child.poll() is None: os.killpg(child.pid,signal.SIGKILL)
            child.communicate(timeout=2)

if __name__ == '__main__': unittest.main()
