#!/usr/bin/env python3
"""Build and compare an isolated Linux compiler using LLVM IR profile guidance."""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import statistics
import sys
import tempfile
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    '--output', type=Path, default=Path('build/compiler-pgo'),
    help='artifact parent, relative to the repository root',
)
parser.add_argument('--samples', type=int, default=31, help='retained alternating pairs per workload (3..101)')
args = parser.parse_args()
if sys.platform != 'linux':
    parser.error('this experiment currently supports native Linux ELF only')
if not 3 <= args.samples <= 101:
    parser.error('--samples must be between 3 and 101')
if not __debug__:
    parser.error('unset PYTHONOPTIMIZE and omit -O so validation remains enabled')
def interrupted(signum, frame):
    raise InterruptedError(f'PGO experiment received signal {signum}')


signal.signal(signal.SIGTERM, interrupted)
os.chdir(Path(__file__).resolve().parents[2])
output_root = args.output.resolve()
if '%' in str(output_root):
    parser.error('--output cannot contain LLVM profile filename substitutions (%)')
output_root.mkdir(parents=True, exist_ok=True)
work = Path(tempfile.mkdtemp(prefix='run-', dir=output_root))
print(json.dumps(dict(event='artifacts', directory=str(work))), flush=True)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

@dataclass(frozen=True)
class Invocation:
    stdout: bytes
    stderr: bytes
    returncode: int
    wall_seconds: float
    cpu_seconds: float


command_directory = work / 'commands'
command_directory.mkdir()
command_serial = 0


def run(command, env=None, expected=0, timeout=180):
    global command_serial
    command_serial += 1
    command = list(map(str, command))
    prefix = command_directory / str(command_serial).zfill(4)
    stdout_path = prefix.with_suffix('.stdout')
    stderr_path = prefix.with_suffix('.stderr')
    metadata_path = prefix.with_suffix('.json')
    event = dict(argv=command, cwd=str(Path.cwd()), expected=expected,
                 timeout_seconds=timeout, state='started',
                 stdout=str(stdout_path), stderr=str(stderr_path))
    if env is not None and 'LLVM_PROFILE_FILE' in env:
        event['LLVM_PROFILE_FILE'] = env['LLVM_PROFILE_FILE']
    metadata_path.write_text(json.dumps(event, indent=2) + '\n')
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    process = None
    failure = None
    stdout = stderr = b''
    try:
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as caught:
        failure = caught
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate(timeout=5)
    wall = time.monotonic() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    timed_out = isinstance(failure, subprocess.TimeoutExpired)
    state = 'timeout' if timed_out else ('interrupted' if failure else 'finished')
    event.update(state=state, returncode=process.returncode if process else None,
                 wall_seconds=wall, cpu_seconds=cpu)
    metadata_path.write_text(json.dumps(event, indent=2) + '\n')
    if timed_out:
        raise TimeoutError(f'command exceeded {timeout}s; process group killed; {metadata_path}') from failure
    if failure is not None:
        raise failure
    if process.returncode != expected:
        raise RuntimeError((command, process.returncode,
                            stdout.decode(errors='replace'), stderr.decode(errors='replace')))
    return Invocation(stdout, stderr, process.returncode, wall, cpu)


def compile_with(executable, source, env=None, expected=0, measurements=None):
    output.unlink(missing_ok=True)
    result = run([executable, source, output, '--library', 'library'], env=env, expected=expected)
    if measurements is not None:
        measurements.update(wall_seconds=result.wall_seconds, cpu_seconds=result.cpu_seconds)
    if expected:
        assert not output.exists(), 'invalid source emitted LLVM'
        return result.stdout, result.stderr
    return output.read_bytes(), result.stdout, result.stderr


# Preserve argv[0]: ld.lld and unified LLVM tools can dispatch by symlink name.
cc = Path(os.path.abspath(run(['sh', 'tools/toolchain.sh', 'toolchain'], timeout=10).stdout.decode().strip()))
profdata = cc.resolve().parent / 'llvm-profdata'
assert profdata.is_file(), profdata
linker_name = run([cc, '-print-prog-name=ld.lld'], timeout=10).stdout.decode().strip()
linker = os.path.abspath(shutil.which(linker_name) or linker_name)
flags = ['-O2', '-Wno-override-module', '-flto=thin', '-fuse-ld=' + linker, '-Wl,--threads=1']
inputs = ['build/compiler-stage2.ll', 'build/minyar-compiler-runtime.ll']
output = work / 'emitted.ll'

versions = {name: run([tool, '--version'], timeout=10).stdout.decode() for name, tool in [('clang', cc), ('profdata', profdata), ('lld', linker)]}
expected_version = re.search(r'clang version ([0-9]+\.[0-9]+\.[0-9]+)', versions['clang']).group(1)
assert all(re.search(r'(?<![0-9.])([0-9]+\.[0-9]+\.[0-9]+)(?![0-9.])', value).group(1) == expected_version for value in versions.values()), versions
source_paths = [
    str(path)
    for directory in ['compiler', 'runtime', 'library', 'examples']
    for path in Path(directory).rglob('*')
    if path.suffix in ['.min', '.c', '.h']
]
frozen_paths = sorted(set(
    inputs + ['build/compiler.min', 'build/compiler-stage3.ll', 'build/minyar-runtime.o', 'build/minyarc',
              'bootstrap/stage0.c', 'Makefile', 'tools/toolchain.sh', str(Path(__file__).resolve())]
    + source_paths + [str(path) for path in Path('build-support').glob('*.mk')]
))
frozen_hashes = {p: digest(p) for p in frozen_paths}
tool_hashes = {str(path): digest(path) for path in [cc, profdata, linker]}
archive_directory = work / 'inputs'
archive_directory.mkdir()
archived_inputs = {}
for source in inputs + ['build/compiler.min', 'build/compiler-stage3.ll', 'build/minyar-runtime.o']:
    destination = archive_directory / Path(source).name
    shutil.copyfile(source, destination)
    assert digest(destination) == frozen_hashes[source], ('input copy changed', source)
    archived_inputs[source] = dict(path=str(destination), sha256=digest(destination))
base = work / 'baseline'
train = work / 'instrumented'
candidate = work / 'pgo'
profile_dir = work / 'profiles'
profile_dir.mkdir(exist_ok=True)
commands = {}
for name, executable, extra in [('baseline', base, []), ('instrumented', train, ['-fprofile-generate=' + str(profile_dir)])]:
    commands[name] = [str(cc), *flags, *extra, *inputs, '-lm', '-o', str(executable)]
    if name == 'instrumented':
        driver = run([*commands[name], '-###']).stderr.decode()
        (work / 'instrumented-driver.txt').write_text(driver)
        assert '-fprofile-instrument=llvm' in driver and 'libclang_rt.profile' in driver, driver
    start = time.monotonic()
    run(commands[name])
    print(json.dumps(dict(event='link', kind=name, wall=time.monotonic()-start)), flush=True)
training = ['build/compiler.min', 'examples/language-tour.min', 'examples/gallery/generics.min', 'examples/gallery/results.min']
train_env = dict(os.environ, LLVM_PROFILE_FILE=str(profile_dir / 'train-%p.profraw'))
for source in training:
    reference = compile_with(base, source)
    assert compile_with(train, source, env=train_env) == reference, ('training output changed', source)
    print(json.dumps(dict(event='trained', source=source)), flush=True)
raw = sorted(profile_dir.glob('*.profraw'))
assert len(raw) == len(training), ('profile files missing', raw)
profile = work / 'compiler.profdata'
run([profdata, 'merge', '--instr', '--sparse=false', '--failure-mode=any', '--num-threads=1', '-o', profile, *raw])
profile_summary = run([profdata, 'show', profile]).stdout.decode()
assert 'Instrumentation level: IR' in profile_summary, profile_summary
(work / 'profile-summary.txt').write_text(profile_summary)
profile_counts = run([profdata, 'show', '--all-functions', '--counts', profile]).stdout.decode()
(work / 'profile-counts.txt').write_text(profile_counts)
positive = {'compiler': False, 'runtime': False}
current_name = ''
for line in profile_counts.splitlines():
    if line.startswith('  ') and not line.startswith('    ') and line.endswith(':'):
        current_name = line.strip()[:-1]
    if line.strip().startswith('Block counts:'):
        counts = [int(n) for n in re.findall(r'\d+', line.split('[', 1)[1])]
        if any(counts):
            if 'minyar.fn.' in current_name:
                positive['compiler'] = True
            if 'minyar_' in current_name:
                positive['runtime'] = True
assert all(positive.values()), ('nonzero compiler/runtime profiles missing', positive)
profile_hash = digest(profile)
raw_hashes = {str(p): digest(p) for p in raw}
commands['pgo'] = [str(cc), *flags, '-fprofile-use=' + str(profile), '-Werror=profile-instr-out-of-date', '-Wprofile-instr-missing', '-Wprofile-instr-unprofiled', *inputs, '-lm', '-o', str(candidate)]
profile_link = run(commands['pgo'])
(work / 'profile-use-link.stderr').write_bytes(profile_link.stderr)
assert not profile_link.stderr, profile_link.stderr.decode(errors='replace')
late = work / 'late-calls.min'
late.write_text(''.join('function value' + str(i) + '(n: Integer): Integer { return n + ' + str(i) + ' }\n' for i in range(1200)) + 'print(value1199(1))\n')
records = work / 'records.min'
records.write_text(''.join('record Leaf' + str(i) + ' { value: Integer }\n' for i in range(1000)) + 'let leaf = Leaf999 { value: 42 }\nprint(leaf.value)\n')
module_dir = work / 'module-holdout'
module_dir.mkdir(exist_ok=True)
module_files = []
for index in range(64):
    leaf = module_dir / ('leaf' + str(index) + '.min')
    leaf.write_text('public function value(): Integer { return ' + str(index) + ' }\n')
    module_files.append(leaf)
modules = module_dir / 'main.min'
modules.write_text(''.join('use "./leaf' + str(i) + '.min" as leaf' + str(i) + '\n' for i in range(64)) + 'print(' + ' + '.join('leaf' + str(i) + '.value()' for i in range(64)) + ')\n')
benchmarks = ['build/compiler.min', str(late), str(records), str(modules)]
invalid_sources = []
for index, source in enumerate(['let answer: Integer = "wrong"\n', 'print(missing)\n', 'print(9223372036854775808)\n']):
    invalid = work / ('invalid-' + str(index) + '.min')
    invalid.write_text(source)
    invalid_sources.append(invalid)
generated_hashes = {str(p):digest(p) for p in [late, records, modules, *module_files, *invalid_sources]}
checks = [*benchmarks, 'examples/graph.min', 'examples/gallery/generic-records.min', 'examples/gallery/methods.min', 'examples/gallery/choice.min']
references = {}
for source in checks:
    references[source] = compile_with(base, source)
    assert compile_with(candidate, source) == references[source], ('PGO output changed', source)
    (work / ('reference-' + str(len(references)) + '.ll')).write_bytes(references[source][0])
for invalid in invalid_sources:
    assert compile_with(base, invalid, expected=1) == compile_with(candidate, invalid, expected=1), ('diagnostics differ', invalid)
assert references['build/compiler.min'][0] == Path('build/compiler-stage3.ll').read_bytes(), 'baseline is not fixed-point compiler'
for source, expected in [(late, b'1200\n'), (records, b'42\n'), (modules, b'2016\n')]:
    assert compile_with(candidate, source) == references[str(source)]
    for optimization in ['-O0', '-O2']:
        program = work / 'holdout-program'
        run([cc, optimization, '-Wno-override-module', '-fuse-ld=' + linker, '-Wl,--threads=1', output, 'build/minyar-runtime.o', '-lm', '-o', program])
        actual = run([program])
        assert (actual.stdout, actual.stderr) == (expected, b''), ('generated holdout expected result changed', source, optimization, actual.stdout, actual.stderr)
rows = []
for source in benchmarks:
    for pair in range(args.samples + 3):
        order = [('baseline', base), ('pgo', candidate)]
        if pair % 2:
            order.reverse()
        for name, executable in order:
            timing = {}
            actual = compile_with(executable, source, measurements=timing)
            assert actual == references[source], ('timed output differs', source, pair, name)
            if pair >= 3:
                row = dict(source=source, pair=pair-3, kind=name, **timing)
                rows.append(row)
                with (work / 'samples.jsonl').open('a') as stream:
                    stream.write(json.dumps(row) + '\n')
                print(json.dumps(row), flush=True)
summary = {}
for source in benchmarks:
    summary[source] = {}
    for field in ['wall_seconds', 'cpu_seconds']:
        medians = {name: statistics.median(r[field] for r in rows if r['source'] == source and r['kind'] == name) for name in ['baseline', 'pgo']}
        pairs = {name: {r['pair']: r[field] for r in rows if r['source'] == source and r['kind'] == name} for name in ['baseline', 'pgo']}
        ratios = [pairs['pgo'][i] / pairs['baseline'][i] for i in range(args.samples)]
        summary[source][field] = dict(medians=medians, median_ratio=statistics.median(ratios), ratio_range=[min(ratios),max(ratios)])
assert {p: digest(p) for p in frozen_paths} == frozen_hashes, 'inputs changed during experiment'
assert {p: digest(p) for p in tool_hashes} == tool_hashes, 'LLVM tools changed during experiment'
assert all(digest(item['path']) == item['sha256'] for item in archived_inputs.values()), 'archived input changed'
assert digest(profile) == profile_hash and {str(p):digest(p) for p in profile_dir.glob('*.profraw')} == raw_hashes, 'profile changed during holdout validation/timing'
assert {p:digest(p) for p in generated_hashes} == generated_hashes, 'generated holdouts changed'
report = dict(
    host=dict(system=sys.platform, machine=os.uname().machine, release=os.uname().release),
    samples_per_workload=args.samples,
    warmups_per_role=3,
    candidate=str(candidate),
    output_sha256={source: hashlib.sha256(value[0]).hexdigest() for source, value in references.items()},
    profile_sha256=profile_hash,
    raw_profile_sha256=raw_hashes,
    generated_source_sha256=generated_hashes,
    profile_nonzero_records=positive,
    tool_versions=versions,
    tool_sha256=tool_hashes,
    archived_inputs=archived_inputs,
    tool_paths={name: dict(invocation=str(path), identity=str(Path(path).resolve()))
                for name, path in [('clang', cc), ('profdata', profdata), ('lld', linker)]},
    frozen_sha256=frozen_hashes,
    wall_scope='compiler subprocess startup through exit with stdout/stderr capture',
    commands=commands,
    training=training,
    correctness_sources=checks,
    trained_timing_sources=['build/compiler.min'],
    holdouts=[source for source in checks if source not in training],
    command_directory=str(command_directory),
    profile_summary=profile_summary,
    input_sha256={p: digest(p) for p in inputs},
    binaries={
        name: dict(bytes=path.stat().st_size, sha256=digest(path))
        for name, path in [('baseline', base), ('instrumented', train), ('pgo', candidate)]
    },
    samples=rows,
    summary=summary,
    same_self_host_ir_sha256=hashlib.sha256(references['build/compiler.min'][0]).hexdigest(),
)
(work / 'results.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(event='summary', candidate=str(candidate), evidence=str(work / 'results.json'), summary=summary)), flush=True)
