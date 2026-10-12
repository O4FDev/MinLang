#!/usr/bin/env python3
"""Link accepted-unwind bookkeeping; reject has no hook, leaves follow hooks."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import runpy
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
from cycle_runtime import engine_source
from sanitizer_llvm import prepare_llvm_for_link
from clang_helpers import asan_leak_options


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sanitize', action='store_true')
    p.add_argument('--evidence', type=Path, default=ROOT / 'build/calldepth-hook-evidence')
    args = p.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    commands = []
    clang = shlex.split(os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    flags = ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if args.sanitize else []
    env = dict(os.environ)
    if args.sanitize:
        env.update(ASAN_OPTIONS=asan_leak_options() + ':detect_stack_use_after_return=1:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1')
    def run(argv, expected=''):
        tool = Path(shutil.which(str(argv[0])) or argv[0]).resolve()
        result = subprocess.run(list(map(str, argv)), capture_output=True, text=True, env=env, timeout=180)
        commands.append(dict(argv=list(map(str, argv)), status=result.returncode, stdout=result.stdout,
                             stderr=result.stderr, executable_sha256=hashlib.sha256(tool.read_bytes()).hexdigest()))
        (args.evidence / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        assert result.returncode == 0 and result.stdout == expected and not result.stderr, commands[-1]
    errors = runpy.run_path(str(ROOT / 'compiler/build-errors-compiler.py'))['assemble']()
    builder = runpy.run_path(str(ROOT / 'compiler/build-calldepth-compiler.py'))
    assert builder['adapt'](errors) == builder['adapt'](errors, unwind_hook=None)
    source = builder['adapt'](errors, unwind_hook='hookJoin(output, globals, caller)\nhookConstants(output, globals, caller)')
    source = builder['replace'](source, '    output.add("declare i32 @minyar_recovery_enter()\\n")\n',
        '    output.add("declare void @minyar_depthtest_hook_join()\\n")\n'
        '    output.add("declare void @minyar_depthtest_hook_constants()\\n")\n'
        '    output.add("declare i32 @minyar_recovery_enter()\\n")\n')
    position = source.index('\nfunction main(')
    helpers = '''
function hookJoin(output: List<Text>, globals: List<Text>, caller: Text) {
    if caller == "minyar_module_0_hookTarget" { output.add("  call void @minyar_depthtest_hook_join()\\n") }
}
function hookConstants(output: List<Text>, globals: List<Text>, caller: Text) {
    if caller == "minyar_module_0_hookTarget" { output.add("  call void @minyar_depthtest_hook_constants()\\n") }
}
'''
    frontend = args.evidence / 'compiler.min'
    frontend.write_text(source[:position] + helpers + source[position:])
    frontend_ir = frontend.with_suffix('.ll')
    compiler = args.evidence / 'compiler'
    run([ROOT / 'build/minyarc', frontend, frontend_ir])
    run(clang + ['-O2', '-Wno-override-module', frontend_ir, ROOT / 'build/minyar-compiler-runtime.ll', '-lm', '-o', compiler])
    program = args.evidence / 'hooks.min'
    program.write_text('''use "calldepth" as depth
use "errors" as errors
function deep(): Integer { return deep() }
function hookTarget(): Integer { let bytes = Bytes(8); return deep() }
function events(): Integer { native "depthtest" }
let accepted = depth.run(3, function(): Integer { return hookTarget() })
print(errors.integerOk(accepted))
let rejected = depth.run(1, function(): Integer { return hookTarget() })
print(errors.integerOk(rejected))
print(events())
let zero = depth.run(1, function(): Integer { return 0 })
print(errors.integerValue(zero))
''')
    harness = args.evidence / 'runtime.c'
    harness.write_text((ROOT / 'tests/memory-contracts-runtime.c').read_text().replace(
        '#include "../runtime/minyar_runtime.c"', engine_source(ROOT) + '\n#include "minyar_stack_frames.h"\n') + '''
static int hook_events;
void minyar_depthtest_hook_join(void) {
    assert(hook_events == 0 && rc_frames && minyar_call_depth > 0 && minyar_recovery_pending());
    hook_events = 1;
}
void minyar_depthtest_hook_constants(void) {
    assert(hook_events == 1 && rc_frames && minyar_call_depth > 0 && minyar_recovery_pending());
    hook_events = 2;
}
long long minyar_depthtest_events(void) { assert(hook_events == 2); return hook_events; }
__attribute__((destructor)) static void hook_exit(void) {
    assert(hook_events == 2 && !minyar_call_depth && !minyar_depth_scope && !minyar_depth_reporting);
}
''')
    for mode in ('O0', 'O2'):
        llvm = args.evidence / ('hooks.' + mode + '.ll')
        run([compiler, program, llvm, '--library', ROOT / 'library', '--bounded-owners', '32'])
        emitted = llvm.read_text()
        target = emitted[emitted.index('define i64 @.minyar.fn.minyar_module_0_hookTarget'):]
        target = target[:target.index('\n}\n')]
        rejected = target[target.index('recovery.reject:'):target.index('recovery.body:')]
        assert 'hook_' not in rejected and 'leave' not in rejected
        unwind = target[target.index('recovery.unwind:'):]
        assert unwind.index('hook_join') < unwind.index('hook_constants') < unwind.index('minyar_rc_leave') < unwind.index('minyar_stack_leave')
        prepare_llvm_for_link(llvm, flags)
        runtime = args.evidence / ('runtime.' + mode + '.o')
        run(clang + ['-' + mode] + flags + ['-DMINYAR_SYSTEM_HEAP=1', '-iquote', ROOT / 'runtime', '-c', harness, '-o', runtime])
        executable = llvm.with_suffix('.bin')
        run(clang + ['-' + mode] + flags + ['-Wno-override-module', llvm, runtime, '-lm', '-o', executable])
        run([executable], 'false\nfalse\n2\n0\n')
    manifest = {'status': 'passed', 'scope': 'Linked generic hook ordering, not WS1 managed-thread certification',
                'files': {str(p.relative_to(args.evidence)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in args.evidence.rglob('*') if p.is_file()},
                'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for directory in ('runtime', 'compiler', 'library') for p in (ROOT / directory).rglob('*')
                           if p.is_file() and '__pycache__' not in p.parts and not p.name.startswith('._')}}
    (args.evidence / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('accepted unwind hooks linked; rejected entry has no bookkeeping')


if __name__ == '__main__': main()
