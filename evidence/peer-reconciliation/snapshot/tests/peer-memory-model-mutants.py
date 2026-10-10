#!/usr/bin/env python3
"""Selected semantic model mutants. Never compiles or edits production sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


MUTANTS = [
    ('poll_cap_off_by_one',
     'budget = min(budget, self.ceiling)',
     'budget = min(budget, self.ceiling + 1)',
     'Public request above K can perform K+1 units; analog: poll clamp.'),
    ('forget_round_robin_history',
     'queue = self.next_queue', 'queue = 0',
     'Budget-one polls repeatedly select objects and starve other queues.'),
    ('retired_frame_missing_task',
     'self.frames.append(frame)\n        self.pending += 1',
     'self.frames.append(frame)\n        self.pending += 0',
     'Detached owner frame is physically present but absent from work cardinality.'),
    ('duplicate_sparse_index',
     'if name is not None and index not in frame.written:',
     'if name is not None:',
     'Repeated/moved local write appends duplicate retirement owner indices.'),
    ('lost_local_retain',
     'if name and not take:\n            self.objects[name].owners += 1',
     'if name and not take:\n            self.objects[name].owners += 0',
     'Replacement fails to establish the new owner before releasing the old.'),
    ('partial_chunk_floor',
     'self.pending += count // 8 + (count % 8 != 0)',
     'self.pending += count // 8',
     'Last partial chunk is omitted from task count, including view-root owner.'),
    ('view_recursively_destroys_root',
     'root.owners -= 1\n                if not root.owners:\n                    self._enqueue(root.name)',
     'self._drop(root.name)',
     'One view visit can physically destroy two managed objects in one unit.'),
    ('fused_carry_undercount',
     'self.active = child.name\n                work += 2',
     'self.active = child.name\n                work += 1',
     'Private carried unary pair consumes two units but records only one.'),
    ('private_child_keeps_live_count',
     'child.owners = 0\n                child.dead = True',
     'child.owners = 1\n                child.dead = True',
     'Transferred zero-count child remains physically live under a dead tag.'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    original = root / 'tests/peer-memory-model-accounting.py'
    source_path = args.source or original
    source = source_path.read_text()
    output = args.output or root / 'research/2026-10-memory/literature-accounting-mutants.json'
    report = {'scope': 'Pure-model semantic mutations, not mutated-C execution or production defects.',
              'source': str(source_path), 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'mutants': []}
    # Point __file__ at the maintained original so static source-map checks use
    # the repository, while executing a separate mutated module in isolation.
    command_code = "import pathlib,sys;source=pathlib.Path(sys.argv[1]).read_text();__file__=sys.argv[2];sys.argv=[sys.argv[2]];exec(compile(source,__file__,'exec'))"
    with tempfile.TemporaryDirectory(prefix='peer-memory-model-calibration-') as directory:
        calibration = Path(directory) / 'original.py'
        calibration.write_text(source)
        result = subprocess.run([sys.executable, '-c', command_code, str(calibration), str(original)],
                                capture_output=True, text=True, timeout=5)
        report['calibration'] = {'exit_code': result.returncode, 'stderr': result.stderr}
        output.write_text(json.dumps(report, indent=2) + '\n')
        assert result.returncode == 0 and 'Ran ' in result.stderr, 'unmutated runner failed: ' + result.stderr
    for name, before, after, meaning in MUTANTS:
        assert source.count(before) == 1, (name, 'anchor must match exactly once')
        mutated = source.replace(before, after)
        with tempfile.TemporaryDirectory(prefix='peer-memory-model-mutant-') as directory:
            path = Path(directory) / 'mutant.py'
            path.write_text(mutated)
            command = [sys.executable, '-c', command_code, str(path), str(original)]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
                completed_tests = 'Ran ' in result.stderr
                status = ('survived' if result.returncode == 0 else
                          'killed' if completed_tests and 'FAILED (' in result.stderr else
                          'invalid_runner_or_mutant')
                record = {'name': name, 'meaning': meaning, 'status': status,
                          'mutated_sha256': hashlib.sha256(mutated.encode()).hexdigest(),
                          'exit_code': result.returncode, 'stdout': result.stdout,
                          'stderr': result.stderr}
            except subprocess.TimeoutExpired as error:
                record = {'name': name, 'meaning': meaning, 'status': 'timeout_inconclusive',
                          'stderr': str(error)}
            report['mutants'].append(record)
        output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'killed': sum(m['status'] == 'killed' for m in report['mutants']),
                      'survived': [m['name'] for m in report['mutants'] if m['status'] == 'survived'],
                      'timeouts': [m['name'] for m in report['mutants'] if m['status'] == 'timeout_inconclusive'],
                      'evidence': str(output)}))


if __name__ == '__main__':
    main()
