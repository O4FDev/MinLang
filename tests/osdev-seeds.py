#!/usr/bin/env python3
"""Seeded-mistake study: the same driver mistakes applied to Minyar and C.

Each seed is one realistic driver mistake from the osdev bug survey (wrong
field width or offset, a write to the wrong register, a missing DMA fence, the
CPU touching a device-owned buffer, allocation in an IRQ handler, a physical/
virtual mix-up, ...). It is applied as one exact source edit to the Minyar
driver and to a conventional C driver doing the same job, and each mutant goes
through the same ladder, stopping at the first stage that notices:

  compile   the compiler rejects it (C: clang -Wall -Wextra errors; warnings
            are recorded separately because they need -Werror to stop a build)
  host      the hosted tests fail (the RTC calendar/transaction oracle, the
            DMA device model; C also runs under ASan+UBSan)
  qemu      the real x86 guest fails under QEMU (RTC drivers only)
  undetected  every available stage still passes

A seed that cannot be written in one language says so instead of being forced.
The unmodified drivers must pass every stage first, or the study is invalid.
Use the approved build host with build/minyarc, build/minyar-runtime.o and
Clang. The full QEMU study requires Linux; --no-qemu uses hosted checks.
"""

import argparse
from dataclasses import dataclass, field
import importlib.util
import json
import os
import re
import signal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
SEEDS_DIR = ROOT / "tests/osdev-seeds"
RTC_BASE = "2026-10-20T12:34:56"
TREE = ("os", "library", "runtime", "vendor", "tools", "scripts", "tests/osdev-rtc.py",
        "tests/memory-contracts-runtime.c", "tests/osdev-seeds")
STAGES = ("compile", "host", "qemu")


@dataclass(frozen=True)
class Edit:
    path: str          # relative to the seed tree
    old: str
    new: str


@dataclass(frozen=True)
class Seed:
    name: str
    driver: str        # rtc, irq or dma
    mistake: str
    source: str        # where this bug class comes from
    minyar: Edit | None
    c: Edit | None
    minyar_note: str = ""
    c_note: str = ""


M_RTC = "os/shared/rtc.min"
M_PORT = "os/arch/x86_64/rtc.min"
M_IRQ = "tests/osdev-seeds/minyar/rtc-irq.min"
M_DMA = "tests/osdev-seeds/minyar/entropy.min"
C_RTC = "tests/osdev-seeds/c/rtc.c"
C_IRQ = "tests/osdev-seeds/c/rtc_irq.c"
C_DMA = "tests/osdev-seeds/c/virtio_entropy.c"
SURVEY = "reports/osdev-research.md layout/bounds class"


def irq(code):
    return Edit(M_IRQ, "    // SEED\n", code)


def c_irq(marker, code):
    return Edit(C_IRQ, f"    /* SEED:{marker} */\n", code)


SEEDS = (
    # --- Register layout and port mistakes in the read-only RTC driver ---
    Seed("field-offset", "rtc", "binary-mode flag read from bit 3 instead of bit 2", SURVEY,
         Edit(M_RTC, "binary: Integer at(2, 1)", "binary: Integer at(3, 1)"),
         Edit(C_RTC, "bool binary = (status_b & 4) != 0;", "bool binary = (status_b & 8) != 0;")),
    Seed("field-width", "rtc", "hour field one bit too wide, swallowing the PM flag", SURVEY,
         Edit(M_RTC, "value: Integer at(0, 7)", "value: Integer at(0, 8)"),
         Edit(C_RTC, "raw_hour &= 127;", "raw_hour &= 255;")),
    Seed("field-past-register", "rtc", "PM flag placed at bit 8 of an 8-bit register", SURVEY,
         Edit(M_RTC, "afternoon: Integer at(7, 1)", "afternoon: Integer at(8, 1)"),
         Edit(C_RTC, "bool pm = (raw_hour & 128) != 0;", "bool pm = (raw_hour & 256) != 0;")),
    Seed("overlapping-fields", "rtc", "24-hour flag given the binary flag's bit", SURVEY,
         Edit(M_RTC, "fullDay: Integer at(1, 1)", "fullDay: Integer at(2, 1)"),
         Edit(C_RTC, "bool hour24 = (status_b & 2) != 0;", "bool hour24 = (status_b & 4) != 0;")),
    Seed("inverted-mode", "rtc", "BCD and binary modes swapped", SURVEY,
         Edit(M_RTC, 'let binary = extractField(StatusB, "binary", statusB) != 0',
              'let binary = extractField(StatusB, "binary", statusB) == 0'),
         Edit(C_RTC, "bool binary = (status_b & 4) != 0;", "bool binary = (status_b & 4) == 0;")),
    Seed("wrong-port-width", "rtc", "32-bit read from the 8-bit CMOS data port", "Linux/Serenity port-width fixes",
         Edit(M_PORT, "return device.in8(data)", "return device.in32(data)"),
         Edit(C_RTC, '__asm__ volatile ("inb %1, %0"', '__asm__ volatile ("inl %1, %0"')),
    Seed("register-as-port", "rtc", "CMOS index written as memory instead of an I/O port", "address-space mix-ups",
         Edit(M_PORT, "let selector = device.port8(0x70)",
              "let selector = device.register8(device.registers(0x70, 1), 0)"),
         Edit(C_RTC, '__asm__ volatile ("outb %0, %1" : : "a"(register_index), "Nd"((uint16_t)0x70) : "memory");',
              "*(volatile uint8_t *)(uintptr_t)0x70 = register_index;")),
    Seed("write-wrong-register", "rtc", "register index written to the data port, overwriting CMOS", "write to the wrong/read-only register",
         Edit(M_PORT, "device.out8(selector, index)", "device.out8(data, index)"),
         Edit(C_RTC, '"Nd"((uint16_t)0x70)', '"Nd"((uint16_t)0x71)')),
    Seed("read-only-register-write", "rtc", "writes zero to read-only CMOS Register D", "MC146818 Register D access permissions",
         Edit(M_PORT, "device.out8(selector, index)",
              "device.out8(selector, 13)\n        device.out8(data, 0)\n        device.out8(selector, index)"),
         Edit(C_RTC, '__asm__ volatile ("outb %0, %1" : : "a"(register_index), "Nd"((uint16_t)0x70) : "memory");',
              '__asm__ volatile ("outb %0, %1" : : "a"((uint8_t)13), "Nd"((uint16_t)0x70) : "memory");\n'
              '    __asm__ volatile ("outb %0, %1" : : "a"((uint8_t)0), "Nd"((uint16_t)0x71) : "memory");\n'
              '    __asm__ volatile ("outb %0, %1" : : "a"(register_index), "Nd"((uint16_t)0x70) : "memory");'),
         minyar_note="no read-only permission type; hardware silently ignores the write",
         c_note="hardware silently ignores the write"),
    Seed("index-out-of-range", "rtc", "selector value computed outside a byte", "integer truncation at device boundaries",
         Edit(M_PORT, "device.out8(selector, index)", "device.out8(selector, index + 256)"),
         Edit(C_RTC, '"a"(register_index), "Nd"((uint16_t)0x70)', '"a"((uint8_t)(register_index + 256)), "Nd"((uint16_t)0x70)')),
    Seed("nmi-disabled", "rtc", "selector sets bit 7, silently disabling NMI", "Linux CMOS_READ NMI handling",
         Edit(M_PORT, "device.out8(selector, index)", "device.out8(selector, index | 0x80)"),
         Edit(C_RTC, '"a"(register_index), "Nd"((uint16_t)0x70)', '"a"((uint8_t)(register_index | 0x80)), "Nd"((uint16_t)0x70)')),
    Seed("read-to-clear", "rtc", "polls read-to-clear Register C instead of Register A", "protocol error class",
         Edit(M_RTC, "let before = try readByte(readRegister, 10)", "let before = try readByte(readRegister, 12)"),
         Edit(C_RTC, "!rtc_read_byte(read, context, 10, &status_a)) return rtc_error(RTC_INVALID_BYTE);\n        if ((status_a & 128) != 0) continue;\n        if (!rtc_read_byte(read, context, 0, &checked))",
              "!rtc_read_byte(read, context, 12, &status_a)) return rtc_error(RTC_INVALID_BYTE);\n        if ((status_a & 128) != 0) continue;\n        if (!rtc_read_byte(read, context, 0, &checked))")),
    Seed("missing-update-check", "rtc", "update-in-progress check dropped before the capture", "Linux mc146818_avoid_UIP history",
         Edit(M_RTC, '        if extractField(StatusA, "updating", before) != 0 { continue }\n', ""),
         Edit(C_RTC, "        if ((status_a & 128) != 0) continue;\n        if (!rtc_read_byte(read, context, 0, &checked))",
              "        if (!rtc_read_byte(read, context, 0, &checked))")),
    # --- Interrupt handler mistakes ---
    Seed("irq-allocation", "irq", "allocates a message in the interrupt handler", "Linux sleeping-allocation-in-atomic class",
         irq("    let note = Text(vector)\n"),
         c_irq("alloc", "    void *note = kmalloc(16);\n    (void)note;\n")),
    Seed("irq-lock", "irq", "takes a spinlock word the interrupted code may hold", "SerenityOS PR27039 class",
         irq("    let ticket = machine.atomicAdd(0x9000, 1)\n"),
         c_irq("lock", "    spin_lock(&rtc_lock);\n    spin_unlock(&rtc_lock);\n"),
         minyar_note="lock word built on machine.atomicAdd; Minyar OS has no lock API"),
    Seed("irq-print", "irq", "prints from the interrupt handler", "blocking console I/O in IRQ context",
         irq('    print("tick")\n'),
         c_irq("print", '    kprintf("tick\\n");\n')),
    Seed("irq-float", "irq", "uses floating point in the interrupt handler", "unsaved FPU state in ISRs",
         irq("    let scale = Float(vector) * 1.5\n"),
         c_irq("float", "    volatile double scale = 1.5 * (double)rtc_tick;\n    (void)scale;\n")),
    Seed("irq-unbounded-wait", "irq", "spins in the handler waiting for the device", "unbounded loops in handlers",
         irq("    let waiting = true\n    while waiting { waiting = vector == 0 }\n"),
         c_irq("loop", "    while (!(inb(CMOS_DATA) & 0x80)) { }\n")),
    # --- DMA buffer ownership and ordering mistakes ---
    Seed("dma-cpu-touch", "dma", "CPU writes the buffer after giving it to the device", "DMA ownership class (Linux DMA API rules)",
         Edit(M_DMA, "    let pending = dma.submit(queue, cpu, count)\n",
              "    let pending = dma.submit(queue, cpu, count)\n    dma.store8(cpu, 0, 1)\n"),
         Edit(C_DMA, "    q->notify(q);\n", "    q->notify(q);\n    buf[0] = 1;\n")),
    Seed("dma-early-read", "dma", "reads the buffer without waiting for completion", "missing completion check",
         Edit(M_DMA, "    let completed = dma.reclaim(pending, 1000)\n", "    let completed = pending\n"),
         Edit(C_DMA, "    while (READ_ONCE(q->used->idx) == q->last_used) { /* SEED:poll */\n",
              "    while (0) { /* SEED:poll */\n")),
    Seed("dma-use-after-free", "dma", "reads the buffer after releasing it", "use-after-free class",
         Edit(M_DMA, "    dma.dispose(completed)\n    return bytes\n",
              "    dma.dispose(completed)\n    let late = dma.load8(completed, 0)\n    return bytes\n"),
         Edit(C_DMA, "    platform_dma_free(buf); /* SEED:free */\n    return 0;\n",
              "    platform_dma_free(buf); /* SEED:free */\n    out[0] = buf[0];\n    return 0;\n")),
    Seed("dma-double-submit", "dma", "submits the same buffer twice", "descriptor reuse while in flight",
         Edit(M_DMA, "    let pending = dma.submit(queue, cpu, count)\n",
              "    let pending = dma.submit(queue, cpu, count)\n    let again = dma.submit(queue, cpu, count)\n"),
         Edit(C_DMA, "    WRITE_ONCE(q->avail->idx, (uint16_t)(avail_idx + 1));\n    q->notify(q);\n",
              "    WRITE_ONCE(q->avail->idx, (uint16_t)(avail_idx + 1));\n    q->notify(q);\n"
              "    q->avail->ring[(avail_idx + 1) % q->size] = 0;\n"
              "    WRITE_ONCE(q->avail->idx, (uint16_t)(avail_idx + 2));\n    q->notify(q);\n")),
    Seed("dma-leak", "dma", "never releases the buffer", "leak on the success path",
         Edit(M_DMA, "    dma.dispose(completed)\n    return bytes\n", "    return bytes\n"),
         Edit(C_DMA, "    platform_dma_free(buf); /* SEED:free */\n", "")),
    Seed("dma-wrong-length", "dma", "tells the device the buffer is one byte longer", "descriptor length bugs",
         Edit(M_DMA, "dma.submit(queue, cpu, count)", "dma.submit(queue, cpu, count + 1)"),
         Edit(C_DMA, "q->desc[0].len = (uint32_t)count;", "q->desc[0].len = (uint32_t)count + 1;")),
    Seed("dma-missing-publish-fence", "dma", "no release fence before publishing the descriptor", "missing DMA fence (Linux virtio/e1000 fixes)",
         None,
         Edit(C_DMA, "    __atomic_thread_fence(__ATOMIC_RELEASE); /* SEED:fence-publish */\n", ""),
         minyar_note="not expressible: dma.submit owns the publication fence"),
    Seed("dma-missing-acquire-fence", "dma", "no acquire fence after seeing the completion", "missing DMA fence (Linux virtio fixes)",
         None,
         Edit(C_DMA, "    __atomic_thread_fence(__ATOMIC_ACQUIRE); /* SEED:fence-acquire */\n", ""),
         minyar_note="not expressible: dma.ready/reclaim own the acquire"),
    Seed("dma-virtual-address", "dma", "puts a virtual address in the descriptor", "physical/virtual mix-up",
         None,
         Edit(C_DMA, "q->desc[0].addr = platform_virt_to_phys(buf); /* SEED:phys */",
              "q->desc[0].addr = (uint64_t)(uintptr_t)buf; /* SEED:phys */"),
         minyar_note="not expressible: the safe DMA API never exposes an address",
         c_note="the host model offsets physical addresses; Minyar OS QEMU guests identity-map, where this passes"),
)


# The measured outcome of each seed (Minyar, C) with QEMU. Without QEMU,
# "qemu" becomes "undetected". A change in either column fails the study.
EXPECTED = {
    "field-offset": ("host", "host"),
    "field-width": ("compile", "host"),
    "field-past-register": ("compile", "host"),
    "overlapping-fields": ("compile", "host"),
    "inverted-mode": ("host", "host"),
    "wrong-port-width": ("compile", "compile"),
    "register-as-port": ("compile", "qemu"),
    "write-wrong-register": ("qemu", "qemu"),
    "read-only-register-write": ("undetected", "undetected"),
    "index-out-of-range": ("qemu", "undetected"),
    "nmi-disabled": ("undetected", "undetected"),
    "read-to-clear": ("host", "host"),
    "missing-update-check": ("host", "host"),
    "irq-allocation": ("compile", "undetected"),
    "irq-lock": ("compile", "undetected"),
    "irq-print": ("compile", "undetected"),
    "irq-float": ("compile", "undetected"),
    "irq-unbounded-wait": ("compile", "undetected"),
    "dma-cpu-touch": ("compile", "host"),
    "dma-early-read": ("compile", "host"),
    "dma-use-after-free": ("compile", "host"),
    "dma-double-submit": ("compile", "host"),
    "dma-leak": ("compile", "host"),
    "dma-wrong-length": ("host", "host"),
    "dma-missing-publish-fence": ("not expressible", "undetected"),
    "dma-missing-acquire-fence": ("not expressible", "undetected"),
    "dma-virtual-address": ("not expressible", "host"),
}


# Stable semantic concepts, all required, for the compile-caught mutants.
# An unrelated compiler error or a compiler crash never counts as detection.
MINYAR_REJECTIONS = {
    "field-width": ("register field", "overlaps"),
    "field-past-register": ("register field", "outside"),
    "overlapping-fields": ("register field", "overlaps"),
    "wrong-port-width": ("Port32", "Port8"),
    "register-as-port": ("Port8", "Register8"),
    "irq-allocation": ("interrupt context",),
    "irq-lock": ("interrupt context",),
    "irq-print": ("interrupt context",),
    "irq-float": ("interrupt context",),
    "irq-unbounded-wait": ("interrupt context",),
    "dma-cpu-touch": ("DMA ownership",),
    "dma-early-read": ("Cpu", "Pending"),
    "dma-use-after-free": ("DMA ownership",),
    "dma-double-submit": ("DMA ownership",),
    "dma-leak": ("DMA ownership",),
}


def decoded_output(value):
    return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")


class StudyFailure(Exception):
    pass


class Study:
    def __init__(self, args):
        self.args = args
        self.out = args.output
        self.compiler = Path(args.compiler).resolve()
        self.runtime = Path(args.runtime).resolve()
        self.clang = shutil.which(args.clang) or args.clang
        self.llvm_bin = Path(self.clang).resolve().parent
        self.log = []
        self.base = None
        self.c_support = None

    # ----- process and tree helpers -----

    def run(self, label, command, cwd=None, timeout=120, stdin=None, quiet=False):
        started = time.monotonic()
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "LLVM_BIN")}
        timed_out = False
        try:
            process = subprocess.Popen([str(part) for part in command], cwd=cwd, env=environment,
                                       stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       encoding="utf-8", errors="replace", start_new_session=True)
        except OSError as error:
            raise StudyFailure(f"{label}: could not start command: {error}") from error
        try:
            stdout, stderr = process.communicate(input=stdin, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            stdout = decoded_output(stdout) or decoded_output(error.stdout)
            stderr = decoded_output(stderr) or decoded_output(error.stderr)
        status = 124 if timed_out else process.returncode
        stdout, stderr = decoded_output(stdout), decoded_output(stderr)
        if status == 124:
            timed_out = True
            stderr += "\nTIMEOUT"
        if not (quiet and status == 0):
            self.log.append(dict(label=label, command=[str(part) for part in command], status=status,
                                 timed_out=timed_out, seconds=round(time.monotonic() - started, 2),
                                 stdout=stdout[-4000:], stderr=stderr[-4000:]))
        if timed_out:
            raise StudyFailure(f"{label}: timeout invalidates the study (limit {timeout}s)")
        return status, stdout, stderr

    def require_build(self, label, status, stderr):
        if status != 0:
            raise StudyFailure(f"{label}: build/infrastructure failure, not driver detection (status {status})\n{stderr[-2000:]}")

    def tree(self, name, edit):
        """A private copy of the needed sources with at most one exact edit applied."""
        target = self.out / "trees" / name
        if self.base is None:
            base = self.out / "trees" / "_base"
            for entry in TREE:
                source, destination = ROOT / entry, base / entry
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, destination, symlinks=True)
                else:
                    shutil.copy2(source, destination)
            (base / "build").mkdir()
            (base / "build/minyarc").symlink_to(self.compiler)
            if not self.args.no_qemu:
                # mkimage is built through the checkout's ./minyar launcher, which
                # these private trees omit; its source is never seeded.
                mkimage = ROOT / "build/os/mkimage"
                mkimage.parent.mkdir(parents=True, exist_ok=True)
                status, _, stderr = self.run("mkimage", [ROOT / "minyar", ROOT / "os/tools/mkimage.min", "-o", mkimage],
                                             cwd=ROOT, timeout=600)
                if status != 0:
                    raise StudyFailure("could not build build/os/mkimage:\n" + stderr[-2000:])
                (base / "build/os").mkdir()
                shutil.copy2(mkimage, base / "build/os/mkimage")
                os.utime(base / "build/os/mkimage")
            self.base = base
        shutil.copytree(self.base, target, symlinks=True)
        if edit is not None:
            path = target / edit.path
            text = path.read_text(encoding="utf-8")
            if text.count(edit.old) != 1:
                raise StudyFailure(f"{name}: edit anchor must occur exactly once in {edit.path}")
            path.unlink()  # never write through a shared copy
            path.write_text(text.replace(edit.old, edit.new), encoding="utf-8")
        return target

    # ----- Minyar stages -----

    def minyar_compile(self, tree, source, freestanding):
        output = tree / "out.ll"
        output.unlink(missing_ok=True)
        command = [self.compiler, tree / source, output]
        if freestanding:
            command += ["--library", tree / "os/arch/x86_64", "--library", tree / "library",
                        "--bounded-owners", "32", "--freestanding", "--kernel-target", "x86_64"]
        else:
            command += ["--library", tree / "library"]
        status, stdout, stderr = self.run(f"{tree.name}/minyar-compile", command, timeout=180)
        if status == 0:
            if stdout or stderr or not output.is_file() or output.stat().st_size == 0:
                raise StudyFailure(f"{tree.name}: compiler success lacks clean, fresh LLVM evidence")
        elif (status != 1 or output.exists() or stdout or "error:" not in stderr or
              re.search(r"\.min:\d+:\d+", stderr) is None or
              re.search(r"LLVM ERROR|Traceback|Sanitizer|runtime error:|Segmentation fault|List position|Minyar stopped:|internal compiler", stderr, re.I)):
            raise StudyFailure(f"{tree.name}: compiler failure is not a semantic source rejection\n{stderr[-2000:]}")
        return status == 0, stderr.strip().splitlines()[:1]

    def minyar_rtc_host(self, tree):
        artifacts = self.out / "oracle-artifacts" / tree.name
        artifacts.parent.mkdir(parents=True, exist_ok=True)
        status, stdout, stderr = self.run(f"{tree.name}/minyar-host", [
            sys.executable, tree / "tests/osdev-rtc.py", "--compiler", self.compiler, "--clang", self.clang,
            "--group", "decode", "--group", "reader", "--artifacts", artifacts], timeout=600)
        try:
            events = json.loads((artifacts / "events.json").read_text())
        except (OSError, ValueError) as error:
            raise StudyFailure(f"{tree.name}: missing RTC execution evidence") from error
        if not isinstance(events, list) or not events:
            raise StudyFailure(f"{tree.name}: malformed RTC execution evidence")
        runs = []
        for event in events:
            if (not isinstance(event, dict) or not isinstance(event.get("stage"), str) or
                    type(event.get("status")) is not int or type(event.get("timed_out")) is not bool):
                raise StudyFailure(f"{tree.name}: malformed RTC stage evidence")
            stage = event["stage"]
            if event["timed_out"] or event["status"] == 124:
                raise StudyFailure(f"{tree.name}: nested RTC timeout invalidates the study")
            if stage == "runtime-build" or stage.endswith("-compile") or "-link-" in stage:
                self.require_build(stage, event["status"], stderr)
            elif "-run-" in stage:
                runs.append(event)
            else:
                raise StudyFailure(f"{tree.name}: unknown RTC stage {stage!r}")
        expected = ["runtime-build"]
        for group in ("decode", "reader"):
            expected.append(group + "-compile")
            for level in ("O0", "O2"):
                expected.extend((group + "-link-" + level, group + "-run-" + level))
        if [event["stage"] for event in events] != expected[:len(events)]:
            raise StudyFailure(f"{tree.name}: RTC stage order/coverage does not match the selected groups")
        if status == 0:
            if len(events) != len(expected) or any(event["status"] != 0 for event in events):
                raise StudyFailure(f"{tree.name}: incomplete or contradictory RTC success evidence")
        elif (status != 1 or not runs or "-run-" not in events[-1]["stage"] or
              "Traceback" in stderr or not (events[-1]["status"] != 0 or re.search(
                  r"(?m)^RTC oracle FAILED: [^\n]*output/diagnostic mismatch", stderr))):
            raise StudyFailure(f"{tree.name}: RTC harness failed without a runtime/oracle detection\n{stderr[-2000:]}")
        return status == 0, (stderr or stdout).strip().splitlines()[-1:]

    def minyar_dma_host(self, tree):
        for level in ("-O0", "-O2"):
            executable = tree / ("entropy" + level)
            status, stdout, stderr = self.run(f"{tree.name}/minyar-link{level}", [
                self.clang, level, "-Wno-override-module", tree / "out.ll", self.runtime, "-lm", "-pthread",
                "-o", executable])
            self.require_build(f"{tree.name}/minyar-link{level}", status, stderr)
            status, stdout, stderr = self.run(f"{tree.name}/minyar-run{level}", [executable], timeout=60)
            if status != 0 or stderr or stdout != "MINYAR ENTROPY HOST PASS\n":
                return False, (stderr or stdout).strip().splitlines()[-1:] or [f"status {status}"]
        return True, []

    def qemu_log_valid(self, tree, serial):
        status, stdout, stderr = self.run(f"{tree.name}/serial-validator", [
            sys.executable, tree / "tests/osdev-rtc.py", "--qemu-log", serial, "--rtc-base", RTC_BASE,
            "--log-only"], timeout=30)
        if status != 0:
            semantic = ("RTC serial calendar is ", "invalid RTC serial calendar:", "malformed RTC calendar serial line")
            if (status != 1 or "RTC oracle FAILED:" not in stderr or not any(term in stderr for term in semantic) or
                    re.search(r"Traceback|Sanitizer|runtime error:|LLVM ERROR", stderr, re.I)):
                raise StudyFailure(f"{tree.name}: serial validator failed without a calendar-oracle rejection\n{stderr[-2000:]}")
        return status == 0, (stderr or stdout).strip().splitlines()[-1:]

    def minyar_qemu(self, tree):
        # The same make command tools/osdev.py issues, without its compiler
        # bootstrap: this private tree links the already-built compiler.
        source = tree / "os/tests/rtc-kernel.min"
        status, stdout, stderr = self.run(f"{tree.name}/minyar-os-build", [
            "make", "-C", tree / "os", "ARCH=x86_64", f"LLVM_BIN={self.llvm_bin}", "-W", source,
            f"KERNEL_SOURCE={source}", "all"], timeout=900)
        self.require_build(f"{tree.name}/minyar-os-build", status, stderr)
        serial = tree / "serial.log"
        status, stdout, stderr = self.run(f"{tree.name}/minyar-qemu", [
            sys.executable, tree / "tools/osdev.py", "test", "--root", tree, "--no-build", "--arch", "x86_64",
            "--expect", "OSDEV RTC PASS", "--timeout", "30", "--rtc-base", RTC_BASE,
            "--llvm-bin", self.llvm_bin, "--log", serial], timeout=120)
        if status != 0:
            text = serial.read_text(errors="replace") if serial.is_file() else ""
            if status != 1 or "OSDEV RTC START" not in text or re.search(
                    r"Minyar stopped:|C comparator RTC error|Minyar OS processor exception|PANIC:", text) is None:
                raise StudyFailure(f"{tree.name}: QEMU failed without guest defect evidence\n{stderr[-2000:]}")
            return False, text.strip().splitlines()[-3:]
        return self.qemu_log_valid(tree, serial)

    # ----- C stages -----

    def c_compile(self, tree, driver):
        artifact = tree / ("irq.o" if driver == "irq" else "dma.o" if driver == "dma" else "rtc.o")
        artifact.unlink(missing_ok=True)
        flags = ["-Wall", "-Wextra"]
        if driver == "irq":
            command = [self.clang, "--target=x86_64-unknown-none-elf", "-ffreestanding", "-mgeneral-regs-only",
                       "-mno-red-zone", "-O2", *flags, "-c", tree / C_IRQ, "-o", tree / "irq.o"]
        elif driver == "dma":
            command = [self.clang, "-std=c11", "-O2", *flags, "-c", tree / C_DMA, "-o", tree / "dma.o"]
        else:
            # The port adapter is x86 code even when hosted oracles run on Arm.
            # Check its actual instruction widths independently of host macros.
            command = [self.clang, "--target=x86_64-unknown-none-elf", "-ffreestanding", "-std=c11",
                       "-O2", *flags, "-c", tree / C_RTC, "-o", artifact]
        status, stdout, stderr = self.run(f"{tree.name}/c-compile", command, timeout=120)
        if status != 0:
            expected = tree.name == "wrong-port-width-c"
            source_error = re.search(r"rtc\.c:\d+:\d+: error: invalid operand for instruction", stderr)
            if (not expected or status != 1 or artifact.exists() or stdout or source_error is None or
                    re.search(r"LLVM ERROR|Traceback|PLEASE submit|Segmentation fault|Sanitizer|runtime error:", stderr, re.I)):
                raise StudyFailure(f"{tree.name}: C compiler failed outside the expected width rejection\n{stderr[-2000:]}")
        else:
            artifact = tree / ("irq.o" if driver == "irq" else "dma.o" if driver == "dma" else "rtc.o")
            if not artifact.is_file() or artifact.stat().st_size == 0:
                raise StudyFailure(f"{tree.name}: C compiler success lacks an artifact")
        warnings = [line for line in stderr.splitlines() if "warning:" in line]
        errors = [line for line in stderr.splitlines() if "error:" in line]
        return status == 0, (errors or warnings)[:1], bool(warnings)

    def c_rtc_host(self, tree):
        oracle = load_oracle(tree / "tests/osdev-rtc.py")
        builds = [("O2", ["-O2"]), ("O0-asan-ubsan", ["-O0", "-g", "-fsanitize=address,undefined",
                                                      "-fno-sanitize-recover=undefined"])]
        for label, flags in builds:
            executable = tree / ("rtc-host-" + label)
            status, _, stderr = self.run(f"{tree.name}/c-host-build-{label}", [
                self.clang, "-std=c11", *flags, "-DRTC_COMPARATOR_CLI", tree / C_RTC, "-o", executable])
            self.require_build(f"{tree.name}/c-host-build-{label}", status, stderr)
            for case in oracle.decode_cases():
                status, stdout, stderr = self.run(f"{tree.name}/c-decode-{label}", [executable, "decode", *case.raw],
                                                  timeout=20, quiet=True)
                if status != 0 or stderr or not same_calendar(stdout, case.expected):
                    return False, [f"{label} decode {case.name}: {stdout.strip()[:80]} {stderr.strip()[:80]}"]
            for case in oracle.read_cases():
                script = "".join(f"{register} {value}\n" for register, value in zip(case.registers, case.values))
                status, stdout, stderr = self.run(f"{tree.name}/c-read-{label}", [executable, "read", case.budget],
                                                  timeout=20, stdin=script, quiet=True)
                try:
                    result = json.loads(stdout)
                except json.JSONDecodeError:
                    return False, [f"{label} read {case.name}: no result ({stderr.strip()[:80]})"]
                reads = result.get("reads", -1)
                ok = (status == 0 and not stderr and result.get("script_error") == "none" and
                      same_calendar(stdout, case.expected) and case.minimum_reads <= reads <= len(case.registers))
                if ok and case.minimum_reads == len(case.registers):
                    ok = reads == len(case.registers)
                if not ok:
                    return False, [f"{label} read {case.name}: {stdout.strip()[:100]} {stderr.strip()[:80]}"]
        return True, []

    def c_dma_host(self, tree):
        sources = [tree / "tests/osdev-seeds/c" / name for name in ("model.c", "virtio_entropy.c", "test_entropy.c")]
        builds = [("O2", ["-O2"]), ("O0-asan-ubsan", ["-O0", "-g", "-fsanitize=address,undefined",
                                                      "-fno-sanitize-recover=undefined"])]
        for label, flags in builds:
            executable = tree / ("entropy-host-" + label)
            status, _, stderr = self.run(f"{tree.name}/c-host-build-{label}", [
                self.clang, "-std=c11", "-Wall", "-Wextra", *flags, *sources, "-o", executable])
            self.require_build(f"{tree.name}/c-host-build-{label}", status, stderr)
            status, stdout, stderr = self.run(f"{tree.name}/c-host-run-{label}", [executable], timeout=60)
            if status != 0 or stderr or stdout != "C ENTROPY HOST PASS\n":
                lines = [line for line in (stderr + stdout).splitlines() if line.strip()]
                summary = next((line for line in lines if "ERROR" in line or "FAIL" in line or "runtime error" in line),
                               lines[-1] if lines else f"status {status}")
                return False, [f"{label}: {summary.strip()[:140]}"]
        return True, []

    def prepare_c_support(self, tree):
        """Bare x86 support objects and image inputs, built once from the base tree's actual OS sources."""
        if self.c_support is not None:
            return self.c_support
        support = self.out / "c-support"
        support.mkdir()
        objects = [support / name for name in ("runtime.o", "freestanding.o", "entry.o")]
        status, stdout, stderr = self.run("c-support/make", [
            "make", "-C", tree / "os", "-j2", "ARCH=x86_64", f"OUT={support}", f"LLVM_BIN={self.llvm_bin}",
            *objects], timeout=600)
        if status != 0:
            raise StudyFailure("could not build the bare x86 support objects:\n" + stderr[-2000:])
        status, stdout, stderr = self.run("c-support/resource", [self.clang, "-print-resource-dir"])
        self.require_build("c-support/resource", status, stderr)
        self.c_support = dict(objects=objects, resource=Path(stdout.strip()) / "include")
        return self.c_support

    def c_qemu(self, tree):
        built = self.base_qemu_tree / "build/os/x86_64"
        support = self.prepare_c_support(self.base_qemu_tree)
        fixture = tree / "c-fixture"
        isolated = fixture / "build/os/x86_64"
        isolated.mkdir(parents=True)
        (fixture / "os").mkdir()
        shutil.copy2(tree / "os/Makefile", fixture / "os/Makefile")
        for name in ("mbr.bin", "loader.bin", "config.txt"):
            shutil.copy2(built / name, isolated / name)
        program = isolated / "c-rtc-program.o"
        status, stdout, stderr = self.run(f"{tree.name}/c-guest-compile", [
            self.clang, "--target=x86_64-unknown-none-elf", "-march=x86-64-v2", "-O2", "-flto", "-ffreestanding",
            "-fno-builtin", "-nostdinc", "-isystem", support["resource"], "-isystem",
            tree / "runtime/freestanding/include", "-mno-red-zone", "-fno-stack-protector", "-fno-pic",
            "-include", tree / C_RTC, "-c", tree / "tests/osdev-seeds/c/rtc_guest.c", "-o", program])
        self.require_build(f"{tree.name}/c-guest-compile", status, stderr)
        kernel = isolated / "kernel.elf"
        entry, runtime, freestanding = support["objects"][2], support["objects"][0], support["objects"][1]
        status, stdout, stderr = self.run(f"{tree.name}/c-guest-link", [
            self.llvm_bin / "ld.lld", "-static", "--no-pie", "-nostdlib", "--lto-O3", "-mllvm", "-mcpu=x86-64-v2",
            "-z", "max-page-size=4096", "--image-base=0", "-T", tree / "os/arch/x86_64/boot/kernel.ld",
            entry, program, runtime, freestanding, "-o", kernel])
        self.require_build(f"{tree.name}/c-guest-link", status, stderr)
        fonts = [f"fonts/{font}={tree / 'os/assets/fonts' / font}"
                 for font in ("Archivo-Regular.ttf", "Archivo-Medium.ttf", "Archivo-SemiBold.ttf")]
        status, stdout, stderr = self.run(f"{tree.name}/c-guest-image", [
            self.base_qemu_tree / "build/os/mkimage", isolated / "minyar-os.img", isolated / "mbr.bin",
            isolated / "loader.bin", f"kernel.elf={kernel}", f"config.txt={isolated / 'config.txt'}", *fonts],
            cwd=tree / "os")
        self.require_build(f"{tree.name}/c-guest-image", status, stderr)
        serial = tree / "c-serial.log"
        status, stdout, stderr = self.run(f"{tree.name}/c-qemu", [
            sys.executable, tree / "tools/osdev.py", "test", "--root", fixture, "--no-build", "--arch", "x86_64",
            "--llvm-bin", self.llvm_bin, "--rtc-base", RTC_BASE, "--expect", "OSDEV RTC PASS",
            "--timeout", "30", "--log", serial], timeout=120)
        if status != 0:
            text = serial.read_text(errors="replace") if serial.is_file() else ""
            if status != 1 or "OSDEV RTC START" not in text or re.search(
                    r"Minyar stopped:|C comparator RTC error|Minyar OS processor exception|PANIC:", text) is None:
                raise StudyFailure(f"{tree.name}: QEMU failed without guest defect evidence\n{stderr[-2000:]}")
            return False, text.strip().splitlines()[-3:]
        return self.qemu_log_valid(tree, serial)

    # ----- the ladder -----

    def ladder(self, name, language, driver, edit):
        """Return the first stage that rejects this program, or 'undetected'."""
        tree = self.tree(f"{name}-{language}", edit)
        evidence = {}
        warned = False
        if language == "minyar":
            source = {"rtc": "os/tests/rtc-kernel.min", "irq": M_IRQ, "dma": M_DMA}[driver]
            passed, detail = self.minyar_compile(tree, source, driver != "dma")
        else:
            passed, detail, warned = self.c_compile(tree, driver)
        evidence["compile"] = detail
        if not passed:
            if language == "minyar":
                required = MINYAR_REJECTIONS.get(name)
                if required is None or not all(term in "\n".join(detail) for term in required):
                    raise StudyFailure(f"{name}: wrong semantic rejection; expected {required}, got {detail}")
            return "compile", evidence, warned
        host = {("minyar", "rtc"): self.minyar_rtc_host, ("minyar", "dma"): self.minyar_dma_host,
                ("c", "rtc"): self.c_rtc_host, ("c", "dma"): self.c_dma_host}.get((language, driver))
        if host is not None:
            passed, detail = host(tree)
            evidence["host"] = detail
            if not passed:
                return "host", evidence, warned
        if driver == "rtc" and not self.args.no_qemu:
            passed, detail = (self.minyar_qemu if language == "minyar" else self.c_qemu)(tree)
            evidence["qemu"] = detail
            if not passed:
                return "qemu", evidence, warned
        if not self.args.keep_trees and not name.startswith("baseline"):
            shutil.rmtree(tree, ignore_errors=True)
        return "undetected", evidence, warned

    def baseline(self):
        """Unmodified drivers must pass every stage; the Minyar RTC run also builds the OS image inputs."""
        results = {}
        for driver in ("rtc", "irq", "dma"):
            for language in ("minyar", "c"):
                if driver == "rtc" and language == "c" and not self.args.no_qemu:
                    continue  # needs the Minyar baseline's OS build; checked below
                results[f"{driver}/{language}"] = self.clean_baseline(driver, language)
                if driver == "rtc" and language == "minyar":
                    self.base_qemu_tree = self.out / "trees" / f"baseline-{driver}-{language}"
        if not self.args.no_qemu:
            results["rtc/c"] = self.clean_baseline("rtc", "c")
        return results

    def clean_baseline(self, driver, language):
        outcome, evidence, warned = self.ladder(f"baseline-{driver}", language, driver, None)
        if outcome != "undetected" or warned:
            raise StudyFailure(f"baseline {driver}/{language} does not pass cleanly: {outcome} {evidence}")
        return outcome, evidence, warned


def load_oracle(path):
    spec = importlib.util.spec_from_file_location("osdev_rtc_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def same_calendar(stdout, expected):
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    if expected is None:
        return result.get("error") != "ok" and result.get("calendar") is None
    return result.get("error") == "ok" and result.get("calendar") == list(expected)


def describe(outcome, warned, note):
    text = {"compile": "compile time", "host": "host tests", "qemu": "only in QEMU",
            "undetected": "undetected"}[outcome]
    if warned and outcome != "compile":
        text += " (compile warning)"
    if warned and outcome == "compile":
        text = "compile time"
    return text + (f"; {note}" if note else "")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compiler", default=os.environ.get("MINYAR_TEST_COMPILER", str(ROOT / "build/minyarc")))
    parser.add_argument("--runtime", default=os.environ.get("MINYAR_TEST_RUNTIME", str(ROOT / "build/minyar-runtime.o")))
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--output", type=Path, help="new or empty directory outside the checkout")
    parser.add_argument("--seed", action="append", default=[], help="run only these seed names")
    parser.add_argument("--no-qemu", action="store_true", help="skip the QEMU stage (RTC seeds stop at host tests)")
    parser.add_argument("--keep-trees", action="store_true")
    args = parser.parse_args()
    if not args.no_qemu and sys.platform != "linux":
        parser.error("run the full QEMU study on the BX Linux box; --no-qemu is portable")
    if args.output is None:
        args.output = Path(tempfile.mkdtemp(prefix="osdev-seeds-"))
    args.output = args.output.resolve()
    if args.output == ROOT or ROOT in args.output.parents:
        parser.error("--output must be outside the checkout")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("--output must be new or empty")
    study = Study(args)
    rows = []
    changed = []
    status = 1
    try:
        study.baseline()
        print("baseline: unmodified Minyar and C drivers pass every stage", flush=True)
        selected = [seed for seed in SEEDS if not args.seed or seed.name in args.seed]
        for seed in selected:
            row = dict(name=seed.name, driver=seed.driver, mistake=seed.mistake, source=seed.source)
            for language, edit, note in (("minyar", seed.minyar, seed.minyar_note), ("c", seed.c, seed.c_note)):
                if edit is None:
                    row[language] = dict(outcome="not expressible", text=note, evidence={})
                    continue
                outcome, evidence, warned = study.ladder(seed.name, language, seed.driver, edit)
                row[language] = dict(outcome=outcome, warned=warned, text=describe(outcome, warned, note),
                                     evidence=evidence)
            rows.append(row)
            print(f"{seed.name}: Minyar {row['minyar']['text']} | C {row['c']['text']}", flush=True)
            expected = tuple("undetected" if args.no_qemu and outcome == "qemu" else outcome
                             for outcome in EXPECTED[seed.name])
            actual = (row["minyar"]["outcome"], row["c"]["outcome"])
            if actual != expected:
                changed.append(f"{seed.name}: expected Minyar {expected[0]} / C {expected[1]}, "
                               f"found Minyar {actual[0]} / C {actual[1]}")
        if changed:
            raise StudyFailure("seed outcomes changed:\n  " + "\n  ".join(changed))
        status = 0
    except StudyFailure as error:
        print(f"seeded-mistake study failed: {error}", file=sys.stderr)
    finally:
        (args.output / "results.json").write_text(json.dumps(dict(rows=rows, log=study.log), indent=1) + "\n")
        table = ["| Mistake | Driver | Minyar | C |", "| --- | --- | --- | --- |"]
        for row in rows:
            table.append(f"| {row['mistake']} | {row['driver']} | {row['minyar']['text']} | {row['c']['text']} |")
        (args.output / "table.md").write_text("\n".join(table) + "\n")
        print("seeded-mistake evidence: " + str(args.output), flush=True)
    return status


if __name__ == "__main__":
    sys.exit(main())
