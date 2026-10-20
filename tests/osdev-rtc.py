#!/usr/bin/env python3
"""Independent RTC contract checks; execute on BX, never on the laptop.

No RTC implementation is copied here. Generated programs import os/shared/rtc.min;
datetime generates calendar expectations and scripted transactions enforce the
frozen read protocol. MINYAR_TEST_COMPILER, MINYAR_TEST_CLANG and
MINYAR_TEST_LINK_FLAGS select the existing tools and sanitizer configuration.
The scratch ownership runtime uses the same actual-runtime transformation as
tests/frontend-fixtures.min. --qemu-log checks serial data, not guest exit.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_STARTED = "2026-10-20T01:05:40Z"  # Never reset by this test runner.
TRACE = (0, 10, 0, 11, 2, 4, 7, 8, 9, 10, 0)
ALLOWED = (0, 2, 4, 7, 8, 9, 10, 11)  # Register C (12) is intentionally absent.
MODES = (0, 2, 4, 6)


class CheckFailure(Exception):
    pass


@dataclass(frozen=True)
class DecodeCase:
    name: str
    raw: tuple
    expected: tuple | None


@dataclass(frozen=True)
class ReadCase:
    name: str
    registers: tuple
    values: tuple
    budget: int
    expected: tuple | None
    minimum_reads: int


def calendar(value):
    return (value.year, value.month, value.day, value.hour, value.minute, value.second)


def bcd(value):
    return (value // 10) * 16 + value % 10


def encode(parts, mode):
    """Test-data encoder only: validity comes from datetime, never the driver."""
    year, month, day, hour, minute, second = parts
    pm = 0
    if not mode & 2:
        pm = 128 if hour >= 12 else 0
        hour = hour % 12 or 12
    fields = (year - 2000, month, day, hour, minute, second)
    if not mode & 4:
        fields = tuple(bcd(value) for value in fields)
    fields = (*fields[:3], fields[3] | pm, *fields[4:])
    return (mode, *fields)


def decode_cases():
    result = []

    def valid(label, value, mode, extra=0):
        expected = calendar(value)
        raw = encode(expected, mode)
        result.append(DecodeCase(f"{label}-mode{mode}-extra{extra}",
                                 (raw[0] | extra, *raw[1:]), expected))

    # All hours expose both PM masking and the 12-hour midnight/noon mapping.
    for mode in MODES:
        for hour in range(24):
            valid(f"hour-{hour}", datetime(2026, 10, 20, hour, 34, 56), mode)
        for month in range(1, 13):
            first = datetime(2024, month, 1, 0, 0, 0)
            next_month = datetime(2025, 1, 1) if month == 12 else datetime(2024, month + 1, 1)
            valid(f"month-{month}-first", first, mode)
            valid(f"month-{month}-last", next_month - timedelta(seconds=1), mode)
        for index, value in enumerate((datetime(2000, 1, 1), datetime(2000, 2, 29, 23, 59, 59),
                                       datetime(2025, 2, 28, 23, 59, 59),
                                       datetime(2099, 12, 31, 23, 59, 59))):
            valid(f"boundary-{index}", value, mode)
        valid("unrelated-status-b-bits", datetime(2026, 10, 20, 13, 2, 3), mode, 0xF9)
    generator = random.Random(0x146818)
    for index in range(32):
        value = datetime(2000, 1, 1) + timedelta(days=generator.randrange(36525),
                                                seconds=generator.randrange(86400))
        for mode in MODES:
            valid(f"generated-{index}", value, mode)

    # datetime independently rejects impossible calendar tuples.
    invalid_dates = ((2025, 2, 29, 12, 34, 56), (2026, 4, 31, 12, 34, 56),
                     (2026, 0, 1, 12, 34, 56), (2026, 13, 1, 12, 34, 56),
                     (2026, 1, 0, 12, 34, 56), (2026, 1, 32, 12, 34, 56),
                     (2026, 1, 1, 12, 60, 0), (2026, 1, 1, 12, 0, 60))
    for index, parts in enumerate(invalid_dates):
        try:
            datetime(*parts)
        except ValueError:
            pass
        else:
            raise CheckFailure("invalid-date oracle accidentally accepted its control")
        for mode in MODES:
            result.append(DecodeCase(f"invalid-date-{index}-mode{mode}", encode(parts, mode), None))
    for mode in MODES:
        base = encode((2026, 10, 20, 12, 34, 56), mode)
        invalid_hours = (0, 13, 0x80, 0x80 | 13) if not mode & 2 else (24, 25)
        for hour in invalid_hours:
            # The hour is a raw byte; 0x13 is valid BCD but outside 1..12.
            raw_hour = (bcd(hour & 127) | (hour & 128)) if not mode & 4 else hour
            raw = (*base[:4], raw_hour, *base[5:])
            result.append(DecodeCase(f"invalid-hour-{hour}-mode{mode}", raw, None))
        raw = list(base)
        raw[1] = bcd(100) if not mode & 4 else 100
        result.append(DecodeCase(f"year-window-mode{mode}", tuple(raw), None))
    for mode in (0, 2):
        base = encode((2026, 10, 20, 12, 34, 56), mode)
        for field, bad in enumerate((0x2A, 0x0A, 0x1A, 0x1A, 0x3A, 0x5A), 1):
            raw = list(base)
            raw[field] = bad
            result.append(DecodeCase(f"invalid-bcd-field{field}-mode{mode}", tuple(raw), None))
    base = encode((2026, 10, 20, 12, 34, 56), 6)
    for field in range(7):
        for bad in (-1, 256, -9223372036854775808, 9223372036854775807):
            raw = list(base)
            raw[field] = bad
            result.append(DecodeCase(f"nonbyte-field{field}-{bad}", tuple(raw), None))
    return result


def transaction(parts, mode=6):
    status, year, month, day, hour, minute, second = encode(parts, mode)
    return (TRACE, (second, 0, second, status, minute, hour, day, month, year, 0, second))


def read_cases():
    result = []
    ordinary = (2026, 10, 20, 12, 34, 56)

    def add(name, steps, budget, expected, minimum_reads=None):
        registers = tuple(register for trace, _ in steps for register in trace)
        values = tuple(value for _, data in steps for value in data)
        if len(registers) != len(values) or any(register not in ALLOWED for register in registers):
            raise CheckFailure("invalid independent transport script")
        if len(registers) > max(0, budget) * 11:
            raise CheckFailure("transport script exceeds its attempt budget")
        if expected is not None:
            datetime(*expected)
        minimum = len(registers) if minimum_reads is None else minimum_reads
        if not 0 <= minimum <= len(registers):
            raise CheckFailure("invalid transport read lower bound")
        result.append(ReadCase(name, registers, values, budget, expected, minimum))

    stable = transaction(ordinary)
    for mode in MODES:
        for hour in (0, 1, 12, 13, 23):
            parts = (*ordinary[:3], hour, *ordinary[4:])
            add(f"stable-mode{mode}-hour{hour}", [transaction(parts, mode)], 1, parts)
    add("maximum-valid-budget", [stable], 1_000_000, ordinary)
    low_status_a = list(stable[1])
    low_status_a[1] = 0x26
    low_status_a[9] = 0x7F
    add("non-uip-status-a-bits", [(TRACE, tuple(low_status_a))], 1, ordinary)
    busy = ((0, 10), (56, 128))
    add("uip-mask-with-low-bits", [((0, 10), (56, 255)), stable], 2, ordinary)
    early_change = ((0, 10, 0), (56, 0, 57))
    after_uip = (TRACE[:-1], (*stable[1][:-2], 128))
    capture_change = (TRACE, (*stable[1][:-1], 57))
    add("delayed-uip", [busy, busy, stable], 3, ordinary)
    add("seconds-before-uip-recheck", [early_change, stable], 2, ordinary)
    add("uip-after-capture", [after_uip, stable], 2, ordinary)
    add("seconds-change-during-capture", [capture_change, stable], 2, ordinary)
    # An inconsistent capture across midnight must be discarded before decode.
    later = (2026, 11, 1, 0, 0, 0)
    mixed = (TRACE, (59, 0, 59, 6, 0, 0, 1, 11, 26, 0, 0))
    add("date-rollover", [mixed, transaction(later)], 2, later)
    add("several-faults-in-order", [busy, early_change, after_uip, capture_change, stable], 5, ordinary)
    for name, step in (("stuck-uip", busy), ("early-change-exhaustion", early_change),
                       ("post-capture-change-exhaustion", capture_change),
                       ("post-capture-uip-exhaustion", after_uip)):
        add(name, [step] * 3, 3, None)
    for budget in (-9223372036854775808, -1, 0, 1_000_001, 9223372036854775807):
        add(f"invalid-budget-{budget}", [], budget, None)
    # Coherent transport does not make bad calendar data valid.
    for name, parts in (("invalid-leap-date", (2025, 2, 29, 12, 34, 56)),
                        ("reordered-calendar-values", (2026, 20, 10, 12, 34, 56)),
                        ("invalid-seconds", (2026, 10, 20, 12, 34, 60))):
        add(name, [transaction(parts)], 1, None)
    for position in range(len(TRACE)):
        for bad in (-1, 256):
            values = list(stable[1])
            values[position] = bad
            # The API freezes Err, order and bounded reads, but permits either
            # immediate validation or capture followed by decoder validation.
            add(f"nonbyte-read{position}-{bad}", [(TRACE, tuple(values))], 1, None, position + 1)
    bcd_bad = list(transaction(ordinary, 2)[1])
    bcd_bad[4] = 0x3A
    add("coherent-invalid-bcd", [(TRACE, tuple(bcd_bad))], 1, None)
    return result


def quoted(value):
    return json.dumps(str(value), ensure_ascii=True)


def integers(values):
    return "[" + ", ".join(str(value) for value in values) + "]"


def prefix():
    # The compiler searches ROOT/os/shared before ROOT/library below, so this
    # package is the actual shared reader even from an external scratch path.
    return 'use "rtc" as rtc\n' + r'''
function emit(label: Text, result: Result<rtc.Calendar, Text>) {
    match result {
        Ok(value) { print(label + " OK " + Text(value.year) + " " + Text(value.month) + " " + Text(value.day) + " " + Text(value.hour) + " " + Text(value.minute) + " " + Text(value.second)) }
        Err(message) { if message.length == 0 { fail("empty RTC error") }; print(label + " ERR") }
    }
}
'''


def expected_line(label, expected):
    return label + (" ERR\n" if expected is None else " OK " + " ".join(map(str, expected)) + "\n")


def decode_program(cases):
    lines = [prefix()]
    expected = []
    for index, case in enumerate(cases):
        label = f"D{index}:{case.name}"
        lines.append(f'emit({quoted(label)}, rtc.decode({", ".join(map(str, case.raw))}))\n')
        expected.append(expected_line(label, case.expected))
    return "".join(lines), "".join(expected)


def reader_program(cases):
    lines = [prefix(), r'''
record ReadScript { registers: List<Integer>; values: List<Integer>; position: Integer }
function readCase(label: Text, registers: List<Integer>, values: List<Integer>, budget: Integer, minimumReads: Integer) {
    let state = ReadScript { registers: registers; values: values; position: 0 }
    let readRegister: Callback<Integer, Integer> = function(register: Integer): Integer {
        if register == 12 { fail("RTC touched read-to-clear Register C") }
        if register != 0 && register != 2 && register != 4 && register != 7 && register != 8 && register != 9 && register != 10 && register != 11 { fail("RTC requested unsupported register") }
        if state.position >= state.registers.length { fail("RTC exceeded scripted read budget") }
        if register != state.registers[state.position] { fail("RTC changed frozen register read order") }
        let value = state.values[state.position]
        state.position += 1
        return value
    }
    emit(label, rtc.read(readRegister, budget))
    if state.position < minimumReads || state.position > state.registers.length { fail("RTC violated required transport read bounds") }
    if minimumReads == state.registers.length { print(label + " READS " + Text(state.position)) }
    else { print(label + " READS BOUNDED") }
}
''']
    expected = []
    for index, case in enumerate(cases):
        label = f"R{index}:{case.name}"
        lines.append(f'readCase({quoted(label)}, {integers(case.registers)}, {integers(case.values)}, {case.budget}, {case.minimum_reads})\n')
        expected.append(expected_line(label, case.expected))
        count = str(len(case.registers)) if case.minimum_reads == len(case.registers) else "BOUNDED"
        expected.append(label + " READS " + count + "\n")
    return "".join(lines), "".join(expected)


def address_enabled(flags):
    enabled = False
    for flag in flags:
        if flag.startswith("-fsanitize=") and "address" in flag.split("=", 1)[1].split(","):
            enabled = True
        if flag.startswith("-fno-sanitize=") and set(flag.split("=", 1)[1].split(",")) & {"address", "all"}:
            enabled = False
    return enabled


def instrument(source):
    """Mirror testing.min's explicit ASan IR annotation; linker flags alone do not."""
    groups = {}
    for line in source.splitlines():
        found = re.match(r"attributes\s+(#\d+)\s*=\s*\{(.*)\}\s*$", line)
        if found:
            groups[found[1]] = found[2]
    result = []
    count = 0
    for line in source.splitlines(keepends=True):
        if line.startswith("define "):
            masked = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
            if not masked.rstrip().endswith("{"):
                raise CheckFailure("unsupported LLVM function header for ASan instrumentation")
            attributes = masked[masked.rfind(")") + 1:]
            for group in re.findall(r"#\d+", attributes):
                if group not in groups:
                    raise CheckFailure("undefined LLVM attribute group")
                attributes += " " + groups[group]
            if not re.search(r"\bsanitize_address\b", attributes):
                brace = line.rfind("{")
                line = line[:brace] + "sanitize_address " + line[brace:]
            count += 1
        result.append(line)
    if not count:
        raise CheckFailure("LLVM contains no functions to instrument")
    return "".join(result)


def kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


class Runner:
    def __init__(self, directory, args, flags):
        self.directory = directory
        self.args = args
        self.flags = flags
        self.environment = os.environ.copy()  # Preserve ASAN_OPTIONS/UBSAN_OPTIONS.
        self.events = []
        self.serial = 0

    def invoke(self, stage, command, timeout):
        self.serial += 1
        stem = self.directory / f"{self.serial:02d}-{stage}"
        command = list(map(str, command))
        started = time.monotonic()
        process = subprocess.Popen(command, cwd=ROOT, env=self.environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace",
                                   start_new_session=True)
        timed_out = False
        try:
            output, errors = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_group(process)
            output, errors = process.communicate()
            errors += f"\ncommand exceeded {timeout}s deadline\n"
        finally:
            if process.poll() is None:
                kill_group(process)
                process.wait()
        status = 124 if timed_out else process.returncode
        elapsed = time.monotonic() - started
        stem.with_suffix(".stdout").write_text(output, encoding="utf-8")
        stem.with_suffix(".stderr").write_text(errors, encoding="utf-8")
        self.events.append(dict(stage=stage, command=command, status=status,
                                elapsed_seconds=elapsed, timed_out=timed_out))
        (self.directory / "events.json").write_text(json.dumps(self.events, indent=2) + "\n", encoding="utf-8")
        print(f"{stage}: status {status} ({elapsed:.2f}s)", flush=True)
        if timed_out:
            raise CheckFailure(f"{stage} timed out\n{shlex.join(command)}\n{errors}")
        return status, output, errors

    def require(self, stage, command, timeout):
        status, output, errors = self.invoke(stage, command, timeout)
        if status:
            raise CheckFailure(f"{stage} failed with status {status}\n{shlex.join(list(map(str, command)))}\n{output}{errors}")
        return output, errors

    def compile(self, name, source, rejection=False):
        path = self.directory / name
        path.with_suffix(".min").write_text(source, encoding="utf-8")
        llvm = path.with_suffix(".ll")
        command = [self.args.compiler, path.with_suffix(".min"), llvm,
                   "--library", ROOT / "os/shared", "--library", ROOT / "library"]
        status, output, errors = self.invoke(name + "-compile", command, self.args.compile_timeout)
        if rejection:
            if status != 1 or output or llvm.exists() or not errors.strip():
                raise CheckFailure(f"{name}: expected source rejection without emitted LLVM\n{errors}")
            if not re.search(r"type|argument|Port|Register", errors, re.IGNORECASE):
                raise CheckFailure(f"{name}: missing type/argument diagnostic\n{errors}")
            if re.search(r"List position|Segmentation fault|Sanitizer|runtime error:|LLVM ERROR", errors):
                raise CheckFailure(f"{name}: internal failure is not a source rejection\n{errors}")
            return None
        if status or output or errors or not llvm.is_file():
            raise CheckFailure(f"{name}: LLVM generation failed\n{output}{errors}")
        if address_enabled(self.flags):
            llvm.write_text(instrument(llvm.read_text(encoding="utf-8")), encoding="utf-8")
        return llvm

    def runtime(self):
        # Reuse the established frontend fixture's cycle + ownership runtime,
        # compiling current product runtime code rather than an oracle copy.
        source = (ROOT / "runtime/minyar_runtime.c").read_text(encoding="utf-8")
        for ordinary, traced in (("minyar_rc.h", "minyar_cycle_rc.h"),
                                 ("minyar_collections.h", "minyar_cycle_collections.h")):
            before = '#include "' + ordinary + '"'
            if source.count(before) != 1:
                raise CheckFailure("actual runtime fixture include contract changed")
            source = source.replace(before, '#include "' + traced + '"')
        source = ('#define MINYAR_SORT_GRAPH 1\n#define MINYAR_MAP_CYCLE_RUNTIME 1\n'
                  '#define MINYAR_NOINLINE __attribute__((noinline))\n' + source +
                  '\n#include "minyar_callbacks.h"\n')
        contract = (ROOT / "tests/memory-contracts-runtime.c").read_text(encoding="utf-8")
        placeholder = '#include "../runtime/minyar_runtime.c"'
        if contract.count(placeholder) != 1:
            raise CheckFailure("ownership runtime fixture contract changed")
        runtime = self.directory / "rtc-runtime.c"
        runtime.write_text(contract.replace(placeholder, source), encoding="utf-8")
        output = runtime.with_suffix(".o")
        self.require("runtime-build", [self.args.clang, "-O1" if self.flags else "-O2",
                     *self.flags, "-DMINYAR_SYSTEM_HEAP=1", "-iquote", ROOT / "runtime",
                     "-c", runtime, "-o", output], self.args.link_timeout)
        return output

    def execute(self, name, source, expected, runtime):
        llvm = self.compile(name, source)
        # A pure read callback offers no writes; reject direct privileged I/O
        # accidentally emitted by the imported reader as an additional guard.
        if re.search(r'\basm\b[^\n]*"[^"\n]*\b(?:out[bwl]?|in[bwl]?)\b', llvm.read_text(encoding="utf-8")):
            raise CheckFailure(name + ": hosted RTC reader emitted privileged I/O")
        for level in ("O0", "O2"):
            executable = self.directory / f"{name}-{level}"
            self.require(name + "-link-" + level,
                         [self.args.clang, "-" + level, *self.flags, "-Wno-override-module",
                          llvm, runtime, "-lm", "-o", executable], self.args.link_timeout)
            output, errors = self.require(name + "-run-" + level, [executable], self.args.run_timeout)
            if errors or output != expected:
                difference = "".join(difflib.unified_diff(expected.splitlines(True), output.splitlines(True),
                                                        fromfile="expected", tofile="actual"))
                raise CheckFailure(f"{name} {level}: output/diagnostic mismatch\n{difference[:16000]}\n{errors}")

    def compiler_seeds(self):
        header = 'use "device" as device\n'
        # Positive typed source compiles first; none of these hardware functions
        # is executed on the host. Failure of module setup cannot pass a seed.
        self.compile("seed-typed-control", header + '''
function correct(register: device.Register8, port: device.Port8, wide: device.Port32) {
    device.out8(port, device.read8(register))
    print(device.in32(wide))
}
''')
        self.compile("seed-wrong-address-space", header + '''
function wrong(register: device.Register8) { device.out8(register, 0) }
''', rejection=True)
        self.compile("seed-wrong-port-width", header + '''
function wrong(port: device.Port8) { print(device.in32(port)) }
''', rejection=True)
        # Integer fit is a runtime contract, not compiler prevention. Compile
        # this control, but never execute its privileged port operation here.
        self.compile("seed-byte-fit-is-runtime", header + '''
function runtimeFit(port: device.Port8) { device.out8(port, 256) }
''')


def qemu_log(path, base_text):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", base_text):
        raise CheckFailure("--rtc-base must use YYYY-MM-DDTHH:MM:SS")
    try:
        base = datetime.strptime(base_text, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise CheckFailure("invalid RTC base: " + str(error)) from error
    if not 2000 <= base.year <= 2099:
        raise CheckFailure("RTC base is outside the frozen 2000..2099 year window")
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    start, passed = "OSDEV RTC START", "OSDEV RTC PASS"
    if lines.count(start) != 1 or lines.count(passed) != 1:
        raise CheckFailure("expected exactly one exact OSDEV RTC START and OSDEV RTC PASS")
    calendars = [line for line in lines if line.startswith("OSDEV RTC ") and line not in (start, passed)]
    if len(calendars) != 1:
        raise CheckFailure("expected exactly one RTC calendar serial line")
    if not lines.index(start) < lines.index(calendars[0]) < lines.index(passed):
        raise CheckFailure("expected RTC START, calendar, PASS in that order")
    found = re.fullmatch(r"OSDEV RTC (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)", calendars[0])
    if found is None:
        raise CheckFailure("malformed RTC calendar serial line")
    try:
        observed = datetime(*(int(value) for value in found.groups()), tzinfo=timezone.utc)
    except ValueError as error:
        raise CheckFailure("invalid RTC serial calendar: " + str(error)) from error
    elapsed = (observed - base).total_seconds()
    if not 0 <= elapsed <= 10:
        raise CheckFailure(f"RTC serial calendar is {elapsed:g}s from fixed base; required 0..10s")
    bad = re.compile(r"\b(?:error|errors|fail|failed|failure|panic|fatal|assertion)\b|"
                     r"(?:Address|UndefinedBehavior|Leak)Sanitizer|Minyar stopped:", re.IGNORECASE)
    for line in lines:
        if bad.search(line):
            raise CheckFailure("error in guest log: " + line)
    print(f"RTC serial calendar/marker passed (+{elapsed:g}s); guest exit is verified separately", flush=True)


def executable(value, label):
    selected = shutil.which(value) if value else None
    if selected is None:
        raise CheckFailure(f"set {label} to an existing executable (no builds are launched)")
    return str(Path(selected).resolve())


def positive_timeout(value):
    number = float(value)
    if not 0 < number <= 3600:
        raise argparse.ArgumentTypeError("timeout must be positive and at most 3600 seconds")
    return number


def main():
    flags = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))
    default_compiler = ROOT / ("build/minyarc-sanitize" if address_enabled(flags) else "build/minyarc")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=os.environ.get("MINYAR_TEST_COMPILER", str(default_compiler)))
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", ""))
    parser.add_argument("--group", action="append", choices=("decode", "reader", "seeds"))
    parser.add_argument("--compile-timeout", type=positive_timeout, default=120)
    parser.add_argument("--link-timeout", type=positive_timeout, default=120)
    parser.add_argument("--run-timeout", type=positive_timeout, default=30)
    parser.add_argument("--artifacts", type=Path, help="preserve an empty directory outside the source checkout")
    parser.add_argument("--qemu-log", type=Path)
    parser.add_argument("--rtc-base")
    parser.add_argument("--log-only", action="store_true", help="validate serial data only; proves no guest exit")
    args = parser.parse_args()
    if bool(args.qemu_log) != bool(args.rtc_base) or (args.log_only and not args.qemu_log):
        parser.error("--qemu-log and --rtc-base are required together; --log-only requires both")
    if sys.platform != "linux":
        raise CheckFailure("run this test on the BX Linux worker; laptop execution is not supported")
    if args.qemu_log:
        qemu_log(args.qemu_log, args.rtc_base)
    if args.log_only:
        return 0
    args.compiler = executable(args.compiler, "MINYAR_TEST_COMPILER/--compiler")
    args.clang = executable(args.clang, "MINYAR_TEST_CLANG/--clang")
    groups = set(args.group or ("decode", "reader", "seeds"))
    if args.artifacts:
        directory = args.artifacts.resolve()
        if directory == ROOT or ROOT in directory.parents:
            raise CheckFailure("generated artifacts must stay outside the source checkout")
        directory.mkdir(parents=True, exist_ok=True)
        if any(directory.iterdir()):
            raise CheckFailure("--artifacts directory must be empty")
    else:
        parent = Path(tempfile.gettempdir()).resolve()
        if parent == ROOT or ROOT in parent.parents:
            raise CheckFailure("temporary artifacts must stay outside the source checkout")
        directory = Path(tempfile.mkdtemp(prefix="minyar-rtc-oracle-", dir=parent))
    runner = Runner(directory, args, flags)
    passed = False
    try:
        decode = decode_cases()
        reads = read_cases()
        manifest = dict(experiment_started=EXPERIMENT_STARTED,
                        compiler=args.compiler, clang=args.clang, flags=flags,
                        groups=sorted(groups), decode_cases=len(decode), read_cases=len(reads),
                        rtc_sha256=hashlib.sha256((ROOT / "os/shared/rtc.min").read_bytes()).hexdigest(),
                        runtime_sha256=hashlib.sha256((ROOT / "runtime/minyar_runtime.c").read_bytes()).hexdigest(),
                        oracle="Python datetime plus independent scripted register transactions",
                        guest_exit_proven=False)
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if "seeds" in groups:
            runner.compiler_seeds()
            print("compiler seeds: 2 type rejections; byte-fit control compiles (runtime, not compile prevention)", flush=True)
        if groups & {"decode", "reader"}:
            runtime = runner.runtime()
            if "decode" in groups:
                runner.execute("decode", *decode_program(decode), runtime)
                print(f"decode: {len(decode)} independent calendar cases at O0/O2", flush=True)
            if "reader" in groups:
                runner.execute("reader", *reader_program(reads), runtime)
                print(f"reader: {len(reads)} exact trace/budget cases at O0/O2", flush=True)
        passed = True
        print("RTC hosted oracle passed; no hardware, QEMU-exit or development-speed claim", flush=True)
        return 0
    finally:
        if passed and not args.artifacts:
            shutil.rmtree(directory)
        else:
            print("RTC oracle artifacts: " + str(directory), file=sys.stderr, flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckFailure, OSError, UnicodeError, ValueError) as error:
        print("RTC oracle FAILED: " + str(error), file=sys.stderr, flush=True)
        raise SystemExit(1)
