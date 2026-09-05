#!/usr/bin/env python3
"""Benchmark module chains, wide imports, and shared dependencies.

Each fresh-process compilation includes startup and source-to-LLVM work,
excluding Clang and linking. Sources are generated and filesystem caches warmed
before measurement. All samples are retained; medians and adjacent-size scaling
ratios are reported. These cases use the ordinary compiler without a cache."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time
try:
    import resource
except ImportError:
    resource = None

ROOT = Path(__file__).resolve().parents[1]


def generate(directory: Path, shape: str, count: int, functions: int, statements: int):
    directory.mkdir(parents=True)
    values = []
    for index in range(count):
        if shape == 'chain':
            dependencies = [index - 1] if index else []
        elif shape == 'wide':
            dependencies = []
        else:
            # A layered diamond: each node shares two earlier dependencies,
            # with bounded values while still compiling every reachable node.
            dependencies = list(range(max(0, index - 2), index))
        imports = ''.join(f'use "./m{dep}.min" as d{dep}\n' for dep in dependencies)
        body = []
        for function in range(functions):
            body.append(f'function helper{function}(input: Integer): Integer {{\n    let result = input\n')
            body.extend('    result = result + 1\n' for _ in range(statements))
            body.append('    return result\n}\n')
        # Modulus prevents exponential growth in a shared dependency graph.
        expression = ' + '.join(f'd{dep}.value()' for dep in dependencies) or '1'
        body.append(f'public function value(): Integer {{\n    let result = ({expression}) % 1000\n')
        body.extend(f'    result = helper{function}(result)\n' for function in range(functions))
        body.append('    return result\n}\n')
        values.append((sum(values[dep] for dep in dependencies) if dependencies else 1) % 1000 + functions * statements)
        (directory / f'm{index}.min').write_text(imports + ''.join(body))
    used = list(range(count)) if shape == 'wide' else [count - 1]
    imports = ''.join(f'use "./m{dep}.min" as d{dep}\n' for dep in used)
    calls = ' + '.join(f'd{dep}.value()' for dep in used)
    entry = directory / 'main.min'
    entry.write_text(imports + f'function main() {{\n    print({calls})\n}}\n')
    return entry, str(sum(values[dep] for dep in used)) + '\n'



def timed(command):
    before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
    start = time.perf_counter()
    result = subprocess.run(list(map(str, command)), text=True, capture_output=True, timeout=30)
    wall = time.perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
    if result.returncode:
        raise RuntimeError(result.stderr)
    return {'cpu_ms': 1000 * (after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime) if resource else None,
            'wall_ms': 1000 * wall}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'build/minyarc')
    parser.add_argument('--clang', default=os.environ.get('MINYAR_TEST_CLANG', 'clang'))
    parser.add_argument('--sizes', type=int, nargs='+', default=[100, 400])
    parser.add_argument('--shapes', nargs='+', choices=['chain', 'wide', 'shared'], default=['chain', 'wide', 'shared'])
    parser.add_argument('--functions', type=int, default=4)
    parser.add_argument('--statements', type=int, default=12)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--output', type=Path, default=ROOT/'build/module-performance.json')
    args = parser.parse_args()
    if args.repeats < 1 or args.functions < 1 or args.statements < 1 or any(n < 1 for n in args.sizes):
        parser.error('sizes, functions, statements and repeats must be positive')
    compiler = args.compiler.resolve()
    compiler_bytes = compiler.read_bytes()
    report = {'platform': platform.platform(), 'machine': platform.machine(),
              'compiler_sha256': hashlib.sha256(compiler_bytes).hexdigest(),
              'workspace_source_sha256': hashlib.sha256((ROOT/'src/compiler.min').read_bytes()).hexdigest(),
              'method': __doc__, 'config': {k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()},
              'results': [], 'scaling': []}
    with tempfile.TemporaryDirectory(prefix='minyar-module-perf-') as name:
        temporary = Path(name)
        compiler = temporary/'minyarc'
        compiler.write_bytes(compiler_bytes)
        compiler.chmod(0o755)
        runtime = temporary/'runtime.o'
        runtime.write_bytes((ROOT/'build/minyar-runtime.o').read_bytes())
        for shape in args.shapes:
            for count in args.sizes:
                directory = temporary / f'{shape}-{count}'
                entry, expected = generate(directory, shape, count, args.functions, args.statements)
                original = entry.read_text()
                library = directory/'m0.min'
                library_text = library.read_text()
                llvm = directory/'program.ll'
                # Check deduplication even for the large shared graph. Running
                # that graph would recursively repeat calls exponentially.
                timed([compiler, entry, llvm])
                definitions = [line for line in llvm.read_text().splitlines() if line.startswith('define ')]
                assert len(definitions) == count * (args.functions + 1) + 1, (shape, count, len(definitions))
                for scenario in ('unchanged', 'entry-edit', 'dependency-edit', 'interface-edit'):
                    entry.write_text(original)
                    library.write_text(library_text)
                    if scenario == 'entry-edit':
                        entry.write_text(original.replace('    print(', '    let edited = 1\n    print('))
                    elif scenario == 'dependency-edit':
                        library.write_text(library_text.replace('result = result + 1', 'result = result + 2', 1))
                    elif scenario == 'interface-edit':
                        # Add a field to an exported record, a true interface
                        # change even if this program does not use that type.
                        library.write_text(library_text + '\npublic record Added { value: Integer }\n')
                    timed([compiler, entry, llvm])
                    samples = [timed([compiler, entry, llvm]) for _ in range(args.repeats)]
                    row = {'shape': shape, 'modules': count, 'scenario': scenario,
                           'source_bytes': sum(p.stat().st_size for p in directory.glob('*.min')),
                           'llvm_bytes': llvm.stat().st_size, 'samples': samples,
                           'cpu_ms': statistics.median(s['cpu_ms'] for s in samples) if resource else None,
                           'wall_ms': statistics.median(s['wall_ms'] for s in samples)}
                    report['results'].append(row)
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(report, indent=2)+'\n')
                    metric = row['cpu_ms'] if resource else row['wall_ms']
                    if metric > 5000:
                        raise AssertionError(f'{shape}/{count}/{scenario}: exceeds 5-second compilation ceiling')
                    cpu_label = f"{row['cpu_ms']:.2f}" if resource else 'unavailable'
                    print(f"{shape:6} {count:4} {scenario:15} CPU {cpu_label} ms, wall {row['wall_ms']:.2f} ms", flush=True)
        # Execute bounded instances of every shape, including shared imports.
        for shape in args.shapes:
            entry, expected = generate(temporary/f'execute-{shape}', shape, 10, args.functions, args.statements)
            llvm = entry.with_suffix('.ll')
            program = entry.with_suffix('.exe')
            timed([compiler, entry, llvm])
            timed([args.clang, '-O0', '-Wno-override-module', llvm, runtime, '-o', program])
            assert subprocess.check_output([str(program)], text=True, timeout=30) == expected
    for shape in args.shapes:
        rows = sorted((r for r in report['results'] if r['shape'] == shape and r['scenario'] == 'unchanged'), key=lambda r:r['modules'])
        for small, large in zip(rows, rows[1:]):
            key = 'cpu_ms' if resource else 'wall_ms'
            ratio = large[key]/max(small[key], 1)
            size_ratio = large['modules']/small['modules']
            report['scaling'].append({'shape':shape, 'small':small['modules'], 'large':large['modules'],
                                      'size_ratio':size_ratio, 'time_ratio':ratio})
            # This catches severe nonlinear regressions without fitting tiny
            # startup-dominated timings to an asymptotic complexity claim.
            if large[key] >= 50 and ratio > 2*size_ratio:
                raise AssertionError(f'{shape}: {ratio:.2f}x time for {size_ratio:.2f}x modules')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(args.output)


if __name__ == '__main__':
    main()
