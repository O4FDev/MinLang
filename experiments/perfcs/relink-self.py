#!/usr/bin/env python3
"""Prepare a runtime-only self-compiler screen from frozen generated LLVM.

Run on bx perfcs. The hardware phase is separate and uses the existing frozen
instruction runner. No compiler regeneration, new input paths or Make process.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen', type=Path, default=ROOT / 'build/perfcs-final-self')
    parser.add_argument('--baseline-runtime', type=Path, default=ROOT / 'runtime')
    parser.add_argument('--candidate-runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == 'Linux' and platform.machine() == 'x86_64', 'bx perfcs only'
    args.frozen = args.frozen.resolve()
    args.baseline_runtime = args.baseline_runtime.resolve()
    args.candidate_runtime = args.candidate_runtime.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    compiler = subprocess.check_output(['sh', str(ROOT / 'tools/toolchain.sh'), 'default-clang'], cwd=ROOT, text=True).strip()
    compiler = str(Path(shutil.which(compiler) or compiler).resolve())
    environment = dict(os.environ, LLVM_CC=compiler, LLVM_FLAGS='-O2 -Wno-override-module',
                       COMPILER_LTO_CACHE_DIR='build/thinlto-cache', COMPILER_LTO_CACHE_POLICY='cache_size=10%')
    lto = shlex.split(subprocess.check_output(['sh', str(ROOT / 'tools/toolchain.sh'), 'compiler-lto-flags'], cwd=ROOT, env=environment, text=True))
    flags = ['-O2', '-Wno-override-module']
    manifest = {'status': 'building', 'clang': compiler, 'clang_sha256': digest(compiler),
                'flags': flags, 'lto': lto, 'commands': [], 'frozen': str(args.frozen),
                'input': str(args.frozen / 'compiler.min'), 'library': str(args.frozen / 'library'),
                'input_sha256': digest(args.frozen / 'compiler.min'),
                'profiles': {}, 'runtime_profiles': {}, 'script_sha256': digest(__file__),
                'toolchain_environment': {name: environment[name] for name in
                    ['LLVM_CC', 'LLVM_FLAGS', 'COMPILER_LTO_CACHE_DIR', 'COMPILER_LTO_CACHE_POLICY']},
                'runtime_accounting_enabled': False,
                'method': 'same frozen generated LLVM; separate runtime LLVM; selected compiler ThinLTO flags'}
    journal = out / 'manifest.json'

    def save():
        journal.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')

    def command(argv, stem):
        row = {'argv': list(map(str, argv)), 'cwd': str(ROOT)}
        manifest['commands'].append(row)
        save()
        with (out / (stem + '.stdout')).open('wb') as stdout, (out / (stem + '.stderr')).open('wb') as stderr:
            result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=600)
        row['exit'] = result.returncode
        save()
        assert result.returncode == 0, row

    save()
    try:
        shutil.copy2(__file__, out / 'relink-self.py')
        shutil.copy2(ROOT / 'experiments/memory/frames-instructions.py', out / 'frames-instructions.py')
        shutil.copy2(args.frozen / 'compiler-stage2.ll', out / 'compiler-stage2.ll')
        for profile in ['default', 'eager']:
            shutil.copy2(args.frozen / (profile + '.ll'), out / (profile + '.ll'))
        for role, runtime in [('baseline', args.baseline_runtime), ('candidate', args.candidate_runtime)]:
            tree = out / (role + '-runtime')
            shutil.copytree(runtime, tree)
            for profile in ['default', 'eager']:
                stem = role + '-' + profile
                wrapper = out / (stem + '.c')
                prefix = '#define MINYAR_SYSTEM_HEAP 1\n' if profile == 'default' else ''
                wrapper.write_text(prefix + '#include "' + str(tree.resolve() / 'minyar_runtime.c') + '"\n#include "' + str(tree.resolve() / 'minyar_stack_frames.h') + '"\n')
                raw = out / (stem + '.raw.ll')
                llvm = out / (stem + '.runtime.ll')
                binary = out / stem
                command([compiler, *flags, '-S', '-emit-llvm', wrapper, '-o', raw], stem + '-emit')
                llvm.write_text(re.sub(r'"(?:target-cpu|target-features|tune-cpu)"="[^\"]*" ?', '', raw.read_text()))
                command([compiler, *flags, *lto, out / (profile + '.ll'), llvm, '-lm', '-o', binary], stem + '-link')
                manifest['profiles'][stem] = str(binary)
                manifest['runtime_profiles'][stem] = {'wrapper_prefix': prefix,
                    'accounting_enabled': False, 'emit_flags': flags,
                    'link_flags': [*flags, *lto], 'runtime_tree': str(tree),
                    'wrapper_sha256': digest(wrapper), 'frozen_llvm_sha256': digest(out / (profile + '.ll'))}
        manifest['immutable_files'] = {str(path): digest(path) for path in sorted(out.rglob('*'))
            if path.is_file() and path != journal}
        manifest['status'] = 'ready'
        save()
    except BaseException as error:
        manifest.update(status='failed', error=repr(error))
        save()
        raise
    print('RELINK_SELF_READY', journal, flush=True)
    print(' '.join(shlex.quote(word) for word in ['sudo', '-n', 'python3', str(out / 'frames-instructions.py'),
        '--directory', str(out), '--input', str(args.frozen / 'compiler.min'), '--library', str(args.frozen / 'library'),
        '--samples', '3', *[part for name, binary in manifest['profiles'].items() for part in ['--profile', name + '=' + binary]]]), flush=True)


if __name__ == '__main__':
    main()
