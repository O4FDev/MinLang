#!/usr/bin/env python3
"""Check that saved independent terrain oracles reject small output corruptions.

These are output controls, separate from the source mutation counts. All generated
application bytes come from the exact passing matrix. No compiler or native jobs.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    matrix_path = args.matrix.resolve()
    matrix = json.loads(matrix_path.read_text())
    assert matrix['status'] == 'passed'
    source = matrix_path.parent / 'sources/tests/native-research-round2.py'
    spec = importlib.util.spec_from_file_location('frozen_round2_oracle', source)
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    evidence = ROOT / 'research/2026-10-memory/evidence/native-application-round2' / args.label
    evidence.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix=args.label + '-', dir=ROOT / 'build/native-research-round2'))
    output = Path(matrix['work']) / 'system-o2-terrain.bin'
    with output.open('rb') as stream:
        packets = []
        for event in range(21):
            parts = []
            for part in range(4):
                length, = struct.unpack('<I', stream.read(4))
                data = stream.read(length)
                assert len(data) == length
                parts.append(data)
            packets.append(parts)
    events = oracle.make_events()
    report = {'status': 'running', 'matrix_sha256': sha(matrix_path.read_bytes()),
              'oracle_sha256': sha(source.read_bytes()), 'source_output_sha256': sha(output.read_bytes()),
              'script_sha256': sha(Path(__file__).read_bytes()), 'controls': [], 'work': str(work),
              'scope': 'Independent output fault detection, not production defects or additional matrix executions.'}
    (evidence / Path(__file__).name).write_bytes(Path(__file__).read_bytes())

    def save():
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')

    mutations = [
        ('block-content', 0, 0, 0, bytes([oracle.STONE])),
        ('column-top', 0, 1, 12, struct.pack('<i', 0)),
        ('dirty-membership', 0, 1, 16396, bytes([1])),
        ('position', 6, 2, 0, struct.pack('<f', 3.125)),
        ('atlas-uv', 6, 2, 12, struct.pack('<f', 0.0)),
        ('ambient-rgb', 6, 2, 24, struct.pack('<f', 0.0)),
        ('sky-light', 6, 2, 32, struct.pack('<f', 0.0)),
        ('torch-glow', 6, 2, 36, struct.pack('<f', 1.0)),
        ('duplicate-torch', 20, 1, 17420, None),
        ('triangle-winding', 6, 2, 0, None)]
    for label, event, part, offset, value in mutations:
        selected = [list(row) for row in packets[:event + 1]]
        data = bytearray(selected[event][part])
        if label == 'duplicate-torch':
            count, = struct.unpack_from('<I', data, offset)
            assert count == 1
            struct.pack_into('<I', data, offset, 2)
            data.extend(data[-4:])
            before, after = selected[event][part][offset:], bytes(data[offset:])
        elif label == 'triangle-winding':
            data[:40], data[40:80] = data[40:80], data[:40]
            before, after = selected[event][part][:80], bytes(data[:80])
        else:
            before = bytes(data[offset:offset + len(value)])
            assert before != value
            data[offset:offset + len(value)] = value
            after = value
        selected[event][part] = bytes(data)
        payload = b''.join(struct.pack('<I', len(data)) + data for row in selected for data in row)
        trace = work / (label + '.bin')
        trace.write_bytes(payload)
        row = {'label': label, 'event': event, 'part': part, 'offset': offset,
               'original_hex': before.hex(), 'replacement_hex': after.hex(),
               'trace_sha256': sha(payload), 'trace_events': event + 1}
        report['controls'].append(row)
        try:
            oracle.terrain_check(trace, events[:event + 1])
            row['detected'] = False
        except (AssertionError, ValueError, struct.error) as error:
            row.update(detected=True, error=repr(error))
        save()
        assert row['detected'], ('oracle corruption survived', label)
    report.update(status='passed', detected=sum(row['detected'] for row in report['controls']))
    save()
    print(json.dumps({'status': report['status'], 'detected': report['detected'], 'results': str(evidence / 'results.json')}, indent=2))


if __name__ == '__main__':
    main()
