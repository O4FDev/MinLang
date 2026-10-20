#!/usr/bin/env python3
"""Run bounded, alternating normalization process pairs on a bx Linux host.

Compilation happens only when this driver is explicitly executed. It never
generates Unicode tables: prepare the committed provider inputs first. Timing
includes transformation, the same lightweight owned Text copy/free ABI, and
full-output FNV-1a checksum work for both variants. It excludes managed-runtime
UTF-8 validation and reference counting; this is a paired native-provider probe.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SMALL_CASES = ("ascii", "short-runs", "prose-composed", "prose-decomposed")
ADVERSARIAL_ITERATIONS = {1024: 16, 4096: 2, 16384: 1}
CASES = SMALL_CASES + tuple(f"{kind}-{size}" for size in ADVERSARIAL_ITERATIONS
                            for kind in ("leading", "starter"))
SOURCES = ("tools/benchmark-unicode-normalization.c", "runtime/native/unicode.c",
           "runtime/native/unicode_data.c")
FINGERPRINT_INPUTS = SOURCES + (
    "tools/benchmark-unicode-normalization.py", "runtime/minyar_native.h",
    "runtime/native/unicode_case_data.h", "vendor/utf8proc/utf8proc.c", "vendor/utf8proc/utf8proc.h",
    "vendor/utf8proc/utf8proc_data.c",
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_capture(command, timeout):
    """One bounded process group; a timeout also stops compiler subprocesses."""
    with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, start_new_session=True) as process:
        try:
            output, error = process.communicate(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as interruption:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, error = process.communicate()
            if isinstance(interruption, subprocess.TimeoutExpired):
                raise subprocess.TimeoutExpired(command, timeout, output=output, stderr=error)
            raise
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, output=output, stderr=error)
        return output


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def machine_details():
    model = None
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() in ("model name", "Hardware"):
                model = value.strip()
                break
    return {"uname": dict(platform.uname()._asdict()), "platform": platform.platform(),
            "cpu_model": model, "logical_cpus": os.cpu_count(),
            "affinity_cpus": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "load_average_start": list(os.getloadavg()) if hasattr(os, "getloadavg") else None}


def iterations_for(case, small_iterations):
    if case in SMALL_CASES:
        return small_iterations
    return ADVERSARIAL_ITERATIONS[int(case.rsplit("-", 1)[1])]


def summarize(group, pairs):
    samples = {variant: [row for row in group["samples"] if row["variant"] == variant]
               for variant in ("baseline", "current")}
    medians = {variant: statistics.median(row["cpu_seconds"] / row["iterations"] for row in rows)
               for variant, rows in samples.items() if rows}
    paired_ratios = []
    for pair_index in range(pairs):
        pair = {row["variant"]: row for row in group["samples"] if row["pair_index"] == pair_index}
        if "baseline" in pair and "current" in pair:
            paired_ratios.append((pair["baseline"]["cpu_seconds"] / pair["baseline"]["iterations"]) /
                                 (pair["current"]["cpu_seconds"] / pair["current"]["iterations"]))
    summary = {"completed_pairs": len(paired_ratios), "complete": len(paired_ratios) == pairs,
               "median_cpu_seconds_per_operation": medians,
               "paired_baseline_over_current_ratios": paired_ratios}
    if len(medians) == 2:
        summary["ratio_of_median_cpu_per_operation_baseline_over_current"] = medians["baseline"] / medians["current"]
    if paired_ratios:
        summary["median_paired_baseline_over_current_ratio"] = statistics.median(paired_ratios)
    group["summary"] = summary


def validate_sample(sample, variant, operation, case, iterations):
    expected = {"schema_version": 1, "variant": variant, "operation": operation,
                "case": case, "iterations": iterations, "utf8proc_version": "2.12.0",
                "unicode_version": "18.0.0"}
    for key, value in expected.items():
        if sample.get(key) != value:
            raise ValueError(f"unexpected sample {key}: {sample.get(key)!r}, expected {value!r}")
    seconds = sample["cpu_seconds"]
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("sample has no positive finite CPU duration")
    for key in ("input_bytes", "input_scalars", "output_bytes", "output_bytes_per_operation"):
        if not isinstance(sample[key], int) or sample[key] < 0:
            raise ValueError(f"invalid sample byte/scalar count: {key}")
    if sample["output_bytes"] != sample["output_bytes_per_operation"] * iterations:
        raise ValueError("output byte total does not match the iteration count")
    checksum = sample["checksum"]
    if not isinstance(checksum, str) or len(checksum) != 16 or any(c not in "0123456789abcdef" for c in checksum):
        raise ValueError("sample has an invalid full-output checksum")
    return tuple(sample[key] for key in ("input_bytes", "input_scalars", "iterations",
                 "output_bytes_per_operation", "output_bytes", "checksum"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--small-iterations", type=int, default=20000)
    parser.add_argument("--operations", choices=("nfc", "fold"), nargs="+", default=["nfc", "fold"])
    parser.add_argument("--cases", choices=CASES, nargs="+", default=list(CASES))
    parser.add_argument("--sample-timeout", type=float, default=15.0, help="wall seconds per timing child")
    parser.add_argument("--maximum-seconds", type=float, default=240.0, help="wall cap including compilation")
    parser.add_argument("--baseline-adversarial-seconds", type=float, default=110.0,
                        help="aggregate wall cap for all baseline adversarial children, including setup")
    parser.add_argument("--revision", help="source revision metadata; defaults to MINYAR_BENCHMARK_REVISION or an available checkout")
    parser.add_argument("--branch", help="source branch metadata; defaults to MINYAR_BENCHMARK_BRANCH or an available checkout")
    parser.add_argument("--output", default="build/unicode-normalization-benchmark.json")
    options = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("run this benchmark through bx on Linux; local laptop compilation is not permitted")
    if not 1 <= options.pairs <= 32 or not 1 <= options.small_iterations <= 10000000:
        parser.error("pairs must be 1..32 and small-iterations must be 1..10000000")
    for name in ("sample_timeout", "maximum_seconds", "baseline_adversarial_seconds"):
        value = getattr(options, name)
        if not math.isfinite(value) or value <= 0:
            parser.error(name.replace("_", "-") + " must be positive and finite")
    if len(set(options.cases)) != len(options.cases) or len(set(options.operations)) != len(options.operations):
        parser.error("cases and operations must not contain duplicates")
    output = Path(options.output)
    if not output.is_absolute():
        output = ROOT / output
    started = time.monotonic()
    deadline = started + options.maximum_seconds
    baseline_adversarial_wall = 0.0
    report = {"schema_version": 1, "status": "preparing", "started_at": utc_now(),
              "machine": machine_details(), "settings": vars(options), "groups": [],
              "method": {"pairs_alternate_order": True, "fresh_process_each_sample": True,
                         "warmup_operations": 0, "timed_scope": "transform + owned Text copy + full-output FNV-1a + release",
                         "runtime_stub": "malloc/memcpy/free; excludes managed UTF-8 validation and reference counting",
                         "instrumentation": "MINYAR_UNICODE_NORMALIZATION_TESTING undefined; no operation counters",
                         "ratio_direction": "baseline/current; values greater than one favor current",
                         "adversarial_size_unit": "marks; starter cases add one scalar",
                         "adversarial_iterations": ADVERSARIAL_ITERATIONS,
                         "speedup_assertions": False}}
    active_sample = None

    def bounded(command, limit):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("overall benchmark wall budget exhausted")
        return run_capture(command, min(limit, remaining))

    def checkout_metadata(argument, environment, git_arguments):
        if argument is not None:
            return argument.strip() or None, "argument"
        if environment in os.environ:
            return os.environ[environment].strip() or None, "environment"
        # bx deliberately omits .git. Do not infer metadata from an unrelated
        # ancestor checkout, and do not make optional provenance block timing.
        if not (ROOT / ".git").exists():
            return None, "unavailable"
        try:
            value = bounded(["git", *git_arguments], 5).strip()
            return value or None, "checkout" if value else "unavailable"
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None, "unavailable"

    write_report(output, report)
    try:
        for name in FINGERPRINT_INPUTS:
            if not (ROOT / name).is_file():
                raise FileNotFoundError(f"prepare this input on bx before benchmarking: {name}; the benchmark does not generate it")
        report["source_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                   for name in FINGERPRINT_INPUTS}
        compiler = bounded(["sh", "tools/toolchain.sh", "default-clang"], 20).strip()
        if not compiler:
            raise ValueError("toolchain.sh returned no Clang executable")
        report["compiler"] = {"selected": compiler,
                              "version": bounded([compiler, "--version"], 10).strip()}
        report["git_revision"], revision_source = checkout_metadata(
            options.revision, "MINYAR_BENCHMARK_REVISION", ["rev-parse", "HEAD"])
        report["git_branch"], branch_source = checkout_metadata(
            options.branch, "MINYAR_BENCHMARK_BRANCH", ["symbolic-ref", "--quiet", "--short", "HEAD"])
        report["git_metadata_source"] = {"revision": revision_source, "branch": branch_source}
        executable = ROOT / "build/unicode-normalization-benchmark"
        executable.parent.mkdir(parents=True, exist_ok=True)
        compile_command = [compiler, "-std=c11", "-O2", "-fno-lto", "-Wall", "-Wextra", "-Werror",
                           "-UMINYAR_UNICODE_NORMALIZATION_TESTING", *SOURCES, "-lm", "-o", str(executable)]
        report["compiler"]["command"] = compile_command
        write_report(output, report)
        compile_started = time.monotonic()
        bounded(compile_command, 90)
        report["compiler"]["wall_seconds"] = time.monotonic() - compile_started
        report["executable_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
        report["status"] = "running"
        write_report(output, report)
        for operation in options.operations:
            for case in options.cases:
                iterations = iterations_for(case, options.small_iterations)
                group = {"operation": operation, "case": case, "iterations": iterations,
                         "adversarial": case not in SMALL_CASES, "samples": []}
                report["groups"].append(group)
                signature = None
                for pair_index in range(options.pairs):
                    order = ("baseline", "current") if pair_index % 2 == 0 else ("current", "baseline")
                    for order_index, variant in enumerate(order):
                        active_sample = {"operation": operation, "case": case, "variant": variant,
                                         "pair_index": pair_index, "order_index": order_index}
                        adversarial_baseline = group["adversarial"] and variant == "baseline"
                        timeout = options.sample_timeout
                        if adversarial_baseline:
                            remaining = options.baseline_adversarial_seconds - baseline_adversarial_wall
                            if remaining <= 0:
                                raise TimeoutError("aggregate baseline adversarial wall budget exhausted")
                            timeout = min(timeout, remaining)
                        command = [str(executable), "--variant", variant, "--operation", operation,
                                   "--case", case, "--iterations", str(iterations)]
                        sample_started = time.monotonic()
                        try:
                            raw = bounded(command, timeout)
                        finally:
                            elapsed = time.monotonic() - sample_started
                            if adversarial_baseline:
                                baseline_adversarial_wall += elapsed
                            report["baseline_adversarial_wall_seconds"] = baseline_adversarial_wall
                        sample = json.loads(raw)
                        current_signature = validate_sample(sample, variant, operation, case, iterations)
                        sample.update({"pair_index": pair_index, "order_index": order_index,
                                       "process_wall_seconds": elapsed})
                        group["samples"].append(sample)
                        if signature is not None and current_signature != signature:
                            raise ValueError(f"baseline/current output checksum or byte count differs for {operation}/{case}")
                        signature = current_signature
                        summarize(group, options.pairs)
                        write_report(output, report)
                active_sample = None
                print(f"{operation}/{case}: {options.pairs} alternating pairs complete", flush=True)
        report["status"] = "complete"
        return_code = 0
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        report["error"] = {"type": type(error).__name__, "message": str(error), "sample": active_sample}
        if isinstance(error, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
            report["error"]["stdout"] = error.output.decode(errors="replace") if isinstance(error.output, bytes) else error.output
            report["error"]["stderr"] = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr
        print(f"normalization benchmark {report['status']}: {error}", file=sys.stderr)
        return_code = 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        for group in report["groups"]:
            summarize(group, options.pairs)
        report["finished_at"] = utc_now()
        report["wall_seconds"] = time.monotonic() - started
        report["machine"]["load_average_end"] = list(os.getloadavg()) if hasattr(os, "getloadavg") else None
        write_report(output, report)
    print(f"Normalization benchmark {report['status']}; raw samples and ratios: {output}")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
