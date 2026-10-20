#!/usr/bin/env python3
"""Measure the prepared native owner study ON bx with sudo -n.

Use the build directory's frozen copy. One warmup and seven retained samples
per role are the default. Every counter/stdout/stderr/job artifact is retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import runpy
import signal
import statistics
import subprocess
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def save(path, value):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    pending.replace(path)


def identities(manifest):
    for path, expected in manifest["immutable_files"].items():
        require(Path(path).is_file() and digest(path) == expected, "study artifact changed: " + path)
    require(digest(manifest["clang"]["path"]) == manifest["clang"]["sha256"], "frozen clang changed")
    source = manifest["product_input"]
    require(digest(source["manifest"]) == source["manifest_sha256"], "complete frozen product manifest changed")


def one_measure(job_path):
    job = json.loads(job_path.read_text())
    try:
        measure = runpy.run_path(job["runner"])["measure"]
        observation = measure(job["argv"], job["stdout"], job["stderr"])
        save(job["result"], {"status": "measured", "observation": observation})
    except BaseException as error:
        save(job["result"], {"status": "failed", "error": repr(error)})
        raise


def invoke(argv, timeout, stdout_path, stderr_path):
    # One bounded wait; a timeout kills the runner and its stopped/measured child.
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(list(map(str, argv)), stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError("measurement timeout; raw logs retained: " + str(stderr_path))
    require(status == 0, "measurement worker failed; raw logs retained: " + str(stderr_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--only", nargs="+", help="optional exact workload IDs for a narrow screen")
    parser.add_argument("--one", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("measure only through bx perfcs on Linux x86_64")
    if args.one:
        one_measure(args.one)
        return
    require(args.manifest is not None and args.samples >= 1 and args.timeout > 0,
            "manifest, positive sample count and timeout required")
    manifest = json.loads(args.manifest.read_text())
    require(manifest["status"] == "ready", "study build did not complete")
    identities(manifest)
    script = Path(manifest["measurement_script"])
    require(digest(__file__) == digest(script), "use the build directory's frozen measurement script")
    selected = [work for work in manifest["workloads"] if not args.only or work["id"] in args.only]
    require(selected and (not args.only or set(args.only) == {work["id"] for work in selected}),
            "empty/unknown workload selection")
    out = (args.output or args.manifest.parent / "measurements").resolve()
    out.mkdir(parents=True, exist_ok=False)
    cpu = args.cpu if args.cpu is not None else min(os.sched_getaffinity(0))
    require(cpu in os.sched_getaffinity(0), "CPU is outside allowed affinity")
    os.sched_setaffinity(0, {cpu})
    report = {"schema": 1, "status": "measuring", "manifest": str(args.manifest.resolve()),
              "manifest_sha256": digest(args.manifest), "cpu": cpu, "samples": args.samples,
              "warmups_per_role": 1, "observations": [], "summaries": {},
              "accounting_enabled": False, "shared_native_object": True,
              "scope": "whole native workload process; user-space hardware instructions; inherited pinned counter enabled at exec; setup, final drain, cache cleanup and stdout included",
              "order": "listed roles on even rounds, reversed roles on odd rounds; round zero warmup",
              "interpretation": "isolated owner-path microstudy only; no product speedup inference",
              "seven_sample_complete_matrix": False}
    report_path = out / "results.json"
    save(report_path, report)
    common_stdout = None
    try:
        for work in selected:
            require(work["kind"] == "native" and work["units"] > 0 and work["owners"] == 8 * work["units"],
                    "unexpected workload shape")
            expected = str(work["owners"] * (work["owners"] - 1) // 2) + "\n"
            require(work["expected_stdout"] == expected and re.fullmatch(r"[0-9]+\n", expected) and int(expected) > 0,
                    "independent exact scalar oracle changed")
            require(set(work["roles"]) == {"baseline", "candidate"} and
                    work["runtime_accounting"] == {"baseline": False, "candidate": False},
                    "measured runtime accounting must be disabled in both roles")
            roles = ["baseline", "candidate"]
            for iteration in range(args.samples + 1):
                order = roles if iteration % 2 == 0 else list(reversed(roles))
                for role in order:
                    stem = out / (work["id"] + "-" + role + f"-{iteration:02d}")
                    job_path = Path(str(stem) + ".job.json")
                    counter_path = Path(str(stem) + ".counter.json")
                    job = {"runner": manifest["counter_runner"], "argv": work["roles"][role],
                           "stdout": str(stem) + ".stdout", "stderr": str(stem) + ".stderr",
                           "result": str(counter_path)}
                    save(job_path, job)
                    invoke([sys.executable, script, "--one", job_path], args.timeout,
                           Path(str(stem) + ".runner.stdout"), Path(str(stem) + ".runner.stderr"))
                    measured = json.loads(counter_path.read_text())
                    require(measured["status"] == "measured", "hardware worker failed")
                    row = measured["observation"]
                    row.update({"workload": work["id"], "role": role, "sample": iteration - 1,
                                "warmup": iteration == 0, "job_path": str(job_path),
                                "counter_path": str(counter_path), "stdout_path": job["stdout"],
                                "stderr_path": job["stderr"], "stdout_sha256": digest(job["stdout"]),
                                "stderr_sha256": digest(job["stderr"])})
                    report["observations"].append(row)
                    save(report_path, report)
                    require(row["exit"] == 0 and not Path(job["stderr"]).read_bytes(),
                            "workload failed or wrote diagnostics: " + str(stem))
                    require(row["retired_instructions"] > 0 and row["counter_scaled"] is False and
                            row["counter_running_ns"] > 0 and row["counter_running_ns"] == row["counter_enabled_ns"],
                            "counter did not run continuously and unscaled")
                    stdout = Path(job["stdout"]).read_text()
                    require(stdout == expected, "exact independent scalar stdout mismatch: " + str(stem))
                    require(common_stdout is None or common_stdout == stdout, "stdout differs across activation/owner/role modes")
                    common_stdout = stdout
                    row["exact_stdout_verified"] = True
                    save(report_path, report)
                    print(json.dumps({"workload": work["id"], "role": role, "sample": iteration - 1,
                                      "instructions": row["retired_instructions"]}), flush=True)
            summary = {}
            for role in roles:
                values = [row["retired_instructions"] for row in report["observations"]
                          if row["workload"] == work["id"] and row["role"] == role and not row["warmup"]]
                require(len(values) == args.samples, "missing retained samples")
                median = statistics.median(values)
                summary[role] = {"instructions": values, "median_instructions": median,
                                 "minimum_instructions": min(values), "maximum_instructions": max(values),
                                 "median_instructions_per_frame": median / work["units"],
                                 "median_instructions_per_owner": median / work["owners"]}
            summary["candidate_over_baseline"] = summary["candidate"]["median_instructions"] / summary["baseline"]["median_instructions"]
            summary["exact_stdout"] = expected
            report["summaries"][work["id"]] = summary
            save(report_path, report)
        identities(manifest)
        report.update({"status": "complete", "artifacts_unchanged": True,
                       "continuous_unscaled_counters": True, "semantic_outputs_identical": True,
                       "seven_sample_complete_matrix": args.samples == 7 and len(selected) == 4})
    except BaseException as error:
        report.update({"status": "failed", "error": repr(error)})
        save(report_path, report)
        raise
    save(report_path, report)
    print("CYCLE_OWNER_STUDY_MEASURED", report_path, flush=True)


if __name__ == "__main__":
    main()
