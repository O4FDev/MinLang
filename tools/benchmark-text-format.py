#!/usr/bin/env python3
"""Compare counted numeric-format probes in alternating process pairs."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="probe compiled before the change")
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=1000000)
    parser.add_argument("--output", default="build/text-format-benchmark.json")
    options = parser.parse_args()
    if options.pairs < 1 or options.iterations < 1:
        parser.error("pairs and iterations must be positive")
    compiler = subprocess.check_output(["sh", "tools/toolchain.sh", "default-clang"], text=True).strip()
    current = "build/text-format-current"
    subprocess.run([compiler, "-O2", "tests/runtime-numeric.c", "-lm", "-o", current], check=True)
    executables = {"baseline": options.baseline, "current": current}
    report = {}
    for kind in ("integer", "mixed"):
        samples = {"baseline": [], "current": []}
        checksums = set()
        for pair in range(options.pairs):
            order = ("baseline", "current") if pair % 2 == 0 else ("current", "baseline")
            for label in order:
                value = json.loads(subprocess.check_output([
                    executables[label], "--bench", kind, str(options.iterations)]))
                checksums.add(value["checksum"])
                samples[label].append(value)
        if len(checksums) != 1:
            raise RuntimeError("baseline and current output checksums differ")
        medians = {label: statistics.median(row["cpu_seconds"] for row in rows)
                   for label, rows in samples.items()}
        report[kind] = {"samples": samples, "median_cpu_seconds": medians,
                        "speedup": medians["baseline"] / medians["current"]}
    Path(options.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({kind: {key: value for key, value in group.items() if key != "samples"}
                      for kind, group in report.items()}))
    print(subprocess.check_output([current, "--budget"], text=True).strip())


if __name__ == "__main__":
    main()
