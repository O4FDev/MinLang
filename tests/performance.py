#!/usr/bin/env python3
"""Measure compiler and generated-program performance.

1. Self-compilation checks resource ceilings and compiler fixed-point output.
2. Scaling checks compare workloads at two sizes, the second four times larger.
3. Measurements are saved to build/performance.json and compared against
   build/performance-baseline.json when it exists. Use --save-baseline to create
   a baseline. Measurements exceeding the configured tolerance fail."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

try:
    import resource
except ImportError:  # Windows
    resource = None


ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "build" / "minyarc"
SOURCE = ROOT / "src" / "compiler.min"
OUTPUT = ROOT / "build" / "compiler-performance-check.ll"
REFERENCE = ROOT / "build" / "compiler-stage3.ll"
RUNTIME = ROOT / "build" / "minyar-runtime.o"
if not RUNTIME.exists():
    RUNTIME = ROOT / "runtime" / "minyar_runtime.c"
BENCHMARK = ROOT / "tests" / "performance" / "runtime.min"
RESULTS = ROOT / "build" / "performance.json"
BASELINE = ROOT / "build" / "performance-baseline.json"

MAX_SECONDS = 20.0
MAX_CPU_SECONDS = 2.0
MAX_RSS_MIB = 64.0
REPEATS = 3
SCALE_FACTOR = 4


def run(command: list[str], *, timeout: float = 60, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def best_of(command: list[str], repeats: int = REPEATS, timeout: float = 60) -> tuple[float, subprocess.CompletedProcess[str]]:
    """Return the lowest child CPU time, or wall time where unavailable.

    The first run of a freshly linked executable pays a one-off cost on macOS
    while the system verifies it, so a warm-up run precedes the timed ones.
    CPU time keeps background-priority scheduling delays out of scaling ratios.
    """
    result = run(command, timeout=timeout)
    if result.returncode != 0:
        return 0.0, result
    best = float("inf")
    for _ in range(repeats):
        before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
        started = time.monotonic()
        result = run(command, timeout=timeout)
        elapsed = time.monotonic() - started
        if before:
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            elapsed = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        best = min(best, elapsed)
        if result.returncode != 0:
            break
    return best, result


def link(clang: str, llvm: Path, executable: Path) -> None:
    linked = run([clang, "-O0", "-Wno-override-module", str(llvm), str(RUNTIME), "-o", str(executable)])
    if linked.returncode != 0:
        raise SystemExit(f"could not link {llvm.name}:\n{linked.stderr}")


# --- 1. self-compile -----------------------------------------------------------


def check_self_compile(results: dict[str, float]) -> None:
    before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
    started = time.monotonic()
    result = run([str(COMPILER), str(SOURCE), str(OUTPUT)], timeout=MAX_SECONDS)
    elapsed = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
    if result.returncode != 0:
        raise SystemExit(f"self-compile failed during performance check:\n{result.stderr}")
    if elapsed > MAX_SECONDS:
        raise SystemExit(f"self-compile took {elapsed:.2f}s; limit is {MAX_SECONDS:.2f}s")
    if REFERENCE.exists() and OUTPUT.read_bytes() != REFERENCE.read_bytes():
        raise SystemExit("performance-check compiler output differs from the fixed-point compiler")
    results["self-compile.wall"] = elapsed
    details = f"wall {elapsed:.3f}s"
    if before and after:
        cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        rss_units = after.ru_maxrss
        rss_mib = rss_units / (1024 * 1024) if sys.platform == "darwin" else rss_units / 1024
        if cpu > MAX_CPU_SECONDS:
            raise SystemExit(f"self-compile used {cpu:.2f}s CPU; limit is {MAX_CPU_SECONDS:.2f}s")
        if rss_mib > MAX_RSS_MIB:
            raise SystemExit(f"self-compile used {rss_mib:.1f} MiB; limit is {MAX_RSS_MIB:.1f} MiB")
        results["self-compile.cpu"] = cpu
        results["self-compile.rss-mib"] = rss_mib
        details += f", CPU {cpu:.3f}s, peak {rss_mib:.1f} MiB"
    print(f"self-compile: {details}")


# --- 2. compile-time scaling ---------------------------------------------------


@dataclass(frozen=True)
class CompileWorkload:
    name: str
    small: int
    max_ratio: float
    generate: Callable[[int, Path], Path]
    note: str = ""


def statements(count: int, directory: Path) -> Path:
    lines = ["let total = 0\n", "let step = 0\n"]
    for index in range(count):
        lines.append(f"step = (step + {index % 13}) % 101\n")
        lines.append("total = total + step * 2 - step / 3\n")
        if index % 50 == 0:
            lines.append("while step > 100 {\n    step = step - 1\n}\n")
    lines.append("print(total)\n")
    source = directory / f"statements-{count}.min"
    source.write_text("".join(lines), encoding="utf-8")
    return source


def locals_in_one_function(count: int, directory: Path) -> Path:
    lines = ["function main() {\n"]
    for index in range(count):
        lines.append(f"    let value{index} = {index}\n")
    lines.append(f"    print(value{count - 1})\n}}\n")
    source = directory / f"locals-{count}.min"
    source.write_text("".join(lines), encoding="utf-8")
    return source


def functions(count: int, directory: Path) -> Path:
    lines = []
    for index in range(count):
        lines.append(f"function compute{index}(value: Integer): Integer {{\n    return value + {index}\n}}\n")
    lines.append("let total = 0\n")
    for index in range(count):
        lines.append(f"total = total + compute{index}({index % 5})\n")
    lines.append("print(total)\n")
    source = directory / f"functions-{count}.min"
    source.write_text("".join(lines), encoding="utf-8")
    return source


def records(count: int, directory: Path) -> Path:
    lines = []
    for index in range(count):
        lines.append(f"record Shape{index} {{\n    width: Integer\n    label: Text\n}}\n")
    lines.append(f"let shape = Shape{count - 1} {{ width: 1, label: \"last\" }}\nprint(shape.width)\n")
    source = directory / f"records-{count}.min"
    source.write_text("".join(lines), encoding="utf-8")
    return source


def module_chain(count: int, directory: Path) -> Path:
    module_dir = directory / f"modules-{count}"
    module_dir.mkdir()
    (module_dir / "module0.min").write_text("public function value(): Integer {\n    return 1\n}\n", encoding="utf-8")
    for index in range(1, count):
        (module_dir / f"module{index}.min").write_text(
            f'use "./module{index - 1}.min" as previous\n\n'
            "public function value(): Integer {\n    return previous.value() + 1\n}\n",
            encoding="utf-8",
        )
    entry = module_dir / "main.min"
    entry.write_text(f'use "./module{count - 1}.min" as last\n\nprint(last.value())\n', encoding="utf-8")
    return entry


# A linear pass scales by about 4x for 4x more input and a quadratic one by
# about 16x. The 7x bound leaves room for timing noise under the throttled
# test runner while still catching a pass that has become quadratic.
COMPILE_WORKLOADS = [
    CompileWorkload("statements", 2000, 7.0, statements),
    CompileWorkload("locals", 4000, 7.0, locals_in_one_function),
    CompileWorkload("modules", 32, 7.0, module_chain),
    CompileWorkload("functions", 500, 7.0, functions),
    CompileWorkload("records", 500, 7.0, records),
]


def check_compile_scaling(temporary: Path, results: dict[str, float]) -> None:
    for workload in COMPILE_WORKLOADS:
        timings = {}
        for size in (workload.small, workload.small * SCALE_FACTOR):
            source = workload.generate(size, temporary)
            output = temporary / f"{workload.name}-{size}.ll"
            elapsed, result = best_of([str(COMPILER), str(source), str(output)])
            if result.returncode != 0:
                raise SystemExit(f"compile workload '{workload.name}' failed at size {size}:\n{result.stderr}")
            timings[size] = elapsed
            results[f"compile.{workload.name}.{size}"] = elapsed
        small, large = timings[workload.small], timings[workload.small * SCALE_FACTOR]
        ratio = large / max(small, 0.001)
        results[f"compile.{workload.name}.ratio"] = ratio
        note = f" ({workload.note})" if workload.note else ""
        print(f"compile {workload.name:11} {workload.small:>6} -> {small:.3f}s   x{SCALE_FACTOR} -> {large:.3f}s   ratio {ratio:.1f}{note}")
        if large >= 0.02 and ratio > workload.max_ratio:
            raise SystemExit(
                f"compile workload '{workload.name}' scaled by {ratio:.1f}x for {SCALE_FACTOR}x more input; "
                f"limit is {workload.max_ratio:.1f}x"
            )


# --- 3. runtime scaling --------------------------------------------------------


def expected_benchmark_output(scale: int) -> str:
    list_count = 200000 * scale
    record_count = 100000 * scale
    text_count = 100000 * scale
    arithmetic_count = 500000 * scale
    call_count = 20 * scale
    list_total = sum(index % 97 for index in range(list_count))
    record_total = record_count * (record_count - 1) // 2
    text_total = text_count + text_count + 2 * text_count
    total = 0
    for position in range(arithmetic_count):
        # Minyar's / truncates toward zero, as does Python's // for positive values.
        total = (total + position * 3 - position // 2 + position % 5) % 1000003
    call_total = call_count * 610
    return f"{list_total}\n{record_total}\n{text_total}\n{total}\n{call_total}\n"


def check_runtime_scaling(clang: str, temporary: Path, results: dict[str, float], max_ratio: float = 7.0) -> None:
    llvm = temporary / "runtime-benchmark.ll"
    executable = temporary / "runtime-benchmark"
    compiled = run([str(COMPILER), str(BENCHMARK), str(llvm)])
    if compiled.returncode != 0:
        raise SystemExit(f"runtime benchmark failed to compile:\n{compiled.stderr}")
    link(clang, llvm, executable)
    small_scale = 2
    timings = {}
    for scale in (small_scale, small_scale * SCALE_FACTOR):
        elapsed, result = best_of([str(executable), str(scale)])
        if result.returncode != 0:
            raise SystemExit(f"runtime benchmark failed at scale {scale}:\n{result.stderr}")
        expected = expected_benchmark_output(scale)
        if result.stdout != expected:
            raise SystemExit(
                f"runtime benchmark produced the wrong result at scale {scale}:\n"
                f"expected:\n{expected}actual:\n{result.stdout}"
            )
        timings[scale] = elapsed
        results[f"runtime.benchmark.{scale}"] = elapsed
    small, large = timings[small_scale], timings[small_scale * SCALE_FACTOR]
    ratio = large / max(small, 0.001)
    results["runtime.benchmark.ratio"] = ratio
    print(f"runtime benchmark   scale {small_scale:>2} -> {small:.3f}s   x{SCALE_FACTOR} -> {large:.3f}s   ratio {ratio:.1f}")
    if large >= 0.02 and ratio > max_ratio:
        raise SystemExit(f"runtime benchmark scaled by {ratio:.1f}x for {SCALE_FACTOR}x more work; limit is {max_ratio:.1f}x")


# --- 4. baseline ---------------------------------------------------------------


def compare_with_baseline(results: dict[str, float], tolerance: float, minimum_seconds: float = 0.02) -> None:
    if not BASELINE.exists():
        print(f"no baseline at {BASELINE.relative_to(ROOT)}; run with --save-baseline to create one")
        return
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    regressions = []
    for key, value in results.items():
        previous = baseline.get(key)
        if previous is None or key.endswith(".ratio") or key.endswith(".rss-mib"):
            continue
        if value >= minimum_seconds and previous > 0 and value > previous * tolerance:
            regressions.append(f"  {key}: {previous:.3f} -> {value:.3f} ({value / previous:.2f}x)")
    if regressions:
        raise SystemExit(f"performance regressed past {tolerance:.2f}x of the baseline:\n" + "\n".join(regressions))
    print(f"no measurement regressed past {tolerance:.2f}x of the baseline")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--tolerance", type=float, default=float(os.environ.get("MINYAR_PERF_TOLERANCE", "1.5")))
    parser.add_argument("--save-baseline", action="store_true", help="store this run as the comparison baseline")
    arguments = parser.parse_args()

    results: dict[str, float] = {}
    with tempfile.TemporaryDirectory(prefix="minyar-performance-") as directory:
        temporary = Path(directory)
        check_self_compile(results)
        check_compile_scaling(temporary, results)
        check_runtime_scaling(arguments.clang, temporary, results)

    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if arguments.save_baseline:
        shutil.copyfile(RESULTS, BASELINE)
        print(f"saved baseline to {BASELINE.relative_to(ROOT)}")
    else:
        compare_with_baseline(results, arguments.tolerance)
    print("performance checks passed")


if __name__ == "__main__":
    main()
