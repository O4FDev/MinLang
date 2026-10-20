#!/usr/bin/env python3
"""Measure prepared product pairs ON bx with sudo -n; retain every raw artifact."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
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


def save(path, value):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    pending.replace(path)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def safelibs_oracle(args):
    """One DSO per fresh process; save full exact bytes, not only a hash."""
    library = ctypes.CDLL(str(args.library.resolve()))
    data = args.fixture.read_bytes()
    storage = ctypes.create_string_buffer(data)
    if args.codec == "zlib":
        library.uncompress2.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong),
                                       ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        library.uncompress2.restype = ctypes.c_int
        produced, consumed = ctypes.c_ulong(args.expected.stat().st_size), ctypes.c_ulong(len(data))
        output = ctypes.create_string_buffer(produced.value)
        status = library.uncompress2(output, ctypes.byref(produced), storage, ctypes.byref(consumed))
        require(status == 0 and produced.value == args.expected.stat().st_size and consumed.value == len(data), "zlib oracle status/length/consumption")
        decoded = output.raw[:produced.value]
        width = height = 0
    else:
        function = getattr(library, "safelibs_decode_" + args.codec)
        function.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p),
                             ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]
        function.restype = ctypes.c_int
        output, width_value, height_value = ctypes.c_void_p(), ctypes.c_uint32(), ctypes.c_uint32()
        status = function(storage, len(data), ctypes.byref(output), ctypes.byref(width_value), ctypes.byref(height_value))
        require(status == 0 and output.value, "image oracle decode status")
        width, height = width_value.value, height_value.value
        require(width == args.width and height == args.height, "image oracle dimensions")
        decoded = ctypes.string_at(output.value, width * height * 4)
        library.safelibs_free.argtypes = [ctypes.c_void_p]
        library.safelibs_free.restype = None
        library.safelibs_free(output)
    args.raw_output.write_bytes(decoded)
    library.safelibs_live_objects.argtypes = []
    library.safelibs_live_objects.restype = ctypes.c_longlong
    live = library.safelibs_live_objects()
    require(live == 0, "safelibs oracle retains managed objects")
    expected = args.expected.read_bytes()
    require(len(decoded) == len(expected), "oracle decoded length differs")
    if args.codec != "jpeg":
        require(decoded == expected, "oracle differs from independent raw expected output")
    print(json.dumps({"codec": args.codec, "bytes": len(decoded), "width": width, "height": height,
                      "live_objects": live, "sha256": digest(args.raw_output)}))


def one_measure(job_path):
    job = json.loads(job_path.read_text())
    try:
        measure = runpy.run_path(job["runner"])["measure"]
        observation = measure(job["argv"], job["stdout"], job["stderr"])
        save(job["result"], {"status": "measured", "observation": observation})
    except BaseException as error:
        save(job["result"], {"status": "failed", "error": repr(error)})
        raise


def invoke(command, timeout, stdout_path, stderr_path):
    """A single bounded wait; timeout kills the complete measurement group."""
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(list(map(str, command)), stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError("command timeout; raw logs retained: " + str(stderr_path))
    require(status == 0, "command failed; raw logs retained: " + str(stderr_path))


def semantics(work, stdout):
    if work["kind"] == "js":
        require(re.fullmatch(r"[0-9]+\n", stdout) is not None and int(stdout) > 0, "invalid JS realm live checksum")
        return {"stdout": stdout}
    value = json.loads(stdout)
    if work["kind"] == "jsmn":
        count, iterations = work["count"], work["units"]
        expected = {"tokens": count + 1, "bytes": 2 + 2 * count, "iterations": iterations,
                    "checksum": (4 * count + 1) * iterations}
        require(all(value.get(key) == wanted for key, wanted in expected.items()), "jsmn independent checksum/count oracle failed")
        require(math.isfinite(value["seconds"]) and value["seconds"] > 0, "jsmn invalid timing")
        return expected
    expected = {"codec": work["codec"], "implementation": "candidate", "iterations": work["units"],
                "encoded_bytes": Path(work["fixture"]).stat().st_size,
                "decoded_bytes": Path(work["expected"]).stat().st_size,
                "width": work["width"], "height": work["height"], "live_objects": 0}
    require(all(value.get(key) == wanted for key, wanted in expected.items()), "safelibs count/lifetime oracle failed")
    require(value["wall_ns"] > 0 and value["candidate_fnv1a64"] == value["final_fnv1a64"], "safelibs final output changed")
    tolerance = 3 if work["codec"] == "jpeg" else 0
    require(value["maximum_channel_error"] <= tolerance, "safelibs C reference tolerance failed")
    expected.update({key: value[key] for key in ("candidate_fnv1a64", "reference_fnv1a64", "final_fnv1a64", "maximum_channel_error", "zlib_version", "libpng_version")})
    return expected


def validate_identities(manifest):
    for path, expected in manifest["immutable_files"].items():
        require(Path(path).is_file() and digest(path) == expected, "build artifact changed: " + path)
    for item in manifest.get("native_references", {}).values():
        require(digest(item["path"]) == item["sha256"], "native reference changed: " + item["path"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--only", nargs="+", help="optional exact workload IDs")
    parser.add_argument("--one", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--safelibs-oracle", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--library", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--codec", choices=["zlib", "png", "jpeg"], help=argparse.SUPPRESS)
    parser.add_argument("--fixture", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--expected", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--raw-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--width", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--height", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("run only through bx perfcs on Linux x86_64")
    if args.one:
        one_measure(args.one)
        return
    if args.safelibs_oracle:
        safelibs_oracle(args)
        return
    require(args.manifest is not None and args.samples >= 1 and args.timeout > 0, "manifest, positive sample count and timeout required")
    manifest = json.loads(args.manifest.read_text())
    require(manifest["status"] == "ready", "product build was not complete")
    validate_identities(manifest)
    require(digest(__file__) == digest(manifest["measurement_script"]), "measurement driver differs from frozen script; use the build directory's copy")
    selected = [work for work in manifest["workloads"] if not args.only or work["id"] in args.only]
    require(selected and (not args.only or set(args.only) == {work["id"] for work in selected}), "unknown/empty workload selection")
    out = (args.output or args.manifest.parent / "measurements").resolve()
    out.mkdir(parents=True, exist_ok=False)
    script = Path(manifest["measurement_script"])
    cpu = args.cpu if args.cpu is not None else min(os.sched_getaffinity(0))
    require(cpu in os.sched_getaffinity(0), "selected CPU is outside allowed affinity")
    # Set affinity before forking so measured argv directly execs the workload;
    # taskset startup is absent from the counted interval.
    os.sched_setaffinity(0, {cpu})
    report = {"schema": 1, "status": "measuring", "manifest": str(args.manifest.resolve()),
              "manifest_sha256": digest(args.manifest), "samples": args.samples, "warmups_per_role": 1,
              "scope": "whole workload process plus inherited children, user-space hardware instructions; enable at exec; no counter scaling; setup/preflight/warmup/output/teardown included",
              "cpu": cpu, "order": "listed roles on even rounds, reversed roles on odd rounds; round zero warmup",
              "semantic_outputs_identical": False, "observations": [], "exact_codec_oracles": [], "summaries": {}}
    result_path = out / "results.json"
    save(result_path, report)
    expected_semantics = {}
    exact_codec_outputs = {}
    try:
        for work in selected:
            if work["kind"] == "safelibs":
                raw = {}
                for role, library in work["libraries"].items():
                    stem = out / (work["id"] + "-" + role + "-exact")
                    raw[role] = stem.with_suffix(".raw")
                    command = [sys.executable, script, "--safelibs-oracle", "--library", library,
                               "--codec", work["codec"], "--fixture", work["fixture"], "--expected", work["expected"],
                               "--raw-output", raw[role], "--width", work["width"], "--height", work["height"]]
                    invoke(command, args.timeout, stem.with_suffix(".stdout"), stem.with_suffix(".stderr"))
                    report["exact_codec_oracles"].append({"workload": work["id"], "role": role,
                                                         "raw_path": str(raw[role]), "raw_sha256": digest(raw[role])})
                    save(result_path, report)
                require(raw["baseline"].read_bytes() == raw["candidate"].read_bytes(), "exact codec baseline/candidate output mismatch: " + work["id"])
                decoded = raw["baseline"].read_bytes()
                require(work["codec"] not in exact_codec_outputs or exact_codec_outputs[work["codec"]] == decoded,
                        "exact codec output differs across ownership profiles: " + work["codec"])
                exact_codec_outputs[work["codec"]] = decoded
            roles = list(work["roles"])
            family = work["id"].removesuffix("-" + work["profile"])
            for iteration in range(args.samples + 1):
                order = roles if iteration % 2 == 0 else list(reversed(roles))
                for role in order:
                    stem = out / (work["id"] + "-" + role + f"-{iteration:02d}")
                    job_path = stem.with_suffix(".job.json")
                    one_result = stem.with_suffix(".counter.json")
                    job = {"runner": manifest["counter_runner"], "argv": work["roles"][role],
                           "stdout": str(stem) + ".stdout", "stderr": str(stem) + ".stderr", "result": str(one_result)}
                    save(job_path, job)
                    invoke([sys.executable, script, "--one", job_path], args.timeout,
                           Path(str(stem) + ".runner.stdout"), Path(str(stem) + ".runner.stderr"))
                    measured = json.loads(one_result.read_text())
                    require(measured["status"] == "measured", "hardware measurement failed")
                    row = measured["observation"]
                    row.update({"workload": work["id"], "role": role, "sample": iteration - 1,
                                "warmup": iteration == 0, "stdout_path": job["stdout"], "stderr_path": job["stderr"],
                                "stdout_sha256": digest(job["stdout"]), "stderr_sha256": digest(job["stderr"])})
                    report["observations"].append(row)
                    save(result_path, report)
                    require(row["exit"] == 0 and not Path(job["stderr"]).read_bytes(), "workload exited or wrote diagnostics: " + str(stem))
                    semantic = semantics(work, Path(job["stdout"]).read_text())
                    require(family not in expected_semantics or expected_semantics[family] == semantic,
                            "semantic output mismatch: " + str(stem))
                    expected_semantics[family] = semantic
                    row["semantic_output"] = semantic
                    save(result_path, report)
                    print(json.dumps({"workload": work["id"], "role": role, "sample": iteration - 1,
                                      "instructions": row["retired_instructions"]}), flush=True)
            summary = {}
            for role in roles:
                values = [row["retired_instructions"] for row in report["observations"]
                          if row["workload"] == work["id"] and row["role"] == role and not row["warmup"]]
                require(len(values) == args.samples, "missing retained samples")
                summary[role] = {"instructions": values, "median_instructions": statistics.median(values),
                                 "minimum_instructions": min(values), "maximum_instructions": max(values),
                                 "median_instructions_per_unit": statistics.median(values) / work["units"]}
            summary["candidate_over_baseline"] = summary["candidate"]["median_instructions"] / summary["baseline"]["median_instructions"]
            summary["semantic_output"] = expected_semantics[family]
            report["summaries"][work["id"]] = summary
            save(result_path, report)
        validate_identities(manifest)
        report.update({"status": "complete", "semantic_outputs_identical": True,
                       "artifacts_unchanged": True, "continuous_unscaled_counters": True})
    except BaseException as error:
        report.update({"status": "failed", "error": repr(error)})
        save(result_path, report)
        raise
    save(result_path, report)
    print("PRODUCTS_MEASURED", result_path, flush=True)


if __name__ == "__main__":
    main()
