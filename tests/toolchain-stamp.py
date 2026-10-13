#!/usr/bin/env python3
"""Toolchain changes invalidate artifacts; unchanged probes preserve mtimes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from clang_helpers import native_path

ROOT = Path(__file__).resolve().parents[1]


class ToolchainStamp(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux ThinLTO selects LLD')
    def test_thin_lto_requires_matching_linker_and_tracks_replacement(self):
        with tempfile.TemporaryDirectory(prefix='minyar linker ') as temporary:
            work = Path(temporary)
            compiler = work / 'clang'
            linker = work / 'ld.lld'
            compiler.write_text('#!' + sys.executable + '\nprint("clang version 23.1.2")\n')
            compiler.chmod(0o755)
            stamp = work / 'stamp.json'
            environment = {**os.environ, 'CC': str(compiler), 'LLVM_CC': str(compiler),
                           'COMPILER_LTO_FLAGS': '-flto=thin -fuse-ld=lld', 'LLVM_FLAGS': '-O2'}
            def probe():
                return subprocess.run([sys.executable, str(ROOT / 'scripts/toolchain-stamp.py'), str(stamp)],
                                      env=environment, capture_output=True, text=True, timeout=10)
            def install(version):
                linker.write_text('#!' + sys.executable + '\nprint("LLD ' + version + '")\n')
                linker.chmod(0o755)
            install('18.1.3')
            result = probe()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('requires LLVM 23.1.2; unsupported linker', result.stderr)
            self.assertFalse(stamp.exists())
            install('23.1.2')
            self.assertEqual(probe().returncode, 0)
            original = stamp.read_bytes(), stamp.stat().st_mtime_ns
            self.assertEqual(json.loads(original[0])['linker']['path'], str(linker.resolve()))
            self.assertEqual(probe().returncode, 0)
            self.assertEqual((stamp.read_bytes(), stamp.stat().st_mtime_ns), original)
            install('23.1.0')
            result = probe()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('LLD 23.1.0', result.stderr)
            self.assertEqual(stamp.read_bytes(), original[0])
            linker.unlink()
            result = probe()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('executable not found', result.stderr)

    def test_identity_flags_and_replaced_binary(self):
        with tempfile.TemporaryDirectory(prefix="minyar toolchain ") as temporary:
            work = Path(temporary)
            first = work / "first compiler.exe"
            second = work / "second compiler.exe"
            for compiler in (first, second):
                compiler.write_text("#!" + sys.executable + "\nprint(\"clang version 23.1.2\")\n")
                compiler.chmod(0o755)
            stamp = work / "stamp.json"
            environment = {**os.environ, "CC": native_path(first), "LLVM_CC": native_path(first)}

            def probe():
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/toolchain-stamp.py"), str(stamp)],
                    env=environment, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return stamp.read_bytes(), stamp.stat().st_mtime_ns

            original = probe()
            self.assertEqual(probe(), original)
            environment["LLVM_CC"] = native_path(second)
            changed = probe()
            self.assertNotEqual(changed[0], original[0])
            self.assertGreater(changed[1] // 1_000_000_000, original[1] // 1_000_000_000,
                               'GNU Make 3.81 compares timestamps at whole-second precision')
            self.assertEqual(probe(), changed)
            environment["LLVM_FLAGS"] = "-O3 -g"
            flags = probe()
            self.assertNotEqual(flags[0], changed[0])
            with second.open("ab") as stream:
                stream.write(b"\n")
            self.assertNotEqual(probe()[0], flags[0])
            self.assertEqual(json.loads(stamp.read_text())["flags"]["LLVM_FLAGS"], "-O3 -g")


class StampFilesystemClock(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('stamp_module', ROOT / 'scripts/toolchain-stamp.py')
        self.stamp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.stamp)

    def exercise(self, timestamps, max_wait=0.3, prior=100):
        temporary = tempfile.TemporaryDirectory(prefix='stamp-clock-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        target = root / 'stamp.json'
        target.write_bytes(b'original')
        real_utime = os.utime
        real_replace = os.replace
        real_utime(target, ns=(prior * 1_000_000_000, prior * 1_000_000_000))
        elapsed = [0.0]
        wall = [100.9]
        observed = []
        values = iter(timestamps)
        def touch(path, *args, **kwargs):
            stamp = next(values, timestamps[-1])
            real_utime(path, ns=(stamp, stamp))
            observed.append(stamp)
        def replace(path, destination):
            self.assertGreaterEqual(Path(path).stat().st_mtime_ns // 1_000_000_000, max(100, prior) + 1)
            real_replace(path, destination)
        def sleep(duration):
            elapsed[0] += duration
            wall[0] = 101.9
        # Userspace time has crossed the second; the filesystem initially has
        # not. Only observing UTIME_NOW on the temporary inode can certify it.
        with mock.patch.object(self.stamp.time, 'time', side_effect=lambda: wall[0]), \
             mock.patch.object(self.stamp.time, 'monotonic', side_effect=lambda: elapsed[0]), \
             mock.patch.object(self.stamp.time, 'sleep', side_effect=sleep), \
             mock.patch.object(self.stamp.os, 'utime', side_effect=touch), \
             mock.patch.object(self.stamp.os, 'replace', side_effect=replace):
            try:
                self.stamp.publish_stamp(target, b'changed', max_wait=max_wait)
            except TimeoutError:
                self.assertEqual(target.read_bytes(), b'original')
                self.assertEqual(list(root.iterdir()), [target])
                raise
        self.assertEqual(target.read_bytes(), b'changed')
        self.assertEqual(list(root.iterdir()), [target])
        return observed, elapsed[0]

    def test_userspace_boundary_does_not_certify_filesystem_boundary(self):
        observed, _ = self.exercise([100_990_000_000, 101_001_000_000])
        self.assertEqual(observed, [100_990_000_000, 101_001_000_000])

    def test_stalled_filesystem_fails_bounded_without_replacing_stamp(self):
        with self.assertRaisesRegex(TimeoutError, 'filesystem timestamp'):
            self.exercise([100_999_999_999], max_wait=0.12)

    def test_clock_rollback_still_requires_newer_than_prior_stamp(self):
        observed, _ = self.exercise([103_999_999_999, 104_000_000_000], prior=103)
        self.assertEqual(observed[-1], 104_000_000_000)


if __name__ == "__main__":
    unittest.main()
