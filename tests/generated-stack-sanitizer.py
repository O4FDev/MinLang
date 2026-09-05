#!/usr/bin/env python3
"""Check that generated LLVM stack instrumentation detects an escaped alloca."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from llvm_sanitizer import instrument_address_sanitizer, address_sanitizer_enabled

CONTROL = '''define ptr @escaped() noinline {
entry:
  %slot = alloca i64, align 8
  store volatile i64 7, ptr %slot
  ret ptr %slot
}
define i32 @main() {
entry:
  %p = call ptr @escaped()
  %read = load volatile i64, ptr %p
  ret i32 0
}
'''
VALID = '''define i32 @main() {
entry:
  %slot = alloca i64, align 8
  store volatile i64 7, ptr %slot
  %read = load volatile i64, ptr %slot
  ret i32 0
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix='minyar-generated-asan-', dir=args.output_dir))
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_stack_use_after_return=1:detect_leaks=0:abort_on_error=1'}
    report = {'status': 'running', 'checks': []}
    assert not address_sanitizer_enabled([])
    assert address_sanitizer_enabled(['-fsanitize=address,undefined'])
    assert not address_sanitizer_enabled(['-fsanitize=address', '-fno-sanitize=all'])
    assert instrument_address_sanitizer(instrument_address_sanitizer(VALID)) == instrument_address_sanitizer(VALID)
    try:
        instrument_address_sanitizer('define i32 @main(\n) {\n ret i32 0\n}\n')
    except ValueError:
        pass
    else:
        raise AssertionError('changed header layout silently lost sanitizer coverage')
    try:
        for name, source in [('unmarked', CONTROL), ('marked', instrument_address_sanitizer(CONTROL)), ('marked-named', instrument_address_sanitizer(CONTROL.replace('@escaped', '@sanitize_address'))), ('valid', instrument_address_sanitizer(VALID))]:
            ir = evidence / (name + '.ll')
            ir.write_text(source)
            for optimization in ('-O0', '-O2'):
                binary = evidence / (name + optimization)
                command = [args.clang, optimization, '-fsanitize=address', '-Wno-override-module', str(ir), '-o', str(binary)]
                built = subprocess.run(command, capture_output=True, text=True, timeout=60)
                (evidence / (binary.name + '-compile.log')).write_text(built.stdout + built.stderr)
                assert built.returncode == 0, built.stderr
                checked = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30, env=env)
                (evidence / (binary.name + '.log')).write_text(checked.stdout + checked.stderr)
                report['checks'].append({'name': name, 'optimization': optimization, 'command': command, 'returncode': checked.returncode})
                if name.startswith('marked'):
                    assert checked.returncode != 0 and 'stack-use-after-return' in checked.stderr, checked.stderr
                else:
                    assert checked.returncode == 0, checked.stderr
        report['status'] = 'passed'
    finally:
        (evidence / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(evidence)


if __name__ == '__main__':
    main()
