"""Platform libraries for direct Clang invocations in standalone test scripts."""
import os
import platform
import re
import shutil
import subprocess


def windows_host():
    """MSYS Python has os.name == 'posix' while its native tools target Windows."""
    system = platform.system()
    return system == 'Windows' or system.startswith(('MSYS', 'MINGW', 'CYGWIN'))


def asan_leak_options():
    """LSan is supported by our Linux native provider, not Windows/macOS."""
    return 'detect_leaks=' + ('1' if platform.system() == 'Linux' else '0')


def clang_command(arguments):
    """Keep libm after its users, and avoid linker arguments in compile phases."""
    arguments = list(arguments)
    compile_only = ('-c', '-S', '-E', '-fsyntax-only', '--version', '-v')
    if platform.system() != 'Darwin' and not windows_host() and not any(
            option in arguments for option in compile_only):
        arguments = [argument for argument in arguments if argument != '-lm']
        arguments.append('-lm')
    return arguments


def native_path(path):
    # MSYS translates command arguments to native paths before launching Clang
    # and Minyar; diagnostics use that same spelling.
    if platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
        return subprocess.check_output(['cygpath', '-m', str(path)], text=True).strip()
    return str(path).replace('\\', '/') if os.name == 'nt' else str(path)


def launcher_command(root):
    """Invoke the shell launcher explicitly under native Windows Python."""
    command = [str(root / 'minyar')]
    if os.name == 'nt':
        bash = shutil.which('bash')
        if not bash:
            raise RuntimeError('Bash is required for the native Windows launcher')
        command.insert(0, bash)
    return command


def without_asm_source_locations(ir):
    """Blank inline-asm `!srcloc` values: they are raw source offsets, not code.

    Any extra -D option or header line before an asm statement shifts them, so
    identity checks of LLVM text compare everything else exactly.
    """
    text = ir.decode() if isinstance(ir, bytes) else ir
    ids = set(re.findall(r'!srcloc !(\d+)', text))
    if ids:
        text = re.sub(r'^!(\d+) = !\{[^\n]*\}$',
                      lambda m: '!' + m[1] + ' = !{srcloc}' if m[1] in ids else m[0],
                      text, flags=re.M)
    return text.encode() if isinstance(ir, bytes) else text
