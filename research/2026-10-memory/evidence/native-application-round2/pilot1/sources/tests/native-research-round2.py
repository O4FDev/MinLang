#!/usr/bin/env python3
"""Frozen native/application adversaries, independent terrain oracle, and bounded soak.

All mutations affect saved source copies. Never modifies production or core tests.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time

from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'research/2026-10-memory/evidence/native-application-round2'
SIZE, HEIGHT = 64, 16
AIR, STONE, WATER, GLASS, TORCH = 0, 3, 7, 10, 21
OPAQUE = {1, 2, 3, 4, 5, 8, 9, 11, 12, 13, 17, 18, 19, 20}
OFFSETS = [(0, 1, 0), (0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]
MODES = {'o0': ['-O0'], 'o2': ['-O2'],
         'sanitize': ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']}
PROFILES = {'eager': [], 'system': ['-DMINYAR_SYSTEM_HEAP=1'],
            'fixed': ['-DMINYAR_BOUNDED_HEAP=1'],
            'lazy': ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_LAZY_HEAP=1']}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_events():
    # The directed prefix supplies exact transitions, top rescans, no-ops,
    # boundary/outside controls, torch replacement, and stacked water.
    edits = [(-1, 1, 0, TORCH), (64, 1, 0, TORCH), (0, -1, 0, STONE),
             (0, 16, 0, STONE), (0, 1, -1, STONE), (0, 1, 64, STONE),
             (3, 1, 3, STONE), (4, 1, 3, STONE), (3, 1, 3, WATER),
             (4, 1, 3, WATER), (3, 2, 3, WATER), (3, 1, 3, GLASS),
             (4, 1, 3, GLASS), (3, 1, 3, AIR), (4, 1, 3, AIR),
             (3, 2, 3, AIR), (15, 15, 15, STONE), (15, 7, 15, STONE),
             (15, 15, 15, AIR), (15, 7, 15, GLASS), (15, 7, 15, TORCH),
             (15, 7, 15, TORCH), (16, 7, 16, TORCH), (15, 7, 15, WATER),
             (16, 7, 16, AIR), (0, 0, 0, STONE), (63, 15, 63, STONE),
             (63, 15, 63, TORCH), (63, 15, 63, TORCH), (63, 15, 63, AIR)]
    # Every directed transition's local chunk is meshed, including a boundary's neighbour.
    events = [(*edit, min(max(edit[0], 0), 63) // 16, min(max(edit[2], 0), 63) // 16)
              for edit in edits]
    state = 0x91a53
    positions = [0, 1, 7, 8, 15, 16, 17, 31, 32, 47, 48, 62, 63]
    materials = [AIR, STONE, WATER, GLASS, TORCH]
    for step in range(162):
        state = (state * 1664525 + 1013904223) & 0xffffffff
        x, z = positions[(state >> 8) % len(positions)], positions[(state >> 16) % len(positions)]
        y, material = (state >> 24) % HEIGHT, materials[state % len(materials)]
        cx, cz = x // 16, z // 16
        if step % 7 == 0:
            cx = (cx + 1) % 4
        events.append((x, y, z, material, cx, cz))
    return events


class WorldOracle:
    def __init__(self):
        self.blocks = bytearray(SIZE * SIZE * HEIGHT)
        self.top = [-1] * (SIZE * SIZE)
        self.torches = set()
        self.counts = Counter()

    def get(self, x, y, z):
        if 0 <= x < SIZE and 0 <= y < HEIGHT and 0 <= z < SIZE:
            return self.blocks[(y * SIZE + z) * SIZE + x]
        return AIR

    def apply(self, x, y, z, block):
        dirty = bytearray(1024)
        if not (0 <= x < SIZE and 0 <= y < HEIGHT and 0 <= z < SIZE):
            self.counts['outside'] += 1
            return dirty
        index = (y * SIZE + z) * SIZE + x
        old = self.blocks[index]
        if old == block:
            self.counts['unchanged'] += 1
            return dirty
        self.counts['changed'] += 1
        self.blocks[index] = block
        self.torches.discard(index)
        if block == TORCH:
            self.torches.add(index)
        old_top = self.top[z * SIZE + x]
        opaque_heights = [level for level in range(HEIGHT) if self.get(x, level, z) in OPAQUE]
        new_top = max(opaque_heights, default=-1)
        self.top[z * SIZE + x] = new_top
        reach = 8 if TORCH in (old, block) else 4 if old_top != new_top else 1
        # Independent interval/rectangle intersection, including fixed metadata chunks
        # beyond the prepared world's edge: terrain's public dirty grid is 32x32.
        for cz in range(32):
            for cx in range(32):
                if cx * 16 <= x + reach and cx * 16 + 15 >= x - reach and \
                        cz * 16 <= z + reach and cz * 16 + 15 >= z - reach:
                    dirty[cz * 32 + cx] = 1
        return dirty

    def sky(self, x, y, z):
        def top(xx, zz):
            return self.top[zz * SIZE + xx] if 0 <= xx < SIZE and 0 <= zz < SIZE else -1
        if y > top(x, z):
            return 1.0
        distances = [d for d in (1, 2, 3)
                     if any(y > top(xx, zz) for xx, zz in
                            [(x + d, z), (x - d, z), (x, z + d), (x, z - d)])]
        return 0.85 - min(distances) * 0.2 if distances else 0.1

    def glow(self, x, y, z):
        points = [(index % SIZE, index // (SIZE * SIZE), index // SIZE % SIZE)
                  for index in self.torches]
        return max([0.0, *(1 - math.dist((x, y, z), point) / 9 for point in points)])

    def faces(self, cx, cz):
        output = {'solid': [], 'water': []}
        for y in range(HEIGHT):
            for z in range(cz * 16, cz * 16 + 16):
                for x in range(cx * 16, cx * 16 + 16):
                    block = self.get(x, y, z)
                    if block == AIR:
                        continue
                    if block == TORCH:
                        lo, hi = (x + 7 / 16, y, z + 7 / 16), (x + 9 / 16, y + 10 / 16, z + 9 / 16)
                        directions = [0, 2, 3, 4, 5]
                    else:
                        height = 0.875 if block == WATER and self.get(x, y + 1, z) != WATER else 1
                        lo, hi = (x, y, z), (x + 1, y + height, z + 1)
                        directions = []
                        for direction, (dx, dy, dz) in enumerate(OFFSETS):
                            neighbour = self.get(x + dx, y + dy, z + dz)
                            if direction == 1 and y == 0:
                                continue
                            if neighbour not in OPAQUE and not (block in (WATER, GLASS) and neighbour == block):
                                directions.append(direction)
                    for direction in directions:
                        dx, dy, dz = OFFSETS[direction]
                        axis = 1 if dy else 0 if dx else 2
                        sign = (dx, dy, dz)[axis]
                        plane = hi[axis] if sign > 0 else lo[axis]
                        corners = []
                        for a in (0, 1):
                            for b in (0, 1):
                                point, others = [0.0] * 3, [i for i in range(3) if i != axis]
                                point[axis] = plane
                                point[others[0]] = (lo, hi)[a][others[0]]
                                point[others[1]] = (lo, hi)[b][others[1]]
                                corners.append(tuple(point))
                        output['water' if block == WATER else 'solid'].append({
                            'corners': tuple(sorted(corners)), 'normal': (dx, dy, dz),
                            'block': block, 'cell': (x, y, z), 'direction': direction,
                            'sky': 1.0 if block == TORCH else self.sky(x + dx, y + dy, z + dz),
                            'glow': 1.0 if block == TORCH else self.glow(x + dx, y + dy, z + dz)})
        return output


def check_geometry(data, faces):
    assert len(data) == len(faces) * 240, (len(data), len(faces))
    rows = list(struct.iter_unpack('<10f', data))
    # Face order and triangulation diagonal are free; compare the complete multiset
    # of independent rectangle surfaces, then verify each emitted triangle's winding.
    wanted = {face['corners']: face for face in faces}
    assert len(wanted) == len(faces), 'duplicate oracle face'
    seen = Counter()
    for offset in range(0, len(rows), 6):
        group = rows[offset:offset + 6]
        assert all(math.isfinite(value) for row in group for value in row)
        corners = tuple(sorted(set(tuple(row[:3]) for row in group)))
        assert corners in wanted, corners
        face = wanted[corners]
        seen[corners] += 1
        for start in (0, 3):
            a, b, c = [row[:3] for row in group[start:start + 3]]
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                     u[0] * v[1] - u[1] * v[0]]
            assert sum(cross[i] * face['normal'][i] for i in range(3)) > 0
        for row in group:
            assert math.isclose(row[8], face['sky'], abs_tol=1e-6)
            assert math.isclose(row[9], face['glow'], abs_tol=1e-6), (row[9], face)
            assert all(0 <= value <= 1 for value in row[3:8])
        if face['block'] != TORCH:
            tile = {STONE: 3, WATER: 8, GLASS: 11}[face['block']]
            u0, v0 = tile % 16 / 16 + 0.0005, tile // 16 / 16 + 0.0005
            u1, v1 = u0 + 0.0615, v0 + 0.0615
            assert all(any(math.isclose(row[3], u, abs_tol=1e-6) for u in (u0, u1)) and
                       any(math.isclose(row[4], v, abs_tol=1e-6) for v in (v0, v1)) for row in group)
    assert seen == Counter({face['corners']: 1 for face in faces})
    return len(rows)


def terrain_check(path, events):
    oracle = WorldOracle()
    total_vertices, hashes = Counter(), []
    with path.open('rb') as stream:
        for event, (x, y, z, block, cx, cz) in enumerate(events):
            parts = []
            for _ in range(4):
                header = stream.read(4)
                assert len(header) == 4, ('truncated snapshot header', event)
                length, = struct.unpack('<I', header)
                assert length < 4 * 1024 * 1024
                data = stream.read(length)
                assert len(data) == length
                parts.append(data)
            blocks, metadata, solid, water = parts
            dirty = oracle.apply(x, y, z, block)
            assert blocks == oracle.blocks, ('blocks', event)
            assert struct.unpack_from('<iii', metadata) == (event, cx, cz)
            tops = list(struct.unpack_from('<4096i', metadata, 12))
            assert tops == oracle.top, ('tops', event)
            assert metadata[16396:17420] == dirty, ('dirty', event)
            count, = struct.unpack_from('<I', metadata, 17420)
            actual_torches = list(struct.unpack_from(f'<{count}i', metadata, 17424))
            assert len(metadata) == 17424 + 4 * count
            assert len(actual_torches) == len(set(actual_torches)) and set(actual_torches) == oracle.torches, ('torches', event)
            faces = oracle.faces(cx, cz)
            total_vertices['solid'] += check_geometry(solid, faces['solid'])
            total_vertices['water'] += check_geometry(water, faces['water'])
            hashes.append(hashlib.sha256(solid + water).hexdigest())
        assert stream.read(1) == b'', 'trailing snapshots'
    return {'events': len(events), 'event_kinds': dict(oracle.counts), 'vertices': dict(total_vertices),
            'snapshots_sha256': digest(path), 'mesh_sequence_sha256': hashlib.sha256(''.join(hashes).encode()).hexdigest(),
            'final_blocks_sha256': hashlib.sha256(oracle.blocks).hexdigest(),
            'final_distinct_torches': len(oracle.torches), 'world_bytes_checked_per_event': len(oracle.blocks),
            'top_columns_checked_per_event': len(oracle.top), 'dirty_slots_checked_per_event': 1024}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--profiles', nargs='+', choices=PROFILES, default=['eager', 'system', 'fixed', 'lazy'])
    parser.add_argument('--modes', nargs='+', choices=MODES, default=['o0', 'o2', 'sanitize'])
    parser.add_argument('--calibrate', action='store_true')
    parser.add_argument('--native-only', action='store_true')
    args = parser.parse_args()
    if not args.label.replace('-', '').isalnum():
        parser.error('invalid label')
    evidence = EVIDENCE / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    sources = evidence / 'sources'
    work_parent = ROOT / 'build/native-research-round2'
    work_parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.label + '-', dir=work_parent))
    report = {'status': 'running', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'invocation': sys.argv, 'work': str(work), 'sources': [], 'commands': [], 'contracts': [],
              'calibrations': [], 'sanitizer_coverage': [], 'binaries': {},
              'scope': 'Real native graphics and generated actual terrain/meshing, typed CPU GL seams; no real GPU proof.',
              'host': {'platform': platform.platform(), 'loadavg': os.getloadavg()},
              'sanitizers': {'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                             'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1',
                             'limitations': 'Default ASan quarantine untouched. Native C ASan+UBSan; generated ASan only; LSan disabled.'}}
    environment = {**os.environ, **{key: value for key, value in report['sanitizers'].items() if key.endswith('_OPTIONS')}}

    def save():
        temporary = evidence / 'results.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(evidence / 'results.json')

    def execute(label, command, required=True, timeout=60):
        row = {'label': label, 'command': [str(item) for item in command], 'cwd': str(sources)}
        report['commands'].append(row)
        save()
        start = time.monotonic()
        try:
            result = subprocess.run(row['command'], cwd=sources, env=environment,
                                    capture_output=True, text=True, timeout=timeout)
            row.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                       wall_seconds=time.monotonic() - start)
            save()
            if required and result.returncode:
                raise RuntimeError((label, result.returncode, result.stderr))
            return result
        except subprocess.TimeoutExpired as error:
            row.update(timed_out=True, stdout=str(error.stdout), stderr=str(error.stderr))
            save()
            raise

    def contract(label, callback):
        row = {'label': label}
        report['contracts'].append(row)
        try:
            row.update(evidence=callback(), passed=True)
        except (AssertionError, ValueError, OSError, struct.error) as error:
            row.update(passed=False, error=repr(error))
        save()
        return row

    def check_png_result(result, png, stage):
        assert result.returncode == 1 and result.stderr == 'Minyar stopped: the computer ran out of memory.\n'
        stats = json.loads(result.stdout)
        assert stats['failed_call'] == stage and stats['malloc_calls'] == 3
        sizes = [256, 200, 211]
        assert stats['allocated_bytes'] == stats['peak_bytes'] == sum(sizes) - sizes[stage - 1]
        assert stats['live_bytes_at_exit'] == stats['allocated_bytes']
        assert not any(stats[key] for key in ['read_calls', 'open_calls', 'write_calls', 'close_calls'])
        assert stats['pending'] == 1 and not png.exists()
        return {'stats': stats, 'fatal_scope': 'Successful staging allocations are still live at process exit; no recoverability/leak claim.'}

    def check_retry(result, png):
        assert result.returncode == 0 and not result.stderr
        stats = json.loads(result.stdout)
        assert stats['malloc_calls'] == 3 and stats['allocated_bytes'] == stats['peak_bytes'] == 667
        assert stats['pending'] == 0 and stats['live_bytes_at_exit'] == 0
        assert stats['read_calls'] == stats['open_calls'] == stats['close_calls'] == 1 and stats['write_calls'] == 9
        # Load the maintained, independent CRC/zlib/flipped-pixel oracle without changing it.
        import importlib.util
        spec = importlib.util.spec_from_file_location('prior_native_oracle', sources / 'tests/native-research-application.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return {'stats': stats, 'png': module.validate_png(png, 8, 8), 'zero_frames': 6}

    def mesh_check(result):
        assert result.returncode == 0 and not result.stderr
        stats = json.loads(result.stdout)
        assert stats['creates'] == stats['deletes'] and stats['updates'] == stats['uploads']
        assert stats['batches'] == 1 and stats['capacity'] == 256 and stats['realloc_calls'] == 3
        assert stats['active'] == stats['array_live'] == stats['buffer_live'] == 0
        assert stats['object_peak'] == 512 and stats['registry_peak'] == stats['registry_bytes'] == 4096
        assert stats['full_checks'] == 1027
        assert stats['peak_rss_bytes'] <= 128 * 1024 * 1024
        return stats

    try:
        paths = list((ROOT / 'runtime').glob('minyar_*'))
        paths += list((ROOT / 'runtime/native').glob('*'))
        paths += list((ROOT / 'examples/craft').glob('*.min'))
        paths += list((ROOT / 'library').glob('*.min'))
        paths += [ROOT / 'tests' / name for name in ['native-research-round2.c', 'native-research-round2.min',
                  'native-research-round2.py', 'native-research-application.py', 'clang_helpers.py', 'llvm_sanitizer.py']]
        for path in paths:
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            target = sources / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            report['sources'].append({'path': str(relative), 'sha256': digest(target)})
        report['compiler_sha256'] = digest(ROOT / 'build/minyarc')
        status = subprocess.run(['git', 'status', '--porcelain=v1'], cwd=ROOT, text=True, capture_output=True, check=True)
        (evidence / 'preexisting-status.txt').write_text(status.stdout)
        for relative in ['runtime/native/graphics.c', 'examples/craft/terrain.min', 'examples/craft/meshing.min']:
            diff = subprocess.run(['git', 'diff', '--binary', '--', relative], cwd=ROOT, capture_output=True, check=True)
            (evidence / (Path(relative).stem + '-entry-dirty.patch')).write_bytes(diff.stdout)
        native_source = sources / 'runtime/native/graphics.c'
        source_text = native_source.read_text()
        anchor = 'while (slot < mesh_count && meshes[slot].used) slot++;'
        assert source_text.count(anchor) == 1
        source_text = source_text.replace(anchor, 'while (slot < mesh_count && (slot_checks++, meshes[slot].used)) slot++;')
        native_source.write_text(source_text)
        report['test_instrumentation'] = {'path': str(native_source.relative_to(evidence)),
                                          'sha256': digest(native_source), 'original_anchor': anchor,
                                          'meaning': 'Exact occupied-slot predicate counts; production remains untouched.'}
        save()
        execute('clang-version', ['clang', '--version'])
        cflags = shlex.split(execute('glfw-cflags', ['pkg-config', '--cflags', 'glfw3']).stdout)
        libraries = shlex.split(execute('glfw-libs', ['pkg-config', '--libs', 'glfw3']).stdout)
        libraries += ['-framework', 'OpenGL'] if platform.system() == 'Darwin' else ['-lGL']
        events = make_events()
        trace = evidence / 'terrain-events.bin'
        trace.write_bytes(b''.join(struct.pack('<6i', *event) for event in events))
        (evidence / 'terrain-events.json').write_text(json.dumps(events, indent=2) + '\n')
        report['terrain_trace'] = {'events': len(events), 'sha256': digest(trace), 'rng_seed': 0x91a53}
        llvm = work / 'application.ll'
        if not args.native_only:
            execute('frontend', [ROOT / 'build/minyarc', sources / 'tests/native-research-round2.min', llvm,
                                  '--library', sources / 'library'])
            report['generated_llvm_sha256'] = digest(llvm)
        for profile in args.profiles:
            for mode in args.modes:
                name = profile + '-' + mode
                common = ['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *MODES[mode], *PROFILES[profile],
                          '-DMINYAR_BOUNDED_HEAP_BYTES=33554432', '-DMINYAR_RC_POLL_BUDGET=32', *cflags]
                runtime = work / (name + '-runtime.o')
                execute(name + '-runtime', clang_command([*common, '-c', sources / 'runtime/minyar_runtime.c', '-o', runtime]))
                native = work / (name + '-native')
                execute(name + '-native', clang_command([*common, sources / 'tests/native-research-round2.c', runtime,
                                                         *libraries, '-o', native]))
                report['binaries'][name] = str(native)
                for stage in (1, 2, 3):
                    png = work / f'{name}-stage-{stage}.png'
                    result = execute(f'{name}-png-stage-{stage}', [native, 'png-fault', png, stage], required=False)
                    contract(f'{name}-png-stage-{stage}', lambda r=result, p=png, s=stage: check_png_result(r, p, s))
                png = work / (name + '-retry.png')
                result = execute(name + '-png-retry', [native, 'png-retry', png, 0])
                contract(name + '-png-retry', lambda r=result, p=png: check_retry(r, p))
                for seed in (0x51f37, 0x91a53, 0xffffffff, 0):
                    result = execute(f'{name}-mesh-{seed}', [native, 'mesh', seed, 1024, 0])
                    contract(f'{name}-mesh-{seed}', lambda r=result: mesh_check(r))
                if not args.native_only:
                    adapter = work / (name + '-adapter.o')
                    execute(name + '-adapter', clang_command([*common, '-Wno-unused-function', '-Wno-unused-variable',
                            '-DNATIVE_RESEARCH_ROUND2_LIBRARY=1', '-c', sources / 'tests/native-research-round2.c', '-o', adapter]))
                    ir = work / (name + '.ll')
                    shutil.copyfile(llvm, ir)
                    prepare_llvm_for_link(ir, MODES[mode])
                    if mode == 'sanitize':
                        headers = re.findall(r'^define [^\n]*', ir.read_text(), flags=re.M)
                        attributed = [row for row in headers if re.search(r'\bsanitize_address\b', row[row.rfind(')') + 1:])]
                        assert headers and len(headers) == len(attributed)
                        report['sanitizer_coverage'].append({'configuration': name, 'definitions': len(headers),
                            'sanitize_address_definitions': len(attributed), 'llvm_sha256': digest(ir)})
                    app = work / (name + '-application')
                    execute(name + '-link', clang_command(['clang', *MODES[mode], '-Wno-override-module', ir,
                                                           runtime, adapter, *libraries, '-o', app]))
                    output = work / (name + '-terrain.bin')
                    result = execute(name + '-terrain', [app, trace, output])
                    def check_app(r=result, p=output):
                        assert r.returncode == 0 and r.stdout == str(len(events)) + '\n' and not r.stderr
                        return terrain_check(p, events)
                    contract(name + '-terrain', check_app)
                print(name + ': saved contracts', flush=True)
        if args.calibrate:
            # Deliberate one-anchor source corruptions each must make a specific
            # existing independent contract red. Never changes ownership code.
            mutations = [
                ('png-oom-bypass', 'if (!pixels || !raw || !compressed)', 'if (0)', 'png-fault', 1),
                ('png-zero-original', 'if (width < 1 || height < 1) return;', '/* Original zero-framebuffer behavior. */', 'png-retry', 0),
                ('mesh-hint-delete', 'if (slot < mesh_next_slot) mesh_next_slot = slot;', '(void)slot;', 'mesh', 0x51f37),
                ('mesh-upload-size', '(GLsizeiptr)vertices->byte_length, vertices->bytes', '(GLsizeiptr)0, vertices->bytes', 'mesh', 0x51f37),
                ('mesh-draw-count', 'glDrawArrays(GL_TRIANGLES, 0, mesh->count);', 'glDrawArrays(GL_TRIANGLES, 0, mesh->count + 3);', 'mesh', 0x51f37)]
            # Calibration shares the exact saved system O2 runtime; source mutation
            # snapshots retain their own hashes/diffs and do not overwrite the baseline.
            name = 'system-o2'
            if name not in report['binaries']:
                raise ValueError('--calibrate requires system/o2')
            for label, before, after, operation, value in mutations:
                assert before in source_text
                changed = source_text.replace(before, after)
                mutant = work / (label + '.c')
                mutant.write_text(changed)
                # The include path remains the frozen native directory.
                stub = work / (label + '-fixture.c')
                stub.write_text((sources / 'tests/native-research-round2.c').read_text().replace(
                    '#include "../runtime/native/graphics.c"', '#include "' + str(mutant) + '"').replace(
                    '#include "../runtime/minyar_native.h"', '#include "' + str(sources / 'runtime/minyar_native.h') + '"'))
                binary = work / label
                execute(label + '-compile', clang_command(['clang', '-std=c11', '-O2', *cflags,
                        '-I', sources / 'runtime/native', stub, work / (name + '-runtime.o'), *libraries, '-o', binary]))
                png = work / (label + '.png')
                command = [binary, operation, value, 1024, 0] if operation == 'mesh' else [binary, operation, png, value]
                result = execute(label, command, required=False)
                if operation == 'mesh':
                    detected = result.returncode != 0
                else:
                    try:
                        (check_png_result(result, png, value) if operation == 'png-fault' else check_retry(result, png))
                        detected = False
                    except (AssertionError, ValueError):
                        detected = True
                row = {'label': label, 'detected': detected, 'returncode': result.returncode,
                       'before': before, 'after': after, 'mutant_sha256': digest(mutant)}
                report['calibrations'].append(row)
                save()
                assert detected, ('calibration survived', label)
        report['failures'] = [row['label'] for row in report['contracts'] if not row['passed']]
        report['status'] = 'red' if report['failures'] else 'passed'
        report['completed_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        report['sources_unchanged'] = all(digest(ROOT / row['path']) == row['sha256'] for row in report['sources'])
        save()
        print(json.dumps({'status': report['status'], 'contracts': len(report['contracts']),
                          'failures': report['failures'], 'evidence': str(evidence)}, indent=2))
        return int(bool(report['failures']))
    except Exception as error:
        report.update(status='infrastructure-failed', error=repr(error))
        save()
        raise


if __name__ == '__main__':
    sys.exit(main())
