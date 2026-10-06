#!/usr/bin/env python3
"""A five-contract FileCheck pilot with IR verification and native oracles.

This target requires opt and FileCheck: missing tools are failures, not skips.
Set MINYAR_LLVM_BIN for a versioned LLVM installation outside PATH.
"""
import json
import os
from pathlib import Path
import shutil

from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    directory = os.environ.get('MINYAR_LLVM_BIN')
    candidate = str(Path(directory) / name) if directory else name
    found = shutil.which(candidate)
    if not found:
        raise RuntimeError(f'Required LLVM tool {name} unavailable; set MINYAR_LLVM_BIN')
    return found


def main():
    compiler = Path(os.environ.get('MINYAR_TEST_COMPILER', ROOT / 'build/minyarc')).resolve()
    clang = os.environ.get('MINYAR_TEST_CLANG', 'clang')
    opt, check = tool('opt'), tool('FileCheck')
    sources = sorted((ROOT / 'tests/codegen').glob('*.min'))
    assert len(sources) == 5, 'Pilot fixture inventory changed; review coverage explicitly'
    with Evidence('codegen', inputs=(compiler, *sources), controls={'opt': opt, 'FileCheck': check}) as evidence:
        def run(command, phase, **kwargs):
            return evidence.run(command, phase=phase, timeout=60, **kwargs)
        versions = {name: run([binary, '--version'], 'capability', check=True).stdout.decode()
                    for name, binary in (('opt', opt), ('FileCheck', check), ('clang', clang))}
        runtime = evidence.path / 'runtime.o'
        run([clang, '-O2', '-c', ROOT / 'runtime/minyar_default_runtime.c', '-o', runtime], 'runtime-build', check=True)
        rows = []
        for source in sources:
            llvm = evidence.path / (source.stem + '.ll')
            run([compiler, source, llvm, '--bounded-owners', '32'], 'compile', check=True)
            run([opt, '-passes=verify', '-disable-output', llvm], 'verify', check=True)
            run([check, source, '--input-file=' + str(llvm)], 'filecheck', check=True)
            expected = evidence.reference_output(source.with_suffix('.stdout'))
            for optimization in ('-O0', '-O2'):
                executable = evidence.path / (source.stem + optimization)
                run([clang, optimization, '-Wno-override-module', llvm, runtime, '-o', executable], 'link', check=True)
                result = run([executable], 'execute')
                assert result.returncode == 0 and result.stdout == expected and not result.stderr, result
            rows.append({'case': source.stem, 'variants': ['O0', 'O2'], 'verified': True, 'checked': True,
                         'output_reference': evidence.controls['output_references'][-1]})

        # A removed required overflow guard must fail FileCheck, not bless the IR.
        source = ROOT / 'tests/codegen/checked-arithmetic.min'
        llvm = evidence.path / 'checked-arithmetic.ll'
        mutant = evidence.path / 'missing-guard.ll'
        text = llvm.read_text()
        lines = [line for line in text.splitlines() if 'call void @.minyar.integer.overflow.checked' not in line]
        assert len(lines) == len(text.splitlines()) - 1, 'Controlled mutation did not apply exactly once'
        mutant.write_text('\n'.join(lines) + '\n')
        rejected = run([check, source, '--input-file=' + str(mutant)], 'harness-negative-control')
        assert rejected.returncode != 0 and b'CHECK' in rejected.stderr, 'FileCheck accepted a removed required guard'

        invalid = evidence.path / 'dominance.ll'
        invalid.write_text('''define i32 @bad(i1 %condition) {
entry:
  br i1 %condition, label %left, label %right
left:
  %value = add i32 1, 2
  br label %right
right:
  ret i32 %value
}
''')
        rejected = run([opt, '-passes=verify', '-disable-output', invalid], 'verifier-negative-control')
        assert rejected.returncode != 0 and b'does not dominate' in rejected.stderr, 'Verifier did not reject invalid dominance'
        malformed = {
            'forward-definition': '''define i64 @forward(i64 %input) {
entry:
  %answer = add i64 %later, 3
  %later = add i64 %input, 5
  ret i64 %answer
}
''',
            'phi-target-definition': '''define i64 @loop(i1 %again) {
entry:
  br label %repeat
repeat:
  %current = phi i64 [ %next, %entry ], [ %next, %repeat ]
  %next = add i64 %current, 1
  br i1 %again, label %repeat, label %done
done:
  ret i64 %next
}
''',
            'phi-wrong-predecessor': '''define i64 @joined() {
entry:
  br label %merge
merge:
  %first = phi i64 [ 7, %entry ]
  %second = phi i64 [ %first, %entry ]
  ret i64 %second
}
''',
        }
        for name, text in malformed.items():
            invalid = evidence.path / (name + '.ll')
            invalid.write_text(text)
            rejected = run([opt, '-passes=verify', '-disable-output', invalid], 'verifier-negative-' + name)
            assert rejected.returncode != 0 and b'does not dominate' in rejected.stderr, (name, rejected)
        (ROOT / 'build/codegen-results.json').write_text(json.dumps({
            'status': 'passed', 'tools': versions, 'cases': rows,
            'negative_controls': ['missing-overflow-guard', 'branch-dominance', *malformed],
        }, indent=2) + '\n')
    print('Five LLVM contracts verified, FileChecked and executed at O0/O2; negative controls rejected')


if __name__ == '__main__':
    main()
