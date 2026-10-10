#!/usr/bin/env python3
"""Package a trusted native Minyar executable for the installed GNOME Flatpak runtime.

This packages an existing executable; it does not compile against the Flatpak
SDK or publish to Flathub. Runtime dependency/relocation checks must pass before
an existing output bundle can be replaced.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def run(*args):
    return subprocess.run(list(map(str, args)), check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('-o', '--output', required=True, type=Path)
    parser.add_argument('--app-id', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--icon', required=True, type=Path, help='application SVG icon')
    parser.add_argument('--license', required=True, action='append', type=Path,
                        help='license/notice files for the app and bundled runtime; repeat as needed')
    parser.add_argument('--runtime-version', default='51')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Flatpak packaging requires Linux')
    if not re.fullmatch(r'(?:[A-Za-z_][A-Za-z_0-9]*\.){2,}[A-Za-z_][A-Za-z_0-9-]*', args.app_id):
        parser.error('--app-id must be a reverse-DNS application ID')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.runtime_version):
        parser.error('invalid runtime version')
    if not args.name.strip() or any(c in args.name for c in '\r\n\0'):
        parser.error('--name must be a nonempty single line')
    try:
        binary = args.binary.resolve(strict=True)
        icon = args.icon.resolve(strict=True)
        licenses = [path.resolve(strict=True) for path in args.license]
        if binary.read_bytes()[:4] != b'\x7fELF':
            raise ValueError('input must be an ELF executable')
        if icon.suffix.lower() != '.svg':
            raise ValueError('--icon must be an SVG file')
        output = args.output.absolute()
        if output.is_symlink() or output.resolve() in [binary, icon, *licenses]:
            raise ValueError('output must not overwrite an input or symbolic link')
        for tool in ['flatpak', 'patchelf', 'ldd']:
            if not shutil.which(tool):
                raise ValueError(f'missing required tool: {tool}')
        # The caller builds and trusts this binary. ldd is not a safe inspector
        # for executables obtained from an untrusted third party.
        dependencies = run('ldd', binary).stdout
        if 'not found' in dependencies:
            raise ValueError('input has unresolved host dependencies:\n' + dependencies)
        bundled = {}
        for line in dependencies.splitlines():
            match = re.match(r'\s*(\S+) => (/.+?) \(0x[0-9a-f]+\)', line)
            if match and (match[1].startswith('libswift') or match[1] in ('libdispatch.so', 'libBlocksRuntime.so')):
                bundled[match[1]] = Path(match[2]).resolve(strict=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='minyar-flatpak-') as temporary:
            root = Path(temporary)
            app = root / 'app'
            run('flatpak', 'build-init', app, args.app_id, 'org.gnome.Sdk',
                'org.gnome.Platform', args.runtime_version)
            files = app / 'files'
            (files / 'bin').mkdir(parents=True)
            (files / 'lib').mkdir()
            executable = files / 'bin/minyar-app'
            shutil.copy2(binary, executable)
            executable.chmod(0o755)
            run('patchelf', '--set-rpath', '$ORIGIN/../lib', executable)
            for name, source in bundled.items():
                destination = files / 'lib' / name
                shutil.copy2(source, destination)
                run('patchelf', '--set-rpath', '$ORIGIN', destination)
            applications = files / 'share/applications'
            applications.mkdir(parents=True)
            name = args.name.replace('\\', '\\\\')
            (applications / f'{args.app_id}.desktop').write_text(
                f'[Desktop Entry]\nType=Application\nName={name}\n'
                f'Exec=minyar-app\nIcon={args.app_id}\nTerminal=false\nCategories=Utility;\n')
            icons = files / 'share/icons/hicolor/scalable/apps'
            icons.mkdir(parents=True)
            shutil.copyfile(icon, icons / f'{args.app_id}.svg')
            notices = files / 'share/licenses' / args.app_id
            notices.mkdir(parents=True)
            for index, license in enumerate(licenses):
                shutil.copyfile(license, notices / f'{index + 1}-{license.name}')
            # Record provenance without leaking absolute development paths.
            import json
            manifest = {'application': hashlib.sha256(binary.read_bytes()).hexdigest(),
                        'runtime': 'org.gnome.Platform/' + args.runtime_version,
                        'bundled': {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                    for name, path in bundled.items()}}
            (notices / 'build-provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')
            # Resolve every dynamic relocation against the target runtime,
            # including versioned glibc/libstdc++ symbols. Host success alone
            # is insufficient evidence that a bundle is runnable.
            check = run('flatpak', 'build', app, 'ldd', '-r', '/app/bin/minyar-app')
            report = check.stdout + check.stderr
            if 'not found' in report or 'undefined symbol:' in report:
                raise ValueError('target runtime cannot satisfy dependencies:\n' + report)
            # Wayland and GPU access only. File access is granted by portals;
            # the app gets no general home-directory or network permission.
            run('flatpak', 'build-finish', '--socket=wayland', '--device=dri',
                '--command=minyar-app', app)
            repository = root / 'repo'
            run('flatpak', 'build-export', repository, app)
            bundle = root / 'application.flatpak'
            run('flatpak', 'build-bundle', repository, bundle, args.app_id,
                '--runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo')
            with tempfile.NamedTemporaryFile(prefix='.minyar-flatpak-', dir=output.parent, delete=False) as stage:
                stage_path = Path(stage.name)
            try:
                shutil.copyfile(bundle, stage_path)
                os.replace(stage_path, output)
            finally:
                stage_path.unlink(missing_ok=True)
        print(f'Packaged {output} with {len(bundled)} runtime libraries')
    except subprocess.CalledProcessError as error:
        parser.exit(1, f'Flatpak packaging failed: {error.stderr or error.stdout or error}\n')
    except (ValueError, OSError) as error:
        parser.exit(1, f'Flatpak packaging failed: {error}\n')


if __name__ == '__main__':
    main()
