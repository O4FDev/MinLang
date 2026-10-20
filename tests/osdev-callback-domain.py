#!/usr/bin/env python3
"""BX gate for the actual freestanding callback-domain header.

Host scenarios call only its explicit-ID binder. Its privileged physical CPU
provider is cross-compiled and inspected, never executed by this harness.
No compiler/runtime is built; pinned Clang is selected explicitly.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
IDS = (0, 1, 255, 256, 4294967295)
FOREIGN = ((0, 256), (1, 0), (255, 4294967295), (256, 0), (4294967295, 255))
LEVELS = ("-O0", "-O2")
TARGETS = (("x86_64-unknown-none-elf", 62, ("-march=x86-64-v2", "-mno-red-zone")),
           ("aarch64-unknown-none-elf", 183, ()))
LIMIT = 1024 * 1024
INVALID = "freestanding callback CPU identity is invalid."
ORIGINAL = "freestanding callbacks require their original CPU."
THREADED = "Freestanding callbacks require the single execution domain profile."

HOST_SOURCE = r'''
#include <stdatomic.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#ifndef MINYAR_THREADED
#define MINYAR_THREADED 0
#endif
static _Noreturn void minyar_stop(const char *message) {
    fprintf(stderr, "minyar_stop: %s\n", message);
    exit(72);
}
#include "freestanding/callback-domain.h"

static uint64_t argument(const char *text) {
    char *end;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno || end == text || *end || text[0] == '-') exit(75);
    return (uint64_t)value;
}

int main(int argc, char **argv) {
    if (argc < 3) return 75;
    uint64_t cpu = argument(argv[2]);
    long long first = minyar_freestanding_callback_domain(cpu);
    if (first <= 0 || (uint64_t)first != cpu + UINT64_C(1)) {
        fputs("binder returned the wrong domain\n", stderr);
        return 71;
    }
    if (!strcmp(argv[1], "same") && argc == 3) {
        long long second = minyar_freestanding_callback_domain(cpu);
        long long third = minyar_freestanding_callback_domain(cpu);
        if (first != second || second != third) return 71;
        printf("DOMAIN %" PRIu64 "\n", (uint64_t)first);
        return 0;
    }
    if (!strcmp(argv[1], "foreign") && argc == 4) {
        (void)minyar_freestanding_callback_domain(argument(argv[3]));
        fputs("foreign CPU was accepted\n", stderr);
        return 73;
    }
    return 75;
}
'''

PHYSICAL_SOURCE = r'''
#include <stdatomic.h>
#include <stdint.h>
#ifndef MINYAR_THREADED
#define MINYAR_THREADED 0
#endif
_Noreturn void minyar_stop(const char *message);
#include "freestanding/callback-domain.h"

long long osdev_callback_physical_probe(void) {
    return minyar_freestanding_callback_domain(minyar_freestanding_callback_cpu());
}
'''

HOST_SELECTION_SOURCE = '''
#ifdef MINYAR_FREESTANDING
#undef MINYAR_FREESTANDING
#endif
#define MINYAR_THREADED 0
#include "minyar_callbacks.h"
'''


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def elf_symbols(path, machine):
    """Read actual ELF64 little-endian section/symbol ABI, without nm tools."""
    data = path.read_bytes()
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("expected an ELF64 little-endian target object")
    kind, actual_machine = struct.unpack_from("<HH", data, 16)
    if kind != 1 or actual_machine != machine:
        raise ValueError("wrong object kind/target machine")
    section_offset = struct.unpack_from("<Q", data, 40)[0]
    entry_size, section_count = struct.unpack_from("<HH", data, 58)
    if entry_size != 64 or section_count == 0 or section_offset + section_count * 64 > len(data):
        raise ValueError("unsupported or truncated ELF section table")
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, section_offset + index * 64)
                for index in range(section_count)]
    if any(section[2] & 0x400 for section in sections):
        raise ValueError("ELF has SHF_TLS storage")
    symbols = []
    for section in sections:
        if section[1] not in (2, 11):
            continue
        offset, size, link, stride = section[4], section[5], section[6], section[9]
        if stride != 24 or size % stride or offset + size > len(data) or link >= len(sections):
            raise ValueError("invalid ELF symbol table")
        strings = sections[link]
        if strings[1] != 3 or strings[4] + strings[5] > len(data):
            raise ValueError("invalid ELF symbol string table")
        names = data[strings[4]:strings[4] + strings[5]]
        for index in range(size // stride):
            name, information, _, section_index, _, symbol_size = struct.unpack_from("<IBBHQQ", data, offset + index * stride)
            if name >= len(names):
                raise ValueError("invalid ELF symbol name")
            end = names.find(b"\0", name)
            if end < 0:
                raise ValueError("unterminated ELF symbol name")
            text = names[name:end].decode("utf-8", "replace")
            symbol_type = information & 15
            if symbol_type == 6:
                raise ValueError("ELF STT_TLS symbol: " + text)
            if re.search(r"__tls|__emutls|_tlv_|thread_pointer|tpidr", text, re.IGNORECASE):
                raise ValueError("ELF TLS/thread-pointer access symbol: " + text)
            if text.startswith(("__aarch64_cas", "__atomic_")):
                raise ValueError("unexpected outlined atomic dependency: " + text)
            symbols.append(dict(name=text, type=symbol_type, size=symbol_size, undefined=section_index == 0))
    if not any(symbol["name"] == "minyar_freestanding_callback_owner" and symbol["type"] == 1 for symbol in symbols):
        raise ValueError("actual callback owner object symbol is missing")
    if not any(symbol["name"] == "osdev_callback_physical_probe" and symbol["type"] == 2 for symbol in symbols):
        raise ValueError("physical provider probe function symbol is missing")
    return symbols


def ir_issues(path, target):
    source = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                       if not line.lstrip().startswith(";"))
    # Hide quoted message/attribute strings when inspecting LLVM keywords.
    code = re.sub(r'"(?:\\.|[^"\\])*"', '""', source)
    errors = []
    if re.search(r"\bthread_local\b|@llvm\.thread(?:local\.address|\.pointer)\b|@__tls|@__emutls", code):
        errors.append("LLVM has TLS storage or a TLS/thread-pointer intrinsic/access")
    if re.search(r"\btpidr(?:ro)?_el[01]\b|%[fg]s:", source, re.IGNORECASE):
        errors.append("LLVM inline assembly reads a thread-pointer/TLS register")
    owner = re.search(r"^@minyar_freestanding_callback_owner\s*=([^\n]+)", source, re.MULTILINE)
    if owner is None or not re.search(r"\bglobal\s+i64\s+0\b", owner[1]):
        errors.append("expected actual zero-initialized global 64-bit callback owner")
    if not re.search(r"^define\b[^\n]*@osdev_callback_physical_probe\(", source, re.MULTILINE):
        errors.append("actual physical-provider probe body missing")
    if target.startswith("x86_64"):
        for instruction in ("cpuid", "rdmsr"):
            if not re.search(r'\basm\b[^\n]*"' + instruction + r'"', source, re.IGNORECASE):
                errors.append("actual x86 physical provider lacks " + instruction)
    elif not re.search(r'\basm\b[^\n]*"mrs[^"\n]*\bmpidr_el1\b', source, re.IGNORECASE):
        errors.append("actual Arm physical provider lacks MPIDR_EL1 read")
    return errors


class Gate:
    def __init__(self, args, directory):
        self.args = args
        self.directory = directory
        self.commands = []
        self.checks = []
        self.symbols = {}
        self.environment = os.environ.copy()
        self.cross_environment = dict(self.environment)
        for name in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH", "SDKROOT"):
            self.cross_environment.pop(name, None)

    def invoke(self, phase, command, cross=False):
        identifier = len(self.commands) + 1
        stdout_path = self.directory / f"command-{identifier:03d}.stdout"
        stderr_path = self.directory / f"command-{identifier:03d}.stderr"
        started = time.monotonic_ns()
        timed_out = False
        process = None
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=self.args.root,
                                       env=self.cross_environment if cross else self.environment,
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                process.wait(timeout=self.args.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        captures = []
        oversized = False
        for path in (stdout_path, stderr_path):
            with path.open("rb") as stream:
                output = stream.read(LIMIT + 1)
            oversized |= len(output) > LIMIT
            captures.append(output[:LIMIT].decode("utf-8", "replace"))
        status = 124 if timed_out else process.returncode
        self.commands.append(dict(phase=phase, argv=command, status=status, timed_out=timed_out,
                                  oversized=oversized, elapsed_seconds=(time.monotonic_ns() - started) / 1e9,
                                  stdout=str(stdout_path), stderr=str(stderr_path)))
        return status, captures[0], captures[1], timed_out or oversized

    def check(self, label, passed, detail=""):
        self.checks.append(dict(label=label, passed=bool(passed), detail=detail))
        print(f"{label}: {'passed' if passed else 'FAILED'}", flush=True)
        if not passed and detail:
            print(detail[:6000], file=sys.stderr, flush=True)
        return bool(passed)

    def host(self, include):
        source = self.directory / "host-binder.c"
        source.write_text(HOST_SOURCE, encoding="utf-8")
        for level in LEVELS:
            executable = self.directory / ("host-" + level[1:])
            command = [self.args.clang, "-std=c11", level, "-Wno-unused-function", *include,
                       str(source), "-o", str(executable)]
            status, stdout, stderr, broken = self.invoke("host-build", command)
            if not self.check(level + " host binder build", not broken and status == 0 and executable.is_file(), stdout + stderr):
                continue
            for cpu in IDS:
                status, stdout, stderr, broken = self.invoke("host-same", [str(executable), "same", str(cpu)])
                self.check(f"{level} CPU {cpu}: positive stable domain {cpu + 1}",
                           not broken and status == 0 and stdout == f"DOMAIN {cpu + 1}\n" and not stderr,
                           f"status={status}\n{stdout}{stderr}")
            for owner, other in FOREIGN:
                status, stdout, stderr, broken = self.invoke("host-foreign", [str(executable), "foreign", str(owner), str(other)])
                self.check(f"{level} CPU {owner} rejects CPU {other}",
                           not broken and status == 72 and not stdout and stderr == "minyar_stop: " + ORIGINAL + "\n",
                           f"status={status}\n{stdout}{stderr}")
            status, stdout, stderr, broken = self.invoke("host-invalid", [str(executable), "same", "4294967296"])
            self.check(level + " CPU UINT32_MAX+1 rejected",
                       not broken and status == 72 and not stdout and stderr == "minyar_stop: " + INVALID + "\n",
                       f"status={status}\n{stdout}{stderr}")

    def hosted_tls_structure(self, include):
        source = self.directory / "host-selection.c"
        source.write_text(HOST_SELECTION_SOURCE, encoding="utf-8")
        selected = self.directory / "host-selection.i"
        status, stdout, stderr, broken = self.invoke("host-selection-preprocess",
            [self.args.clang, "-std=c11", "-E", "-P", *include, str(source), "-o", str(selected)])
        if not self.check("hosted profile preprocessing", not broken and status == 0 and selected.is_file(), stdout + stderr):
            return
        text = selected.read_text(encoding="utf-8")
        tls = bool(re.search(r"static\s+_Thread_local\s+uint64_t\s+minyar_callback_current_domain\s*;", text))
        self.check("hosted profile retains actual TLS declaration (structural only)",
                   tls and "minyar_freestanding_callback_domain" not in text,
                   "hosted TLS/bare-provider selection changed; this is not a host cross-domain execution test")

    def cross(self, include, resource, shim):
        source = self.directory / "physical-probe.c"
        source.write_text(PHYSICAL_SOURCE, encoding="utf-8")
        common = ["-std=c11", "-ffreestanding", "-fno-builtin", "-nostdinc",
                  "-isystem", str(resource), "-isystem", str(shim), *include,
                  "-fno-stack-protector", "-fno-pic", "-Wno-unused-function"]
        for target, machine, cpu in TARGETS:
            for level in LEVELS:
                label = target + " " + level
                stem = self.directory / (target + "-" + level[1:])
                llvm, obj = stem.with_suffix(".ll"), stem.with_suffix(".o")
                flags = [self.args.clang, "--target=" + target, *cpu, level, *common]
                status, stdout, stderr, broken = self.invoke("cross-ir", [*flags, "-S", "-emit-llvm", str(source), "-o", str(llvm)], True)
                ir_ok = self.check(label + " actual-header LLVM compile", not broken and status == 0 and llvm.is_file(), stdout + stderr)
                if ir_ok:
                    errors = ir_issues(llvm, target)
                    self.check(label + " LLVM has global owner, physical probe and no TLS", not errors, "\n".join(errors))
                status, stdout, stderr, broken = self.invoke("cross-object", [*flags, "-c", str(source), "-o", str(obj)], True)
                object_ok = self.check(label + " actual-header object compile", not broken and status == 0 and obj.is_file(), stdout + stderr)
                if object_ok:
                    try:
                        self.symbols[label] = elf_symbols(obj, machine)
                    except (ValueError, struct.error) as error:
                        self.check(label + " actual ELF has no TLS or outlined atomics", False, str(error))
                    else:
                        self.check(label + " actual ELF has no TLS or outlined atomics", True)
                if not ir_ok or not object_ok:
                    self.check(label + " threaded rejection", False, "blocked by failed nonthreaded compile control")
                    continue
                rejected = self.directory / (target + "-" + level[1:] + "-threaded.o")
                status, stdout, stderr, broken = self.invoke("cross-threaded-reject",
                    [*flags, "-DMINYAR_THREADED=1", "-c", str(source), "-o", str(rejected)], True)
                self.check(label + " MINYAR_THREADED=1 rejected",
                           not broken and status == 1 and "error:" in stderr and THREADED in stderr and
                           "file not found" not in stderr and not rejected.exists(), f"status={status}\n{stdout}{stderr}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG"), help="pinned Clang executable (or MINYAR_TEST_CLANG)")
    parser.add_argument("--root", type=Path, default=ROOT, help="candidate root; defaults to this script's checkout")
    parser.add_argument("--output-dir", type=Path, help="new/empty evidence directory, retained on success and failure")
    parser.add_argument("--timeout", type=int, default=60, help="per-command seconds, 1..60")
    args = parser.parse_args()
    if not args.clang or not shutil.which(args.clang):
        parser.error("select the pinned Clang executable with --clang or MINYAR_TEST_CLANG")
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be in 1..60")
    args.clang = str(Path(shutil.which(args.clang)).resolve())
    args.root = args.root.resolve()
    directory = (args.output_dir or Path(tempfile.mkdtemp(prefix="osdev-callback-domain-"))).resolve()
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        parser.error("--output-dir must be new or empty")
    directory.mkdir(parents=True, exist_ok=True)
    gate = Gate(args, directory)
    started = time.monotonic_ns()
    metadata = {}
    status = 1
    try:
        header = args.root / "runtime/freestanding/callback-domain.h"
        callbacks = args.root / "runtime/minyar_callbacks.h"
        metadata = dict(clang=args.clang, clang_sha256=digest(Path(args.clang)),
                        header=str(header), header_sha256=digest(header),
                        callbacks=str(callbacks), callbacks_sha256=digest(callbacks),
                        host_hardware_provider_executed=False)
        include = ["-iquote", str(args.root / "runtime")]
        query, stdout, stderr, broken = gate.invoke("resource-query", [args.clang, "-print-resource-dir"], True)
        if not gate.check("pinned Clang resource query", not broken and query == 0 and bool(stdout.strip()), stderr):
            raise ValueError("cannot resolve pinned Clang resource headers")
        resource = Path(stdout.strip()) / "include"
        shim = args.root / "runtime/freestanding/include"
        if not resource.is_dir() or not shim.is_dir():
            raise ValueError("missing actual freestanding shim or Clang resource includes")
        metadata.update(resource_include=str(resource), shim_include=str(shim))
        gate.host(include)
        gate.hosted_tls_structure(include)
        gate.cross(include, resource, shim)
        gate.check("candidate header sources unchanged", digest(header) == metadata["header_sha256"] and
                   digest(callbacks) == metadata["callbacks_sha256"])
        status = 0 if gate.checks and all(check["passed"] for check in gate.checks) else 1
    except (OSError, ValueError, struct.error) as error:
        gate.check("harness configuration/artifact error", False, str(error))
        status = 2
    except KeyboardInterrupt:
        gate.check("harness interrupted", False)
        status = 130
    passed = sum(check["passed"] for check in gate.checks)
    counts = {phase: sum(command["phase"] == phase for command in gate.commands)
              for phase in sorted({command["phase"] for command in gate.commands})}
    result = dict(status=status, metadata=metadata, checks=gate.checks, commands=gate.commands,
                  object_symbols=gate.symbols, command_counts=counts,
                  elapsed_seconds=(time.monotonic_ns() - started) / 1e9,
                  limitations=["No actual CPUID/RDMSR/MPIDR provider execution, SMP race or guest proof.",
                               "No-TLS checks cover emitted probe IR/ELF, not every runtime dependency.",
                               "Hosted TLS check is structural preprocessing, not host cross-domain execution proof."])
    (directory / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"callback domain: {passed}/{len(gate.checks)} checks passed; {len(gate.commands)} commands; "
          f"status={status}; artifacts: {directory}", flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
