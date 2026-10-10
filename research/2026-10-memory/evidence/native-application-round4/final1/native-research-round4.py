#!/usr/bin/env python3
"""Bounded original, isolated PNG repair, and final production-source validation."""
import argparse
from collections import Counter
import datetime
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory/evidence/native-application-round4'
CONTROLS = ROOT / 'research/2026-10-memory/evidence/native-application-round3/control4'
PROPOSAL = ROOT / 'research/2026-10-memory/evidence/native-application-round3/png-proposal1'
LIMIT = 128 * 1024 * 1024
spec = importlib.util.spec_from_file_location('round3', ROOT / 'tests/native-research-round3.py')
round3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round3)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_pair():
    original = (BASE / 'entry/graphics.c').read_text()
    candidate = (PROPOSAL / 'graphics-proposed.c').read_text()
    candidate = candidate.replace('(slot_checks++, meshes[slot].used)', 'meshes[slot].used')
    patch = ''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
                                        fromfile='a/runtime/native/graphics.c',
                                        tofile='b/runtime/native/graphics.c'))
    assert patch == (PROPOSAL / 'minimal-proposed.patch').read_text()
    assert digest(PROPOSAL / 'minimal-proposed.patch') == json.loads(
        (PROPOSAL / 'results.json').read_text())['patch_sha256']
    return original, candidate, patch


def decode(path, width, height):
    result = round3.png_check(path, width, height)
    data, offset, payload = path.read_bytes(), 8, b''
    while offset < len(data):
        length = int.from_bytes(data[offset:offset + 4], 'big')
        if data[offset + 4:offset + 8] == b'IDAT':
            payload += data[offset + 8:offset + 8 + length]
        offset += length + 12
    decoder = zlib.decompressobj()
    raw = decoder.decompress(payload) + decoder.flush()
    assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
    assert len(raw) == result['raw']
    # Inspect the stored-block representation separately from zlib's decoder.
    assert payload[:2] == b'\x78\x01'
    offset, lengths, final = 2, [], False
    while not final:
        header = payload[offset]
        assert header in (0, 1)
        final = bool(header)
        length = int.from_bytes(payload[offset + 1:offset + 3], 'little')
        complement = int.from_bytes(payload[offset + 3:offset + 5], 'little')
        assert length ^ complement == 65535 and 0 < length <= 65535
        lengths.append(length)
        offset += 5 + length
    assert offset + 4 == len(payload) and sum(lengths) == result['raw']
    assert int.from_bytes(payload[offset:], 'big') == zlib.adler32(raw)
    return dict(**result, stored_blocks=lengths, complete_zlib_stream=True)


def prepare(mode, source):
    old = CONTROLS / (mode + '-distinct-original.c')
    fixture = old.read_text()
    anchor = str(CONTROLS / 'graphics-original.c')
    assert fixture.count(anchor) == 1
    fixture = fixture.replace(anchor, str(source))
    fixture = fixture.replace('static int round3_size_probe, round3_header_probe;',
                              'static int round3_size_probe, round3_header_probe;\n'
                              'static int round4_io_fault;\nstatic void round4_stats(void);')
    fixture = fixture.replace('    malloc_calls++;\n',
                              '    malloc_calls++;\n'
                              '    assert(malloc_calls <= 3);\n'
                              '    round3_sizes[malloc_calls - 1] = size;\n')
    fixture = fixture.replace('    open_calls++;\n',
                              '    open_calls++;\n    if (round4_io_fault == 10) return NULL;\n')
    fixture = fixture.replace('    write_calls++;\n',
                              '    write_calls++;\n'
                              '    if (round4_io_fault < 0 && write_calls == (size_t)-round4_io_fault)\n'
                              '        return count ? fwrite(data, size, count - 1, file) : 0;\n')
    fixture = fixture.replace('    return fclose(file);\n',
                              '    int result = fclose(file);\n'
                              '    return round4_io_fault == 20 ? EOF : result;\n')
    # The frozen round2 main is still present under its disabled preprocessor guard.
    assert fixture.count('int main(int argc, char **argv)') == 2
    before, after = fixture.rsplit('int main(int argc, char **argv)', 1)
    fixture = before + 'static int round3_entry(int argc, char **argv)' + after
    fixture = fixture.replace('atexit(round3_stats)', 'atexit(round4_stats)')
    return fixture + '\n' + (ROOT / 'tests/native-research-round4.c').read_text()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--source', choices=['entry', 'candidate', 'current'], required=True)
    parser.add_argument('--loader', action='store_true')
    args = parser.parse_args()
    evidence = BASE / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    work = ROOT / 'build/native-research-round4' / args.label
    work.mkdir(parents=True, exist_ok=False)
    original, candidate, patch = source_pair()
    current = (ROOT / 'runtime/native/graphics.c').read_text()
    if args.source == 'current':
        assert current == candidate
        source_text = current
    else:
        assert current == original
        source_text = original if args.source == 'entry' else candidate
    source = evidence / 'graphics.c'
    source.write_text(source_text)
    (evidence / 'reviewed-minimal.patch').write_text(patch)
    for path in [Path(__file__), ROOT / 'tests/native-research-round4.c']:
        (evidence / path.name).write_bytes(path.read_bytes())
    prior = json.loads((CONTROLS / 'results.json').read_text())
    for item in prior['objects']:
        assert digest(Path(item['path'])) == item['sha256']
    report = dict(status='running', source_kind=args.source, source_sha256=digest(source),
                  production_sha256_at_start=digest(ROOT / 'runtime/native/graphics.c'),
                  started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  commands=[], contracts=[], objects=prior['objects'],
                  fixture_origin_sha256=digest(CONTROLS / 'o2-distinct-original.c'),
                  readonly_harness_sha256=digest(ROOT / 'tests/native-research-round3.py'),
                  sanitizer_options={'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                                     'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'},
                  generated_code=False, fresh_core_build=False,
                  limits={'native_children': 1, 'wall_seconds_per_command': 30, 'rss_bytes': LIMIT},
                  limitations='int32/size_t64 ABI; no huge allocation, payload encoding or GPU readback; no performance or LSan claim')
    environment = {**os.environ, **report['sanitizer_options']}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, command, native=False):
        command = [str(part) for part in command]
        argv = ['/usr/bin/time', '-l', *command] if native else command
        start = time.monotonic()
        process = subprocess.Popen(argv, cwd=ROOT, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
        sampled, failure = 0, None
        while process.poll() is None:
            if native:
                # Darwin time execs the native child; sample both its PID and immediate children.
                sample = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss='], capture_output=True,
                                        text=True, timeout=2)
                for line in sample.stdout.splitlines():
                    pid, parent, rss = map(int, line.split())
                    if pid == process.pid or parent == process.pid:
                        sampled = max(sampled, rss * 1024)
                if sampled > LIMIT:
                    failure = 'rss_limit'
            if time.monotonic() - start > 30:
                failure = 'wall_limit'
            if failure:
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(0.005)
        stdout, stderr = process.communicate(timeout=2)
        row = dict(label=label, command=argv, returncode=process.returncode, stdout=stdout,
                   stderr=stderr, wall_seconds=time.monotonic() - start,
                   sampled_peak_rss_bytes=sampled, limit_failure=failure)
        if native:
            match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', stderr, re.M)
            row['measured_peak_rss_bytes'] = int(match[1]) if match else None
        report['commands'].append(row)
        save()
        assert not failure and row['wall_seconds'] <= 30, row
        if native:
            assert row['measured_peak_rss_bytes'] is not None
            assert row['measured_peak_rss_bytes'] <= LIMIT
            assert 'AddressSanitizer' not in stderr and 'runtime error:' not in stderr
        return row

    def contract(label, kind, row, status=0, diagnostic=None, target=True, **detail):
        assert row['returncode'] == status, row
        actual = [line for line in row['stderr'].splitlines() if line and not line[0].isspace()]
        assert actual == ([] if diagnostic is None else ['Minyar stopped: ' + diagnostic]), row
        # Exclude Darwin resource statistics while requiring exact program diagnostics.
        stderr = re.sub(r'^.*\b(?:real|user|sys)\b.*\n', '', row['stderr'], count=1)
        if diagnostic is None:
            assert not stderr.lstrip().startswith('Minyar'), row
        report['contracts'].append(dict(label=label, kind=kind, expectation_passed=True,
                                       behavior_matches_target=target, **detail))
        save()

    try:
        for mode in ['o2', 'sanitize']:
            prepared = evidence / (mode + '-fixture.c')
            prepared.write_text(prepare(mode, source))
            binary = work / mode
            old = next(r['command'] for r in prior['commands']
                       if r['label'] == mode + '-distinct-original-compile')
            command = old.copy()
            command[command.index(str(CONTROLS / (mode + '-distinct-original.c')))] = str(prepared)
            command[command.index('-o') + 1] = str(binary)
            optimization = [arg for arg in command if re.fullmatch(r'-O(?:[0-3sz]|fast)', arg)]
            assert optimization == (['-O2'] if mode == 'o2' else ['-O1'])
            compiled = run(mode + '-compile', command)
            assert compiled['returncode'] == 0 and not compiled['stderr'], compiled
            report.setdefault('effective_optimization', {})[mode] = optimization[-1]
            for length in [0, (1 << 31) - 1, 1 << 31, (1 << 32) - 1, 1 << 32]:
                label = f'{mode}-chunk-{length}'
                row = run(label, [binary, 'chunk-header', length], True)
                values = [json.loads(line) for line in row['stdout'].splitlines()]
                rejected = length >= 1 << 31 and args.source != 'entry'
                stats = values[-1]
                assert stats['malloc_calls'] == 0
                assert stats['write_calls'] == (0 if rejected else 1)
                if not rejected:
                    assert values[0]['header'] == f'{length & 0xffffffff:08x}49444154'
                contract(label, 'chunk-prefix', row, 1 if rejected else 2 if length >= 1 << 31 else 0,
                         'the screenshot is too large.' if rejected else None,
                         target=not (args.source == 'entry' and length >= 1 << 31), stats=stats)
            dimensions = [(0, 8), (8, 0), (-1, 8), (8, -1), (16384, 43686),
                          (16384, 43687), (536870913, 1), (715827884, 1),
                          (2147483647, 2147483647), (1456, 491490)]
            for width, height in dimensions:
                label = f'{mode}-dimensions-{width}-{height}'
                row = run(label, [binary, 'dimensions', width, height], True)
                stats = json.loads(row['stdout'])
                expected = round3.arithmetic(width, height) if width > 0 and height > 0 else None
                rejected = expected and not expected['idat_fits'] and args.source != 'entry'
                count = 0 if expected is None or rejected else 3
                assert stats['malloc_calls'] == count and stats['pending'] == 1
                assert stats['sizes'] == ([expected['pixels'], expected['raw'], expected['capacity']]
                                          if count else [0, 0, 0])
                assert not any(stats[k] for k in ['read_calls', 'open_calls', 'write_calls', 'close_calls'])
                diagnostic = None if expected is None else ('the screenshot is too large.' if rejected
                                                            else 'the computer ran out of memory.')
                contract(label, 'dimension-preflight', row, 0 if expected is None else 1, diagnostic,
                         target=not (args.source == 'entry' and expected and not expected['idat_fits']),
                         expected=expected, stats=stats)
            for width, height in [(1, 1), (427, 51), (428, 51), (429, 51)]:
                label = f'{mode}-png-{width}-{height}'
                path = evidence / (label + '.png')
                row = run(label, [binary, 'small-png', width, height, path], True)
                stats = json.loads(row['stdout'])
                assert stats['live_bytes'] == 0 and stats['pending'] == 0
                contract(label, 'png-decoding', row, expected=decode(path, width, height), stats=stats)
            for width, height in [(0, 8), (8, 0), (0, 0)]:
                label = f'{mode}-retry-{width}-{height}'
                path = evidence / (label + '.png')
                row = run(label, [binary, 'png-retry', width, height, path], True)
                contract(label, 'deferred-retry', row, expected=decode(path, 8, 8),
                         stats=json.loads(row['stdout']))
            sizes = round3.arithmetic(8, 8)
            requests = [sizes['pixels'], sizes['raw'], sizes['capacity']]
            for stage in [1, 2, 3]:
                label = f'{mode}-oom-{stage}'
                path = evidence / (label + '.png')
                row = run(label, [binary, 'png-fault', stage, 0, path], True)
                stats = json.loads(row['stdout'])
                assert stats['malloc_calls'] == 3 and stats['sizes'] == requests
                assert stats['allocated_bytes'] == stats['live_bytes'] == sum(requests) - requests[stage - 1]
                assert stats['pending'] and not path.exists()
                assert not any(stats[k] for k in ['read_calls', 'open_calls', 'write_calls', 'close_calls'])
                contract(label, 'selective-oom', row, 1, 'the computer ran out of memory.', stats=stats)
            for fault in [10, *range(-1, -10, -1), 20]:
                label = f'{mode}-io-{fault}'
                path = evidence / (label + '.png')
                row = run(label, [binary, 'png-fault', 0, fault, path], True)
                stats = json.loads(row['stdout'])
                assert stats['malloc_calls'] == 3 and stats['sizes'] == requests
                assert stats['read_calls'] == stats['open_calls'] == stats['pending'] == 1
                assert stats['live_bytes'] == stats['allocated_bytes'] == sum(requests)
                assert stats['write_calls'] == (0 if fault == 10 else -fault if fault < 0 else 9)
                assert stats['close_calls'] == (1 if fault == 20 else 0)
                assert path.exists() == (fault != 10)
                diagnostic = 'the screenshot file could not be created.' if fault == 10 else 'the screenshot file could not be written.'
                contract(label, 'file-fault', row, 1, diagnostic, stats=stats)
            label = mode + '-distinct-tiny'
            row = run(label, [binary, 'tiny', CONTROLS / 'triangle-120.bin'], True)
            observations = [json.loads(line) for line in row['stdout'].splitlines()]
            assert observations[0]['array'] == 1 and observations[0]['buffer'] == 513
            assert observations[0]['deleted'] and observations[0]['bytes'] == 120
            contract(label, 'distinct-mesh', row, observations=observations)
        if args.loader:
            assert args.source == 'current'
            loader_source = evidence / 'graphics-loader.c'
            loader_source.write_text((ROOT / 'tests/graphics-loader.c').read_text().replace(
                '../runtime/native/opengl-functions.h', str(ROOT / 'runtime/native/opengl-functions.h')))
            common = ['clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                      '-I/opt/homebrew/Cellar/glfw/3.4/include']
            binary = work / 'loader'
            row = run('loader-compile', [*common, loader_source, '-o', binary])
            assert row['returncode'] == 0 and not row['stderr']
            row = run('loader-native', [binary], True)
            assert row['stdout'] == 'OpenGL loader success, missing entry, and retry verified\n'
            contract('loader-native', 'native-loader', row)
            row = run('production-forced-loader-compile', [*common, '-DMINYAR_GRAPHICS_LOAD_GL=1', '-c',
                       ROOT / 'runtime/native/graphics.c', '-o', work / 'graphics.o'])
            assert row['returncode'] == 0 and not row['stderr'], row
        report['status'] = 'completed_with_retained_reds' if args.source == 'entry' else 'passed'
        report['counts'] = dict(observations=len(report['contracts']),
                                matched_expectations=sum(c['expectation_passed'] for c in report['contracts']),
                                target_passes=sum(bool(c['behavior_matches_target']) for c in report['contracts']),
                                retained_reds=sum(not c['behavior_matches_target'] for c in report['contracts']),
                                by_kind=dict(Counter(c['kind'] for c in report['contracts'])))
        assert digest(ROOT / 'runtime/native/graphics.c') == report['production_sha256_at_start']
        for item in prior['objects']:
            assert digest(Path(item['path'])) == item['sha256']
        save()
        print(json.dumps({'status': report['status'], 'counts': report['counts'],
                          'results': str(evidence / 'results.json')}, indent=2))
    except BaseException as error:
        report['status'] = 'failed'
        report['failure'] = {'type': type(error).__name__, 'message': str(error)}
        save()
        raise


if __name__ == '__main__':
    main()
