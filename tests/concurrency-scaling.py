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
            mock = patch.object(scaling, target, replacement) if '.' not in target else None
            if '.' in target:
                owner, attribute = target.split('.')
                mock = patch.object(getattr(scaling, owner), attribute, replacement,
                                    create=owner == 'os' and attribute == 'sched_getaffinity')
            mock.start()
            self.addCleanup(mock.stop)
        self.clock = 0
        self.observed_clock = 0
        self.control_seconds = 8
        self.width_seconds = {1: 8, 2: 4, 4: 2, 8: 1}

    def publish(self):
        value = dict(self.value)
        value['protocol_sha256'] = hashlib.sha256(scaling.canonical(value)).hexdigest()
        self.protocol.write_text(json.dumps(value))

    def item(self, index):
        phase = 'warmup_order' if index < 3 else 'paired_order'
        order = self.value[phase][index if index < 3 else index - 3]
        ticks = []
        def append(seconds):
            ticks.append(self.clock)
            self.clock += int(seconds * 1e9)
            ticks.append(self.clock)
        for width in order:
            if width == 1 and 'single_thread_control' in self.value and (index if index < 3 else index - 3) % 2 == 0:
                append(self.control_seconds)
            append(self.width_seconds[width])
            if width == 1 and 'single_thread_control' in self.value and (index if index < 3 else index - 3) % 2 != 0:
                append(self.control_seconds)
        clock = iter(ticks)
        def tick():
            self.observed_clock = next(clock)
            return self.observed_clock
        def usage(_):
            return argparse.Namespace(ru_utime=self.observed_clock / 1e9, ru_stime=0)
        with patch.object(scaling.time, 'perf_counter_ns', side_effect=tick), \
                patch.object(scaling.resource, 'getrusage', side_effect=usage), \
                contextlib.redirect_stdout(io.StringIO()):
            scaling.run(argparse.Namespace(protocol=self.protocol, results=self.results, item=index))

    def control(self):
        self.value['single_thread_control'] = {'executable': self.value['executable'],
            'sha256': self.value['executable_sha256'], 'source_sha': 'fixed',
            'upper_95_ratio_max': 1.01}
        self.publish()

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
        with patch.object(scaling.time, 'sleep') as sleep:
            with self.assertRaises(RuntimeError): self.item(1)
        self.assertEqual(sum(call.args == (30,) for call in sleep.call_args_list), 10)
        self.assertEqual(len(json.loads(self.results.read_text())['preflight_waits'][-1]['checks']), 11)
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

    def test_paired_cpu_improvement_passes(self):
        self.control()
        self.control_seconds = 9
        for index in range(43): self.item(index)
        result = json.loads(self.results.read_text())
        self.assertTrue(result['qualified'])
        self.assertEqual(len(result['samples']), 172)
        self.assertEqual(len(result['single_thread_pairs']), 43)
        self.assertEqual(len(result['single_thread_cpu']['ratios']), 40)
        self.assertLess(result['single_thread_cpu']['interval_95'][1], .99)

    def test_paired_cpu_regression_fails(self):
        self.control()
        self.control_seconds = 8 / 1.02
        for index in range(42): self.item(index)
        with self.assertRaises(SystemExit): self.item(42)
        result = json.loads(self.results.read_text())
        self.assertFalse(result['qualified'])
        self.assertFalse(result['single_thread_cpu']['qualified'])
        self.assertGreater(result['single_thread_cpu']['interval_95'][1], 1.01)

    def test_changed_workload_or_gate_rejected(self):
        self.value['workload_sha256'] = 'changed'
        self.publish()
        with self.assertRaises(RuntimeError): self.item(0)

        self.value['workload_sha256'] = scaling.WORKLOAD_SHA256
        self.value['gates']['median_eight_min'] = 7.1
        self.publish()
        with self.assertRaises(RuntimeError): self.item(0)

    def resources(self, session='100', parent='user-1000.slice'):
        root = self.directory / 'cgroup'
        leaf = root / 'user.slice' / parent / ('session-' + session + '.scope')
        leaf.mkdir(parents=True, exist_ok=True)
        for directory in (root, root / 'user.slice', leaf.parent, leaf):
            (directory / 'cpu.max').write_text('max 100000\n')
            (directory / 'cpu.max.burst').write_text('0\n')
            (directory / 'cpu.weight').write_text('100\n')
            (directory / 'cpuset.cpus.effective').write_text('0-7\n')
        membership = '0::/user.slice/' + parent + '/session-' + session + '.scope\n'
        return root, leaf, membership

    def test_resource_session_change_only(self):
        root, _, first = self.resources()
        _, _, second = self.resources('101')
        self.assertEqual(scaling.resource_identity(first, root), scaling.resource_identity(second, root))

    def test_resource_guard_rejects_before_measurement(self):
        root, leaf, membership = self.resources()
        original = scaling.resource_identity(membership, root)
        self.value['resource_identity'] = original
        self.publish()
        (leaf / 'cpu.max').write_text('400000 100000\n')
        changed = scaling.resource_identity(membership, root)
        with patch.object(scaling, 'resource_snapshot', return_value={'identity': changed}), \
                patch.object(scaling, 'cpu_ticks', side_effect=AssertionError('measurement started')):
            with self.assertRaisesRegex(RuntimeError, 'ancestry, limits or availability'):
                self.item(0)
        self.assertFalse(self.results.exists())

    def test_resource_parent_quota_cpuset_and_availability(self):
        root, leaf, first = self.resources()
        original = scaling.resource_identity(first, root)
        _, _, moved = self.resources('102', 'other.slice')
        self.assertNotEqual(original, scaling.resource_identity(moved, root))
        for name, value in (('cpu.max', '400000 100000\n'), ('cpu.max.burst', '1000\n'),
                            ('cpu.weight', '200\n'), ('cpuset.cpus.effective', '0-3\n')):
            path = leaf.parent / name
            before = path.read_text()
            path.write_text(value)
            self.assertNotEqual(original, scaling.resource_identity(first, root))
            path.write_text(before)
            path.unlink()
            self.assertNotEqual(original, scaling.resource_identity(first, root))
            path.write_text(before)
        with patch.object(scaling.os, 'sched_getaffinity', return_value={0, 1, 2, 3}):
            self.assertNotEqual(original, scaling.resource_identity(first, root))
        real_read = Path.read_text
        def unreadable(path, *args, **kwargs):
            if path == leaf / 'cpu.max': raise PermissionError(13, 'denied')
            return real_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', unreadable):
            self.assertNotEqual(original, scaling.resource_identity(first, root))


if __name__ == '__main__':
    unittest.main()
