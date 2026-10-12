"""Resolve an opt-in SHA-256/libarchive provider and fingerprint its actual inputs.

MINYAR_SHA256_PREFIX and MINYAR_TARARCHIVE_PREFIX select one installed prefix.
MSYS2 requires the compiler and provider to belong to the active MINGW_PREFIX.
Stable APIs may use a shared library; advanced zstd selection is separate.
"""
import hashlib
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import tempfile

from host_paths import host_path


CONFIG = {
    'sha256': ('libcrypto', 'openssl@3', 'openssl/sha.h', 'libcrypto'),
    'tararchive': ('libarchive', 'libarchive', 'archive.h', 'libarchive'),
}


def _output(arguments):
    return subprocess.check_output(arguments, text=True, stderr=subprocess.PIPE,
                                   timeout=30).strip()


def _windows():
    return platform.system() == 'Windows' or platform.system().startswith(
        ('MSYS', 'MINGW', 'CYGWIN'))


def _dependency_paths(output):
    """Decode Clang's Make escaping, where quote characters are ordinary bytes."""
    words = re.findall(r'(?:\\.|[^\s])+',
                       output.replace('\\\n', '').partition(':')[2])
    return [re.sub(r'\\([ \t#\\])', r'\1', value).replace('$$', '$')
            for value in words]


def _probe_source(kind):
    if kind == 'sha256':
        return '''#define OPENSSL_SUPPRESS_DEPRECATED
#include <openssl/sha.h>
#include <openssl/crypto.h>
#include <string.h>
_Static_assert(sizeof(void *) == 8, "64-bit provider required");
int main(void) {
    SHA256_CTX state;
    unsigned char digest[32];
    static const unsigned char expected[32] = {
        0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,
        0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,
        0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,
        0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad
    };
    if (OpenSSL_version_num() != OPENSSL_VERSION_NUMBER) return 1;
    if (!SHA256_Init(&state) || !SHA256_Update(&state, "abc", 3)
        || !SHA256_Final(digest, &state)) return 2;
    return memcmp(digest, expected, 32) != 0;
}
'''
    return '''#include <archive.h>
#include <archive_entry.h>
_Static_assert(sizeof(void *) == 8, "64-bit provider required");
int main(void) {
    struct archive *reader;
    struct archive_entry *entry;
    if (archive_version_number() != ARCHIVE_VERSION_NUMBER) return 1;
    reader = archive_read_new();
    entry = archive_entry_new();
    if (!reader || !entry) return 2;
    archive_entry_free(entry);
    return archive_read_free(reader) != ARCHIVE_OK;
}
'''


def provider_info(kind, clang='clang', compile_flags=()):
    """Return literal compile/link argv and a receipt for the selected provider."""
    if kind not in CONFIG:
        raise ValueError('unknown format provider: ' + kind)
    package, formula, header, stem = CONFIG[kind]
    override = os.environ.get('MINYAR_' + kind.upper() + '_PREFIX')
    active = os.environ.get('MINGW_PREFIX')
    windows = _windows()
    dependencies = []
    if override or windows:
        value = override or active
        if not value:
            raise ValueError(f'{kind} requires an active MSYS2 MINGW_PREFIX '
                             'or an explicit matched provider prefix')
        prefix = host_path(value).resolve()
        include, lib = prefix / 'include', prefix / 'lib'
    else:
        try:
            prefix = host_path(_output(['pkg-config', '--variable=prefix', package])).resolve()
            include = host_path(_output(['pkg-config', '--variable=includedir', package])).resolve()
            lib = host_path(_output(['pkg-config', '--variable=libdir', package])).resolve()
            dependencies = [value for value in shlex.split(
                _output(['pkg-config', '--libs', '--static', package]))
                if value != '-l' + stem.removeprefix('lib') and not value.startswith('-L')]
        except (FileNotFoundError, subprocess.CalledProcessError):
            if platform.system() != 'Darwin' or not shutil.which('brew'):
                raise ValueError(f'install the {package} development package or set '
                                 f'MINYAR_{kind.upper()}_PREFIX') from None
            prefix = host_path(_output(['brew', '--prefix', formula])).resolve()
            include, lib = prefix / 'include', prefix / 'lib'
    if not (include / header).is_file() or prefix not in include.resolve().parents:
        raise ValueError(f'{kind} headers must belong to provider prefix {prefix}')
    if windows:
        executable = host_path(shutil.which(clang) or clang).resolve()
        active_prefix = host_path(active).resolve() if active else prefix
        if active_prefix != prefix or active_prefix not in executable.parents:
            raise ValueError('format provider and compiler must use the same MSYS2 prefix/CRT')
    names = ([stem + '.dll.a', stem + '.a'] if windows else
             [stem + '.dylib', stem + '.a'] if platform.system() == 'Darwin' else
             [stem + '.so', stem + '.a'])
    candidates = [lib / name for name in names]
    if not override and not windows:
        for name in names:
            selected = _output([clang, '-print-file-name=' + name])
            if selected != name:
                candidates.append(host_path(selected))
    library = next((path.resolve() for path in candidates if path.is_file()), None)
    if library is None or prefix not in library.parents:
        raise ValueError(f'{kind} library and headers must come from one provider prefix {prefix}')
    cflags = ['-I' + str(include)]
    libraries = [str(library), *dependencies]
    shared = not windows and ('.so' in library.name or library.suffix == '.dylib')
    if shared:
        libraries += ['-Xlinker', '-rpath', '-Xlinker', str(library.parent)]
    with tempfile.TemporaryDirectory(prefix='minyar-format-provider-') as directory:
        source = Path(directory) / 'probe.c'
        binary = Path(directory) / ('probe.exe' if windows else 'probe')
        source.write_text(_probe_source(kind))
        command = [clang, *compile_flags, *cflags]
        output = _output([*command, '-M', '-MT', 'minyar_provider', str(source)])
        # Clang's Make dependency escaping uses backslash-newline and escaped
        # spaces. A stable target name avoids drive-letter colons at the split.
        paths = _dependency_paths(output)
        headers = sorted({host_path(value).resolve() for value in paths
                          if host_path(value).resolve() != source.resolve()})
        primary = (include / header).resolve()
        if primary not in headers:
            raise ValueError(f'{kind} compiler did not select its matched primary header')
        inputs = [*headers, library]
        if windows:
            # An import archive alone is not the runtime identity.
            runtime_libraries = sorted((prefix / 'bin').glob(stem + '*.dll'))
            if not runtime_libraries:
                raise ValueError(f'{kind} provider runtime DLL is missing from {prefix / "bin"}')
            inputs += runtime_libraries
        digest = hashlib.sha256()
        receipt = []
        for path in inputs:
            content = path.read_bytes()
            value = hashlib.sha256(content).hexdigest()
            digest.update(str(path).encode() + b'\0' + bytes.fromhex(value))
            receipt.append({'path': str(path), 'sha256': value})
        result = subprocess.run([*command, str(source), *libraries, '-o', str(binary)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError(f'{kind} matched provider compile/link probe failed:\n{result.stderr}')
        environment = dict(os.environ)
        if windows:
            environment['PATH'] = str(prefix / 'bin') + os.pathsep + environment.get('PATH', '')
        elif shared:
            variable = 'DYLD_LIBRARY_PATH' if platform.system() == 'Darwin' else 'LD_LIBRARY_PATH'
            environment[variable] = str(library.parent) + os.pathsep + environment.get(variable, '')
        result = subprocess.run([str(binary)], capture_output=True, timeout=30,
                                env=environment)
        if result.returncode:
            raise ValueError(f'{kind} provider version/64-bit API probe failed '
                             f'(status {result.returncode})')
    fingerprint = digest.hexdigest()
    return {'kind': kind, 'prefix': str(prefix), 'include': str(include),
            'library': str(library), 'inputs': receipt, 'sha256': fingerprint,
            'clang': clang, 'compile_flags': list(compile_flags),
            'cflags': [*cflags, '-DMINYAR_FORMAT_PROVIDER_' + fingerprint[:16].upper() + '=1'],
            'libraries': libraries}


def format_provider(kind, clang='clang', compile_flags=()):
    info = provider_info(kind, clang, compile_flags)
    return info['cflags'], info['libraries']


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=CONFIG)
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--flags', default='')
    arguments = parser.parse_args()
    print(json.dumps(provider_info(arguments.kind, arguments.clang,
                                   shlex.split(arguments.flags)), indent=2))
