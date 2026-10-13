#!/usr/bin/env python3
"""Freeze and run the shared FrozenBytes scaling qualification on eight CPUs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import shutil
import statistics
import subprocess
import sys
import time

WIDTHS = (1, 2, 4, 8)
ROUNDS = 40
WARMUPS = 3
ORDER_SEED = 20261012
BOOTSTRAP_SEED = 424242
BOOTSTRAPS = 20000
ROOT = Path(__file__).resolve().parents[1]
WORKLOAD = ROOT / "benchmarks/concurrency/frozen-lcg.min"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def oracle() -> str:
    factor = pow(48271, 4096, 2147483647)
    total = sum(((block * 104729 + 20261012) % 2147483647) * factor % 2147483647
                for block in range(131072))
    return str(total) + "\n"


def schedule(rounds: int, seed: int) -> list[list[int]]:
    generator = random.Random(seed)
    result = []
    for _ in range(rounds):
        order = list(WIDTHS)
        generator.shuffle(order)
        result.append(order)
    return result


def cpu_ticks() -> dict[int, list[int]]:
    result = {}
    for line in Path("/proc/stat").read_text().splitlines():
        name, *fields = line.split()
        if name.startswith("cpu") and name[3:].isdigit():
            # guest/guest_nice already belong to user/nice; do not double count.
            result[int(name[3:])] = [int(v) for v in fields[:8]]
    return result


def cpu_activity(before: dict[int, list[int]], after: dict[int, list[int]],
                 cpus: list[int], child_seconds: float = 0) -> dict[str, float]:
    ticks = [sum(after[cpu][i] - before[cpu][i] for cpu in cpus) for i in range(8)]
    total = sum(ticks)
    if total <= 0:
        raise RuntimeError("CPU accounting interval is too short")
    busy = total - ticks[3] - ticks[4] - ticks[7]
    child_ticks = child_seconds * os.sysconf("SC_CLK_TCK")
    return {"other_busy_fraction": max(0, busy - child_ticks) / total,
            "steal_fraction": ticks[7] / total}


def quiet(activity: dict[str, float]) -> bool:
    return activity["other_busy_fraction"] <= .02 and activity["steal_fraction"] <= .005


def bootstrap_interval(values: list[float]) -> tuple[float, float]:
    if len(values) != ROUNDS:
        raise ValueError("all 40 paired rounds are required")
    generator = random.Random(BOOTSTRAP_SEED)
    estimates = sorted(statistics.median(generator.choices(values, k=len(values)))
                       for _ in range(BOOTSTRAPS))
    return (estimates[math.floor(.025 * (BOOTSTRAPS - 1))],
            estimates[math.ceil(.975 * (BOOTSTRAPS - 1))])


def write_new(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def register(arguments: argparse.Namespace) -> None:
    if sys.platform != "linux":
        raise RuntimeError("qualification requires the admitted Linux Boat host")
    cpus = sorted(os.sched_getaffinity(0))
    if len(cpus) != 8:
        raise RuntimeError(f"exactly eight available CPUs required, found {cpus}")
    executable = arguments.executable.resolve(strict=True)
    lowered = arguments.lowered_llvm.resolve(strict=True)
    llvm = lowered.read_text()
    if '; minyar-thread-runtime: 1' not in llvm or not all(
            ('@' + symbol) in llvm for symbol in ('minyar_thread_spawn', 'minyar_frozen_bytes_take')):
        raise RuntimeError('lowered program must use the checked managed thread/shared-value API')
    clang = Path(shutil.which(arguments.clang) or arguments.clang).resolve(strict=True)
    quota = {}
    for name in ("/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
                 "/sys/fs/cgroup/cpu/cpu.cfs_period_us", "/proc/self/cgroup"):
        path = Path(name)
        quota[name] = path.read_text() if path.exists() else "not exposed in guest"
    protocol = {
        "frozen_at_unix_ns": time.time_ns(), "executable": str(executable),
        "executable_sha256": digest(executable), "workload_sha256": digest(WORKLOAD),
        "lowered_llvm": str(lowered), "lowered_llvm_sha256": digest(lowered),
        "sampler_sha256": digest(Path(__file__)), "expected_stdout": oracle(),
        "source_shas": {"candidate": arguments.candidate_sha,
                        "compiler": arguments.compiler_sha, "runtime": arguments.runtime_sha},
        "build_flags": arguments.build_flags, "memory_profile": arguments.memory_profile,
        "python": sys.version, "toolchain": subprocess.check_output(
            [arguments.clang, "--version"], text=True),
        "clang_path": str(clang), "clang_sha256": digest(clang), "kernel": list(os.uname()),
        "guest_topology": subprocess.check_output(["lscpu", "-J"], text=True),
        "affinity": cpus, "quota": quota,
        "work": {"blocks": 131072, "dependent_steps_per_block": 4096,
                 "seed": 20261012, "input_bytes": 1048576,
                 "kernel": "x = x * 48271 % 2147483647; sum final x per block"},
        "timing": "whole executable wall time: input creation, publication, launch, work, join, output",
        "warmup_order": schedule(WARMUPS, ORDER_SEED + 1),
        "paired_order": schedule(ROUNDS, ORDER_SEED),
        "estimator": "median of 40 within-round T1/Tn ratios",
        "interval": {"method": "paired percentile bootstrap of median ratios",
                     "replicates": BOOTSTRAPS, "seed": BOOTSTRAP_SEED,
                     "bounds": "floor(.025*(B-1)), ceil(.975*(B-1))"},
        "quiet": {"preflight_seconds": 5, "other_busy_fraction_max": .02,
                  "steal_fraction_max": .005, "no_post_result_sample_exclusion": True},
        "gates": {"median_eight_min": 7.2, "lower_95_eight_min": 6.4},
    }
    protocol["protocol_sha256"] = hashlib.sha256(canonical(protocol)).hexdigest()
    write_new(arguments.protocol, protocol)
    print(f"frozen {arguments.protocol}; no timed qualification has run")


def run(arguments: argparse.Namespace) -> None:
    protocol = json.loads(arguments.protocol.read_text())
    seal = protocol.pop("protocol_sha256")
    if hashlib.sha256(canonical(protocol)).hexdigest() != seal:
        raise RuntimeError("frozen protocol changed")
    for path, key in ((Path(protocol["executable"]), "executable_sha256"),
                      (WORKLOAD, "workload_sha256"), (Path(__file__), "sampler_sha256"),
                      (Path(protocol['lowered_llvm']), 'lowered_llvm_sha256'),
                      (Path(protocol['clang_path']), 'clang_sha256')):
        if digest(path) != protocol[key]:
            raise RuntimeError(f"frozen artifact changed: {path}")
    if sorted(os.sched_getaffinity(0)) != protocol["affinity"]:
        raise RuntimeError("affinity changed since registration")
    if sys.version != protocol['python'] or list(os.uname()) != protocol['kernel']:
        raise RuntimeError('Python or kernel changed since registration')
    if subprocess.check_output(['lscpu', '-J'], text=True) != protocol['guest_topology']:
        raise RuntimeError('CPU topology changed since registration')
    for name, expected in protocol['quota'].items():
        path = Path(name)
        if (path.read_text() if path.exists() else 'not exposed in guest') != expected:
            raise RuntimeError('CPU quota/cgroup configuration changed since registration')
    if protocol["paired_order"] != schedule(ROUNDS, ORDER_SEED):
        raise RuntimeError("paired order or sample count changed")
    before = cpu_ticks()
    time.sleep(5)
    activity = cpu_activity(before, cpu_ticks(), protocol["affinity"])
    result = {"protocol_sha256": seal, "started_unix_ns": time.time_ns(),
              "preflight": activity, "samples": [], "qualified": False}
    # Retain failed and interrupted runs; never overwrite or filter their samples.
    with arguments.results.open("x") as stream:
        def save() -> None:
            stream.seek(0)
            json.dump(result, stream, indent=2)
            stream.write("\n")
            stream.truncate()
            stream.flush()
        save()
        if not quiet(activity):
            raise RuntimeError("host failed frozen quiet criterion; retained unqualified run")
        try:
            for phase, orders in (("warmup", protocol["warmup_order"]),
                                  ("paired", protocol["paired_order"])):
                for round_index, order in enumerate(orders):
                    for width in order:
                        before = cpu_ticks()
                        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                        started = time.perf_counter_ns()
                        completed = subprocess.run([protocol["executable"], str(width)],
                                                   capture_output=True, text=True, timeout=120)
                        seconds = (time.perf_counter_ns() - started) / 1e9
                        after_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                        child_seconds = (after_usage.ru_utime + after_usage.ru_stime -
                                         usage.ru_utime - usage.ru_stime)
                        activity = cpu_activity(before, cpu_ticks(), protocol["affinity"], child_seconds)
                        sample = {"phase": phase, "round": round_index, "threads": width,
                                  "seconds": seconds, "child_cpu_seconds": child_seconds,
                                  "activity": activity, "returncode": completed.returncode,
                                  "stdout": completed.stdout, "stderr": completed.stderr}
                        result["samples"].append(sample)
                        save()
                        if (completed.returncode, completed.stdout, completed.stderr) != (
                                0, protocol["expected_stdout"], ""):
                            raise RuntimeError("incorrect workload result; retained unqualified run")
            ratios = {width: [] for width in WIDTHS}
            for round_index in range(ROUNDS):
                paired = {s["threads"]: s["seconds"] for s in result["samples"]
                          if s["phase"] == "paired" and s["round"] == round_index}
                for width in WIDTHS:
                    ratios[width].append(paired[1] / paired[width])
            result["scaling"] = {width: {"median": statistics.median(values),
                                        "interval_95": bootstrap_interval(values)}
                                 for width, values in ratios.items()}
            eight = result["scaling"][8]
            result["quiet_all_samples"] = all(quiet(s["activity"]) for s in result["samples"])
            result["qualified"] = (result["quiet_all_samples"] and eight["median"] >= 7.2
                                   and eight["interval_95"][0] >= 6.4)
        except BaseException as error:
            result["failure"] = str(error)
            save()
            raise
        result["finished_unix_ns"] = time.time_ns()
        save()
    print(json.dumps({"qualified": result["qualified"], "scaling": result["scaling"]}, indent=2))
    if not result["qualified"]:
        raise SystemExit("frozen scaling gate failed; diagnose without changing thresholds")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("register")
    freeze.add_argument("executable", type=Path)
    freeze.add_argument("protocol", type=Path)
    freeze.add_argument('--lowered-llvm', type=Path, required=True)
    for name in ("candidate-sha", "compiler-sha", "runtime-sha", "build-flags"):
        freeze.add_argument("--" + name, required=True)
    freeze.add_argument("--memory-profile", choices=("system", "eager"), required=True)
    freeze.add_argument("--clang", default="clang")
    campaign = commands.add_parser("run")
    campaign.add_argument("protocol", type=Path)
    campaign.add_argument("results", type=Path)
    arguments = parser.parse_args()
    (register if arguments.command == "register" else run)(arguments)


if __name__ == "__main__":
    main()
