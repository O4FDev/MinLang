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
            for name, flag in (('late optimization override','-O2'),
                               ('late ASan disable','-fno-sanitize=address'),
                               ('late all-sanitizer disable','-fno-sanitize=all')):
                def change(row, flag=flag):
                    row['command'].append(flag)
                    row['actual_command'] = row['command'] + ['-o',row['staged_requested_path']]
                mutation(name,change)
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
            for flag in ('-fsanitize=address', '@unrepresented-flags'):
                mutant=copy.deepcopy(native)
                mutant['command'].append(flag)
                mutant['actual_command']=mutant['command']+['-o',mutant['staged_requested_path']]
                (artifacts/'manifest.json').write_text(json.dumps(mutant))
                with self.subTest(native_override=flag),self.assertRaises(ValueError):
                    RFC.verify_link(artifacts,binary,False)
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
                fakecopy=lambda source,target:dict(before=inputs.get(source.relative_to(ROOT).as_posix(),'a'*64),retained=inputs.get(source.relative_to(ROOT).as_posix(),'a'*64),after=inputs.get(source.relative_to(ROOT).as_posix(),'a'*64),
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

    def test_per_case_artifact_inventories_reject_missing_and_wrong_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';artifacts=base/'artifacts'
            project.mkdir();artifacts.mkdir();(artifacts/'fixtures').mkdir()
            names=('tests/quic-migration-cids.py','tests/quic-migration-cids.min',
                   'tests/quic_protocol_artifacts.py','tests/test_evidence.py','tests/tls-local.py')
            sources={}
            for name in names:
                path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(name.encode())
                sources[name]=RFC.digest(path)
            binary=base/'migration';binary.write_bytes(b'benign native fixture')
            certificate_files=['fixtures/'+name for name in
                               ('root.der','server.der','server.pk8','client.der','client.pk8')]
            for name in certificate_files:
                (artifacts/name).write_bytes(name.encode())
            commands=[]
            for index,case in enumerate((None,'a','b')):
                row=dict(command=['openssl','version'] if case is None else [str(binary),*[str(artifacts/name) for name in certificate_files],case],
                    cwd=str(project),timeout=30 if case is None else 60,
                    phase='certificate-fixture' if case is None else 'protocol-case',case=case,
                    returncode=0,status=0,timed_out=False,executable_sha256='e'*64 if case is None else RFC.digest(binary))
                for stream in ('stdout','stderr'):
                    path=artifacts/(str(index)+'.'+stream)
                    path.write_bytes(b'passed\r\n' if case is not None and stream=='stdout' else b'')
                    row[stream+'_path']=str(path)
                    row[stream+'_sha256']=RFC.digest(path);row[stream+'_bytes']=path.stat().st_size
                commands.append(row)
            references=[]
            for case,index in (('a',1),('b',2)):
                raw=sorted(Path(commands[i][stream+'_path']).relative_to(artifacts).as_posix()
                           for i in (0,index) for stream in ('stdout','stderr'))
                roles=dict(certificates=sorted(certificate_files),raw_output=raw)
                references.append(dict(case=case,command_indices=[0,index],endpoint_indices=[],
                    fixture_workspace=str(artifacts/'fixtures'),file_roles=roles,
                    files=sorted([*certificate_files,*raw])))
            parsed=dict(declared_cases=['a','b'],case_inventory=references,
                        results=[dict(case=case,stdout='passed\n',stderr='') for case in ('a','b')])
            result_path=artifacts/'results.json';result_path.write_text(json.dumps(parsed))
            files=RFC.inventory(artifacts)
            positive=dict(schema_version=1,status='passed',workspace=str(artifacts/'fixtures'),
                inputs={str((project/name).resolve()):value for name,value in sources.items()},
                commands=commands,endpoint_commands=[],declared_cases=['a','b'],
                case_inventory=references,files=files,
                file_bytes={name:(artifacts/name).stat().st_size for name in files})
            positive['inputs'][str(binary)]=RFC.digest(binary)
            manifest=artifacts/'manifest.json'
            manifest.write_text(json.dumps(positive))
            with patch.object(RFC,'ROOT',project):
                RFC.verify_driver_artifacts(artifacts,'migration',parsed,['a','b'],
                                            {'migration':binary},sources)
                mutations=[]
                def add(name, change):
                    value=copy.deepcopy(positive);change(value);mutations.append((name,value))
                add('boolean schema',lambda row:row.update(schema_version=True))
                add('float schema',lambda row:row.update(schema_version=1.0))
                add('wrong source hash',lambda row:row['inputs'].update({str(project/names[0]):'0'*64}))
                add('missing source',lambda row:row['inputs'].pop(str(project/names[0])))
                add('wrong file hash',lambda row:row['files'].update({'fixtures/root.der':'0'*64}))
                add('missing file hash',lambda row:row['files'].pop('fixtures/root.der'))
                add('boolean file size',lambda row:row['file_bytes'].update({'fixtures/root.der':True}))
                add('float status',lambda row:row['commands'][1].update(status=0.0))
                add('boolean returncode',lambda row:row['commands'][1].update(returncode=False))
                add('float timeout',lambda row:row['commands'][1].update(timeout=60.0))
                add('different actual case',lambda row:row['commands'][1]['command'].__setitem__(-1,'b'))
                add('truncated case argv',lambda row:row['commands'][1].update(command=[str(binary),'a']))
                add('swapped certificate argv',lambda row:row['commands'][1]['command'].__setitem__(1,str(artifacts/'fixtures/server.der')))
                add('wrong raw hash',lambda row:row['commands'][1].update(stdout_sha256='0'*64))
                add('missing raw path',lambda row:row['commands'][1].pop('stdout_path'))
                add('boolean raw bytes',lambda row:row['commands'][1].update(stdout_bytes=True))
                add('reordered cases',lambda row:row.update(case_inventory=row['case_inventory'][::-1]))
                add('missing case hash refs',lambda row:row['case_inventory'][0].update(files=[]))
                add('missing case command',lambda row:row['case_inventory'][0].update(command_indices=[0]))
                add('boolean case index',lambda row:row['case_inventory'][0].update(command_indices=[0,True]))
                add('missing fixture role',lambda row:row['case_inventory'][0]['file_roles'].pop('certificates'))
                for name,value in mutations:
                    manifest.write_text(json.dumps(value))
                    with self.subTest(name=name),self.assertRaises((ValueError,TypeError)):
                        RFC.verify_driver_artifacts(artifacts,'migration',parsed,['a','b'],
                                                    {'migration':binary},sources)


    def test_snapshot_includes_assembly_and_all_native_cache_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder)
            names={'minyar','Makefile','tests/quic-rfc.py','tests/quic-rfc-harness.py',
                   'tests/tls-local.py','tests/test_evidence.py','tests/clang_helpers.py',
                   'tests/quic_protocol_artifacts.py','tests/quic-protocol-artifacts.py','tests/interop/qns/endpoint.py',
                   'compiler/managed-graphs-adapter.patch','scripts/build-closure-compiler.py',
                   'compiler/build-errors-compiler.py','vendor/monocypher/LICENCE.md',
                   'vendor/monocypher/NOTICE','runtime/native/abi.h'}
            names.update(RFC.BINARIES.values())
            names.update(row[1] for row in RFC.DRIVERS)
            for name in names:
                path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
            with patch.object(RFC,'ROOT',project),patch.object(RFC,'__file__',str(project/'tests/quic-rfc.py')):
                before=RFC.snapshot_inputs()
                self.assertEqual(set(before),names)
                (project/'vendor/monocypher/NOTICE').write_text('changed cache metadata')
                self.assertNotEqual(RFC.snapshot_inputs(),before)

    def test_original_child_status_survives_manifest_retention_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            compiler,raw,runtime=(directory/name for name in ('compiler','raw.ll','runtime.o'))
            compiler.write_bytes(b'compiler');runtime.write_bytes(b'runtime')
            raw.write_bytes(b'define i32 @main() {\n ret i32 0\n}\n')
            original_write=Path.write_text
            def fail_primary(path,*args,**kwargs):
                if path.name=='manifest.json':
                    raise OSError('intentional finalization failure')
                return original_write(path,*args,**kwargs)
            artifacts=directory/'failed-link'
            with patch.dict(os.environ,{'MINYAR_LINK_ARTIFACTS':str(artifacts)}), \
                    patch.object(DRIVER.subprocess,'run',return_value=SimpleNamespace(returncode=37)), \
                    patch.object(DRIVER.subprocess,'check_output',return_value='version'), \
                    patch.object(Path,'write_text',new=fail_primary):
                with self.assertRaises(SystemExit) as observed:
                    DRIVER.link_program(str(compiler),RFC.requested_flags('0',False),[],
                                        str(raw),str(runtime),[],[],str(directory/'output'),None)
            self.assertEqual(observed.exception.code,37)
            report=json.loads((artifacts/'manifest-retention-error.json').read_text())
            self.assertEqual(report['link_subprocess_status'],37)
            self.assertIn('SystemExit',report['link_error'])
            self.assertEqual(report['retention_errors'][0]['phase'],'manifest-retention')


    def test_complete_client_server_case_and_fixture_argv_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);workspace=directory/'fixtures';workspace.mkdir()
            binaries={name:directory/name for name in RFC.BINARIES}
            for name,path in binaries.items():path.write_bytes(name.encode())
            certificate_files=['fixtures/'+name for name in
                               ('root.der','server.der','server.pk8','client.der','client.pk8')]
            for name in certificate_files:(directory/name).write_bytes(name.encode())
            roles={'certificates':sorted(certificate_files)}
            migration=[str(binaries['migration'].resolve()),
                       *[str(directory/name) for name in certificate_files],'a']
            RFC.verify_case_invocation('migration','a',migration,None,roles,directory,binaries)
            for label,command in (('b',migration),('a',migration[:-1]),
                                  ('a',migration[:-1]+['b']),
                                  ('a',[migration[0],migration[2],*migration[2:]])):
                with self.subTest(label=label,command=command),self.assertRaises(ValueError):
                    RFC.verify_case_invocation('migration',label,command,None,roles,directory,binaries)
            mapping={'multiplex1999':'transfer','multiconnect50':'multiconnect',
                     'ipv6':'transfer','preferred':'connectionmigration',
                     'resumption40':'resumption','zerortt40':'zerortt',
                     'keyupdate':'keyupdate','chacha20':'chacha20'}
            for case,testcase in mapping.items():
                count=1999 if case=='multiplex1999' else 50 if case=='multiconnect50' else (
                    40 if case in ('resumption40','zerortt40') else 1)
                names=['file'+str(index) for index in range(count)]
                local_roles=dict(roles,payloads=['fixtures/'+case+'-www/'+name for name in sorted(names)],
                    downloads=['fixtures/'+case+'-downloads/'+name for name in sorted(names)],
                    keylogs=sorted(['fixtures/'+case+'-client.keys','fixtures/'+case+'-server.keys']))
                client=[str(binaries['client'].resolve()),str(workspace/'root.der'),
                        '::1' if case=='ipv6' else '127.0.0.1','44300',
                        str(workspace/(case+'-client.keys')),str(workspace/(case+'-downloads')),
                        testcase,*names]
                server=[str(binaries['server'].resolve()),str(workspace/'server.pk8'),
                        str(workspace/'root.der'),str(workspace/(case+'-server.keys')),
                        str(workspace/(case+'-www')),testcase,str(workspace/'server.der'),'--port=44300']
                if case=='preferred':server+=['--preferred-ipv4=7f000001','--preferred-port=44301']
                RFC.verify_case_invocation('local',case,client,server,local_roles,directory,binaries)
                for location in (0,1,2,3,4,5,6,7):
                    wrong=list(client);wrong[location]='incorrect'
                    with self.subTest(case=case,client_argument=location),self.assertRaises(ValueError):
                        RFC.verify_case_invocation('local',case,wrong,server,local_roles,directory,binaries)
                for location in range(len(server)):
                    wrong=list(server);wrong[location]='incorrect'
                    with self.subTest(case=case,server_argument=location),self.assertRaises(ValueError):
                        RFC.verify_case_invocation('local',case,client,wrong,local_roles,directory,binaries)
            vn_roles=dict(roles,packets=['fixtures/request.bin','fixtures/response.bin'],keylogs=[])
            server=[str(binaries['server'].resolve()),str(workspace/'server.pk8'),
                    str(workspace/'root.der'),str(workspace/'keys'),str(workspace/'www'),
                    'transfer',str(workspace/'server.der'),'--port=44300']
            RFC.verify_case_invocation('vn','reserved-version',None,server,vn_roles,directory,binaries)
            for location in range(len(server)):
                wrong=list(server);wrong[location]='incorrect'
                with self.subTest(vn_argument=location),self.assertRaises(ValueError):
                    RFC.verify_case_invocation('vn','reserved-version',None,wrong,vn_roles,directory,binaries)


    def test_pre_shutdown_state_rejects_unexpected_exit_and_inconsistent_ownership(self):
        for prior,requested,status in ((None,True,-15),(0,False,0)):
            row=dict(status_before_shutdown=prior,owned_termination_requested=requested,status=status)
            RFC.verify_server_shutdown_state(row)
        for changes in ({'status_before_shutdown':-11,'owned_termination_requested':False,'status':-11},
                        {'status_before_shutdown':7,'owned_termination_requested':False,'status':7},
                        {'status_before_shutdown':0.0,'owned_termination_requested':False,'status':0},
                        {'status_before_shutdown':False,'owned_termination_requested':False,'status':0},
                        {'status_before_shutdown':None,'owned_termination_requested':False,'status':0},
                        {'status_before_shutdown':0,'owned_termination_requested':True,'status':0},
                        {'status_before_shutdown':0,'owned_termination_requested':False,'status':-11},
                        {'status_before_shutdown':None,'owned_termination_requested':1,'status':-15},
                        {'status_before_shutdown':None,'owned_termination_requested':True,'status':-15.0}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                RFC.verify_server_shutdown_state(changes)
        for name in ('status_before_shutdown','owned_termination_requested','status'):
            row=dict(status_before_shutdown=None,owned_termination_requested=True,status=-15)
            row.pop(name)
            with self.subTest(missing=name),self.assertRaises(ValueError):
                RFC.verify_server_shutdown_state(row)


    def test_lifecycle_receipts_bind_owned_termination_and_exact_final_status(self):
        pid=123
        def posix_receipt(signal=15):
            return dict(pid=pid,pgid=pid,attempted=True,signal=signal,
                        grace_seconds=5,wait_timed_out=False,result='sent')
        def endpoint(strategy='posix-sigterm'):
            return dict(pid=pid,status_before_shutdown=None,owned_termination_requested=True,status=-15,
                lifecycle=dict(healthy_before_shutdown=True,cleanup_complete=True,passed=True,
                    termination_strategy=strategy,expected_final_status=-15,escalated=False,
                    cleanup_errors=[],receipt=posix_receipt()))
        with patch.object(RFC,'windows_host',return_value=False):
            row=endpoint()
            self.assertEqual(RFC.verify_server_lifecycle(row,lambda row,stream:stream),[])
            already=endpoint()
            already.update(status_before_shutdown=0,owned_termination_requested=False,status=0)
            already['lifecycle'].update(termination_strategy='already-exited',
                                        expected_final_status=0,receipt={})
            self.assertEqual(RFC.verify_server_lifecycle(already,lambda row,stream:stream),[])
            escalated=endpoint('posix-sigkill-after-grace')
            escalated['status']=-9
            previous=posix_receipt();previous['wait_timed_out']=True
            receipt=posix_receipt(9);receipt['previous']=previous
            escalated['lifecycle'].update(expected_final_status=-9,escalated=True,receipt=receipt)
            self.assertEqual(RFC.verify_server_lifecycle(escalated,lambda row,stream:stream),[])
            mutations=[
                ('prior crash',lambda r:r.update(status_before_shutdown=-11,owned_termination_requested=False)),
                ('final status',lambda r:r.update(status=0)),
                ('expected status',lambda r:r['lifecycle'].update(expected_final_status=0)),
                ('expected bool',lambda r:r['lifecycle'].update(expected_final_status=True)),
                ('passed flag',lambda r:r['lifecycle'].update(passed=False)),
                ('health flag',lambda r:r['lifecycle'].update(healthy_before_shutdown=False)),
                ('cleanup flag',lambda r:r['lifecycle'].update(cleanup_complete=False)),
                ('cleanup error',lambda r:r['lifecycle'].update(cleanup_errors=[{'exception':'Failure'}])),
                ('unknown action',lambda r:r['lifecycle'].update(termination_strategy='any-zero-or-signal')),
                ('unproved escalation',lambda r:r['lifecycle'].update(escalated=True)),
                ('wrong process',lambda r:r['lifecycle']['receipt'].update(pid=124)),
                ('wrong group',lambda r:r['lifecycle']['receipt'].update(pgid=124)),
                ('wrong signal',lambda r:r['lifecycle']['receipt'].update(signal=9)),
                ('signal bool',lambda r:r['lifecycle']['receipt'].update(signal=True)),
                ('missing action',lambda r:r['lifecycle']['receipt'].update(attempted=False)),
                ('wrong grace',lambda r:r['lifecycle']['receipt'].update(grace_seconds=6)),
                ('grace float',lambda r:r['lifecycle']['receipt'].update(grace_seconds=5.0)),
                ('unsent action',lambda r:r['lifecycle']['receipt'].update(result='pending')),
                ('unexplained timeout',lambda r:r['lifecycle']['receipt'].update(wait_timed_out=True)),
                ('unexpected previous',lambda r:r['lifecycle']['receipt'].update(previous=posix_receipt())),
            ]
            for name,mutate in mutations:
                wrong=endpoint();mutate(wrong)
                with self.subTest(mutation=name),self.assertRaises(ValueError):
                    RFC.verify_server_lifecycle(wrong,lambda row,stream:stream)
            for name in ('healthy_before_shutdown','cleanup_complete','passed','termination_strategy',
                         'expected_final_status','escalated','cleanup_errors','receipt'):
                wrong=endpoint();wrong['lifecycle'].pop(name)
                with self.subTest(missing=name),self.assertRaises(ValueError):
                    RFC.verify_server_lifecycle(wrong,lambda row,stream:stream)
            for name,mutate in (
                    ('missing grace timeout',lambda r:r['lifecycle']['receipt']['previous'].update(wait_timed_out=False)),
                    ('wrong first signal',lambda r:r['lifecycle']['receipt']['previous'].update(signal=9)),
                    ('different first pid',lambda r:r['lifecycle']['receipt']['previous'].update(pid=124))):
                wrong=copy.deepcopy(escalated);mutate(wrong)
                with self.subTest(escalation=name),self.assertRaises(ValueError):
                    RFC.verify_server_lifecycle(wrong,lambda row,stream:stream)
        with patch.object(RFC,'windows_host',return_value=True):
            row=endpoint('windows-taskkill-tree');row['status']=1
            receipt=dict(pid=pid,native_pid=456,pid_source='proc-winpid',python_os_name='posix',
                         argv=['taskkill.exe','-F','-T','-PID','456'],timeout_seconds=10,
                         attempted=True,status=0)
            row['lifecycle'].update(expected_final_status=1,receipt=receipt)
            self.assertEqual(RFC.verify_server_lifecycle(row,lambda row,stream:'termination.'+stream),
                             ['termination.stdout','termination.stderr'])
            for name,mutate in (
                    ('wrong process',lambda r:r['lifecycle']['receipt'].update(pid=124)),
                    ('zero native pid',lambda r:r['lifecycle']['receipt'].update(native_pid=0)),
                    ('native pid bool',lambda r:r['lifecycle']['receipt'].update(native_pid=True)),
                    ('wrong action',lambda r:r['lifecycle']['receipt'].update(argv=['taskkill.exe','-F','-PID','456'])),
                    ('wrong status',lambda r:r['lifecycle']['receipt'].update(status=1)),
                    ('status bool',lambda r:r['lifecycle']['receipt'].update(status=False)),
                    ('wrong pid source',lambda r:r['lifecycle']['receipt'].update(pid_source='popen')),
                    ('wrong timeout',lambda r:r['lifecycle']['receipt'].update(timeout_seconds=11)),
                    ('missing action',lambda r:r['lifecycle']['receipt'].update(attempted=False)),
                    ('generic exit',lambda r:r.update(status=-11)),
                    ('inferred escalation',lambda r:r['lifecycle'].update(escalated=True))):
                wrong=copy.deepcopy(row);mutate(wrong)
                with self.subTest(native_action=name),self.assertRaises(ValueError):
                    RFC.verify_server_lifecycle(wrong,lambda row,stream:stream)
            with self.assertRaises(ValueError):
                RFC.verify_server_lifecycle(row,lambda row,stream:(_ for _ in ()).throw(ValueError('raw missing')))


if __name__ == '__main__':
    unittest.main()
