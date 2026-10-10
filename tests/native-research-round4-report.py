#!/usr/bin/env python3
"""Derive separate cohort counts, source proof and protected-file provenance."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/2026-10-memory'
BASE = RESEARCH / 'evidence/native-application-round4'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sizes(width, height):
    raw = (3 * width + 1) * height
    quotient, remainder = divmod(raw, 65535)
    return dict(row=3 * width + 1, raw=raw, pixels=4 * width * height,
                capacity=raw + 5 * (quotient + 1) + 6,
                encoded=raw + 5 * (quotient + bool(remainder)) + 6)


def main():
    own_patch = BASE / 'entry/own-production.patch'
    original = (BASE / 'entry/graphics.c').read_text()
    current_path = ROOT / 'runtime/native/graphics.c'
    current = current_path.read_text()
    actual_patch = ''.join(difflib.unified_diff(original.splitlines(True), current.splitlines(True),
                                               fromfile='a/runtime/native/graphics.c',
                                               tofile='b/runtime/native/graphics.c'))
    assert actual_patch == own_patch.read_text()
    assert digest(own_patch) == '3b42ed486322cd77f1f502303b19691b4fe63d74fb0948e84b430c43ec126999'
    assert digest(current_path) == '736bc64a8bea8edb134d7752cdb9ad9f0f3e8174cbe0ef7f716e4698e8f33eed'
    (BASE / 'entry/final-total-dirty.patch').write_bytes(subprocess.check_output(
        ['git', 'diff', '--', 'runtime/native/graphics.c'], cwd=ROOT))
    cohorts = []
    for label in ['original2', 'isolated1', 'final1']:
        path = BASE / label / 'results.json'
        report = json.loads(path.read_text())
        contracts = report['contracts']
        counts = dict(observations=len(contracts),
                      matched_expectations=sum(c['expectation_passed'] for c in contracts),
                      target_passes=sum(bool(c['behavior_matches_target']) for c in contracts),
                      retained_reds=sum(not c['behavior_matches_target'] for c in contracts),
                      by_kind=dict(Counter(c['kind'] for c in contracts)))
        assert counts == report['counts']
        assert report['effective_optimization'] == {'o2': '-O2', 'sanitize': '-O1'}
        for mode in ['o2', 'sanitize']:
            command = next(r['command'] for r in report['commands'] if r['label'] == mode + '-compile')
            assert [arg for arg in command if arg.startswith('-O')] == [report['effective_optimization'][mode]]
        for row in report['commands']:
            assert not row['limit_failure'] and row['wall_seconds'] <= 30
            if 'measured_peak_rss_bytes' in row:
                assert row['measured_peak_rss_bytes'] <= 128 * 1024 * 1024
        cohorts.append(dict(label=label, status=report['status'], counts=counts,
                            results_sha256=digest(path), source_sha256=report['source_sha256'],
                            effective_optimization=report['effective_optimization']))
    assert cohorts[0]['counts']['retained_reds'] == 12
    assert cohorts[1]['counts']['target_passes'] == 72
    assert cohorts[2]['counts']['target_passes'] == 75
    edge_path = BASE / 'capacity-edge1/results.json'
    edge = json.loads(edge_path.read_text())
    assert edge['status'] == 'passed' and edge['checks'] == 4
    assert all(r['passed'] for r in edge['commands'])
    failure_path = BASE / 'original1/results.json'
    preparation = json.loads(failure_path.read_text())
    assert preparation['status'] == 'failed' and not preparation['commands'] and not preparation['contracts']

    protected = json.loads((BASE / 'entry/protected-hashes.json').read_text())
    changes = []
    for item in protected:
        path = ROOT / item['path']
        current_hash = digest(path) if path.exists() else None
        if current_hash != item['sha256']:
            changes.append(dict(**item, current_sha256=current_hash,
                                ownership='round4 authorized minimal patch' if item['path'] == 'runtime/native/graphics.c'
                                else 'concurrent parent campaign documentation'))
    assert {item['path'] for item in changes} <= {'runtime/native/graphics.c', 'research/2026-10-memory/README.md'}
    objects = json.loads((BASE / 'final1/results.json').read_text())['objects']
    for item in objects:
        assert digest(Path(item['path'])) == item['sha256']

    endpoint = sizes((1 << 31) - 1, (1 << 31) - 1)
    prior_proof = json.loads((RESEARCH / 'evidence/native-application-round3/arithmetic-proof.json').read_text())
    assert all(endpoint[key] == prior_proof['maximum_sizes'][key] for key in endpoint)
    assert all(value <= (1 << 64) - 1 for value in endpoint.values())
    examples = []
    for example in prior_proof['dimension_threshold_examples']:
        expected = sizes(example['width'], example['height'])
        assert all(example[key] == value for key, value in expected.items())
        examples.append(dict(width=example['width'], height=example['height'], **expected))
    edge_expected = sizes(edge['width'], edge['height'])
    assert edge_expected['encoded'] == (1 << 31) - 2
    assert edge_expected['capacity'] > (1 << 31) - 1
    assert current.count('memcpy(target + 1 + (size_t)x * 3, source + (size_t)x * 4, 3);') == 1
    proof = dict(abi={'int_bits': 32, 'size_t_bits': 64}, endpoint=endpoint,
                 size_max=(1 << 64) - 1, matched_prior_examples=examples,
                 exact_capacity_edge=dict(width=edge['width'], height=edge['height'], **edge_expected),
                 admitted_domain={'raw_strict_upper_bound': 1 << 31,
                                  'pixel_proof': '3P < 4R because R=(3w+1)h and h>0',
                                  'pixel_upper_bound': 4 * ((1 << 31) - 1) // 3,
                                  'ptrdiff_max': (1 << 63) - 1},
                 cast_source_checked=True, huge_pixel_loop_executed=False,
                 large_allocation_or_encoding=False, real_gpu_reachability=False)
    save(BASE / 'arithmetic-proof.json', proof)

    formatter = '/Users/luke/.cache/uv/archive-v0/qir4EsQDYRgTcgFN/clang_format/data/bin/clang-format'
    commands = [['clang', '--version'], [formatter, '--version'],
                [formatter, '--dry-run', '--Werror', 'tests/native-research-round4.c'],
                ['python3', '-m', 'py_compile', 'tests/native-research-round4.py',
                 'tests/native-research-round4-capacity-edge.py', 'tests/native-research-round4-report.py'],
                ['git', 'diff', '--check', '--', 'runtime/native/graphics.c']]
    checks = []
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
        checks.append(dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        assert result.returncode == 0
    compiler = Path(shutil.which('clang')).resolve()
    verification = dict(status='passed', protected_files=len(protected), changed_protected=changes,
                        historical_native_evidence_unchanged=True, frozen_objects=objects,
                        own_patch_matches_reviewed=True, compiler_path=str(compiler), compiler_sha256=digest(compiler),
                        checks=checks, preparation_failure=dict(path=str(failure_path.relative_to(RESEARCH)),
                                                               sha256=digest(failure_path), diagnostic=preparation['failure']),
                        tool_discovery_failure={'command': ['clang-format', '--version'], 'returncode': 127,
                                                'stderr': 'zsh:1: command not found: clang-format\n',
                                                'origin': 'initial tool invocation; pinned executable subsequently passed'},
                        current_tests=[dict(path=str(p.relative_to(ROOT)), sha256=digest(p))
                                       for p in sorted((ROOT / 'tests').glob('native-research-round4*')) if p.is_file()])
    save(BASE / 'verification.json', verification)
    summary = dict(status='authorized_minimal_png_repair_passed_bounded_lane', campaign_complete=False,
                   cohorts=cohorts, capacity_edge={'checks': edge['checks'], 'results_sha256': digest(edge_path)},
                   production=json.loads((BASE / 'entry/applied.json').read_text()),
                   independent_review='runtime-native-round3-review.md', final_observations=75,
                   immutable_preparatory_failures=1, resource_limit_failure=False,
                   generated_code=False, fresh_core_build=False, performance_claim=False,
                   real_gpu_reachability=False, huge_image_encoding=False)
    save(RESEARCH / 'native-application-round4-results.json', summary)
    records = [dict(path=str(p.relative_to(RESEARCH)), sha256=digest(p))
               for p in sorted(BASE.rglob('*')) if p.is_file()]
    for path in [RESEARCH / 'native-application-round4-report.md', RESEARCH / 'native-application-round4-results.json',
                 RESEARCH / 'runtime-native-round3-review.md']:
        records.append(dict(path=str(path.relative_to(RESEARCH)), sha256=digest(path)))
    save(RESEARCH / 'native-application-round4-index.json',
         dict(status=summary['status'], report='native-application-round4-report.md',
              machine_summary='native-application-round4-results.json', records=records))
    print(json.dumps({'status': summary['status'], 'final_observations': 75,
                      'protected_files': len(protected), 'changed_protected': [r['path'] for r in changes]}, indent=2))


if __name__ == '__main__':
    main()
