#!/usr/bin/env python3
"""Compile the real native renderer and exercise GL loading without a display."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from clang_helpers import clang_command

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('clang_driver', ROOT / 'tools/clang-driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class NativeGraphics(unittest.TestCase):
    def test_platform_headers_renderer_and_entry_loading(self):
        cflags, _ = driver.glfw_flags()
        clang = os.environ.get('MINYAR_TEST_CLANG', os.environ.get('LLVM_CC', 'clang'))
        with tempfile.TemporaryDirectory(prefix='minyar native graphics ') as work:
            output = Path(work) / 'loader'
            if os.name == 'nt': output = output.with_suffix('.exe')
            common = [clang, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', *cflags]
            subprocess.run(clang_command([*common, str(ROOT / 'tests/graphics-loader.c'), '-o', str(output)]), check=True)
            subprocess.run([str(output)], check=True, timeout=10)
            # Force the Windows entry-point path on other hosts too, using the
            # platform's real API pointer signatures and calling convention.
            subprocess.run(clang_command([*common, '-DMINYAR_GRAPHICS_LOAD_GL=1', '-c',
                            str(ROOT / 'runtime/native/graphics.c'), '-o', str(Path(work) / 'graphics.o')]), check=True)


if __name__ == '__main__':
    unittest.main()
