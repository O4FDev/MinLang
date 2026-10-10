#!/usr/bin/env python3
"""Launcher for the experimental native frontend and older Swift source prototype.

main(native=True) passes original files directly to the pinned compiler on
macOS or Linux. The default main() path lowers source for Xcode on macOS.
See docs/native-frontend.md and docs/linux-desktop.md for compatibility limits.
"""
import argparse
import importlib.util
import json
import os
import platform
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass


@dataclass
class Token:
    kind: str
    text: str


def lex(source):
    """Keep literal/comment contents intact, including nested interpolations."""
    result = []
    i = 0
    while i < len(source):
        start = i
        if source[i].isspace():
            while i < len(source) and source[i].isspace():
                i += 1
            kind = 'trivia'
        elif source.startswith('//', i):
            end = source.find('\n', i)
            i = len(source) if end < 0 else end
            kind = 'trivia'
        elif source.startswith('/*', i):
            i += 2
            depth = 1
            while i < len(source) and depth:
                if source.startswith('/*', i):
                    depth += 1
                    i += 2
                elif source.startswith('*/', i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ValueError('unterminated block comment')
            kind = 'trivia'
        elif re.match(r'(?:\#*"|\#+/)', source[i:]):
            hashes = len(source[i:]) - len(source[i:].lstrip('#'))
            i += hashes
            quote = '"""' if source.startswith('"""', i) else source[i]
            i += len(quote)
            close = quote + '#' * hashes
            escape = '\\' + '#' * hashes
            pieces = [source[start:i]]
            segment = i
            while i < len(source):
                if source.startswith(close, i):
                    i += len(close)
                    pieces.append(source[segment:i])
                    break
                if source.startswith(escape + '(', i):
                    pieces.append(source[segment:i + len(escape) + 1])
                    i += len(escape) + 1
                    expression_start = i
                    # Lex the suffix so strings/comments containing ')' cannot
                    # terminate an interpolation. Stop at its matching paren.
                    depth = 1
                    expression = []
                    for token in lex_until_interpolation_end(source[i:]):
                        i += len(token.text)
                        if token.kind == 'symbol' and token.text == '(':
                            depth += 1
                        if token.kind == 'symbol' and token.text == ')':
                            depth -= 1
                            if depth == 0:
                                break
                        expression.append(token)
                    if depth:
                        raise ValueError('unterminated string interpolation')
                    pieces.append(lower(source[expression_start:i - 1], fragment=True))
                    pieces.append(')')
                    segment = i
                elif source.startswith(escape, i):
                    i += len(escape) + 1
                else:
                    i += 1
            else:
                raise ValueError('unterminated string literal')
            result.append(Token('string', ''.join(pieces)))
            continue
        elif (source[i] == '/' and i + 1 < len(source) and not source[i + 1].isspace()
              and next((t.text for t in reversed(result) if t.kind != 'trivia'), None)
              in ('=', '(', '[', '{', ',', ':', 'return', 'case')):
            raise ValueError('use extended regex literals #/.../# in the native frontend')
        elif source[i] == '`':
            i = source.find('`', i + 1)
            if i < 0:
                raise ValueError('unterminated escaped identifier')
            i += 1
            kind = 'escaped'
        elif source[i].isalpha() or source[i] == '_':
            i += 1
            while i < len(source) and (source[i].isalnum() or source[i] == '_'):
                i += 1
            kind = 'identifier'
        else:
            i += 1
            kind = 'symbol'
        result.append(Token(kind, source[start:i]))
    return result


def lex_until_interpolation_end(source):
    # Find the expression boundary without lexing the trailing enclosing quote.
    # A small balanced scanner skips nested strings and comments as complete
    # tokens. Its offsets use the original text, before any keyword lowering.
    i = 0
    depth = 1
    while i < len(source):
        start = i
        if source.startswith('//', i):
            end = source.find('\n', i)
            i = len(source) if end < 0 else end
        elif source.startswith('/*', i):
            i += 2
            nesting = 1
            while i < len(source) and nesting:
                if source.startswith('/*', i):
                    nesting += 1
                    i += 2
                elif source.startswith('*/', i):
                    nesting -= 1
                    i += 2
                else:
                    i += 1
        elif re.match(r'(?:\#*"|\#+/)', source[i:]):
            hashes = len(source[i:]) - len(source[i:].lstrip('#'))
            i += hashes
            quote = '"""' if source.startswith('"""', i) else source[i]
            i += len(quote)
            close = quote + '#' * hashes
            escape = '\\' + '#' * hashes
            while i < len(source) and not source.startswith(close, i):
                if source.startswith(escape + '(', i):
                    i += len(escape) + 1
                    for token in lex_until_interpolation_end(source[i:]):
                        i += len(token.text)
                elif source.startswith(escape, i):
                    i += len(escape) + 1
                else:
                    i += 1
            if not source.startswith(close, i):
                raise ValueError('unterminated nested string')
            i += len(close)
        else:
            if source[i] == '(':
                depth += 1
            elif source[i] == ')':
                depth -= 1
            i += 1
            yield Token('symbol', source[start:i])
            if depth == 0:
                return
            continue
        yield Token('opaque', source[start:i])


def lower(source, fragment=False):
    tokens = lex(source)
    significant = [i for i, t in enumerate(tokens) if t.kind != 'trivia']
    output = [t.text for t in tokens]
    words = [tokens[i].text for i in significant]
    for p, index in enumerate(significant):
        token = tokens[index]
        if token.kind != 'identifier':
            continue
        if token.text == 'use':
            if fragment or p + 1 >= len(words):
                raise ValueError('expected use "ModuleName"')
            module = words[p + 1]
            if not re.fullmatch(r'"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*"', module):
                raise ValueError('native imports require an SDK/module name; local Minyar packages are not supported')
            if p + 2 < len(words) and words[p + 2] == 'as':
                raise ValueError('native imports do not support aliases; use "ModuleName" and ModuleName.Type')
            output[index] = 'import'
            output[significant[p + 1]] = module[1:-1]
        elif token.text in ('record', 'constant', 'let'):
            output[index] = {'record': 'struct', 'constant': 'let', 'let': 'var'}[token.text]
        elif token.text == 'function':
            output[index] = 'func'
            q = p + 1
            while q < len(words) and words[q] != '(':
                q += 1
            if q == len(words):
                raise ValueError('function declaration is missing its parameter list')
            stack = []
            param_start = q + 1
            q += 1
            while q < len(words):
                word = words[q]
                if not stack and word in (',', ')'):
                    # Minyar parameters are unlabelled unless the author gives
                    # an explicit external name (including underscore).
                    if q > param_start + 1 and words[param_start + 1] == ':':
                        at = significant[param_start]
                        output[at] = '_ ' + output[at]
                    param_start = q + 1
                    if word == ')':
                        break
                elif word in ('(', '[', '<'):
                    stack.append(word)
                elif stack and {')': '(', ']': '[', '>': '<'}.get(word) == stack[-1]:
                    stack.pop()
                q += 1
            q += 1
            while q < len(words) and words[q] in ('async', 'throws', 'rethrows'):
                q += 1
            if q < len(words) and words[q] == ':':
                output[significant[q]] = '->'
    return ''.join(output)


def run(command):
    subprocess.run([str(x) for x in command], check=True)


def install_library(source, output):
    """Publish binary and module metadata together, retaining rollback on failure."""
    marker = '.minyar-native-library'
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_name(output.name + '.minyar-lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    temporary = None
    preserve_backup = False
    try:
        if output.is_symlink() or (output.exists() and
                (not output.is_dir() or not (output / marker).is_file())):
            raise ValueError(f'refusing to replace a directory not generated as a Minyar native library: {output}')
        temporary = Path(tempfile.mkdtemp(prefix='.minyar-library-', dir=output.parent))
        stage = temporary / 'next'
        shutil.copytree(source, stage)
        (stage / marker).write_text('Minyar native library v1\n')
        backup = temporary / 'previous'
        if output.exists():
            os.replace(output, backup)
        try:
            os.replace(stage, output)
        except BaseException:
            if backup.exists():
                try:
                    os.replace(backup, output)
                except BaseException as error:
                    preserve_backup = True
                    raise OSError(f'library installation and rollback failed; previous library preserved at {backup}') from error
            raise
    finally:
        if temporary and not preserve_backup:
            shutil.rmtree(temporary)
        lock.unlink()


def main(native=False):
    description = ('Experimental direct Minyar compiler frontend; original source files are compiled without Swift source lowering.'
                   if native else __doc__)
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('sources', nargs='+', type=Path)
    parser.add_argument('-o', '--output', type=Path)
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--app', action='store_true')
    parser.add_argument('--library', action='store_true', help='emit a native shared library, module and resilient interface into the output directory')
    parser.add_argument('--bundle-id', default=None)
    parser.add_argument('--module-name', default='MinyarApp')
    parser.add_argument('--emit-swift', type=Path, help=argparse.SUPPRESS if native else 'save lowered source files to a directory')
    parser.add_argument('--emit-sil', type=Path, help='save optimized SIL for inspection (not reparsed)')
    parser.add_argument('--emit-ir', type=Path, help='save LLVM IR for inspection')
    parser.add_argument('--swift-flag', action='append', default=[], help='one additional compiler argument; use --swift-flag=-FLAG')
    if native:
        parser.add_argument('--target-platform', choices=['mac', 'ios', 'windows', 'linux', 'android', 'web'],
                            default='linux' if sys.platform == 'linux' else 'mac',
                            help='select platform-specific files; native macOS and Linux hosts are supported')
        parser.add_argument('--pkg-config', action='append', default=[], metavar='PACKAGE',
                            help='import compile and link flags for a Linux system library')
        parser.add_argument('--compiler', type=Path,
                            default=Path(os.environ.get('MINYAR_NATIVE_SWIFTC', str(
                                Path(__file__).resolve().parents[1] /
                                'build/native-toolchain/build/Ninja-ReleaseAssert' /
                                ('swift-' + ('linux-' if sys.platform == 'linux' else 'macosx-')
                                 + platform.machine()) / 'bin/swiftc'))))
        parser.add_argument('--parse-as-library', action='store_true',
                            help='use for an @main executable; implied by --app and --library')
    args = parser.parse_args()
    if sys.platform != 'darwin' and not (native and sys.platform == 'linux'):
        parser.error('the experimental SwiftUI backend currently requires macOS and Xcode')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', args.module_name):
        parser.error('--module-name must be an identifier')
    if args.library and args.app:
        parser.error('--library and --app are mutually exclusive')
    if native and args.emit_swift:
        parser.error('the direct frontend does not generate Swift source; use --emit-sil or --emit-ir')
    if native and not args.compiler.is_file():
        parser.error('native compiler is not built; run scripts/native-toolchain.py native, or select --compiler PATH')
    if native:
        host_platform = 'linux' if sys.platform == 'linux' else 'mac'
        if args.target_platform != host_platform:
            parser.error(f'target platform {args.target_platform} requires its native build host; '
                         f'this host builds {host_platform}. Cross-compilation SDKs are not configured yet')
        if args.pkg_config and host_platform != 'linux':
            parser.error('--pkg-config is currently supported only on Linux')
    try:
        project = None
        if native:
            spec = importlib.util.spec_from_file_location('native_project', Path(__file__).with_name('native_project.py'))
            project_loader = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(project_loader)
            source_paths, project = project_loader.resolve_sources(args.sources, args.target_platform)
            if project:
                if args.library:
                    raise ValueError('an app.min project cannot be built with --library; pass library source files explicitly')
                args.app = True
        else:
            source_paths = [source.resolve(strict=True) for source in args.sources]
        if args.bundle_id and not args.app:
            raise ValueError('--bundle-id requires --app or an app.min project')
        if args.bundle_id and sys.platform != 'darwin':
            raise ValueError('--bundle-id is macOS bundle metadata; set the Linux application ID in the app entry point')
        if len(set(source_paths)) != len(source_paths):
            raise ValueError('duplicate source file')
        output = (args.output or Path(project.name if project else source_paths[0].stem)).absolute()
        mac_app = args.app and sys.platform == 'darwin'
        if mac_app and output.suffix != '.app':
            output = Path(str(output) + '.app')
        artifacts = [p.absolute() for p in (args.emit_sil, args.emit_ir) if p]
        if len(set([output, *artifacts])) != 1 + len(artifacts):
            raise ValueError('output and inspection artifacts must have distinct paths')
        for path in [output, *artifacts]:
            if path.resolve() in source_paths or path.is_symlink():
                raise ValueError(f'refusing to overwrite source or symbolic link: {path}')
        if args.library:
            root = output.resolve()
            # Replacing a library directory must not remove its own source or
            # inspection files as a side effect.
            for path in [*source_paths, *artifacts, *([args.emit_swift] if args.emit_swift else [])]:
                if path.resolve() == root or root in path.resolve().parents:
                    raise ValueError(f'library output must not contain an input or inspection path: {path}')
        with tempfile.TemporaryDirectory(prefix='minyar-native-') as directory:
            temp = Path(directory)
            compiler_inputs = []
            has_main = False
            for n, source in enumerate([] if native else source_paths):
                body = lower(source.read_text())
                main_tokens = [t.text for t in lex(body) if t.kind != 'trivia']
                has_main |= any(a == '@' and b == 'main' for a, b in zip(main_tokens, main_tokens[1:]))
                # main.swift enables ordinary top-level Minyar statements.
                target = temp / ('main.swift' if n == 0 else f'input{n}.swift')
                escaped_path = json.dumps(str(source), ensure_ascii=False)
                target.write_text(f'#sourceLocation(file: {escaped_path}, line: 1)\n' + body)
                compiler_inputs.append(target)
            compiler = ['xcrun', 'swiftc']
            if native:
                # Preserve the compiler symlink name: swiftc and swift-frontend
                # select different modes based on argv[0].
                compiler = [str(args.compiler.absolute())]
                if sys.platform == 'darwin':
                    target = json.loads(subprocess.check_output(['xcrun', 'swiftc', '-print-target-info'], text=True))
                    sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
                    compiler += ['-resource-dir', target['paths']['runtimeResourcePath'],
                                 '-sdk', sdk, '-target', target['target']['triple']]
                compiler_inputs = source_paths
            common = [*compiler, '-swift-version', '6', '-module-name', args.module_name,
                      '-whole-module-optimization', '-O' if args.release else '-Onone']
            if native and sys.platform == 'linux':
                common += ['-I', str(Path(__file__).resolve().parents[1] / 'library/native/linux')]
            if has_main and args.library:
                raise ValueError('a native library cannot contain an @main entry point')
            if has_main or args.library or (native and (args.app or args.parse_as_library)):
                common += ['-parse-as-library']
            if args.library:
                common += ['-enable-library-evolution']
            common += args.swift_flag
            if native and args.pkg_config:
                for package in args.pkg_config:
                    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]*', package):
                        raise ValueError(f'invalid pkg-config package name: {package}')
                cflags = subprocess.check_output(['pkg-config', '--cflags', *args.pkg_config], text=True)
                for flag in shlex.split(cflags):
                    common += ['-Xcc', flag]
                libraries = subprocess.check_output(['pkg-config', '--libs', *args.pkg_config], text=True)
                for flag in shlex.split(libraries):
                    # Clang-style linker flags must go through the C driver;
                    # ordinary -l/-L flags are understood by the native driver.
                    if flag.startswith(('-l', '-L')):
                        common.append(flag)
                    elif flag.startswith('-Wl,'):
                        for item in flag[4:].split(','):
                            common += ['-Xlinker', item]
                    elif flag == '-pthread':
                        common.append('-lpthread')
                    else:
                        raise ValueError(f'unsupported pkg-config linker flag: {flag}')
            # Keep semantic analysis, SILGen, mandatory passes, SIL optimization
            # and LLVM lowering together. Textual SIL is not a stable round-trip
            # format for property wrappers in the installed Apple compiler.
            binary = temp / 'application'
            if args.library:
                products = temp / 'library'
                products.mkdir()
                name = args.module_name
                extension = 'dylib' if sys.platform == 'darwin' else 'so'
                binary = products / f'lib{name}.{extension}'
                identity = (['-Xlinker', '-install_name', '-Xlinker', f'@rpath/lib{name}.dylib']
                            if sys.platform == 'darwin' else
                            ['-Xlinker', '-soname', '-Xlinker', f'lib{name}.so'])
                run([*common, '-emit-library', '-emit-module',
                     '-emit-module-path', products / f'{name}.swiftmodule',
                     '-emit-module-interface-path', products / f'{name}.swiftinterface',
                     *identity,
                     *compiler_inputs, '-o', binary])
            else:
                run([*common, *compiler_inputs, '-o', binary])
            for flag, path in [('-emit-sil', args.emit_sil), ('-emit-ir', args.emit_ir)]:
                if path:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    run([*common, flag, *compiler_inputs, '-o', path])
            if args.emit_swift:
                args.emit_swift.mkdir(parents=True, exist_ok=True)
                for target in compiler_inputs:
                    destination = args.emit_swift / target.name
                    if destination.is_symlink() or destination.resolve() in source_paths:
                        raise ValueError(f'refusing to overwrite source or symbolic link: {destination}')
                    shutil.copyfile(target, destination)
            output.parent.mkdir(parents=True, exist_ok=True)
            if args.library:
                install_library(products, output)
            elif mac_app:
                spec = importlib.util.spec_from_file_location('macos_app', Path(__file__).with_name('macos-app.py'))
                packager = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(packager)
                packager.package(binary, output, args.bundle_id or 'org.minyar.application')
            else:
                # Stage beside the destination, so a failed compile never
                # replaces an existing executable and installation is atomic.
                with tempfile.NamedTemporaryFile(prefix='.minyar-native-', dir=output.parent, delete=False) as stage:
                    stage_path = Path(stage.name)
                try:
                    shutil.copyfile(binary, stage_path)
                    stage_path.chmod(0o755)
                    os.replace(stage_path, output)
                finally:
                    stage_path.unlink(missing_ok=True)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{"native Minyar frontend" if native else "native Swift backend"}: {error}\n')


if __name__ == '__main__':
    main()
