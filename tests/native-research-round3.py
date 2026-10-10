#!/usr/bin/env python3
"""Bounded GL namespace calibration and PNG arithmetic probes; no production edits."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import struct
import subprocess
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 128 * 1024 * 1024
PNG_LIMIT = (1 << 31) - 1


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arithmetic(width, height):
    row = width * 3 + 1
    raw = row * height
    capacity = raw + (raw // 65535 + 1) * 5 + 6
    encoded = raw + ((raw + 65534) // 65535) * 5 + 6
    return dict(row=row, raw=raw, pixels=width * height * 4,
                capacity=capacity, encoded=encoded, idat_fits=encoded <= PNG_LIMIT)


def png_check(path, width, height):
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    offset, chunks, raw = 8, [], b''
    while offset < len(data):
        length = int.from_bytes(data[offset:offset + 4], 'big')
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc = int.from_bytes(data[offset + 8 + length:offset + 12 + length], 'big')
        assert length <= PNG_LIMIT and zlib.crc32(kind + payload) == crc
        chunks.append((kind.decode(), length))
        if kind == b'IHDR':
            assert payload == struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        if kind == b'IDAT':
            raw += payload
        offset += length + 12
    assert offset == len(data) and [row[0] for row in chunks] == ['IHDR', 'IDAT', 'IEND']
    wanted = b''.join(b'\0' + bytes(channel for x in range(width)
                                  for channel in (x & 255, y & 255, (x ^ y) & 255))
                      for y in reversed(range(height)))
    assert zlib.decompress(raw) == wanted
    expected = arithmetic(width, height)
    assert len(raw) == expected['encoded'] and len(wanted) == expected['raw']
    return dict(chunks=chunks, file_sha256=digest(path), **expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    evidence = ROOT / 'research/2026-10-memory/evidence/native-application-round3' / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    matrix_path = ROOT / 'research/2026-10-memory/evidence/native-application-round2/final-matrix/results.json'
    matrix = json.loads(matrix_path.read_text())
    assert matrix['status'] == 'passed'
    frozen = matrix_path.parent / 'sources'
    original_fixture_path = frozen / 'tests/native-research-round2.c'
    graphics_path = frozen / 'runtime/native/graphics.c'
    original_fixture = original_fixture_path.read_text()
    graphics = graphics_path.read_text()
    slot_probe = '(slot_checks++, meshes[slot].used)'
    assert graphics.count(slot_probe) == 1
    assert graphics.replace(slot_probe, 'meshes[slot].used') == (ROOT / 'runtime/native/graphics.c').read_text()
    (evidence / 'graphics-original.c').write_text(graphics)
    (evidence / 'fixture-original.c').write_text(original_fixture)
    for path in [Path(__file__), ROOT / 'tests/native-research-round3.c']:
        (evidence / path.name).write_bytes(path.read_bytes())
    work = ROOT / 'build/native-research-round3' / args.label
    work.mkdir(parents=True, exist_ok=False)
    report = dict(disposable_work=str(work), status='running', started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  matrix_sha256=digest(matrix_path), original_graphics_sha256=digest(graphics_path),
                  original_fixture_sha256=digest(original_fixture_path), commands=[], controls=[],
                  frozen_difference='Only saved slot_checks predicate instrumentation; normalized renderer equals current production',
                  sanitizer_options=matrix['sanitizers'], objects=[],
                  resource_limits=dict(native_wall_seconds=30, rss_bytes=LIMIT, native_children=1),
                  generated_code=False, production_edits=False)
    environment = {**os.environ, **{k: v for k, v in matrix['sanitizers'].items() if k.endswith('_OPTIONS')}}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, command, native=False):
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        process = subprocess.Popen([str(p) for p in command], cwd=ROOT, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
        sampled = 0
        failure = None
        while process.poll() is None:
            if native:
                sample = subprocess.run(['ps', '-o', 'rss=', '-p', str(process.pid)],
                                        capture_output=True, text=True, timeout=2)
                if sample.stdout.strip():
                    sampled = max(sampled, int(sample.stdout.strip()) * 1024)
                if sampled > LIMIT:
                    failure = 'rss_limit'
            if time.monotonic() - start > 30:
                failure = 'wall_limit'
            if failure:
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(0.005)
        stdout, stderr = process.communicate(timeout=2)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        row = dict(label=label, command=[str(p) for p in command], returncode=process.returncode,
                   stdout=stdout, stderr=stderr, wall_seconds=time.monotonic() - start,
                   child_cpu_seconds=(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime),
                   sampled_peak_rss_bytes=sampled, limit_failure=failure)
        report['commands'].append(row)
        save()
        assert not failure, row
        return row

    prefix = '''#include <stddef.h>
#include <setjmp.h>
#define NATIVE_RESEARCH_ROUND2_LIBRARY
static int round3_size_probe, round3_header_probe;
static size_t round3_sizes[3];
static unsigned char round3_uploaded[3840], round3_header[8];
static jmp_buf round3_header_jump;
'''

    def prepare(namespace, source, integration=False):
        start = 513 if namespace == 'distinct' else 1
        fixture = original_fixture.replace('MAX_NAMES = 512', 'MAX_NAMES = 1024')
        anchor = 'static void gen_buffers(GLsizei count, GLuint *names) {\n    assert(count == 1);\n    GLuint name = 1;'
        assert fixture.count(anchor) == 1
        fixture = fixture.replace(anchor, anchor.replace('GLuint name = 1;', f'GLuint name = {start};'))
        fixture = fixture.replace('    malloc_calls++;', '''    malloc_calls++;
    if (round3_size_probe) {
        assert(malloc_calls <= 3);
        round3_sizes[malloc_calls - 1] = size;
        return NULL;
    }''')
        fixture = fixture.replace('    write_calls++;', '''    write_calls++;
    if (round3_header_probe) {
        assert(size == 1 && count == 8);
        memcpy(round3_header, data, 8);
        longjmp(round3_header_jump, 1);
    }''')
        fixture = fixture.replace('    uploads++;', '''    assert((size_t)size <= sizeof(round3_uploaded));
    if (size) memcpy(round3_uploaded, data, (size_t)size);
    uploads++;''')
        fixture = fixture.replace('    assert(buffers[expected[slot].buffer].hash == expected[slot].hash);\n    /* GL seam',
                                  '    assert(buffers[expected[slot].buffer].hash == expected[slot].hash);\n'
                                  '    assert(!memcmp(round3_uploaded, reference, vertices * 40));\n    /* GL seam')
        fixture = fixture.replace('#include "../runtime/minyar_native.h"', f'#include "{frozen / "runtime/minyar_native.h"}"')
        fixture = fixture.replace('#include "../runtime/native/graphics.c"', f'#include "{source}"')
        if integration:
            return prefix.replace('#define NATIVE_RESEARCH_ROUND2_LIBRARY\n', '') + fixture
        return prefix + f'#define ROUND3_BUFFER_START {start}\n#define ROUND3_BUFFER_TEXT "{start}"\n' + fixture + '\n' + (ROOT / 'tests/native-research-round3.c').read_text()

    binaries = {}

    def compile_fixture(mode, namespace, source, label, integration=False):
        prepared = evidence / (label + '.c')
        prepared.write_text(prepare(namespace, source, integration))
        binary = work / label
        old = next(row['command'] for row in matrix['commands'] if row['label'] == 'system-' + mode + '-native')
        command = old.copy()
        command[command.index(str(original_fixture_path))] = str(prepared)
        command[command.index('-o') + 1] = str(binary)
        command[1:1] = ['-I', str(frozen / 'runtime/native')]
        runtime_object = Path(next(part for part in command if part.endswith('-runtime.o')))
        if not any(row['path'] == str(runtime_object) for row in report['objects']):
            report['objects'].append(dict(path=str(runtime_object), sha256=digest(runtime_object)))
        result = run(label + '-compile', command)
        assert result['returncode'] == 0, result['stderr']
        return binary

    # Mutations are separate single-site changes, each in a retained source copy.
    variants = {'original': graphics}
    for label, function, before, after in [
            ('swap-create-buffer', 'long long minyar_graphics_createMesh(',
             'glBindBuffer(GL_ARRAY_BUFFER, mesh->buffer);', 'glBindBuffer(GL_ARRAY_BUFFER, mesh->array);'),
            ('swap-update-buffer', 'void minyar_graphics_updateMesh(',
             'glBindBuffer(GL_ARRAY_BUFFER, mesh->buffer);', 'glBindBuffer(GL_ARRAY_BUFFER, mesh->array);'),
            ('swap-draw-array', 'void minyar_graphics_drawMesh(',
             'glBindVertexArray(mesh->array);', 'glBindVertexArray(mesh->buffer);')]:
        begin = graphics.index(function)
        end = graphics.index('\n}', begin) + 2
        section = graphics[begin:end]
        assert section.count(before) == 1
        variants[label] = graphics[:begin] + section.replace(before, after) + graphics[end:]
        report.setdefault('mutations', []).append(dict(label=label, function=function, before=before, after=after, occurrences=1))
    for label, text in variants.items():
        (evidence / ('graphics-' + label + '.c')).write_text(text)
    triangle = [(0, 0, 0, 0, 0, 1, 0.5, 0.25, 1, 0),
                (1, 0, 0, 1, 0, 0.25, 1, 0.5, 0.75, 0.125),
                (0, 1, 0, 0, 1, 0.5, 0.25, 1, 0.5, 0.25)]
    payload = struct.pack('<30f', *(value for vertex in triangle for value in vertex))
    triangle_path = evidence / 'triangle-120.bin'
    triangle_path.write_bytes(payload)
    report['triangle'] = dict(vertices=triangle, byte_length=len(payload), sha256=digest(triangle_path))
    save()
    for mode in ['o2', 'sanitize']:
        for namespace in ['coincident', 'distinct']:
            for variant in variants:
                label = f'{mode}-{namespace}-{variant}'
                binary = compile_fixture(mode, namespace, evidence / ('graphics-' + variant + '.c'), label)
                binaries[mode, namespace, variant] = binary
                row = run(label + '-tiny', [binary, 'tiny', triangle_path], native=True)
                must_fail = namespace == 'distinct' and variant != 'original'
                if must_fail:
                    wanted = 'buffers[name].used' if 'buffer' in variant else 'arrays[name]'
                    assert row['returncode'] != 0 and wanted in row['stderr'], row
                    assert 'AddressSanitizer' not in row['stderr'] and 'runtime error:' not in row['stderr']
                else:
                    assert row['returncode'] == 0 and not row['stderr'], row
                    stats = [json.loads(line) for line in row['stdout'].splitlines()]
                    assert stats[0]['buffer'] == (513 if namespace == 'distinct' else 1)
                    assert stats[-1]['peak_rss_bytes'] <= LIMIT
                report['controls'].append(dict(label=label + '-tiny', kind='namespace', namespace=namespace,
                                               mutation=variant, detected=must_fail, survived=variant != 'original' and not must_fail, passed=True))
                save()
    # Integration runs start only after every smallest control has calibrated.
    for mode in ['o2', 'sanitize']:
        binary = compile_fixture(mode, 'distinct', evidence / 'graphics-original.c', mode + '-distinct-trace', True)
        for seed in [0x51f37, 0x91a53, 0xffffffff, 0]:
            label = f'{mode}-trace-{seed}'
            row = run(label, [binary, 'mesh', str(seed), '1024', '0'], native=True)
            assert row['returncode'] == 0 and not row['stderr'], row
            stats = json.loads(row['stdout'])
            wanted = next(c['evidence'] for c in matrix['contracts'] if c['label'] == f'system-{mode}-mesh-{seed}')
            assert stats['trace_hash'] == wanted['trace_hash']
            assert stats['mixed_iterations'] == 1024 and stats['capacity'] == 256
            assert stats['creates'] == stats['deletes'] and stats['updates'] == stats['uploads'] == stats['draw_calls']
            assert stats['active'] == stats['array_live'] == stats['buffer_live'] == 0
            assert stats['peak_rss_bytes'] <= LIMIT
            report['controls'].append(dict(label=label, kind='integration', stats=stats, passed=True))
            save()
    # No-large-allocation arithmetic observations on original renderer.
    dimensions = [(0, 8), (8, 0), (-1, 8), (8, -1), (1, 1), (16384, 16384),
                  (16384, 43686), (16384, 43687), (536870913, 1), (715827884, 1),
                  (2147483647, 2147483647)]
    for mode in ['o2', 'sanitize']:
        binary = binaries[mode, 'distinct', 'original']
        for width, height in dimensions:
            label = f'{mode}-dimensions-{width}-{height}'
            row = run(label, [binary, 'dimensions', str(width), str(height)], native=True)
            stats = json.loads(row['stdout'])
            assert stats['peak_rss_bytes'] <= LIMIT
            assert not any(stats[k] for k in ['read_calls', 'open_calls', 'write_calls', 'close_calls'])
            expected = None
            if width <= 0 or height <= 0:
                assert row['returncode'] == 0 and not row['stderr'] and stats['malloc_calls'] == 0
            else:
                expected = arithmetic(width, height)
                assert row['returncode'] == 1 and row['stderr'] == 'Minyar stopped: the computer ran out of memory.\n'
                assert stats['malloc_calls'] == 3 and stats['sizes'] == [expected['pixels'], expected['raw'], expected['capacity']]
            assert stats['pending'] == 1
            report['controls'].append(dict(label=label, kind='dimensions', width=width, height=height,
                                           expected=expected, stats=stats, passed=True, no_large_allocation=True))
            save()
        for length in [0, PNG_LIMIT, PNG_LIMIT + 1, (1 << 32) - 1, 1 << 32]:
            label = f'{mode}-chunk-header-{length}'
            row = run(label, [binary, 'chunk-header', str(length)], native=True)
            stats = [json.loads(line) for line in row['stdout'].splitlines()]
            assert not row['stderr'] and row['returncode'] == (2 if length > PNG_LIMIT else 0)
            assert stats[0]['header'] == struct.pack('>I', length & 0xffffffff).hex() + '49444154'
            assert stats[1]['write_calls'] == 1 and stats[1]['malloc_calls'] == 0
            report['controls'].append(dict(label=label, kind='chunk-header', length=length,
                                           desired_reject_before_write=length > PNG_LIMIT,
                                           original_red=length > PNG_LIMIT, observed=stats, observation_passed=True,
                                           payload_read_or_encoded=False))
            save()
        # Real small PNG controls span exact and neighboring DEFLATE block boundaries.
        for width, height in [(1, 1), (8, 8), (2184, 10), (2185, 10), (7281, 3), (10922, 2)]:
            label = f'{mode}-small-png-{width}-{height}'
            path = evidence / (label + '.png')
            row = run(label, [binary, 'small-png', str(width), str(height), path], native=True)
            assert row['returncode'] == 0 and not row['stderr'], row
            report['controls'].append(dict(label=label, kind='small-png', passed=True, expected=png_check(path, width, height)))
            save()
    report.update(status='completed_with_retained_png_reds', finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    report['counts'] = dict(namespace_controls=sum(c['kind'] == 'namespace' for c in report['controls']),
                           distinct_mutants_detected=sum(c.get('detected', False) for c in report['controls']),
                           coincident_mutant_survivals=sum(c.get('survived', False) for c in report['controls']),
                           integration_traces=sum(c['kind'] == 'integration' for c in report['controls']),
                           dimension_observations=sum(c['kind'] == 'dimensions' for c in report['controls']),
                           header_observations=sum(c['kind'] == 'chunk-header' for c in report['controls']),
                           retained_png_reds=sum(c.get('original_red', False) for c in report['controls']),
                           real_small_pngs=sum(c['kind'] == 'small-png' for c in report['controls']))
    save()
    print(json.dumps(dict(status=report['status'], counts=report['counts'], results=str(evidence / 'results.json')), indent=2))


if __name__ == '__main__':
    main()
