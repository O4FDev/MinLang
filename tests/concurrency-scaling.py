import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scaling', ROOT / 'tools/concurrency_scaling.py')
scaling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scaling)


class ScalingProtocol(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        artifact = self.directory / 'artifact'
        artifact.write_bytes(b'fixed')
        self.protocol = self.directory / 'protocol.json'
        self.results = self.directory / 'results.json'
        self.value = {
            'executable': str(artifact), 'executable_sha256': scaling.digest(artifact),
            'lowered_llvm': str(artifact), 'lowered_llvm_sha256': scaling.digest(artifact),
            'clang_path': str(artifact), 'clang_sha256': scaling.digest(artifact),
            'workload_sha256': scaling.WORKLOAD_SHA256,
            'sampler_sha256': scaling.digest(Path(scaling.__file__)),
            'affinity': list(range(8)), 'python': sys.version,
            'kernel': list(scaling.os.uname()), 'guest_topology': 'fixed', 'quota': {},
            'warmup_order': scaling.schedule(3, scaling.ORDER_SEED + 1),
            'paired_order': scaling.schedule(40, scaling.ORDER_SEED),
            'expected_stdout': scaling.oracle(),
            'gates': {'median_eight_min': 7.2, 'lower_95_eight_min': 6.4},
        }
        self.publish()
        self.activity = {'other_busy_fraction': 0, 'steal_fraction': 0}
        for target, replacement in (
                ('os.sched_getaffinity', lambda _: set(range(8))),
                ('subprocess.check_output', lambda *a, **k: 'fixed'),
                ('subprocess.run', lambda *a, **k: argparse.Namespace(returncode=0,
                    stdout=self.value['expected_stdout'], stderr='')),
                ('cpu_ticks', lambda: {}),
                ('cpu_activity', lambda *a: dict(self.activity)),
                ('time.sleep', lambda _: None)):
            mock = patch.object(scaling, target, replacement) if '.' not in target else patch(
                'scaling.' + target, replacement)
            if '.' in target:
                owner, attribute = target.split('.')
                mock = patch.object(getattr(scaling, owner), attribute, replacement)
            mock.start()
            self.addCleanup(mock.stop)
        self.clock = 0
        self.width_seconds = {1: 8, 2: 4, 4: 2, 8: 1}

    def publish(self):
        value = dict(self.value)
        value['protocol_sha256'] = hashlib.sha256(scaling.canonical(value)).hexdigest()
        self.protocol.write_text(json.dumps(value))

    def item(self, index):
        phase = 'warmup_order' if index < 3 else 'paired_order'
        order = self.value[phase][index if index < 3 else index - 3]
        ticks = []
        for width in order:
            ticks.append(self.clock)
            self.clock += int(self.width_seconds[width] * 1e9)
            ticks.append(self.clock)
        with patch.object(scaling.time, 'perf_counter_ns', side_effect=ticks), contextlib.redirect_stdout(io.StringIO()):
            scaling.run(argparse.Namespace(protocol=self.protocol, results=self.results, item=index))

    def test_complete_original_campaign(self):
        for index in range(43): self.item(index)
        result = json.loads(self.results.read_text())
        self.assertTrue(result['qualified'])
        self.assertEqual(len(result['samples']), 172)
        self.assertEqual(len(result['preflights']), 43)
        self.assertEqual(result['scaling']['8']['median'], 8)
        self.assertEqual(result['scaling']['8']['interval_95'], [8, 8])

    def test_duplicate_skip_and_failed_resume(self):
        self.item(0)
        original = self.results.read_bytes()
        with self.assertRaises(FileExistsError): self.item(0)
        with self.assertRaises(RuntimeError): self.item(2)
        self.assertEqual(self.results.read_bytes(), original)
        self.activity['other_busy_fraction'] = .021
        with self.assertRaises(RuntimeError): self.item(1)
        with self.assertRaises(RuntimeError): self.item(1)
        self.assertIn('failure', json.loads(self.results.read_text()))

    def test_original_threshold_and_all_samples(self):
        self.width_seconds[8] = 8 / 7.19
        for index in range(42): self.item(index)
        with self.assertRaises(SystemExit): self.item(42)
        self.assertFalse(json.loads(self.results.read_text())['qualified'])
        self.assertEqual(len(json.loads(self.results.read_text())['samples']), 172)

    def test_lower_interval_gate(self):
        self.assertEqual(scaling.bootstrap_interval([5] * 20 + [10] * 20), (5, 10))
        with self.assertRaises(ValueError): scaling.bootstrap_interval([8] * 39)

    def test_changed_workload_or_gate_rejected(self):
        self.value['workload_sha256'] = 'changed'
        self.publish()
        with self.assertRaises(RuntimeError): self.item(0)
        self.value['workload_sha256'] = scaling.WORKLOAD_SHA256
        self.value['gates']['median_eight_min'] = 7.1
        self.publish()
        with self.assertRaises(RuntimeError): self.item(0)


if __name__ == '__main__':
    unittest.main()
