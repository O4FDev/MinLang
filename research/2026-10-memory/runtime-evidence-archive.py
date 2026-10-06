#!/usr/bin/env python3
"""Curate durable runtime evidence without binaries, LLVM or redundant sources."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / 'research/2026-10-memory/evidence/runtime'
SELECTION = [
    ('baseline', 'memory-research-runtime-baseline/minyar-memory-profiles-1msa1ju5', 'Nine unchanged native cursor/fairness/service checks.'),
    ('allocation-red', 'memory-research-list-reserve-red-evidence/run-vb29a14s', 'Expected allocation-bound failure before List reservation.'),
    ('original-counts', 'memory-research-list-reserve-before/run-ruw3uli7', 'Original allocator counts with improved bound disabled.'),
    ('rejected-growth-design', 'memory-research-list-reserve-bench/run-orc9795b', 'Rejected planner on ordinary growth: negative timing controls.'),
    ('unconditional-list-timing', 'memory-research-list-reserve-bench/run-131w4uv4', 'Historical unconditional reservation timing; superseded by debt guard.'),
    ('final-list-timing', 'memory-research-list-reserve-bench/run-9t0lgm8s', 'Final guarded paired timing; fixed growth residual slowdown retained.'),
    ('historical-list-matrix', 'memory-research-list-reserve/run-lml85q04', 'Unconditional matrix; C sanitizer only in generated links.'),
    ('historical-guarded-matrix', 'memory-research-list-reserve/run-9ekj44fd', 'Guarded matrix before generated AddressSanitizer attribute correction.'),
    ('list-sanitizer-matrix', 'memory-research-list-reserve/run-tja7d6bv', 'Final guarded List matrix with generated AddressSanitizer attributes.'),
    ('list-object-debt', 'memory-research-list-debt-pressure/run-mmxhx7t9', 'Original/unconditional/guarded finite-pool differential,24 executions.'),
    ('invalid-owner-fixture', 'memory-research-list-owner-debt/run-_cz_08lm', 'Invalid first calibration: correct guard also failed; not a runtime defect.'),
    ('list-owner-debt', 'memory-research-list-owner-debt/run-vkrj6rvc', 'Frame/chunk admission controls kill object-only guard mutant.'),
    ('unicode-native-red', 'memory-research-text-join-index-red/run-8o4rlalr', 'Original Unicode consuming join produces wrong scalar.'),
    ('unicode-generated-red-green', 'memory-research-text-join-index-generated-red-green/run-o44vcd_o', 'Original generated wrong output versus isolated repair.'),
    ('unicode-repair-matrix', 'memory-research-text-join-index/run-9mfrbcfx', 'Unicode repair matrix before separate ASCII propagation.'),
    ('text-c-only-correction', 'memory-research-text-join-index/run-_gj9t242', '64 C-only checks; initial107/native-generated progress claim corrected.'),
    ('final-text-matrix', 'memory-research-text-join-index/run-zxq8d1m_', 'Exact final runtime107 checks,21 C configurations,21 generated runs,21 traps.'),
    ('ascii-first-counts', 'memory-research-ascii-join/run-ie72rhd_', 'Baseline metadata red before external candidate mutation.'),
    ('ascii-expanded-controls', 'memory-research-ascii-join/run-41o8qr07', 'Additional empty/view/cache/asymmetric-right controls.'),
    ('ascii-fixed-sanitizer', 'memory-research-ascii-join/run-is7ea_xn', 'Fixed K1 expanded counters and generated AddressSanitizer.'),
    ('ascii-final-lazy-sanitizer', 'memory-research-ascii-join/run-r4eocr5x', 'Production lazy K32 expanded counters and generated AddressSanitizer.'),
    ('ascii-final-eager', 'memory-research-ascii-join/run-6k38fw4n', 'Production eager native counter controls.'),
    ('ascii-paired-timing', 'memory-research-ascii-join-bench/run-603xbkqt', 'Five generated modes,12 randomized blocks, no discarded CPU/wall pairs.'),
    ('deferred-isolated', 'memory-research-deferred-reuse/run-7_ql4lfc', 'Test-only extra service positive case plus alias/deep/retention negatives.'),
    ('deferred-generated', 'memory-research-deferred-generated/run-7r05rn2u', 'Realistic65-member generated negative: one extraK does not yield reuse.'),
    ('deferred-starvation-a', 'memory-research-deferred-reuse/run-sgfu6jfx', 'Incomplete background-QoS wall timeout, no correctness conclusion.'),
    ('deferred-starvation-b', 'memory-research-deferred-reuse/run-x7agg8z1', 'Interrupted/host-starved historical attempt, not a correctness result.'),
    ('accounting-probes', 'memory-research-accounting-probes/run-bv0yq7a7', 'Private scheduler edges and large immortal-prefix scan-debt measurement.'),
    ('rejected-bytes-policy', 'memory-research-bytes-debt-pressure/run-tm7tl7ch', 'Specific size-class-slack policy rejected by later-debt allocation OOM.'),
    ('credit-causal-counts', 'memory-research-credit-relocation/run-g9x69qkm', 'Four test-only causal builds: equal-credit reuse and retained-capacity tradeoff.'),
    ('credit-admission-classifier', 'memory-research-credit-relocation/run-ks8nvgie', 'Counterexample already reproduced; initial runner expected the wrong OOM diagnostic.'),
    ('credit-admission-native', 'memory-research-credit-relocation/run-3wn68r25', 'Fixed/lazy K1/K32 admission: compact baseline succeeds, retained-capacity prototype OOMs.'),
    ('credit-admission-sanitizer', 'memory-research-credit-relocation/run-_5xsy9ar', 'Same four admission controls with ASan+UBSan and unchanged allowances.'),
    ('api-count-adapter-failure', 'memory-research-credit-relocation/run-9x3rjskn', 'Missing stddef declaration in new fixture; no runtime execution.'),
    ('api-count-native', 'memory-research-credit-relocation/run-ceyk3adm', 'Baseline slice/Boolean counts192 C observations plus10 generated view cases.'),
    ('api-count-sanitizer', 'memory-research-credit-relocation/run-f28v6y8n', 'Same count controls under C ASan+UBSan and attributed generated ASan.'),
    ('guard-order-native', 'memory-research-credit-relocation/run-9wo93__y', 'Eleven native/internal invalid-size cases under debt in four configurations.'),
    ('guard-order-sanitizer', 'memory-research-credit-relocation/run-mlya8ahl', 'Same managed failure-order controls, plus injected-service oracle calibration.'),
    ('peer-projections', 'memory-research-peer-projections/run-ki_43p1a', 'Historical18 executions: native O0/O2, sanitizer effectively O1; correction retained.'),
    ('peer-projections-expanded', 'memory-research-peer-projections/run-crettoqb', 'Historical24 executions: native O0/O2, sanitizer effectively O1; correction retained.'),
    ('peer-projections-final', 'memory-research-peer-projections/run-7m86apqr', 'Six original projections including NaN and source underflow;36 executions with exact actual O0/O2 link argv.'),
    ('peer-projections-round6', 'memory-research-peer-projections/run-l5_218bk', 'Eight original projections including middle-literal effects and2^53 tie arithmetic;48 exact O0/O2 executions.'),
    ('queue-empty-fragmentation', 'memory-research-list-fragmentation/run-q8c_86fq', 'Final formatted bounded differential,16384 histories,15653 admitted appends; no observed placement/admission difference.'),
    ('hud-formatting-pilot', 'memory-research-hud-formatting/run-ar18ynek', '16-frame real generated HUD formatting pilot,public conversions separate from allocating calls and intentional cache.'),
    ('hud-formatting-matrix', 'memory-research-hud-formatting/run-xm7s2ljs', '2048-frame cold/warm application projection,18 generated executions; no timing or cache-policy adoption.'),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {'path': str(path.relative_to(DESTINATION)), 'sha256': sha(data), 'bytes': len(data)}


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    index = {'scope': 'Curated runtime evidence. Original JSON bytes preserved. No binaries or LLVM. '
                      'Statuses include expected red/negative outcomes and incomplete attempts; do not aggregate them as passes.',
             'results': [], 'final_runtime': [], 'source_snapshots': [], 'hash_mismatches': []}
    final = {}
    for source in sorted((ROOT / 'runtime').glob('minyar_*')):
        if source.is_file():
            final[source.name] = source.read_bytes()
            index['final_runtime'].append(write(DESTINATION / 'final-runtime' / source.name, source.read_bytes()))
    seen_sources = {}
    for label, directory, description in SELECTION:
        original = ROOT / 'build' / directory / 'results.json'
        data = original.read_bytes()
        report = json.loads(data)
        entry = {**write(DESTINATION / 'results' / (label + '.json'), data),
                 'label': label, 'original_path': str(original.relative_to(ROOT)),
                 'recorded_status': report.get('status'), 'description': description,
                 'recorded_check_count': len(report.get('checks', [])), 'sources': []}
        index['results'].append(entry)
        source_records = [*report.get('sources', []), *report.get('staged_sources', [])]
        for record in source_records:
            snapshot = record.get('snapshot', record.get('snapshot_path'))
            if not snapshot:
                continue
            source = original.parent / snapshot
            if not source.is_file() or source.suffix not in ('.c', '.h', '.py', '.min', '.stdout'):
                continue
            assert source.resolve().is_relative_to(original.parent.resolve())
            content = source.read_bytes()
            actual_sha = sha(content)
            key = (actual_sha, source.name)
            if key not in seen_sources:
                if source.name in final:
                    reference = {'kind': 'runtime', 'file': source.name, 'target_sha256': actual_sha,
                                 'base_sha256': sha(final[source.name])}
                    if content != final[source.name]:
                        difference = ''.join(difflib.unified_diff(
                            final[source.name].decode().splitlines(True), content.decode().splitlines(True),
                            fromfile='a/' + source.name, tofile='b/' + source.name)).encode()
                        reference['diff'] = write(DESTINATION / 'diffs' / (actual_sha + '-' + source.name + '.patch'), difference)
                else:
                    reference = {'kind': 'fixture_or_helper', **write(
                        DESTINATION / 'sources' / (actual_sha + '-' + source.name), content)}
                seen_sources[key] = reference
                index['source_snapshots'].append(reference)
            recorded_sha = record.get('sha256')
            mapping = {'original_snapshot': snapshot, 'archive_source': seen_sources[key],
                       'recorded_sha256': recorded_sha, 'observed_sha256': actual_sha,
                       'recorded_hash_matches': recorded_sha == actual_sha}
            entry['sources'].append(mapping)
            if recorded_sha and recorded_sha != actual_sha:
                mutation = report.get('candidate', report.get('mutant', {}))
                before_sha = mutation.get('before_sha256', mutation.get('original_sha256'))
                after_sha = mutation.get('after_sha256', mutation.get('mutant_sha256'))
                assert (recorded_sha, actual_sha) == (before_sha, after_sha), (label, snapshot)
                index['hash_mismatches'].append({'label': label, 'snapshot': snapshot,
                                                'recorded_sha256': recorded_sha, 'observed_sha256': actual_sha,
                                                'resolution': 'Recorded snapshot hash equals the explicit pre-mutation hash; '
                                                              'archived bytes equal the explicit post-mutation hash. '
                                                              'Both fields are preserved in the unmodified result JSON.'})
    index['archive_generator_sha256'] = sha(Path(__file__).read_bytes())
    target = DESTINATION / 'index.json'
    target.write_text(json.dumps(index, indent=2) + '\n')
    # Independent reread validates preserved results, sources and diffs.
    files = [*index['results'], *index['final_runtime']]
    files += [source['diff'] for source in index['source_snapshots'] if 'diff' in source]
    files += [source for source in index['source_snapshots'] if source['kind'] == 'fixture_or_helper']
    for entry in files:
        assert sha((DESTINATION / entry['path']).read_bytes()) == entry['sha256']
    for source in index['source_snapshots']:
        if source['kind'] == 'runtime' and 'diff' in source:
            with tempfile.TemporaryDirectory(prefix='minyar-runtime-diff-') as temporary:
                reconstructed = Path(temporary) / source['file']
                shutil.copyfile(DESTINATION / 'final-runtime' / source['file'], reconstructed)
                applied = subprocess.run(['patch', '-s', '-p1', '-d', temporary],
                                         input=(DESTINATION / source['diff']['path']).read_text(),
                                         text=True, capture_output=True, timeout=10)
                assert applied.returncode == 0, applied.stderr
                assert sha(reconstructed.read_bytes()) == source['target_sha256']
    index['verification'] = ('Every copied result/source/diff hash reread; every differing runtime source reconstructed '
                             'in a disposable directory and matched its observed source SHA256.')
    target.write_text(json.dumps(index, indent=2) + '\n')
    print(f'Archived {len(index["results"])} results, {len(index["source_snapshots"])} distinct source versions; '
          f'{len(index["hash_mismatches"])} historical hash mismatches retained for audit.')
    print(target)


if __name__ == '__main__':
    main()
