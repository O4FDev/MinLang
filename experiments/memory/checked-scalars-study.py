#!/usr/bin/env python3
"""Independent scalar oracles, allocation contracts, and checked C++ comparisons.

Correctness runs also instrument the generated LLVM. --measure times only the
selected function with setup and complete teardown outside its timer. Generated
compiler IR stays unchanged; its ordinary native package ABI starts the driver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
from llvm_sanitizer import prepare_llvm_for_link
from measurement_stats import paired_cpu_ratio_summary

KINDS = ("shift", "character", "float", "abs-clamp")
FUNCTIONS = (
    "checkedScalarShift",
    "checkedScalarCharacter",
    "checkedScalarFloat",
    "checkedScalarAbsClamp",
)


def signed_integer(value: int) -> int:
    value &= (1 << 64) - 1
    return value - (1 << 64) if value >= 1 << 63 else value


def oracle(kind: str, count: int, seed: int) -> int:
    if kind not in KINDS:
        raise ValueError(f"unknown scalar workload: {kind}")
    state, total = seed, 0
    for _ in range(count):
        if kind == "shift":
            amount = state & 31
            state = (
                signed_integer(state << amount) ^ (state >> (31 - amount))
            ) & 2147483647
            state = (state + 17) & 2147483647
            total = signed_integer(total + state)
            continue
        state = (state * 17 + 23) % 1000003
        if kind == "character":
            total = (total + state % 55296) % 1000003
        elif kind == "float":
            # state - 500001 is an exact small integer and division by four is
            # exact in binary64. Python int truncates toward zero independently
            # of the fixture's Float conversion lowering.
            total = signed_integer(total + int((state - 500001) / 4))
        elif kind == "abs-clamp":
            total = signed_integer(total + min(abs(state - 500001), 250000))
        else:
            raise ValueError(f"unknown scalar workload: {kind}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--samples", type=int, default=31)
    parser.add_argument("--count", type=int, default=5000000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cc", default="clang")
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--compiler", type=Path, default=ROOT / "build/minyarc")
    args = parser.parse_args()
    if not 3 <= args.samples <= 101 or not 0 < args.count <= 100000000:
        parser.error("samples must be 3..101 and count must be 1..100000000")
    work = Path(tempfile.mkdtemp(prefix="minyar-checked-scalars-"))
    commands = []
    native_normalizations = []
    print(work, flush=True)

    def run(command, label, env=None):
        command = [str(item) for item in command]
        observation = {"label": label, "argv": command, "returncode": None}
        commands.append(observation)
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                capture_output=True,
                env=env,
                timeout=240,
            )
        except subprocess.TimeoutExpired as error:
            observation["error"] = "timeout"
            output = b"".join(
                part.encode() if isinstance(part, str) else part or b""
                for part in (error.stdout, error.stderr)
            )
            (work / f"{label}.log").write_bytes(output)
            raise
        except OSError as error:
            observation["error"] = str(error)
            (work / f"{label}.log").write_text(str(error))
            raise
        observation["returncode"] = completed.returncode
        (work / f"{label}.log").write_text(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError(f"{label} failed: {completed.stdout}{completed.stderr}")
        return completed

    compiler = args.compiler.resolve()
    sources = [
        "compiler/compiler.min",
        "runtime/minyar_runtime.c",
        *(
            str(path.relative_to(ROOT))
            for path in sorted((ROOT / "runtime").glob("*.h"))
        ),
        "experiments/memory/checked-scalars.min",
        "experiments/memory/checked-scalars-driver.c",
        "experiments/memory/checked-scalars-cpp.cpp",
        "experiments/memory/checked-scalars-study.py",
        "experiments/memory/measurement_stats.py",
        "tests/llvm_sanitizer.py",
        "tests/llvm_symbols.h",
    ]
    result = {
        "directory": str(work),
        "mode": "measurement" if args.measure else "correctness",
        "compiler_executable": str(compiler),
        "allocation_monitoring": not args.measure,
        "compiler_sha256": None,
        "generated_llvm_sha256": None,
        "status": "running",
        "source_sha256": {
            source: hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
            for source in sources
        },
        "commands": commands,
        "native_ir_normalizations": native_normalizations,
        "configurations": {},
        "limitations": [
            "Only the selected function is timed; setup and complete teardown are outside timing.",
            "Workloads exercise shifts, Unicode scalar conversion, Float projection, and amplitude clamping.",
            "C++ retains corresponding overflow, shift, Unicode, conversion, and clamp checks.",
            "C++20 bit_cast and unsigned arithmetic define wrapping additions and left shifts.",
            "Allocation monitors count runtime allocator operations, with an independent live allocation control.",
            "Bootstrap intervals resample observed pairs as independent; host trends require separate analysis.",
            "Local measurements do not establish universal performance or hard deadlines.",
        ],
    }
    report_destination = args.output or work / "results.json"
    try:
        result["compiler_sha256"] = hashlib.sha256(compiler.read_bytes()).hexdigest()
        ir = work / "fixture.ll"
        run([compiler, HERE / "checked-scalars.min", ir], "compile-fixture")
        result["generated_llvm_sha256"] = hashlib.sha256(ir.read_bytes()).hexdigest()
        source_ir = ir.read_text()
        for name in FUNCTIONS:
            body = re.search(
                rf"^define [^\n]* @{re.escape('.minyar.fn.' + name)}\(.*?^}}",
                source_ir,
                re.M | re.S,
            )
            assert body and "@minyar_rc_" not in body.group(), name
        # The normal generated entry point calls the driver through a native body.
        assert "@minyar_checked_scalars_runScalarStudy(" in source_ir
        configurations = (
            [
                ("system", "-O2", False, False),
                ("system-lto", "-O2", False, True),
                ("eager", "-O2", False, False),
                ("eager-lto", "-O2", False, True),
                ("bounded-lto", "-O2", True, True),
            ]
            if args.measure
            else [
                ("system-o2", "-O2", False, False),
                ("eager-o0", "-O0", False, False),
                ("eager-o2", "-O2", False, False),
                ("bounded-o2", "-O2", True, False),
                ("eager-sanitize", "-O1", False, False),
                ("bounded-sanitize", "-O1", True, False),
            ]
        )
        executables = {}
        for name, optimization, bounded, lto in configurations:
            flags = [optimization, "-Wno-override-module"]
            sanitize = name.endswith("sanitize")
            if sanitize:
                flags += [
                    "-g",
                    "-fsanitize=address,undefined",
                    "-fno-omit-frame-pointer",
                ]
            link_ir = ir
            if sanitize:
                link_ir = work / f"{name}-fixture.ll"
                link_ir.write_bytes(ir.read_bytes())
                prepare_llvm_for_link(link_ir, flags)
            defines = ["-DMINYAR_BOUNDED_HEAP=1"] if bounded else []
            if name.startswith("system"):
                defines += ["-DMINYAR_SYSTEM_HEAP=1"]
            if not args.measure:
                defines += ["-DMINYAR_SCALAR_ACCOUNTING=1"]
            driver, cpp = work / f"{name}-driver.o", work / f"{name}-cpp.o"
            for native_compiler, source, destination, language_flags in (
                (args.cc, HERE / "checked-scalars-driver.c", driver, []),
                (args.cxx, HERE / "checked-scalars-cpp.cpp", cpp, ["-std=c++20"]),
            ):
                native_flags = [*flags, *language_flags]
                if lto:
                    native_ir = destination.with_suffix(".ll")
                    run(
                        [
                            native_compiler,
                            *native_flags,
                            *defines,
                            "-S",
                            "-emit-llvm",
                            source,
                            "-o",
                            native_ir,
                        ],
                        f"{name}-{source.stem}-ir",
                    )
                    # Use the generated Minyar module's generic target attributes
                    # for both native sources, as in the critical-path comparison.
                    before = native_ir.read_text()
                    before_path = native_ir.with_suffix(".before-normalization.ll")
                    before_path.write_text(before)
                    native_source = re.sub(
                        r'"(?:target-cpu|target-features|tune-cpu)"="[^"]*" ?',
                        "",
                        before,
                    )
                    # C asm aliases suppress target mangling (LLVM \01).
                    # Canonical names resolve to the unchanged language IR.
                    alias_pattern = r'@"\\01_?(\.minyar\.fn\.([A-Za-z0-9_]+))"'
                    aliases = re.findall(alias_pattern, native_source)
                    expected_aliases = (
                        set(FUNCTIONS) if source.suffix == ".c" else set()
                    )
                    assert {name for _, name in aliases} == expected_aliases, (
                        source,
                        aliases,
                    )
                    native_source, replaced = re.subn(
                        alias_pattern, r"@\1", native_source
                    )
                    assert replaced == len(aliases)
                    native_ir.write_text(native_source)
                    native_normalizations.append(
                        {
                            "before": str(before_path),
                            "after": str(native_ir),
                            "before_sha256": hashlib.sha256(
                                before.encode()
                            ).hexdigest(),
                            "after_sha256": hashlib.sha256(
                                native_source.encode()
                            ).hexdigest(),
                            "alias_replacements": replaced,
                            "alias_names": sorted(expected_aliases),
                            "method": "Remove generic target attributes and canonicalize only C asm language aliases for LLVM LTO resolution.",
                        }
                    )
                    run(
                        [
                            native_compiler,
                            *flags,
                            "-flto",
                            "-c",
                            native_ir,
                            "-o",
                            destination,
                        ],
                        f"{name}-{source.stem}-object",
                    )
                else:
                    run(
                        [
                            native_compiler,
                            *native_flags,
                            *defines,
                            "-c",
                            source,
                            "-o",
                            destination,
                        ],
                        f"{name}-{source.stem}-object",
                    )
            executable = work / name
            run(
                [
                    args.cxx,
                    *flags,
                    *(["-flto"] if lto else []),
                    link_ir,
                    driver,
                    cpp,
                    "-o",
                    executable,
                ],
                f"{name}-link",
            )
            executables[name] = executable

        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0")
        if args.measure:
            seed = 271828
            expected = {kind: oracle(kind, args.count, seed) for kind in KINDS}
            result.update(count=args.count, sample_pairs=args.samples, seed=seed)
            for name, executable in executables.items():
                entries = result["configurations"][name] = {}
                for kind in KINDS:
                    samples = {"cpp": [], "minyar": []}
                    warmup = {}
                    entries[kind] = {"samples": samples, "warmup_samples": warmup}
                    for index in range(args.samples + 1):
                        for language in (
                            ("cpp", "minyar") if index % 2 else ("minyar", "cpp")
                        ):
                            completed = run(
                                [executable, language, kind, args.count, seed],
                                f"{name}-{kind}-{language}-{index}",
                                env,
                            )
                            row = json.loads(completed.stdout)
                            if index:
                                samples[language].append(row)
                            else:
                                warmup[language] = row
                            assert row["result"] == expected[kind], (
                                name,
                                kind,
                                language,
                                row,
                            )
                    paired = paired_cpu_ratio_summary(
                        [row["cpu_ns"] for row in samples["minyar"]],
                        [row["cpu_ns"] for row in samples["cpp"]],
                    )
                    paired.update(numerator="minyar", denominator="cpp")
                    entries[kind] = {
                        "samples": samples,
                        "warmup_samples": warmup,
                        "median_cpu_ns": {
                            language: statistics.median(row["cpu_ns"] for row in rows)
                            for language, rows in samples.items()
                        },
                        "paired_cpu_ratio": paired,
                    }
                    print(
                        name,
                        kind,
                        entries[kind]["median_cpu_ns"],
                        "paired ratio",
                        paired["median"],
                        flush=True,
                    )
        else:
            rng = random.Random(20261002)
            cases = [(0, 0), (1, 0), (1, 1000002), (1027, 999983)]
            cases += [
                (rng.randrange(1, 1500), rng.randrange(1000003)) for _ in range(8)
            ]
            for name, executable in executables.items():
                entries = result["configurations"][name] = []
                for kind in KINDS:
                    for index, (count, seed) in enumerate(cases):
                        expected = oracle(kind, count, seed)
                        for language in ("minyar", "cpp"):
                            completed = run(
                                [executable, language, kind, count, seed],
                                f"{name}-{kind}-{language}-{index}",
                                env,
                            )
                            row = json.loads(completed.stdout)
                            entries.append(
                                {
                                    "kind": kind,
                                    "language": language,
                                    "count": count,
                                    "seed": seed,
                                    "result": row["result"],
                                    "system_operations": row["system_operations"],
                                    "pool_allocations": row["pool_allocations"],
                                }
                            )
                            assert row["result"] == expected, (
                                name,
                                kind,
                                language,
                                count,
                                seed,
                                row,
                            )
                            assert (
                                row["system_operations"] == row["pool_allocations"] == 0
                            )
                result["configurations"][name] = entries
                print(
                    f"{name}: {len(entries)} oracle/allocation checks passed",
                    flush=True,
                )
        result["status"] = "passed"
    except BaseException as error:
        result["status"] = "failed"
        result["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report_destination.parent.mkdir(parents=True, exist_ok=True)
        report_destination.write_text(json.dumps(result, indent=2) + "\n")
        print(report_destination, flush=True)


if __name__ == "__main__":
    main()
