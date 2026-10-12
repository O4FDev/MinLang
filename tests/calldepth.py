#!/usr/bin/env python3
"""Cooperative G14 recovery with exact RC accounting and retained commands."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import engine_source
from sanitizer_llvm import prepare_llvm_for_link
sys.path.insert(0, str(ROOT / 'tests'))
from clang_helpers import asan_leak_options, windows_host

if not windows_host():
    import resource

EXPECTED = {
    'g14-recovered': 'false\ntrue\n1000\nalive\n',
    'limits': '-1\n0\n14\n14\n0\nfalse\n42\n-1\n',
    'nested': '7\n-1\n',
    'ownership': '0\nfresh text\n3\n',
    'control-flow': '42\nfalse\nfalse\n10\n',
    'native-reserve': 'false\n10\n',
    'results-imports': '12\nfalse\n',
    'native-callback': 'false\n42\n',
    'domain-rejection': 'domain checked before depth state\n',
    'reporting-exhausted': '17\n0\n-1\n',
    'large-dispatch': '1450\nfalse\n',
    'reporting-global': '14\n17\n0\n42\nalive\n',
    'reporting-fallback': '85\n14\n17\n42\nalive\n',
    'reporting-physical': '14\n42\nalive\n',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc-calldepth')
    parser.add_argument('--evidence', type=Path, default=ROOT / 'build/calldepth-evidence')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--profile', choices=['system', 'eager', 'fixed', 'lazy'], default='system')
    parser.add_argument('--budget', type=int, choices=(1, 32, 1024), default=32)
    parser.add_argument('--case', choices=list(EXPECTED), action='append')
    parser.add_argument('--small-stack', action='store_true')
    parser.add_argument('--large-dispatch', action='store_true')
    parser.add_argument('--lto', action='store_true', help='Include the Linux ThinLTO/lld gate.')
    parser.add_argument('--max-depth', type=int)
    parser.add_argument('--fallback-depth', type=int)
    args = parser.parse_args()
    if args.lto and platform.system() != 'Linux': parser.error('--lto requires Linux/lld')
    if args.small_stack and windows_host(): parser.error('--small-stack requires POSIX setrlimit')
    if args.profile == 'lazy' and windows_host(): parser.error('the lazy heap requires POSIX mmap')
    args.evidence.mkdir(parents=True, exist_ok=True)
    commands = []
    clang = shlex.split(os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    flags = ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else []
    env = dict(os.environ)
    if args.sanitize:
        env['ASAN_OPTIONS'] = asan_leak_options() + ':detect_stack_use_after_return=1:halt_on_error=1'
        env['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
    def run(command, expected=None, stack=False, status=0, stderr=''):
        def set_stack(): resource.setrlimit(resource.RLIMIT_STACK, (256 * 1024, 256 * 1024))
        result = subprocess.run(list(map(str, command)), capture_output=True, env=env,
            timeout=180, preexec_fn=set_stack if stack else None)
        executable = Path(shutil.which(str(command[0])) or command[0]).resolve()
        commands.append({'argv': list(map(str, command)), 'status': result.returncode,
            'executable': str(executable), 'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
            'stdout': result.stdout.decode(errors='replace'), 'stderr': result.stderr.decode(errors='replace'),
            'small_stack_bytes': 256 * 1024 if stack else None,
            'sanitizer_environment': {name: env[name] for name in ('ASAN_OPTIONS', 'UBSAN_OPTIONS') if name in env}})
        (args.evidence / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if result.returncode != status or (expected is not None and result.stdout != expected.encode()) or result.stderr != stderr.encode():
            raise AssertionError(json.dumps(commands[-1], indent=2))
        return result
    # Render the same graph engine used for callbacks, with the exact debt and
    # object ledger checked at process exit, including partial constructions.
    contract = (ROOT / 'tests/memory-contracts-runtime.c').read_text()
    harness = args.evidence / 'runtime.c'
    harness.write_text(contract.replace('#include "../runtime/minyar_runtime.c"',
        engine_source(ROOT) + '\n#include "minyar_stack_frames.h"\n') + '''
#ifdef __APPLE__
#define DEPTH_SYMBOL(name) "_" name
#else
#define DEPTH_SYMBOL(name) name
#endif
extern MinyarText *depth_test_language(void)
    __asm__(DEPTH_SYMBOL(".minyar.fn.minyar_module_0_deepNative")) __attribute__((weak));
MinyarText *minyar_depthtest_bounce(void) {
    assert(depth_test_language);
    MinyarText *value = depth_test_language();
    if (value) minyar_rc_release(value);
    return minyar_integer_text(42);
}
extern MinyarRecord *depth_test_run(long long, MinyarRecord *)
    __asm__(DEPTH_SYMBOL(".minyar.fn.minyar_module_1_run")) __attribute__((weak));
static MinyarDepthScope *depth_expected_scope;
static size_t depth_expected_count;
static void depth_domain_exit(void) {
    assert(minyar_depth_scope == depth_expected_scope);
    assert(minyar_call_depth == depth_expected_count);
    assert(minyar_depth_reporting == 0);
    puts("domain checked before depth state");
}
long long minyar_depthtest_foreign(void) {
    assert(depth_test_run);
    struct { long long length; long long fields[3]; } storage =
        { 3, { 0, 0, minyar_callback_domain() + 1 } };
    MinyarRecord *callback = (MinyarRecord *)&storage;
    depth_expected_scope = minyar_depth_scope;
    depth_expected_count = minyar_call_depth;
    assert(atexit(depth_domain_exit) == 0);
    (void)depth_test_run(0, callback);
    abort();
}
__attribute__((destructor)) static void depth_exit_contract(void) {
    if (contract_explicit_exit) return;
    assert(minyar_call_depth == 0);
    assert(minyar_depth_scope == NULL);
    assert(minyar_depth_reporting == 0);
}
''' + (ROOT / 'tests/calldepth-reporting-native.c').read_text())
    policy = []
    if args.profile == 'system': policy = ['-DMINYAR_SYSTEM_HEAP=1']
    if args.profile in ('fixed', 'lazy'):
        policy = ['-DMINYAR_BOUNDED_HEAP=1', '-DMINYAR_BOUNDED_HEAP_BYTES=16777216']
    if args.profile == 'lazy': policy += ['-DMINYAR_LAZY_HEAP=1']
    policy += ['-DMINYAR_RC_POLL_BUDGET=' + str(args.budget)]
    if args.max_depth is not None: policy += ['-DMINYAR_MAX_CALL_DEPTH=' + str(args.max_depth)]
    if args.fallback_depth is not None: policy += ['-DMINYAR_FALLBACK_CALL_DEPTH=' + str(args.fallback_depth)]
    for fixture in ('calldepth-runtime', 'calldepth-thread-local'):
        if fixture.endswith('thread-local') and windows_host():
            print('pthread scope isolation requires a POSIX host', flush=True)
            continue
        executable = args.evidence / fixture
        definitions = ['-DMINYAR_SYSTEM_HEAP=1', '-DMINYAR_FALLBACK_CALL_DEPTH=16']
        if fixture.endswith('thread-local'): definitions += ['-DMINYAR_THREADED=1']
        run(clang + ['-O2'] + flags + definitions + [ROOT / 'tests' / (fixture + '.c'),
            '-lm'] + ([] if windows_host() else ['-pthread']) + ['-o', executable])
        run([executable], '')
    for name, definitions, controls in (
            ('global', ['-DMINYAR_MAX_CALL_DEPTH=2'], ('global', 'bounded', 'physical', 'escape')),
            ('fallback', ['-DMINYAR_MAX_CALL_DEPTH=1000', '-DMINYAR_FALLBACK_CALL_DEPTH=16'], ('fallback',))):
        executable = args.evidence / ('reporting-controls-' + name)
        run(clang + ['-O2'] + flags + ['-DMINYAR_SYSTEM_HEAP=1'] + definitions +
            [ROOT / 'tests/calldepth-reporting.c', '-lm'] +
            ([] if windows_host() else ['-pthread']) + ['-o', executable])
        for control in controls:
            run([executable, control], 'escaped pending status 2\n' if control == 'escape' else
                'nested failure; success; alive\n')
    modes = ['O0', 'O2'] + (['LTO'] if args.lto and not args.sanitize else [])
    cases = args.case or [case for case in EXPECTED if case not in ('large-dispatch', 'reporting-global', 'reporting-fallback')]
    libraries = ['--library', ROOT / 'library']
    if any(case.startswith('reporting-') and case != 'reporting-exhausted' for case in cases):
        # Test-only one-frame inspectors permit MAX=2 without changing the
        # actual factory bodies or asking the ordinary native ABI for records.
        overlay = args.evidence / 'library'
        overlay.mkdir(exist_ok=True)
        (overlay / 'calldepth.min').write_bytes((ROOT / 'library/calldepth.min').read_bytes())
        (overlay / 'errors.min').write_text((ROOT / 'library/errors.min').read_text() + '''
public function depthTestCode(result: IntegerResult): Integer { return result.error.code }
public function depthTestValue(result: IntegerResult): Integer { return result.value }
''')
        libraries = ['--library', overlay] + libraries
    if args.large_dispatch and 'large-dispatch' not in cases: cases += ['large-dispatch']
    generated_dispatch = None
    if 'large-dispatch' in cases:
        body = 'function dispatch(value: Integer): Integer {\n' + ''.join(
            f'if value == {i} {{ return {i} }} else {{\n' for i in range(1500)) + 'return 9999\n' + '}\n' * 1501
        control = args.evidence / 'dispatch-control.min'
        control.write_text(body + 'print(dispatch(1450))\n')
        control_ir = control.with_suffix('.ll')
        run([ROOT / 'build/minyarc', control, control_ir])
        assert 'dispatch.found:' in control_ir.read_text(), 'control did not exercise integer dispatch'
        generated_dispatch = args.evidence / 'large-dispatch.min'
        generated_dispatch.write_text('use "calldepth" as depth\nuse "errors" as errors\n' + body +
            'let good=depth.run(2, function(): Integer { return dispatch(1450) })\nprint(errors.integerValue(good))\n'
            'let failed=depth.run(1, function(): Integer { return dispatch(1450) })\nprint(errors.integerOk(failed))\n')
    for mode in modes:
        optimization = ['-O0'] if mode == 'O0' else ['-O2']
        if mode == 'LTO': optimization += ['-flto=thin', '-fuse-ld=lld']
        runtime = args.evidence / ('runtime.' + mode + ('.ll' if mode == 'LTO' else '.o'))
        run(clang + ['-O2'] + flags + policy + ['-iquote', ROOT / 'runtime',
            '-S', '-emit-llvm', harness, '-o', runtime] if mode == 'LTO' else
            clang + optimization + flags + policy + ['-iquote', ROOT / 'runtime', '-c', harness, '-o', runtime])
        for case in cases:
            source = generated_dispatch if case == 'large-dispatch' else ROOT / 'tests/calldepth' / (case + '.min')
            llvm = args.evidence / (case + '.' + mode + '.ll')
            run([args.compiler, source, llvm, *libraries, '--bounded-owners', str(args.budget)])
            assert '; minyar-calldepth-policy: cooperative-v1-full-program' in llvm.read_text()
            if case == 'large-dispatch': assert 'dispatch.found:' not in llvm.read_text()
            if args.sanitize: prepare_llvm_for_link(llvm, flags)
            executable = llvm.with_suffix('.bin')
            run(clang + optimization + flags + ['-Wno-override-module', llvm, runtime, '-lm', '-o', executable])
            run([executable], EXPECTED[case], stack=args.small_stack and case in ('native-reserve', 'reporting-physical'),
                status=1 if case == 'domain-rejection' else 0,
                stderr='Minyar stopped: callback belongs to a different execution domain.\n' if case == 'domain-rejection' else '')
            print(mode, case, 'passed', flush=True)
    files = {str(p.relative_to(args.evidence)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in args.evidence.rglob('*') if p.is_file()}
    inputs = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for directory in ('runtime', 'compiler', 'library', 'tests/calldepth') for p in (ROOT / directory).glob('*') if p.is_file()}
    for name in ('calldepth.py', 'calldepth-runtime.c', 'calldepth-thread-local.c',
                 'calldepth-reporting.c', 'calldepth-reporting-native.c', 'memory-contracts-runtime.c', 'clang_helpers.py'):
        p = ROOT / 'tests' / name
        inputs[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    inputs[str(args.compiler)] = hashlib.sha256(args.compiler.read_bytes()).hexdigest()
    (args.evidence / 'manifest.json').write_text(json.dumps({'status': 'passed', 'files': files,
        'inputs': inputs, 'configuration': vars(args)}, default=str, indent=2) + '\n')


if __name__ == '__main__': main()
