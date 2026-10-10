#!/usr/bin/env python3
"""Sign and notarize release copies; publish the output only after verification."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit


def checked(run, args):
    result = run(args, check=True, capture_output=True, text=True)
    # SignTool returns 2 for warnings, including a failed timestamp. Refuse it.
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
    return result


def notarize(path, profile, run):
    result = checked(run, ['xcrun', 'notarytool', 'submit', str(path), '--keychain-profile', profile,
                           '--wait', '--output-format', 'json'])
    try:
        status = json.loads(result.stdout)['status']
    except (ValueError, KeyError, TypeError):
        raise ValueError('notarytool did not return an explicit notarization status') from None
    if status != 'Accepted':
        raise ValueError(f'notarization was not accepted: {status}')


def macos(app, output, identity, profile, *, entitlements=None, run=subprocess.run):
    if not identity.startswith('Developer ID Application: ') or not profile:
        raise ValueError('a Developer ID Application identity and notarytool Keychain profile are required')
    app, output = Path(app).resolve(strict=True), Path(output).absolute()
    if app.suffix != '.app' or not (app / 'Contents/MacOS').is_dir() or output.suffix != '.dmg':
        raise ValueError('macOS release requires an application bundle and .dmg output')
    if entitlements is not None:
        import plistlib
        entitlements = Path(entitlements).resolve(strict=True)
        values = plistlib.loads(entitlements.read_bytes())
        if values.get('com.apple.security.get-task-allow'):
            raise ValueError('development get-task-allow entitlement cannot ship')
    for path in app.rglob('*'):
        if path.is_symlink() and not path.resolve().is_relative_to(app):
            raise ValueError(f'bundle symlink escapes the app: {path}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.minyar-release-', dir=output.parent) as directory:
        temp = Path(directory)
        stage = temp / app.name
        shutil.copytree(app, stage, symlinks=True)
        macho = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
                 b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'}
        targets = set()
        for path in stage.rglob('*'):
            if path.is_file() and not path.is_symlink():
                with path.open('rb') as stream:
                    if stream.read(4) in macho:
                        targets.add(path)
            if path.is_dir() and not path.is_symlink() and path.suffix in ('.framework', '.xpc', '.appex', '.app'):
                targets.add(path)
        for target in sorted(targets, key=lambda p: (-len(p.parts), str(p))) + [stage]:
            command = ['codesign', '--force', '--sign', identity, '--options', 'runtime', '--timestamp']
            if entitlements is not None and target == stage:
                command += ['--entitlements', str(entitlements)]
            checked(run, command + [str(target)])
        checked(run, ['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(stage)])
        archive = temp / 'notarization.zip'
        checked(run, ['ditto', '-c', '-k', '--keepParent', str(stage), str(archive)])
        notarize(archive, profile, run)
        checked(run, ['xcrun', 'stapler', 'staple', str(stage)])
        checked(run, ['xcrun', 'stapler', 'validate', str(stage)])
        checked(run, ['spctl', '--assess', '--type', 'execute', '--verbose=2', str(stage)])
        image = temp / output.name
        checked(run, ['hdiutil', 'create', '-volname', app.stem, '-srcfolder', str(stage),
                      '-format', 'UDZO', '-ov', str(image)])
        checked(run, ['codesign', '--force', '--sign', identity, '--timestamp', str(image)])
        notarize(image, profile, run)
        checked(run, ['xcrun', 'stapler', 'staple', str(image)])
        checked(run, ['xcrun', 'stapler', 'validate', str(image)])
        checked(run, ['codesign', '--verify', '--strict', str(image)])
        checked(run, ['spctl', '--assess', '--type', 'open', '--context', 'context:primary-signature', str(image)])
        os.replace(image, output)


def windows(source, output, signtool, thumbprint, timestamp, *, azure_dlib=None,
            azure_metadata=None, machine_store=False, run=subprocess.run):
    source, output = Path(source).resolve(strict=True), Path(output).absolute()
    if source.suffix.lower() not in ('.exe', '.dll', '.msi') or source.suffix.lower() != output.suffix.lower():
        raise ValueError('Windows release requires .exe/.dll/.msi source and matching output type')
    address = urlsplit(timestamp)
    if address.scheme != 'https' or not address.hostname or address.username or address.fragment:
        raise ValueError('an HTTPS RFC3161 timestamp URL is required')
    if azure_dlib is not None or azure_metadata is not None:
        if thumbprint or azure_dlib is None or azure_metadata is None:
            raise ValueError('choose either a certificate thumbprint or both Azure signing DLL and metadata')
        azure_dlib, azure_metadata = Path(azure_dlib).resolve(strict=True), Path(azure_metadata).resolve(strict=True)
        metadata = json.loads(azure_metadata.read_text())
        endpoint = urlsplit(metadata.get('Endpoint', ''))
        if (endpoint.scheme != 'https' or not endpoint.hostname or
                not re.fullmatch(r'[a-z0-9-]+\.codesigning\.azure\.net', endpoint.hostname) or
                endpoint.username or endpoint.password or endpoint.port or
                endpoint.path not in ('', '/') or endpoint.query or endpoint.fragment):
            raise ValueError('Azure signing metadata requires a regional codesigning.azure.net HTTPS endpoint')
        for field in ('CodeSigningAccountName', 'CertificateProfileName'):
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', metadata.get(field, '')):
                raise ValueError(f'missing or invalid Azure {field}')
        identity = ['/dlib', str(azure_dlib), '/dmdf', str(azure_metadata)]
    else:
        if not re.fullmatch('[A-Fa-f0-9]{40}', thumbprint):
            raise ValueError('an explicit 40-digit certificate thumbprint is required')
        identity = ['/sha1', thumbprint, '/s', 'My'] + (['/sm'] if machine_store else [])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.minyar-release-', dir=output.parent) as directory:
        stage = Path(directory) / source.name
        shutil.copyfile(source, stage)
        checked(run, [signtool, 'sign', '/fd', 'SHA256', '/tr', timestamp, '/td', 'SHA256', *identity, str(stage)])
        checked(run, [signtool, 'verify', '/pa', '/all', '/tw', str(stage)])
        os.replace(stage, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    mac = modes.add_parser('macos')
    mac.add_argument('--app', required=True)
    mac.add_argument('--output', required=True)
    mac.add_argument('--identity', required=True)
    mac.add_argument('--notary-profile', required=True)
    mac.add_argument('--entitlements')
    win = modes.add_parser('windows')
    win.add_argument('--input', required=True)
    win.add_argument('--output', required=True)
    win.add_argument('--signtool', required=True)
    win.add_argument('--thumbprint', default='')
    win.add_argument('--timestamp', required=True)
    win.add_argument('--azure-dlib')
    win.add_argument('--azure-metadata')
    win.add_argument('--machine-store', action='store_true')
    args = parser.parse_args()
    try:
        if args.mode == 'macos':
            macos(args.app, args.output, args.identity, args.notary_profile, entitlements=args.entitlements)
        else:
            windows(args.input, args.output, args.signtool, args.thumbprint, args.timestamp,
                    azure_dlib=args.azure_dlib, azure_metadata=args.azure_metadata, machine_store=args.machine_store)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'release failed: {error}\n')


if __name__ == '__main__':
    main()
