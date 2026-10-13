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
import shlex
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from host_paths import host_path, pinned_llvm, pinned_lld, LLVM_VERSION

FLAGS = (
    "CPPFLAGS", "CFLAGS", "LLVM_FLAGS", "LDLIBS", "SANITIZER_FLAGS", "COMPILER_RUNTIME_FLAGS",
    "COMPILER_LTO_FLAGS", "PROGRAM_RUNTIME_FLAGS", "BOUNDED_FLAGS",
)


def identity(name, default, command=None):
    command = command if command is not None else os.environ.get(name, default)
    resolved = shutil.which(command)
    if resolved is None:
        raise ValueError(f"{name}: compiler executable not found: {command}")
    path = host_path(resolved).resolve()
    stat = path.stat()
    return {
        "command": command, "path": str(path), "device": stat.st_dev,
        "inode": stat.st_ino, "size": stat.st_size,
        "modified_ns": stat.st_mtime_ns, "changed_ns": stat.st_ctime_ns,
    }


def publish_stamp(target, content, max_wait=3.0):
    target.parent.mkdir(parents=True, exist_ok=True)
    # Apple's GNU Make 3.81 compares whole seconds. A changed stamp must be
    # strictly newer than artifacts built earlier in this second; otherwise a
    # quick toolchain/flag switch can silently keep an incompatible object.
    # Userspace CLOCK_REALTIME crossing a boundary does not certify the
    # filesystem clock. Touch with UTIME_NOW and verify the inode itself.
    # Never assign a future mtime; never replace a stamp on a stalled clock.
    previous = target.stat().st_mtime_ns // 1_000_000_000 if target.exists() else 0
    boundary = max(int(time.time()), previous) + 1
    deadline = time.monotonic() + max_wait
    descriptor, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        while True:
            os.utime(temporary, None)
            if Path(temporary).stat().st_mtime_ns // 1_000_000_000 >= boundary:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('filesystem timestamp did not cross the required whole-second boundary')
            time.sleep(min(remaining, 0.05))
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    target = Path(sys.argv[1])
    llvm = identity("LLVM_CC", "clang" if sys.platform == "darwin" else "clang-23")
    try:
        previous = json.loads(target.read_text()) if target.is_file() else {}
    except ValueError:
        previous = {}
    if previous.get("llvm_cc") != llvm or previous.get("llvm_version") != LLVM_VERSION:
        pinned_llvm(llvm["command"])
    linker = None
    options = shlex.split(os.environ.get("LLVM_FLAGS", "")) + shlex.split(os.environ.get("COMPILER_LTO_FLAGS", ""))
    if sys.platform.startswith("linux") and any(option.startswith("-flto") for option in options):
        selected = next((option.split("=", 1)[1] for option in reversed(options) if option.startswith("--ld-path=")), None)
        if selected is None:
            selected = next((option.split("=", 1)[1] for option in reversed(options) if option.startswith("-fuse-ld=")), "lld")
        if selected == "lld":
            selected = subprocess.check_output([llvm["command"], "-print-prog-name=ld.lld"], text=True, timeout=10).strip()
        elif not Path(selected).is_absolute():
            selected = shutil.which(selected) or shutil.which("ld." + selected) or selected
        linker = identity("LLD", selected, command=selected)
        if previous.get("linker") != linker or previous.get("llvm_version") != LLVM_VERSION:
            pinned_lld(selected)
    content = json.dumps({
        "cc": identity("CC", "cc"), "llvm_cc": llvm, "llvm_version": LLVM_VERSION,
        "linker": linker,
        "flags": {name: os.environ.get(name, "") for name in FLAGS},
    }, sort_keys=True, indent=2).encode() + b"\n"
    if target.is_file() and target.read_bytes() == content:
        return
    publish_stamp(target, content)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"minyar: {error}", file=sys.stderr)
        sys.exit(1)
