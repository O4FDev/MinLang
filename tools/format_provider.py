"""Resolve an opt-in SHA-256/libarchive provider and fingerprint its actual inputs.

MINYAR_SHA256_PREFIX and MINYAR_TARARCHIVE_PREFIX select one installed prefix.
MSYS2 requires the compiler and provider to belong to the active MINGW_PREFIX.
Stable APIs may use a shared library; advanced zstd selection is separate.
"""
import hashlib
import json
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
    'lz4': ('liblz4', 'lz4', 'lz4.h', 'liblz4'),
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


def _image_probe(apis, windows, shared, dll_name):
    if windows:
        implementation = '''#include <windows.h>
#include <stdio.h>
static int provider_image(const void *address) {
    HMODULE module;
    char path[32768];
    DWORD length;
    if (!address) return 0;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)address,
            &module)) return 0;
    length = GetModuleFileNameA(module, path, sizeof(path));
    if (!length || length >= sizeof(path)) return 0;
    return puts(path) >= 0;
}
'''
    else:
        implementation = '''#include <dlfcn.h>
#include <stdio.h>
static int provider_image(const void *address) {
    Dl_info image;
    if (!dladdr(address, &image) || !image.dli_fname) return 0;
    return puts(image.dli_fname) >= 0;
}
'''
    # Non-PIE ELF function addresses may point to the executable's PLT. Look
    # up dynamic API addresses before dladdr instead of fingerprinting that
    # trampoline as the provider. Static providers use their executable image.
    if windows and dll_name:
        # MinGW headers need not mark these APIs dllimport: &api can address an
        # executable import thunk. GetModuleHandle does not load/redirect a DLL;
        # obtain exports from the normally loaded import module, then identify
        # each export's actual image (including DLL export forwarders).
        module = f'GetModuleHandleA({json.dumps(dll_name)})'
        addresses = [f'(const void *)GetProcAddress({module}, "{api}")' for api in apis]
    else:
        addresses = [f'dlsym(RTLD_DEFAULT, "{api}")' if shared and not windows else
                     f'(const void *)&{api}' for api in apis]
    calls = '\n'.join(f'    if (!provider_image({address})) return 3;'
                      for address in addresses)
    return implementation, calls


def _probe_source(kind, identify=False, windows=False, shared=False, dll_name=None):
    if kind == 'sha256':
        source = '''#define OPENSSL_SUPPRESS_DEPRECATED
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
        apis = ('SHA256_Init', 'SHA256_Update', 'SHA256_Final', 'OpenSSL_version_num')
    elif kind == 'lz4':
        source = '''#include <lz4.h>
#include <string.h>
_Static_assert(sizeof(void *) == 8, "64-bit provider required");
int main(void) {
    char packed[32], plain[8];
    if (LZ4_VERSION_NUMBER < 10903 || LZ4_versionNumber() != LZ4_VERSION_NUMBER) return 1;
    int size = LZ4_compress_default("erofs", packed, 5, sizeof(packed));
    if (size <= 0 || LZ4_decompress_safe(packed, plain, size, sizeof(plain)) != 5) return 2;
    return memcmp(plain, "erofs", 5) != 0;
}
'''
        apis = ('LZ4_versionNumber', 'LZ4_compress_default', 'LZ4_decompress_safe')
    else:
        source = '''#include <archive.h>
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
        apis = ('archive_version_number', 'archive_read_new', 'archive_read_free',
                'archive_entry_new', 'archive_entry_free')
    if identify:
        implementation, calls = _image_probe(apis, windows, shared, dll_name)
        source = '#ifndef _GNU_SOURCE\n#define _GNU_SOURCE\n#endif\n' + implementation + source
        source = source.replace('int main(void) {', 'int main(void) {\n' + calls)
    return source


def _runtime_dll(library, prefix, stem):
    # A MinGW import archive records the DLL name in its .idata entries. Match
    # that exact runtime file, rather than fingerprinting every similarly named
    # DLL and allowing the normal loader to choose a different one.
    names = {value.decode('ascii') for value in re.findall(
        re.escape(stem.encode()) + rb'[^\x00/\\\r\n]*?\.dll\x00',
        library.read_bytes(), re.IGNORECASE)}
    names = {value.rstrip('\0') for value in names}
    if len(names) != 1:
        raise ValueError(f'cannot identify one runtime DLL in import archive {library}')
    runtime = (prefix / 'bin' / names.pop()).resolve()
    if not runtime.is_file() or prefix not in runtime.parents:
        raise ValueError(f'provider runtime DLL is missing from {prefix / "bin"}')
    return runtime


def provider_info(kind, clang='clang', compile_flags=(), link_flags=()):
    """Validate effective flags; return additive argv and actual input identity.

    The probe inherits the consumer's loader environment unchanged. Its runtime
    identity is valid for that environment; changing it requires re-resolution.
    """
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
    if not windows and any('\\' in str(path) for path in (prefix, include, lib)):
        raise ValueError(f'{kind} literal backslash provider paths are unsupported '
                         'by Clang Make dependencies; use a prefix without backslashes')
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
    imported = windows and library.name.endswith('.dll.a')
    runtime_library = (_runtime_dll(library, prefix, stem) if imported else
                       library if shared else None)
    if shared:
        libraries += ['-Xlinker', '-rpath', '-Xlinker', str(library.parent)]
    with tempfile.TemporaryDirectory(prefix='minyar-format-provider-') as directory:
        source = Path(directory) / 'probe.c'
        binary = Path(directory) / ('probe.exe' if windows else 'probe')
        source.write_text(_probe_source(kind, identify=True, windows=windows, shared=shared,
                                       dll_name=runtime_library.name if imported else None))
        command = [clang, *compile_flags, *cflags]
        output = _output([*command, '-M', '-MT', 'minyar_provider', str(source)])
        # Clang's Make dependency escaping uses backslash-newline and escaped
        # spaces. A stable target name avoids drive-letter colons at the split.
        paths = _dependency_paths(output)
        headers = set()
        for value in paths:
            path = host_path(value)
            physical = path.resolve()
            if physical == source.resolve():
                continue
            # Check lexical names too: a provider-owned header may be a symlink
            # whose target no longer has an OpenSSL/archive filename.
            if kind == 'sha256':
                owned = ('openssl' in path.parts or 'openssl' in physical.parts
                         or any(p.name in ('opensslconf.h', 'configuration.h', 'opensslv.h')
                                for p in (path, physical)))
            elif kind == 'lz4':
                owned = any(p.name.startswith('lz4') for p in (path, physical))
            else:
                owned = any(p.name == 'archive.h' or p.name.startswith('archive_')
                            for p in (path, physical))
            if owned and prefix not in physical.parents:
                raise ValueError(f'{kind} provider-owned header {physical} must '
                                 f'belong to provider prefix {prefix}')
            headers.add(physical)
        headers = sorted(headers)
        primary = (include / header).resolve()
        if primary not in headers:
            raise ValueError(f'{kind} compiler did not select its matched primary header')
        # dladdr needs libdl on older Linux libc. This diagnostic dependency is
        # probe-only and does not change the consumer's public link policy.
        identity_flags = ['-ldl'] if not windows and platform.system() != 'Darwin' else []
        result = subprocess.run([*command, str(source), *link_flags, *libraries,
                                 *identity_flags, '-o', str(binary)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError(f'{kind} matched provider compile/link probe failed:\n{result.stderr}')
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        images = [host_path(value).resolve() for value in result.stdout.splitlines()]
        expected = runtime_library or binary.resolve()
        count = 4 if kind == 'sha256' else 3 if kind == 'lz4' else 5
        if len(images) != count:
            raise ValueError(f'{kind} provider image identification/API probe failed '
                             f'(status {result.returncode})')
        for actual in images:
            if actual != expected or (runtime_library and prefix not in actual.parents):
                raise ValueError(f'{kind} loaded provider image {actual} does not match '
                                 f'selected library {library} (expected image {expected}); '
                                 'check install name/SONAME and the consumer loader environment')
        if result.returncode:
            raise ValueError(f'{kind} provider version/64-bit API probe failed '
                             f'(status {result.returncode})')
        # Only a validated actual image may become runtime/cache identity.
        actual_library = images[0] if runtime_library else None
        inputs = sorted(set([*headers, library, *([actual_library] if actual_library else [])]))
        digest = hashlib.sha256()
        digest.update(json.dumps([kind, clang, list(compile_flags), list(link_flags)],
                                 separators=(',', ':')).encode() + b'\0')
        receipt = []
        for path in inputs:
            content = path.read_bytes()
            value = hashlib.sha256(content).hexdigest()
            digest.update(str(path).encode() + b'\0' + bytes.fromhex(value))
            receipt.append({'path': str(path), 'sha256': value})
    fingerprint = digest.hexdigest()
    return {'kind': kind, 'prefix': str(prefix), 'include': str(include),
            'library': str(library), 'inputs': receipt, 'sha256': fingerprint,
            'runtime_library': str(actual_library) if actual_library else None,
            'clang': clang, 'compile_flags': list(compile_flags), 'link_flags': list(link_flags),
            'cflags': [*cflags, '-DMINYAR_FORMAT_PROVIDER_' + fingerprint[:16].upper() + '=1'],
            'libraries': libraries}


def format_provider(kind, clang='clang', compile_flags=(), link_flags=()):
    info = provider_info(kind, clang, compile_flags, link_flags)
    return info['cflags'], info['libraries']


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=CONFIG)
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--flags', default='')
    parser.add_argument('--link-flags', default='')
    arguments = parser.parse_args()
    print(json.dumps(provider_info(arguments.kind, arguments.clang,
                                   shlex.split(arguments.flags),
                                   shlex.split(arguments.link_flags)), indent=2))
