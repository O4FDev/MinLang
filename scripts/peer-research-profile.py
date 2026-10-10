#!/usr/bin/env python3
"""Measure coarse compiler phases in isolated LLVM; retain every observation.

The markers perturb optimization, so phase times diagnose costs rather than
establish production speed. Each marked run must emit byte-identical LLVM to
the unmarked compiler. Production resource measurements remain separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASES = [
    "compileEntryWithLibrary", "loadModule", "tokenize", "recordScannedDeclarations",
    "discoverRecordNames", "discoverDeclarations", "buildSymbolLookup",
    "compileTokens", "compileFunctions", "compileTopLevel",
    "collectModuleDeclarations", "appendModuleTokens",
]


def instrument_ir(source: str, names: list[str]) -> str:
    if len(names) != len(set(names)):
        raise ValueError("duplicate phase selection")
    selected = {name: index for index, name in enumerate(names)}
    seen = set()
    output = []
    active = None
    needs_entry = False
    for line in source.splitlines(keepends=True):
        declaration = re.match(r"define\b.*@(?:\"\.minyar\.fn\.([^\"]+)\"|\.minyar\.fn\.([^ (]+))\(", line)
        if declaration:
            name = declaration.group(1) or declaration.group(2)
            active = selected.get(name)
            needs_entry = active is not None
            if needs_entry:
                if name in seen:
                    raise ValueError("duplicate function definition: " + name)
                seen.add(name)
        if active is not None and re.match(r"\s*ret\b", line):
            output.append(f"  call void @peer_profile_leave(i32 {active})\n")
        output.append(line)
        if needs_entry and re.match(r"[A-Za-z0-9_.]+:", line):
            output.append(f"  call void @peer_profile_enter(i32 {active})\n")
            needs_entry = False
        if line.strip() == "}":
            if needs_entry:
                raise ValueError("selected function has no explicit entry block")
            active = None
    missing = set(names) - seen
    if missing:
        raise ValueError("missing selected functions: " + ", ".join(sorted(missing)))
    output.append("\ndeclare void @peer_profile_enter(i32)\ndeclare void @peer_profile_leave(i32)\n")
    return "".join(output)


def parse_profile(stderr: str, names: list[str]) -> dict:
    records = [line.removeprefix("peer-profile ") for line in stderr.splitlines()
               if line.startswith("peer-profile ")]
    if len(records) != 1:
        raise ValueError("missing or duplicate profile evidence")
    try:
        result = json.loads(records[0])
    except json.JSONDecodeError as error:
        raise ValueError("malformed profile evidence") from error
    if (result.get("schema") != 1 or result.get("complete") is not True
            or not isinstance(result.get("phases"), list)
            or len(result["phases"]) != len(names)):
        raise ValueError("incomplete profile evidence")
    for index, phase in enumerate(result["phases"]):
        if phase.get("id") != index:
            raise ValueError("phase identity mismatch")
        for key in ("calls", "inclusive_ns", "exclusive_ns"):
            if type(phase.get(key)) is not int or phase[key] < 0:
                raise ValueError("invalid phase counter: " + key)
        if phase["exclusive_ns"] > phase["inclusive_ns"]:
            raise ValueError("invalid elapsed accounting")
        if phase["calls"] == 0 and (phase["inclusive_ns"] or phase["exclusive_ns"]):
            raise ValueError("time reported without calls")
        phase["name"] = names[index]
    return result


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], timeout: float = 180) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {command!r}\n{result.stderr}")
    return result


def resource_probe(command: list[str], timeout: float) -> dict:
    import resource
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter_ns()
    child = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(child.pid, signal.SIGKILL)
        stdout, stderr = child.communicate()
    wall_ns = time.perf_counter_ns() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss = after.ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)
    return {"returncode": child.returncode, "timed_out": timed_out, "wall_ns": wall_ns,
            "cpu_ns": round(((after.ru_utime - before.ru_utime)
                            + (after.ru_stime - before.ru_stime)) * 1e9),
            "peak_rss_mib": rss, "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr": stderr.decode("utf-8", errors="replace"), "command": command}


def measure_existing(directory: Path, samples: int) -> None:
    phase_report = json.loads((directory / "results.json").read_text())
    if phase_report.get("status") != "passed":
        raise ValueError("cannot measure a failed or incomplete phase campaign")
    compiler = Path(phase_report["inputs"][0]["path"])
    if digest(compiler) != phase_report["inputs"][0]["sha256"]:
        raise ValueError("production compiler changed since phase observations")
    report = {"schema": 1, "phase_report": str(directory / "results.json"),
              "phase_report_sha256": digest(directory / "results.json"),
              "host": platform.platform(), "samples_per_workload": samples,
              "method": "one fresh Python worker per native process; warmup retained separately",
              "workloads": [], "status": "running"}
    try:
        for workload in phase_report["workloads"]:
            source = Path(workload["source"])
            if digest(source) != workload["source_sha256"]:
                raise ValueError("workload source changed: " + str(source))
            output = directory / (workload["name"] + ".resource.ll")
            expected = workload["observations"][0]["output_sha256"]
            observations = []
            record = {"name": workload["name"], "observations": observations}
            report["workloads"].append(record)
            for index in range(samples + 1):
                output.unlink(missing_ok=True)
                command = [str(compiler), str(source), str(output)]
                probe_command = [sys.executable, str(Path(__file__).resolve()),
                                 "--resource-probe", json.dumps(command)]
                probe = run(probe_command, timeout=40)
                observation = json.loads(probe.stdout)
                observation.update(sample=index, warmup=index == 0)
                observations.append(observation)
                if observation["returncode"] != 0 or observation["timed_out"]:
                    raise RuntimeError("production resource probe failed")
                if not output.exists() or digest(output) != expected:
                    raise RuntimeError("production resource probe emitted different LLVM")
                observation["output_sha256"] = expected
            record["summary"] = {key + "_median": statistics.median(
                observation[key] for observation in observations[1:])
                for key in ("wall_ns", "cpu_ns", "peak_rss_mib")}
            print(workload["name"], record["summary"], flush=True)
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        (directory / "production-resources.json").write_text(json.dumps(report, indent=2) + "\n")


def workloads(directory: Path) -> list[tuple[str, Path]]:
    cases = [("self", ROOT / "compiler/compiler.min")]
    for count in (500, 2000):
        path = directory / f"functions-{count}.min"
        path.write_text("".join(f"function f{i}(x: Integer): Integer {{ return x + {i} }}\n"
                                for i in range(count)) + f"print(f{count - 1}(1))\n")
        cases.append((f"functions-{count}", path))
    for count in (4000, 16000):
        path = directory / f"locals-{count}.min"
        path.write_text("function main() {\n" + "".join(f"let v{i} = {i}\n" for i in range(count))
                        + f"print(v{count - 1})\n}}\n")
        cases.append((f"locals-{count}", path))
    for width in (32, 128):
        module_dir = directory / f"modules-{width}"
        module_dir.mkdir()
        for i in range(width):
            (module_dir / f"part{i}.min").write_text(
                f"public function value(): Integer {{ return {i} }}\n")
        entry = module_dir / "main.min"
        entry.write_text("".join(f'use "./part{i}.min" as m{i}\n' for i in range(width))
                         + "let total = 0\n"
                         + "".join(f"total = total + m{i}.value()\n" for i in range(width))
                         + "print(total)\n")
        cases.append((f"modules-{width}", entry))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--compiler", type=Path, default=ROOT / "build/minyarc")
    parser.add_argument("--llvm", type=Path, default=ROOT / "build/compiler-stage2.ll")
    parser.add_argument("--runtime", type=Path, default=ROOT / "build/minyar-compiler-runtime.ll")
    parser.add_argument("--output-parent", type=Path, default=ROOT / "build/peer-research")
    parser.add_argument("--measure-existing", type=Path)
    parser.add_argument("--resource-probe", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.samples <= 101:
        parser.error("samples must be between 1 and 101")
    if args.resource_probe:
        print(json.dumps(resource_probe(json.loads(args.resource_probe), 30)))
        return
    if args.measure_existing:
        measure_existing(args.measure_existing.resolve(), args.samples)
        return
    args.output_parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="profiling-", dir=args.output_parent))
    llvm = directory / "marked.ll"
    llvm.write_text(instrument_ir(args.llvm.read_text(), PHASES))
    executable = directory / "compiler-marked"
    build_command = [args.clang, "-O2", "-flto", "-Wno-override-module", str(llvm),
                     str(args.runtime), str(ROOT / "tests/peer-research-profile-runtime.c"),
                     f"-DPEER_PROFILE_PHASES={len(PHASES)}", "-lm", "-o", str(executable)]
    run(build_command)
    report = {"schema": 1, "host": platform.platform(), "python": sys.version,
              "build_command": build_command, "samples_per_workload": args.samples,
              "inputs": [{"path": str(path), "sha256": digest(path)} for path in
                         (args.compiler, args.llvm, args.runtime,
                          ROOT / "tests/peer-research-profile-runtime.c")],
              "clock": "process CPU nanoseconds; nested exclusive accounting",
              "limitation": "instrumentation changes optimization; diagnostic timings only",
              "workloads": []}
    try:
        for name, source in workloads(directory):
            baseline = directory / f"{name}.baseline.ll"
            run([str(args.compiler), str(source), str(baseline)])
            expected = digest(baseline)
            observations = []
            marked_output = directory / f"{name}.marked.ll"
            for sample in range(args.samples + 1):
                marked_output.unlink(missing_ok=True)
                command = [str(executable), str(source), str(marked_output)]
                started = time.perf_counter_ns()
                result = run(command, timeout=30)
                wall_ns = time.perf_counter_ns() - started
                if not marked_output.exists() or digest(marked_output) != expected:
                    raise RuntimeError("instrumented compiler changed output: " + name)
                observation = parse_profile(result.stderr, PHASES)
                observation.update(sample=sample, wall_ns=wall_ns,
                                   warmup=sample == 0, command=command, output_sha256=expected)
                observations.append(observation)
            retained = observations[1:]
            summary = [{"name": phase, "exclusive_cpu_ns_median": statistics.median(
                sample["phases"][index]["exclusive_ns"] for sample in retained),
                "inclusive_cpu_ns_median": statistics.median(
                    sample["phases"][index]["inclusive_ns"] for sample in retained)}
                for index, phase in enumerate(PHASES)]
            report["workloads"].append({"name": name, "source": str(source),
                "source_sha256": digest(source), "source_bytes": source.stat().st_size,
                "observations": observations, "summary": summary})
            print(name, "verified", args.samples, "samples", flush=True)
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        print("Evidence:", directory, flush=True)


if __name__ == "__main__":
    main()
