#!/usr/bin/env python3
"""Mandatory Linux kernel ABI and raw-child instrumentation compile controls.

Target layout proof is not native aarch64 execution. Instrumentation objects are
compiled for the native Linux target; no privileged or sanitizer execution occurs.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT/'tests/system-process-abi-reference'
CLANG = os.environ.get('MINYAR_TEST_CLANG', 'clang')

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checks', choices=('all', 'abi', 'instrumentation'), default='all')
    parser.add_argument('--evidence', type=Path)
    options = parser.parse_args()
    if options.checks != 'abi' and platform.system() != 'Linux':
        parser.error('native Linux child audits require a Linux host; target ABI controls use --checks abi')
    if options.evidence:
        directory = options.evidence.resolve(); directory.mkdir(parents=True, exist_ok=False)
        run_checks(directory, options.checks)
    else:
        with tempfile.TemporaryDirectory(prefix='system-process-boundary-') as directory:
            run_checks(Path(directory), options.checks)

def run_checks(directory, checks):
    records, failures = [], []
    header = ROOT/'runtime/native/system_process.h'
    sources = {str(header.relative_to(ROOT)): digest(header),
               'runtime/native/system.c': digest(ROOT/'runtime/native/system.c'),
               'tests/system-process-abi.c': digest(ROOT/'tests/system-process-abi.c'),
               'tests/system-process-boundary.py': digest(__file__)}
    references = json.loads((REFERENCE/'sources.json').read_text())
    for source in references:
        assert digest(REFERENCE/source['file']) == source['sha256'], source
        sources['tests/system-process-abi-reference/'+source['file']] = source['sha256']

    def command(args, name):
        args = list(map(str, args))
        result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        log = directory/(name+'.log'); log.write_bytes(result.stdout)
        records.append({'command': args, 'exit_code': result.returncode, 'log': log.name,
                        'log_sha256': hashlib.sha256(result.stdout).hexdigest()})
        return result

    def check(condition, name, detail=''):
        if not condition: failures.append({'check': name, 'detail': detail})
        print(name+(': passed' if condition else ': FAILED'), flush=True)

    command([CLANG, '--version'], 'clang-version')
    resource = subprocess.check_output([CLANG, '-print-resource-dir'], text=True).strip()
    compiler = Path(shutil.which(CLANG) or CLANG).resolve()
    if checks in ('abi', 'all'):
        declaration = re.search(r'typedef struct SystemKernelAction \{.*?\} SystemKernelAction;', header.read_text(), re.S)
        assert declaration, 'provider kernel action declaration missing'
        (directory/'system-action.h').write_text('#include <stdint.h>\n'+declaration.group(0)+'\n')
        generic = (REFERENCE/'linux-v6.8-generic-signal.h').read_text()
        kernel = (REFERENCE/'linux-v6.8-kernel-signal.h').read_text()
        sigset = re.search(r'typedef struct \{\s*unsigned long sig\[_NSIG_WORDS\];\s*\} sigset_t;', generic)
        action = re.search(r'struct sigaction \{.*?\n\};', kernel, re.S)
        assert sigset and action
        macros = '\n'.join(re.search(r'^#define '+name+r'\s+[^\n]+', generic, re.M).group(0)
                           for name in ('_NSIG', '_NSIG_BPW', '_NSIG_WORDS'))
        for target, reference in [('x86_64-linux-gnu', 'linux-v6.8-x86-signal.h'),
                                  ('aarch64-linux-gnu', 'linux-v6.8-arm64-signal.h')]:
            architecture = (REFERENCE/reference).read_text()
            restorer = re.search(r'^#define SA_RESTORER\s+[^\n]+', architecture, re.M)
            assert restorer, 'architecture UAPI must supply the restorer field'
            (directory/'kernel-action.h').write_text(
                '#define __BITS_PER_LONG (__SIZEOF_LONG__ * 8)\n'+macros+'\n'+restorer.group(0)+
                '\n#define __ARCH_HAS_SA_RESTORER\n'+
                'typedef void (*__sighandler_t)(int);\ntypedef void (*__sigrestore_t)(void);\n'+
                sigset.group(0)+'\n'+action.group(0)+'\n')
            shutil.copy2(directory/'kernel-action.h', directory/(target+'-kernel-action.h'))
            base = [CLANG, '--target='+target, '-std=c11', '-ffreestanding', '-nostdinc',
                    '-isystem', Path(resource)/'include', '-I', directory, '-Wall', '-Wextra', '-Werror']
            result = command([*base, '-fsyntax-only', ROOT/'tests/system-process-abi.c'], target+'-layout')
            check(result.returncode == 0, target+' kernel layout', result.stdout.decode(errors='replace'))

    if checks in ('instrumentation', 'all'):
        objdump = os.environ.get('MINYAR_TEST_OBJDUMP', 'objdump')
        extras = ['-fsanitize-coverage=trace-pc-guard', '-fprofile-instr-generate', '-fcoverage-mapping',
                  '-fstack-protector-all', '-finstrument-functions']
        for mode, sanitizer in [('native', []), ('asan-ubsan', ['-fsanitize=address,undefined']),
                                ('tsan', ['-fsanitize=thread'])]:
            for optimization in ('O0', 'O1', 'O2'):
                name = mode+'-'+optimization; output = directory/(name+'.o')
                result = command([CLANG, '-std=c11', '-Wall', '-Wextra', '-Werror', '-'+optimization,
                                  '-g', *sanitizer, *extras, '-c', ROOT/'runtime/native/system.c', '-o', output], name+'-build')
                check(result.returncode == 0, name+' compile', result.stdout.decode(errors='replace'))
                if result.returncode: continue
                assembly = command([objdump, '-dr', '--disassemble=system_clone_child', output], name+'-disassembly')
                raw = assembly.stdout
                check(assembly.returncode == 0 and b'<system_clone_child>:' in raw and
                      bool(re.search(rb'\b(syscall|svc)\b', raw)), name+' real child body')
                check(not re.search(rb'\b(callq?|bl|blr)\b', raw), name+' zero child calls')
                check(not re.search(rb'__tsan|__asan|__ubsan|__sanitizer|__cyg_profile|__stack_chk|__llvm_profile|@TPOFF|@TLS|%fs:|%gs:', raw),
                      name+' no instrumentation or TLS references')
                symbols = command([objdump, '-t', output], name+'-symbols').stdout
                if mode == 'tsan': check(b'__tsan_func_entry' in symbols, name+' TSan enabled outside child')
                if mode == 'asan-ubsan': check(b'__asan' in symbols, name+' ASan enabled outside child')
                records[-1]['object_sha256'] = digest(output)
        unsupported = command([CLANG, '-std=c11', '-Wno-builtin-macro-redefined', '-D__has_attribute(x)=0',
                               '-fsyntax-only', ROOT/'runtime/native/system.c'], 'unsupported-attributes')
        check(unsupported.returncode != 0 and b'requires complete child instrumentation exclusion' in unsupported.stdout,
              'unsupported exclusion capability fails closed', unsupported.stdout.decode(errors='replace'))

    receipt = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'checks': checks, 'host': platform.platform(), 'compiler': str(compiler),
               'compiler_sha256': digest(compiler), 'sources': sources, 'references': references,
               'commands': records, 'failures': failures, 'native_aarch64_execution': False}
    (directory/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'boundary controls: {len(failures)} failures', flush=True)
    if failures: raise SystemExit(1)

if __name__ == '__main__': main()
