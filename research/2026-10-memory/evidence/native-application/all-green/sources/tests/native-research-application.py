#!/usr/bin/env python3
"""Frozen headless native/application contracts and bounded work evidence.

No launcher/build integration is changed. Binaries live only under build/.
Use --expect-gaps to retain the original red observations without hiding them.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib

from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signed(value):
    return ((value + (1 << 63)) % (1 << 64)) - (1 << 63)


def noise_hash(x, z, seed):
    value = signed(signed(x * 374761393) + signed(z * 668265263))
    value = signed(value + signed(seed * 1442695041))
    value = signed((value ^ (value >> 13)) * 1274126177)
    return (value ^ (value >> 16)) & 0x7fffffff


def value_noise(x, z, seed):
    ix, iz = math.floor(x), math.floor(z)
    fx, fz = x - ix, z - iz
    fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    samples = [(noise_hash(ix + dx, iz + dz, seed) & 0xffffff) / 16777216
               for dz in range(2) for dx in range(2)]
    near = samples[0] + (samples[1] - samples[0]) * fx
    far = samples[2] + (samples[3] - samples[2]) * fx
    return near + (far - near) * fz


def fractal_noise(x, z, seed, octaves):
    total = weight = 0.0
    for octave in range(octaves):
        amplitude = 2.0 ** -octave
        total += value_noise(x * 2 ** octave, z * 2 ** octave, seed + octave * 7919) * amplitude
        weight += amplitude
    return total / weight


def validate_png(path, width, height):
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    offset, kinds, compressed = 8, [], b''
    while offset < len(data):
        length, = struct.unpack_from('>I', data, offset)
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc, = struct.unpack_from('>I', data, offset + 8 + length)
        assert zlib.crc32(kind + payload) == crc
        kinds.append(kind.decode('ascii'))
        if kind == b'IHDR':
            assert payload == struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        elif kind == b'IDAT':
            compressed += payload
        offset += length + 12
    assert offset == len(data) and kinds == ['IHDR', 'IDAT', 'IEND']
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed) + decoder.flush()
    assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
    expected = bytearray()
    for y in range(height):
        expected.append(0)
        for x in range(width):
            expected.extend((x & 255, (height - 1 - y) & 255, (x ^ (height - 1 - y)) & 255))
    assert raw == expected
    return {'png_bytes': len(data), 'raw_bytes': len(raw), 'sha256': digest(path)}


def validate_mesh(path):
    data = path.read_bytes()
    assert len(data) == 6 * 6 * 40
    vertices = list(struct.iter_unpack('<10f', data))
    assert all(all(math.isfinite(value) for value in row) for row in vertices)
    assert all(3 <= row[0] <= 4 and 1 <= row[1] <= 2 and 3 <= row[2] <= 4 for row in vertices)
    assert all(0 <= value <= 1 for row in vertices for value in row[3:])
    # Independent exposed-cube winding oracle: each triangle points outward.
    for start in range(0, len(vertices), 3):
        a, b, c = [row[:3] for row in vertices[start:start + 3]]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                  u[0] * v[1] - u[1] * v[0]]
        center = [sum(row[i] for row in (a, b, c)) / 3 - (3.5, 1.5, 3.5)[i]
                  for i in range(3)]
        assert sum(normal[i] * center[i] for i in range(3)) > 0
    return {'vertices': len(vertices), 'sha256': digest(path), 'outward_triangles': 12}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--expect-gaps', action='store_true')
    parser.add_argument('--modes', nargs='+', choices=['o0', 'o2', 'sanitize'],
                        default=['o0', 'o2', 'sanitize'])
    parser.add_argument('--profiles', nargs='+', choices=['eager', 'system', 'fixed', 'lazy'],
                        default=['eager'])
    parser.add_argument('--source-dir', type=Path, default=ROOT)
    parser.add_argument('--graphics-only', action='store_true')
    parser.add_argument('--slot-counts', action='store_true')
    args = parser.parse_args()
    if not args.label.replace('-', '').isalnum():
        parser.error('label must contain only letters, numbers and hyphens')
    evidence = ROOT / 'research/2026-10-memory/evidence/native-application' / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    sources = evidence / 'sources'
    build_parent = ROOT / 'build/native-research-application'
    build_parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.label + '-', dir=build_parent))
    compiler = ROOT / 'build/minyarc'
    report = {'status': 'running', 'label': args.label, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'invocation': sys.argv, 'work': str(work), 'commands': [], 'contracts': [], 'sources': [],
              'scope': 'Headless CPU helpers and small prepared craft world; no GPU/display or whole-game claim.',
              'host': {'platform': platform.platform(), 'loadavg': os.getloadavg(),
                       'memory_bound': 'World 8192 block bytes; largest PNG fixture ~181 KiB staged; mesh registry <=4096.'}}
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    report['sanitizers'] = {'ASAN_OPTIONS': environment['ASAN_OPTIONS'], 'UBSAN_OPTIONS': environment['UBSAN_OPTIONS'],
                            'leak_scope': 'LSan disabled consistently with maintained macOS harnesses; this is not leak proof.'}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def execute(label, command, required=True):
        entry = {'label': label, 'command': [str(part) for part in command], 'cwd': str(sources)}
        report['commands'].append(entry)
        save()
        try:
            result = subprocess.run(entry['command'], cwd=sources, env=environment,
                                    text=True, capture_output=True, timeout=60)
            entry.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            save()
            if required and result.returncode:
                raise RuntimeError(f'{label}: {result.stderr}')
            return result
        except subprocess.TimeoutExpired as error:
            entry.update(timed_out=True, stdout=str(error.stdout), stderr=str(error.stderr))
            save()
            raise

    def contract(label, callback):
        entry = {'label': label}
        report['contracts'].append(entry)
        try:
            entry['evidence'] = callback()
            entry['passed'] = True
        except (AssertionError, ValueError, OSError, struct.error, zlib.error) as error:
            entry.update(passed=False, error=repr(error))
        save()

    def exact(result, expected):
        assert result.returncode == 0
        assert result.stdout == expected, {'actual': result.stdout, 'expected': expected}
        return {'stdout': result.stdout}

    try:
        paths = list((args.source_dir / 'runtime').glob('minyar_*'))
        paths += list((args.source_dir / 'runtime/native').glob('*'))
        paths += list((args.source_dir / 'examples/craft').glob('*.min'))
        paths += list((args.source_dir / 'library').glob('*.min'))
        paths += [ROOT / 'tests' / name for name in ['native-research-graphics.c', 'native-research-craft.min',
                                                     'native-research-application.py', 'clang_helpers.py', 'llvm_sanitizer.py']]
        for path in paths:
            if not path.is_file(): continue
            relative = path.relative_to(ROOT if path.parent == ROOT / 'tests' else args.source_dir)
            target = sources / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            report['sources'].append({'path': str(relative), 'sha256': digest(target)})
        report['compiler_sha256'] = digest(compiler)
        if args.slot_counts:
            source = sources / 'runtime/native/graphics.c'
            text = source.read_text()
            anchor = 'while (slot < mesh_count && meshes[slot].used) slot++;'
            assert text.count(anchor) == 1, 'mesh count instrumentation anchor changed'
            prefix = '#ifdef NATIVE_RESEARCH_SLOT_COUNTS\nstatic size_t native_research_slot_checks;\n#define NATIVE_RESEARCH_SLOT_USED(slot) (native_research_slot_checks++, meshes[slot].used)\n#else\n#define NATIVE_RESEARCH_SLOT_USED(slot) meshes[slot].used\n#endif\n'
            text = text.replace('long long minyar_graphics_createMesh(void) {', prefix + '\nlong long minyar_graphics_createMesh(void) {')
            text = text.replace(anchor, 'while (slot < mesh_count && NATIVE_RESEARCH_SLOT_USED(slot)) slot++;')
            source.write_text(text)
            report['count_instrumentation'] = {'file': 'runtime/native/graphics.c', 'anchor': anchor,
                                              'sha256': digest(source),
                                              'scope': 'Actual occupied-slot predicate evaluations; CPU binaries keep counter disabled.'}
        execute('clang-version', ['clang', '--version'])
        cflags = shlex.split(execute('glfw-cflags', ['pkg-config', '--cflags', 'glfw3']).stdout)
        libraries = shlex.split(execute('glfw-libs', ['pkg-config', '--libs', 'glfw3']).stdout)
        if platform.system() == 'Darwin': libraries += ['-framework', 'OpenGL']
        else: libraries += ['-lGL']
        llvm = work / 'craft.ll'
        if not args.graphics_only:
            execute('craft-frontend', [compiler, sources / 'tests/native-research-craft.min', llvm,
                                      '--library', sources / 'library'])
            report['generated_llvm_sha256'] = digest(llvm)
        modes = {'o0': ['-O0'], 'o2': ['-O2'],
                 'sanitize': ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']}
        profiles = {'eager': [], 'system': ['-DMINYAR_SYSTEM_HEAP=1'],
                    'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
                    'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1']}
        for profile in args.profiles:
            for mode in args.modes:
                label = profile + '-' + mode
                flags = modes[mode]
                common = ['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                          *profiles[profile], '-DMINYAR_BOUNDED_HEAP_BYTES=33554432',
                          '-DMINYAR_RC_POLL_BUDGET=32', *cflags]
                runtime = work / (label + '-runtime.o')
                execute(label + '-runtime', clang_command([*common, '-c', sources / 'runtime/minyar_runtime.c', '-o', runtime]))
                graphics = work / (label + '-graphics')
                execute(label + '-graphics-compile', clang_command([*common, sources / 'tests/native-research-graphics.c',
                                                                     runtime, *libraries, '-o', graphics]))
                result = execute(label + '-helpers', [graphics])
                contract(label + '-helpers', lambda r=result: exact(r, 'vertex bytes, refill initialization, matrix alias, buffer growth, UTF8 width, input bounds\n'))
                for width, height in [(1, 1), (257, 83), (28, 771), (1, 16383), (1, 16384)]:
                    png = work / f'{label}-{width}x{height}.png'
                    execute(label + f'-png-{width}x{height}', [graphics, 'png', width, height, png, 0])
                    contract(label + f'-png-{width}x{height}', lambda p=png, w=width, h=height: validate_png(p, w, h))
                for width, height in [(0, 1), (1, 0), (0, 0)]:
                    png = work / f'{label}-zero-{width}x{height}.png'
                    result = execute(label + f'-zero-{width}x{height}', [graphics, 'png', width, height, png, 0])
                    def check_zero(p=png, r=result):
                        assert not p.exists(), 'zero framebuffer should defer screenshot; must not publish invalid PNG'
                        assert json.loads(r.stdout)['pending'] == 1
                        return {'pending': True, 'file_created': False}
                    contract(label + f'-zero-{width}x{height}', check_zero)
                for fault in [1, 2]:
                    result = execute(label + f'-io-fault-{fault}', [graphics, 'png', 8, 8, work / f'{label}-fault-{fault}.png', fault], required=False)
                    def check_fault(r=result):
                        assert r.returncode == 1 and r.stderr == 'Minyar stopped: the screenshot file could not be written.\n', (r.returncode, r.stderr)
                        return {'diagnostic': r.stderr, 'returncode': r.returncode}
                    contract(label + f'-io-fault-{fault}', check_fault)
                result = execute(label + '-mesh-handles', [graphics, 'meshes', 1024])
                contract(label + '-mesh-handles', lambda r=result: {'counts': json.loads(r.stdout)})
                result = execute(label + '-mesh-model', [graphics, 'mesh-model'])
                contract(label + '-mesh-model', lambda r=result: {'model': json.loads(r.stdout)})
                if args.slot_counts:
                    counted = work / (label + '-mesh-counted')
                    execute(label + '-mesh-counted-compile', clang_command([*common, '-DNATIVE_RESEARCH_SLOT_COUNTS=1',
                            sources / 'tests/native-research-graphics.c', runtime, *libraries, '-o', counted]))
                    for count in [128, 512, 1024, 4096]:
                        result = execute(label + f'-mesh-counts-{count}', [counted, 'meshes', count])
                        def check_work(r=result, n=count):
                            row = json.loads(r.stdout)
                            assert row['initial_slot_checks'] <= n, row
                            assert row['reuse_slot_checks'] <= n, row
                            return row
                        contract(label + f'-mesh-linear-work-{count}', check_work)
                if args.graphics_only: continue
                native = work / (label + '-native.o')
                # Unused local GL seams are legitimate in the metrics/library-only build.
                execute(label + '-native', clang_command([*common, '-Wno-unused-function', '-Wno-unused-variable',
                        '-DNATIVE_RESEARCH_LIBRARY_ONLY=1', '-c', sources / 'tests/native-research-graphics.c', '-o', native]))
                generated = work / (label + '-craft.ll')
                shutil.copyfile(llvm, generated)
                prepare_llvm_for_link(generated, flags)
                application = work / (label + '-craft')
                execute(label + '-link', clang_command(['clang', *flags, '-Wno-override-module', generated,
                                                        runtime, native, *libraries, '-o', application]))
                for workload, expected in [('torch', '1\n3171\n3\n2\n0\n0\n'),
                        ('mesh', '1440\n0\n36\n2400\n0\n60\n0\n2400\n60\n76800\n0\n1920\n'),
                        ('physics', 'true\n4\n2\n1\n0\n0\n1\nfalse\n')]:
                    mesh = work / (label + '-cube.bin')
                    result = execute(label + '-' + workload, [application, workload, mesh] if workload == 'mesh' else [application, workload])
                    contract(label + '-' + workload, lambda r=result, e=expected: exact(r, e))
                    if workload == 'mesh': contract(label + '-cube-winding', lambda p=mesh: validate_mesh(p))
                result = execute(label + '-noise', [application, 'noise'])
                def check_noise(r=result):
                    rows = r.stdout.splitlines()
                    expected = [noise_hash(0, 0, 123), noise_hash(-17, 19, -3), noise_hash(1000000, -2000000, 77),
                                value_noise(-0.25, 1.75, 123), fractal_noise(1.25, -2.75, 123, 4),
                                sum(noise_hash(x, z, 123) for z in range(-16, 16) for x in range(-16, 16))]
                    assert len(rows) == len(expected)
                    for actual, wanted in zip(rows, expected):
                        if isinstance(wanted, int): assert int(actual) == wanted
                        else: assert math.isclose(float(actual), wanted, abs_tol=1e-12, rel_tol=1e-12)
                    return {'actual': rows, 'expected': expected, 'integer_grid_cells': 1024}
                contract(label + '-noise', check_noise)
        failures = [item['label'] for item in report['contracts'] if not item['passed']]
        report.update(status='red' if failures else 'passed', failures=failures, completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        save()
        print(json.dumps({'evidence': str(evidence), 'status': report['status'], 'contracts': len(report['contracts']), 'failures': failures}, indent=2))
        return int(bool(failures) and not args.expect_gaps)
    except Exception as error:
        report.update(status='infrastructure-failed', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    sys.exit(main())
