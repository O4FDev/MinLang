"""Platform libraries for direct Clang invocations in standalone test scripts."""
import os
import platform
import subprocess


def windows_host():
    """MSYS Python has os.name == 'posix' while its native tools target Windows."""
    system = platform.system()
    return system == 'Windows' or system.startswith(('MSYS', 'MINGW', 'CYGWIN'))


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
