import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--artifacts', type=Path)
args = parser.parse_args()
temporary = tempfile.TemporaryDirectory(prefix='minyar-thread-tsan-') if args.artifacts is None else None
directory = args.artifacts.resolve() if args.artifacts else Path(temporary.name) / 'control'
directory.mkdir(parents=True, exist_ok=False)
source = directory / 'race-control.min'
source.write_text('''thread function writer(seed: Integer, input: FrozenBytes, queue: BytesChannel): Integer {
    let status = threadSleepNanoseconds(100000000)
    return seed
}
function main() {
    let frozen = freezeBytes(Bytes(0))
    let queue = bytesChannel(0, 1)
    let first = startThread(writer, 1, frozen, queue)
    let second = startThread(writer, 2, frozen, queue)
    print(joinThread(first) + joinThread(second))
}
''')
manifest = {'commands': [], 'files': {}, 'inputs': {}}
for directory_name in ('compiler', 'runtime', 'library', 'tools', 'scripts', 'build-support'):
    for path in sorted((ROOT / directory_name).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            manifest['inputs'][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
for path in (Path(__file__), ROOT / 'build/minyarc-threads', ROOT / 'Makefile'):
    manifest['inputs'][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()


def run(label, command, environment=None):
    result = subprocess.run(list(map(str, command)), env=environment, capture_output=True, text=True, timeout=120)
    manifest['commands'].append({'label': label, 'argv': list(map(str, command)), 'returncode': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr,
                                 'environment': {name: environment.get(name) for name in
                                    ('MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_NATIVE_FLAGS', 'TSAN_OPTIONS')}
                                    if environment else {}})
    for path in directory.rglob('*'):
        if path.is_file() and path.name != 'manifest.json':
            manifest['files'][path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.artifacts:
        (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return result


raw = directory / 'compiler.raw.ll'
compiled = run('compiler', [ROOT / 'build/minyarc-threads', source, raw, '--bounded-owners', '32'])
assert compiled.returncode == 0, compiled.stderr
text = raw.read_text()
header = re.search(r'^define i64 @\.minyar\.fn\.writer\([^\n]*\{\nentry:\n', text, re.M)
assert header, 'generated writer entry changed'
text = (text[:header.end()] + '  store volatile i64 %argument.0, ptr @.thread.tsan.unsafe, align 8\n' +
        text[header.end():] + '\n@.thread.tsan.unsafe = internal global i64 0, align 8\n')
unsafe = directory / 'unsafe.raw.ll'
unsafe.write_text(text)
runtime = ROOT / 'build/minyar-default-runtime.o'
options = '-O1 -g -fsanitize=thread -fno-omit-frame-pointer -Wno-override-module'
environment = dict(os.environ, MINYAR_CLANG_FLAGS=options, MINYAR_RUNTIME_FLAGS=options,
                   MINYAR_NATIVE_FLAGS=options, MINYAR_LINK_ARTIFACTS=str(directory / 'link'),
                   TSAN_OPTIONS='halt_on_error=1:exitcode=66')
binary = directory / 'race-control'
linked = run('link', ['python3', ROOT / 'tools/clang-driver.py', 'link', ROOT, unsafe, runtime, binary, '0'], environment)
assert linked.returncode == 0, linked.stderr
annotated = (directory / 'link/program.tsan.ll').read_text()
for line in annotated.splitlines():
    if line.startswith('define '):
        assert 'sanitize_thread' in line, 'generated definition escaped TSan: ' + line
observed = run('race', [binary], environment)
assert observed.returncode != 0 and 'ThreadSanitizer: data race' in observed.stderr, observed.stderr
assert 'unsafe.raw.ll' in observed.stderr or 'writer' in observed.stderr, observed.stderr
print('TSan detected the generated LLVM shared-global race')
