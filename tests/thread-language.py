

from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from clang_helpers import launcher_command, asan_leak_options

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sanitizer', choices=('native', 'address', 'thread'), default='native')
parser.add_argument('--artifacts', type=Path)
args = parser.parse_args()
if not (ROOT / 'runtime/minyar_thread_domain.h').is_file():
    raise SystemExit('thread language qualification requires the real runtime sibling; no shim/stub is permitted')
environment = dict(os.environ, LIMITED='', SANITIZER_LIMITED='', COMPILER_LTO_FLAGS='')
if args.sanitizer != 'native':
    sanitizer = 'address,undefined' if args.sanitizer == 'address' else 'thread'
    options = '-O1 -g -fsanitize=' + sanitizer + ' -fno-omit-frame-pointer -Wno-override-module'
    environment.update(MINYAR_CLANG_FLAGS=options, MINYAR_RUNTIME_FLAGS=options, MINYAR_NATIVE_FLAGS=options,
                       ASAN_OPTIONS=asan_leak_options() + ':halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
                       TSAN_OPTIONS='halt_on_error=1:exitcode=66')
manifest = {'sanitizer': args.sanitizer, 'commands': [], 'inputs': {}}
manifest['environment'] = {name: environment.get(name) for name in
    ('MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_NATIVE_FLAGS', 'ASAN_OPTIONS', 'UBSAN_OPTIONS', 'TSAN_OPTIONS')}
if args.artifacts:
    args.artifacts = args.artifacts.resolve()
    args.artifacts.mkdir(parents=True, exist_ok=False)
    for directory in ('compiler', 'runtime', 'library', 'tools', 'scripts', 'build-support'):
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                manifest['inputs'][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in [Path(__file__), *(ROOT / 'tests/thread-fixtures').glob('*.min'),
                 ROOT / 'build/minyarc', ROOT / 'build/minyarc-threads', ROOT / 'tests/clang_helpers.py',
                 ROOT / 'Makefile', ROOT / 'minyar']:
        manifest['inputs'][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()


def record(label, command, result):
    manifest['commands'].append({'label': label, 'argv': list(map(str, command)), 'returncode': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr})
    if args.artifacts:
        (args.artifacts / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


with tempfile.TemporaryDirectory(prefix='minyar-thread-language-') as temporary:
    directory = args.artifacts or Path(temporary)
    for profile in ('system', 'eager'):
        for fixture, expected in (('creator-exit', 'creator-exit shared frozen passed\n'),
                                  ('transfer-local', 'managed local transfer passed\n'),
                                  ('nothing-nested', 'Nothing and nested joins passed\n'),
                                  ('recovery-unwind', 'recovery and child cleanup passed\n'),
                                  ('result-guard', None)):
            label = fixture + '-' + profile
            output = directory / label
            command = [*launcher_command(ROOT), '--memory-profile', profile,
                       str(ROOT / 'tests/thread-fixtures' / (fixture + '.min')), '-o', str(output)]
            link_environment = dict(environment)
            if args.artifacts:
                link_environment['MINYAR_LINK_ARTIFACTS'] = str(directory / (label + '-link'))
            compiled = subprocess.run(command, env=link_environment, capture_output=True, text=True, timeout=300)
            record(label + '-build', command, compiled)
            if compiled.returncode:
                raise SystemExit(compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(output)], env=environment, capture_output=True, text=True, timeout=30)
            record(label + '-run', [str(output)], ran)
            if expected is None:
                if (ran.returncode == 0 or ran.stdout != '' or
                        'an unsuccessful FrozenBytes Result has no value.' not in ran.stderr or
                        any(message in ran.stderr for message in ('AddressSanitizer:', 'LeakSanitizer:',
                                                                 'runtime error:', 'ThreadSanitizer:'))):
                    raise SystemExit(f'{fixture}/{profile}: {ran.returncode} {ran.stdout!r} {ran.stderr!r}')
            elif (ran.returncode, ran.stdout, ran.stderr) != (0, expected, ''):
                raise SystemExit(f'{fixture}/{profile}: {ran.returncode} {ran.stdout!r} {ran.stderr!r}')
            print(f'{fixture}/{profile}: passed with real runtime')
