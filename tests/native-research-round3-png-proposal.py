#!/usr/bin/env python3
"""Validate a small PNG proposal in isolated copies, preserving production reds."""
import argparse
import difflib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('round3', ROOT / 'tests/native-research-round3.py')
round3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round3)
LIMIT = 128 * 1024 * 1024
DIAGNOSTIC = 'Minyar stopped: the screenshot is too large.\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls', type=Path, required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    controls = args.controls.resolve()
    prior = json.loads((controls / 'results.json').read_text())
    assert prior['status'] == 'completed_with_retained_png_reds'
    evidence = ROOT / 'research/2026-10-memory/evidence/native-application-round3' / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    work = ROOT / 'build/native-research-round3' / args.label
    work.mkdir(parents=True, exist_ok=False)
    source = (controls / 'graphics-original.c').read_text()
    chunk_anchor = 'static void png_chunk(FILE *file, const char *type, const unsigned char *data, size_t length) {\n'
    size_anchor = '    size_t row = (size_t)width * 3 + 1, raw_length = row * (size_t)height;\n'
    pixel_anchor = 'memcpy(target + 1 + x * 3, source + x * 4, 3);'
    for anchor in [chunk_anchor, size_anchor, pixel_anchor]:
        assert source.count(anchor) == 1
    candidate = source.replace(chunk_anchor, chunk_anchor +
                               '    if (length > UINT32_C(0x7fffffff)) stop_graphics("the screenshot is too large.");\n')
    candidate = candidate.replace(size_anchor, size_anchor +
                                  '    size_t encoded_blocks = (raw_length - 1) / 65535 + 1;\n'
                                  '    if (raw_length + encoded_blocks * 5 + 6 > UINT32_C(0x7fffffff))\n'
                                  '        stop_graphics("the screenshot is too large.");\n')
    candidate = candidate.replace(pixel_anchor, 'memcpy(target + 1 + (size_t)x * 3, source + (size_t)x * 4, 3);')
    candidate_path = evidence / 'graphics-proposed.c'
    candidate_path.write_text(candidate)
    normalized = candidate.replace('(slot_checks++, meshes[slot].used)', 'meshes[slot].used')
    current = (ROOT / 'runtime/native/graphics.c').read_text()
    assert source.replace('(slot_checks++, meshes[slot].used)', 'meshes[slot].used') == current
    patch = ''.join(difflib.unified_diff(current.splitlines(True), normalized.splitlines(True),
                                        fromfile='a/runtime/native/graphics.c', tofile='b/runtime/native/graphics.c'))
    (evidence / 'minimal-proposed.patch').write_text(patch)
    (evidence / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    report = dict(disposable_work=str(work), status='running', production_edits=False, candidate_sha256=round3.digest(candidate_path),
                  original_control_results_sha256=round3.digest(controls / 'results.json'),
                  patch_sha256=round3.digest(evidence / 'minimal-proposed.patch'), commands=[], contracts=[],
                  limitations='64-bit size_t and 32-bit int; no large allocation/readback/encoding, GPU, generated code or production changes')
    environment = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1',
                   'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, command, native=False):
        command = [str(part) for part in command]
        actual = ['/usr/bin/time', '-l', *command] if native else command
        start = time.monotonic()
        result = subprocess.run(actual, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
        row = dict(label=label, command=actual, returncode=result.returncode, stdout=result.stdout,
                   stderr=result.stderr, wall_seconds=time.monotonic() - start)
        if native:
            match = re.search(r'^\s*(\d+)\s+maximum resident set size\s*$', result.stderr, re.M)
            assert match, row
            row['peak_rss_bytes'] = int(match[1])
            assert row['peak_rss_bytes'] <= LIMIT
            # Darwin time output follows the program diagnostic. Keep raw stderr too.
            row['program_stderr'] = result.stderr.split('        ')[0] if result.stderr.startswith('Minyar stopped:') else ''
            assert 'AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr
        report['commands'].append(row)
        save()
        return row

    for mode in ['o2', 'sanitize']:
        original_compile = next(row['command'] for row in prior['commands']
                                if row['label'] == mode + '-distinct-original-compile')
        original_binary = Path(original_compile[original_compile.index('-o') + 1])
        relocations = prior.get('artifact_relocations', {})
        original_binary = Path(relocations.get(str(original_binary), str(original_binary)))
        prepared = evidence / (mode + '-candidate.c')
        original_prepared = controls / (mode + '-distinct-original.c')
        fixture = original_prepared.read_text().replace(str(controls / 'graphics-original.c'), str(candidate_path))
        assert str(candidate_path) in fixture
        prepared.write_text(fixture)
        binary = work / (mode + '-candidate')
        old = next(row['command'] for row in prior['commands'] if row['label'] == mode + '-distinct-original-compile')
        command = old.copy()
        command[command.index(str(original_prepared))] = str(prepared)
        command[command.index('-o') + 1] = str(binary)
        row = run(mode + '-candidate-compile', command)
        assert row['returncode'] == 0 and not row['stderr'], row
        for length in [0, (1 << 31) - 1, 1 << 31, (1 << 32) - 1, 1 << 32]:
            label = f'{mode}-candidate-chunk-{length}'
            row = run(label, [binary, 'chunk-header', str(length)], True)
            observations = [json.loads(line) for line in row['stdout'].splitlines()]
            if length >= 1 << 31:
                assert row['returncode'] == 1 and row['stderr'].startswith(DIAGNOSTIC), row
                stats = observations[0]
                assert stats['write_calls'] == stats['malloc_calls'] == 0
            else:
                assert row['returncode'] == 0 and not row['program_stderr']
                stats = observations[1]
                assert stats['write_calls'] == 1
            report['contracts'].append(dict(label=label, kind='candidate-chunk', passed=True, stats=stats))
            save()
        for width, height in [(0, 8), (8, 0), (16384, 43686), (16384, 43687),
                              (536870913, 1), (715827884, 1), (2147483647, 2147483647)]:
            label = f'{mode}-candidate-dimensions-{width}-{height}'
            row = run(label, [binary, 'dimensions', str(width), str(height)], True)
            stats = json.loads(row['stdout'])
            expected = round3.arithmetic(width, height) if width > 0 and height > 0 else None
            if expected is None:
                assert row['returncode'] == 0 and stats['malloc_calls'] == 0
            elif expected['idat_fits']:
                assert row['returncode'] == 1 and row['stderr'].startswith('Minyar stopped: the computer ran out of memory.\n')
                assert stats['malloc_calls'] == 3 and stats['sizes'] == [expected['pixels'], expected['raw'], expected['capacity']]
            else:
                assert row['returncode'] == 1 and row['stderr'].startswith(DIAGNOSTIC), row
                assert stats['malloc_calls'] == 0 and stats['sizes'] == [0, 0, 0]
            assert stats['pending'] and not any(stats[k] for k in ['read_calls', 'open_calls', 'write_calls', 'close_calls'])
            report['contracts'].append(dict(label=label, kind='candidate-dimensions', expected=expected, passed=True, stats=stats))
            save()
        for variant, selected in [('original', original_binary), ('candidate', binary)]:
            for width, height in [(427, 51), (428, 51), (429, 51)]:
                label = f'{mode}-{variant}-block-boundary-{width}-{height}'
                path = evidence / (label + '.png')
                row = run(label, [selected, 'small-png', str(width), str(height), path], True)
                assert row['returncode'] == 0 and not row['program_stderr'], row
                report['contracts'].append(dict(label=label, kind='real-block-boundary', variant=variant,
                                               passed=True, expected=round3.png_check(path, width, height)))
                save()
        row = run(mode + '-candidate-tiny', [binary, 'tiny', controls / 'triangle-120.bin'], True)
        assert row['returncode'] == 0 and not row['program_stderr']
        report['contracts'].append(dict(label=mode + '-candidate-tiny', kind='candidate-tiny', passed=True))
        save()
    report['status'] = 'isolated_proposal_passed_not_applied'
    report['counts'] = dict(contracts=len(report['contracts']), passed=sum(c['passed'] for c in report['contracts']),
                           candidate_chunk=sum(c['kind'] == 'candidate-chunk' for c in report['contracts']),
                           candidate_dimensions=sum(c['kind'] == 'candidate-dimensions' for c in report['contracts']),
                           real_block_boundary=sum(c['kind'] == 'real-block-boundary' for c in report['contracts']),
                           candidate_tiny=sum(c['kind'] == 'candidate-tiny' for c in report['contracts']))
    save()
    print(json.dumps(dict(status=report['status'], counts=report['counts'], results=str(evidence / 'results.json')), indent=2))


if __name__ == '__main__':
    main()
