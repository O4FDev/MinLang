#!/usr/bin/env python3
"""Build, run, test and debug Minyar OS using the existing os/Makefile."""

import argparse
from datetime import datetime
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


def rtc_datetime(value):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", value):
        raise argparse.ArgumentTypeError("RTC base must use YYYY-MM-DDTHH:MM:SS")
    try:
        datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("RTC base must be a valid calendar date and time") from error
    return value


def tool(name):
    found = shutil.which(str(name))
    if not found:
        raise WorkflowError(f"missing executable {name!s}; install it or select its path explicitly")
    return found


def announce(command, overrides=None):
    prefix = ["env"] + [f"{name}={value}" for name, value in overrides.items()] if overrides else []
    print("+ " + shlex.join(prefix + [str(item) for item in command]), file=sys.stderr, flush=True)


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


def build(command, timeout, environment=None):
    process = subprocess.Popen(command, env=environment, start_new_session=True)
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
    replay = getattr(args, "record", None) or getattr(args, "replay", None)
    # Record/replay needs one deterministic instruction counter: one CPU,
    # single-threaded TCG, a virtual clock, and every input passing through QEMU's
    # replay log (disk via blkreplay, network via filter-replay, seeded entropy).
    command = [executable, "-m", "1G", "-smp", "1" if replay else "4",
               "-accel", "tcg,thread=single" if replay else "tcg", "-cpu", "max",
               "-display", args.display, "-serial", "stdio", "-monitor", "none",
               "-no-reboot", "-netdev", "user,id=net0", "-device", "e1000,netdev=net0"]
    if replay:
        mode = "record" if getattr(args, "record", None) else "replay"
        log = str(Path(replay).resolve()).replace(",", ",,")
        command += ["-icount", f"shift=auto,rr={mode},rrfile={log}", "-object", "filter-replay,id=replay,netdev=net0",
                    "-seed", "1"]
    if args.rtc_base:
        command += ["-rtc", f"base={args.rtc_base},clock=vm"]
    elif replay:
        command += ["-rtc", "clock=vm"]
    # QEMU key/value options use doubled commas for literal path commas.
    image = str(output / "minyar-os.img").replace(",", ",,")
    if args.arch == "x86_64":
        command += ["-vga", "std", "-drive", f"file={image},format=raw,if=ide,snapshot=on"]
        command += ["-device", "isa-debug-exit,iobase=0xf4,iosize=0x04"]
    else:
        command += ["-M", "virt,gic-version=3", "-kernel", str(output / "kernel.elf"), "-device", "bochs-display"]
        if replay:
            command += ["-drive", f"if=none,id=disk-direct,file={image},format=raw,snapshot=on",
                        "-drive", "driver=blkreplay,if=none,image=disk-direct,id=disk"]
        else:
            command += ["-drive", f"if=none,id=disk,file={image},format=raw,snapshot=on"]
        command += ["-device", "virtio-blk-pci,drive=disk,disable-legacy=on",
                    "-device", "virtio-keyboard-pci,disable-legacy=on",
                    "-device", "virtio-tablet-pci,disable-legacy=on"]
        if replay:
            command += ["-object", "rng-builtin,id=entropy", "-device", "virtio-rng-pci,rng=entropy,disable-legacy=on"]
        else:
            command += ["-device", "virtio-rng-pci,disable-legacy=on"]
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
    if (getattr(args, "record", None) or getattr(args, "replay", None)) and args.arch != "arm64":
        # x86 boots through a polled ATA loader; under QEMU's blkreplay its reads
        # time out, and without blkreplay a replay diverges.
        raise WorkflowError("record/replay currently supports --arch arm64 only")
    if args.no_build and args.kernel_source:
        raise WorkflowError("--kernel-source requires a build; remove --no-build")
    if not (args.root / "os/Makefile").is_file():
        raise WorkflowError(f"missing {args.root / 'os/Makefile'}; select a Minyar checkout with --root")
    llvm = llvm_directory(args)
    make = make_command(args, llvm)
    bootstrap = args.root / "tools/toolchain.sh"
    compiler = ["sh", str(bootstrap), "bootstrap", str(args.root), "build/minyarc"]
    overrides = {"MINYAR_CLANG": str(llvm / "clang"), "LLVM_CC": str(llvm / "clang"),
                 "MINYAR_INTERACTIVE_BOOTSTRAP": "1"}
    qemu = qemu_command(args)
    if args.action == "debug":
        elf = args.root / "build/os" / args.arch / "kernel.elf"
        print("osdev: connect with " + shlex.join(["gdb", str(elf), "-ex", f"target remote 127.0.0.1:{args.gdb_port}"]),
              file=sys.stderr)
    if not args.no_build:
        print(f"osdev: bootstrap PATH make uses {args.make!r} through a temporary symlink", file=sys.stderr)
        announce(compiler, overrides)
        announce(make, overrides)
    announce(qemu)
    log = Path(args.log).resolve() if args.log else args.root / "build/os" / args.arch / "osdev-serial.log"
    print(f"osdev: serial log: {log}", file=sys.stderr)
    if args.dry_run:
        return 0
    qemu[0] = tool(qemu[0])
    if not args.no_build:
        make[0] = str(Path(tool(make[0])).resolve())
        compiler[0] = tool(compiler[0])
        if not bootstrap.is_file():
            raise WorkflowError(f"missing bootstrap helper {bootstrap}")
        for executable in (llvm / "clang", llvm / "llvm-objcopy"):
            tool(executable)
        # os/Makefile searches LLVM_BIN first, then PATH for the ELF linker.
        tool(llvm / "ld.lld" if (llvm / "ld.lld").is_file() else "ld.lld")
        if args.kernel_source and not Path(args.kernel_source).is_file():
            raise WorkflowError(f"missing kernel source {args.kernel_source}")
        environment = dict(os.environ, **overrides)
        # Public bootstrap and nested launchers invoke PATH's `make`. Preserve
        # --make without changing shared scripts or normalizing their flags.
        # Inherited explicit COMPILER_LTO_FLAGS stays byte-for-byte unchanged.
        with tempfile.TemporaryDirectory(prefix="minyar-osdev-make-") as shim:
            (Path(shim) / "make").symlink_to(make[0])
            environment["PATH"] = shim + os.pathsep + environment.get("PATH", os.defpath)
            deadline = time.monotonic() + args.build_timeout
            for command in (compiler, make):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    print(f"osdev: build timed out after {args.build_timeout:g}s", file=sys.stderr)
                    return 124
                status = build(command, remaining, environment)
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
    status = boot(args, qemu, log)
    elf = args.root / "build/os" / args.arch / "kernel.elf"
    if log.is_file() and elf.is_file():
        report_minyar_trace(log.read_text(errors="replace"), elf)
    return status


def trace_return_addresses(text):
    """Return addresses a freestanding kernel printed under "Minyar stack trace:"."""
    traces, current = [], None
    for line in text.splitlines():
        if line.strip() == "Minyar stack trace:":
            current = []
            traces.append(current)
        elif current is not None:
            match = re.fullmatch(r"\s+at (0x[0-9a-fA-F]+)\s*", line)
            if match:
                current.append(int(match.group(1), 16))
            elif not line.startswith("  at "):
                current = None
    return traces


# runtime/minyar_traces.h MinyarTraceRow: five i32 offsets/flags, padding,
# then i64 line and column.
TRACE_ROW_BYTES = 40


def elf_trace_functions(elf):
    """Map kernel function addresses to Minyar names through the ELF symbol
    table and the compiler's runtime trace rows; no DWARF or runtime cost."""
    data = Path(elf).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise WorkflowError(f"{elf} is not a little-endian ELF64 kernel")
    number = lambda offset, size: int.from_bytes(data[offset:offset + size], "little")
    signed = lambda offset, size: int.from_bytes(data[offset:offset + size], "little", signed=True)
    sections = []
    table, entry_size, count = number(0x28, 8), number(0x3A, 2), number(0x3C, 2)
    for index in range(count):
        base = table + index * entry_size
        sections.append(dict(type=number(base + 4, 4), address=number(base + 16, 8), offset=number(base + 24, 8),
                             size=number(base + 32, 8), link=number(base + 40, 4)))

    def at(address, size):
        for section in sections:
            if section["type"] != 8 and section["address"] <= address and address + size <= section["address"] + section["size"]:
                start = section["offset"] + address - section["address"]
                return data[start:start + size]
        return None

    def text(address):
        for section in sections:
            if section["type"] != 8 and section["address"] <= address < section["address"] + section["size"]:
                start = section["offset"] + address - section["address"]
                return data[start:data.index(b"\0", start)].decode(errors="replace")
        return None

    functions, objects = [], {}
    for section in (item for item in sections if item["type"] == 2):
        strings = sections[section["link"]]
        for base in range(section["offset"], section["offset"] + section["size"], 24):
            start = strings["offset"] + number(base, 4)
            name = data[start:data.index(b"\0", start)].decode(errors="replace")
            kind, value, size = number(base + 4, 1) & 15, number(base + 8, 8), number(base + 16, 8)
            if kind == 2 and size:
                functions.append((value, size, name))
            elif name.startswith("minyar.trace|"):
                objects[name] = value
    rows = {}
    for name, address in objects.items():
        if not name.endswith("|rows") or name[:-5] + "|count" not in objects:
            continue
        total = at(objects[name[:-5] + "|count"], 8)
        for index in range(int.from_bytes(total or b"", "little")):
            row = at(address + index * TRACE_ROW_BYTES, TRACE_ROW_BYTES)
            if row is None:
                break
            relative = lambda field: address + int.from_bytes(row[field:field + 4], "little", signed=True)
            symbol, readable, path = text(relative(0)), text(relative(4)), text(relative(8))
            if symbol:
                rows[symbol] = (readable, path, int.from_bytes(row[24:32], "little", signed=True),
                                int.from_bytes(row[32:40], "little", signed=True))
    return sorted(functions), rows


def symbolize_minyar_trace(addresses, functions, rows):
    frames = []
    for address in addresses:
        # A return address follows its call; look up the call instruction.
        target = address - 1
        for start, size, name in functions:
            if start <= target < start + size:
                row = rows.get(name) or rows.get(name.split(".llvm.")[0])
                if row:
                    frames.append("  at %s (%s:%d:%d)" % row)
                break
    return frames


def report_minyar_trace(text, elf):
    traces = [trace for trace in trace_return_addresses(text) if trace]
    if not traces:
        return
    try:
        functions, rows = elf_trace_functions(elf)
    except (OSError, ValueError, WorkflowError) as error:
        print(f"osdev: cannot symbolize the Minyar stack trace: {error}", file=sys.stderr)
        return
    for trace in traces:
        frames = symbolize_minyar_trace(trace, functions, rows)
        print(f"osdev: Minyar stack trace, symbolized with {elf}:", file=sys.stderr)
        for frame in frames or ["  (no Minyar function owns these return addresses)"]:
            print(frame, file=sys.stderr)


def instruction_addresses(text):
    addresses = re.findall(r"\b(?:rip|elr|pc)\s*[:=]?\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]{8,16})\b", text, re.I)
    addresses += re.findall(r"Minyar stopped:[^\n]*?\bat (0x[0-9a-fA-F]+)\b", text)
    return addresses


def symbolize(args):
    addresses = args.addresses[:]
    traced = False
    if args.log:
        text = Path(args.log).read_text(errors="replace")
        addresses += instruction_addresses(text)
        traced = any(trace_return_addresses(text))
        elf = Path(args.elf).resolve() if args.elf else args.root / "build/os" / args.arch / "kernel.elf"
        if traced and not args.dry_run:
            if not elf.is_file():
                raise WorkflowError(f"missing ELF {elf}; preserve the exact kernel from the failing run")
            report_minyar_trace(text, elf)
        if traced and not addresses:
            return 0
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
            part.add_argument("--rtc-base", type=rtc_datetime, help="initial QEMU calendar YYYY-MM-DDTHH:MM:SS, advancing on virtual time")
            journal = part.add_mutually_exclusive_group()
            journal.add_argument("--record", type=Path, help="record a deterministic replay log of this run (arm64, one CPU)")
            journal.add_argument("--replay", type=Path, help="replay a recorded run exactly; with debug, GDB can step backwards")
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
