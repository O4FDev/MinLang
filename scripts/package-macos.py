#!/usr/bin/env python3
"""Build and audit a native macOS distribution. No client-side Python is needed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile

LLVM_VERSION = "23.1.2"
MINIMUM = (14, 0)
ROOT = Path(__file__).resolve().parent.parent
EXECUTABLES = [
    "minyarc", "minyarc-modules", "minyar-module-build",
    "tooling/tools/clang-driver", "tooling/scripts/macos-app",
    *("tooling/tools/" + source.stem for source in sorted((ROOT / "tools").glob("*-cli.min"))),
]
RUNTIMES = [
    "minyar-default-runtime.o", "minyar-default-runtime-release.ll",
    "minyar-runtime-eager.o", "minyar-runtime-eager-release.ll",
]


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def output(*args):
    return run(*args, capture_output=True, text=True).stdout


def audit(binary, arch):
    """Reject Homebrew paths, a wrong CPU and accidental build-host OS floors."""
    if output("lipo", "-archs", binary).strip() != arch:
        raise ValueError(f"{binary}: expected a native {arch} executable/object")
    commands = output("otool", "-l", binary)
    versions = re.findall(r"^\s*minos (\d+)\.(\d+)", commands, re.M)
    versions += re.findall(r"cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version (\d+)\.(\d+)", commands)
    if not versions or any(tuple(map(int, version)) > MINIMUM for version in versions):
        raise ValueError(f"{binary}: deployment target exceeds macOS 14.0 or is missing")
    for line in output("otool", "-L", binary).splitlines()[1:]:
        dependency = line.strip().split(" (", 1)[0]
        if not dependency.startswith(("/usr/lib/", "/System/Library/")):
            raise ValueError(f"{binary}: non-system dynamic dependency: {dependency}")


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=True, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
    else:
        shutil.copy2(source, destination, follow_symlinks=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm", required=True, type=Path, help="native LLVM 23.1.2 prefix (clang, lld, dsymutil, lib/clang)")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/releases")
    parser.add_argument("--no-build", action="store_true", help="audit and package already built release artifacts")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() not in ("arm64", "x86_64"):
        parser.error("run on a native Apple silicon or Intel Mac")
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]*", args.version):
        parser.error("version must contain only letters, numbers, dots, plus and hyphens")
    llvm = args.llvm.resolve()
    if not re.search(r"\bclang version 23\.1\.2\b", output(llvm / "bin/clang", "--version")):
        parser.error(f"LLVM {LLVM_VERSION} is required")
    if not re.match(r"^LLD 23\.1\.2(?:\s|$)", output(llvm / "bin/ld64.lld", "--version")):
        parser.error(f"LLD {LLVM_VERSION} is required")
    arch = platform.machine()
    env = os.environ.copy()
    for inherited in ("MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS"):
        env.pop(inherited, None)
    env.update(CC=str(llvm / "bin/clang"), LLVM_CC=str(llvm / "bin/clang"), MACOSX_DEPLOYMENT_TARGET="14.0")
    if not args.no_build:
        # No -march=native: every executable must run on the baseline CPU.
        linker = shlex.quote("--ld-path=" + str(llvm / "bin/ld64.lld"))
        run("make", "-C", ROOT, "LIMITED=", "CC=" + str(llvm / "bin/clang"), "LLVM_CC=" + str(llvm / "bin/clang"),
            "CPPFLAGS=-isystem vendor", "LDLIBS=-lm",
            "CFLAGS=-std=c11 -O2 -Wall -Wextra -Werror " + linker,
            "LLVM_FLAGS=-O2 -Wno-override-module " + linker,
            "COMPILER_LTO_FLAGS=-flto=thin " + linker,
            "COMPILER_RUNTIME_FLAGS=-DMINYAR_COMPILER_ARENA", "PROGRAM_RUNTIME_FLAGS=-DMINYAR_SYSTEM_HEAP=1",
            *("build/" + name for name in EXECUTABLES + RUNTIMES), env=env)
    args.output.mkdir(parents=True, exist_ok=True)
    name = f"minyar-{args.version}-macos-{arch}"
    archive = args.output / f"{name}.tar.gz"
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    if archive.exists() or checksum.exists():
        raise ValueError(f"refusing to overwrite release: {archive}")
    with tempfile.TemporaryDirectory(prefix=".minyar-package-", dir=args.output) as temporary:
        stage = Path(temporary) / name
        stage.mkdir()
        for item in ["minyar", "Makefile", "LICENSE", "compiler", "runtime", "library", "tools", "scripts", "bootstrap", "vendor", "build-support", "install"]:
            copy(ROOT / item, stage / item)
        for item in EXECUTABLES + RUNTIMES:
            copy(ROOT / "build" / item, stage / "build" / item)
        for item in ["clang", "lld", "dsymutil"]:
            target = "clang.bin" if item == "clang" else item
            copy(llvm / "bin" / item, stage / "toolchain/bin" / target)
        (stage / "toolchain/bin/ld64.lld").symlink_to("lld")
        copy(ROOT / "tools/bundled-clang.sh", stage / "toolchain/bin/clang")
        (stage / "toolchain/bin/clang").chmod(0o755)
        copy(llvm / "lib/clang", stage / "toolchain/lib/clang")
        copy(ROOT / "vendor/llvm-LICENSE.txt", stage / "toolchain/LICENSE.txt")
        copy(ROOT / "scripts/install-macos.sh", stage / "install.sh")
        (stage / "minyar").chmod(0o755)
        (stage / ".minyar-distribution").write_text("1\n")
        (stage / "distribution.arch").write_text(arch + "\n")
        (stage / "distribution.version").write_text(args.version + "\n")
        audited = [stage / "build" / item for item in EXECUTABLES]
        audited += [stage / "toolchain/bin" / item for item in ["clang.bin", "lld", "dsymutil"]]
        audited += [stage / "build" / item for item in RUNTIMES if item.endswith(".o")]
        for binary in audited:
            audit(binary, arch)
        for entry in stage.rglob("*"):
            if entry.is_symlink() and not entry.resolve().is_relative_to(stage.resolve()):
                raise ValueError(f"distribution symlink escapes its root: {entry}")
        metadata = {"version": args.version, "arch": arch, "minimum_macos": "14.0", "llvm": LLVM_VERSION,
                    "files": {str(path.relative_to(stage)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted(stage.rglob("*")) if path.is_file()}}
        (stage / "distribution.json").write_text(json.dumps(metadata, indent=2) + "\n")
        staged_archive = Path(temporary) / archive.name
        with tarfile.open(staged_archive, "w:gz") as tar:
            tar.add(stage, arcname=name)
        digest = hashlib.sha256(staged_archive.read_bytes()).hexdigest()
        staged_archive.rename(archive)
        checksum.write_text(f"{digest}  {archive.name}\n")
    print(f"Packaged {archive}\nSHA-256: {digest}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"package-macos: {error}") from error
