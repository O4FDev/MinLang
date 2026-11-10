#!/usr/bin/env python3
"""Check (default) or rewrite (--write) every copy of the pinned LLVM release against its one source.

  python3 tools/llvm-pin.py            # `make check-llvm-pin`; fails on any copy that disagrees with the pin
  python3 tools/llvm-pin.py --write    # after changing the pin: rewrite every copy, then run the check again

The pin is the block of `llvm_*=` lines at the top of tools/toolchain.sh: the release version and the SHA-256 of
each archive we download. Places that cannot read it at run time (CI workflow YAML, docs, packaging notes, test
fixtures that imitate the pinned Clang) keep a literal copy, and this tool keeps those copies true:

  1. Versions. On every line that names LLVM, Clang or LLD, and on every line at all that carries a version with
     the pin's major, each `MAJOR.MINOR.PATCH` must be the pinned version. A line that deliberately names another
     version (a test that the toolchain check rejects it, another project's Clang) says so with the comment
     `llvm-pin: not the pin`: at the end of a line it covers that line; on a line of its own it covers the
     following lines up to the next blank line. Marked lines must not contain the pinned version itself.
  2. Major-version names: `clang-NN`, `llvm-NN`, `lld-NN` must use the pin's major.
  3. Digests. A 64-hex SHA-256 within a few lines of an LLVM archive name (`LLVM-V-macOS-ARM64.tar.xz`,
     `LLVM-V-Linux-X64.tar.zst`, `LLVM-V-Linux-ARM64.tar.zst`, `llvm-project-V.src.tar.xz`) must be the pinned
     digest of that archive.

Files about a different, independently pinned LLVM (FOREIGN below) and history are exempt and never rewritten.
History: records of past runs, measurement write-ups that say which LLVM produced
their numbers (docs/performance.md, docs/iteration.md, docs/research), benchmarks, experiments and the
third-party corpora in tests/data.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = "tools/toolchain.sh"
# Files whose subject is a different, independently pinned LLVM: the browser playground's YoWASP Clang
# (docs/wasm.md, playground/THIRD_PARTY.md) and the distribution Clang that builds the QNS ngtcp2 peer.
FOREIGN = ("playground/THIRD_PARTY.md", "docs/wasm.md", "tools/prepare-wasm.py", "tools/trim-wasm-resources.py",
           "tests/interop/qns/Dockerfile.ngtcp2-awslc")
HISTORY = ("docs/records/", "docs/research/", "docs/performance.md", "docs/iteration.md", "benchmarks/",
           "experiments/", "reports/", "tests/data/")
LONGEST = 4000  # longer lines are data (minified JSON), not pins
MARKER = "llvm-pin: not the pin"
ARCHIVES = {  # archive name suffix -> pin key
    "macOS-ARM64.tar.xz": "llvm_sha256_macos_arm64",
    "Linux-X64.tar.zst": "llvm_sha256_linux_x64",
    "Linux-ARM64.tar.zst": "llvm_sha256_linux_arm64",
    ".src.tar.xz": "llvm_sha256_source",
}
VERSION = re.compile(r"(?<![\w.])(\d{2})\.(\d+)\.(\d+)(?!\d|\.\d)")
LLVM_WORD = re.compile(r"llvm|clang|lld", re.I)
MAJOR_NAME = re.compile(r"(?<![\w-])((?:clang|llvm|lld)-)(\d{2})(?![\w.])", re.I)
DIGEST = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
ARCHIVE = re.compile(r"(?:LLVM-[^\s'\"/]*-(macOS-ARM64\.tar\.xz|Linux-X64\.tar\.zst|Linux-ARM64\.tar\.zst))"
                     r"|(?:llvm-project-[^\s'\"/]*(\.src\.tar\.xz))")
WINDOW = 8


def pin():
    values = dict(re.findall(r"^(llvm_[a-z0-9_]+)=(\S+)$", open(os.path.join(ROOT, SOURCE)).read(), re.M))
    missing = [key for key in ["llvm_version", *ARCHIVES.values()] if key not in values]
    if missing:
        sys.exit(f"llvm-pin: {SOURCE} lacks {', '.join(missing)}")
    return values


def files():
    listed = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], check=True, capture_output=True).stdout
    for path in listed.decode().split("\0"):
        if not path or path == SOURCE or path.startswith(HISTORY) or path in FOREIGN:
            continue
        try:
            text = open(os.path.join(ROOT, path), encoding="utf-8").read()
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue
        yield path, text


def problems(path, lines, values):
    """(line index, kind, found, expected) for every copy that disagrees with the pin."""
    version = values["llvm_version"]
    major = version.split(".")[0]
    found = []
    archives = []
    for index, line in enumerate(lines):
        for match in ARCHIVE.finditer(line):
            archives.append((index, ARCHIVES[match.group(1) or match.group(2)]))
    block = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            block = False
        if MARKER in line and stripped.startswith(("#", "//", "<!--")):
            block = True
        marked = block or MARKER in line
        if len(line) > LONGEST:
            continue
        named = LLVM_WORD.search(line)
        for match in VERSION.finditer(line):
            token = match.group(0)
            relevant = match.group(1) == major or named
            if marked and token == version:
                found.append((index, "a line marked as naming another version names the pin", token, None))
            elif relevant and not marked and token != version:
                found.append((index, "version", token, version))
        for match in MAJOR_NAME.finditer(line):
            if match.group(2) != major and not marked:
                found.append((index, "major", match.group(0), match.group(1) + major))
        for match in DIGEST.finditer(line):
            near = [(abs(other - index), key) for other, key in archives if abs(other - index) <= WINDOW]
            if near:
                key = min(near)[1]
                if match.group(0) != values[key]:
                    found.append((index, "digest of " + key[len("llvm_sha256_"):], match.group(0), values[key]))
    return found


def main():
    write = sys.argv[1:] == ["--write"]
    if sys.argv[1:] not in ([], ["--write"]):
        sys.exit("usage: tools/llvm-pin.py [--write]")
    values = pin()
    failures = 0
    changed = []
    for path, text in files():
        lines = text.split("\n")
        found = problems(path, lines, values)
        if not found:
            continue
        if write:
            for index, kind, old, new in found:
                if new is not None:
                    lines[index] = re.sub(r"(?<![\w.])" + re.escape(old) + r"(?!\d|\.\d)", new, lines[index])
            open(os.path.join(ROOT, path), "w", encoding="utf-8").write("\n".join(lines))
            changed.append(path)
            found = problems(path, lines, values)
        for index, kind, old, new in found:
            failures += 1
            expected = f" (pin: {new})" if new else ""
            print(f"{path}:{index + 1}: {kind} {old}{expected}")
    for path in changed:
        print(f"rewrote {path}")
    if failures:
        print(f"llvm-pin: {failures} copies disagree with the pin in {SOURCE} (LLVM {values['llvm_version']}); "
              "run `python3 tools/llvm-pin.py --write`, or mark a deliberate other version with "
              f"`{MARKER}`")
        return 1
    print(f"llvm-pin: every copy matches LLVM {values['llvm_version']} in {SOURCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
