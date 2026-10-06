#!/usr/bin/env python3
"""Invalidate native build artifacts when the compiler or build flags change.

Probe executable metadata without launching Clang on every warm build. Resolve
PATH and symlinks each time, so toolchain upgrades and switches change identity.
Atomic publication keeps concurrent readers from observing a partial stamp.
"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

FLAGS = (
    "CPPFLAGS", "CFLAGS", "LLVM_FLAGS", "LDLIBS", "SANITIZER_FLAGS", "COMPILER_RUNTIME_FLAGS",
    "COMPILER_LTO_FLAGS", "PROGRAM_RUNTIME_FLAGS", "BOUNDED_FLAGS",
)


def identity(name, default):
    command = os.environ.get(name, default)
    resolved = shutil.which(command)
    if resolved is None:
        raise ValueError(f"{name}: compiler executable not found: {command}")
    path = Path(resolved).resolve()
    stat = path.stat()
    return {
        "command": command, "path": str(path), "device": stat.st_dev,
        "inode": stat.st_ino, "size": stat.st_size,
        "modified_ns": stat.st_mtime_ns, "changed_ns": stat.st_ctime_ns,
    }


def main():
    target = Path(sys.argv[1])
    content = json.dumps({
        "cc": identity("CC", "cc"), "llvm_cc": identity("LLVM_CC", "clang"),
        "flags": {name: os.environ.get(name, "") for name in FLAGS},
    }, sort_keys=True, indent=2).encode() + b"\n"
    if target.is_file() and target.read_bytes() == content:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    # Apple's GNU Make 3.81 compares whole seconds. A changed stamp must be
    # strictly newer than artifacts built earlier in this second; otherwise a
    # quick toolchain/flag switch can silently keep an incompatible object.
    # Wait only on configuration changes, never move mtimes into the future.
    boundary = int(time.time()) + 1
    while True:
        remaining = boundary - time.time()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 1.0))
    descriptor, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"minyar: {error}", file=sys.stderr)
        sys.exit(1)
