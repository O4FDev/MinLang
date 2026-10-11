#!/usr/bin/env python3
"""Negative controls for mandatory QUIC RFC case and link provenance."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('quic_rfc', ROOT / 'tests/quic-rfc.py')
RFC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RFC)


class QuicRfcHarness(unittest.TestCase):
    def test_author_inventory_is_literal_complete_and_unfiltered(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'cases.py'
            for literal, expected in (("{'a': (0, ''), 'b': (0, '')}", ['a', 'b']),
                                      ("('a', 'b')", ['a', 'b'])):
                source.write_text('BASELINE = ' + literal + '\n')
                self.assertEqual(RFC.declared_cases(source, 'BASELINE'), expected)
            for content in ("BASELINE = ()\n", "BASELINE = ('a','a')\n",
                            "BASELINE = (1,)\n", "BASELINE = factory()\n",
                            "BASELINE = ('a',)\nBASELINE = ('b',)\n"):
                source.write_text(content)
                with self.subTest(content=content), self.assertRaises((ValueError, TypeError)):
                    RFC.declared_cases(source, 'BASELINE')

    def test_every_protocol_result_and_binary_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            binaries = {}
            for name in RFC.BINARIES:
                binaries[name] = directory / name
                binaries[name].write_bytes(name.encode())
            source = directory / 'source.min'
            source.write_text('function main() {}\n')
            rows = [dict(case=name, expected_returncode=0, returncode=0,
                         matched=True, stdout='passed\n', stderr='')
                    for name in ('a', 'b')]
            positive = dict(baseline=False, compiler_invoked=False, results=rows,
                            binary_sha256=RFC.digest(binaries['migration']),
                            test_source_sha256=RFC.digest(source))
            RFC.verify_result('migration', positive, ['a', 'b'], binaries, source)
            for name, changes in (
                    ('missing', {'results': rows[:1]}),
                    ('duplicate', {'results': rows + rows[:1]}),
                    ('reordered', {'results': rows[::-1]}),
                    ('old oracle', {'baseline': True}),
                    ('compiler invoked', {'compiler_invoked': True}),
                    ('wrong binary', {'binary_sha256': '0' * 64}),
                    ('wrong source', {'test_source_sha256': '0' * 64})):
                mutant = dict(positive, **changes)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    RFC.verify_result('migration', mutant, ['a', 'b'], binaries, source)
            for field, value in (('returncode', 1), ('expected_returncode', 42),
                                 ('matched', False), ('stderr', 'AddressSanitizer\n')):
                mutant = copy.deepcopy(positive)
                mutant['results'][1][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    RFC.verify_result('migration', mutant, ['a', 'b'], binaries, source)

    def test_local_endpoint_and_version_negotiation_results(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            binaries = {name: directory / name for name in ('client', 'server')}
            for name, path in binaries.items():
                path.write_bytes(name.encode())
            positive = dict(binary_hashes={name: RFC.digest(path)
                                          for name, path in binaries.items()},
                            results=[dict(case='keyupdate', expected=0, semantic_status=0,
                                client_status=0, matched=True, files_match=True,
                                reciprocal_epoch_secrets=True, client_stderr='', server_stderr='')])
            RFC.verify_result('local', positive, ['keyupdate'], binaries, None)
            for field, value in (('semantic_status', 62), ('client_status', 1),
                                 ('expected', 62), ('files_match', False),
                                 ('reciprocal_epoch_secrets', False),
                                 ('client_stderr', 'runtime error\n'),
                                 ('server_stderr', 'AddressSanitizer\n')):
                mutant = copy.deepcopy(positive)
                mutant['results'][0][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    RFC.verify_result('local', mutant, ['keyupdate'], binaries, None)
            vn = dict(result='passed', server_sha256=RFC.digest(binaries['server']),
                      reserved_version='0x0a0a0a0a', versions=[1], request_bytes=1200,
                      response_bytes=27)
            RFC.verify_result('vn', vn, None, binaries, None)
            for field, value in (('result', 'failed'), ('server_sha256', '0' * 64),
                                 ('versions', [0x0a0a0a0a]), ('request_bytes', 1199),
                                 ('response_bytes', 3601)):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    RFC.verify_result('vn', dict(vn, **{field: value}), None, binaries, None)

    def test_canonical_program_annotation_and_native_runtime_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            binary = directory / 'endpoint'
            binary.write_bytes(b'native endpoint proof')
            (directory / 'program').write_bytes(binary.read_bytes())
            raw = b'define i32 @main() {\nentry:\n  ret i32 0\n}\n'
            (directory / 'program.raw.ll').write_bytes(raw)
            annotated = RFC.instrument_address_sanitizer(raw.decode()).encode()
            (directory / 'program.asan.ll').write_bytes(annotated)
            (directory / 'runtime.o').write_bytes(b'native runtime object')
            for name in ('clang-driver.py', 'sanitizer_llvm.py'):
                (directory / name).write_bytes((ROOT / 'tools' / name).read_bytes())
            (directory / 'clang.bin').write_bytes(b'compiler proof')
            positive = dict(schema=1, link_status=0, address_sanitizer_enabled=True,
                program_ir_cached=False, runtime_reannotated=False,
                raw_sha256=RFC.digest(directory / 'program.raw.ll'),
                linked_program_sha256=RFC.digest(directory / 'program.asan.ll'),
                binary_sha256=RFC.digest(binary),
                raw_program=str(directory/'program.raw.ll'),
                command=['clang', str(directory/'program.asan.ll'), '/original/runtime.o'],
                compiler_version='recorded Clang version',
                inputs=[dict(original='/original/runtime.o', retained='runtime.o',
                             sha256=RFC.digest(directory / 'runtime.o'))],
                tools={name: RFC.digest(directory / name)
                       for name in ('clang-driver.py', 'sanitizer_llvm.py', 'clang.bin')})
            manifest = directory / 'manifest.json'
            manifest.write_text(json.dumps(positive))
            RFC.verify_link(directory, binary, True)
            native = dict(positive, address_sanitizer_enabled=False,
                          linked_program_sha256=RFC.digest(directory/'program.raw.ll'),
                          command=['clang', str(directory/'program.raw.ll'), '/original/runtime.o'])
            manifest.write_text(json.dumps(native))
            RFC.verify_link(directory, binary, False)
            self.assertEqual((directory/'program.raw.ll').read_bytes(), raw)
            self.assertEqual((directory/'runtime.o').read_bytes(), b'native runtime object')
            manifest.write_text(json.dumps(positive))
            for name, value in (('link_status', 1), ('address_sanitizer_enabled', False),
                                ('program_ir_cached', True), ('runtime_reannotated', True),
                                ('raw_sha256', '0' * 64), ('linked_program_sha256', '0' * 64),
                                ('binary_sha256', '0' * 64), ('inputs', []), ('compiler_version', ''),
                                ('command', ['clang', '/other/program.ll', '/original/runtime.o']),
                                ('tools', {})):
                manifest.write_text(json.dumps(dict(positive, **{name: value})))
                with self.subTest(field=name), self.assertRaises(ValueError):
                    RFC.verify_link(directory, binary, True)
            mutant = copy.deepcopy(positive)
            mutant['inputs'][0]['original'] = '/original/runtime.ll'
            manifest.write_text(json.dumps(mutant))
            with self.assertRaises(ValueError):
                RFC.verify_link(directory, binary, True)
            manifest.write_text(json.dumps(positive))
            (directory / 'program.asan.ll').write_bytes(raw)
            with self.assertRaises(ValueError):
                RFC.verify_link(directory, binary, True)
            (directory / 'program.asan.ll').write_bytes(annotated)
            (directory / 'runtime.o').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                RFC.verify_link(directory, binary, True)


if __name__ == '__main__':
    unittest.main()
