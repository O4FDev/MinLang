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

ROOT = Path(__file__).resolve().parents[1]


class ToolchainStamp(unittest.TestCase):
    def test_identity_flags_and_replaced_binary(self):
        with tempfile.TemporaryDirectory(prefix="minyar toolchain ") as temporary:
            work = Path(temporary)
            first = work / "first compiler.exe"
            second = work / "second compiler.exe"
            # MSYS checks executable contents as well as permission bits. The
            # stamp only reads metadata, so use portable native image fixtures.
            shutil.copy2(sys.executable, first)
            shutil.copy2(sys.executable, second)
            stamp = work / "stamp.json"
            environment = {**os.environ, "CC": str(first), "LLVM_CC": str(first)}

            def probe():
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/toolchain-stamp.py"), str(stamp)],
                    env=environment, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return stamp.read_bytes(), stamp.stat().st_mtime_ns

            original = probe()
            self.assertEqual(probe(), original)
            environment["LLVM_CC"] = str(second)
            changed = probe()
            self.assertNotEqual(changed[0], original[0])
            self.assertGreater(changed[1] // 1_000_000_000, original[1] // 1_000_000_000,
                               'GNU Make 3.81 compares timestamps at whole-second precision')
            self.assertEqual(probe(), changed)
            environment["LLVM_FLAGS"] = "-O3 -g"
            flags = probe()
            self.assertNotEqual(flags[0], changed[0])
            with second.open("ab") as stream:
                stream.write(b"replacement compiler, same executable path")
            self.assertNotEqual(probe()[0], flags[0])
            self.assertEqual(json.loads(stamp.read_text())["flags"]["LLVM_FLAGS"], "-O3 -g")


if __name__ == "__main__":
    unittest.main()
