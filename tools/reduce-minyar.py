#!/usr/bin/env python3
"""Reduce a type-correct source while preserving a caller-supplied failure oracle.

The oracle is an argv list (no shell), with {source} and {llvm} placeholders.
Exit 0 means the same failure persists; nonzero means uninteresting. A timeout
or signal is inconclusive and aborts. This is for wrong-result/runtime failures,
not compiler-crash minimization. Relative imported .min files are snapshotted.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]


def reduce(args):
    source = args.source.resolve()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + '.json').exists():
        raise ValueError('Refusing to overwrite existing reduced source or report: ' + str(args.output))
    if not args.oracle or not any('{source}' in arg or '{llvm}' in arg for arg in args.oracle):
        raise ValueError('Oracle command must refer to {source} or {llvm}')
    # Existing file arguments are relative to the invocation directory, not
    # the isolated candidate workspace used to run the oracle.
    args.oracle = [str(Path(arg).resolve()) if Path(arg).is_file() else arg for arg in args.oracle]
    compiler = args.compiler.resolve()
    inputs = [Path(__file__).resolve(), compiler, source, *[Path(arg) for arg in args.oracle if Path(arg).is_file()]]
    with Evidence('reduction', inputs=inputs, controls={'oracle': args.oracle}) as evidence:
        # Freeze paths before copying: the evidence directory may itself live
        # below the source tree, so a live rglob would recursively copy output.
        snapshot_paths = tuple(path for path in source.parent.rglob('*.min')
                               if not path.is_relative_to(evidence.path))
        work = evidence.path / 'modules'
        work.mkdir()
        for original in snapshot_paths:
            if original.is_symlink():
                raise ValueError('Module snapshot does not follow symlinks: ' + str(original))
            destination = work / original.relative_to(source.parent)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
        candidate = work / source.name
        if args.output.name != source.name and (work / args.output.name).exists():
            raise ValueError('Output name collides with a snapshotted module: ' + args.output.name)
        llvm = evidence.path / 'candidate.ll'
        attempts = 0

        def interesting(lines):
            nonlocal attempts
            attempts += 1
            if attempts > args.max_attempts:
                raise RuntimeError('Reduction attempt budget exhausted; evidence retained')
            candidate.write_text(''.join(lines))
            llvm.unlink(missing_ok=True)
            compiled = evidence.run([compiler, candidate, llvm], timeout=args.timeout, phase='compile')
            if compiled.returncode == 1:
                return False
            if compiled.returncode != 0 or not llvm.is_file():
                raise RuntimeError('Compiler failed abnormally during reduction')
            command = [arg.replace('{source}', str(candidate)).replace('{llvm}', str(llvm)) for arg in args.oracle]
            result = evidence.run(command, cwd=work, timeout=args.timeout, phase='interestingness')
            if result.returncode < 0:
                raise RuntimeError('Oracle died from a signal; reduction is inconclusive')
            return result.returncode == 0

        original_lines = source.read_text().splitlines(keepends=True)
        if not interesting(original_lines):
            raise ValueError('Original source does not compile and reproduce the requested failure')
        current, partitions = original_lines, 2
        while current:
            width = max(1, (len(current) + partitions - 1) // partitions)
            changed = False
            for start in range(0, len(current), width):
                smaller = current[:start] + current[start + width:]
                if interesting(smaller):
                    current, partitions, changed = smaller, max(2, partitions - 1), True
                    break
            if not changed:
                if partitions >= len(current):
                    break
                partitions = min(len(current), partitions * 2)
        if not interesting(current):
            raise RuntimeError('Final reproducer is unstable')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Keep imported modules relative to the reduced entry. Never replace an
        # existing destination with different contents as a side effect.
        for original in work.rglob('*.min'):
            if original == candidate:
                continue
            destination = args.output.parent / original.relative_to(work)
            if destination.exists() and destination.read_bytes() != original.read_bytes():
                raise ValueError('Output would overwrite a different module: ' + str(destination))
        for original in work.rglob('*.min'):
            if original == candidate:
                continue
            destination = args.output.parent / original.relative_to(work)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copy2(original, destination)
        args.output.write_text(''.join(current))
        # Relocation and the output basename can affect imports or an oracle
        # that inspects its source path. Validate the actual deliverable too.
        final_llvm = evidence.path / 'final.ll'
        try:
            compiled = evidence.run([compiler, args.output.resolve(), final_llvm], timeout=args.timeout, phase='compile-final')
            if compiled.returncode != 0 or not final_llvm.is_file():
                raise RuntimeError('Relocated reduced source does not compile')
            command = [arg.replace('{source}', str(args.output.resolve())).replace('{llvm}', str(final_llvm))
                       for arg in args.oracle]
            reproduced = evidence.run(command, cwd=args.output.parent.resolve(), timeout=args.timeout, phase='interestingness-final')
            if reproduced.returncode != 0:
                raise RuntimeError('Relocated reduced source does not preserve the oracle')
        except BaseException:
            args.output.unlink(missing_ok=True)
            raise
        report = {'status': 'reduced', 'source': str(source), 'output': str(args.output.resolve()),
                  'original_lines': len(original_lines), 'reduced_lines': len(current),
                  'attempts': attempts, 'oracle': args.oracle,
                  'scope': 'Line deletion preserving compile success and the supplied oracle; not global minimality'}
        args.output.with_suffix(args.output.suffix + '.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--max-attempts', type=int, default=1000)
    parser.add_argument('--oracle', nargs=argparse.REMAINDER, required=True)
    args = parser.parse_args()
    if args.timeout <= 0 or args.max_attempts < 1:
        parser.error('timeout and attempt budget must be positive')
    reduce(args)
