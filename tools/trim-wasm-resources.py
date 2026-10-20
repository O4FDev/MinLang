#!/usr/bin/env python3
"""Publish only pinned WASI link resources; never alter the build sysroot."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile


PACKAGE = "@yowasp/clang"
PACKAGE_VERSION = "22.0.0-git20542-10"
PACKAGE_URL = "https://registry.npmjs.org/@yowasp/clang/-/clang-22.0.0-git20542-10.tgz"
PACKAGE_INTEGRITY = (
    "sha512-V31/z9GrJECKeACTDUyvg2llbEUiFi3bxtL5HSg7H/6sydSxdI/AoVAD9F5ozrfLjotWl0B9rghR87m+DUM/zg=="
)
RESOURCE_SHA256 = "79eef0c336fe55cf03ff8f5b42b784c8168f929a3603138b2c6301f4601e4c86"
REQUIRED_MEMBERS = (
    "lib/wasm32-unknown-wasip1/libclang_rt.builtins.a",
    "lib/wasm32-wasip1/crt1-command.o",
    "lib/wasm32-wasip1/crt1-reactor.o",
    "lib/wasm32-wasip1/crt1.o",
    "lib/wasm32-wasip1/libc.a",
    "lib/wasm32-wasip1/libm.a",
    "lib/wasm32-wasip1/libsetjmp.a",
)
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 8192


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_name(member):
    name = member.name
    if (not name or name.startswith("/") or "\\" in name
            or re.match(r"^[A-Za-z]:", name) or "\0" in name):
        raise ValueError(f"unsafe archive path: {name!r}")
    if member.type == tarfile.DIRTYPE:
        name = name.removesuffix("/")
    if any(part in ("", ".", "..") for part in name.split("/")):
        raise ValueError(f"unsafe archive path: {member.name!r}")
    if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
        raise ValueError(f"unsupported archive entry: {name!r}")
    if member.sparse is not None or any("sparse" in key for key in member.pax_headers):
        raise ValueError(f"sparse archive entry: {name!r}")
    return name


def ensure_separate_paths(paths):
    for index, first in enumerate(paths):
        for second in paths[index + 1:]:
            if first.resolve() == second.resolve():
                raise ValueError("source, destination and manifest must be separate files")
            if first.exists() and second.exists() and first.samefile(second):
                raise ValueError("source, destination and manifest must not be hard links")


class ResourceTarInfo(tarfile.TarInfo):
    def get_info(self):
        info = super().get_info()
        # YoWASP's existing browser unpacker expects directory header names
        # without a trailing slash, matching its pinned original archive.
        info["name"] = self.name
        return info


def normalized_info(name, *, directory=False, size=0):
    info = ResourceTarInfo(name)
    info.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
    info.mode = 0o755 if directory else 0o644
    info.size = size
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def trim_resources(source: Path, dest: Path, manifest: Path, *,
                   expected_source_sha256=RESOURCE_SHA256):
    """Validate all entries and retain seven files byte for byte.

    The default enforces the published resource pin. A different explicit digest
    supports synthetic fixtures or a deliberately reviewed future source pin;
    both the expected digest and published pin remain visible in the manifest.
    """
    source, destination, manifest = map(Path, (source, dest, manifest))
    ensure_separate_paths((source, destination, manifest))
    if not re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256):
        raise ValueError("expected source SHA-256 must contain 64 lowercase hex digits")
    # Parse the same immutable bytes that were hashed, including if another
    # process replaces or modifies the source path during publication.
    with source.open("rb") as input_file:
        source_bytes = input_file.read(MAX_SOURCE_BYTES + 1)
    source_size = len(source_bytes)
    if source_size > MAX_SOURCE_BYTES:
        raise ValueError("source archive exceeds 64 MiB")
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != expected_source_sha256:
        raise ValueError("source archive failed SHA-256 integrity verification")

    retained = {}
    seen = {}
    with tarfile.open(fileobj=io.BytesIO(source_bytes), mode="r:", errorlevel=2) as archive:
        for member in archive:
            name = checked_name(member)
            if name in seen:
                raise ValueError(f"duplicate archive entry: {name!r}")
            seen[name] = member.type
            if len(seen) > MAX_MEMBERS:
                raise ValueError("source archive contains too many entries")
            if member.size < 0 or member.offset_data + member.size > source_size:
                raise ValueError(f"truncated archive entry: {name!r}")
            if name not in REQUIRED_MEMBERS:
                continue
            if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE):
                raise ValueError(f"required resource is not a regular file: {name!r}")
            with archive.extractfile(member) as content:
                data = content.read()
            if len(data) != member.size:
                raise ValueError(f"truncated required resource: {name!r}")
            retained[name] = data
    for name in seen:
        for parent in PurePosixPath(name).parents:
            if str(parent) != "." and seen.get(str(parent), tarfile.DIRTYPE) != tarfile.DIRTYPE:
                raise ValueError(f"archive parent is not a directory: {str(parent)!r}")
    missing = set(REQUIRED_MEMBERS) - retained.keys()
    if missing:
        raise ValueError("missing required resources: " + ", ".join(sorted(missing)))

    directories = {str(parent) for name in REQUIRED_MEMBERS
                   for parent in PurePosixPath(name).parents if str(parent) != "."}
    temporary_paths = []
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
            output_path = Path(output.name)
            temporary_paths.append(output_path)
            with tarfile.open(fileobj=output, mode="w:", format=tarfile.USTAR_FORMAT) as archive:
                for name in sorted(directories, key=lambda item: (item.count("/"), item)):
                    archive.addfile(normalized_info(name, directory=True))
                for name in REQUIRED_MEMBERS:
                    data = retained[name]
                    archive.addfile(normalized_info(name, size=len(data)), io.BytesIO(data))
        document = {
            "schema": "minyar.wasm-resources/1",
            "upstream": {
                "package": PACKAGE,
                "version": PACKAGE_VERSION,
                "url": PACKAGE_URL,
                "integrity": PACKAGE_INTEGRITY,
                "resource_member": "package/gen/llvm-resources.tar",
                "resource_sha256": RESOURCE_SHA256,
            },
            "source": {
                "sha256": source_hash,
                "expected_sha256": expected_source_sha256,
                "matches_published_pin": source_hash == RESOURCE_SHA256,
                "size_bytes": source_size,
            },
            "transformation": {
                "name": "minyar-wasi-link-resources",
                "version": 1,
                "format": "ustar",
                "mtime": 0,
                "uid": 0,
                "gid": 0,
                "uname": "",
                "gname": "",
                "file_mode": "0644",
                "directory_mode": "0755",
                "directory_trailing_slash": False,
                "order": "directories by depth then name; files by name",
                "preserves_retained_file_bytes": True,
            },
            "output": {
                "sha256": sha256_file(output_path),
                "size_bytes": output_path.stat().st_size,
                "files": [{"name": name, "size_bytes": len(retained[name]),
                           "sha256": hashlib.sha256(retained[name]).hexdigest()}
                          for name in REQUIRED_MEMBERS],
            },
        }
        with tempfile.NamedTemporaryFile(dir=manifest.parent, delete=False) as output:
            manifest_path = Path(output.name)
            temporary_paths.append(manifest_path)
            output.write((json.dumps(document, indent=2, sort_keys=True) + "\n").encode())
        output_path.chmod(0o644)
        manifest_path.chmod(0o644)
        os.replace(output_path, destination)
        os.replace(manifest_path, manifest)
        return document
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="original pinned llvm-resources.tar")
    parser.add_argument("destination", type=Path, help="separate browser resource archive")
    parser.add_argument("manifest", type=Path, help="separate derivation manifest JSON")
    args = parser.parse_args()
    try:
        document = trim_resources(args.source, args.destination, args.manifest)
    except (OSError, ValueError, tarfile.TarError) as error:
        parser.exit(1, f"trim-wasm-resources: {error}\n")
    print(f"Browser WASI resources: {document['output']['size_bytes']} bytes; "
          f"SHA-256 {document['output']['sha256']}")


if __name__ == "__main__":
    main()
