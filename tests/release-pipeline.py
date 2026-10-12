#!/usr/bin/env python3
"""TEST ONLY: real tiny native signing, updater roundtrip, mutations and cleanup.

No production credentials, network publication, compiler build or Apple acceptance.
Windows execution requires native Windows Python on an owned Boat guest.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


release = module('release', 'scripts/release.py')
bundle = module('bundle', 'scripts/update-bundle.py')
manifest = module('manifest', 'scripts/update-manifest.py')


def run(args, **kwargs):
    kwargs.setdefault('timeout', 60)
    kwargs.setdefault('stdin', subprocess.DEVNULL)
    kwargs.setdefault('check', True)
    kwargs.setdefault('capture_output', True)
    return subprocess.run([str(arg) for arg in args], **kwargs)


def require_ephemeral_macos_ci(path, *, explicit=False):
    """Authorization check, before tools or directories; never infer CI from OS."""
    require(explicit and sys.platform == 'darwin' and
            os.environ.get('GITHUB_ACTIONS') == 'true' and
            os.environ.get('RUNNER_OS') == 'macOS' and
            os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
            bool(os.environ.get('RUNNER_TEMP')),
            'automatic Mac credentials require --ephemeral-macos-ci on an ephemeral GitHub-hosted macOS runner; owner Mac is refused')
    try:
        runner_temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    except OSError:
        raise ValueError('ephemeral Mac RUNNER_TEMP must be an existing directory') from None
    require(runner_temp.is_dir(), 'ephemeral Mac RUNNER_TEMP must be an existing directory')
    require(Path(path).resolve().is_relative_to(runner_temp),
            'ephemeral Mac credentials/output must be under RUNNER_TEMP')


def require_owned_boat_windows(*, explicit=False):
    require(os.name == 'nt' and sys.platform == 'win32',
            'Windows signing requires actual native Windows Python on OWN Boat')
    require(explicit and re.fullmatch(r'bx_[a-z0-9]+', os.environ.get('MINYAR_OWN_BOAT_ID', '')),
            'Windows TEST credentials require --owned-boat-windows and MINYAR_OWN_BOAT_ID for the exclusive OWN Boat signing slot')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rejected(action, label, results):
    try:
        action()
    except (ValueError, subprocess.CalledProcessError):
        results.append(label)
    else:
        raise ValueError(f'mutation accepted: {label}')


def ps(script, environment):
    return run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
               env=dict(os.environ, **environment), text=True)


WINDOWS_CREATE = r"""
$ErrorActionPreference='Stop'
$state=@{ baseline=@{}; certificates=@() }
foreach ($store in @('My','Root','TrustedPublisher')) {
  $state.baseline[$store]=@(Get-ChildItem "Cert:\CurrentUser\$store" | ForEach-Object {$_.Thumbprint} | Sort-Object)
}
function Save-State { $state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $env:MINYAR_TEST_STATE -Encoding UTF8 }
Save-State
foreach ($name in @('signer','wrong')) {
  $subject='CN=Minyar TEST ONLY '+[guid]::NewGuid().ToString('N')
  $cert=New-SelfSignedCertificate -Type CodeSigningCert -Subject $subject -CertStoreLocation 'Cert:\CurrentUser\My' -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -KeyExportPolicy NonExportable -Provider 'Microsoft Software Key Storage Provider' -NotAfter (Get-Date).AddDays(1)
  $entry=@{name=$name; thumbprint=$cert.Thumbprint; subject=$subject}
  $state.certificates+=@($entry)
  Save-State
  $rsa=[System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
  try { $entry.keyFile=Join-Path $env:APPDATA ('Microsoft\Crypto\Keys\'+$rsa.Key.UniqueName) } finally { $rsa.Dispose() }
  Save-State
  $der=Join-Path $env:MINYAR_TEST_CREDENTIALS ($name+'.der')
  [System.IO.File]::WriteAllBytes($der,$cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert))
  foreach ($store in @('Root','TrustedPublisher')) {
    if ($state.baseline[$store] -contains $cert.Thumbprint) { throw 'TEST certificate collided with prior trust' }
    Import-Certificate -FilePath $der -CertStoreLocation "Cert:\CurrentUser\$store" | Out-Null
  }
}
"""

WINDOWS_CLEANUP = r"""
$ErrorActionPreference='Stop'
$state=Get-Content -LiteralPath $env:MINYAR_TEST_STATE -Raw | ConvertFrom-Json
$failures=@()
foreach ($entry in @($state.certificates)) {
  foreach ($store in @('Root','TrustedPublisher','My')) {
    try {
      if ($state.baseline.$store -contains $entry.thumbprint) { throw 'refusing unrelated certificate removal' }
      $path="Cert:\CurrentUser\$store\$($entry.thumbprint)"
      if (Test-Path $path) {
        $cert=Get-Item $path
        if ($cert.Subject -ne $entry.subject) { throw 'refusing changed TEST certificate removal' }
        if ($store -eq 'My') { Remove-Item $path -DeleteKey -Force } else { Remove-Item $path -Force }
      }
      if (Test-Path $path) { throw 'TEST certificate remains after cleanup' }
    } catch { $failures+=@($_.Exception.Message) }
  }
  if ($entry.keyFile -and (Test-Path -LiteralPath $entry.keyFile)) { $failures+=@('TEST private key remains after cleanup') }
}
foreach ($store in @('My','Root','TrustedPublisher')) {
  $after=@(Get-ChildItem "Cert:\CurrentUser\$store" | ForEach-Object {$_.Thumbprint} | Sort-Object)
  if ((@($state.baseline.$store) -join ',') -cne ($after -join ',')) { $failures+=@('certificate store differs after cleanup: '+$store) }
}
if ($failures.Count) { throw ($failures -join '; ') }
"""


@contextmanager
def windows_credentials(credentials, report, *, owned_boat=False):
    require_owned_boat_windows(explicit=owned_boat)
    state = credentials / 'windows-state.json'
    environment = {'MINYAR_TEST_STATE': str(state), 'MINYAR_TEST_CREDENTIALS': str(credentials)}
    try:
        ps(WINDOWS_CREATE, environment)
        value = json.loads(state.read_text(encoding='utf-8-sig'))
        identities = {entry['name']: entry['thumbprint'] for entry in value['certificates']}
        yield identities
    finally:
        # The state is persisted immediately after each creation, before trust imports.
        try:
            if state.exists():
                ps(WINDOWS_CLEANUP, environment)
        except (OSError, ValueError, subprocess.SubprocessError):
            report['windowsCredentialCleanup'] = 'FAILED: see cleanup error; no generation published'
            raise
        report['windowsCredentialCleanup'] = 'verified: own My/Root/TrustedPublisher entries and private keys removed; prior stores preserved'


@contextmanager
def macos_credentials(credentials, openssl, report, *, ephemeral_ci=False):
    require_ephemeral_macos_ci(credentials, explicit=ephemeral_ci)
    keychain = credentials / 'TEST-signing.keychain-db'
    password = secrets.token_hex(24)
    before = run(['security', 'list-keychains', '-d', 'user']).stdout
    trust_before = trust_inventory()
    trust_attempted = False
    try:
        for name in ('signer', 'wrong'):
            key, pem = credentials / (name + '.pem'), credentials / (name + '.crt')
            run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', key,
                 '-out', pem, '-days', '1', '-sha256', '-subj', '/CN=Minyar TEST ONLY ' + secrets.token_hex(16),
                 '-addext', 'basicConstraints=critical,CA:FALSE',
                 '-addext', 'keyUsage=critical,digitalSignature', '-addext', 'extendedKeyUsage=codeSigning'])
            run([openssl, 'x509', '-in', pem, '-outform', 'DER', '-out', credentials / (name + '.der')])
        p12 = credentials / 'TEST-signer.p12'
        environment = dict(os.environ, MINYAR_TEST_P12_PASSWORD=password)
        run([openssl, 'pkcs12', '-export', '-legacy', '-inkey', credentials / 'signer.pem',
             '-in', credentials / 'signer.crt', '-out', p12, '-passout', 'env:MINYAR_TEST_P12_PASSWORD'], env=environment)
        run(['security', 'create-keychain', '-p', password, keychain])
        run(['security', 'unlock-keychain', '-p', password, keychain])
        run(['security', 'import', p12, '-k', keychain, '-P', password, '-T', '/usr/bin/codesign'])
        run(['security', 'set-key-partition-list', '-S', 'apple-tool:,apple:,codesign:', '-s', '-k', password, keychain])
        # Only the disposable GitHub runner may change trust. sudo -n and closed
        # stdin fail instead of waiting for a password/authorization prompt.
        trust_attempted = True
        run(['sudo', '-n', 'security', 'add-trusted-cert', '-d', '-r', 'trustRoot', '-p', 'codeSign',
             '-a', '/usr/bin/codesign', '-k', keychain, credentials / 'signer.crt'])
        identities = {name: hashlib.sha1((credentials / (name + '.der')).read_bytes()).hexdigest().upper()
                      for name in ('signer', 'wrong')}
        yield dict(identities, keychain=keychain, certificate=credentials / 'signer.der')
    finally:
        failures = []
        def attempt(label, action):
            try:
                action()
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                failures.append(label + ': ' + type(error).__name__)
        if trust_attempted:
            attempt('admin TEST trust removal', lambda: run([
                'sudo', '-n', 'security', 'remove-trusted-cert', '-d', credentials / 'signer.crt']))
        if keychain.exists():
            attempt('TEST keychain deletion', lambda: run(['security', 'delete-keychain', keychain]))
        attempt('TEST keychain absence', lambda: require(not keychain.exists(), 'TEST keychain remains'))
        attempt('search list preservation', lambda: require(
            run(['security', 'list-keychains', '-d', 'user']).stdout == before, 'keychain search list drift'))
        attempt('trust preservation', lambda: require(trust_inventory() == trust_before, 'user/admin trust drift'))
        report['macosCredentialCleanup'] = {'status': 'FAILED' if failures else 'verified', 'failures': failures,
            'scope': 'own admin codeSign/codesign TEST trust and temporary keychain; prior search list/user/admin trust preserved'}
        if failures:
            raise ValueError('Mac CI cleanup failed; no publication: ' + '; '.join(failures))


def trust_inventory():
    values = []
    for flags in ([], ['-d']):
        result = run(['security', 'dump-trust-settings', *flags], check=False)
        # A missing trust domain is normal; any other inventory error is a refusal.
        require(result.returncode == 0 or b'No Trust Settings' in result.stdout + result.stderr,
                'cannot inventory certificate trust')
        values.append((result.returncode, result.stdout, result.stderr))
    return values


@contextmanager
def provisioned_macos_credentials(certificate, thumbprint, keychain, report):
    """OWNER-RUN/CI only: use existing credentials; never import/trust/delete them."""
    certificate, keychain = Path(certificate).resolve(strict=True), Path(keychain).resolve(strict=True)
    require(certificate.is_file() and keychain.is_file(), 'provisioned TEST DER/keychain must already exist')
    require(re.fullmatch('[A-Fa-f0-9]{40}', thumbprint) and
            hashlib.sha1(certificate.read_bytes()).hexdigest().upper() == thumbprint.upper(),
            'provisioned TEST certificate thumbprint mismatch')
    wrong = '0' * 40 if thumbprint.upper() != '0' * 40 else '1' * 40
    try:
        yield {'signer': thumbprint.upper(), 'wrong': wrong, 'keychain': keychain, 'certificate': certificate}
    finally:
        report['macosCredentialCleanup'] = 'operator-owned provisioned identity left intact; no automatic OS setting mutation'


def decoded_path(data):
    """Consumer path policy, independent of update-bundle.py's encoder checks."""
    value = data.decode('ascii')
    require(1 <= len(data) <= 512, 'invalid decoded path length')
    for part in value.split('/'):
        require(1 <= len(part) <= 64 and part not in ('.', '..') and
                not part.startswith(' ') and not part.endswith(('.', ' ')) and
                re.fullmatch(r'[A-Za-z0-9._ -]+', part), 'invalid decoded path')
        stem = part.split('.')[0].upper()
        require(stem not in ('CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$') and
                not re.fullmatch(r'(COM|LPT)[0-9]', stem), 'reserved decoded path')
    return value


def decode(data, destination):
    """Independent, bounded file-data decoder; never extracts links or absolute paths."""
    offset = 0

    def take(length):
        nonlocal offset
        require(0 <= length <= len(data) - offset, 'truncated bundle')
        value = data[offset:offset + length]
        offset += length
        return value

    require(len(data) <= 134217728, 'bundle too large')
    require(take(16) == b'MINYAR-BUNDLE-1\n', 'wrong bundle domain')
    entry = decoded_path(take(struct.unpack('>I', take(4))[0]))
    count = struct.unpack('>I', take(4))[0]
    require(1 <= count <= 4096, 'invalid bundle entry count')
    seen, executable = set(), set()
    destination.mkdir()
    for _ in range(count):
        kind, mode, length, size = struct.unpack('>BBIQ', take(14))
        name = decoded_path(take(length))
        require(name.lower() not in seen, 'duplicate bundle path')
        seen.add(name.lower())
        path = destination / name
        require(path.parent == destination or path.parent.is_dir(), 'missing parent record')
        if kind == ord('D'):
            require(mode == size == 0, 'invalid directory record')
            path.mkdir()
        else:
            require(kind == ord('F') and mode in (0, 1), 'invalid file record')
            with path.open('xb') as stream:
                stream.write(take(size))
            path.chmod(0o755 if mode else 0o644)
            if mode:
                executable.add(name)
    require(offset == len(data) and entry in executable, 'bundle tail or nonexecutable entrypoint')
    return entry


def verify_envelope(envelope, artifact, public, openssl, scratch, *, domain=b'MINYAR-UPDATE-SIGNATURE-V1\0'):
    require(64 < len(envelope) <= 4160, 'invalid envelope size')
    signature, data = envelope[:64], envelope[64:]
    # Independent OpenSSL verify, never use the producer's public-key field as trust.
    scratch.mkdir(exist_ok=True)
    pub, sig, message = scratch / 'public.der', scratch / 'signature', scratch / 'message'
    pub.write_bytes(bytes.fromhex('302a300506032b6570032100') + public)
    sig.write_bytes(signature)
    message.write_bytes(domain + data)
    run([openssl, 'pkeyutl', '-verify', '-rawin', '-pubin', '-keyform', 'DER',
         '-inkey', pub, '-sigfile', sig, '-in', message])
    fields = data.decode('ascii').splitlines()
    require(len(fields) == 12 and data == ('\n'.join(fields) + '\n').encode('ascii'), 'invalid metadata structure')
    require(fields[:4] == ['MINYAR-UPDATE-1', 'org.minyar.test', TARGET, 'test'], 'metadata policy mismatch')
    require(fields[4:6] == ['1', '1.0.0'] and fields[8] == '100', 'metadata policy mismatch')
    require(all(re.fullmatch(r'0|[1-9][0-9]*', fields[index]) for index in (6, 7)), 'invalid TEST timestamp')
    issued, expires = int(fields[6]), int(fields[7])
    require(0 < expires - issued <= 604800 and issued <= int(time.time()) < expires,
            'expired or invalid TEST metadata')
    digest = hashlib.sha256(artifact).hexdigest()
    require(fields[10] == digest and fields[11] == str(len(artifact)), 'artifact hash/size mismatch')
    require(fields[9] == 'https://updates.invalid/releases/' + digest + '/TEST-fixture.bundle', 'artifact origin mismatch')
    return fields


def native_fixture(work, cc, native):
    source = work / 'tiny.c'
    source.write_text('int main(void) { return 0; }\n')
    tree = work / 'input'
    tree.mkdir()
    if native == 'macos':
        app = tree / 'TEST-fixture.app'
        (app / 'Contents/MacOS').mkdir(parents=True)
        resources = app / 'Contents/Resources'
        resources.mkdir()
        (resources / 'TEST-resource.txt').write_bytes(b'Minyar TEST ONLY resource\n')
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
            'CFBundleIdentifier': 'org.minyar.test', 'CFBundleName': 'Minyar TEST ONLY',
            'CFBundleExecutable': 'fixture', 'CFBundlePackageType': 'APPL',
            'CFBundleVersion': '1', 'CFBundleShortVersionString': '1.0.0'}))
        binary = app / 'Contents/MacOS/fixture'
        sdk = run(['xcrun', '--show-sdk-path'], text=True).stdout.strip()
        run([cc, '-isysroot', sdk, '-Os', source, '-o', binary])
        return app, 'TEST-fixture.app/Contents/MacOS/fixture', 'TEST-fixture.app/Contents/Resources/TEST-resource.txt'
    binary = tree / 'TEST-fixture.exe'
    run([cc, '-Os', source, '-o', binary])
    (tree / 'TEST-resource.txt').write_bytes(b'Minyar TEST ONLY resource\n')
    return binary, binary.name, 'TEST-resource.txt'


def authorize_context(args):
    """Called by both CLI and pipeline API before tools, output or cert dirs."""
    require((args.native == 'macos' and sys.platform == 'darwin') or
            (args.native == 'windows' and os.name == 'nt'),
            'native mode requires the actual OS; Windows requires native Python on Boat')
    require(args.native != 'windows' or args.signtool, '--signtool is required for Windows')
    require(args.native != 'macos' or not args.signtool, '--signtool is Windows-only')
    provisioned = [args.macos_certificate, args.macos_thumbprint, args.macos_keychain]
    if args.native == 'macos':
        require(not args.owned_boat_windows, '--owned-boat-windows is Windows-only')
        if args.ephemeral_macos_ci:
            require(not any(provisioned), 'choose ephemeral CI or provisioned Mac identity, never both')
            require_ephemeral_macos_ci(args.output, explicit=True)
        else:
            require(all(provisioned), 'Mac harness defaults to refusal: use explicit ephemeral CI or OWNER-RUN/CI provisioned TEST identity')
            with provisioned_macos_credentials(*provisioned, {}):
                pass
    else:
        require(not args.ephemeral_macos_ci and not any(provisioned), 'Mac credential options are Mac-only')
        require_owned_boat_windows(explicit=args.owned_boat_windows)
    release.test_output(args.output, '')


def pipeline(args, work, publication, report):
    authorize_context(args)
    if args.native == 'macos' and args.ephemeral_macos_ci:
        require_ephemeral_macos_ci(work, explicit=True)
    source, entry, resource = native_fixture(work, args.cc, args.native)
    credentials = work / 'credentials'
    credentials.mkdir(mode=0o700)
    if args.native == 'macos':
        credential_context = (macos_credentials(credentials, args.openssl, report, ephemeral_ci=args.ephemeral_macos_ci)
            if args.ephemeral_macos_ci else provisioned_macos_credentials(
                args.macos_certificate, args.macos_thumbprint, args.macos_keychain, report))
    else:
        credential_context = windows_credentials(credentials, report, owned_boat=args.owned_boat_windows)
    mutations = report['rejectedMutations'] = []
    with credential_context as identities:
        signed_root = publication / 'signed'
        signed_root.mkdir()
        signed_output = signed_root / source.name
        cert = identities.get('certificate', credentials / 'signer.der')
        if args.native == 'macos':
            release.test_macos(source, signed_output, cert, identities['signer'], identities['keychain'], openssl=args.openssl, run=run)
            verify = lambda root, thumb: release.verify_test_macos(root / source.name, thumb, run=run)
        else:
            release.test_windows(source, signed_output, cert, identities['signer'], args.signtool, openssl=args.openssl, run=run)
            shutil.copyfile(source.parent / resource, signed_root / resource)
            verify = lambda root, thumb: release.verify_test_windows(root / source.name, args.signtool, thumb, run=run)
        require(source.read_bytes() != signed_output.read_bytes() if args.native == 'windows' else
                not (source / 'Contents/_CodeSignature').exists(), 'signing did not preserve the unsigned input')
        verify(signed_root, identities['signer'])
        rejected(lambda: verify(signed_root, identities['wrong']), 'wrong OS certificate', mutations)
        artifact = publication / 'TEST-fixture.bundle'
        bundle.prepare(signed_root, artifact, entry)
        # A separate ephemeral update key: never reuse the OS certificate key.
        key = credentials / 'TEST-update.pem'
        passphrase_name = 'MINYAR_TEST_UPDATE_PASSPHRASE_' + secrets.token_hex(8).upper()
        environment = dict(os.environ)
        environment[passphrase_name] = secrets.token_hex(24)
        run([args.openssl, 'genpkey', '-algorithm', 'ED25519', '-aes-256-cbc', '-pass', 'env:' + passphrase_name,
             '-out', key], env=environment)
        # signed() consumes its passphrase through an environment name, as production does.
        os.environ[passphrase_name] = environment[passphrase_name]
        try:
            public_der = run([args.openssl, 'pkey', '-in', key, '-passin', 'env:' + passphrase_name,
                              '-pubout', '-outform', 'DER']).stdout
            require(len(public_der) == 44, 'unexpected Ed25519 public key')
            public = public_der[12:]
            issued = int(time.time()) - 1
            static = publication / 'TEST-local-publication'
            plan = manifest.prepare(artifact, static, 'org.minyar.test', TARGET, 'test', 1, '1.0.0',
                issued, issued + 3600, 100, 'https://updates.invalid',
                sign=lambda data: manifest.signed(data, key, args.openssl, passphrase_name, run=run))
        finally:
            del os.environ[passphrase_name]
        # Trust comes from the independently derived key; not from the upload plan.
        envelope = (static / plan['objects'][1]['key']).read_bytes()
        data = (static / plan['objects'][0]['key']).read_bytes()
        scratch = work / 'verify'
        verify_envelope(envelope, data, public, args.openssl, scratch)
        decoded = publication / 'decoded'
        require(decode(data, decoded) == entry, 'decoded entrypoint mismatch')
        verify(decoded, identities['signer'])
        run([decoded / entry])
        wrong_key = credentials / 'TEST-wrong-update.pem'
        run([args.openssl, 'genpkey', '-algorithm', 'ED25519', '-out', wrong_key])
        wrong_public = run([args.openssl, 'pkey', '-in', wrong_key, '-pubout', '-outform', 'DER']).stdout[12:]
        rejected(lambda: verify_envelope(envelope, data, wrong_public, args.openssl, scratch), 'wrong Ed25519 key', mutations)
        rejected(lambda: verify_envelope(envelope, data, public, args.openssl, scratch, domain=b'MINYAR-WRONG-DOMAIN\0'),
                 'wrong signature domain', mutations)
        modified = bytearray(envelope)
        modified[64 + len(b'MINYAR-UPDATE-1\n')] ^= 1
        rejected(lambda: verify_envelope(bytes(modified), data, public, args.openssl, scratch), 'metadata mutation', mutations)
        modified = bytearray(envelope)
        modified[0] ^= 1
        rejected(lambda: verify_envelope(bytes(modified), data, public, args.openssl, scratch), 'signature mutation', mutations)
        modified_artifact = data[:-1] + bytes([data[-1] ^ 1])
        rejected(lambda: verify_envelope(envelope, modified_artifact, public, args.openssl, scratch), 'artifact mutation', mutations)
        rejected(lambda: verify_envelope(envelope, data[:-1], public, args.openssl, scratch), 'artifact truncation', mutations)
        # Valid signatures on wrong policy metadata must also be rejected.
        for index, replacement in [(0, 'MINYAR-UPDATE-2'), (1, 'org.other.test'),
                (2, 'linux-x86_64'), (3, 'stable'), (4, '2'), (5, '9.0.0'), (7, '1'),
                (8, '10'), (9, 'https://wrong.invalid/releases/fixture')]:
            fields = envelope[64:].decode('ascii').splitlines()
            fields[index] = replacement
            metadata = ('\n'.join(fields) + '\n').encode('ascii')
            os.environ[passphrase_name] = environment[passphrase_name]
            try:
                signature, _ = manifest.signed(metadata, key, args.openssl, passphrase_name, run=run)
            finally:
                del os.environ[passphrase_name]
            rejected(lambda: verify_envelope(signature + metadata, data, public, args.openssl, scratch),
                     'signed policy field mutation ' + str(index), mutations)
        # Decoded changes must also fail after re-encoding with the existing encoder.
        resource_path = decoded / resource
        resource_path.write_bytes(b'unsigned altered resource\n')
        changed = work / 'TEST-resource-mutated.bundle'
        bundle.prepare(decoded, changed, entry)
        rejected(lambda: verify_envelope(envelope, changed.read_bytes(), public, args.openssl, scratch), 'resource mutation', mutations)
        if args.native == 'macos':
            rejected(lambda: verify(decoded, identities['signer']), 'macOS sealed resource mutation', mutations)
        # Separate executable mutation, after restoring the decoded original tree.
        shutil.rmtree(decoded)
        decode(data, decoded)
        executable = decoded / entry
        body = executable.read_bytes()
        require(len(body) > 128, 'native fixture is too small')
        executable.write_bytes(body[:128] + bytes([body[128] ^ 1]) + body[129:])
        rejected(lambda: verify(decoded, identities['signer']), 'native executable mutation', mutations)
        shutil.rmtree(decoded)
        decode(data, decoded)
        verify(decoded, identities['signer'])
        shutil.copyfile(cert, publication / 'TEST-os-certificate.der')
        (publication / 'TEST-update-public-key.hex').write_text(public.hex() + '\n')
        report.update(osCertificateSHA1=identities['signer'], ed25519PublicKeyHex=public.hex(),
                      artifactSHA256=hashlib.sha256(data).hexdigest(), artifactBytes=len(data),
                      nativeVerification='real OS signature verified before and after bundle decoding')
    # Credential files and the private keys disappear before the public generation is visible.
    shutil.rmtree(credentials)
    require(not credentials.exists(), 'TEST credential files remain after cleanup')
    report['privateCredentialFiles'] = 'removed before publication'


TARGET = ''


def main():
    global TARGET
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', choices=['macos', 'windows'], required=True)
    parser.add_argument('--output', required=True, help='new TEST-* directory, atomically published after cleanup')
    parser.add_argument('--openssl', required=True, help='OpenSSL 3 executable')
    parser.add_argument('--cc', required=True, help='native clang executable and configured linker/SDK')
    parser.add_argument('--signtool', help='required Windows SDK SignTool executable on Boat')
    parser.add_argument('--ephemeral-macos-ci', action='store_true', help='allow automatic TEST credentials ONLY on GitHub-hosted ephemeral macOS CI')
    parser.add_argument('--macos-certificate', help='OWNER-RUN/CI alternative: already-provisioned TEST DER certificate')
    parser.add_argument('--macos-thumbprint', help='OWNER-RUN/CI alternative: SHA1 of existing TEST DER certificate')
    parser.add_argument('--macos-keychain', help='OWNER-RUN/CI alternative: existing unlocked TEST identity keychain; never changed')
    parser.add_argument('--owned-boat-windows', action='store_true', help='acknowledge the exclusive OWN Boat Windows signing slot')
    parser.add_argument('--report', help='optional new TEST-*.json cleanup/status report, including runtime failures')
    args = parser.parse_args()
    report, report_path, work, publication = None, None, None, None
    published = False
    try:
        authorize_context(args)
        output = release.test_output(args.output, '')
        if args.report:
            report_path = release.test_output(args.report, '.json')
            require(not report_path.resolve().is_relative_to(output.resolve()), 'external report cannot be inside unpublished output')
        arch = platform.machine().lower()
        require(arch in ('arm64', 'aarch64', 'amd64', 'x86_64'), 'unsupported native architecture')
        TARGET = args.native + ('-arm64' if arch in ('arm64', 'aarch64') else '-x86_64')
        report = {'schema': 1, 'testOnly': True, 'native': args.native, 'target': TARGET, 'status': 'running',
                  'sourceSHA256': {str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                      for path in ('scripts/release.py', 'scripts/update-bundle.py', 'scripts/update-manifest.py', 'tests/release-pipeline.py')},
                  'externalPublication': 'none', 'productionAcceptance': 'not performed',
                  'appleNotarization': 'unavailable: self-signed TEST certificate cannot obtain Apple notarization, staple or Gatekeeper acceptance'
                      if args.native == 'macos' else 'not applicable',
                  'windowsTimestamp': 'TEST ONLY: omitted; production still requires RFC3161 SHA256 and /tw'}
        require(run([args.openssl, 'version'], text=True).stdout.startswith('OpenSSL 3.'), 'OpenSSL 3 required')
        output.parent.mkdir(parents=True, exist_ok=True)
        # Keep the public-only generation beside, rather than inside, private
        # staging so complete staging cleanup can succeed before publication.
        publication = Path(tempfile.mkdtemp(prefix='.minyar-test-generation-', dir=output.parent))
        with tempfile.TemporaryDirectory(prefix='.minyar-test-pipeline-', dir=output.parent) as directory:
            work = Path(directory)
            pipeline(args, work, publication, report)
        require(not work.exists(), 'private staging remains; no generation published')
        report['stagingCleanup'] = 'verified: removed before publication'
        report.update(status='passed', generationPublished=True)
        (publication / 'TEST-report.json').write_text(json.dumps(report, indent=2) + '\n')
        release.publish_directory(publication, output)
        published = True
        if report_path:
            write_report(report_path, report)
        print(json.dumps(report, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        detail = getattr(error, 'stderr', '') or ''
        if isinstance(detail, bytes):
            detail = detail.decode(errors='replace')
        if report is not None:
            report.update(status='FAILED', errorType=type(error).__name__, generationPublished=published)
            if publication is not None and publication.exists():
                try:
                    shutil.rmtree(publication)
                except OSError as cleanup_error:
                    report['unpublishedGenerationCleanupError'] = type(cleanup_error).__name__
            report['unpublishedGenerationCleanup'] = ('verified: absent' if publication is None or
                not publication.exists() else 'FAILED: unpublished staging remains')
            report['stagingCleanup'] = ('not created' if work is None else
                'verified: removed' if not work.exists() else 'not verified')
            if report_path:
                try:
                    write_report(report_path, report)
                except OSError as report_error:
                    report['externalReportError'] = type(report_error).__name__
            print(json.dumps(report, indent=2), file=sys.stderr)
        # Subprocess args can contain the ephemeral keychain password: omit them.
        message = str(error) if not isinstance(error, subprocess.SubprocessError) else type(error).__name__
        outcome = ('generation published; external status reporting failed' if published else 'no successful generation')
        parser.exit(1, f'TEST pipeline failed; {outcome}: {message}\n{detail}')


def write_report(path, report):
    """An explicit, public evidence file; credentials are never included."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='.minyar-test-report-', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write((json.dumps(report, indent=2) + '\n').encode())
            stream.close()
            os.link(temporary, path)  # Fail rather than overwrite a prior report.
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
