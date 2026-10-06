#!/usr/bin/env python3
"""Bounded actual Craft save/load and movement correctness, with frozen runtime reuse."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import time

from llvm_sanitizer import prepare_llvm_for_link

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory/evidence/native-application-round5'
MATRIX = ROOT / 'research/2026-10-memory/evidence/native-application-round2/final-matrix'
FLAGS = {'o2': ['-O2'], 'o0': ['-O0'],
         'sanitize': ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']}
SAVED = (-12.5, 63.25, 0.125, -1.75, 0.375, 0.875)
WORLD = bytes((i * 17 + 3) % 22 for i in range(512))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_store(world, player, flying):
    assert world == WORLD
    assert player == struct.pack('<6dB', *SAVED, int(flying))
    return {'world_bytes': 512, 'player_bytes': 49, 'flying': flying}


def physics_expected():
    # Analytical endpoint contracts, not a grid-step/collision implementation.
    # Tuple fields: x,y,z,vx,vy,vz,yaw,pitch,width,height,ground,fly,water.
    base = [4.5, 2., 4.5, 0., 0., 0., 0., 0., .3, 1.8, 0, 0, 0]
    rows = []
    def add(**changes):
        names = ['x', 'y', 'z', 'vx', 'vy', 'vz', 'yaw', 'pitch', 'width', 'height',
                 'ground', 'fly', 'water']
        row = base.copy()
        for name, value in changes.items():
            row[names.index(name)] = value
        rows.append(row)
    add(y=1.72, z=4.07, vy=-2.8, vz=-4.3)
    diagonal = 4.3 / math.sqrt(2)
    add(x=4.5 + diagonal * .1, y=1.72, z=4.5 - diagonal * .1,
        vx=diagonal, vy=-2.8, vz=-diagonal)
    add(x=5.14, y=1.72, vx=6.4, vy=-2.8)
    add(y=1.93, z=4.242, vy=-.7, vz=-2.58, water=1)
    add(y=1.7, z=4.242, vy=-3., vz=-2.58, water=1)
    add(y=2.35, z=4.242, vy=3.5, vz=-2.58, water=1)
    add(x=5.7, y=3.2, vx=12., vy=12., fly=1)
    add(x=5.7, y=.8, vx=12., vy=-12., fly=1)
    add(y=1., ground=1)
    add(y=1.86, vy=8.6)
    add(x=4.699, fly=1)
    add(x=4.301, fly=1)
    add(y=2.199, fly=1)
    add(y=8.)
    add(vy=-50.)
    add(z=3.3, vz=-12., fly=1, water=1)
    return rows


def validate_physics(payload):
    assert len(payload) == 16 * 83 + 25, len(payload)
    rows = []
    for index, expected in enumerate(physics_expected()):
        actual = struct.unpack_from('<10d3B', payload, index * 83)
        for field, (got, want) in enumerate(zip(actual, expected)):
            assert math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-12), (index, field, got, want)
        rows.append(list(actual))
    # Materials are independently classified by gameplay roles.
    nonsolid = {0, 7, 14, 15, 16, 21}
    assert payload[16 * 83:] == bytes([int(i not in nonsolid) for i in range(22)] + [1, 0, 0])
    return {'movement_endpoints': rows, 'material_collision_flags': 22, 'occupancy_controls': 3,
            'logical_update_calls': 16, 'meaning': 'Calls in authored workload, not machine instructions.'}


def validate_load(directory, world_input, player_input):
    loaded = world_input is not None and len(world_input) == 512
    assert (directory / 'loaded-world.bin').read_bytes() == (world_input if loaded else bytes([255]) * 512)
    assert (directory / 'old-world-alias.bin').read_bytes() == bytes([255]) * 512
    valid_player = player_input is not None and len(player_input) == 49
    saved = struct.unpack('<6dB', player_input) if valid_player else (4.5, 2., 4.5, 0., 0., .125, 0)
    x, y, z, yaw, pitch, day, flying = saved
    expected = bytes([int(loaded)]) + struct.pack('<10d3B', x, y, z, 17., -4., 3., yaw, pitch,
                                                .3, 1.8, 1, int(flying == 1), 1)
    expected += struct.pack('<5dqBqq', day, .11, .22, .33, .44, 6, 1, 1, 123)
    assert (directory / 'loaded-state.bin').read_bytes() == expected
    return {'world_accepted': loaded, 'player_accepted': valid_player,
            'old_bytes_alias_preserved': True, 'metadata_preserved': True,
            'unserialized_player_sky_fields_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--modes', nargs='+', choices=FLAGS, default=['o2'])
    parser.add_argument('--calibrate', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch(r'[a-z0-9-]+', args.label)
    evidence = BASE / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    work = ROOT / 'build/native-research-round5' / args.label
    work.mkdir(parents=True, exist_ok=False)
    sources = evidence / 'sources'
    sources.mkdir()
    prior = json.loads((MATRIX / 'results.json').read_text())
    report = {'status': 'running', 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'invocation': sys.argv, 'commands': [], 'contracts': [], 'sources': [], 'objects': [],
              'sanitizer_coverage': [], 'calibrations': [], 'work': str(work),
              'limits': {'children': 1, 'wall_seconds': 30, 'compile_rss_bytes': 512 * 1024**2,
                         'native_rss_bytes': 128 * 1024**2},
              'sanitizer_options': {'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'},
              'limitations': 'Shared-host resource observations only; generated ASan/native ASan+UBSan; no generated UBSan or LSan; no complete game lifetime or allocation accounting.'}
    def save_report():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    def run(label, command, cwd, native=False, required=True):
        argv = ['/usr/bin/time', '-l', *map(str, command)]
        process = subprocess.Popen(argv, cwd=cwd, env={**os.environ, **report['sanitizer_options']},
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        start, sampled, failure = time.monotonic(), 0, None
        limit = report['limits']['native_rss_bytes' if native else 'compile_rss_bytes']
        while process.poll() is None:
            sample = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], capture_output=True,
                                    text=True, timeout=2)
            for line in sample.stdout.splitlines():
                pid, parent, rss = map(int, line.split())
                if pid == process.pid or parent == process.pid:
                    sampled = max(sampled, rss * 1024)
            if sampled > limit:
                failure = 'sampled_rss_limit'
            if time.monotonic() - start > 30:
                failure = 'wall_limit'
            if failure:
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(.01)
        stdout, stderr = process.communicate(timeout=2)
        match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', stderr, re.M)
        peak = int(match[1]) if match else None
        diagnostics = '\n'.join(line for line in stderr.splitlines() if line and not line[0].isspace())
        row = {'label': label, 'command': argv, 'cwd': str(cwd), 'returncode': process.returncode,
               'stdout': stdout, 'stderr': stderr, 'diagnostics': diagnostics,
               'wall_seconds': time.monotonic() - start, 'sampled_peak_rss_bytes': sampled,
               'darwin_time_peak_rss_bytes': peak, 'limit_failure': failure, 'native': native}
        report['commands'].append(row)
        save_report()
        assert not failure and peak is not None and peak <= limit, row
        assert row['wall_seconds'] <= 30, row
        if required:
            assert process.returncode == 0, row
        return row
    def contract(label, callback):
        row = {'label': label}
        try:
            row.update(passed=True, evidence=callback())
        except (AssertionError, ValueError, OSError) as error:
            row.update(passed=False, error=repr(error))
        report['contracts'].append(row)
        save_report()
    try:
        paths = list((ROOT / 'examples/craft').glob('*.min'))
        paths += list((ROOT / 'library').glob('*.min'))
        paths += list((ROOT / 'runtime').glob('minyar_*'))
        paths += [ROOT / 'runtime/native/graphics.c', ROOT / 'tests/native-research-round5.min',
                  ROOT / 'tests/native-research-round5.c',
                  Path(__file__), ROOT / 'tests/llvm_sanitizer.py', ROOT / 'tests/clang_helpers.py']
        paths += [ROOT / p for p in ['README.md', 'docs/architecture.md', 'docs/testing.md',
                                    'docs/performance.md', 'docs/toolchain.md', 'docs/runtime-memory.md']]
        for path in paths:
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            target = sources / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            report['sources'].append({'path': str(relative), 'sha256': digest(target)})
        (evidence / 'entry-status.txt').write_text(subprocess.run(
            ['git', 'status', '--porcelain=v1'], cwd=ROOT, text=True, capture_output=True, check=True).stdout)
        (evidence / 'entry-craft-graphics-dirty.patch').write_bytes(subprocess.run(
            ['git', 'diff', '--binary', '--', 'examples/craft', 'runtime/native/graphics.c'],
            cwd=ROOT, capture_output=True, check=True).stdout)
        report['compiler_sha256'] = digest(ROOT / 'build/minyarc')
        assert report['compiler_sha256'] == prior['compiler_sha256']
        for row in prior['sources']:
            if row['path'].startswith('runtime/minyar_'):
                assert digest(ROOT / row['path']) == row['sha256'], row
        run('clang-identity', ['clang', '--version'], sources)
        # Derive only ABI declarations from the real graphics header; every stub is fatal.
        text = (sources / 'runtime/native/graphics.c').read_text()
        signatures = re.findall(r'^(?:void|bool|long long|double) minyar_graphics_\w+\([^)]*\)', text, re.M)
        seam = '#include "runtime/minyar_native.h"\n'
        seam += '\n'.join(signature + ' { fputs("unexpected graphics seam reached\\n", stderr); exit(91); }'
                          for signature in signatures) + '\n'
        seam_path = sources / 'tests/native-research-round5-seam.c'
        seam_path.write_text(seam)
        report['seam'] = {'path': str(seam_path.relative_to(evidence)), 'sha256': digest(seam_path),
                          'fatal_symbols': len(signatures), 'extraction': 'Exact C graphics signatures only; no production bodies.'}
        llvm = work / 'application.ll'
        run('frontend', [ROOT / 'build/minyarc', sources / 'tests/native-research-round5.min',
                         llvm, '--library', sources / 'library'], sources)
        report['generated_llvm_sha256'] = digest(llvm)
        shutil.copyfile(llvm, evidence / 'application.ll')
        original_ir = llvm.read_text()
        instrumented = original_ir
        instrument_rows = []
        for name, old, new, expected in [
            ('loadWorld', '@minyar_read_bytes_file(', '@minyar_round5_save_read(', 1),
            ('loadPlayer', '@minyar_read_bytes_file(', '@minyar_round5_save_read(', 1),
            ('store', '@minyar_write_bytes_file(', '@minyar_round5_save_write(', 2)]:
            matches = list(re.finditer(r'^define [^\n]*@\.minyar\.fn\.\w+_' + name +
                                      r'\([^\n]*\) \{\n.*?^\}', instrumented, re.M | re.S))
            assert len(matches) == 1, name
            match = matches[0]
            body = match[0]
            assert body.count(old) == expected, name
            changed = body.replace(old, new)
            instrumented = instrumented[:match.start()] + changed + instrumented[match.end():]
            instrument_rows.append({'function': name, 'from': old, 'to': new, 'callsites': expected})
        instrumented += '\ndeclare ptr @minyar_round5_save_read(ptr)\n'
        instrumented += 'declare void @minyar_round5_save_write(ptr, ptr)\n'
        llvm.write_text(instrumented)
        shutil.copyfile(llvm, evidence / 'application-counted.ll')
        report['count_instrumentation'] = {'sha256': digest(llvm), 'callsites': instrument_rows,
                                          'meaning': 'Save-only logical runtime I/O requests; wrapper invokes unchanged runtime API; no allocation/machine-instruction count.'}
        for mode in args.modes:
            native_runtime = Path(prior['work']) / ('system-' + mode + '-runtime.o')
            compile_row = next(row for row in prior['commands'] if row['label'] == 'system-' + mode + '-runtime')
            report['objects'].append({'mode': mode, 'path': str(native_runtime), 'sha256': digest(native_runtime),
                                      'original_compile': compile_row, 'dependency_hashes_match': True})
            ir = work / (mode + '.ll')
            shutil.copyfile(llvm, ir)
            prepare_llvm_for_link(ir, FLAGS[mode])
            if mode == 'sanitize':
                headers = re.findall(r'^define [^\n]*', ir.read_text(), flags=re.M)
                annotated = [h for h in headers if re.search(r'\bsanitize_address\b', h[h.rfind(')') + 1:])]
                assert headers and len(headers) == len(annotated)
                report['sanitizer_coverage'].append({'definitions': len(headers),
                                                     'annotated_definitions': len(annotated), 'sha256': digest(ir)})
            binary = work / mode
            run(mode + '-link', ['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', *FLAGS[mode],
                                '-Wno-override-module', '-Wno-unused-parameter',
                                '-I', sources, ir, seam_path, sources / 'tests/native-research-round5.c',
                                native_runtime, '-o', binary], sources)
            def execute_case(label, operation, world_input=None, player_input=None):
                # All game filenames resolve within this new disposable fixture directory.
                directory = work / (mode + '-' + label)
                directory.mkdir(exist_ok=False)
                if world_input is not None:
                    (directory / 'minyarcraft-world.bin').write_bytes(world_input)
                if player_input is not None:
                    (directory / 'minyarcraft-player.bin').write_bytes(player_input)
                result = run(mode + '-' + label, [binary, operation], directory, native=True)
                stats = json.loads(result['stdout'])
                assert result['diagnostics'] == '', result
                expected = {'save_read_calls': 0, 'save_write_calls': 0,
                            'save_read_bytes': 0, 'save_write_bytes': 0}
                if operation.startswith('store'):
                    expected.update(save_write_calls=2, save_write_bytes=561)
                elif operation == 'load':
                    expected.update(save_read_calls=int(world_input is not None) + int(player_input is not None),
                                    save_read_bytes=len(world_input or b'') + len(player_input or b''))
                assert stats == expected, (label, stats, expected)
                result['save_api_counts'] = stats
                save_report()
                for path in directory.glob('*.bin'):
                    target = evidence / (mode + '-' + label) / path.name
                    target.parent.mkdir(exist_ok=True)
                    shutil.copyfile(path, target)
                return directory
            for flying in (True, False):
                label = 'store-' + str(int(flying))
                directory = execute_case(label, 'store' if flying else 'store-false')
                def check_store(d=directory, f=flying):
                    return validate_store((d / 'minyarcraft-world.bin').read_bytes(),
                                          (d / 'minyarcraft-player.bin').read_bytes(), f)
                contract(mode + '-' + label, check_store)
            cases = [('missing', None, None), ('valid', WORLD, struct.pack('<6dB', *SAVED, 1)),
                     ('valid-false', WORLD, struct.pack('<6dB', *SAVED, 0)),
                     ('empty', b'', b''), ('short', WORLD[:-1], bytes(48)),
                     ('long', WORLD + b'\x00', bytes(50)),
                     ('nonone-flag', WORLD, struct.pack('<6dB', *SAVED, 2)),
                     ('mixed-world-valid', WORLD, bytes(48)),
                     ('mixed-player-valid', WORLD[:-1], struct.pack('<6dB', *SAVED, 1))]
            for label, w, p in cases:
                directory = execute_case(label, 'load', w, p)
                contract(mode + '-' + label, lambda d=directory, wi=w, pi=p: validate_load(d, wi, pi))
            directory = execute_case('physics', 'physics')
            contract(mode + '-physics', lambda d=directory: validate_physics((d / 'physics.bin').read_bytes()))
        if args.calibrate:
            directory = work / 'seam-control'
            directory.mkdir(exist_ok=False)
            result = run('fatal-seam-control', [work / args.modes[0], 'graphics-control'],
                         directory, native=True, required=False)
            assert result['returncode'] == 91 and result['diagnostics'] == 'unexpected graphics seam reached', result
            assert all(value == 0 for value in json.loads(result['stdout']).values())
            report['calibrations'].append({'label': 'fatal-seam-control', 'detected': True,
                                            'kind': 'Actual graphics.createMesh call stops in headless seam',
                                            'returncode': result['returncode']})
            # Output-only controls prove byte/endpoint sensitivity without production mutations/builds.
            for label, payload, offset, validator in [
                ('physics-wall', (evidence / (args.modes[0] + '-physics/physics.bin')).read_bytes(),
                 10 * 83, validate_physics),
                ('physics-water', (evidence / (args.modes[0] + '-physics/physics.bin')).read_bytes(),
                 3 * 83 + 32, validate_physics)]:
                changed = bytearray(payload)
                struct.pack_into('<d', changed, offset, 999.)
                try:
                    validator(changed)
                    detected = False
                except AssertionError as error:
                    detected, diagnostic = True, repr(error)
                report['calibrations'].append({'label': label, 'detected': detected,
                                                'error': diagnostic, 'kind': 'output-only isolated corruption'})
                assert detected
            store_dir = evidence / (args.modes[0] + '-store-1')
            world_bytes = (store_dir / 'minyarcraft-world.bin').read_bytes()
            player_bytes = (store_dir / 'minyarcraft-player.bin').read_bytes()
            for label, w, p in [
                ('save-world-byte', bytes([world_bytes[0] ^ 1]) + world_bytes[1:], player_bytes),
                ('save-player-layout', world_bytes, player_bytes[:8] + bytes(8) + player_bytes[16:])]:
                try:
                    validate_store(w, p, True)
                    detected = False
                except AssertionError as error:
                    detected, diagnostic = True, repr(error)
                report['calibrations'].append({'label': label, 'detected': detected,
                                                'error': diagnostic, 'kind': 'output-only isolated corruption'})
                assert detected
        report['protected_changed'] = [row['path'] for row in report['sources']
                                       if digest(ROOT / row['path']) != row['sha256']]
        assert not report['protected_changed']
        report['failures'] = [row['label'] for row in report['contracts'] if not row['passed']]
        report['status'] = 'red' if report['failures'] else 'passed'
        report['completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_report()
        print(json.dumps({'status': report['status'], 'contracts': len(report['contracts']),
                          'failures': report['failures'], 'evidence': str(evidence)}))
        return int(bool(report['failures']))
    except Exception as error:
        report.update(status='infrastructure-failed', error=repr(error))
        save_report()
        raise


if __name__ == '__main__':
    sys.exit(main())
