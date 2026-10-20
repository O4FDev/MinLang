#!/usr/bin/env python3
"""Linux/BX unit regression for the extracted production freestanding allocator.

This isolates allocator code with a fixed hosted heap. It does not exercise the
whole freestanding runtime, linker script, guest startup or hardware allocator.
Set MINYAR_TEST_CLANG to the pinned compiler; no compiler is built by this test.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
START = "extern unsigned char __heap_start[], __heap_end[];"
END = "long long minyar_freestanding_heap_used(void) { return (long long)heap_used; }"
BEFORE_SHA256 = "8494540379c7e724f6582b4c7c28ba18c18a738ffc4775b067147002b4a7babc"
SIZE_MAX = 2**64 - 1
HEADER_BYTES = 16
HEAP_BYTES = 512
# A mathematical capacity table, not the production C mask/shift loop.
CAPACITIES = tuple((exponent, 2**exponent) for exponent in range(5, 40))
SMALL_REQUESTS = (0, 1, 15, 16, 17, 47, 48, 49, 111, 112, 113, 239,
                  240, 241, 495, 496, 497, 512, 513)


def expected_class(request):
    total = request + HEADER_BYTES  # Python integers cannot wrap.
    return next((exponent for exponent, capacity in CAPACITIES if total <= capacity), 40)


def class_cases():
    overflow = (SIZE_MAX, SIZE_MAX - 1, SIZE_MAX - 15)
    boundaries = {0, 1, 15, 16, 17, SIZE_MAX - 16, SIZE_MAX - 17}
    for _, capacity in CAPACITIES:
        boundaries.update((capacity - HEADER_BYTES - 1,
                           capacity - HEADER_BYTES,
                           capacity - HEADER_BYTES + 1))
    # Unsupported classes and shifts near the width of size_t are separate from
    # header-addition wrap. The old source must not turn either into tiny blocks.
    boundaries.update((2**40 - 16, 2**40 - 15, 2**63 - 16,
                       2**63 - 15, 2**63, 2**64 - 32))
    return overflow, tuple(sorted(boundaries))


def extract(source):
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("allocator extraction requires each explicit boundary exactly once")
    first = source.index(START)
    last = source.index(END) + len(END)
    if last <= first:
        raise ValueError("allocator extraction boundaries are reversed")
    section = source[first:last] + "\n"
    replacement = (
        f"_Alignas(64) static unsigned char osdev_scratch[{HEAP_BYTES + 128}];\n"
        "#define __heap_start (osdev_scratch + 64)\n"
        f"#define __heap_end (osdev_scratch + 64 + {HEAP_BYTES})"
    )
    # This is the only textual substitution inside the production section.
    return section, section.replace(START, replacement, 1)


C_PROBES = r"""
#undef malloc
#undef free
#undef calloc
#undef realloc
#undef heap_used
#undef minyar_freestanding_heap_used

#define REQUIRE(condition, message) do { if (!(condition)) { \
    fprintf(stderr, "FAIL %s at line %d\n", message, __LINE__); return 1; \
} } while (0)

static void reset_heap(void) {
    memset(osdev_scratch, 0xa5, sizeof(osdev_scratch));
    memset(free_blocks, 0, sizeof(free_blocks));
    heap_next = NULL;
    osdev_heap_live_bytes = 0;
}

static int guards_ok(void) {
    for (size_t i = 0; i < 64; i++)
        if (osdev_scratch[i] != 0xa5 ||
            osdev_scratch[64 + OSDEV_HEAP_BYTES + i] != 0xa5) return 0;
    return 1;
}

static int allocation_accounting(void) {
    const size_t requests[] = { OSDEV_SMALL_REQUESTS };
    for (size_t i = 0; i < sizeof(requests) / sizeof(requests[0]); i++) {
        reset_heap();
        unsigned char *pointer = osdev_heap_malloc(requests[i]);
        long long charged = osdev_heap_used();
        if (pointer) {
            REQUIRE((uintptr_t)pointer % 16 == 0, "returned pointer alignment");
            memset(pointer, 0x31, requests[i]);
        }
        osdev_heap_free(pointer);
        printf("ALLOC %zu %d %lld %lld\n", requests[i], pointer != NULL,
               charged, osdev_heap_used());
        REQUIRE(guards_ok(), "allocation scratch guard");
    }
    return 0;
}

static int operation_checks(void) {
    reset_heap();
    const size_t oversized[] = {
        SIZE_MAX, SIZE_MAX - 15, SIZE_MAX - 16,
        UINT64_C(549755813873), UINT64_C(1099511627776)
    };
    for (size_t i = 0; i < sizeof(oversized) / sizeof(oversized[0]); i++) {
        REQUIRE(osdev_heap_malloc(oversized[i]) == NULL,
                "oversized malloc returned storage");
        REQUIRE(osdev_heap_used() == 0, "oversized malloc changed accounting");
        REQUIRE(guards_ok(), "oversized malloc scratch guard");
    }
    REQUIRE(osdev_heap_calloc(SIZE_MAX, 2) == NULL, "calloc product overflow");
    REQUIRE(osdev_heap_calloc(SIZE_MAX / 2 + 1, 2) == NULL,
            "calloc boundary product overflow");
    REQUIRE(osdev_heap_calloc(1, SIZE_MAX) == NULL, "calloc allocator header overflow");
    unsigned char *zero = osdev_heap_calloc(17, 3);
    REQUIRE(zero != NULL, "small calloc");
    for (size_t i = 0; i < 51; i++) REQUIRE(zero[i] == 0, "calloc did not zero data");
    osdev_heap_free(zero);
    REQUIRE(osdev_heap_used() == 0, "calloc/free accounting");

    reset_heap();
    unsigned char *old = osdev_heap_malloc(64);
    REQUIRE(old != NULL, "realloc setup");
    for (size_t i = 0; i < 64; i++) old[i] = (unsigned char)(i ^ 0x5a);
    long long before = osdev_heap_used();
    for (size_t i = 0; i < sizeof(oversized) / sizeof(oversized[0]); i++) {
        REQUIRE(osdev_heap_realloc(old, oversized[i]) == NULL,
                "oversized realloc returned storage");
        REQUIRE(osdev_heap_used() == before, "failed realloc changed old allocation");
        for (size_t j = 0; j < 64; j++)
            REQUIRE(old[j] == (unsigned char)(j ^ 0x5a), "failed realloc lost payload");
    }
    REQUIRE(osdev_heap_realloc(old, 8) == old, "in-capacity realloc moved block");
    unsigned char *grown = osdev_heap_realloc(old, 200);
    REQUIRE(grown != NULL, "realloc growth");
    for (size_t i = 0; i < 64; i++)
        REQUIRE(grown[i] == (unsigned char)(i ^ 0x5a), "realloc growth lost payload");
    osdev_heap_free(grown);
    REQUIRE(osdev_heap_used() == 0 && guards_ok(), "realloc final accounting/guard");
    REQUIRE(osdev_heap_realloc(NULL, SIZE_MAX) == NULL, "realloc NULL oversized");
    old = osdev_heap_realloc(NULL, 1);
    REQUIRE(old != NULL, "realloc NULL allocation");
    osdev_heap_free(old);

    reset_heap();
    unsigned char *first = osdev_heap_malloc(1);
    unsigned char *second = osdev_heap_malloc(1);
    REQUIRE(first && second && first != second, "two live allocations alias");
    second[0] = 0x71;
    osdev_heap_free(first);
    unsigned char *reused = osdev_heap_malloc(1);
    REQUIRE(reused == first && second[0] == 0x71, "freelist reuse/payload isolation");
    osdev_heap_free(reused);
    osdev_heap_free(second);
    osdev_heap_free(NULL);
    REQUIRE(osdev_heap_used() == 0 && guards_ok(), "reuse accounting/guard");

    reset_heap();
    unsigned char *blocks[OSDEV_TINY_COUNT];
    for (size_t i = 0; i < OSDEV_TINY_COUNT; i++) {
        blocks[i] = osdev_heap_malloc(16);
        REQUIRE(blocks[i] != NULL, "tiny heap exhausted too early");
        for (size_t j = 0; j < i; j++) REQUIRE(blocks[i] != blocks[j], "live block reused");
        memset(blocks[i], (int)(i + 1), 16);
    }
    REQUIRE(osdev_heap_malloc(16) == NULL, "tiny heap failed to exhaust");
    REQUIRE(osdev_heap_used() == OSDEV_HEAP_BYTES, "tiny heap charged bytes");
    for (size_t i = 0; i < OSDEV_TINY_COUNT; i++) {
        for (size_t j = 0; j < 16; j++)
            REQUIRE(blocks[i][j] == (unsigned char)(i + 1), "exhaustion corrupted live payload");
        osdev_heap_free(blocks[i]);
    }
    REQUIRE(osdev_heap_used() == 0, "tiny heap frees");
    for (size_t i = 0; i < OSDEV_TINY_COUNT; i++) {
        blocks[i] = osdev_heap_malloc(16);
        REQUIRE(blocks[i] != NULL, "freelist cannot reuse exhausted heap");
    }
    REQUIRE(osdev_heap_malloc(16) == NULL, "reuse over-allocated tiny heap");
    for (size_t i = 0; i < OSDEV_TINY_COUNT; i++) osdev_heap_free(blocks[i]);
    REQUIRE(osdev_heap_used() == 0 && guards_ok(), "exhaustion final accounting/guard");
    puts("OSDEV ALLOCATOR PASS");
    return 0;
}

int main(int argc, char **argv) {
    _Static_assert(sizeof(size_t) == 8, "allocator oracle requires a 64-bit BX host");
    if (argc >= 2 && strcmp(argv[1], "classes") == 0) {
        for (int i = 2; i < argc; i++) {
            char *after = NULL;
            errno = 0;
            uintmax_t input = strtoumax(argv[i], &after, 10);
            REQUIRE(!errno && after && !*after && input <= SIZE_MAX, "invalid class input");
            int actual = class_for((size_t)input);
            printf("CLASS %" PRIuMAX " %d\n", input, actual);
            fflush(stdout);
        }
        return 0;
    }
    REQUIRE(argc == 2 && strcmp(argv[1], "operations") == 0, "unknown probe mode");
    if (allocation_accounting()) return 1;
    return operation_checks();
}
"""


def probe_source(section):
    prefix = """#include <stddef.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#define malloc osdev_heap_malloc
#define free osdev_heap_free
#define calloc osdev_heap_calloc
#define realloc osdev_heap_realloc
#define heap_used osdev_heap_live_bytes
#define minyar_freestanding_heap_used osdev_heap_used
"""
    defines = (
        f"\n#define OSDEV_HEAP_BYTES {HEAP_BYTES}\n"
        f"#define OSDEV_TINY_COUNT {HEAP_BYTES // CAPACITIES[0][1]}\n"
        "#define OSDEV_SMALL_REQUESTS " + ", ".join(map(str, SMALL_REQUESTS)) + "\n"
    )
    return prefix + section + defines + C_PROBES


def invoke(command, log, timeout, environment):
    started = time.monotonic()
    status = None
    with log.open("wb") as output:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            status = 124
            output.write(f"\nTIMEOUT after {timeout:g}s\n".encode())
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
    return {"command": command, "status": status,
            "seconds": time.monotonic() - started, "log": str(log)}


def class_errors(output, requests):
    rows = [tuple(map(int, row)) for row in
            re.findall(r"^CLASS ([0-9]+) (-?[0-9]+)$", output, re.MULTILINE)]
    expected = [(request, expected_class(request)) for request in requests]
    if rows == expected:
        return []
    mismatches = [f"class({request}): expected {want}, got {got}"
                  for (request, got), (_, want) in zip(rows, expected) if got != want]
    if len(rows) != len(expected):
        mismatches.append(f"class row count: expected {len(expected)}, got {len(rows)}")
    if [row[0] for row in rows] != list(requests):
        mismatches.append("class inputs/output order changed")
    return mismatches or ["class oracle mismatch"]


def operation_errors(output):
    rows = [tuple(map(int, row)) for row in
            re.findall(r"^ALLOC ([0-9]+) ([01]) ([0-9]+) ([0-9]+)$", output, re.MULTILINE)]
    expected = []
    for request in SMALL_REQUESTS:
        exponent = expected_class(request)
        charged = 2**exponent
        fits = exponent < 40 and charged <= HEAP_BYTES
        expected.append((request, int(fits), charged if fits else 0, 0))
    errors = []
    if rows != expected:
        errors.append(f"allocation accounting oracle mismatch: expected {expected}, got {rows}")
    if output.splitlines().count("OSDEV ALLOCATOR PASS") != 1:
        errors.append("missing unique operation success marker")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "runtime/freestanding/freestanding.c")
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG"))
    parser.add_argument("--artifacts", type=Path, help="parent directory for retained run artifacts")
    parser.add_argument("--keep", action="store_true", help="retain temporary artifacts on success")
    parser.add_argument("--timeout", type=float, default=10, help="deadline per executed probe")
    parser.add_argument("--compile-timeout", type=float, default=60)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("run this harness on BX/Linux; laptop execution is unsupported")
    if not args.clang or not shutil.which(args.clang):
        parser.error("select the pinned Clang with --clang or MINYAR_TEST_CLANG")
    if not (0 < args.timeout <= 600 and 0 < args.compile_timeout <= 600):
        parser.error("deadlines must be finite and in 0..600 seconds")
    clang = str(Path(shutil.which(args.clang)).resolve())
    source_path = args.source.resolve(strict=True)
    raw = source_path.read_bytes()
    original, isolated = extract(raw.decode("utf-8"))
    if args.artifacts:
        args.artifacts.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="osdev-allocator-", dir=args.artifacts))
    manifest = {
        "source": str(source_path), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "known_before_sha256": BEFORE_SHA256,
        "is_known_before": hashlib.sha256(raw).hexdigest() == BEFORE_SHA256,
        "extracted_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "clang": clang, "heap_bytes": HEAP_BYTES, "header_bytes": HEADER_BYTES,
        "capacities": CAPACITIES, "results": [],
        "limitation": "extracted hosted allocator unit; no whole guest/startup/ABI proof",
    }
    failed = False
    try:
        (directory / "allocator-production.c").write_text(original, encoding="utf-8")
        probe = directory / "allocator-probe.c"
        probe.write_text(probe_source(isolated), encoding="utf-8")
        overflow, boundaries = class_cases()
        (directory / "class-oracle.json").write_text(json.dumps(
            {name: [(value, expected_class(value)) for value in values]
             for name, values in (("header-overflow", overflow), ("boundaries", boundaries))},
            indent=2) + "\n", encoding="utf-8")
        environment = os.environ.copy()
        for name in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH", "SDKROOT"):
            environment.pop(name, None)
        environment["UBSAN_OPTIONS"] = ":".join(filter(None, (
            environment.get("UBSAN_OPTIONS", ""), "halt_on_error=1", "print_stacktrace=1")))
        extra = shlex.split(environment.get("MINYAR_TEST_LINK_FLAGS", ""))

        def run(label, command, timeout, oracle=None):
            nonlocal failed
            result = invoke(command, directory / f"{label}.log", timeout, environment)
            output = Path(result["log"]).read_text(encoding="utf-8", errors="replace")
            result["label"] = label
            result["oracle_errors"] = oracle(output) if oracle else []
            result["passed"] = result["status"] == 0 and not result["oracle_errors"]
            failed = failed or not result["passed"]
            manifest["results"].append(result)
            print(f"{label}: {'PASS' if result['passed'] else 'FAIL'} "
                  f"(status {result['status']}, {result['seconds']:.2f}s)", flush=True)
            if not result["passed"]:
                print("command: " + shlex.join(command), file=sys.stderr)
                for error in result["oracle_errors"]:
                    print(error, file=sys.stderr)
                print(output[-6000:], file=sys.stderr)
            return result["passed"]

        if run("clang-version", [clang, "--version"], args.compile_timeout,
               lambda output: [] if re.search(r"\bclang version\s", output, re.IGNORECASE)
               else ["selected compiler did not identify itself as Clang"]):
            for optimization in ("O0", "O2"):
                for sanitized in (False, True):
                    profile = optimization + ("-ubsan" if sanitized else "")
                    executable = directory / profile
                    flags = ["-std=c11", f"-{optimization}", "-g", "-Wall", "-Wextra"]
                    if sanitized:
                        flags += ["-fsanitize=undefined", "-fno-sanitize-recover=undefined"]
                    command = [clang, *flags, str(probe), *extra, "-o", str(executable)]
                    if not run(profile + "-compile", command, args.compile_timeout):
                        continue
                    for name, values in (("header-overflow", overflow), ("boundaries", boundaries)):
                        run(profile + "-" + name,
                            [str(executable), "classes", *map(str, values)], args.timeout,
                            lambda output, values=values: class_errors(output, values))
                    run(profile + "-operations", [str(executable), "operations"],
                        args.timeout, operation_errors)
    finally:
        manifest["passed"] = not failed and len(manifest["results"]) == 17
        (directory / "results.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        retain = args.keep or args.artifacts is not None or not manifest["passed"]
        if retain:
            print(f"allocator artifacts: {directory}", flush=True)
        else:
            shutil.rmtree(directory)
    if not manifest["passed"]:
        print("osdev allocator: FAILED; inspect retained logs and oracle", file=sys.stderr)
        return 1
    print("osdev allocator: 4 profiles passed (O0/O2, each plain and UBSan)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"osdev allocator: {error}", file=sys.stderr)
        raise SystemExit(2)
