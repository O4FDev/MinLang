#!/usr/bin/env python3
"""Base/delta generation safety, successive edits and native equivalence."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DRIVER = Path(os.environ.get('MINYAR_MODULE_DRIVER', ROOT / 'build/minyar-module-build'))
COMPILER = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc-modules'))


def run(command):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return result


with tempfile.TemporaryDirectory(prefix='minyar-delta-') as name:
    d = Path(name)
    entry = d / 'main.min'
    source = ''.join(f'use "./m{i}.min" as m{i}\n' for i in range(8))
    source += 'function main() { print(' + ' + '.join(f'm{i}.answer()' for i in range(8)) + ') }\n'
    entry.write_text(source)
    for i in range(8):
        (d / f'm{i}.min').write_text(f'public function answer(): Integer {{ return {i} }}\n')
    empty = d / 'empty'; empty.write_text('')
    output = d / 'out.ll'; cache = d / 'cache'; stats = d / 'stats'

    def build(expected=None):
        run([DRIVER, COMPILER, entry, output, cache, stats])
        counters = tuple(map(int, stats.read_text().split()[:6]))
        run([COMPILER, entry, d / 'cold.ll', '--module-state', empty, d / 'state', d / 'cold.stats'])
        assert output.read_bytes() == (d / 'cold.ll').read_bytes(), 'overlay differs from cold compilation'
        if expected is not None:
            assert counters[:2] == expected, counters
        assert not list(cache.glob('invocation.*'))
        return counters

    build((0, 9))
    base = next(cache.glob('*.cache')); original = base.read_bytes()
    delta = base.with_suffix('.cache.delta')
    entry.write_text(source.replace('print(', 'let extra = "λ"\nprint('))
    build((8, 1))
    assert base.read_bytes() == original, 'one edit rewrote base'
    assert delta.exists() and delta.stat().st_size < base.stat().st_size
    first_delta = delta.read_bytes()
    assert build((9, 0))[2:6] == (0, 9, 0, 0)
    (d / 'm0.min').write_text('public function answer(): Integer { return 20 }\n')
    build((8, 1))
    assert base.read_bytes() == original
    build((9, 0))
    # Reverting an earlier edit removes its overlay row without losing the
    # later dependency edit. Every comparison uses an independent cold build.
    entry.write_text(source)
    build((8, 1)); build((9, 0))
    saved_delta = delta.read_bytes()
    delta.write_bytes(b'broken overlay')
    build((8, 1)); build((9, 0))
    assert base.read_bytes() == original
    # Graph additions/reordering/removal require new interface tables while
    # stable code identities remain reusable.
    (d / 'new.min').write_text('public record New { value: Integer }\npublic function answer(): Integer { return 9 }\n')
    entry.write_text('use "./new.min" as new\n' + source)
    build((8, 2)); build((10, 0))
    entry.write_text(source + 'use "./new.min" as new\n')
    build((9, 1)); build((10, 0))
    entry.write_text(source)
    build((8, 1)); build((9, 0))
    # Changing most modules compacts to a fresh base. An old overlay must be
    # ignored even when its compiler and entry identities are still valid.
    for i in range(6):
        (d / f'm{i}.min').write_text(f'public function answer(): Integer {{ return {30+i} }}\n')
    build((3, 6))
    assert base.read_bytes() != original
    delta.write_bytes(first_delta)
    build((9, 0))
    # An older base combined with a newer overlay also cannot reuse a wrong
    # generation. It may lose cache hits, but must emit identical native code.
    new_base = base.read_bytes()
    entry.write_text(source.replace('print(', 'let second = 1\nprint('))
    build((8, 1))
    new_delta = delta.read_bytes()
    base.write_bytes(original)
    build()
    base.write_bytes(new_base); delta.write_bytes(new_delta)
    build((9, 0))
    run(['clang', '-O0', '-Wno-override-module', output, ROOT / 'build/minyar-runtime.o', '-o', d / 'program'])
    assert run([d / 'program']).stdout == '208\n'

print('module deltas: cumulative/reverted edits, graph changes, corruption and mismatched generations match cold native builds')
