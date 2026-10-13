"""Translate native paths in the caller's filesystem namespace."""
from pathlib import Path
import platform
import os
import shutil
import re
import subprocess


def host_path(value):
    # Native Windows Python can hand an absolute drive path to MSYS Python.
    # MSYS Path.resolve otherwise drops its drive letter (C:/ becomes /:/).
    native = str(value)
    windows_spelling = re.match(r'^[A-Za-z]:[\\/]', native) or native.startswith('\\\\')
    if windows_spelling and platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN')):
        value = subprocess.check_output(['cygpath', '-u', str(value)],
                                             text=True).rstrip('\r\n')
    return Path(value)


LLVM_VERSION = "23.1.2"


def pinned_llvm(command=None):
    if command is None:
        command = os.environ.get("MINYAR_CLANG", os.environ.get("LLVM_CC",
                    "clang" if platform.system() == "Darwin" else "clang-23"))
    resolved = shutil.which(command)
    if resolved is None:
        raise ValueError(f"Minyar requires LLVM {LLVM_VERSION}; Clang executable not found: {command}. Select it with MINYAR_CLANG or LLVM_CC.")
    result = subprocess.run([resolved, "--version"], capture_output=True, text=True, timeout=10)
    match = re.search(r"\bclang version (\d+\.\d+\.\d+)(?=\s|$)", result.stdout)
    if result.returncode or not match or match[1] != LLVM_VERSION:
        actual = result.stdout.splitlines()[0] if result.stdout else result.stderr.strip()
        raise ValueError(f"Minyar requires LLVM {LLVM_VERSION}; unsupported compiler {command}: {actual}")
    return resolved


def pinned_lld(command):
    resolved = shutil.which(command)
    if resolved is None:
        raise ValueError(f"Minyar requires LLVM {LLVM_VERSION}; LLD executable not found: {command}")
    result = subprocess.run([resolved, "--version"], capture_output=True, text=True, timeout=10)
    match = re.search(r"\bLLD (\d+\.\d+\.\d+)(?=\s|$)", result.stdout)
    if result.returncode or not match or match[1] != LLVM_VERSION:
        actual = result.stdout.splitlines()[0] if result.stdout else result.stderr.strip()
        raise ValueError(f"Minyar requires LLVM {LLVM_VERSION}; unsupported linker {command}: {actual}")
    return resolved
