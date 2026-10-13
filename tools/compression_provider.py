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
import re
import shlex
import shutil
import subprocess
import tempfile
from host_paths import host_path


def _output(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def _static_archive(path, clang, required):
    """Require embedded relocatable objects, not a DSO, script or import lib."""
    data = path.read_bytes()
    def reject(reason):
        raise ValueError(f'{path} must be a real static archive: {reason}')
    if not data.startswith(b'!<arch>\n'):
        reject('thin archives, shared libraries and linker scripts are unsupported')
    offset, objects = 8, 0
    while offset < len(data):
        header = data[offset:offset + 60]
        if len(header) != 60 or header[58:60] != b'`\n':
            reject('malformed member header')
        try:
            size = int(header[48:58])
        except ValueError:
            reject('malformed member size')
        if size < 0 or offset + 60 + size > len(data):
            reject('truncated member')
        name = header[:16].decode('ascii', errors='replace').strip()
        member = data[offset + 60:offset + 60 + size]
        offset += 60 + size + (size & 1)
        if name.startswith('#1/'):
            try:
                length = int(name[3:])
            except ValueError:
                reject('malformed extended member name')
            if length < 0 or length > len(member):
                reject('truncated extended member name')
            name = member[:length].rstrip(b'\0').decode('utf-8', errors='replace')
            member = member[length:]
        if name in ('/', '//', '/SYM64/') or name.startswith('__.SYMDEF'):
            continue
        objects += 1
        if member.startswith(b'\x7fELF'):
            if len(member) < 20 or member[5] not in (1, 2):
                reject('invalid ELF member')
            endian = 'little' if member[5] == 1 else 'big'
            if int.from_bytes(member[16:18], endian) != 1:  # ET_REL
                reject('ELF member is not relocatable')
        elif member[:4] in (b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe',
                            b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf'):
            endian = 'little' if member[0] in (0xce, 0xcf) else 'big'
            if len(member) < 28 or int.from_bytes(member[12:16], endian) != 1:
                reject('Mach-O member is not MH_OBJECT')
        elif len(member) >= 20 and int.from_bytes(member[:2], 'little') in (0x8664, 0xaa64, 0x14c):
            count = int.from_bytes(member[2:4], 'little')
            optional = int.from_bytes(member[16:18], 'little')
            flags = int.from_bytes(member[18:20], 'little')
            if optional or flags & 0x2002 or not count or 20 + 40 * count > len(member):
                reject('COFF member is not a relocatable object')
            for index in range(count):
                section = member[20 + 40 * index:28 + 40 * index].rstrip(b'\0')
                if section.startswith(b'.idata'):
                    reject('COFF import-library member')
        else:
            reject('unsupported object or short COFF import member')
    if offset != len(data) or not objects:
        reject('empty or malformed archive')
    compiler = Path(shutil.which(clang) or clang).resolve()
    nm = next((str(p) for p in (compiler.parent / 'llvm-nm', compiler.parent / 'nm')
               if p.is_file()), None) or shutil.which('llvm-nm') or shutil.which('nm')
    if not nm:
        reject('install llvm-nm or nm to verify static symbol definitions')
    try:
        symbols = _output([nm, '-g', str(path)])
    except (OSError, subprocess.CalledProcessError) as error:
        reject(f'cannot inspect symbol definitions ({error})')
    definitions = set(re.findall(r'^\s*[0-9a-fA-F]+\s+T\s+_?(\w+)\s*$', symbols, re.MULTILINE))
    missing = set(required) - definitions
    if missing:
        reject('missing static definitions: ' + ', '.join(sorted(missing)))


def codec_provider(codec, clang='clang', compile_flags=(), link_flags=()):
    if codec not in ('zstd', 'deflate'):
        raise ValueError('unknown codec')
    zstd = codec == 'zstd'
    name, package, header, archive = ('zstd', 'libzstd', 'zstd.h', 'libzstd.a') if zstd else ('zlib', 'zlib', 'zlib.h', 'libz.a')
    override = os.environ.get('MINYAR_' + name.upper() + '_PREFIX')
    msys = os.environ.get('MINGW_PREFIX')
    windows = platform.system() == 'Windows' or platform.system().startswith(('MSYS', 'MINGW', 'CYGWIN'))
    if override:
        prefix = host_path(override).resolve()
        include, lib = prefix / 'include', prefix / 'lib'
        dependencies = []
    elif windows:
        if not msys:
            raise ValueError(f'{name} needs the active MSYS2 MINGW_PREFIX or an explicit matched provider prefix')
        prefix = host_path(msys).resolve()
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
    if os.name != 'nt' and any('\\' in str(path) for path in (prefix, include, lib)):
        raise ValueError('literal backslash provider paths are unsupported on POSIX; select a prefix without backslashes')
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
    if zstd:
        _static_archive(selected, clang, ('ZSTD_versionNumber', 'ZSTD_createCDict_advanced',
                                         'ZSTD_createDDict_advanced'))
    elif selected.suffix == '.a':
        _static_archive(selected, clang, ('zlibVersion', 'deflateInit2_', 'inflateInit2_'))
    cflags = ['-isystem', str(include)]
    libraries = [str(selected), *dependencies]
    probe = ('''#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>
#include <zstd_errors.h>
int main(void) {
    const char raw[] = "raw dictionary";
    ZSTD_customMem memory = {0};
    ZSTD_CDict *c = ZSTD_createCDict_advanced(raw, sizeof(raw), ZSTD_dlm_byCopy,
        ZSTD_dct_rawContent, ZSTD_getCParams(1, 0, sizeof(raw)), memory);
    ZSTD_DDict *d = ZSTD_createDDict_advanced(raw, sizeof(raw), ZSTD_dlm_byCopy,
        ZSTD_dct_rawContent, memory);
    int failed = !c || !d || ZSTD_versionNumber() != ZSTD_VERSION_NUMBER;
    ZSTD_freeCDict(c); ZSTD_freeDDict(d); return failed;
}
''' if zstd else
             '#include <zlib.h>\n#include <string.h>\nint main(void) { return strcmp(zlibVersion(), ZLIB_VERSION) != 0; }\n')
    probe = '_Static_assert(sizeof(void *) == 8, "64-bit provider required");\n' + probe
    with tempfile.TemporaryDirectory(prefix='minyar-codec-provider-') as tmp:
        source, binary = Path(tmp) / 'probe.c', Path(tmp) / ('probe.exe' if windows else 'probe')
        source.write_text(probe)
        command = [clang, *compile_flags, *cflags]
        # Include forced headers too; -H alone omits them on Apple Clang.
        trace = subprocess.run([*command, '-M', '-MT', 'minyar_codec', str(source)],
                               capture_output=True, text=True, timeout=30)
        if trace.returncode:
            raise ValueError(f'{name} provider header probe failed:\n{trace.stderr}')
        words = re.findall(r'(?:\\.|[^\s])+', trace.stdout.replace('\\\n', '').partition(':')[2])
        headers = sorted({host_path(re.sub(r'\\([ \t#\\])', r'\1', word).replace('$$', '$')).resolve()
                          for word in words if not word.endswith('probe.c')})
        owned = {'zstd.h', 'zstd_errors.h'} if zstd else {'zlib.h', 'zconf.h'}
        primary = (include / header).resolve()
        if primary not in headers or any(prefix not in path.parents
                                        for path in headers if path.name in owned):
            raise ValueError(f'{name} primary and secondary headers must belong to provider prefix {prefix}')
        identity = hashlib.sha256()
        for path in [*headers, selected]:
            identity.update(str(path).encode() + b'\0' + path.read_bytes())
        fingerprint = identity.hexdigest()
        cflags += ['-DMINYAR_CODEC_PROVIDER_' + fingerprint[:16].upper() + '=1']
        result = subprocess.run([clang, *compile_flags, *cflags, str(source), *libraries,
                                 *link_flags, '-o', str(binary)], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError(f'{name} matched static provider ABI probe failed:\n' + result.stderr)
        if subprocess.run([str(binary)], capture_output=True, timeout=30).returncode:
            raise ValueError(f'{name} header/static archive version mismatch')
    return cflags, libraries


if __name__ == '__main__':
    import argparse
    import json
    from host_paths import pinned_llvm
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=('zstd', 'deflate'))
    parser.add_argument('--clang', required=True)
    parser.add_argument('--compile-flag', action='append', default=[])
    parser.add_argument('--link-flag', action='append', default=[])
    arguments = parser.parse_args()
    pinned_llvm(arguments.clang)
    cflags, libraries = codec_provider(arguments.kind, arguments.clang,
                                      arguments.compile_flag, arguments.link_flag)
    print(json.dumps({'cflags': cflags, 'libraries': libraries}))
