





from pathlib import Path
import os
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'build/thread-compiler.min').read_text()
source = source[:source.index('\nfunction main(')] + r'''
function main() {
    let output: List<Text> = []
    let globals: List<Text> = ["; minyar-thread-runtime: 1\n", "; minyar-thread-entry: worker\n"]
    let probe = argument(0)
    let getter = "\"minyar.constant|minyar_module_2_data|load\""
    if probe == "managed" || probe == "managed-helper" || probe == "main-managed" {
        globals.add("; minyar-module-constant: minyar_module_2_data|managed\n")
    } else if probe != "unknown" {
        globals.add("; minyar-module-constant: minyar_module_2_data|scalar\n")
    }
    let caller = "worker"
    if probe == "main-managed" || probe == "initializer" { caller = "main" }
    if probe == "managed-helper" {
        threadNote(output, "worker", "call", "helper", "2()")
        caller = "helper"
    }
    threadNote(output, caller, "runtime", getter, "2()")
    if probe == "initializer" {
        threadNote(output, "constant minyar_module_2_data", "call", "unsafeHelper", "1()")
        threadNote(output, "unsafeHelper", "native", "minyar_machine_address", "1(8)")
    }
    if probe == "indirect" { threadNote(output, "worker", "indirect", "callback", "1(1)") }
    threadCheckGraph(output, globals)
    print("checked graph")
}
'''
with tempfile.TemporaryDirectory(prefix='minyar-thread-effects-') as temporary:
    work = Path(temporary)
    program = work / 'probe.min'
    llvm = work / 'probe.ll'
    binary = work / 'probe'
    program.write_text(source)
    compiled = subprocess.run([str(ROOT / 'build/minyarc'), str(program), str(llvm)],
                              capture_output=True, text=True, timeout=60)
    if compiled.returncode:
        raise SystemExit(compiled.stdout + compiled.stderr)
    clang = shlex.split(os.environ.get('LLVM_CC', 'clang'))
    subprocess.run([*clang, '-O2', '-Wno-override-module', str(llvm),
                    str(ROOT / 'build/minyar-compiler-runtime.ll'), '-lm', '-o', str(binary)],
                   check=True, timeout=120)
    for probe in ('managed', 'managed-helper', 'main-managed', 'scalar', 'unknown', 'initializer', 'indirect'):
        result = subprocess.run([str(binary), probe], capture_output=True, text=True, timeout=10)
        allowed = probe in ('main-managed', 'scalar')
        if allowed:
            assert (result.returncode, result.stdout, result.stderr) == (0, 'checked graph\n', ''), result
        else:
            assert result.returncode != 0, (probe, result)
            diagnostic = 'unreviewed module constant getter' if probe == 'unknown' else 'unsafe thread effect'
            assert diagnostic in result.stderr + result.stdout, (probe, result)
        print(probe + ': ' + ('accepted' if allowed else 'rejected'))
