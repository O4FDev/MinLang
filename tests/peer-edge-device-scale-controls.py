#!/usr/bin/env python3
"""Reject misleading device-capacity and heartbeat evidence before live load."""
import copy
import importlib.util
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('device_scale', Path(__file__).with_name('peer-edge-device-scale.py'))
scale = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scale)


def rows(count, now=1000):
    return [(f'peer:live:{{exit-{index:05d}}}', dict(exit_id=f'exit-{index:05d}',
        edge_instance='localhost:12345', edge_region='eu-west', _epoch=f'{index + 1:064x}',
        capacity_weight=1, in_flight=0, max_concurrent=8, paused=False, policy_hash='a' * 64,
        public_ip='203.0.113.2', asn=64500, country='GB', ts=now)) for index in range(count)]


class CapacityEvidence(unittest.TestCase):
    def check(self, records, count=7, **kwargs):
        return scale.validate_states(records, count, 'localhost:12345', now=1000, **kwargs)

    def test_actual_distinct_devices_required(self):
        for count in (1, 7, 32, 101):
            record = rows(count)
            random.Random(9002).shuffle(record)
            epochs = self.check(record, count)
            self.assertEqual(len(epochs), count)

    def test_gateway_count_and_partial_device_count_are_insufficient(self):
        for wrong in ([], rows(6), rows(8), rows(1) * 7,
                      [('gateway-count', dict(connections=20000))]):
            with self.assertRaises(ValueError):
                self.check(wrong)

    def test_each_record_is_bound_to_its_expected_key_and_exit(self):
        mutations = [('exit_id', 'exit-other'), ('edge_instance', 'other:12345'),
                     ('edge_region', 'elsewhere'), ('_epoch', 'x' * 64),
                     ('capacity_weight', 0), ('capacity_weight', True),
                     ('in_flight', True), ('max_concurrent', 99), ('paused', True),
                     ('policy_hash', 'b' * 64), ('public_ip', '203.0.113.3'),
                     ('asn', 64501), ('country', 'US'), ('ts', 969), ('ts', 1001),
                     ('ts', True)]
        for field, wrong in mutations:
            for index in (0, 3, 6):
                with self.subTest(field=field, index=index):
                    records = rows(7)
                    records[index][1][field] = wrong
                    with self.assertRaises(ValueError):
                        self.check(records)
        for field in rows(1)[0][1]:
            records = rows(7)
            del records[3][1][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.check(records)

    def test_all_epochs_remain_fenced_and_all_heartbeats_advance(self):
        initial = self.check(rows(7, 980))
        self.check(rows(7), previous=initial, minimum_timestamp=995)
        for index in range(7):
            records = rows(7)
            records[index][1]['_epoch'] = 'f' * 64
            with self.assertRaises(ValueError):
                self.check(records, previous=initial)
            records = rows(7)
            records[index][1]['ts'] = 990
            with self.assertRaises(ValueError):
                self.check(records, previous=initial, minimum_timestamp=995)

    def test_input_is_not_repaired_or_mutated(self):
        records = rows(7)
        original = copy.deepcopy(records)
        self.check(records)
        self.assertEqual(records, original)

    def test_generated_identities_pass_independent_strict_x509_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'certificates'
            scale.make_fixtures(directory, 3)
            root = directory / 'root.pem'
            subprocess.run(['openssl', 'x509', '-inform', 'DER', '-in', str(directory / 'root.der'),
                            '-out', str(root)], check=True, capture_output=True)
            for label, purpose in [('server', 'sslserver'), ('gateway', 'sslclient')] + [
                    (f'device-{index:05d}', 'sslclient') for index in range(3)]:
                with self.subTest(identity=label):
                    pem = directory / (label + '.pem')
                    subprocess.run(['openssl', 'x509', '-inform', 'DER', '-in', str(directory / (label + '.der')),
                                    '-out', str(pem)], check=True, capture_output=True)
                    command = ['openssl', 'verify', '-x509_strict', '-auth_level', '2', '-trusted_first',
                               '-purpose', purpose, '-CAfile', str(root)]
                    if purpose == 'sslserver':
                        command += ['-verify_hostname', 'localhost']
                    result = subprocess.run([*command, str(pem)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    wrong = subprocess.run(['openssl', 'verify', '-x509_strict', '-auth_level', '2',
                        '-purpose', 'sslclient' if purpose == 'sslserver' else 'sslserver',
                        '-CAfile', str(root), str(pem)], capture_output=True, text=True)
                    self.assertNotEqual(wrong.returncode, 0, 'wrong-purpose certificate was accepted')


if __name__ == '__main__':
    unittest.main()
