"""Select matched codec headers/absolute archives; never dynamic advanced zstd.

Overrides: MINYAR_ZSTD_PREFIX / MINYAR_ZLIB_PREFIX name one provider prefix.
Otherwise pkg-config selects the provider, with Homebrew fallback on Darwin.
MSYS uses only the active MINGW_PREFIX and requires its Clang/toolchain + CRT.
The compile/link/run probe checks 64-bit ABI and header/library version equality;
linker rejects incompatible architecture/CRT. Platform qualification still belongs
in the relevant platform suite (a Linux pass is no Windows ABI qualification).
"""
import hashlib
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tempfile


def _output(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def codec_provider(codec, clang='clang'):
    if codec not in ('zstd', 'deflate'):
        raise ValueError('unknown codec')
    zstd = codec == 'zstd'
    name, package, header, archive = ('zstd', 'libzstd', 'zstd.h', 'libzstd.a') if zstd else ('zlib', 'zlib', 'zlib.h', 'libz.a')
    override = os.environ.get('MINYAR_' + name.upper() + '_PREFIX')
    msys = os.environ.get('MINGW_PREFIX')
    windows = platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN'))
    if override:
        prefix = Path(override).resolve()
        include, lib = prefix / 'include', prefix / 'lib'
        dependencies = []
    elif windows:
        if not msys:
            raise ValueError(f'{name} needs the active MSYS2 MINGW_PREFIX or an explicit matched provider prefix')
        prefix = Path(msys).resolve()
        include, lib = prefix / 'include', prefix / 'lib'
        dependencies = []
    else:
        try:
            prefix = Path(_output(['pkg-config', '--variable=prefix', package])).resolve()
            include = Path(_output(['pkg-config', '--variable=includedir', package])).resolve()
            lib = Path(_output(['pkg-config', '--variable=libdir', package])).resolve()
            dependencies = [a for a in shlex.split(_output(['pkg-config', '--libs', '--static', package]))
                            if a not in ('-lzstd', '-lz') and not a.startswith('-L')]
        except (FileNotFoundError, subprocess.CalledProcessError):
            if platform.system() != 'Darwin' or not shutil.which('brew'):
                raise ValueError(f'install matched {name} development headers and static archive, or set MINYAR_{name.upper()}_PREFIX') from None
            prefix = Path(_output(['brew', '--prefix', name])).resolve()
            include, lib, dependencies = prefix / 'include', prefix / 'lib', []
    prefix, include, lib = prefix.resolve(), include.resolve(), lib.resolve()
    if not zstd and platform.system() == 'Darwin' and prefix not in lib.parents:
        # Apple's zlib.pc gives SDK includes but a system /usr/lib link directory.
        lib = prefix / 'lib'
    if not prefix.is_dir() or not (include / header).is_file():
        raise ValueError(f'{name} header missing from provider {prefix}')
    # Ubuntu pkg-config can say /usr/lib while the archive lives in its multiarch directory.
    candidates = [lib / archive]
    if not override and not windows:
        selected = _output([clang, '-print-file-name=' + archive])
        if selected != archive:
            candidates.append(Path(selected).resolve())
    if not zstd and platform.system() == 'Darwin':
        # SDK zlib is a stable public API; Apple's SDK supplies a link stub.
        candidates += [lib / 'libz.tbd', lib / 'libz.dylib']
    selected = next((p.resolve() for p in candidates if p.is_file()), None)
    if selected is None or prefix not in selected.parents or prefix not in include.parents:
        raise ValueError(f'{name} requires {archive} and {header} from the same provider prefix {prefix}')
    if windows:
        active = Path(msys).resolve() if msys else prefix
        executable = Path(shutil.which(clang) or clang).resolve()
        if active != prefix or active not in executable.parents:
            raise ValueError('codec provider and compiler must use the same MSYS2 prefix/CRT')
    identity = hashlib.sha256()
    for path in [include / header, *([include / 'zstd_errors.h'] if zstd else [include / 'zconf.h']), selected]:
        identity.update(path.read_bytes())
    fingerprint = identity.hexdigest()
    cflags = ['-isystem', str(include), '-DMINYAR_CODEC_PROVIDER_' + fingerprint[:16].upper() + '=1']
    libraries = [str(selected), *dependencies]
    probe = ('#include <zstd.h>\nint main(void) { return ZSTD_versionNumber() != ZSTD_VERSION_NUMBER; }\n' if zstd else
             '#include <zlib.h>\n#include <string.h>\nint main(void) { return strcmp(zlibVersion(), ZLIB_VERSION) != 0; }\n')
    probe = '_Static_assert(sizeof(void *) == 8, "64-bit provider required");\n' + probe
    with tempfile.TemporaryDirectory(prefix='minyar-codec-provider-') as tmp:
        source, binary = Path(tmp) / 'probe.c', Path(tmp) / ('probe.exe' if windows else 'probe')
        source.write_text(probe)
        result = subprocess.run([clang, *cflags, str(source), *libraries, '-o', str(binary)], capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f'{name} matched static provider ABI probe failed:\n' + result.stderr)
        if subprocess.run([str(binary)], capture_output=True).returncode:
            raise ValueError(f'{name} header/static archive version mismatch')
    return cflags, libraries
