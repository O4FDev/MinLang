#!/usr/bin/env python3
"""Output-only sensitivity controls; no new production/module execution."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/2026-10-memory/evidence/native-application-round8'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--label', required=True)
    parser.add_argument('--approval-file', required=True, type=Path)
    args = parser.parse_args()
    assert args.approval_file.is_file()
    directory = BASE / args.label
    directory.mkdir(exist_ok=False)
    expected = json.loads((args.source / 'expected-inputs.json').read_text())
    spec = importlib.util.spec_from_file_location('round8_oracle', args.source / 'sources/tests/native-research-round8-oracle.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    inputs = args.source / 'o2-outputs'
    baseline = oracle.validate(inputs, expected)
    shutil.copyfile(args.approval_file, directory / 'authorization.txt')
    shutil.copyfile(args.source / 'sources/tests/native-research-round8-oracle.py', directory / 'oracle.py')
    shutil.copyfile(Path(__file__), directory / 'calibration.py')
    mutations = [
        ('atlas-alpha', 'atlas.bin', ((16 + 6) * 256 + 10 * 16 + 7) * 4 + 3, bytes([0]), oracle.validate_texture),
        ('icon-uv', 'icons.bin', 0, struct.pack('<d', .5), oracle.validate_texture),
        ('periodic-value', 'periodic.bin', 0, struct.pack('<d', .99), oracle.validate_periodic),
        ('strict-timer', 'states.bin', (5 * 7 + 6) * 8, struct.pack('<d', 0), oracle.validate_atmosphere),
        ('cloud-height', 'upload-00-2.bin', 4, struct.pack('<f', 113), oracle.validate_atmosphere),
        ('halo-rim-color', 'upload-04-1.bin', 40 + 5 * 4, struct.pack('<f', .99), oracle.validate_atmosphere),
        ('body-inset', 'upload-04-1.bin', 288 * 40 + 3 * 4, struct.pack('<f', 0), oracle.validate_atmosphere),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix='native-round8-output-calibration-') as temporary:
        target = Path(temporary) / 'outputs'
        shutil.copytree(inputs, target)
        for label, filename, offset, replacement, validate in mutations:
            original = (inputs / filename).read_bytes()
            assert original[offset:offset + len(replacement)] != replacement, label
            mutant = original[:offset] + replacement + original[offset + len(replacement):]
            (target / filename).write_bytes(mutant)
            (directory / (label + '.bin')).write_bytes(mutant)
            error = None
            try:
                validate(target, expected)
            except AssertionError as caught:
                error = repr(caught)
            assert error is not None, ('survived', label)
            results.append({'label': label, 'kind': 'saved-output mutation only', 'filename': filename, 'offset': offset,
                            'old_hex': original[offset:offset + len(replacement)].hex(), 'new_hex': replacement.hex(),
                            'original_sha256': hashlib.sha256(original).hexdigest(), 'mutant_sha256': hashlib.sha256(mutant).hexdigest(),
                            'detected': True, 'diagnostic': error})
            (target / filename).write_bytes(original)
    report = {'status': 'passed_sensitivity_controls', 'baseline_source': str(args.source), 'baseline_groups': sum(r['groups'] for r in baseline.values()),
              'controls': results, 'control_count': len(results), 'native_executions': 0,
              'scope': 'Selected saved-output comparator sensitivity; neither production source mutants nor additional module/GPU executions.'}
    (directory / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'controls': len(results)}))


if __name__ == '__main__':
    main()
