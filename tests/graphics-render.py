#!/usr/bin/env python3
"""Real renders: a fixed scene is deterministic, quad meshes draw exactly what
the same triangles draw, and a quad mesh must have four vertices per quad.
Needs a macOS desktop session (the graphics window opens briefly)."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

if sys.platform != 'darwin':
    print('graphics render tests skipped: they need a macOS desktop session')
    sys.exit(0)


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], cwd=ROOT, capture_output=True, text=True, timeout=120, **kwargs)


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

print('graphics renders are deterministic, quads match their triangles, and incomplete quads stop')
