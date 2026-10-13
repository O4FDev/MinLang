import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cycle_runtime import publish_engine
from clang_helpers import asan_leak_options

parser = argparse.ArgumentParser()
parser.add_argument('--sanitizer', choices=('native', 'address', 'thread'), default='native')
parser.add_argument('--runtime-only', action='store_true')
parser.add_argument('--language-only', action='store_true')
args = parser.parse_args()
if sys.platform != 'linux':
    raise SystemExit('native-region qualification requires Linux and real KVM')
environment = dict(os.environ, DEBUGINFOD_URLS='', LIMITED='', SANITIZER_LIMITED='',
    ASAN_OPTIONS=asan_leak_options() + ':halt_on_error=1',
    UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', TSAN_OPTIONS='halt_on_error=1:exitcode=66')
flags = ['-O2'] if args.sanitizer == 'native' else ['-O1', '-g', '-fno-omit-frame-pointer',
    '-fsanitize=' + ('address,undefined' if args.sanitizer == 'address' else 'thread')]
for name in ('MINYAR_CLANG_FLAGS', 'MINYAR_RUNTIME_FLAGS', 'MINYAR_NATIVE_FLAGS'):
    environment[name] = ' '.join([*flags, '-Wno-override-module'])
compiler = os.environ.get('MINYAR_TEST_CLANG', 'clang')
if not args.language_only:
    publish_engine(ROOT, ROOT / 'build/thread-cycle-engine.c')
    for cycles in (False, True):
        for system in (False, True):
            label = 'native-regions-' + ('cycle' if cycles else 'rc') + '-' + ('system' if system else 'eager')
            binary = ROOT / 'build' / (label + '-' + args.sanitizer)
            command = [compiler, '-std=c11', *flags, '-Wall', '-Wextra', '-Werror',
                '-DMINYAR_THREADED=1', '-I' + str(ROOT / 'runtime')]
            if cycles: command += ['-DMINYAR_TEST_CYCLES=1']
            if system: command += ['-DMINYAR_SYSTEM_HEAP=1']
            command += [str(ROOT / 'tests/thread-native-regions.c'), '-pthread', '-lm', '-o', str(binary)]
            subprocess.run(command, check=True, timeout=180, env=environment)
            ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, env=environment)
            assert ran.returncode == 0 and ran.stderr == '', (label, ran)
            assert 'real KVM IO dispatch' in ran.stdout, ran
            for case, diagnostic in (('bounds', 'outside'), ('negative', 'outside'), ('alignment', 'aligned'),
                                     ('value', 'fit'), ('result', 'unsuccessful'), ('protection', 'permit')):
                stopped = subprocess.run([binary, case], capture_output=True, text=True, timeout=10, env=environment)
                assert stopped.returncode not in (0, 99) and diagnostic in stopped.stderr, (label, case, stopped)
            print(label, args.sanitizer, 'real KVM and six rejected runtime controls passed', flush=True)
if args.runtime_only:
    raise SystemExit(0)

entry = '''thread function worker(seed: Integer, input: NativeRegion, channel: BytesChannel): Integer {
    return input.getInt64(0)
}
'''
main = '''function main() {
    nativeThreadSetup()
    let input = mapNativeRegion(4096, 3, 34, -1, 0)
    let channel = bytesChannel(0, 1)
    let workerHandle = startThread(worker, 0, input, channel)
    joinThread(workerHandle)
}
'''
with tempfile.TemporaryDirectory(prefix='minyar-native-regions-') as temporary:
    directory = Path(temporary)
    selected = ROOT / 'build/minyarc-sanitize' if args.sanitizer == 'address' else ROOT / 'build/minyarc'
    for name in ('native-regions', 'native-region-kvm', 'native-region-providers'):
        source = ROOT / 'tests/thread-fixtures' / (name + '.min')
        llvm = directory / (name + '.ll')
        compiled = subprocess.run([str(selected), str(source), str(llvm), '--library', str(ROOT / 'library'),
            '--bounded-owners', '32'], capture_output=True, text=True, timeout=90, env=environment)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        binary = directory / name
        linked = subprocess.run(['python3', str(ROOT / 'tools/clang-driver.py'), 'link', str(ROOT), str(llvm),
            str(ROOT / 'build/minyar-default-runtime.o'), str(binary), '0'],
            capture_output=True, text=True, timeout=240, env=environment)
        assert linked.returncode == 0, linked.stdout + linked.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, env=environment)
        assert (ran.returncode, ran.stdout, ran.stderr) == (0, name + ' passed\n', ''), ran
        print(name, args.sanitizer, 'generated language passed', flush=True)
    for variant in ('direct', 'helper', 'children'):
        source = directory / 'main-exit.min'
        text = entry.replace('return input.getInt64(0)', 'return seed') + main.replace(
            'startThread(worker, 0,', 'startThread(worker, 7,').replace(
            '    joinThread(workerHandle)',
            '    let result = joinThread(workerHandle)\n    closeBytesChannel(channel)\n    ' +
            ('stop(result)' if variant == 'helper' else 'exit(result)'))
        expected_stdout = ''
        if variant == 'helper': text = 'function stop(status: Integer) { exit(status) }\n' + text
        if variant == 'children':
            text = text.replace('return seed', 'threadSleepNanoseconds(10000000)\n    print("child joined")\n    return seed')
            text = text.replace('    let result = joinThread(workerHandle)\n    closeBytesChannel(channel)\n    exit(result)', '    exit(7)')
            expected_stdout = 'child joined\n'
        source.write_text(text)
        llvm = directory / 'main-exit.ll'
        compiled = subprocess.run([str(selected), str(source), str(llvm), '--bounded-owners', '32'],
            capture_output=True, text=True, timeout=90, env=environment)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        binary = directory / 'main-exit'
        linked = subprocess.run(['python3', str(ROOT / 'tools/clang-driver.py'), 'link', str(ROOT), str(llvm),
            str(ROOT / 'build/minyar-default-runtime.o'), str(binary), '0'],
            capture_output=True, text=True, timeout=240, env=environment)
        assert linked.returncode == 0, linked.stdout + linked.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, env=environment)
        assert (ran.returncode, ran.stdout, ran.stderr) == (7, expected_stdout, ''), ran
        print('main-exit-' + variant, args.sanitizer, 'joined status passed', flush=True)
    for compile_only in (False, True):
        source = directory / 'main-machine.min'
        controls = 'machine.out8(244, 7)' if compile_only else 'machine.pause()\n    machine.fence()\n    controls()'
        text = entry + main.replace('    nativeThreadSetup()', '    nativeThreadSetup()\n    ' + controls)
        if not compile_only:
            text = 'function controls() { machine.pause(); machine.fence() }\n' + text
        source.write_text('use "machine" as machine\n' + text)
        llvm = directory / 'main-machine.ll'
        compiled = subprocess.run([str(selected), str(source), str(llvm), '--library', str(ROOT / 'library'),
            '--bounded-owners', '32'], capture_output=True, text=True, timeout=90, env=environment)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        symbols = ('out8',) if compile_only else ('pause', 'fence')
        emitted = llvm.read_text()
        assert all('minyar_machine_' + name in emitted for name in symbols)
        if compile_only: assert 'asm sideeffect "outb $0, $1"' in emitted
        else: assert 'asm sideeffect "pause"' in emitted and 'fence seq_cst' in emitted
        binary = directory / 'main-machine'
        linked = subprocess.run(['python3', str(ROOT / 'tools/clang-driver.py'), 'link', str(ROOT), str(llvm),
            str(ROOT / 'build/minyar-default-runtime.o'), str(binary), '0'],
            capture_output=True, text=True, timeout=240, env=environment)
        assert linked.returncode == 0, linked.stdout + linked.stderr
        if compile_only:
            print('main-out8', args.sanitizer, 'compile-only passed; not executed', flush=True)
        else:
            ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, env=environment)
            assert (ran.returncode, ran.stdout, ran.stderr) == (0, '', ''), ran
            print('main-pause-fence', args.sanitizer, 'bounded direct and helper calls passed', flush=True)
    cases = {
        'legacy-main-address': entry + main.replace('    nativeThreadSetup()\n', '').replace(
            '    let input =', '    let local = Bytes(8)\n    let raw = machine.address(local)\n    let input ='),
        'worker-address': entry.replace('return input.getInt64(0)', 'return input.address') + main,
        'worker-raw': entry.replace('return input.getInt64(0)', 'return machine.load64(0)') + main,
        'worker-managed-address': entry.replace('return input.getInt64(0)',
            'let local = Bytes(8)\n    return machine.address(local)') + main,
        'worker-setup': entry.replace('return input.getInt64(0)', 'nativeThreadSetup()\n    return 0') + main,
        'legacy-main-exit': entry + main.replace('    nativeThreadSetup()\n', '').replace(
            '    joinThread(workerHandle)', '    joinThread(workerHandle)\n    exit(0)'),
        'worker-exit': entry.replace('return input.getInt64(0)', 'exit(0)\n    return 0') + main,
        'worker-exit-helper': 'function stop() { exit(0) }\n' +
            entry.replace('return input.getInt64(0)', 'stop()\n    return 0') + main,
        'managed-input': entry.replace('input: NativeRegion', 'input: Bytes') + main,
        'managed-region-list': entry + main.replace('    let channel =',
            '    let managed: List<Bytes> = [Bytes(8)]\n    let invalid = shareNativeRegions(managed)\n    let channel ='),
        'opaque-constructor': entry + main.replace('mapNativeRegion(4096, 3, 34, -1, 0)', 'NativeRegion(0)'),
        'wrong-map-input': entry + main.replace('mapNativeRegion(4096, 3, 34, -1, 0)',
            'mapNativeRegion(Bytes(8), 3, 34, -1, 0)'),
        'worker-native-helper': 'function unsafe(): Integer { return zstd.rawCreateDCtx() }\n' +
            entry.replace('return input.getInt64(0)', 'return unsafe()') + main,
        'worker-decode-helper': 'function unsafe(): Integer { let ctx = zstd.createDCtx(); let result = zstd.decompressInto(ctx, Bytes(0), Bytes(8)); zstd.closeDCtx(ctx); return result }\n' +
            entry.replace('return input.getInt64(0)', 'return unsafe()') + main,
        'worker-close-helper': 'function unsafe(): Integer { zstd.rawCloseDCtx(0); return 0 }\n' +
            entry.replace('return input.getInt64(0)', 'return unsafe()') + main,
        'worker-buffer-helper': 'function unsafe(): Integer { return zstd.threadRejectionDecompress() }\n' +
            entry.replace('return input.getInt64(0)', 'return unsafe()') + main,
        'unreviewed-extern-main': 'function dangerous(): Integer { native "not_reviewed" }\n' +
            entry + main.replace('    nativeThreadSetup()', '    nativeThreadSetup()\n    dangerous()'),
    }
    for operation, call in (('pause', 'machine.pause()'), ('fence', 'machine.fence()'),
                            ('out8', 'machine.out8(244, 7)')):
        cases['worker-machine-' + operation] = entry.replace('return input.getInt64(0)', call + '\n    return 0') + main
        cases['worker-machine-' + operation + '-helper'] = 'function unsafe() { ' + call + ' }\n' + \
            entry.replace('return input.getInt64(0)', 'unsafe()\n    return 0') + main
        cases['legacy-main-machine-' + operation] = entry + main.replace('    nativeThreadSetup()', '    ' + call)
    library = directory / 'library'
    library.mkdir()
    (library / 'machine.min').write_bytes((ROOT / 'library/machine.min').read_bytes())
    (library / 'zstd.min').write_text((ROOT / 'library/zstd.min').read_text() +
        '\npublic function threadRejectionDecompress(): Integer { return bufferDecompress(0, Bytes(0), Bytes(0)) }\n')
    for label, text in cases.items():
        source = directory / 'rejected.min'
        source.write_text('use "machine" as machine\nuse "zstd" as zstd\n' + text)
        llvm = directory / 'rejected.ll'
        llvm.unlink(missing_ok=True)
        rejected = subprocess.run([str(selected), str(source), str(llvm), '--library', str(library),
            '--bounded-owners', '32'], capture_output=True, text=True, timeout=90, env=environment)
        assert rejected.returncode != 0 and not llvm.exists(), (label, rejected)
        diagnostic = 'unsafe thread effect'
        if label == 'managed-input': diagnostic = 'thread entry'
        if label in ('managed-region-list', 'wrong-map-input'): diagnostic = 'wrong thread boundary argument types'
        if label == 'opaque-constructor': diagnostic = 'opaque thread types cannot be constructed'
        assert diagnostic in rejected.stderr + rejected.stdout, (label, rejected)
        provider = {'worker-native-helper': 'minyar_zstd_rawCreateDCtx',
                    'worker-close-helper': 'minyar_zstd_rawCloseDCtx',
                    'worker-buffer-helper': 'minyar_zstd_bufferDecompress'}.get(label)
        if provider: assert provider in rejected.stderr + rejected.stdout, (label, rejected)
        if label in ('legacy-main-exit', 'worker-exit', 'worker-exit-helper'):
            assert "builtin 'exit' 0(1)" in rejected.stderr + rejected.stdout, (label, rejected)
        if '-machine-' in label:
            operation = label.split('-machine-', 1)[1].removesuffix('-helper')
            signature = '5(1,1)' if operation == 'out8' else '5()'
            assert "native 'minyar_machine_" + operation + "' " + signature in rejected.stderr + rejected.stdout, (label, rejected)
        assert 'AddressSanitizer:' not in rejected.stderr and 'runtime error:' not in rejected.stderr, (label, rejected)
        print(label, args.sanitizer, 'rejected before IR publication', flush=True)
