#!/usr/bin/env python3
"""Real renders: a fixed scene is deterministic, quad meshes draw exactly what
the same triangles draw, light, fog and translucency changes between the
meshes of one frame all take effect, and a quad mesh must have four vertices
per quad. Needs a macOS desktop session (the graphics window opens briefly)."""
from pathlib import Path
import math
import struct
import subprocess
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]

if sys.platform != 'darwin':
    print('graphics render tests skipped: they need a macOS desktop session')
    sys.exit(0)


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], cwd=ROOT, capture_output=True, text=True, timeout=120, **kwargs)


def read_png(data):
    """Width, height and RGB rows of the library's uncompressed 8-bit PNGs."""
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    position, idat = 8, b''
    while position < len(data):
        length, kind = struct.unpack('>I4s', data[position:position + 8])
        body = data[position + 8:position + 8 + length]
        if kind == b'IHDR':
            width, height = struct.unpack('>II', body[:8])
        elif kind == b'IDAT':
            idat += body
        position += 12 + length
    raw = zlib.decompress(idat)
    row = width * 3 + 1
    assert all(raw[y * row] == 0 for y in range(height))
    return width, height, b''.join(raw[y * row + 1:(y + 1) * row] for y in range(height))


with tempfile.TemporaryDirectory(prefix='graphics-render-', dir=ROOT / 'build') as directory:
    work = Path(directory)
    program = work / 'render-check'
    built = run([ROOT / 'minyar', ROOT / 'benchmarks/desktop/render-check.min', '-o', program])
    assert built.returncode == 0, built.stderr
    images = {}
    for name, extra in (('triangles', []), ('triangles-again', []), ('quads', ['quads'])):
        image = work / (name + '.png')
        result = run([program, image, *extra])
        assert result.returncode == 0 and image.is_file(), (name, result.stderr)
        images[name] = image.read_bytes()
    assert images['triangles'] == images['triangles-again'], 'the same scene rendered differently twice'
    assert images['quads'] == images['triangles'], 'quads drew something other than their two triangles'

    # Light, fog and translucency change between the meshes of one frame; each
    # change must reach the next draw, and opaque draws after a translucent
    # one must cull back faces and write depth again.
    program = work / 'render-states'
    built = run([ROOT / 'minyar', ROOT / 'benchmarks/desktop/render-states.min', '-o', program])
    assert built.returncode == 0, built.stderr
    image = work / 'states.png'
    result = run([program, image])
    assert result.returncode == 0 and image.is_file(), result.stderr
    width, height, pixels = read_png(image.read_bytes())
    half_height = 5 * math.tan(math.radians(35))
    half_width = half_height * width / height

    def probe(x, y):
        column = int((x / half_width + 1) / 2 * width)
        row = int((1 - y / half_height) / 2 * height)
        offset = (row * width + column) * 3
        return tuple(pixels[offset:offset + 3])

    expected = {
        'light 0.25': ((-3.25, 1.75), (64, 64, 64)),
        'light 1.0 after 0.25': ((-1.25, 1.75), (255, 255, 255)),
        'fog after a light change': ((0.75, 1.75), (255, 0, 0)),
        'translucent at half opacity': ((2.75, 1.75), (128, 128, 179)),
        'back face culled after translucency': ((-3.25, -1.75), (0, 0, 102)),
        'depth written after translucency': ((-1.25, -1.75), (0, 255, 0)),
    }
    for name, ((x, y), colour) in expected.items():
        actual = probe(x, y)
        assert all(abs(a - e) <= 3 for a, e in zip(actual, colour)), (name, actual, colour)
    assert probe(-half_width * 0.99, half_height * 0.99) == (255, 255, 0), 'the overlay rectangle is missing'

    broken = work / 'broken.min'
    broken.write_text('use "graphics" as graphics\n'
                      'graphics.openWindow(64, 64, "Broken")\n'
                      'let mesh = graphics.createMesh()\n'
                      'let vertices = Bytes()\n'
                      'for corner in 0..3 { graphics.addVertex(vertices, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0) }\n'
                      'graphics.updateQuads(mesh, vertices)\n')
    built = run([ROOT / 'minyar', broken, '-o', work / 'broken'])
    assert built.returncode == 0, built.stderr
    result = run([work / 'broken'])
    assert result.returncode != 0 and 'four vertices per quad' in result.stderr, result

print('graphics renders are deterministic, quads match their triangles, state changes between draws take effect, and incomplete quads stop')
