import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

from clang_helpers import asan_leak_options

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--sanitizer', choices=('native', 'address', 'thread'), default='native')
parser.add_argument('--runtime-root', type=Path, default=ROOT)
parser.add_argument('--expect-old', action='store_true')
parser.add_argument('--case', choices=('normal', 'bridge-reject', 'target-reject', 'accepted-unwind'))
args = parser.parse_args()
environment = dict(os.environ, LIMITED='', SANITIZER_LIMITED='',
    ASAN_OPTIONS=asan_leak_options() + ':halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1',
    TSAN_OPTIONS='halt_on_error=1:exitcode=66')
flags = '-O2 -Wno-override-module'
if args.sanitizer != 'native':
    flags = '-O1 -g -fno-omit-frame-pointer -Wno-override-module -fsanitize=' + (
        'address,undefined' if args.sanitizer == 'address' else 'thread')
for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_NATIVE_FLAGS'):
    environment[name] = flags
failure = ''.join(f'  %probe.begin.{i} = call i32 @minyar_calldepth_reporting_begin()\n' for i in range(33))
failure += ''.join(f'  %probe.end.{i} = call i32 @minyar_calldepth_reporting_end()\n' for i in range(32))
with tempfile.TemporaryDirectory(prefix='minyar-generated-recovery-') as temporary:
    directory = Path(temporary)
    for result_type in ('Integer', 'Nothing'):
        source = directory / 'main.min'
        source.write_text('''use "calldepth" as depth
thread function worker(seed: Integer, input: FrozenBytes, queue: BytesChannel): ''' + result_type + ''' {
    let local = Bytes(64)
    local.setInt64(0, seed)
    ''' + ('return 0' if result_type == 'Integer' else 'return') + '''
}
function main() {
    let remaining = depth.remaining()
    if remaining != -1 { fail("main depth scope changed") }
    let input = freezeBytes(Bytes(0))
    let queue = bytesChannel(0, 1)
    let worker = startThread(worker, 42, input, queue)
    let joined = joinThreadResult(worker)
    if joined.ok { print(joined.value) } else { print(joined.code) }
    closeBytesChannel(queue)
}
''')
        for profile in ('system', 'eager'):
            raw = directory / 'program.ll'
            command = [ROOT / 'build/minyarc', source, raw, '--library', ROOT / 'library']
            if profile == 'system': command += ['--bounded-owners', '32']
            compiled = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=60)
            assert compiled.returncode == 0, compiled.stdout + compiled.stderr
            text = raw.read_text()
            assert 'declare i32 @minyar_calldepth_reporting_begin()' in text
            bridge = re.search(r'define internal i64 @\.minyar\.thread\.bridge\.worker\([^\n]*\{\nentry:\n', text)
            worker = re.search(r'define (?:i64|void) @\.minyar\.fn\.worker\([^\n]*\{', text)
            assert bridge and worker
            for case in ([args.case] if args.case else ('normal', 'bridge-reject', 'target-reject', 'accepted-unwind')):
                changed = text
                if case == 'bridge-reject': position = bridge.end()
                elif case == 'target-reject': position = text.index('thread.body:\n', bridge.end()) + len('thread.body:\n')
                elif case == 'accepted-unwind': position = text.index('recovery.body:\n', worker.end()) + len('recovery.body:\n')
                else: position = None
                if position is not None: changed = text[:position] + failure + text[position:]
                program = directory / (case + '.ll')
                program.write_text(changed)
                binary = directory / (case + '-run')
                runtime_name = 'minyar-default-runtime.o' if profile == 'system' else 'minyar-runtime-eager.o'
                command = ['python3', ROOT / 'tools/clang-driver.py', 'link', args.runtime_root,
                           program, args.runtime_root / 'build' / runtime_name, binary, '0']
                linked = subprocess.run(list(map(str, command)), env=environment,
                                        capture_output=True, text=True, timeout=120)
                assert linked.returncode == 0, linked.stdout + linked.stderr
                observed = subprocess.run([binary], env=environment, capture_output=True, text=True, timeout=30)
                expected = '0\n' if case == 'normal' or args.expect_old else '2\n'
                assert (observed.returncode, observed.stdout, observed.stderr) == (0, expected, ''), (
                    result_type, profile, case, observed.returncode, observed.stdout, observed.stderr)
                print(f'{result_type}/{profile}/{case}/{args.sanitizer}: passed')
