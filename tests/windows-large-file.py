#!/usr/bin/env python3
"""Verify the Windows runtime reports file lengths above signed 32-bit range."""

from __future__ import annotations

import ctypes
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIZE = (2 << 30) + 17


def main() -> None:
    if os.name != "nt":
        print("Windows sparse-file length check skipped on this platform")
        return

    import msvcrt

    with tempfile.TemporaryDirectory(prefix="minyar-windows-file-size-") as directory:
        temporary = Path(directory)
        sparse = temporary / "above-2gib.bin"
        with sparse.open("w+b") as file:
            returned = ctypes.c_ulong()
            handle = ctypes.c_void_p(msvcrt.get_osfhandle(file.fileno()))
            # FSCTL_SET_SPARSE ensures extending the file consumes negligible
            # physical disk space on the NTFS GitHub runner.
            success = ctypes.windll.kernel32.DeviceIoControl(
                handle, 0x000900C4, None, 0, None, 0,
                ctypes.byref(returned), None,
            )
            if not success:
                raise ctypes.WinError()
            file.seek(SIZE - 1)
            file.write(b"\0")
        if sparse.stat().st_size != SIZE:
            raise AssertionError("sparse file did not reach the requested 64-bit size")

        executable = temporary / "file-size.exe"
        compiled = subprocess.run(
            [os.environ.get("MINYAR_TEST_CLANG", "clang"), "-std=c11", "-O2",
             "-Wall", "-Wextra", "-Werror", str(ROOT / "tests/windows-file-size.c"),
             "-o", str(executable)],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
        if compiled.returncode != 0:
            raise AssertionError(compiled.stderr)
        checked = subprocess.run(
            [str(executable), str(sparse)], capture_output=True, text=True, timeout=30,
        )
        if checked.returncode != 0 or checked.stdout != f"{SIZE}\n" or checked.stderr:
            raise AssertionError(
                f"64-bit file probe failed: status={checked.returncode}, "
                f"stdout={checked.stdout!r}, stderr={checked.stderr!r}"
            )
    print("Windows runtime measured a sparse file above 2 GiB exactly")


if __name__ == "__main__":
    main()
