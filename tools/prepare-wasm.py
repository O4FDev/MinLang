#!/usr/bin/env python3
"""Fetch integrity-pinned browser tools; no npm install or package scripts."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "wasm"
PACKAGES = (
    ("clang", "22.0.0-git20542-10",
     "https://registry.npmjs.org/@yowasp/clang/-/clang-22.0.0-git20542-10.tgz",
     "V31/z9GrJECKeACTDUyvg2llbEUiFi3bxtL5HSg7H/6sydSxdI/AoVAD9F5ozrfLjotWl0B9rghR87m+DUM/zg=="),
    ("wasi", "0.4.2",
     "https://registry.npmjs.org/@bjorn3/browser_wasi_shim/-/browser_wasi_shim-0.4.2.tgz",
     "/iHkCVUG3VbcbmEHn5iIUpIrh7a7WPiwZ3sHy4HZKZzBdSadwdddYDZAII2zBvQYV0Lfi8naZngPCN7WPHI/hA=="),
)


def unpack(archive, destination):
    """Accept regular files/directories only, with no path traversal."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError(f"unsafe archive path: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
            else:
                raise ValueError(f"unsupported archive entry: {member.name}")


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / ".prepared").unlink(missing_ok=True)
    for name, version, url, integrity in PACKAGES:
        archive = BUILD / f"{name}-{version}.tgz"
        if not archive.exists():
            print(f"Downloading {name} {version}", flush=True)
            temporary = archive.with_suffix(".download")
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as out:
                shutil.copyfileobj(response, out)
            temporary.replace(archive)
        expected = base64.b64decode(integrity, validate=True)
        if hashlib.sha512(archive.read_bytes()).digest() != expected:
            archive.unlink()
            raise ValueError(f"{name} archive failed SHA-512 integrity verification")
        destination = BUILD / name
        if destination.exists():
            shutil.rmtree(destination)
        unpack(archive, destination)
    if (BUILD / "sysroot").exists():
        shutil.rmtree(BUILD / "sysroot")
    unpack(BUILD / "clang/package/gen/llvm-resources.tar", BUILD / "sysroot")
    (BUILD / "dependencies.json").write_text(json.dumps({
        name: {"version": version, "url": url, "integrity": "sha512-" + integrity}
        for name, version, url, integrity in PACKAGES
    }, indent=2) + "\n")
    (BUILD / ".prepared").touch()
    print(f"Browser tools ready in {BUILD}", flush=True)


if __name__ == "__main__":
    main()
