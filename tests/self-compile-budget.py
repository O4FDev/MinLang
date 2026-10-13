#!/usr/bin/env python3
from __future__ import annotations

import platform
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from compiler_output import check_compiler_behavior, validate_compile_output as validate_output
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments/memory"))
from measurement_stats import paired_cpu_ratio_summary

try:
    import resource
except ImportError:  # Windows
    resource = None

ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "build" / "minyarc"
SOURCE = ROOT / "build" / "compiler.min"
OUTPUT = ROOT / "build" / "self-compile-budget.ll"

RUNS = 100
BATCHES = 3

MAX_PEAK_RSS_MIB = 17.0
MAX_INSTRUCTIONS = 75_000_000
MAX_PAIRED_MEDIAN = 1.01
MAX_PAIRED_UPPER = 1.05


def file_identity(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def configuration_environment() -> dict:
    return {name: os.environ.get(name, "") for name in ("SDKROOT", "MACOSX_DEPLOYMENT_TARGET")}


def record_comparison(previous: Path, source: Path, manifest: Path) -> None:
    toolchain = json.loads((ROOT / "build/.toolchain.json").read_text())
    configuration = {"previous_ref": os.environ["MINYAR_BUDGET_PREVIOUS_REF"],
                     "current_ref": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                     "toolchain": toolchain,
                     "environment": configuration_environment(),
                     "clang": file_identity(Path(toolchain["llvm_cc"]["path"])),
                     "artifacts": {name: file_identity(path) for name, path in {
                         "current": COMPILER, "previous": previous, "input": source,
                         "runtime": ROOT / "build/minyar-compiler-runtime.ll"}.items()}}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(configuration, indent=2) + "\n")


def wall_comparison(previous: Path, source: Path, manifest: Path, report: Path) -> dict:
    if resource is None:
        raise SystemExit("same-input compiler comparison requires child CPU measurements")
    configuration = json.loads(manifest.read_text())
    paths = {"current": COMPILER, "previous": previous, "input": source,
             "runtime": ROOT / "build/minyar-compiler-runtime.ll"}
    identities = {name: file_identity(path) for name, path in paths.items()}
    if configuration["artifacts"] != identities:
        raise SystemExit("same-input compiler comparison identity mismatch")
    if configuration["toolchain"]["llvm_version"] != "23.1.2":
        raise SystemExit("same-input compiler comparison requires LLVM 23.1.2")
    stamp = ROOT / "build/.toolchain.json"
    clang = Path(configuration["toolchain"]["llvm_cc"]["path"])
    if (json.loads(stamp.read_text()) != configuration["toolchain"] or file_identity(clang) != configuration["clang"]
            or configuration_environment() != configuration["environment"]):
        raise SystemExit("same-input compiler comparison toolchain changed")
    result = {"configuration": configuration, "pairs": [], "status": "running"}
    outputs = {name: OUTPUT.with_name("wall-comparison-" + name + ".ll")
               for name in ("current", "previous")}

    def measured(name):
        output = outputs[name]
        output.unlink(missing_ok=True)
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.perf_counter()
        process = subprocess.run([str(paths[name]), str(source), str(output)], text=True,
                                 capture_output=True, close_fds=sys.platform != "darwin")
        elapsed = time.perf_counter() - started
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        validate_output(process, output, "same-input " + name)
        if any(not math.isfinite(value) or value <= 0 for value in (elapsed, cpu)):
            raise SystemExit("invalid same-input compiler duration")
        return {"wall": elapsed, "cpu": cpu}

    try:
        for name in outputs:
            measured(name)
        for batch in range(BATCHES):
            for index in range(RUNS):
                order = ("current", "previous") if (batch * RUNS + index) % 2 == 0 else ("previous", "current")
                pair = {"batch": batch, "index": index, "order": list(order)}
                result["pairs"].append(pair)
                for name in order:
                    pair[name] = measured(name)
                pair["ratios"] = {clock: pair["current"][clock] / pair["previous"][clock]
                                  for clock in ("wall", "cpu")}
        if {name: file_identity(path) for name, path in paths.items()} != identities:
            raise SystemExit("same-input compiler comparison artifacts changed")
        if (json.loads(stamp.read_text()) != configuration["toolchain"] or file_identity(clang) != configuration["clang"]
                or configuration_environment() != configuration["environment"]):
            raise SystemExit("same-input compiler comparison toolchain changed")
        for output in outputs.values():
            check_compiler_behavior(output)
        result["summaries"] = {clock: paired_cpu_ratio_summary(
            [pair["current"][clock] for pair in result["pairs"]],
            [pair["previous"][clock] for pair in result["pairs"]]) for clock in ("wall", "cpu")}
        enforce_paired_budget(result)
        result["status"] = "passed"
        return result
    except BaseException as error:
        result["status"] = "failed"
        result["error"] = str(error)
        raise
    finally:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2) + "\n")


def enforce_paired_budget(result: dict) -> None:
    failures = []
    for clock in ("wall", "cpu"):
        summary = result["summaries"][clock]
        median = summary["median"]
        upper = summary["confidence_interval"]["upper"]
        print(f"  same-input {clock} current/previous median {median:.6f} (limit {MAX_PAIRED_MEDIAN:.2f}), 95% upper {upper:.6f} (limit {MAX_PAIRED_UPPER:.2f})")
        if not math.isfinite(median) or median > MAX_PAIRED_MEDIAN:
            failures.append(f"{clock} paired median {median:.6f} exceeds {MAX_PAIRED_MEDIAN:.2f}")
        if not math.isfinite(upper) or upper > MAX_PAIRED_UPPER:
            failures.append(f"{clock} paired 95% upper {upper:.6f} exceeds {MAX_PAIRED_UPPER:.2f}")
    if failures:
        raise SystemExit("same-input compiler budget exceeded:\n  " + "\n  ".join(failures))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def compile_once() -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(COMPILER), str(SOURCE), str(OUTPUT)], text=True, capture_output=True,
                          close_fds=sys.platform != "darwin")


def validate_compile_output(result: subprocess.CompletedProcess[str], phase: str = "self-compile") -> None:
    validate_output(result, OUTPUT, phase)


def retired_instructions() -> int | None:
    """Ask /usr/bin/time -l for the retired instruction count (macOS only)."""
    if sys.platform != "darwin" or not Path("/usr/bin/time").exists():
        return None
    best = None
    for _ in range(5):
        # A stale valid file must not disguise a failed/no-output invocation.
        OUTPUT.unlink(missing_ok=True)
        result = subprocess.run(["/usr/bin/time", "-l", str(COMPILER), str(SOURCE), str(OUTPUT)],
                                text=True, capture_output=True, close_fds=sys.platform != "darwin")
        validate_compile_output(result, "profiled self-compile")
        match = re.search(r"(\d+)\s+instructions retired", result.stderr)
        if not match:
            return None
        count = int(match.group(1))
        best = count if best is None else min(best, count)
    return best


def main() -> None:
    if len(sys.argv) == 5 and sys.argv[1] == "--record-comparison":
        record_comparison(*map(Path, sys.argv[2:]))
        return
    if not COMPILER.exists():
        raise SystemExit(f"build {COMPILER.relative_to(ROOT)} first (make build/minyarc)")

    OUTPUT.unlink(missing_ok=True)
    warm_up = compile_once()
    validate_compile_output(warm_up)

    instructions = retired_instructions()
    peak_rss_mib = None
    if resource:
        units = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        peak_rss_mib = units / (1024 * 1024) if sys.platform == "darwin" else units / 1024
    print(f"self-compile resources on {platform.machine()}:")
    if peak_rss_mib is not None:
        print(f"  peak memory:          {peak_rss_mib:.1f} MiB (limit {MAX_PEAK_RSS_MIB:.1f} MiB)")
    if instructions is not None:
        print(f"  instructions retired: {instructions / 1e6:.2f} M (limit {MAX_INSTRUCTIONS / 1e6:.2f} M)")

    failures = []
    paired = sys.platform == "darwin" or "MINYAR_BUDGET_PREVIOUS_COMPILER" in os.environ
    if peak_rss_mib is not None and peak_rss_mib > MAX_PEAK_RSS_MIB:
        failures.append(f"peak memory {peak_rss_mib:.1f} MiB is over the {MAX_PEAK_RSS_MIB:.1f} MiB budget")
    if instructions is not None and instructions > MAX_INSTRUCTIONS:
        failures.append(f"{instructions} retired instructions is over the {MAX_INSTRUCTIONS} budget")
    if failures:
        raise SystemExit("self-compile budget exceeded:\n  " + "\n  ".join(failures))
    check_compiler_behavior(OUTPUT)
    if paired:
        required = ("MINYAR_BUDGET_PREVIOUS_COMPILER", "MINYAR_BUDGET_FIXED_INPUT", "MINYAR_BUDGET_COMPARISON_MANIFEST")
        if any(name not in os.environ for name in required):
            raise SystemExit("macOS wall qualification requires the matched previous compiler and fixed input")
        wall_comparison(*(Path(os.environ[name]) for name in required),
                        ROOT / "build/performance-evidence/self-compile-pairs.json")
    print("self-compile budget met")


if __name__ == "__main__":
    main()
