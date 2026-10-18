#!/usr/bin/env python3
"""Prepare a local signed release directory. Never upload or publish anything."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import urlsplit

NAMESPACE = "toolchain@minyar"
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")


def run(*arguments):
    return subprocess.run([str(value) for value in arguments], check=True, capture_output=True, text=True)


def atomic(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        output.write(data)
    temporary.chmod(mode)
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sign(data, destination, key, public_key):
    with tempfile.TemporaryDirectory(prefix=".minyar-sign-", dir=destination.parent) as directory:
        source = Path(directory) / "message"
        source.write_bytes(data)
        run("ssh-keygen", "-Y", "sign", "-f", key, "-n", NAMESPACE, source)
        signature = source.with_suffix(".sig").read_bytes()
        allowed = Path(directory) / "allowed"
        allowed.write_text(f'minyar-release namespaces="{NAMESPACE}" {public_key}\n')
        subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I", "minyar-release", "-n", NAMESPACE, "-s", str(source.with_suffix(".sig"))], input=data, check=True, capture_output=True)
    atomic(destination, signature)


def prepare(args):
    if not VERSION.fullmatch(args.version) or len(args.version) > 80 or ".." in args.version:
        raise ValueError("version must be canonical MAJOR.MINOR.PATCH, optionally with prerelease/build identifiers")
    server = args.server.rstrip("/")
    url = urlsplit(server)
    if not re.fullmatch(r"[A-Za-z0-9._~:/+-]+", server) or url.query or url.fragment or url.username or url.password:
        raise ValueError("server URL must not contain credentials, query parameters or shell characters")
    if url.scheme != "https" and not (url.scheme == "http" and url.hostname == "127.0.0.1" and url.port):
        raise ValueError("use an HTTPS host or an HTTP loopback test server")
    key_fields = args.public_key.read_text().split()
    if len(key_fields) < 2 or key_fields[0] != "ssh-ed25519" or not re.fullmatch(r"[A-Za-z0-9+/=]+", key_fields[1]):
        raise ValueError("expected an Ed25519 OpenSSH public key")
    public_key = " ".join(key_fields[:2])
    run("ssh-keygen", "-l", "-f", args.public_key)
    name = args.archive.name
    match = re.fullmatch(r"minyar-(.+)-(macos|linux)-(arm64|x86_64)\.tar\.gz", name)
    if not match or match[1] != args.version:
        raise ValueError("archive filename must be minyar-VERSION-{macos,linux}-{arm64,x86_64}.tar.gz")
    root = name.removesuffix(".tar.gz")
    with tarfile.open(args.archive, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        for required in ("minyar", "install/install.sh", "install/manager.sh"):
            member = members.get(f"{root}/{required}")
            if member is None or not member.isfile():
                raise ValueError(f"archive is missing {required}; rebuild with the current packager")
    output = args.output.resolve()
    release = output / "releases" / args.version
    release.mkdir(parents=True, exist_ok=True)
    digest = sha256(args.archive)
    destination = release / name
    if destination.exists():
        previous = sha256(destination)
        if previous != digest:
            raise ValueError(f"release archives are immutable: {destination}")
    else:
        with tempfile.NamedTemporaryFile(dir=release, delete=False) as source:
            temporary = Path(source.name)
        shutil.copyfile(args.archive, temporary)
        temporary.replace(destination)
    destination.chmod(0o644)
    records = {}
    checksums = release / "SHA256SUMS"
    if checksums.exists():
        for line in checksums.read_text().splitlines():
            checksum, filename = line.split()
            if not re.fullmatch(r"[0-9a-f]{64}", checksum) or Path(filename).name != filename:
                raise ValueError("existing release checksum manifest is malformed")
            records[filename] = checksum
    if name in records and records[name] != digest:
        raise ValueError("the existing signed checksum differs; choose a new release version")
    records[name] = digest
    content = "".join(f"{checksum}  {filename}\n" for filename, checksum in sorted(records.items())).encode()
    sign(content, release / "SHA256SUMS.sig", args.signing_key, public_key)
    atomic(checksums, content)
    template = Path(__file__).with_name("install.sh").read_text()
    installer = template.replace("@MINYAR_RELEASE_KEY@", public_key, 1).replace("@MINYAR_DIST_URL@", server, 1)
    atomic(output / "install", installer.encode(), 0o755)
    if args.latest:
        content = (args.version + "\n").encode()
        sign(content, output / "latest.sig", args.signing_key, public_key)
        atomic(output / "latest", content)
    print(f"Prepared {release}\nSHA-256: {digest}\nInstaller: {output / 'install'}\nNothing was uploaded or published.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--signing-key", type=Path, required=True, help="private key, or public key with its private half in ssh-agent")
    parser.add_argument("--server", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--latest", action="store_true", help="also sign and select this version as latest")
    prepare(parser.parse_args())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
        raise SystemExit(f"prepare-release: {error}") from error
