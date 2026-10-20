#!/usr/bin/env python3
"""Frozen source-derived collection scaling study; run ON bx perfcs only.

python3 experiments/perfcs/collections-study.py --prepare-only
sudo -n python3 build/perfcs-collections/collections-study.py \
  --measure-only build/perfcs-collections/manifest.json --samples 3

Whole-process hardware counters include construction, validation and complete
cleanup. No kernel-only cost attribution, timing threshold or speed gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import statistics
import subprocess
import sys
import time
import runpy

ROOT = Path(__file__).resolve().parents[2]
KERNELS = ["map-hash", "set-hash", "map-sparse", "map-empty", "list-add",
           "list-unique-appended", "list-aliased-appended", "text-append",
           "text-append-length", "text-join"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    pending.replace(path)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def expected(kernel, size, repeats):
    if kernel == "map-hash": checksum = 11 * repeats
    elif kernel == "set-hash": checksum = repeats
    elif kernel == "map-sparse": checksum = 2 * repeats
    elif kernel == "map-empty": checksum = repeats
    elif kernel.startswith("list-"): checksum = repeats * (17 * size * (size - 1) // 2 + 3 * size)
    else: checksum = repeats * size * 1046
    return {"kernel": kernel, "size": size, "repeats": repeats, "checksum": checksum,
            "observed_scalar_sum": repeats * size * (size + 1) if kernel == "text-append-length" else 0,
            "live_objects": 0, "live_bytes": 0, "pending": 0}


def validate(stdout, kernel, size, repeats):
    result = json.loads(stdout)
    require(all(result.get(key) == wanted for key, wanted in expected(kernel, size, repeats).items()),
            "independent semantic oracle failed: " + stdout)
    capacity = result.get("peak_capacity")
    require(isinstance(capacity, int) and capacity >= 0, "invalid observed capacity")
    if kernel.startswith("list-") or kernel in ("map-sparse", "map-empty"):
        require(capacity >= size, "actual peak capacity cannot fit initial/final size")
    return result


def invoke(command, stem, timeout=180, env=None):
    stdout_path, stderr_path = Path(str(stem) + ".stdout"), Path(str(stem) + ".stderr")
    began = time.monotonic()
    journal = Path(str(stem) + ".command.json")
    row = {"argv": list(map(str, command)), "status": "running", "timeout_seconds": timeout,
           "stdout": str(stdout_path), "stderr": str(stderr_path)}
    save(journal, row)
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(list(map(str, command)), stdout=stdout, stderr=stderr,
                                   start_new_session=True, env=env)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            row.update({"status": "timeout", "exit": 124, "wall_seconds": time.monotonic() - began,
                        "stdout_sha256": digest(stdout_path), "stderr_sha256": digest(stderr_path)})
            save(journal, row)
            raise RuntimeError("timeout; raw artifacts retained: " + str(stem))
    row.update({"status": "finished", "exit": status, "wall_seconds": time.monotonic() - began,
                "stdout_sha256": digest(stdout_path), "stderr_sha256": digest(stderr_path)})
    save(journal, row)
    require(status == 0, "command failed; raw artifacts retained: " + str(stem))
    return row


def identities(manifest):
    for path, value in manifest["immutable_files"].items():
        require(Path(path).is_file() and digest(path) == value, "immutable artifact changed: " + path)


def prepare(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    logs = out / "build-logs"
    logs.mkdir()
    manifest = {"schema": 1, "status": "building", "builds": [], "checks": [], "workloads": [],
                "sanitizer_correctness_requested": not args.no_sanitize,
                "profile": "unchanged included acyclic system/K32 runtime; testing accounting enabled; integer Text cache disabled",
                "scope": "whole process including setup, correctness checks, final validation and complete cleanup",
                "limitations": ["one host and one runtime snapshot", "not generated Minyar application code",
                    "List growth uses the real allocator; bytes copied and realloc counts are not invented or instrumented",
                    "compiler memory barriers preserve repeated API calls without adding runtime instructions",
                    "measured alias checks use old prefix length/endpoints and exhaustive final contents; small correctness runs check every old prefix",
                    "sparse Map probe combines keys enumeration and equality; population and removal are included"]}
    path = out / "manifest.json"
    save(path, manifest)
    try:
        runtime = out / "runtime-source"
        shutil.copytree(args.runtime_root.resolve(), runtime, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
        fixture = out / "collections.c"
        shutil.copy2(ROOT / "experiments/perfcs/collections.c", fixture)
        shutil.copy2(Path(__file__), out / "collections-study.py")
        shutil.copy2(ROOT / "experiments/memory/frames-instructions.py", out / "frames-instructions.py")
        clang = args.clang or subprocess.check_output(["sh", "tools/toolchain.sh", "default-clang"], cwd=ROOT, text=True).strip()
        clang = str(Path(shutil.which(clang) or clang).resolve())
        manifest["clang"] = {"path": clang, "sha256": digest(clang),
                             "version": subprocess.check_output([clang, "--version"], text=True)}
        manifest["host"] = {"kernel": platform.release(), "machine": platform.machine()}
        include = '-DMINYAR_RUNTIME_SOURCE="' + str(runtime / "minyar_runtime.c") + '"'
        variants = [("o0", ["-O0"]), ("o2", ["-O2"])]
        if not args.no_sanitize:
            variants.append(("sanitize", ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer"]))
        for variant, flags in variants:
            binary = out / ("collections-" + variant)
            command = [clang, "-std=c11", "-Wall", "-Wextra", "-Werror", *flags,
                       include, fixture, "-lm", "-pthread", "-ldl", "-o", binary]
            manifest["builds"].append(invoke(command, logs / (variant + "-build"), args.timeout))
            save(path, manifest)
            environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            for kernel in args.kernels:
                stem = logs / (variant + "-" + kernel + "-check")
                row = invoke([binary, kernel, 32, 2, "--full-check"], stem, args.timeout, environment)
                require(not Path(row["stderr"]).read_bytes(), "correctness check wrote diagnostics: " + str(stem))
                row["semantic_output"] = validate(Path(row["stdout"]).read_text(), kernel, 32, 2)
                manifest["checks"].append(row)
                save(path, manifest)
        for kernel in args.kernels:
            if kernel in ("map-hash", "set-hash"):
                sizes, repeats = [256, 512, 1024, 2048], 4096
            elif kernel in ("map-sparse", "map-empty"):
                sizes, repeats = [256, 512, 1024, 2048], 512
            elif kernel == "list-aliased-appended":
                sizes, repeats = [256, 512, 1024, 2048], 8
            elif kernel.startswith("list-"):
                sizes, repeats = [2048, 4096, 8192, 16384], 32
            else:
                sizes, repeats = [128, 256, 512, 1024], 4
            for size in sizes:
                manifest["workloads"].append({"id": kernel + "-" + str(size), "kernel": kernel,
                    "size": size, "repeats": repeats,
                    "argv": [str(out / "collections-o2"), kernel, str(size), str(repeats)],
                    "expected": expected(kernel, size, repeats)})
        manifest["runner"] = str(out / "frames-instructions.py")
        manifest["driver"] = str(out / "collections-study.py")
        manifest["immutable_files"] = {str(item): digest(item) for item in sorted(out.rglob("*"))
            if item.is_file() and "build-logs" not in item.relative_to(out).parts and item != path and item.name != "manifest.json.pending"}
        manifest["status"] = "ready"
        save(path, manifest)
    except BaseException as error:
        manifest.update({"status": "failed", "error": repr(error)})
        save(path, manifest)
        raise
    print("COLLECTIONS_READY", path, flush=True)
    return path


def one(job_path):
    job = json.loads(job_path.read_text())
    try:
        function = runpy.run_path(job["runner"])["measure"]
        observation = function(job["argv"], job["stdout"], job["stderr"])
        save(job["result"], {"status": "measured", "observation": observation})
    except BaseException as error:
        save(job["result"], {"status": "failed", "error": repr(error)})
        raise


def measure(manifest_path, args):
    require(os.geteuid() == 0, "hardware phase requires sudo -n; use --prepare-only then sudo -n ... --measure-only MANIFEST")
    manifest = json.loads(manifest_path.read_text())
    require(manifest["status"] == "ready", "build/correctness campaign incomplete")
    identities(manifest)
    require(digest(__file__) == digest(manifest["driver"]), "use the frozen collections-study.py from the build directory")
    out = args.measurement_output.resolve() if args.measurement_output else manifest_path.resolve().parent / "measurements"
    out.mkdir(parents=True, exist_ok=False)
    selected = [row for row in manifest["workloads"] if row["kernel"] in args.kernels]
    require(selected, "no selected prepared workloads")
    cpu = args.cpu if args.cpu is not None else min(os.sched_getaffinity(0))
    require(cpu in os.sched_getaffinity(0), "CPU is outside allowed affinity")
    os.sched_setaffinity(0, {cpu})
    report = {"schema": 1, "status": "measuring", "manifest": str(manifest_path.resolve()),
              "manifest_sha256": digest(manifest_path), "samples": args.samples, "warmups_per_workload": 1,
              "cpu": cpu, "counter_scope": manifest["scope"] + "; user-space only, inherited, pinned hardware event, no scaling",
              "order": "size list forward on even rounds, reversed on odd rounds, warmup round zero; kernels remain grouped",
              "observations": [], "summaries": {}, "scaling": []}
    path = out / "results.json"
    save(path, report)
    try:
        for kernel in args.kernels:
            workloads = [row for row in selected if row["kernel"] == kernel]
            if not workloads:
                continue
            semantic_outputs = {}
            for iteration in range(args.samples + 1):
                order = workloads if iteration % 2 == 0 else list(reversed(workloads))
                for work in order:
                    stem = out / (work["id"] + f"-{iteration:02d}")
                    job_path = Path(str(stem) + ".job.json")
                    job = {"runner": manifest["runner"], "argv": work["argv"],
                           "stdout": str(stem) + ".stdout", "stderr": str(stem) + ".stderr",
                           "result": str(stem) + ".counter.json"}
                    save(job_path, job)
                    invoke([sys.executable, manifest["driver"], "--one", job_path], Path(str(stem) + ".runner"), args.timeout)
                    raw = json.loads(Path(job["result"]).read_text())
                    require(raw["status"] == "measured", "hardware counter failed")
                    row = raw["observation"]
                    row.update({"workload": work["id"], "sample": iteration - 1, "warmup": iteration == 0,
                                "stdout_path": job["stdout"], "stderr_path": job["stderr"],
                                "stdout_sha256": digest(job["stdout"]), "stderr_sha256": digest(job["stderr"])})
                    report["observations"].append(row)
                    save(path, report)
                    require(row["exit"] == 0 and not Path(job["stderr"]).read_bytes(), "workload failed or wrote diagnostics: " + str(stem))
                    semantic = validate(Path(job["stdout"]).read_text(), kernel, work["size"], work["repeats"])
                    require(work["id"] not in semantic_outputs or semantic_outputs[work["id"]] == semantic, "semantic output changed across samples")
                    semantic_outputs[work["id"]] = semantic
                    row["semantic_output"] = semantic
                    save(path, report)
                    print(json.dumps({"workload": work["id"], "sample": iteration - 1,
                                      "instructions": row["retired_instructions"]}), flush=True)
            for work in workloads:
                rows = [row for row in report["observations"] if row["workload"] == work["id"] and not row["warmup"]]
                values = [row["retired_instructions"] for row in rows]
                require(len(values) == args.samples, "missing retained samples")
                report["summaries"][work["id"]] = {"kernel": kernel, "size": work["size"], "repeats": work["repeats"],
                    "instructions": values, "median_instructions": statistics.median(values), "range_instructions": [min(values), max(values)],
                    "median_user_seconds": statistics.median(row["user_seconds"] for row in rows),
                    "median_wall_ns": statistics.median(row["wall_ns"] for row in rows),
                    "semantic_output": semantic_outputs[work["id"]]}
            for previous, current in zip(workloads, workloads[1:]):
                low, high = report["summaries"][previous["id"]], report["summaries"][current["id"]]
                report["scaling"].append({"kernel": kernel, "from_size": low["size"], "to_size": high["size"],
                    "instruction_ratio": high["median_instructions"] / low["median_instructions"],
                    "interpretation": "descriptive whole-process doubling ratio; setup, allocator and validation included; no timing gate"})
            save(path, report)
        identities(manifest)
        report.update({"status": "complete", "all_semantic_oracles_passed": True,
                       "artifacts_unchanged": True, "all_counters_continuous_unscaled": True})
    except BaseException as error:
        report.update({"status": "failed", "error": repr(error)})
        save(path, report)
        raise
    save(path, report)
    print("COLLECTIONS_MEASURED", path, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/perfcs-collections")
    parser.add_argument("--runtime-root", type=Path, default=ROOT / "runtime")
    parser.add_argument("--clang")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--measure-only", type=Path)
    parser.add_argument("--measurement-output", type=Path)
    parser.add_argument("--samples", type=int, choices=range(3, 8), default=3)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--kernels", nargs="+", choices=KERNELS, default=KERNELS)
    parser.add_argument("--no-sanitize", action="store_true", help="record that sanitizer correctness checks were omitted")
    parser.add_argument("--one", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("all builds/checks/measurements must run through bx perfcs on Linux x86_64")
    if args.one:
        one(args.one)
        return
    require(args.timeout > 0 and len(set(args.kernels)) == len(args.kernels), "positive timeout and unique kernels required")
    require(not (args.prepare_only and args.measure_only), "select one prepare/measure mode")
    manifest = args.measure_only or prepare(args)
    if not args.prepare_only:
        measure(manifest, args)


if __name__ == "__main__":
    main()
