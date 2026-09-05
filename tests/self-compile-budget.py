#!/usr/bin/env python3
"""Check fixed resource ceilings for self-compilation.

Run outside scripts/with-limits.sh, as make check-budget does: background
priority changes scheduling and inflates absolute timings. The test uses the
best 90th-percentile result across batches to reduce sensitivity to transient
host load. CPU, memory, and instruction limits are checked separately."""

from __future__ import annotations

import platform
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource
except ImportError:  # Windows
    resource = None

ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "build" / "minyarc"
SOURCE = ROOT / "src" / "compiler.min"
OUTPUT = ROOT / "build" / "self-compile-budget.ll"
REFERENCE = ROOT / "build" / "compiler-stage3.ll"

RUNS = 100
BATCHES = 3

# Measured on an Apple M-series laptop in September 2026: wall 90th percentile
# about 6.5 ms, CPU 90th percentile about 4.7 ms, peak resident memory 5.5 MiB
# and about 30.4 million retired instructions, of which roughly 9.6 million
# are the cost of starting and ending any process at all.
MAX_WALL_P90_MS = 8.0
MAX_CPU_P90_MS = 6.0
MAX_PEAK_RSS_MIB = 6.0
MAX_INSTRUCTIONS = 32_000_000


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def compile_once() -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(COMPILER), str(SOURCE), str(OUTPUT)], text=True, capture_output=True)


def retired_instructions() -> int | None:
    """Ask /usr/bin/time -l for the retired instruction count (macOS only)."""
    if sys.platform != "darwin" or not Path("/usr/bin/time").exists():
        return None
    best = None
    for _ in range(5):
        result = subprocess.run(["/usr/bin/time", "-l", str(COMPILER), str(SOURCE), str(OUTPUT)],
                                text=True, capture_output=True)
        match = re.search(r"(\d+)\s+instructions retired", result.stderr)
        if not match:
            return None
        count = int(match.group(1))
        best = count if best is None else min(best, count)
    return best


def main() -> None:
    if not COMPILER.exists():
        raise SystemExit(f"build {COMPILER.relative_to(ROOT)} first (make build/minyarc)")

    warm_up = compile_once()
    if warm_up.returncode != 0:
        raise SystemExit(f"self-compile failed:\n{warm_up.stderr}")
    if REFERENCE.exists() and OUTPUT.read_bytes() != REFERENCE.read_bytes():
        raise SystemExit("self-compile output differs from the fixed-point compiler")

    wall_p90 = float("inf")
    cpu_p90: float | None = float("inf") if resource else None
    for _ in range(BATCHES):
        walls: list[float] = []
        cpus: list[float] = []
        for _ in range(RUNS):
            before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
            started = time.perf_counter()
            result = compile_once()
            walls.append((time.perf_counter() - started) * 1000)
            if before:
                after = resource.getrusage(resource.RUSAGE_CHILDREN)
                cpus.append(((after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)) * 1000)
            if result.returncode != 0:
                raise SystemExit(f"self-compile failed:\n{result.stderr}")
        wall_p90 = min(wall_p90, percentile(walls, 0.9))
        if cpu_p90 is not None:
            cpu_p90 = min(cpu_p90, percentile(cpus, 0.9))
    peak_rss_mib = None
    if resource:
        units = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        peak_rss_mib = units / (1024 * 1024) if sys.platform == "darwin" else units / 1024
    instructions = retired_instructions()

    print(f"self-compile, best of {BATCHES} batches of {RUNS} runs on {platform.machine()}:")
    print(f"  wall 90th percentile: {wall_p90:.2f} ms (limit {MAX_WALL_P90_MS:.2f} ms)")
    if cpu_p90 is not None:
        print(f"  CPU 90th percentile:  {cpu_p90:.2f} ms (limit {MAX_CPU_P90_MS:.2f} ms)")
    if peak_rss_mib is not None:
        print(f"  peak memory:          {peak_rss_mib:.1f} MiB (limit {MAX_PEAK_RSS_MIB:.1f} MiB)")
    if instructions is not None:
        print(f"  instructions retired: {instructions / 1e6:.2f} M (limit {MAX_INSTRUCTIONS / 1e6:.2f} M)")

    failures = []
    if wall_p90 > MAX_WALL_P90_MS:
        failures.append(f"wall 90th percentile {wall_p90:.2f} ms is over the {MAX_WALL_P90_MS:.2f} ms budget")
    if cpu_p90 is not None and cpu_p90 > MAX_CPU_P90_MS:
        failures.append(f"CPU 90th percentile {cpu_p90:.2f} ms is over the {MAX_CPU_P90_MS:.2f} ms budget")
    if peak_rss_mib is not None and peak_rss_mib > MAX_PEAK_RSS_MIB:
        failures.append(f"peak memory {peak_rss_mib:.1f} MiB is over the {MAX_PEAK_RSS_MIB:.1f} MiB budget")
    if instructions is not None and instructions > MAX_INSTRUCTIONS:
        failures.append(f"{instructions} retired instructions is over the {MAX_INSTRUCTIONS} budget")
    if failures:
        raise SystemExit("self-compile budget exceeded:\n  " + "\n  ".join(failures))
    print("self-compile budget met")


if __name__ == "__main__":
    main()
