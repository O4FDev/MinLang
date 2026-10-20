#!/usr/bin/env python3
"""Build, run, test and debug Minyar OS using the existing os/Makefile."""

import argparse
import math
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
FAILURE = re.compile(
    rb"(?im)\bpanic\b|processor exception|Minyar stopped:|runtime error:|"
    rb"\[minyar exited with status (?!0\])[^\]]+\]"
)


class WorkflowError(Exception):
    pass


def positive_seconds(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return result


def tool(name):
    found = shutil.which(str(name))
    if not found:
        raise WorkflowError(f"missing executable {name!s}; install it or select its path explicitly")
    return found


def announce(command):
    print("+ " + shlex.join([str(item) for item in command]), file=sys.stderr, flush=True)


def stop(process):
    """Reap the child and terminate its process group, including build children."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


def build(command, timeout):
    process = subprocess.Popen(command, start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"osdev: build timed out after {timeout:g}s", file=sys.stderr)
        return 124
    finally:
        stop(process)


def llvm_directory(args):
    if args.llvm_bin:
        return Path(args.llvm_bin).expanduser().resolve()
    clang = shutil.which("clang")
    return Path(clang).parent if clang else Path("/missing-llvm/bin")


def make_command(args, llvm):
    command = [args.make, "-C", str(args.root / "os"), f"ARCH={args.arch}",
               f"LLVM_BIN={llvm}"]
    source = Path(args.kernel_source).resolve() if args.kernel_source else args.root / "os/kernel/main.min"
    # The Makefile does not record KERNEL_SOURCE changes. Force the selected
    # kernel each time, including a return from a test to the default desktop.
    # Runtime, compiler and other prerequisites retain their incremental builds.
    command += ["-W", str(source), f"KERNEL_SOURCE={source}"]
    return command + ["all"]


def qemu_command(args):
    output = args.root / "build" / "os" / args.arch
    name = "qemu-system-aarch64" if args.arch == "arm64" else "qemu-system-x86_64"
    local = args.root / "build/qemu/bin" / name
    executable = args.qemu or (str(local) if local.is_file() else name)
    command = [executable, "-m", "1G", "-smp", "4", "-accel", "tcg", "-cpu", "max",
               "-display", args.display, "-serial", "stdio", "-monitor", "none",
               "-no-reboot", "-netdev", "user,id=net0", "-device", "e1000,netdev=net0"]
    # QEMU key/value options use doubled commas for literal path commas.
    image = str(output / "minyar-os.img").replace(",", ",,")
    if args.arch == "x86_64":
        command += ["-vga", "std", "-drive", f"file={image},format=raw,if=ide,snapshot=on",
                    "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04"]
    else:
        command += ["-M", "virt,gic-version=3", "-kernel", str(output / "kernel.elf"),
                    "-device", "bochs-display", "-drive", f"if=none,id=disk,file={image},format=raw,snapshot=on",
                    "-device", "virtio-blk-pci,drive=disk,disable-legacy=on",
                    "-device", "virtio-keyboard-pci,disable-legacy=on",
                    "-device", "virtio-tablet-pci,disable-legacy=on",
                    "-device", "virtio-rng-pci,disable-legacy=on"]
    if args.action == "debug":
        command += ["-S", "-gdb", f"tcp:127.0.0.1:{args.gdb_port}"]
    return command


def boot(args, command, log):
    timeout = args.timeout if args.timeout is not None else (30 if args.action == "test" else None)
    deadline = time.monotonic() + timeout if timeout else None
    # QEMU stderr stays separate: host diagnostics cannot supply guest evidence.
    with tempfile.TemporaryFile() as errors, log.open("wb") as serial:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL if args.action == "test" else None,
                                   stdout=subprocess.PIPE, stderr=errors, start_new_session=True)
        timed_out = False
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = None if deadline is None else max(0, deadline - time.monotonic())
                    if remaining is not None and remaining <= 0:
                        timed_out = True
                        break
                    ready = selector.select(remaining)
                    if not ready:
                        timed_out = True
                        break
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        selector.unregister(process.stdout)
                        break
                    serial.write(chunk)
                    serial.flush()
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                if not timed_out:
                    try:
                        process.wait(timeout=None if deadline is None else max(0, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        timed_out = True
        finally:
            stop(process)
            process.stdout.close()
            errors.seek(0)
            shutil.copyfileobj(errors, sys.stderr.buffer)
    if timed_out:
        print(f"osdev: QEMU timed out after {timeout:g}s; serial log: {log}", file=sys.stderr)
        return 124
    expected_status = 1 if args.arch == "x86_64" else 0
    evidence = log.read_bytes()
    if FAILURE.search(evidence):
        print(f"osdev: guest reported a failure; serial log: {log}", file=sys.stderr)
        return 1
    if args.action != "test":
        # QEMU also uses host status 1 for initialization failures. Translate
        # x86 debug-exit only with the runtime's successful serial exit report.
        if args.arch == "x86_64" and process.returncode == 1 and b"[minyar exited with status 0]" in evidence:
            return 0
        return 128 - process.returncode if process.returncode < 0 else process.returncode
    if process.returncode != expected_status:
        print(f"osdev: QEMU exited {process.returncode}, expected {expected_status}; serial log: {log}", file=sys.stderr)
        return 1
    if args.expect.encode("utf-8") not in evidence.replace(b"\r\n", b"\n").split(b"\n"):
        print(f"osdev: missing exact serial line {args.expect!r}; serial log: {log}", file=sys.stderr)
        return 1
    print(f"osdev: test passed; serial log: {log}", file=sys.stderr)
    return 0


def run(args):
    if args.action == "test" and (not args.expect or "\n" in args.expect or "\r" in args.expect):
        raise WorkflowError("test requires --expect with one nonempty exact serial line")
    if args.no_build and args.kernel_source:
        raise WorkflowError("--kernel-source requires a build; remove --no-build")
    if not (args.root / "os/Makefile").is_file():
        raise WorkflowError(f"missing {args.root / 'os/Makefile'}; select a Minyar checkout with --root")
    llvm = llvm_directory(args)
    make = make_command(args, llvm)
    qemu = qemu_command(args)
    if args.action == "debug":
        elf = args.root / "build/os" / args.arch / "kernel.elf"
        print("osdev: connect with " + shlex.join(["gdb", str(elf), "-ex", f"target remote 127.0.0.1:{args.gdb_port}"]),
              file=sys.stderr)
    if not args.no_build:
        announce(make)
    announce(qemu)
    log = Path(args.log).resolve() if args.log else args.root / "build/os" / args.arch / "osdev-serial.log"
    print(f"osdev: serial log: {log}", file=sys.stderr)
    if args.dry_run:
        return 0
    qemu[0] = tool(qemu[0])
    if not args.no_build:
        make[0] = tool(make[0])
        for executable in (llvm / "clang", llvm / "llvm-objcopy"):
            tool(executable)
        # os/Makefile searches LLVM_BIN first, then PATH for the ELF linker.
        tool(llvm / "ld.lld" if (llvm / "ld.lld").is_file() else "ld.lld")
        if args.kernel_source and not Path(args.kernel_source).is_file():
            raise WorkflowError(f"missing kernel source {args.kernel_source}")
        status = build(make, args.build_timeout)
        if status:
            return status if status > 0 else 1
    for artifact in ("minyar-os.img", "kernel.elf"):
        path = args.root / "build/os" / args.arch / artifact
        if not path.is_file():
            raise WorkflowError(f"missing {path}; build the selected architecture first")
    for name in ("minyar-os.img", "kernel.elf"):
        artifact = args.root / "build/os" / args.arch / name
        if log == artifact.resolve() or (log.exists() and log.samefile(artifact)):
            raise WorkflowError("serial log must not overwrite the kernel or disk image")
    log.parent.mkdir(parents=True, exist_ok=True)
    return boot(args, qemu, log)


def instruction_addresses(text):
    addresses = re.findall(r"\b(?:rip|elr|pc)\s*[:=]?\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]{8,16})\b", text, re.I)
    addresses += re.findall(r"Minyar stopped:[^\n]*?\bat (0x[0-9a-fA-F]+)\b", text)
    return addresses


def symbolize(args):
    addresses = args.addresses[:]
    if args.log:
        addresses += instruction_addresses(Path(args.log).read_text(errors="replace"))
    normalized = []
    for address in addresses:
        if not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{1,16}", address):
            raise WorkflowError(f"invalid hexadecimal instruction address {address!r}")
        value = "0x" + address.removeprefix("0x").lower()
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise WorkflowError("no instruction addresses; pass hex addresses or --log with a RIP/ELR/PC fault")
    elf = Path(args.elf).resolve() if args.elf else args.root / "build/os" / args.arch / "kernel.elf"
    executable = args.symbolizer or shutil.which("llvm-symbolizer") or shutil.which("addr2line") or "llvm-symbolizer"
    if "addr2line" in Path(executable).name:
        command = [executable, "-a", "-f", "-C", "-i", "-e", str(elf)] + normalized
    else:
        command = [executable, "--print-address", "--functions=linkage", "--inlines", "--demangle", f"--obj={elf}"] + normalized
    announce(command)
    if args.dry_run:
        return 0
    if not elf.is_file():
        raise WorkflowError(f"missing ELF {elf}; preserve the exact kernel from the failing run")
    command[0] = tool(executable)
    return build(command, args.timeout or 15)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for action in ("run", "test", "debug", "symbolize"):
        part = actions.add_parser(action)
        part.add_argument("--root", type=Path, default=ROOT, help="Minyar checkout (also supports Minyar-OS)")
        part.add_argument("--arch", choices=("x86_64", "arm64"), default="x86_64")
        part.add_argument("--dry-run", action="store_true", help="print commands without running tools or creating logs")
        part.add_argument("--log", help="serial output, or serial input for symbolize")
        part.add_argument("--timeout", type=positive_seconds, help="QEMU deadline; test defaults to 30 seconds")
        if action == "symbolize":
            part.add_argument("addresses", nargs="*", help="hex instruction addresses")
            part.add_argument("--elf", help="exact linked ELF from the failing run")
            part.add_argument("--symbolizer", help="llvm-symbolizer or addr2line executable")
        else:
            part.add_argument("--no-build", action="store_true", help="use existing image and kernel")
            part.add_argument("--make", default="make", help="make executable")
            part.add_argument("--llvm-bin", default=os.environ.get("LLVM_BIN"), help="directory containing clang and llvm-objcopy")
            part.add_argument("--build-timeout", type=positive_seconds, default=600)
            part.add_argument("--kernel-source", help="finite test kernel, passed to os/Makefile with forced rebuild")
            part.add_argument("--qemu", help="QEMU executable (one path, not shell syntax)")
            part.add_argument("--display", default="none", help="QEMU display backend, e.g. cocoa or gtk; default none")
            if action == "test":
                part.add_argument("--expect", required=True, help="nonempty exact guest serial line required for success")
            if action == "debug":
                part.add_argument("--gdb-port", type=int, choices=range(1, 65536), default=1234, metavar="PORT")
    args = parser.parse_args(argv)
    args.root = args.root.expanduser().resolve()
    try:
        return symbolize(args) if args.action == "symbolize" else run(args)
    except (WorkflowError, OSError, subprocess.SubprocessError) as error:
        print(f"osdev: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
