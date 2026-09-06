#!/usr/bin/env python3
"""Measure compiler function/region coverage and runtime line/branch coverage."""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def find_tool(environment: str, name: str) -> str:
    configured = os.environ.get(environment)
    if configured:
        return configured
    found = shutil.which(name)
    if found:
        return found
    xcrun = shutil.which("xcrun")
    if xcrun:
        result = subprocess.run([xcrun, "-f", name], text=True, capture_output=True)
        if result.returncode == 0:
            return result.stdout.strip()
    raise SystemExit(f"coverage tool '{name}' is required (set {environment} to override)")


def run(command: list[str], *, env: dict[str, str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}{result.stderr}")
    return result


def percentage(covered: int, count: int) -> float:
    return round(100.0 * covered / count, 2) if count else 100.0


def main() -> int:
    clang = os.environ.get("MINYAR_TEST_CLANG", "clang")
    profdata = find_tool("LLVM_PROFDATA", "llvm-profdata")
    llvm_cov = find_tool("LLVM_COV", "llvm-cov")
    coverage_root = ROOT / "build" / "coverage"
    coverage_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=coverage_root)).resolve()
    profiles = run_dir / "profiles"
    profiles.mkdir()
    compiler_edges = run_dir / "compiler-edges"
    compiler_edges.mkdir()
    env = dict(os.environ)
    env.update(
        LLVM_PROFILE_FILE=str(profiles / "%p-%m.profraw"),
        MINYAR_SANCOV_DIR=str(compiler_edges),
        MINYAR_TEST_CLANG=clang,
    )

    run(
        ["make", "-s", "LIMITED=", "SANITIZER_LIMITED=", "build/compiler-stage2.ll", "build/minyar-compiler-runtime.ll"],
        env=env,
    )
    instrumented_compiler_ir = run_dir / "compiler-coverage.ll"
    run(
        [
            clang,
            "-O0",
            "-S",
            "-emit-llvm",
            "-fsanitize-coverage=trace-pc-guard",
            "-Wno-override-module",
            str(ROOT / "build" / "compiler-stage2.ll"),
            "-o",
            str(instrumented_compiler_ir),
        ],
        env=env,
    )
    compiler = run_dir / "minyarc-profile"
    run(
        [
            clang,
            "-O0",
            "-g",
            "-Wno-override-module",
            str(instrumented_compiler_ir),
            str(ROOT / "build" / "minyar-compiler-runtime.ll"),
            str(ROOT / "tests" / "compiler-coverage-runtime.c"),
            "-o",
            str(compiler),
        ],
        env=env,
    )
    runtime_object = run_dir / "runtime-profile.o"
    run(
        [
            clang,
            "-O0",
            "-g",
            "-fprofile-instr-generate",
            "-fcoverage-mapping",
            "-DMINYAR_RC_TESTING=1",
            "-c",
            str(ROOT / "runtime" / "minyar_runtime.c"),
            "-o",
            str(runtime_object),
        ],
        env=env,
    )
    runtime_unit = run_dir / "runtime-unit-profile"
    run(
        [
            clang,
            "-O0",
            "-g",
            "-fprofile-instr-generate",
            "-fcoverage-mapping",
            str(ROOT / "tests" / "runtime-unit.c"),
            "-o",
            str(runtime_unit),
        ],
        env=env,
    )
    run([str(runtime_unit)], env=env)

    suite_env = {
        **env,
        "MINYAR_TEST_COMPILER": str(compiler),
        "MINYAR_TEST_RUNTIME": str(runtime_object),
        "MINYAR_TEST_LINK_FLAGS": "-fprofile-instr-generate",
    }
    run([sys.executable, "tests/diagnostics.py"], env=suite_env)
    run([sys.executable, "tests/conformance.py"], env=suite_env)
    run([sys.executable, "tests/regressions.py"], env=suite_env)
    run([sys.executable, "tests/fuzz.py", "--cases", "200", "--program-cases", "40"], env=suite_env)
    # Self-compilation reaches compiler-only module merging and large-program paths.
    run([str(compiler), "src/compiler.min", str(run_dir / "self.ll")], env=env)

    raw_profiles = sorted(profiles.glob("*.profraw"))
    if not raw_profiles:
        raise RuntimeError("instrumented checks produced no coverage profiles")
    merged = run_dir / "coverage.profdata"
    run([profdata, "merge", "-sparse", *map(str, raw_profiles), "-o", str(merged)], env=env)

    total_edges = 0
    merged_edges = bytearray()
    for edge_file in sorted(compiler_edges.glob("*.edges")):
        data = edge_file.read_bytes()
        if len(data) < 8:
            raise RuntimeError(f"truncated compiler edge profile: {edge_file}")
        count = struct.unpack("=Q", data[:8])[0]
        bitmap = data[8:]
        if len(bitmap) != count:
            raise RuntimeError(f"invalid compiler edge profile: {edge_file}")
        if total_edges == 0:
            total_edges = count
            merged_edges = bytearray(bitmap)
        elif count != total_edges:
            raise RuntimeError("instrumented compiler edge counts changed within one coverage run")
        else:
            for index, value in enumerate(bitmap):
                merged_edges[index] |= value
    if total_edges == 0:
        raise RuntimeError("instrumented compiler produced no edge profiles")
    covered_edges = sum(1 for value in merged_edges if value)

    exported = run(
        [
            llvm_cov,
            "export",
            str(runtime_unit),
            f"-instr-profile={merged}",
            str(ROOT / "runtime" / "minyar_runtime.c"),
        ],
        env=env,
    )
    coverage_json = json.loads(exported.stdout)
    runtime_totals = coverage_json["data"][0]["totals"]
    report = {
        "run_directory": str(run_dir),
        "profiles": len(raw_profiles),
        "compiler": {
            "measurement": "SanitizerCoverage control-flow edges in LLVM emitted from src/compiler.min",
            "edges": {
                "count": total_edges,
                "covered": covered_edges,
                "percent": percentage(covered_edges, total_edges),
            },
        },
        "runtime": runtime_totals,
    }
    report_path = run_dir / "coverage.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

    minimum_compiler = float(os.environ.get("MINYAR_MIN_COMPILER_EDGE_COVERAGE", "0"))
    minimum_runtime_lines = float(os.environ.get("MINYAR_MIN_RUNTIME_LINE_COVERAGE", "0"))
    minimum_runtime_branches = float(os.environ.get("MINYAR_MIN_RUNTIME_BRANCH_COVERAGE", "0"))
    failures = []
    compiler_percent = report["compiler"]["edges"]["percent"]
    if compiler_percent < minimum_compiler:
        failures.append(f"compiler edge coverage {compiler_percent}% < {minimum_compiler}%")
    if runtime_totals["lines"]["percent"] < minimum_runtime_lines:
        failures.append(f"runtime line coverage {runtime_totals['lines']['percent']}% < {minimum_runtime_lines}%")
    if runtime_totals["branches"]["percent"] < minimum_runtime_branches:
        failures.append(f"runtime branch coverage {runtime_totals['branches']['percent']}% < {minimum_runtime_branches}%")
    if failures:
        print("coverage gate failed: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
