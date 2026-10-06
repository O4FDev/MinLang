#!/usr/bin/env python3
"""Only new caller-lifetime native/generated controls; no broad integration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import tempfile
from clang_helpers import clang_command
from llvm_sanitizer import prepare_llvm_for_link

ROOT=Path(__file__).resolve().parents[1]


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['baseline','final'],default='baseline')
    parser.add_argument('--runtime-dir',type=Path,default=ROOT/'runtime')
    args=parser.parse_args()
    parent=ROOT/'build/memory-research-list-bulk-caller';parent.mkdir(parents=True,exist_ok=True)
    evidence=Path(tempfile.mkdtemp(prefix='run-',dir=parent))
    report={'status':'running','phase':args.phase,'checks':[],'sources':[],'scope':'Six native owner/length shapes per3configurations and one original language source per5configurations; no timing/wholecompiler claim'}
    original={str(p):digest(p) for p in args.runtime_dir.glob('minyar_*') if p.is_file()}
    shutil.copytree(args.runtime_dir,evidence/'runtime',ignore=shutil.ignore_patterns('native'))
    (evidence/'tests').mkdir()
    for name in ['memory-research-list-bulk-caller.c','memory-research-list-bulk-caller.min',Path(__file__).name,'clang_helpers.py','llvm_sanitizer.py']:
        shutil.copyfile(ROOT/'tests'/name,evidence/'tests'/name)
    shutil.copyfile(ROOT/'research/2026-10-memory/runtime-list-bulk-caller-oracle.json',evidence/'oracle.json')
    oracle=json.loads((evidence/'oracle.json').read_text())
    compiler=evidence/'minyarc';shutil.copyfile(ROOT/'build/minyarc',compiler);compiler.chmod(0o755)
    report['compiler_artifact_sha256']=digest(compiler)
    environment={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}

    def save(): (evidence/'results.json').write_text(json.dumps(report,indent=2)+'\n')

    def limits():
        os.setsid();resource.setrlimit(resource.RLIMIT_CPU,(30,30));resource.setrlimit(resource.RLIMIT_FSIZE,(32*1024*1024,32*1024*1024))

    def execute(label,command,expected=None,native=False):
        wrapped=['/usr/bin/time','-l','/usr/sbin/taskpolicy','-m','128',*command] if native else command
        p=subprocess.Popen(wrapped,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment,preexec_fn=limits)
        timeout=False
        try:out,err=p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate()
        row={'label':label,'command':wrapped,'returncode':p.returncode,'stdout':out,'stderr':err,'timed_out':timeout,
             'effective_last_optimization':next((a for a in reversed(command) if re.fullmatch(r'-O(?:[0123szg]|fast)',a)),None)}
        report['checks'].append(row);save();assert not timeout and p.returncode==0,row
        if native:
            match=re.search(r'(\d+)\s+maximum resident set size',err);assert match,row
            row['peak_rss_bytes']=int(match.group(1));assert row['peak_rss_bytes']<=128*1024*1024,row
        if expected is not None:assert out==expected,row
        save();return row

    try:
        execute('toolchain',['clang','--version'])
        llvm=evidence/'generated.ll'
        execute('language-compile',[str(compiler),str(evidence/'tests/memory-research-list-bulk-caller.min'),str(llvm)])
        report['generated_llvm_sha256']=digest(llvm)
        configurations=[('system-o0',32,['-DMINYAR_SYSTEM_HEAP=1'],['-O0']),
                        ('system-o2',32,['-DMINYAR_SYSTEM_HEAP=1'],['-O2']),
                        ('fixed-o0',1,['-DMINYAR_BOUNDED_HEAP=1','-DMINYAR_BOUNDED_HEAP_BYTES=2097152'],['-O0']),
                        ('fixed-o2',1,['-DMINYAR_BOUNDED_HEAP=1','-DMINYAR_BOUNDED_HEAP_BYTES=2097152'],['-O2']),
                        ('system-sanitize',32,['-DMINYAR_SYSTEM_HEAP=1'],['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'])]
        wrapper=evidence/'runtime-wrapper.c'
        wrapper.write_text('#include "runtime/minyar_runtime.c"\n#include "runtime/minyar_stack_frames.h"\n')
        for label,budget,defines,flags in configurations:
            linked=evidence/(label+'.ll');shutil.copyfile(llvm,linked);prepare_llvm_for_link(linked,flags)
            headers=re.findall(r'^define[^\n]*',linked.read_text(),re.M)
            annotated=sum(' sanitize_address ' in h for h in headers)
            if 'sanitize' in label:assert annotated==len(headers) and headers
            report.setdefault('generated_modes',[]).append({'label':label,'definitions':len(headers),'asan_definitions':annotated,'llvm_sha256':digest(linked),'native_runtime_ubsan':'sanitize' in label,'generated_ubsan':False})
            binary=evidence/label
            execute('link-'+label,clang_command(['clang',*flags,*defines,f'-DMINYAR_RC_POLL_BUDGET={budget}',
                '-Wno-override-module',str(linked),str(wrapper),'-o',str(binary)]))
            row=execute(label,[str(binary)],oracle['language_expected_stdout'],True)
            if label=='system-o2':
                corrupted='21\n'+row['stdout'].split('\n',1)[1]
                assert corrupted!=oracle['language_expected_stdout']
                report['output_only_oracle_calibration']={'actual_stdout_sha256':hashlib.sha256(row['stdout'].encode()).hexdigest(),
                    'corrupted_stdout':corrupted,'rejected':True,'scope':'Saved-output order corruption12->21 only; not source/runtime mutation or runtime defect'}
            if label in ['system-o2','fixed-o2','system-sanitize']:
                c_binary=evidence/(label+'-native')
                execute('compile-native-'+label,clang_command(['clang','-std=c11',*flags,*defines,f'-DMINYAR_RC_POLL_BUDGET={budget}',
                    '-Wall','-Wextra','-Werror',str(evidence/'tests/memory-research-list-bulk-caller.c'),'-o',str(c_binary)]))
                expected=''.join(f'mode={mode} length={length} stack={int(mode==2 and budget>1)} recovered\n'
                                 for mode in range(3) for length in [0,257])
                execute(label+'-native',[str(c_binary)],expected,True)
        assert len(report['generated_modes'])==5
        assert all(digest(Path(p))==value for p,value in original.items())
        assert digest(ROOT/'build/minyarc')==report['compiler_artifact_sha256']
        report.update(status='passed',runtime_entry_hashes=original)
        report['sources']=[{'path':str(p.relative_to(evidence)),'sha256':digest(p)} for p in evidence.rglob('*') if p.is_file() and (p.suffix in ['.c','.h','.min','.py','.ll'] or p.name=='oracle.json')]
    except BaseException as error:
        report.update(status='failed',failure=repr(error));raise
    finally:
        save();print('Results: '+str(evidence/'results.json'),flush=True)


if __name__=='__main__':main()
