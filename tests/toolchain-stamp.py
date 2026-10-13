#!/usr/bin/env python3
"""Toolchain changes invalidate artifacts; unchanged probes preserve mtimes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from clang_helpers import native_path

ROOT = Path(__file__).resolve().parents[1]


class ToolchainStamp(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux ThinLTO selects LLD')
    def test_thin_lto_requires_matching_linker_and_tracks_replacement(self):
        with tempfile.TemporaryDirectory(prefix='minyar linker ') as temporary:
            work = Path(temporary)
            compiler = work / 'clang'
            linker = work / 'ld.lld'
            compiler.write_text('#!' + sys.executable + '\nimport sys\nprint(' + repr(str(linker)) + ' if "-print-prog-name=ld.lld" in sys.argv else "clang version 23.1.2")\n')
            compiler.chmod(0o755)
            stamp = work / 'stamp.json'
            environment = {**os.environ, 'CC': str(compiler), 'LLVM_CC': str(compiler),
                           'COMPILER_LTO_FLAGS': '-flto=thin -fuse-ld=lld', 'LLVM_FLAGS': '-O2'}
            def probe():
                return subprocess.run(['sh', str(ROOT / 'tools/toolchain.sh'), 'stamp', str(stamp)],
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
            linker = work / "ld.lld"
            linker.write_text("#!" + sys.executable + "\nprint(\"LLD 23.1.2\")\n")
            linker.chmod(0o755)
            for compiler in (first, second):
                compiler.write_text("#!" + sys.executable + "\nimport sys\nprint(" + repr(str(linker)) + " if \"-print-prog-name=ld.lld\" in sys.argv else \"clang version 23.1.2\")\n")
                compiler.chmod(0o755)
            stamp = work / "stamp.json"
            environment = {**os.environ, "CC": native_path(first), "LLVM_CC": native_path(first)}

            def probe():
                result = subprocess.run(
                    ["sh", str(ROOT / "tools/toolchain.sh"), "stamp", str(stamp)],
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
    def exercise(self, timestamps, prior=100):
        temporary = tempfile.TemporaryDirectory(prefix='stamp-clock-')
        self.addCleanup(temporary.cleanup)
        work = Path(temporary.name)
        root = work / 'stamps'
        root.mkdir()
        target = root / 'stamp.json'
        target.write_bytes(b'original')
        os.utime(target, ns=(prior * 1_000_000_000, prior * 1_000_000_000))
        tools = work / 'tools'
        tools.mkdir()
        sequence = work / 'sequence.json'
        sequence.write_text(json.dumps(timestamps))
        log = work / 'clock.jsonl'
        compiler = work / 'clang'
        compiler.write_text('#!' + sys.executable + '\nprint("clang version 23.1.2")\n')
        compiler.chmod(0o755)
        fakes = {
            'date': 'print(100)\n',
            'sleep': 'pass\n',
            'touch': ('import json,os,sys\n'
                      'values=json.load(open(os.environ["STAMP_SEQUENCE"]))\n'
                      'log=os.environ["STAMP_LOG"]\n'
                      'count=sum(1 for line in open(log) if line.startswith("touch")) if os.path.exists(log) else 0\n'
                      'stamp=values[min(count,len(values)-1)]\n'
                      'os.utime(sys.argv[-1],ns=(stamp,stamp))\n'
                      'open(log,"a").write("touch "+str(stamp)+"\\n")\n'),
            'mv': ('import os,sys\n'
                   'source,destination=sys.argv[-2],sys.argv[-1]\n'
                   'open(os.environ["STAMP_LOG"],"a").write("replace "+str(os.stat(source).st_mtime_ns)+"\\n")\n'
                   'os.replace(source,destination)\n'),
        }
        for name, code in fakes.items():
            path = tools / name
            path.write_text('#!' + sys.executable + '\n' + code)
            path.chmod(0o755)
        environment = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'],
                           CC=str(compiler), LLVM_CC=str(compiler), COMPILER_LTO_FLAGS='', LLVM_FLAGS='',
                           STAMP_SEQUENCE=str(sequence), STAMP_LOG=str(log))
        result = subprocess.run(['sh', str(ROOT / 'tools/toolchain.sh'), 'stamp', str(target)],
                                env=environment, capture_output=True, text=True, timeout=30)
        rows = log.read_text().splitlines() if log.exists() else []
        observed = [int(row.split()[1]) for row in rows if row.startswith('touch')]
        replaced = [int(row.split()[1]) for row in rows if row.startswith('replace')]
        if result.returncode:
            self.assertEqual(target.read_bytes(), b'original')
            self.assertEqual(list(root.iterdir()), [target])
            self.assertEqual(replaced, [])
            raise TimeoutError(result.stderr)
        self.assertEqual(len(replaced), 1)
        self.assertGreaterEqual(replaced[0] // 1_000_000_000, max(100, prior) + 1)
        self.assertNotEqual(target.read_bytes(), b'original')
        self.assertEqual(json.loads(target.read_text())['llvm_version'], '23.1.2')
        self.assertEqual(list(root.iterdir()), [target])
        return observed

    def test_userspace_boundary_does_not_certify_filesystem_boundary(self):
        observed = self.exercise([100_990_000_000, 101_001_000_000])
        self.assertEqual(observed, [100_990_000_000, 101_001_000_000])

    def test_stalled_filesystem_fails_bounded_without_replacing_stamp(self):
        with self.assertRaisesRegex(TimeoutError, 'filesystem timestamp'):
            self.exercise([100_999_999_999])

    def test_clock_rollback_still_requires_newer_than_prior_stamp(self):
        observed = self.exercise([103_999_999_999, 104_000_000_000], prior=103)
        self.assertEqual(observed[-1], 104_000_000_000)


if __name__ == "__main__":
    unittest.main()
