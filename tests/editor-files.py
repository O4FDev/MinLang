#!/usr/bin/env python3
"""Formatter file-safety contracts through the real CLI."""
import argparse
from pathlib import Path
import stat
import subprocess
import tempfile


def run(formatter):
    with tempfile.TemporaryDirectory(prefix="minyar format files ") as temporary:
        root = Path(temporary)
        directory = root / "source"
        directory.mkdir()
        source = directory / "a light 星.min"
        before = b"print( 42 )\n"
        source.write_bytes(before)
        source.chmod(0o751)

        def invoke(*arguments, cwd=None):
            return subprocess.run([formatter, *map(str, arguments)], cwd=cwd, capture_output=True, timeout=15)

        checked = invoke("--check", source)
        assert checked.returncode == 1 and source.read_bytes() == before, checked
        preview = invoke("--stdout", source)
        assert preview.returncode == 0 and preview.stdout == b"print(42)\n" and not preview.stderr, preview
        assert source.read_bytes() == before
        formatted = invoke(source)
        assert formatted.returncode == 0 and source.read_bytes() == b"print(42)\n", formatted
        assert stat.S_IMODE(source.stat().st_mode) == 0o751
        assert invoke("--check", source).returncode == 0

        outside = root / "outside.min"
        outside.write_bytes(before)
        (directory / "linked.min").symlink_to(outside)
        (directory / "loop").symlink_to(directory, target_is_directory=True)
        (directory / "outside-directory").symlink_to(root, target_is_directory=True)
        assert invoke("--check", directory).returncode == 0
        assert outside.read_bytes() == before
        assert invoke(directory / "linked.min").returncode == 1
        assert invoke(str(directory / "outside-directory") + "/").returncode == 1
        assert (directory / "linked.min").is_symlink() and outside.read_bytes() == before

        empty = root / "empty"
        empty.mkdir()
        assert invoke(empty, cwd=root).returncode == 0
        assert outside.read_bytes() == before
        assert invoke("--check", "--stdout", source).returncode == 1
        assert invoke("--stdout", source, outside).returncode == 1
        strange = root / "-strange.min"
        strange.write_bytes(before)
        assert invoke("--stdout", "--", "-strange.min", cwd=root).stdout == b"print(42)\n"
        invalid = directory / "unfinished.min"
        invalid.write_bytes(b'print("unfinished)\n')
        assert invoke(invalid).returncode == 1 and invalid.read_bytes() == b'print("unfinished)\n'
        assert not list(directory.glob("*.fmt.*")), "formatter left a replacement temporary behind"
    print("formatter preview, modes, symlinks, traversal, empty paths and failure preservation passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("formatter")
    options = parser.parse_args()
    run(str(Path(options.formatter).resolve()))
