#!/usr/bin/env python3
"""Adversarial checks of the independent long-run observer."""
import importlib.util
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

    def test_rss_trend_distinguishes_plateau_from_growth(self):
        plateau = [{'elapsed_seconds': n, 'rss_kib': 1000 + n % 3} for n in range(100)]
        growth = [{'elapsed_seconds': n, 'rss_kib': 1000 + n * 100} for n in range(100)]
        self.assertLess(abs(observer.memory_summary(plateau, 10)['rss_slope_kib_per_second']), .01)
        self.assertAlmostEqual(observer.memory_summary(growth, 10)['rss_slope_kib_per_second'], 100)

if __name__ == '__main__': unittest.main()
