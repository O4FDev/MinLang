#!/usr/bin/env python3
"""Prepared only: root runs on an existing remote Linux box after its gate.

The first child process is the one required privileged perf permission probe.
No compiler build, kernel-policy change, counter fallback, or timing analysis.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import statistics
import subprocess
import sys


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def library_digest(root):
    value = hashlib.sha256()
    for path in sorted(root.rglob("*.min")):
        value.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return value.hexdigest()


def expected_checksum(count, repeats, seed):
    values = [(seed + position * 17) % 1024 for position in range(count)]
    contribution = lambda value: value * 3 + 1 if value % 2 else 0
    total = sum(map(contribution, values))
    checksum = 0
    for round_number in range(repeats):
        slot = round_number % count
        old = values[slot]
        values[slot] = (old + 1) % 1024
        total += contribution(values[slot]) - contribution(old)
        checksum += total
    return checksum


def counter(stderr):
    rows = [row for row in csv.reader(stderr.splitlines(), delimiter=";")
            if len(row) >= 5 and row[2].strip() == "instructions:u"]
    if len(rows) != 1 or not rows[0][0].strip().isdigit():
        raise ValueError("Exactly one available instructions:u event is required")
    row = rows[0]
    try:
        running = Decimal(row[4].strip().rstrip("%"))
    except InvalidOperation as error:
        raise ValueError("Missing perf counter running percentage") from error
    if running != Decimal(100) or int(row[0]) <= 0:
        raise ValueError("Counter unavailable or reported multiplexing; no retry")
    return {"instructions": int(row[0]), "reported_running_percent": str(running),
            "counter_runtime_field": row[3].strip()}


def static_artifacts(path, out, tag):
    # Whole-function sites only. Keep full IR/assembly for exact CFG/loop review.
    symbol = r'("(?:[^"\\]|\\.)*"|[-A-Za-z$._0-9]+)'
    functions = re.compile(r'^define\b[^\n]*@' + symbol + r'\([^\n]*\)[^\n]*\{\n(.*?)^\}', re.M | re.S)
    result, generated = {}, {}
    for match in functions.finditer(path.read_text()):
        name, body = match.groups()
        name = name.strip('"')
        if name.removeprefix(".minyar.fn.").startswith("minyar_sequence_"):
            filename = "sequence-helper-" + str(len(generated)) + "." + tag + ".ll"
            (out / filename).write_text(match.group(0) + "\n")
            generated[name] = filename
        for wanted in ("immediate", "handwritten"):
            if not (name in {wanted, ".minyar.fn." + wanted} or "|" + wanted + "|" in name or name.endswith("_" + wanted)):
                continue
            (out / (wanted + "." + tag + ".ll")).write_text(match.group(0) + "\n")
            lines = [line for line in body.splitlines() if line.strip()
                     and not line.lstrip().startswith(";") and not re.match(r'^[-A-Za-z$._0-9]+:', line)]
            result[wanted] = {"symbol": name, "static_instruction_lines": len(lines),
                              "record_new_sites": sum("@minyar_record_new(" in line for line in lines),
                              "immediate_setup_marker": "immediate named recipe setup removed" in body}
    return {"selected_functions": result, "generated_sequence_snippets": generated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name("instruction-scalar.min"))
    parser.add_argument("--compiler", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--runtime", type=Path, required=True, help="One existing runtime object shared by all profiles")
    parser.add_argument("--output", type=Path, required=True, help="New artifact directory; must not exist")
    parser.add_argument("--clang", type=Path)
    parser.add_argument("--revision", help="Caller-recorded revision/change description for bx trees without .git")
    parser.add_argument("--scope-owners", action="store_true")
    parser.add_argument("--count", type=int, default=1024)
    parser.add_argument("--repeats", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=7919)
    parser.add_argument("--samples", type=int, default=7, help="Retained pairs per compiler")
    parser.add_argument("--timeout", type=int, default=180, help="Per command; not a measurement")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Remote Linux only; do not execute on the laptop")
    if not (16 <= args.count <= 16384 and 1 <= args.repeats <= 65536
            and args.count * args.repeats <= 67108864 and 0 <= args.seed <= 1048575
            and 1 <= args.samples <= 31 and 1 <= args.timeout <= 600):
        parser.error("Bounds exceeded")
    repo, out = args.repo.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands, observations = [], []
    report = {"status": "preparing", "parameters": vars(args), "observations": observations,
              "measurement": "whole selected child-process user-space retired instructions",
              "limits": ["Includes loader/main, common list setup/mutation, selected function and loops, print and teardown.",
                         "Counts are not isolated loop-region counts or elapsed-time/speed measurements.",
                         "No scaling; only counters reporting 100 percent running are accepted (perf display precision).",
                         "Warmup pair is declared in advance; every retained observation is kept.",
                         "Measured children run in sudo perf's execution context for every profile/variant.",
                         "Static instruction-line sites are not retired instruction counts."]}

    def save():
        (out / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")

    def run(argv, stem, timeout=None):
        argv = [str(value) for value in argv]
        commands.append({"stem": stem, "argv": argv})
        (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        (out / "commands.sh").write_text("\n".join(shlex.join(row["argv"]) for row in commands) + "\n")
        environment = dict(os.environ, LC_ALL="C", LANG="C")
        try:
            result = subprocess.run(argv, cwd=repo, env=environment, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=timeout or args.timeout)
        except subprocess.TimeoutExpired as error:
            decode = lambda value: value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            result = subprocess.CompletedProcess(argv, 124, decode(error.stdout), decode(error.stderr) + "\ncommand timed out\n")
        except OSError as error:
            result = subprocess.CompletedProcess(argv, 127, "", str(error) + "\n")
        (out / (stem + ".stdout")).write_text(result.stdout)
        (out / (stem + ".stderr")).write_text(result.stderr)
        (out / (stem + ".status")).write_text(str(result.returncode) + "\n")
        return result

    # Mandatory first subprocess: one probe, no fallback or policy changes.
    probe = run(["sudo", "-n", "perf", "stat", "-e", "instructions:u", "--", "true"], "perf-probe", 20)
    matches = re.findall(r'^\s*([0-9][0-9,]*)\s+instructions:u(?:\s|$)', probe.stderr, re.M)
    report["probe"] = {"argv": commands[0]["argv"], "status": probe.returncode, "stderr": probe.stderr}
    paranoid = Path("/proc/sys/kernel/perf_event_paranoid")
    if paranoid.is_file():
        report["probe"]["perf_event_paranoid"] = paranoid.read_text().strip()
    if probe.returncode or len(matches) != 1 or int(matches[0].replace(",", "")) <= 0:
        report["status"] = "counter-unavailable"
        save()
        print("Counter probe unavailable; no compilation or measurements. See " + str(out / "report.json"))
        return 77

    try:
        source = args.source.resolve()
        frozen_source = out / "source.min"
        shutil.copyfile(source, frozen_source)
        runtime = args.runtime.resolve()
        frozen_runtime = out / "runtime.o"
        shutil.copyfile(runtime, frozen_runtime)
        profiles = []
        for specification in args.compiler:
            name, separator, path = specification.partition("=")
            if not separator or not re.fullmatch(r"[A-Za-z0-9_-]+", name) or any(p["name"] == name for p in profiles):
                raise ValueError("Compiler profiles must be unique safe NAME=PATH values")
            original = Path(path).resolve()
            frozen = out / ("compiler-" + name)
            shutil.copy2(original, frozen)
            frozen.chmod(frozen.stat().st_mode | 0o100)
            profiles.append({"name": name, "original": str(original), "compiler": str(frozen), "sha256": digest(frozen)})
        selected_clang = str(args.clang) if args.clang else run(["sh", repo / "tools/toolchain.sh", "default-clang"], "clang-path").stdout.strip()
        resolved_clang = shutil.which(selected_clang)
        if not resolved_clang:
            raise ValueError("Selected Clang is not executable: " + selected_clang)
        clang = Path(resolved_clang).resolve()
        metadata = [([clang, "--version"], "clang-version"), (["sudo", "-n", "perf", "--version"], "perf-version")]
        if (repo / ".git").exists():
            metadata.extend([(["git", "-C", repo, "rev-parse", "HEAD"], "git-head"), (["git", "-C", repo, "status", "--porcelain"], "git-status")])
        elif not args.revision:
            raise ValueError("A synced tree without .git needs --revision provenance")
        for argv, stem in metadata:
            if run(argv, stem).returncode:
                raise ValueError("Metadata command failed: " + stem)
        report["identity"] = {"source_sha256": digest(frozen_source), "runner_sha256": digest(Path(__file__).resolve()),
                              "caller_revision": args.revision, "git_metadata_available": (repo / ".git").exists(),
                              "runtime_sha256": digest(frozen_runtime), "runtime_original": str(runtime),
                              "clang": str(clang), "clang_sha256": digest(clang.resolve()), "caller_uid": os.getuid(), "uname": list(os.uname()),
                              "ownership_request": "scope-owners" if args.scope_owners else "legacy", "profiles": profiles}
        library = out / "library"
        shutil.copytree(repo / "library", library)
        report["identity"]["library_min_tree_sha256"] = library_digest(library)
        for profile in profiles:
            directory = out / profile["name"]
            directory.mkdir()
            raw, optimized, assembly, executable = [directory / name for name in ("scalar.raw.ll", "scalar.O2.ll", "scalar.O2.s", "scalar")]
            compile_argv = [profile["compiler"], frozen_source, raw, "--library", library]
            if args.scope_owners:
                compile_argv.append("--scope-owners")
            build_commands = [(compile_argv, "compile"), ([clang, "-O2", "-S", "-emit-llvm", "-Wno-override-module", raw, "-o", optimized], "optimize"), ([clang, "-O2", "-S", "-Wno-override-module", raw, "-o", assembly], "assembly"), ([clang, "-O2", "-Wno-override-module", raw, frozen_runtime, "-lm", "-o", executable], "link")]
            for argv, stem in build_commands:
                if run(argv, profile["name"] + "-" + stem).returncode:
                    raise ValueError("Fixture command failed: " + profile["name"] + "-" + stem)
            profile.update({"executable": str(executable), "executable_sha256": digest(executable),
                            "raw_sha256": digest(raw), "O2_sha256": digest(optimized), "assembly_sha256": digest(assembly),
                            "static_raw": static_artifacts(raw, directory, "raw"), "static_O2": static_artifacts(optimized, directory, "O2")})
        expected = str(expected_checksum(args.count, args.repeats, args.seed)) + "\n"
        report["expected_stdout"] = expected
        save()
        for pair in range(args.samples + 1):
            phase = "warmup" if pair == 0 else "sample"
            ordered_profiles = profiles if pair % 2 == 0 else list(reversed(profiles))
            for profile in ordered_profiles:
                variants = ("i", "h") if pair % 2 == 0 else ("h", "i")
                for variant in variants:
                    stem = phase + "-" + str(pair) + "-" + profile["name"] + "-" + variant
                    argv = ["sudo", "-n", "perf", "stat", "-x", ";", "--no-big-num", "--no-scale", "-e", "instructions:u", "--", profile["executable"], variant, args.count, args.repeats, args.seed]
                    result = run(argv, stem)
                    observation = {"phase": phase, "pair": pair, "profile": profile["name"], "variant": variant,
                                   "status": result.returncode, "stem": stem, "stdout": result.stdout}
                    observations.append(observation)
                    save()
                    if result.returncode or result.stdout != expected:
                        raise ValueError("Execution/checksum failure; measurements stop: " + stem)
                    observation.update(counter(result.stderr))
                    save()
        summary = {}
        for profile in profiles:
            kept = [row for row in observations if row["phase"] == "sample" and row["profile"] == profile["name"]]
            counts = {variant: [row["instructions"] for row in kept if row["variant"] == variant] for variant in ("i", "h")}
            ratios = [next(row["instructions"] for row in kept if row["pair"] == pair and row["variant"] == "i") / next(row["instructions"] for row in kept if row["pair"] == pair and row["variant"] == "h") for pair in range(1, args.samples + 1)]
            summary[profile["name"]] = {"whole_process_median_instructions": {key: statistics.median(value) for key, value in counts.items()}, "paired_immediate_over_handwritten_instruction_ratios": ratios, "median_paired_instruction_ratio": statistics.median(ratios)}
            if digest(Path(profile["compiler"])) != profile["sha256"] or digest(Path(profile["executable"])) != profile["executable_sha256"]:
                raise ValueError("Frozen compiler/executable bytes changed")
        if digest(frozen_source) != report["identity"]["source_sha256"] or digest(frozen_runtime) != report["identity"]["runtime_sha256"]:
            raise ValueError("Frozen source/runtime bytes changed")
        if library_digest(library) != report["identity"]["library_min_tree_sha256"]:
            raise ValueError("Frozen library bytes changed")
        if digest(clang.resolve()) != report["identity"]["clang_sha256"]:
            raise ValueError("Clang bytes changed")
        report.update({"status": "complete", "instruction_summary": summary})
        save()
        print(json.dumps({"status": report["status"], "instruction_summary": summary, "artifacts": str(out)}, indent=2))
        return 0
    except Exception as error:
        report.update({"status": "incomplete", "reason": str(error)})
        save()
        print("Study stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
