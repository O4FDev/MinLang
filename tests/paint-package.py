#!/usr/bin/env python3
"""Install the actual unpublished paint tag through the GitHub transport route."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

if not __debug__:
    raise SystemExit("paint package checks require Python assertions; remove -O")


def main():
    launcher, source, example = (Path(value).resolve() for value in sys.argv[1:4])
    if not (source / ".git").exists():
        raise SystemExit("set MINYAR_PAINT_SOURCE to the local minyar-paint repository")
    with tempfile.TemporaryDirectory(prefix="minyar paint package ") as temporary:
        root = Path(temporary)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k not in ("MINYAR_REGISTRY", "MINYAR_HOME", "MINYAR_GIT_MIRROR")}
        env.update(MINYAR_HOME=str(root / "home"), MINYAR_GIT_MIRROR=str(root / "mirror"), GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")

        def run(*arguments, cwd=root):
            result = subprocess.run([str(value) for value in arguments], env=env, cwd=cwd, text=True, capture_output=True, timeout=180)
            assert result.returncode == 0, (arguments, result.stdout, result.stderr)
            return result.stdout

        mirror = root / "mirror/github.com/O4FDev/paint.git"
        mirror.parent.mkdir(parents=True)
        run("git", "clone", "--bare", "--quiet", source, mirror)
        project = root / "first light"
        shutil.copytree(example, project, ignore=shutil.ignore_patterns("target", "*.png", "*.svg"))
        run(launcher, "add", "github.com/O4FDev/paint@v0.1.0", cwd=project)
        lock = (project / "Minyar.lock").read_text()
        assert 'source = "github.com/O4FDev/paint"' in lock and 'rev = "v0.1.0"' in lock
        # Removing the mirror proves rendering needs only the content cache.
        shutil.rmtree(root / "mirror")
        for release in (False, True):
            for name in ("first-light.png", "first-light.svg"):
                (project / name).unlink(missing_ok=True)
            arguments = [launcher, "run", "--locked", "--offline"]
            if release:
                arguments.append("--release")
            output = run(*arguments, cwd=project)
            assert "first light · paint v0.1.0 · 640 × 480\n" in output
            png = (project / "first-light.png").read_bytes()
            assert png[:8] == b"\x89PNG\r\n\x1a\n"
            assert struct.unpack_from(">II", png, 16) == (640, 480)
            offset, compressed = 8, bytearray()
            while offset < len(png):
                length = struct.unpack_from(">I", png, offset)[0]
                kind = png[offset + 4:offset + 8]
                payload = png[offset + 8:offset + 8 + length]
                assert zlib.crc32(kind + payload) == struct.unpack_from(">I", png, offset + 8 + length)[0]
                if kind == b"IDAT":
                    compressed.extend(payload)
                offset += length + 12
            assert len(zlib.decompress(compressed)) == 480 * (640 * 4 + 1)
            assert "<linearGradient" in (project / "first-light.svg").read_text()
            assert (project / "Minyar.lock").read_text() == lock
        print("Paint package: GitHub-shaped add, source lock, offline O0/O2 PNG/SVG gallery passed")


if __name__ == "__main__":
    main()
