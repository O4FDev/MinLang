#!/usr/bin/env python3
"""Measure compiler function/region coverage and runtime line/branch coverage."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPILER_SUITES = ("diagnostics", "conformance", "regressions", "compiler-hardening", "list-access",
                   "checked-arithmetic", "checked-scalars", "readonly-parameters",
                   "peer-research-semantics", "peer-research-reachability",
                   "peer-memory-nim-koka-lean", "peer-memory-nim-koka-followups")


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


def run(command: list[str], *, env: dict[str, str], timeout: int = 180, input: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, env=env, input=input, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}{result.stderr}")
    return result


def percentage(covered: int, count: int) -> float:
    if count <= 0 or not 0 <= covered <= count:
        raise ValueError(f"invalid coverage denominator: covered={covered}, count={count}")
    return round(100.0 * covered / count, 2)


def minimum_coverage(environment: str) -> float:
    value = float(os.environ.get(environment, "0"))
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError(f"{environment} must be finite and between 0 and 100")
    return value


def toolchain_identity(tools: dict[str, str], env: dict[str, str]) -> dict:
    identities = {}
    for name, path in tools.items():
        version = run([path, "--version"], env=env).stdout.strip()
        match = re.search(r"\b(?:clang|LLVM)\s+version\s+(\d+)\b", version, re.IGNORECASE)
        if not match:
            raise ValueError(f"cannot identify LLVM version for {name}: {path}")
        identities[name] = {"path": path, "version": version, "major": int(match.group(1))}
    if len({identity["major"] for identity in identities.values()}) != 1:
        raise ValueError("coverage requires matching LLVM major versions for Clang, opt, llvm-cov and llvm-profdata")
    return identities


def build_compiler_runtime(destination: Path, *, clang: str, env: dict[str, str]) -> None:
    # A prebuilt LLVM runtime may carry vendor-specific ABI attributes from a
    # different Clang. Compile the same arena source with the selected backend;
    # keep stack protection and shared production artifacts intact.
    run([clang, "-O2", "-DMINYAR_COMPILER_ARENA=1", "-c",
         str(ROOT / "runtime/minyar_runtime.c"), "-o", str(destination)], env=env)


def instrument_compiler_ir(source: Path, destination: Path, *, clang: str, opt: str,
                           phase: str, env: dict[str, str]) -> None:
    if phase not in ("before-inlining", "after-inlining"):
        raise ValueError(f"unknown coverage phase: {phase}")
    if phase == "before-inlining":
        # Assign IDs to the original CFG. Later inlining preserves those IDs,
        # so copies of a checked helper share identities for its distinct arms.
        # No helper, safety branch, or compiler function is excluded.
        triple = run([clang, "-dumpmachine"], env=env).stdout.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.]+(?:-[A-Za-z0-9_.]+){2,}", triple):
            raise ValueError("selected Clang did not provide a valid target triple")
        run([opt, "--mtriple=" + triple, "-passes=sancov-module", "-sanitizer-coverage-level=3",
             "-sanitizer-coverage-trace-pc-guard", "-S", str(source),
             "-o", str(destination)], env=env)
        return
    run([clang, "-O0", "-S", "-emit-llvm", "-fsanitize-coverage=trace-pc-guard",
         "-Wno-override-module", str(source), "-o", str(destination)], env=env)


def compiler_edge_coverage(directory: Path) -> dict:
    total = 0
    merged = bytearray()
    for path in sorted(directory.glob("*.edges")):
        data = path.read_bytes()
        if len(data) < 8:
            raise RuntimeError(f"truncated compiler edge profile: {path}")
        count = struct.unpack("=Q", data[:8])[0]
        bitmap = data[8:]
        if count == 0 or len(bitmap) != count:
            raise RuntimeError(f"invalid compiler edge profile: {path}")
        if not total:
            total, merged = count, bytearray(bitmap)
        elif count != total:
            raise RuntimeError("instrumented compiler edge counts changed within one coverage run")
        else:
            for index, value in enumerate(bitmap):
                merged[index] |= value
    covered = sum(bool(value) for value in merged)
    return {"count": total, "covered": covered, "percent": percentage(covered, total)}


def aggregate_runtime_coverage(exported: dict, runtime_directory: Path) -> tuple[dict, list[dict]]:
    """Use mapped files, including inline headers, rather than a single C filename."""
    if len(exported.get("data", [])) != 1:
        raise ValueError("expected one merged llvm-cov export")
    runtime_directory = runtime_directory.resolve()
    files = []
    names = set()
    totals: dict[str, dict[str, int | float | None]] = {}
    for row in exported["data"][0]["files"]:
        filename = Path(row["filename"]).resolve()
        if not filename.is_relative_to(runtime_directory):
            continue
        if str(filename) in names:
            raise ValueError(f"duplicate runtime coverage mapping: {filename}")
        names.add(str(filename))
        files.append({"filename": str(filename), "summary": row["summary"]})
        for metric, summary in row["summary"].items():
            total = totals.setdefault(metric, {})
            for key, value in summary.items():
                if key != "percent":
                    total[key] = total.get(key, 0) + value
    if not files or not totals.get("lines", {}).get("count"):
        raise ValueError("instrumented runtime produced no mapped lines")
    for summary in totals.values():
        summary["percent"] = percentage(summary["covered"], summary["count"]) if summary["count"] else None
    return totals, files


def main() -> int:
    # Reject malformed controls before running a potentially expensive campaign.
    minimum_compiler = minimum_coverage("MINYAR_MIN_COMPILER_EDGE_COVERAGE")
    minimum_runtime_lines = minimum_coverage("MINYAR_MIN_RUNTIME_LINE_COVERAGE")
    minimum_runtime_branches = minimum_coverage("MINYAR_MIN_RUNTIME_BRANCH_COVERAGE")
    clang = os.environ.get("MINYAR_TEST_CLANG", "clang")
    math_flags = [] if os.name == "nt" else ["-lm"]
    profdata = find_tool("LLVM_PROFDATA", "llvm-profdata")
    llvm_cov = find_tool("LLVM_COV", "llvm-cov")
    opt = find_tool("LLVM_OPT", "opt")
    tools = toolchain_identity({"clang": clang, "opt": opt, "llvm_cov": llvm_cov,
                               "profdata": profdata}, dict(os.environ))
    coverage_root = ROOT / "build" / "coverage"
    coverage_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=coverage_root)).resolve()
    profiles = run_dir / "profiles"
    profiles.mkdir()
    env = dict(os.environ)
    env.update(
        LLVM_PROFILE_FILE=str(profiles / "%p-%m.profraw"),
        MINYAR_TEST_CLANG=clang,
    )

    run(
        ["make", "-s", "LIMITED=", "SANITIZER_LIMITED=", "build/compiler-stage2.ll", "build/minyarc-modules"],
        env=env,
    )
    compiler_runtime = run_dir / "compiler-arena-runtime.o"
    build_compiler_runtime(compiler_runtime, clang=clang, env=env)
    compiler_runs = []
    for phase in ("before-inlining", "after-inlining"):
        directory = run_dir / phase
        directory.mkdir()
        compiler_edges = directory / "compiler-edges"
        compiler_edges.mkdir()
        instrumented_compiler_ir = directory / "compiler-coverage.ll"
        instrument_compiler_ir(ROOT / "build/compiler-stage2.ll", instrumented_compiler_ir,
                               clang=clang, opt=opt, phase=phase, env=env)
        compiler = directory / "minyarc-profile"
        run([clang, "-O0", "-g", "-Wno-override-module", str(instrumented_compiler_ir),
             str(compiler_runtime),
             str(ROOT / "tests/compiler-coverage-runtime.c"), *math_flags,
             "-o", str(compiler)], env=env)
        compiler_runs.append((phase, directory, compiler, compiler_edges))
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
            *math_flags,
            "-o",
            str(runtime_unit),
        ],
        env=env,
    )
    run([str(runtime_unit)], env=env)
    runtime_bytes = run_dir / "runtime-bytes-profile"
    run([clang, "-O0", "-g", "-fprofile-instr-generate", "-fcoverage-mapping",
         str(ROOT / "tests/runtime-bytes.c"), *math_flags, "-o", str(runtime_bytes)], env=env)
    run([str(runtime_bytes)], env=env)
    runtime_numeric = run_dir / "runtime-numeric-profile"
    run([clang, "-O0", "-g", "-fprofile-instr-generate", "-fcoverage-mapping",
         str(ROOT / "tests/runtime-numeric.c"), *math_flags, "-o", str(runtime_numeric)], env=env)
    run([str(runtime_numeric), "--bounds"], env=env)
    run([str(runtime_numeric), "--budget"], env=env)
    spec = importlib.util.spec_from_file_location("numeric_oracle", ROOT / "tests/runtime-numeric.py")
    sys.path.insert(0, str(ROOT / "tests"))
    numeric_oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(numeric_oracle)
    numeric_bits, numeric_golden = numeric_oracle.oracle_cases(2000, 0x4e554d45524943)
    numeric_input = "".join(f"{value:016x}\n" for value in numeric_bits)
    (run_dir / "numeric.bits").write_text(numeric_input)
    numeric_result = run([str(runtime_numeric)], env=env, input=numeric_input)
    numeric_oracle.verify_output(numeric_bits, numeric_result.stdout, numeric_golden)
    (run_dir / "numeric.stdout").write_text(numeric_result.stdout)

    compiler_reports = {}
    self_outputs = []
    for phase, directory, compiler, compiler_edges in compiler_runs:
        suite_env = {
            **env,
            "MINYAR_SANCOV_DIR": str(compiler_edges),
            "MINYAR_TEST_COMPILER": str(compiler),
            "MINYAR_TEST_RUNTIME": str(runtime_object),
            "MINYAR_TEST_LINK_FLAGS": " ".join(["-fprofile-instr-generate", *math_flags]),
        }
        for name in COMPILER_SUITES:
            run([sys.executable, f"tests/{name}.py"], env=suite_env)
        run([sys.executable, "tests/linkage.py", "LanguageLinkage.test_ordinary_names_do_not_interpose_c_dependencies"], env=suite_env)
        run([sys.executable, "tests/runtime-numeric.py", "--mode", "native", "--cases", "2000",
             "--output-dir", str(directory / "numeric")], env=suite_env)
        run([sys.executable, "tests/fuzz.py", "--cases", "200", "--program-cases", "40",
             "--output-dir", str(directory / "fuzz")], env=suite_env)
        # Both instrumentation orders must preserve exact compiler output.
        output = directory / "self.ll"
        run([str(compiler), "compiler/compiler.min", str(output)], env=suite_env)
        self_outputs.append(output.read_bytes())
        compiler_reports[phase] = compiler_edge_coverage(compiler_edges)
    if self_outputs[0] != self_outputs[1] or self_outputs[0] != (ROOT / "build/compiler-stage2.ll").read_bytes():
        raise RuntimeError("coverage instrumentation changed self-hosted compiler output")

    raw_profiles = sorted(profiles.glob("*.profraw"))
    if not raw_profiles:
        raise RuntimeError("instrumented checks produced no coverage profiles")
    merged = run_dir / "coverage.profdata"
    run([profdata, "merge", "-sparse", *map(str, raw_profiles), "-o", str(merged)], env=env)

    exported = run(
        [
            llvm_cov,
            "export",
            str(runtime_unit),
            f"-object={runtime_bytes}",
            f"-object={runtime_numeric}",
            f"-instr-profile={merged}",
        ],
        env=env,
    )
    coverage_json = json.loads(exported.stdout)
    runtime_totals, runtime_files = aggregate_runtime_coverage(coverage_json, ROOT / "runtime")
    for row in runtime_files:
        row["source_sha256"] = hashlib.sha256(Path(row["filename"]).read_bytes()).hexdigest()
    report = {
        "run_directory": str(run_dir),
        "profiles": len(raw_profiles),
        "tools": tools,
        "compiler_runtime": {"configuration": "MINYAR_COMPILER_ARENA=1; isolated selected-Clang C build at O2",
                             "object_sha256": hashlib.sha256(compiler_runtime.read_bytes()).hexdigest()},
        "target_triple": run([clang, "-dumpmachine"], env=env).stdout.strip(),
        "compiler_suites": list(COMPILER_SUITES),
        "compiler": {
            "measurement": "SanitizerCoverage distinct LLVM control-flow edges, IDs assigned before inlining; no function or guard exclusions",
            "source_sha256": hashlib.sha256((ROOT / "compiler/compiler.min").read_bytes()).hexdigest(),
            "ir_sha256": hashlib.sha256((ROOT / "build/compiler-stage2.ll").read_bytes()).hexdigest(),
            "edges": compiler_reports["before-inlining"],
            "after_inlining_edges": compiler_reports["after-inlining"],
            "instrumented_outputs_match_fixed_point": True,
        },
        "runtime": runtime_totals,
        "runtime_files": runtime_files,
        "runtime_configuration": "eager reference counting; compiler-arena, bounded/pool, and optional native backends are separate configurations",
    }
    report_path = run_dir / "coverage.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

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
