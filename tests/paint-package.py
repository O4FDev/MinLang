#!/usr/bin/env python3
"""Install the actual unpublished paint tag through the GitHub transport route."""
import hashlib
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


def pixels(path):
    png = path.read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    offset, compressed, dimensions, ended = 8, bytearray(), None, False
    while offset < len(png):
        length = struct.unpack_from(">I", png, offset)[0]
        kind = png[offset + 4:offset + 8]
        payload = png[offset + 8:offset + 8 + length]
        assert len(payload) == length
        assert zlib.crc32(kind + payload) == struct.unpack_from(">I", png, offset + 8 + length)[0]
        if kind == b"IHDR":
            assert dimensions is None and offset == 8
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            assert (depth, color, compression, filtering, interlace) == (8, 6, 0, 0, 0)
            dimensions = width, height
        elif kind == b"IDAT":
            assert dimensions and not ended
            compressed.extend(payload)
        elif kind == b"IEND":
            assert not payload
            ended = True
        else:
            raise AssertionError((path, "unexpected PNG chunk", kind))
        offset += length + 12
        if ended:
            break
    assert ended and offset == len(png)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed) + decoder.flush()
    assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
    width, height = dimensions
    stride = width * 4
    assert len(raw) == height * (stride + 1)
    rgba = bytearray()
    for y in range(height):
        start = y * (stride + 1)
        assert raw[start] in (0, 1)
        row = bytearray(raw[start + 1:start + 1 + stride])
        if raw[start] == 1:
            for x in range(4, stride):
                row[x] = (row[x] + row[x - 4]) & 255
        rgba.extend(row)
    assert all(alpha == 255 for alpha in rgba[3::4])
    return dimensions, hashlib.sha256(rgba).hexdigest()


def main():
    launcher, source, example = (Path(value).resolve() for value in sys.argv[1:4])
    if not (source / ".git").exists():
        raise SystemExit("set MINYAR_PAINT_SOURCE to the local minyar-paint repository")
    with tempfile.TemporaryDirectory(prefix="minyar paint package ' ") as temporary:
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
        cases = [
            (example, "first-light", (640, 480), "first light · paint v0.1.0 · 640 × 480\n", "f436298955968f62d255f17bc22a4436f71dd72845caa0f31f20e8078eae8fe5", "6cf6af106897acf40c714e207f7e36d0c77aa0a93da8bb2152c6134b2b906230"),
            (example.parent / "observatory", "observatory", (960, 720), "observatory · paint v0.1.0 · 960 × 720\n", "2a8715d7201cafde48898551192fa41f950903c8f269acc268df0841cfe88042", "fbbff2dc0ba3041f79500d64e4e6688996dc66aa69cd986c98b1da40ea2dc174"),
        ]
        projects = []
        for folder, name, dimensions, message, pixel_hash, svg_hash in cases:
            project = root / (name + " project")
            shutil.copytree(folder, project, ignore=shutil.ignore_patterns("target", "*.png", "*.svg"))
            run(launcher, "add", "github.com/O4FDev/paint@v0.1.0", cwd=project)
            lock = (project / "Minyar.lock").read_text()
            assert 'source = "github.com/O4FDev/paint"' in lock and 'rev = "v0.1.0"' in lock
            arguments = []
            if name == "observatory":
                metadata = json.loads(run(launcher, "metadata", "--locked", "--offline", cwd=project))
                package = next(item for item in metadata["packages"] if item["name"] == "paint")
                font = Path(package["manifest_path"]).parent / "assets/CormorantGaramond.ttf"
                assert hashlib.sha256(font.read_bytes()).hexdigest() == "b20b7d9626dd956b2c5e558692ad328b1f19e3275e2782db4fa07670d83f35e0"
                arguments = ["--", font]
                assert pixels(folder / "preview.png") == (dimensions, pixel_hash)
            projects.append((project, name, dimensions, message, pixel_hash, svg_hash, arguments, lock))
        # Removing the mirror proves rendering needs only the content cache.
        shutil.rmtree(root / "mirror")
        for project, name, dimensions, message, pixel_hash, svg_hash, program_arguments, lock in projects:
            for release in (False, True):
                for suffix in (".png", ".svg"):
                    (project / (name + suffix)).unlink(missing_ok=True)
                arguments = [launcher, "run", "--locked", "--offline"]
                if release:
                    arguments.append("--release")
                output = run(*arguments, *program_arguments, cwd=project)
                assert message in output
                assert pixels(project / (name + ".png")) == (dimensions, pixel_hash), (name, "PNG pixels", release)
                svg = (project / (name + ".svg")).read_bytes()
                assert b"<linearGradient" in svg and hashlib.sha256(svg).hexdigest() == svg_hash, (name, "SVG paths", release)
                assert (project / "Minyar.lock").read_text() == lock
        print("Paint package: GitHub add, offline O0/O2 first light + observatory, TrueType, choices, generics, methods and exact PNG/SVG output passed")


if __name__ == "__main__":
    main()
