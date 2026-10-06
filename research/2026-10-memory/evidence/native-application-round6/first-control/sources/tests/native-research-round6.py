#!/usr/bin/env python3
"""Prepare, then run only the separately approved first hidden64 GL control."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory/evidence/native-application-round6'
PROPOSAL = ROOT / 'research/2026-10-memory/native-application-round6-proposal.json'
ACCEPTED = {'runtime/native/graphics.c': '736bc64a8bea8edb134d7752cdb9ad9f0f3e8174cbe0ef7f716e4698e8f33eed',
            'runtime/minyar_runtime.c': 'c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def expected_fixture():
    positions = [(-.75, -.75, 0.), (.75, -.75, 0.), (0., .75, 0.)]
    attributes = (.5, .5, .5, .75, .375, .5, .125)
    packed = b''.join(__import__('struct').pack('<10f', *p, *attributes) for p in positions)
    # Flat inputs make all interpolation immaterial. The expected code values
    # are simple radiometric products, not a duplicate renderer/shader program.
    assert .5 * .75 + .125 == .5
    assert [192 * .5 * .5, 128 * .75 * .5, 64 * .375 * .5] == [48, 48, 12]
    oracle = {'framebuffer': [64, 64], 'origin': 'bottom-left', 'channels': 'RGBA8',
              'triangle_window_coordinates': [[8, 8], [56, 8], [32, 56]],
              'interior_rgba': [48, 48, 12, 255], 'background_rgba': [32, 64, 128, 255],
              'tolerance_codes': 2, 'edge_exclusion_pixels': 2,
              'texel_rgba': [192, 128, 64, 255], 'color': [.5, .75, .375],
              'sky': .5, 'glow': .125, 'light': .75, 'brightness': .5,
              'clear_float_rgba': [.125, .25, .5, 1.], 'fog_range': [100, 101],
              'matrix': 'production initial identity', 'packed_bytes': 120,
              'expected_before_execution': True}
    return packed, oracle


def validate_pixels(payload, oracle):
    assert len(payload) == 64 * 64 * 4, len(payload)
    vertices = oracle['triangle_window_coordinates']
    inside = outside = excluded = max_error = 0
    for y in range(64):
        for x in range(64):
            # Independent geometric half-plane distances in framebuffer pixels;
            # no GL coverage/edge rule is assumed near the primitive boundary.
            distances = []
            for a, b in zip(vertices, vertices[1:] + vertices[:1]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                distances.append((dx * (y + .5 - a[1]) - dy * (x + .5 - a[0])) /
                                 math.hypot(dx, dy))
            if min(distances) >= oracle['edge_exclusion_pixels']:
                want = oracle['interior_rgba']
                inside += 1
            elif min(distances) <= -oracle['edge_exclusion_pixels']:
                want = oracle['background_rgba']
                outside += 1
            else:
                excluded += 1
                continue
            got = list(payload[(y * 64 + x) * 4:(y * 64 + x + 1) * 4])
            error = max(abs(a - b) for a, b in zip(got, want))
            assert error <= oracle['tolerance_codes'], (x, y, got, want, error)
            max_error = max(max_error, error)
    assert inside > 500 and outside > 2000
    return {'passed': True, 'interior_pixels': inside, 'background_pixels': outside,
            'excluded_edge_pixels': excluded, 'maximum_channel_error_codes': max_error,
            'tolerance_codes': oracle['tolerance_codes']}


def monitored(label, argv, cwd, evidence, report):
    stdout_path, stderr_path = evidence / (label + '.stdout'), evidence / (label + '.stderr')
    command = ['/usr/bin/time', '-l', *map(str, argv)]
    start = time.monotonic()
    sampled = 0
    failure = None
    limit = 256 * 1024**2
    with stdout_path.open('w') as out, stderr_path.open('w') as err:
        child = subprocess.Popen(command, cwd=cwd, stdout=out, stderr=err, start_new_session=True)
        while child.poll() is None:
            try:
                observation = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], capture_output=True,
                                             text=True, timeout=2)
                if observation.returncode:
                    raise RuntimeError('RSS sampler failed')
                rows = [tuple(map(int, row.split())) for row in observation.stdout.splitlines()]
                descendants = {child.pid}
                while True:
                    enlarged = descendants | {pid for pid, parent, _ in rows if parent in descendants}
                    if enlarged == descendants:
                        break
                    descendants = enlarged
                sampled = max(sampled, sum(rss * 1024 for pid, _, rss in rows if pid in descendants))
            except (subprocess.TimeoutExpired, ValueError, RuntimeError) as error:
                failure = 'sampling_failure:' + str(error)
            if sampled > limit:
                failure = 'sampled_rss_limit'
            if time.monotonic() - start > 30:
                failure = 'wall_limit'
            if failure:
                os.killpg(child.pid, signal.SIGKILL)
                break
            time.sleep(.05)
        child.wait(timeout=2)
    wall = time.monotonic() - start
    stderr = stderr_path.read_text()
    match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', stderr, re.M)
    peak = int(match[1]) if match else None
    row = {'label': label, 'argv': command, 'cwd': str(cwd), 'returncode': child.returncode,
           'wall_seconds': wall, 'sampled_process_group_peak_rss_bytes': sampled,
           'darwin_time_child_peak_rss_bytes': peak, 'limit_failure': failure,
           'stdout': str(stdout_path.relative_to(ROOT)), 'stderr': str(stderr_path.relative_to(ROOT)),
           'effective_optimization': 'O2', 'rss_threshold_bytes': limit,
           'rss_note': 'Sampled group RSS and OS child peak are distinct; neither measures driver/GPU memory.'}
    report['commands'].append(row)
    write_json(evidence / 'results.json', report)
    assert child.returncode == 0 and not failure and wall <= 30, row
    assert peak is not None and peak <= limit, row
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch(r'[a-z0-9-]+', args.label)
    evidence = BASE / args.label
    evidence.mkdir(exist_ok=False)
    work = ROOT / 'build/native-research-round6' / args.label
    work.mkdir(parents=True, exist_ok=False)
    report = {'status': 'preparing', 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'execute_requested': args.execute, 'commands': [], 'sources': [], 'objects': [],
              'real_context_attempts': 0, 'production_edits': False,
              'limits': {'one_native_child': True, 'wall_seconds': 30, 'rss_bytes': 256 * 1024**2},
              'limitations': 'No performance, GPU-memory, generated-code, sanitizer, leak, event-loop, presentation, screenshot/PNG, whole-app or production-teardown proof.'}
    try:
        for name, expected in ACCEPTED.items():
            assert digest(ROOT / name) == expected, name
        authorization = json.loads((BASE / 'authorization.json').read_text())
        assert authorization['approved'] and authorization['scope'] == 'first-hidden64-control-only'
        proposal = json.loads(PROPOSAL.read_text())
        assert proposal['status'] == 'approved_first_control' and proposal['native_wall_seconds'] == 30
        prior = json.loads((ROOT / 'research/2026-10-memory/evidence/native-application-round5/final-matrix/results.json').read_text())
        runtime = next(obj for obj in prior['objects'] if obj['mode'] == 'o2')
        runtime_path = Path(runtime['path'])
        assert digest(runtime_path) == runtime['sha256']
        dependency_source = ROOT / 'research/2026-10-memory/evidence/native-application-round2/final-matrix/sources'
        dependencies = [p for p in (ROOT / 'runtime').glob('minyar_*') if p.is_file() and p.suffix in ('.c', '.h')]
        for path in dependencies:
            relative = path.relative_to(ROOT)
            assert digest(path) == digest(dependency_source / relative), str(relative)
        report['objects'].append({**runtime, 'dependency_files_compared': len(dependencies)})
        frozen = evidence / 'sources'
        paths = dependencies + [ROOT / 'runtime/native/graphics.c', ROOT / 'runtime/native/opengl-functions.h',
                                ROOT / 'tests/native-research-round6.c', Path(__file__)]
        paths += [ROOT / p for p in ['README.md', 'docs/architecture.md', 'docs/toolchain.md',
                                    'research/2026-10-memory/native-application-round6-proposal.json']]
        for source in paths:
            relative = source.relative_to(ROOT)
            target = frozen / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            report['sources'].append({'path': str(relative), 'sha256': digest(target)})
        packed, oracle = expected_fixture()
        (evidence / 'triangle-120.bin').write_bytes(packed)
        write_json(evidence / 'expected-pixels.json', oracle)
        shutil.copy2(evidence / 'triangle-120.bin', work / 'triangle-120.bin')
        report['oracle_sha256'] = digest(evidence / 'expected-pixels.json')
        report['triangle_sha256'] = digest(evidence / 'triangle-120.bin')
        report['proposal_sha256'] = digest(PROPOSAL)
        report['authorization_sha256'] = digest(BASE / 'authorization.json')
        report['compiler'] = {'path': shutil.which('clang'), 'sha256': digest(Path(shutil.which('clang'))),
                              'version': subprocess.check_output(['clang', '--version'], text=True)}
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'glfw3'], text=True))
        libraries = shlex.split(subprocess.check_output(['pkg-config', '--libs', 'glfw3'], text=True))
        report['status'] = 'fixture_and_oracle_frozen_before_compilation'
        write_json(evidence / 'results.json', report)
        obj, binary = work / 'fixture.o', work / 'fixture'
        monitored('compile-o2', ['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2', *flags,
                                '-c', frozen / 'tests/native-research-round6.c', '-o', obj], work, evidence, report)
        report['objects'].append({'path': str(obj), 'sha256': digest(obj), 'role': 'real renderer plus typed fixture TU'})
        monitored('link-o2', ['clang', '-O2', obj, runtime_path, *libraries,
                             '-framework', 'OpenGL', '-lm', '-o', binary], work, evidence, report)
        report['binary_sha256'] = digest(binary)
        report['status'] = 'compiled_not_executed'
        write_json(evidence / 'results.json', report)
        if args.execute:
            # Save the intent before the only call that can create a GL context.
            report['real_context_attempts'] = 1
            report['status'] = 'approved_first_context_attempt_started'
            write_json(evidence / 'results.json', report)
            monitored('native-o2', [binary, '--approved-hidden64'], work, evidence, report)
            observations = [json.loads(row) for row in (evidence / 'native-o2.stdout').read_text().splitlines()]
            report['driver_observations'] = observations
            cleanup = next(row for row in observations if row['kind'] == 'cleanup')
            assert cleanup['completed'] and cleanup['gl_error'] == 0 and cleanup['context_destroyed']
            raw = (work / 'pixels-rgba8.bin').read_bytes()
            (evidence / 'pixels-rgba8.bin').write_bytes(raw)
            report['pixels_sha256'] = digest(evidence / 'pixels-rgba8.bin')
            report['pixel_oracle'] = validate_pixels(raw, oracle)
            report['status'] = 'passed_first_control'
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = repr(error)
        if (work / 'pixels-rgba8.bin').is_file():
            shutil.copy2(work / 'pixels-rgba8.bin', evidence / 'pixels-rgba8.bin')
        raise
    finally:
        report['completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['accepted_sources_unchanged'] = {name: digest(ROOT / name) == expected for name, expected in ACCEPTED.items()}
        write_json(evidence / 'results.json', report)
        # Durable input/readback/source records stay in evidence. Temporary build
        # files are removed; hashes preserve executable/object identity only.
        shutil.rmtree(work)
        print(json.dumps({'status': report['status'], 'evidence': str(evidence),
                          'real_context_attempts': report['real_context_attempts']}))


if __name__ == '__main__':
    main()
