#!/usr/bin/env python3
"""Sign and notarize release copies; publish the output only after verification."""
import argparse
from contextlib import ExitStack
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import sys
from urllib.parse import urlsplit


def checked(run, args):
    result = run(args, check=True, capture_output=True, text=True)
    # SignTool returns 2 for warnings, including a failed timestamp. Refuse it.
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
    return result


def notarize(path, profile, run, *, keychain=None):
    command = ['xcrun', 'notarytool', 'submit', str(path), '--keychain-profile', profile,
               '--wait', '--output-format', 'json']
    if keychain is not None:
        command += ['--keychain', str(keychain)]
    result = checked(run, command)
    try:
        status = json.loads(result.stdout)['status']
    except (ValueError, KeyError, TypeError):
        raise ValueError('notarytool did not return an explicit notarization status') from None
    if status != 'Accepted':
        raise ValueError(f'notarization was not accepted: {status}')


def publish_directory(source, destination):
    """Atomically publish a generation without replacing even an empty directory."""
    if os.name == 'nt':
        # Windows rename refuses an existing destination, including directories.
        os.rename(source, destination)
        return
    if sys.platform.startswith(('cygwin', 'msys')):
        # MSYS exposes POSIX replacement semantics and has no renameat2.
        # MoveFileW retains Windows' exclusive directory publication contract.
        native = [subprocess.check_output(['cygpath', '-w', str(path)],
                                         text=True).strip()
                  for path in (source, destination)]
        kernel = ctypes.CDLL('kernel32.dll')
        move = kernel.MoveFileW
        move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        move.restype = ctypes.c_int
        if not move(*native):
            if os.path.lexists(destination):
                raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST),
                                      str(destination))
            # Keep an unpublished generation on any other native rename failure.
            raise OSError(errno.EIO, 'exclusive Windows directory publication failed',
                          str(destination))
        return
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin':
        # Apple XNU bsd/sys/stdio.h: RENAME_EXCL=0x4.
        function = library.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        arguments = [os.fsencode(source), os.fsencode(destination), 4]
    else:
        # Linux renameat2: RENAME_NOREPLACE=1, AT_FDCWD=-100.
        function = library.renameat2
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                             ctypes.c_char_p, ctypes.c_uint]
        arguments = [-100, os.fsencode(source), -100, os.fsencode(destination), 1]
    function.restype = ctypes.c_int
    if function(*arguments):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def macos(app, output, identity, profile, *, entitlements=None,
          signed_app_output=None, keychain=None, notary_keychain=None, run=subprocess.run):
    if not identity.startswith('Developer ID Application: ') or not profile:
        raise ValueError('a Developer ID Application identity and notarytool Keychain profile are required')
    app, output = Path(app).resolve(strict=True), Path(output).absolute()
    keychain = Path(keychain).resolve(strict=True) if keychain is not None else None
    notary_keychain = Path(notary_keychain).resolve(strict=True) if notary_keychain is not None else None
    if app.suffix != '.app' or not (app / 'Contents/MacOS').is_dir() or output.suffix != '.dmg':
        raise ValueError('macOS release requires an application bundle and .dmg output')
    retained = None
    if signed_app_output is not None:
        retained = Path(signed_app_output).absolute()
        if retained.suffix != '.app':
            raise ValueError('signed app output must be a new .app generation')
        if os.path.lexists(retained):
            raise FileExistsError(f'signed app output already exists: {retained}')
        retained.parent.mkdir(parents=True, exist_ok=True)
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
    with ExitStack() as stack:
        temp = Path(stack.enter_context(tempfile.TemporaryDirectory(
            prefix='.minyar-release-', dir=output.parent)))
        app_temp = temp if retained is None else Path(stack.enter_context(
            tempfile.TemporaryDirectory(prefix='.minyar-signed-app-', dir=retained.parent)))
        stage = app_temp / app.name
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
            if keychain is not None:
                command += ['--keychain', str(keychain)]
            if entitlements is not None and target == stage:
                command += ['--entitlements', str(entitlements)]
            checked(run, command + [str(target)])
        checked(run, ['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(stage)])
        archive = temp / 'notarization.zip'
        checked(run, ['ditto', '-c', '-k', '--keepParent', str(stage), str(archive)])
        notarize(archive, profile, run, keychain=notary_keychain)
        checked(run, ['xcrun', 'stapler', 'staple', str(stage)])
        checked(run, ['xcrun', 'stapler', 'validate', str(stage)])
        checked(run, ['spctl', '--assess', '--type', 'execute', '--verbose=2', str(stage)])
        image = temp / output.name
        checked(run, ['hdiutil', 'create', '-volname', app.stem, '-srcfolder', str(stage),
                      '-format', 'UDZO', '-ov', str(image)])
        command = ['codesign', '--force', '--sign', identity, '--timestamp']
        if keychain is not None:
            command += ['--keychain', str(keychain)]
        checked(run, command + [str(image)])
        notarize(image, profile, run, keychain=notary_keychain)
        checked(run, ['xcrun', 'stapler', 'staple', str(image)])
        checked(run, ['xcrun', 'stapler', 'validate', str(image)])
        checked(run, ['codesign', '--verify', '--strict', str(image)])
        checked(run, ['spctl', '--assess', '--type', 'open', '--context', 'context:primary-signature', str(image)])
        if retained is None:
            os.replace(image, output)
        else:
            # Move the exact verified stage on its original filesystem; copying
            # would risk losing signature/staple metadata or resource forks.
            publish_directory(stage, retained)
            try:
                os.replace(image, output)
            except BaseException:
                os.rename(retained, stage)
                raise


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


def test_output(output, suffix):
    """TEST artifacts are immutable local generations, never release replacements."""
    output = Path(output).absolute()
    if not output.name.startswith('TEST-') or output.suffix.lower() != suffix:
        raise ValueError(f'TEST ONLY output must be named TEST-*{suffix}')
    if os.path.lexists(output):
        raise FileExistsError(f'TEST output already exists: {output}')
    return output


def test_certificate(certificate, thumbprint, openssl, run):
    """Pin a DER self-signed code-signing certificate with the reserved TEST CN."""
    if not re.fullmatch('[A-Fa-f0-9]{40}', thumbprint):
        raise ValueError('TEST certificate requires an explicit SHA1 DER thumbprint')
    certificate = Path(certificate).resolve(strict=True)
    if hashlib.sha1(certificate.read_bytes()).hexdigest().upper() != thumbprint.upper():
        raise ValueError('TEST certificate thumbprint mismatch')
    names = checked(run, [openssl, 'x509', '-inform', 'DER', '-in', str(certificate),
                          '-noout', '-subject', '-issuer', '-nameopt', 'RFC2253']).stdout.splitlines()
    if len(names) != 2 or not names[0].startswith('subject=') or not names[1].startswith('issuer='):
        raise ValueError('cannot inspect TEST certificate names')
    subject, issuer = names[0][8:].strip(), names[1][7:].strip()
    if subject != issuer or not re.fullmatch(r'CN=Minyar TEST ONLY [a-f0-9]{32}', subject):
        raise ValueError('certificate must be self-signed with a randomized Minyar TEST ONLY CN')
    usage = checked(run, [openssl, 'x509', '-inform', 'DER', '-in', str(certificate),
                          '-noout', '-ext', 'extendedKeyUsage']).stdout
    lines = [line.strip() for line in usage.splitlines()]
    if len(lines) != 2 or lines[0] not in ('X509v3 Extended Key Usage:', 'X509v3 Extended Key Usage: critical') or lines[1] != 'Code Signing':
        raise ValueError('TEST certificate must have only the Code Signing extended key usage')
    with tempfile.TemporaryDirectory(prefix='minyar-test-certificate-') as directory:
        pem = Path(directory) / 'certificate.pem'
        checked(run, [openssl, 'x509', '-inform', 'DER', '-in', str(certificate), '-out', str(pem)])
        checked(run, [openssl, 'verify', '-check_ss_sig', '-purpose', 'any', '-CAfile', str(pem), str(pem)])
    return thumbprint.upper()


def verify_test_macos(app, thumbprint, *, run=subprocess.run):
    checked(run, ['codesign', '--verify', '--deep', '--strict', '--verbose=2',
                  '-R', f'certificate leaf = H"{thumbprint}"', str(app)])


def verify_test_windows(source, signtool, thumbprint, *, run=subprocess.run):
    # TEST certificates have no RFC3161 timestamp. Production still requires /tw.
    checked(run, [signtool, 'verify', '/pa', '/all', str(source)])
    # /pa alone does not pin the selected signer. Check the actual signer too.
    command = ("$ErrorActionPreference='Stop'; "
               "$s=Get-AuthenticodeSignature -LiteralPath $env:MINYAR_TEST_SIGNED_FILE; "
               "if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Thumbprint -ne "
               "$env:MINYAR_TEST_SIGNER) { throw 'TEST Authenticode signer mismatch' }")
    environment = dict(os.environ, MINYAR_TEST_SIGNED_FILE=str(Path(source).absolute()),
                       MINYAR_TEST_SIGNER=thumbprint)
    result = run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                 env=environment, check=True, capture_output=True, text=True)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)


def test_macos(app, output, certificate, thumbprint, keychain, *, openssl='openssl', run=subprocess.run):
    """CI/OWNER-RUN provisioned TEST signing: no notarization/Gatekeeper claim."""
    output = test_output(output, '.app')
    thumbprint = test_certificate(certificate, thumbprint, openssl, run)
    app, keychain = Path(app).resolve(strict=True), Path(keychain).resolve(strict=True)
    if app.suffix != '.app' or not (app / 'Contents/MacOS').is_dir() or not keychain.is_file():
        raise ValueError('TEST macOS signing requires an app and explicit provisioned keychain')
    for path in app.rglob('*'):
        if path.is_symlink() and not path.resolve().is_relative_to(app):
            raise ValueError('TEST bundle symlink escapes the app')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.minyar-test-sign-', dir=output.parent) as directory:
        stage = Path(directory) / output.name
        shutil.copytree(app, stage, symlinks=True)
        macho = {bytes.fromhex(value) for value in
                 ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe', 'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}
        targets = set()
        for path in stage.rglob('*'):
            if path.is_file() and not path.is_symlink():
                with path.open('rb') as stream:
                    if stream.read(4) in macho:
                        targets.add(path)
            if path.is_dir() and not path.is_symlink() and path.suffix in ('.framework', '.xpc', '.appex', '.app'):
                targets.add(path)
        for target in sorted(targets, key=lambda p: (-len(p.parts), str(p))) + [stage]:
            checked(run, ['codesign', '--force', '--sign', thumbprint, '--keychain', str(keychain),
                          '--options', 'runtime', '--timestamp=none', str(target)])
        verify_test_macos(stage, thumbprint, run=run)
        publish_directory(stage, output)


def test_windows(source, output, certificate, thumbprint, signtool, *, openssl='openssl', run=subprocess.run):
    """Real CurrentUser TEST certificate signing ONLY; never production signing."""
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() not in ('.exe', '.dll', '.msi'):
        raise ValueError('TEST Windows source must be .exe/.dll/.msi')
    output = test_output(output, source.suffix.lower())
    thumbprint = test_certificate(certificate, thumbprint, openssl, run)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.minyar-test-sign-', dir=output.parent) as directory:
        stage = Path(directory) / output.name
        shutil.copyfile(source, stage)
        checked(run, [signtool, 'sign', '/fd', 'SHA256', '/sha1', thumbprint, '/s', 'My', str(stage)])
        verify_test_windows(stage, signtool, thumbprint, run=run)
        publish_directory(stage, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    mac = modes.add_parser('macos')
    mac.add_argument('--app', required=True)
    mac.add_argument('--output', required=True)
    mac.add_argument('--identity', required=True)
    mac.add_argument('--notary-profile', required=True)
    mac.add_argument('--entitlements')
    mac.add_argument('--signed-app-output', help='retain the exact verified signed/stapled app as a new immutable generation')
    mac.add_argument('--keychain', help='already-provisioned identity keychain; never created or modified')
    mac.add_argument('--notary-keychain', help='already-provisioned keychain containing the notarization profile')
    win = modes.add_parser('windows')
    win.add_argument('--input', required=True)
    win.add_argument('--output', required=True)
    win.add_argument('--signtool', required=True)
    win.add_argument('--thumbprint', default='')
    win.add_argument('--timestamp', required=True)
    win.add_argument('--azure-dlib')
    win.add_argument('--azure-metadata')
    win.add_argument('--machine-store', action='store_true')
    for name in ('test-macos', 'test-windows'):
        test = modes.add_parser(name, help='TEST ONLY self-signed local artifact; never a production release')
        test.add_argument('--app' if name == 'test-macos' else '--input', required=True)
        test.add_argument('--output', required=True, help='new TEST-* output; existing paths are refused')
        test.add_argument('--certificate', required=True, help='self-signed Minyar TEST ONLY DER certificate')
        test.add_argument('--thumbprint', required=True, help='pinned SHA1 of DER certificate')
        test.add_argument('--openssl', default='openssl')
        test.add_argument('--keychain' if name == 'test-macos' else '--signtool', required=True)
    args = parser.parse_args()
    try:
        if args.mode in ('macos', 'test-macos') and sys.platform != 'darwin':
            raise ValueError('macOS release signing requires actual macOS')
        if args.mode in ('windows', 'test-windows') and (os.name != 'nt' or sys.platform != 'win32'):
            raise ValueError('Windows release signing requires native Windows Python on Boat')
        if args.mode == 'macos':
            macos(args.app, args.output, args.identity, args.notary_profile, entitlements=args.entitlements,
                  signed_app_output=args.signed_app_output, keychain=args.keychain, notary_keychain=args.notary_keychain)
        elif args.mode == 'windows':
            windows(args.input, args.output, args.signtool, args.thumbprint, args.timestamp,
                    azure_dlib=args.azure_dlib, azure_metadata=args.azure_metadata, machine_store=args.machine_store)
        elif args.mode == 'test-macos':
            test_macos(args.app, args.output, args.certificate, args.thumbprint, args.keychain, openssl=args.openssl)
        else:
            test_windows(args.input, args.output, args.certificate, args.thumbprint, args.signtool, openssl=args.openssl)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'release failed: {error}\n')


if __name__ == '__main__':
    main()
