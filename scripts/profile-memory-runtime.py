#!/usr/bin/env python3
"""Sample eager and bounded runtimes with the mixed workload on macOS.

A temporary LLVM copy renames main so a C driver can call it repeatedly.
Sampling shares CPU with the workload and affects timing."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import os
import select
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default=os.environ.get('CLANG', 'clang'))
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/minyarc')
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument('--duration', type=int, default=2)
    parser.add_argument('--heap-bytes', type=int, default=67108864)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sampler', choices=('attach', 'self'), default='attach')
    args = parser.parse_args()
    assert args.iterations > 0 and 0 < args.duration < 60
    directory = Path(tempfile.mkdtemp(prefix='minyar-runtime-sampling-'))
    (directory / 'runtime').mkdir()
    sources = [ROOT / 'runtime/minyar_runtime.c', *sorted((ROOT / 'runtime').glob('*.h'))]
    for source in sources:
        shutil.copy2(source, directory / 'runtime' / source.name)
    benchmark = ROOT / 'tests/performance/runtime.min'
    compiler = args.compiler.resolve()

    def run(command):
        return subprocess.run(list(map(str, command)), check=True, capture_output=True,
                              text=True, timeout=60)

    ll = directory / 'benchmark.ll'
    run([compiler, benchmark, ll])
    original = ll.read_text()
    assert original.count('define i32 @main(') == 1
    ll.write_text(original.replace('define i32 @main(', 'define i32 @minyar_benchmark_main('))
    driver = directory / 'driver.c'
    driver.write_text('''#include <stdio.h>
extern int minyar_benchmark_main(int, char **);
int main(void) {
    char *arguments[] = {"minyar-profile", "8", 0};
    int status = minyar_benchmark_main(2, arguments);
    if (status) return status;
    fputs("MINYAR_SAMPLE_READY\\n", stderr);
    fflush(stderr);
    for (unsigned i = 0; i < ''' + str(args.iterations) + '''; i++) {
        status = minyar_benchmark_main(2, arguments);
        if (status) return status;
    }
    return 0;
}
''')
    results = {}
    expected = None
    sampler_object = directory / 'sampler.o'
    if args.sampler == 'self':
        sampler_source = directory / 'sampler.c'
        sampler = (ROOT / 'scripts/ownership-sampler.c').read_text()
        sampler = sampler.replace('__attribute__((constructor)) static void begin_sampling(void)',
                                  'void minyar_profile_begin(void)')
        sampler = sampler.replace('__attribute__((destructor)) static void finish_sampling(void)',
                                  'void minyar_profile_finish(void)')
        sampler = sampler.replace('"MINYAR_PC\\t%s\\t%s\\n",',
                                  '"MINYAR_PC\\t%s\\t%s\\t%p\\t%p\\n",')
        sampler = sampler.replace('symbol.dli_sname ? symbol.dli_sname : "unknown");',
                                  'symbol.dli_sname ? symbol.dli_sname : "unknown",\n'
                                  '                (void *)pc, symbol.dli_fbase);')
        sampler_source.write_text(sampler)
        run([args.clang, '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
             '-c', sampler_source, '-o', sampler_object])
        source = driver.read_text().replace('int main(void) {',
            'void minyar_profile_begin(void);\nvoid minyar_profile_finish(void);\nint main(void) {')
        source = source.replace('    for (unsigned i = 0;',
                                '    minyar_profile_begin();\n    for (unsigned i = 0;')
        source = source.replace('    return 0;\n}', '    minyar_profile_finish();\n    return 0;\n}')
        driver.write_text(source)

    for version in ('eager', 'bounded'):
        obj = directory / f'{version}.o'
        executable = directory / version
        flags = [] if version == 'eager' else [
            '-DMINYAR_BOUNDED_HEAP=1', f'-DMINYAR_BOUNDED_HEAP_BYTES={args.heap_bytes}']
        run([args.clang, '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', *flags,
             '-c', directory / 'runtime/minyar_runtime.c', '-o', obj])
        run([args.clang, '-O2', '-g', '-Wno-override-module', ll, driver, obj,
             *([sampler_object] if args.sampler == 'self' else []),
             '-Wl,-export_dynamic', '-o', executable])
        if args.sampler == 'self':
            run(['/usr/bin/dsymutil', executable])
        stdout_path = directory / f'{version}.stdout'
        report = directory / f'{version}.sample.txt'
        with stdout_path.open('wb') as stdout:
            process = subprocess.Popen([str(executable)], stdout=stdout, stderr=subprocess.PIPE)
            ready, _, _ = select.select([process.stderr], [], [], 60)
            if not ready:
                process.kill()
                raise RuntimeError(f'{version}: did not finish warm-up')
            message = process.stderr.readline()
            if message != b'MINYAR_SAMPLE_READY\n':
                process.kill()
                remaining = process.communicate(timeout=30)[1]
                raise RuntimeError(f'{version}: warm-up failed: {(message + remaining).decode()}')
            if args.sampler == 'attach':
                sampled = subprocess.run(['/usr/bin/sample', str(process.pid), str(args.duration),
                                          '1', '-mayDie', '-fullPaths', '-file', str(report)],
                                         capture_output=True, text=True, timeout=args.duration + 45)
            stderr = process.communicate(timeout=120)[1]
        assert process.returncode == 0, (version, process.returncode, stderr.decode())
        output = stdout_path.read_bytes()
        lines = output.splitlines(keepends=True)
        assert len(lines) == 5 * (args.iterations + 1), (version, len(lines))
        first = b''.join(lines[:5])
        assert output == first * (args.iterations + 1), version
        if expected is None:
            expected = first
        else:
            assert first == expected, version
        if args.sampler == 'attach':
            results[version] = {'sample_returncode': sampled.returncode,
                                'sample_stdout': sampled.stdout, 'sample_stderr': sampled.stderr,
                                'report': str(report), 'report_exists': report.exists()}
        else:
            report = directory / f'{version}.self-samples.txt'
            report.write_bytes(stderr)
            own_libraries = {str(executable), str(executable.resolve())}
            samples = []
            addresses = set()
            own_base = None
            for line in stderr.decode().splitlines():
                if line.startswith('MINYAR_PC\t'):
                    _, library, symbol, pc, base = line.split('\t')
                    samples.append((library, symbol, pc, base))
                    if library in own_libraries:
                        addresses.add(pc)
                        own_base = base
            assert samples, stderr.decode()
            resolved = {}
            addresses = sorted(addresses)
            for start in range(0, len(addresses), 256):
                batch = addresses[start:start + 256]
                blocks = run(['/usr/bin/atos', '-o', executable, '-l', own_base,
                              '-inlineFrames', '-d', 'MINYAR_ADDRESS_END', *batch]).stdout.split('MINYAR_ADDRESS_END')
                symbols = [' <- '.join(block.strip().splitlines()) for block in blocks if block.strip()]
                assert len(symbols) == len(batch), symbols
                resolved.update(zip(batch, symbols))
            counts = Counter()
            for library, symbol, pc, base in samples:
                detail = resolved.get(pc, symbol) if library in own_libraries else symbol
                counts[(Path(library).name, detail)] += 1
            results[version] = {'report': str(report), 'sample_count': len(samples),
                'scope': 'Flat on-CPU program counters after warm-up, 1ms SIGPROF; '
                         'not inclusive stacks or uninstrumented timing. Static runtime '
                         'functions resolved afterward with atos and load addresses.',
                'locations': [{'library': library, 'symbol': symbol, 'samples': count,
                               'percent': count * 100 / len(samples)}
                              for (library, symbol), count in counts.most_common()]}
        results[version].update(program_returncode=process.returncode,
                                stdout_sha256=hashlib.sha256(output).hexdigest())
        print(version, json.dumps({key: value for key, value in results[version].items()
                                   if key != 'locations'}), flush=True)
    result = {'method': __doc__, 'optimization': 'O2 with runtime debug symbols',
              'iterations_after_warmup': args.iterations, 'sampling_seconds': args.duration if args.sampler == 'attach' else None,
              'sampler': args.sampler,
              'bounded_heap_bytes': args.heap_bytes, 'artifacts': str(directory),
              'expected_one_iteration': expected.decode(), 'results': results,
              'benchmark_sha256': hashlib.sha256(benchmark.read_bytes()).hexdigest(),
              'source_sha256': {str(source): hashlib.sha256(
                  (directory / 'runtime' / source.name).read_bytes()).hexdigest() for source in sources}}
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
