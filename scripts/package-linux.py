#!/usr/bin/env python3
"""Build and audit a native glibc Linux release with private LLVM libraries."""
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

ROOT = Path(__file__).resolve().parent.parent
LLVM_VERSION = "23.1.3"
EXECUTABLES = [
    "minyarc", "minyarc-modules", "minyar-module-build",
    "tooling/tools/clang-driver",
    *("tooling/tools/" + source.stem for source in sorted((ROOT / "tools").glob("*-cli.min"))),
]
RUNTIMES = [
    "minyar-default-runtime.o", "minyar-default-runtime-release.ll",
    "minyar-runtime-eager.o", "minyar-runtime-eager-release.ll",
]


def run(*arguments, **options):
    return subprocess.run([str(value) for value in arguments], check=True, **options)


def output(*arguments, **options):
    environment = dict(options.pop("env", os.environ))
    environment["LC_ALL"] = "C"
    return run(*arguments, text=True, capture_output=True, env=environment, **options).stdout


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, symlinks=True,
                        ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
    else:
        shutil.copy2(source, target, follow_symlinks=True)


def audit(binary, arch, minimum, root):
    header = output("readelf", "-h", binary)
    machine = "AArch64" if arch == "arm64" else "Advanced Micro Devices X86-64"
    if not re.search(r"Class:\s+ELF64\b", header) or not re.search(r"Machine:\s+" + re.escape(machine) + r"\s*$", header, re.M):
        raise ValueError(f"{binary}: expected native 64-bit {arch} ELF")
    if "little endian" not in header:
        raise ValueError(f"{binary}: expected little-endian ELF")
    interpreter = re.findall(r"Requesting program interpreter:\s*(.*?)\]", output("readelf", "-l", binary))
    expected = "/lib/ld-linux-aarch64.so.1" if arch == "arm64" else "/lib64/ld-linux-x86-64.so.2"
    if interpreter and interpreter != [expected]:
        raise ValueError(f"{binary}: unexpected ELF interpreter: {interpreter}")
    versions = output("readelf", "--version-info", binary)
    if "GLIBC_PRIVATE" in versions:
        raise ValueError(f"{binary}: private glibc ABI is not portable")
    for version in re.findall(r"\bGLIBC_(\d+(?:\.\d+)+)\b", versions):
        if tuple(map(int, version.split("."))) > minimum:
            raise ValueError(f"{binary}: needs glibc {version}, above the declared minimum")
    dynamic = output("readelf", "-d", binary)
    for name in re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic):
        if "/" in name:
            raise ValueError(f"{binary}: absolute shared-library dependency: {name}")
    for paths in re.findall(r"\((?:RUNPATH|RPATH)\).*?\[(.*?)\]", dynamic):
        for path in paths.split(":"):
            if path != "$ORIGIN" and not path.startswith("$ORIGIN/"):
                raise ValueError(f"{binary}: non-relocatable library search path: {path}")
            if path != "$ORIGIN":
                relative = path.removeprefix("$ORIGIN/")
                if "$" in relative or not (binary.parent / relative).resolve().is_relative_to(root.resolve()):
                    raise ValueError(f"{binary}: library search path escapes the distribution: {path}")


def dependencies(binary, environment):
    if "(NEEDED)" not in output("readelf", "-d", binary):
        return {}
    text = output("ldd", binary, env=environment)
    if "not found" in text:
        raise ValueError(f"{binary}: missing build-host runtime dependency:\n{text}")
    found = {}
    for name, path in re.findall(r"^\s*(\S+)\s+=>\s+(/[^\n]+?)\s+\(0x[0-9a-f]+\)", text, re.M):
        found[name] = Path(path)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm", type=Path, required=True, help="native LLVM 23.1.3 prefix")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/releases")
    parser.add_argument("--minimum-glibc", default="2.39", help="declared ABI floor, audited against every bundled ELF")
    parser.add_argument("--no-build", action="store_true", help="audit and package existing native release builds")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() not in ("aarch64", "arm64", "x86_64"):
        parser.error("run on a native Arm64 or x86-64 glibc Linux host")
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]*", args.version):
        parser.error("version must contain only letters, numbers, dots, plus and hyphens")
    if not re.fullmatch(r"[0-9]+\.[0-9]+", args.minimum_glibc):
        parser.error("minimum glibc must be MAJOR.MINOR")
    minimum = tuple(map(int, args.minimum_glibc.split(".")))
    host_libc = output("getconf", "GNU_LIBC_VERSION").strip()
    if not host_libc.startswith("glibc "):
        parser.error("musl Linux requires a separate build and runtime contract")
    arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64"
    name = f"minyar-{args.version}-linux-{arch}"
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / f"{name}.tar.gz"
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    if archive.exists() or checksum.exists():
        raise ValueError(f"refusing to overwrite release: {archive}")
    llvm = args.llvm.resolve()
    if not re.search(r"\bclang version 23\.1\.2\b", output(llvm / "bin/clang", "--version")):
        parser.error(f"LLVM {LLVM_VERSION} is required")
    if not re.search(r"\bLLD 23\.1\.2\b", output(llvm / "bin/ld.lld", "--version")):
        parser.error(f"LLD {LLVM_VERSION} is required")
    environment = os.environ.copy()
    for inherited in ("MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "LD_PRELOAD", "LD_LIBRARY_PATH"):
        environment.pop(inherited, None)
    if not args.no_build:
        linker = shlex.quote("--ld-path=" + str(llvm / "bin/ld.lld"))
        run("make", "-j1", "-C", ROOT, "CC=" + str(llvm / "bin/clang"), "LLVM_CC=" + str(llvm / "bin/clang"),
            "CPPFLAGS=-isystem vendor", "LDLIBS=-lm", "CFLAGS=-std=c11 -O2 -Wall -Wextra -Werror",
            "LLVM_FLAGS=-O2 -Wno-override-module " + linker,
            "COMPILER_LTO_FLAGS=-flto=thin -Wl,--threads=1 " + linker,
            "COMPILER_RUNTIME_FLAGS=-DMINYAR_COMPILER_ARENA", "PROGRAM_RUNTIME_FLAGS=-DMINYAR_SYSTEM_HEAP=1",
            *("build/" + item for item in EXECUTABLES + RUNTIMES), env=environment)
    with tempfile.TemporaryDirectory(prefix=".minyar-package-", dir=args.output) as temporary:
        stage = Path(temporary) / name
        stage.mkdir()
        for item in ["minyar", "Makefile", "LICENSE", "compiler", "runtime", "library", "tools", "scripts", "bootstrap", "vendor", "build-support", "install"]:
            copy(ROOT / item, stage / item)
        copy(ROOT / "docs/linux-distribution.md", stage / "docs/linux-distribution.md")
        for item in EXECUTABLES + RUNTIMES:
            copy(ROOT / "build" / item, stage / "build" / item)
        for source, target in [("clang", "clang"), ("ld.lld", "ld.lld")]:
            copy(llvm / "bin" / source, stage / "toolchain/libexec" / target)
        for source, target in [("bundled-linux-clang.sh", "clang"), ("bundled-linux-lld.sh", "ld.lld")]:
            copy(ROOT / "tools" / source, stage / "toolchain/bin" / target)
            (stage / "toolchain/bin" / target).chmod(0o755)
        copy(llvm / "lib/clang", stage / "toolchain/lib/clang")
        copy(ROOT / "vendor/llvm-LICENSE.txt", stage / "toolchain/LICENSE.txt")
        binaries = [stage / "build" / item for item in EXECUTABLES]
        binaries += list((stage / "toolchain/libexec").iterdir())
        libraries = {}
        system = set()
        build_environment = dict(environment, LD_LIBRARY_PATH=str(llvm / "lib"))
        # ldd lists the complete transitive closure. Only LLVM libraries are
        # bundled; glibc and distro runtime libraries remain explicit OS prerequisites.
        for binary in binaries:
            for library, location in dependencies(binary, build_environment).items():
                if re.fullmatch(r"lib(?:LLVM|clang-cpp)\.so\.[0-9.]+", library):
                    libraries[library] = location
                else:
                    if not str(location).startswith(("/lib/", "/usr/lib/")):
                        raise ValueError(f"{binary}: non-system runtime dependency: {location}")
                    system.add(library)
        for library, location in libraries.items():
            copy(location, stage / "toolchain/lib" / library)
        # Include Clang's resource objects and sanitizer shared libraries too.
        binaries = []
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                with path.open("rb") as stream:
                    if stream.read(4) == b"\x7fELF":
                        binaries.append(path)
        for binary in binaries:
            audit(binary, arch, minimum, stage)
        staged_environment = dict(environment, LD_LIBRARY_PATH=str(stage / "toolchain/lib"))
        for binary in binaries:
            for library, location in dependencies(binary, staged_environment).items():
                if library in libraries:
                    if not location.resolve().is_relative_to(stage.resolve()):
                        raise ValueError(f"{binary}: LLVM escaped the private toolchain: {location}")
                else:
                    if not str(location).startswith(("/lib/", "/usr/lib/")):
                        raise ValueError(f"{binary}: non-system runtime dependency: {location}")
                    system.add(library)
        (stage / ".minyar-distribution").write_text("1\n")
        (stage / "distribution.platform").write_text("linux\n")
        (stage / "distribution.arch").write_text(arch + "\n")
        (stage / "distribution.version").write_text(args.version + "\n")
        (stage / "distribution.libc").write_text(args.minimum_glibc + "\n")
        (stage / "minyar").chmod(0o755)
        for entry in stage.rglob("*"):
            if entry.is_symlink() and not entry.resolve().is_relative_to(stage.resolve()):
                raise ValueError(f"distribution symlink escapes its root: {entry}")
        metadata = {"version": args.version, "platform": "linux", "arch": arch, "llvm": LLVM_VERSION,
                    "minimum_glibc": args.minimum_glibc, "build_host_libc": host_libc,
                    "system_shared_libraries": sorted(system),
                    "files": {str(path.relative_to(stage)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted(stage.rglob("*")) if path.is_file()}}
        (stage / "distribution.json").write_text(json.dumps(metadata, indent=2) + "\n")
        staged_archive = Path(temporary) / archive.name
        with tarfile.open(staged_archive, "w:gz") as target:
            target.add(stage, arcname=name)
        digest = hashlib.sha256(staged_archive.read_bytes()).hexdigest()
        staged_archive.rename(archive)
        checksum.write_text(f"{digest}  {archive.name}\n")
    print(f"Packaged {archive}\nSHA-256: {digest}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"package-linux: {error}") from error
