#!/usr/bin/env python3
"""Derive round3 counts/proofs and verify immutable prior evidence and PNG streams."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory'
EVIDENCE = BASE / 'evidence/native-application-round3'
spec = importlib.util.spec_from_file_location('round3', ROOT / 'tests/native-research-round3.py')
round3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round3)


def main():
    controls = json.loads((EVIDENCE / 'control4/results.json').read_text())
    proposal = json.loads((EVIDENCE / 'png-proposal1/results.json').read_text())
    assert controls['status'] == 'completed_with_retained_png_reds'
    assert proposal['status'] == 'isolated_proposal_passed_not_applied'
    rows = controls['controls']
    assert controls['counts'] == dict(namespace_controls=sum(c['kind'] == 'namespace' for c in rows),
                                    distinct_mutants_detected=sum(c.get('detected', False) for c in rows),
                                    coincident_mutant_survivals=sum(c.get('survived', False) for c in rows),
                                    integration_traces=sum(c['kind'] == 'integration' for c in rows),
                                    dimension_observations=sum(c['kind'] == 'dimensions' for c in rows),
                                    header_observations=sum(c['kind'] == 'chunk-header' for c in rows),
                                    retained_png_reds=sum(c.get('original_red', False) for c in rows),
                                    real_small_pngs=sum(c['kind'] == 'small-png' for c in rows))
    assert proposal['counts']['contracts'] == len(proposal['contracts'])
    assert proposal['counts']['passed'] == sum(c['passed'] for c in proposal['contracts'])
    initial = json.loads((EVIDENCE / 'provenance/initial-hashes.json').read_text())
    unchanged = [dict(**row, unchanged=round3.digest(ROOT / row['path']) == row['sha256'])
                 for row in initial['files']]
    assert all(row['unchanged'] for row in unchanged)
    for obj in controls['objects']:
        assert round3.digest(Path(obj['path'])) == obj['sha256']
    # Independent complete zlib-stream check added only to these new PNG artifacts.
    pngs = []
    for path in sorted(EVIDENCE.rglob('*.png')):
        data = path.read_bytes()
        offset, compressed = 8, b''
        while offset < len(data):
            length = int.from_bytes(data[offset:offset + 4], 'big')
            if data[offset + 4:offset + 8] == b'IDAT':
                compressed += data[offset + 8:offset + 8 + length]
            offset += length + 12
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed) + decoder.flush()
        assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
        pngs.append(dict(path=str(path.relative_to(BASE)), sha256=round3.digest(path), raw_length=len(raw),
                         complete_zlib_stream=True))
    int_max = (1 << 31) - 1
    size_max = (1 << 64) - 1
    maximum = round3.arithmetic(int_max, int_max)
    assert all(maximum[k] <= size_max for k in ['row', 'raw', 'pixels', 'capacity', 'encoded'])
    # All positive-domain products are monotone, so these endpoints prove representability.
    proof = dict(assumptions=dict(int_bits=32, size_t_bits=64, positive_dimensions=True,
                                 targets_32_bit_supported=False, malloc_success_not_assumed=True),
                 maximum_dimensions=[int_max, int_max], maximum_sizes=maximum, size_max=size_max,
                 ptrdiff_max=(1 << 63) - 1, maximum_pixels_exceed_ptrdiff=True,
                 png_chunk_max=int_max, rgba_first_overflow_x=int_max // 4 + 1,
                 rgba_first_overflow_width=int_max // 4 + 2,
                 rgb_first_overflow_x=int_max // 3 + 1,
                 rgb_first_overflow_width=int_max // 3 + 2,
                 encoded_formula='(3*w+1)*h + 5*ceil(((3*w+1)*h)/65535) + 6',
                 allocated_capacity_formula='raw + 5*(floor(raw/65535)+1) + 6',
                 exact_multiple_capacity_slack_bytes=5,
                 native_input_domain='Framebuffer int values from GLFW; screenshot public API takes a path only',
                 large_encode_executed=False, signed_overflow_executed=False,
                 dimension_threshold_examples=[dict(width=w, height=h, **round3.arithmetic(w, h))
                                               for w, h in [(16384, 16384), (16384, 43686), (16384, 43687),
                                                            (32768, 21843), (32768, 21844),
                                                            (536870913, 1), (428, 51)]])
    (EVIDENCE / 'arithmetic-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    verification = dict(prior_read_only_files=unchanged, objects_unchanged=controls['objects'],
                        new_png_streams=pngs, checks=[], owned_files=[])
    formatter = Path('/Users/luke/.cache/uv/archive-v0/qir4EsQDYRgTcgFN/clang_format/data/bin/clang-format')
    for label, command in [('formatter-version', [formatter, '--version']),
                           ('owned-c-format', [formatter, '--dry-run', '--Werror', ROOT / 'tests/native-research-round3.c']),
                           ('owned-python-syntax', ['python3', '-m', 'py_compile', *sorted((ROOT / 'tests').glob('native-research-round3*.py'))]),
                           ('git-whitespace', ['git', 'diff', '--check']), ('clang-version', ['clang', '--version'])]:
        result = subprocess.run([str(p) for p in command], capture_output=True, text=True, timeout=30)
        verification['checks'].append(dict(label=label, command=[str(p) for p in command], returncode=result.returncode,
                                           stdout=result.stdout, stderr=result.stderr))
        assert result.returncode == 0, result.stderr
    verification['clang_path'] = shutil.which('clang')
    verification['clang_sha256'] = round3.digest(Path(verification['clang_path']))
    for path in sorted((ROOT / 'tests').glob('native-research-round3*')):
        verification['owned_files'].append(dict(path=str(path.relative_to(ROOT)), sha256=round3.digest(path)))
    (EVIDENCE / 'provenance/final-status.txt').write_bytes(subprocess.check_output(['git', 'status', '--short']))
    (EVIDENCE / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    traces = [c['stats'] for c in rows if c['kind'] == 'integration']
    self_rss = []
    for command in controls['commands']:
        for line in command['stdout'].splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict) and 'peak_rss_bytes' in value:
                    self_rss.append(value['peak_rss_bytes'])
            except ValueError:
                pass
    summary = dict(status='bounded_round_complete_with_unapplied_png_proposal', campaign_completion=False,
                   original=controls['counts'], isolated_proposal=proposal['counts'],
                   integration_mixed_iterations=sum(r['mixed_iterations'] for r in traces),
                   integration_mesh_api_calls=sum(sum(r[k] for k in ['creates', 'deletes', 'updates', 'draw_calls']) for r in traces),
                   resource=dict(original_native_self_peak_rss_bytes=max(self_rss),
                                 original_native_sampled_peak_rss_bytes=max(r['sampled_peak_rss_bytes'] for r in controls['commands']),
                                 proposal_native_time_peak_rss_bytes=max(r.get('peak_rss_bytes', 0) for r in proposal['commands']),
                                 original_all_command_wall_seconds=sum(r['wall_seconds'] for r in controls['commands']),
                                 original_child_plus_sampler_cpu_seconds=sum(r['child_cpu_seconds'] for r in controls['commands']),
                                 proposal_all_command_wall_seconds=sum(r['wall_seconds'] for r in proposal['commands']),
                                 original_max_command_wall_seconds=max(r['wall_seconds'] for r in controls['commands']),
                                 proposal_max_command_wall_seconds=max(r['wall_seconds'] for r in proposal['commands']),
                                 wall_limit_seconds=30, rss_limit_bytes=128 * 1024 * 1024, native_children=1,
                                 observations_only_not_timing_comparison=True,
                                 original_abort_mutant_rss='Sampled only; assertions bypass self getrusage stats',
                                 default_asan_quarantine=True, leak_detection=False),
                   immutable_prior_files=len(unchanged), complete_new_png_streams=len(pngs),
                   owned_test_files=verification['owned_files'], production_edits=False, generated_code=False,
                   proposal='evidence/native-application-round3/png-proposal1/minimal-proposed.patch')
    (BASE / 'native-application-round3-results.json').write_text(json.dumps(summary, indent=2) + '\n')
    index = dict(status=summary['status'], report='native-application-round3-report.md', records=[])
    for path in sorted(EVIDENCE.rglob('*')):
        if path.is_file():
            index['records'].append(dict(path=str(path.relative_to(BASE)), sha256=round3.digest(path)))
    index['records'].append(dict(path='native-application-round3-results.json', sha256=round3.digest(BASE / 'native-application-round3-results.json')))
    report_path = BASE / 'native-application-round3-report.md'
    if report_path.exists():
        index['records'].append(dict(path=report_path.name, sha256=round3.digest(report_path)))
    (BASE / 'native-application-round3-index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
