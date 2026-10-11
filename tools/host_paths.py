"""Translate native paths in the caller's filesystem namespace."""
from pathlib import Path
import platform
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
