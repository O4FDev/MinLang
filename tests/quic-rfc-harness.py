#!/usr/bin/env python3
"""Prepared benign controls for RFC inventories, provenance and failure retention."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


RFC = module('quic_rfc', ROOT / 'tests/quic-rfc.py')
DRIVER = module('quic_rfc_clang', ROOT / 'tools/clang-driver.py')


class QuicRfcHarness(unittest.TestCase):
    def test_literal_inventory_rejects_duplicate_dictionary_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'cases.py'
            for literal in ("{'a': 0, 'b': 0}", "('a', 'b')", "['a', 'b']"):
                source.write_text('BASELINE = ' + literal + '\n')
                self.assertEqual(RFC.declared_cases(source, 'BASELINE'), ['a', 'b'])
            for content in ("BASELINE=()\n", "BASELINE=('a','a')\n",
                            "BASELINE={'a':0,'a':1}\n", "BASELINE=(1,)\n",
                            "BASELINE=factory()\n", "BASELINE='abc'\n",
                            "BASELINE=('a',)\nBASELINE=('b',)\n"):
                source.write_text(content)
                with self.subTest(content=content), self.assertRaises((ValueError, TypeError)):
                    RFC.declared_cases(source, 'BASELINE')

    def test_numeric_fields_exclude_boolean_float_and_string_values(self):
        for value in (True, False, 0.0, 2.0, '0', None):
            self.assertFalse(RFC.exact_integer(value))
        for value in (-127, 0, 2, 1200):
            self.assertTrue(RFC.exact_integer(value))
        self.assertFalse(RFC.exact_integer(-1, minimum=0))
        self.assertFalse(RFC.exact_integer(5, maximum=4))
        self.assertEqual(DRIVER.effective_optimization(['-O0', '-ObjC']), '0')
        self.assertEqual(DRIVER.effective_optimization(['-O2', '-O']), '1')
        self.assertEqual(DRIVER.effective_optimization(['-O0', '-Ofast', '-O2']), '2')
        for flag in ('-ObjC', '-ObjC++', '-Other', '-O2garbage'):
            self.assertIsNone(DRIVER.effective_optimization([flag]))

    def protocol_fixture(self, directory):
        binaries = {name: directory / name for name in RFC.BINARIES}
        for name, path in binaries.items():
            path.write_bytes(name.encode())
        source = directory / 'source.min'
        source.write_text('function main() {}\n')
        rows = [dict(case=name, expected_returncode=0, returncode=0,
                     matched=True, stdout='passed\n', stderr='') for name in ('a', 'b')]
        return binaries, source, dict(baseline=False, compiler_invoked=False, results=rows,
            binary_sha256=RFC.digest(binaries['migration']),
            test_source_sha256=RFC.digest(source))

    def test_protocol_reports_preserve_every_case_and_exact_status(self):
        with tempfile.TemporaryDirectory() as folder:
            binaries, source, positive = self.protocol_fixture(Path(folder))
            RFC.verify_result('migration', positive, ['a', 'b'], binaries, source)
            for changes in ({'results': positive['results'][:1]},
                            {'results': positive['results'][::-1]},
                            {'results': positive['results'] + positive['results'][:1]},
                            {'baseline': True}, {'compiler_invoked': True},
                            {'binary_sha256': '0'*64}, {'test_source_sha256': '0'*64}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    RFC.verify_result('migration', dict(positive, **changes), ['a', 'b'], binaries, source)
            for key in ('expected_returncode', 'returncode'):
                for value in (True, False, 0.0, '0', 1):
                    mutant = copy.deepcopy(positive)
                    mutant['results'][0][key] = value
                    with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                        RFC.verify_result('migration', mutant, ['a', 'b'], binaries, source)
            local = dict(binary_hashes={name: RFC.digest(binaries[name]) for name in ('client','server')},
                results=[dict(case='keyupdate', expected=0, semantic_status=0, client_status=0,
                    matched=True, files_match=True, reciprocal_epoch_secrets=True,
                    client_stderr='', server_stderr='')])
            RFC.verify_result('local', local, ['keyupdate'], binaries, None)
            for key in ('expected', 'semantic_status', 'client_status'):
                for value in (False, 0.0, 62):
                    mutant = copy.deepcopy(local)
                    mutant['results'][0][key] = value
                    with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                        RFC.verify_result('local', mutant, ['keyupdate'], binaries, None)
            vn = dict(result='passed', server_sha256=RFC.digest(binaries['server']),
                      reserved_version=hex(0x0a0a0a0a), versions=[1],
                      request_bytes=1200, response_bytes=27)
            RFC.verify_result('vn', vn, ['reserved-version'], binaries, None)
            for key, values in (('request_bytes', (True, 1200.0, 1199)),
                                ('response_bytes', (False, 27.0, 3601)),
                                ('versions', ([True], [1.0], [1, 1], [0x0a0a0a0a]))):
                for value in values:
                    with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                        RFC.verify_result('vn', dict(vn, **{key:value}), None, binaries, None)

    def link_fixture(self, directory, sanitize=True):
        compiler = directory / 'selected-clang'
        compiler.write_bytes(b'benign selected compiler bytes')
        raw = directory / 'transient-program.ll'
        raw.write_bytes(b'define i32 @main() {\nentry:\n  ret i32 0\n}\n')
        runtime = directory / 'actual-runtime.o'
        runtime.write_bytes(b'unchanged native runtime object')
        provider = directory / 'actual-provider.o'
        provider.write_bytes(b'provider object bytes')
        binary = directory / 'endpoint'
        artifacts = directory / 'link'
        observed = []
        def ordinary_link(command, **kwargs):
            observed.append(list(command))
            self.assertEqual(command[-2], '-o')
            Path(command[-1]).write_bytes(b'benign staged native binary')
            return SimpleNamespace(returncode=0)
        with patch.dict(os.environ, {'MINYAR_LINK_ARTIFACTS':str(artifacts)}), \
                patch.object(DRIVER.subprocess, 'run', side_effect=ordinary_link), \
                patch.object(DRIVER.subprocess, 'check_output', return_value='benign Clang version\n'):
            DRIVER.link_program(str(compiler), RFC.requested_flags('0', sanitize), [],
                                str(raw), str(runtime), [str(provider)], ['-lcrypto'],
                                str(binary), None)
        report = json.loads((artifacts/'manifest.json').read_text())
        self.assertEqual(report['actual_command'], observed[0])
        self.assertEqual(len(observed), 1)  # Mocked link calls, not runtime compile counts.
        return artifacts, binary, report

    def test_actual_link_schema_input_output_and_tool_byte_binding(self):
        # This exercises only a mocked ordinary linker writing benign bytes.
        # It neither compiles nor executes LLVM or any generated access.
        with tempfile.TemporaryDirectory() as folder:
            artifacts, binary, positive = self.link_fixture(Path(folder))
            RFC.verify_link(artifacts, binary, True, '0', positive['tools']['clang.bin'])
            manifest = artifacts/'manifest.json'
            mutations = []
            def mutation(name, change):
                mutant = copy.deepcopy(positive)
                change(mutant)
                mutations.append((name, mutant))
            for key, values in (('schema', (True, 2.0, 1)),
                                ('link_status', (False, 0.0, 1)),
                                ('link_subprocess_status', (False, 0.0, 1))):
                for value in values:
                    mutation(key+repr(value), lambda row,k=key,v=value:row.update({k:v}))
            mutation('wrong compiler', lambda row:row['compiler_pre_link'].update(sha256='0'*64))
            mutation('wrong flags', lambda row:row.update(link_flags=['-O2']))
            mutation('wrong optimization', lambda row:row.update(optimization='2'))
            mutation('extra runtime IR', lambda row:row['command'].append('/extra/runtime.ll'))
            mutation('unrepresented provider', lambda row:row['command'].append('/extra/provider.o'))
            mutation('missing provider', lambda row:row.update(inputs=row['inputs'][:1]))
            mutation('wrong transient raw', lambda row:row['raw_program_input'].update(pre_link_sha256='0'*64))
            mutation('wrong copied raw', lambda row:row['raw_program_input'].update(retained_sha256='0'*64))
            mutation('wrong copied compiler', lambda row:row['tool_bindings']['clang.bin'].update(source_after_sha256='0'*64))
            mutation('wrong staged argv', lambda row:row['actual_command'].__setitem__(-1,'/other/stage'))
            mutation('wrong staged size', lambda row:row['staged_output'].update(bytes=True))
            mutation('wrong final size', lambda row:row['final_output'].update(bytes=float(row['final_output']['bytes'])))
            mutation('runtime reannotation', lambda row:row.update(runtime_reannotated=True))
            mutation('incomplete retention', lambda row:row.update(retention_errors=[{'phase':'copy'}]))
            for name, mutant in mutations:
                manifest.write_text(json.dumps(mutant))
                with self.subTest(name=name), self.assertRaises(ValueError):
                    RFC.verify_link(artifacts, binary, True)
            manifest.write_text(json.dumps(positive))
            (artifacts/'native-0.o').write_bytes(b'corrupt provider')
            with self.assertRaises(ValueError):
                RFC.verify_link(artifacts, binary, True)
        with tempfile.TemporaryDirectory() as folder:
            artifacts, binary, native = self.link_fixture(Path(folder), False)
            RFC.verify_link(artifacts, binary, False)
            self.assertEqual((artifacts/'program.raw.ll').read_bytes(),
                             (Path(folder)/'transient-program.ll').read_bytes())

    def test_producer_retains_child_failure_without_retention_masking(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            compiler, raw, runtime = (directory/name for name in ('compiler','raw.ll','runtime.o'))
            compiler.write_bytes(b'tool'); raw.write_bytes(b'define i32 @main() {\n ret i32 0\n}\n')
            runtime.write_bytes(b'runtime')
            artifacts = directory/'evidence'
            original_copy = DRIVER.shutil.copyfile
            def failed_copy(source, target):
                if Path(target).name == 'sanitizer_llvm.py':
                    raise OSError('retention intentionally unavailable')
                return original_copy(source,target)
            with patch.dict(os.environ, {'MINYAR_LINK_ARTIFACTS':str(artifacts)}), \
                    patch.object(DRIVER.subprocess,'run',return_value=SimpleNamespace(returncode=37)), \
                    patch.object(DRIVER.subprocess,'check_output',return_value='version'):
                with self.assertRaises(SystemExit) as status:
                    DRIVER.link_program(str(compiler), RFC.requested_flags('0',False), [],
                        str(raw),str(runtime),[],[],str(directory/'output'),None)
            self.assertEqual(status.exception.code,37)
            report=json.loads((artifacts/'manifest.json').read_text())
            self.assertEqual(report['link_subprocess_status'],37)
            self.assertIn('SystemExit',report['link_error'])
            # A separate setup failure also produces a manifest, before link.
            second=directory/'setup-failure'
            with patch.dict(os.environ, {'MINYAR_LINK_ARTIFACTS':str(second)}), \
                    patch.object(DRIVER.shutil,'copyfile',side_effect=failed_copy):
                with self.assertRaises(OSError):
                    DRIVER.link_program(str(compiler),RFC.requested_flags('0',False),[],
                        str(raw),str(runtime),[],[],str(directory/'second-output'),None)
            setup=json.loads((second/'manifest.json').read_text())
            self.assertFalse(setup['link_attempted'])
            self.assertTrue(setup['retention_errors'])

    def test_setup_and_finalization_errors_keep_failure_manifest_and_exception(self):
        for phase in ('snapshot', 'copy', 'Evidence'):
            with tempfile.TemporaryDirectory() as folder:
                directory=Path(folder)
                original=ValueError('original '+phase)
                if phase == 'snapshot':
                    target=patch.object(RFC,'snapshot_inputs',side_effect=original)
                elif phase == 'copy':
                    target=patch.object(RFC,'bound_copy',side_effect=original)
                else:
                    target=patch.object(RFC,'Evidence',side_effect=original)
                inputs={'minyar':RFC.digest(ROOT/'minyar')}
                # Supply all frontend copies without invoking an actual compiler.
                fakecopy=lambda source,target:dict(before='a'*64,retained='a'*64,after='a'*64,
                                                  source=str(source),copy=str(target))
                with patch.object(RFC,'snapshot_inputs',return_value=inputs), \
                        patch.object(RFC,'bound_copy',side_effect=fakecopy), \
                        patch.object(RFC.Path,'is_file',return_value=True), target:
                    with self.assertRaises(ValueError) as observed:
                        RFC.run_gate(directory,False)
                self.assertIs(observed.exception,original)
                report=json.loads((directory/'manifest.json').read_text())
                self.assertFalse(report['passed'])
                self.assertEqual(report['error']['message'],str(original))
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            report=dict(passed=True,retention_errors=[])
            original_write=Path.write_text
            def fail_primary(path,*args,**kwargs):
                if path.name=='manifest.json':
                    raise OSError('primary write failure')
                return original_write(path,*args,**kwargs)
            with patch.object(Path,'write_text',new=fail_primary):
                RFC.write_report(directory,report)
            self.assertFalse(report['passed'])
            self.assertTrue((directory/'manifest-retention-error.json').is_file())
            self.assertEqual(report['retention_errors'][0]['phase'],'manifest-write')

    def test_copy_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source,target=(Path(folder)/name for name in ('source','copy'))
            source.write_bytes(b'original')
            with patch.object(RFC.shutil,'copyfile',side_effect=lambda a,b:Path(b).write_bytes(b'wrong')):
                with self.assertRaises(ValueError):
                    RFC.bound_copy(source,target)


if __name__ == '__main__':
    unittest.main()
