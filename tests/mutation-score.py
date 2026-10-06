#!/usr/bin/env python3
"""Deterministic operator-mutation score over automatically discovered compiler sites."""

from __future__ import annotations

import argparse
import json
import hashlib
import math
import os
import subprocess
import signal
import time
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "compiler" / "compiler.min"
STAGE0 = ROOT / "build" / "stage0"
COMPILER_RUNTIME = ROOT / "build" / "minyar-compiler-runtime.ll"
PROGRAM_RUNTIME = ROOT / "build" / "minyar-runtime.o"
CLANG = os.environ.get("MINYAR_TEST_CLANG", "clang")
MATH_FLAGS = [] if os.name == "nt" else ["-lm"]
REPLACEMENTS = {"==": "!=", "!=": "==", "<=": "<", ">=": ">", "&&": "||", "||": "&&", "<": "<=", ">": ">="}


@dataclass(frozen=True)
class Site:
    offset: int
    operator: str
    line: int
    column: int

    @property
    def label(self) -> str:
        return f"line-{self.line}-column-{self.column}-{self.operator}-to-{REPLACEMENTS[self.operator]}"


def discover(source: str) -> list[Site]:
    """Find operators outside Text, Character, and comment contents."""
    sites: list[Site] = []
    index = 0
    line = 1
    line_start = 0
    quote = ""
    block_comment = False
    while index < len(source):
        if block_comment:
            if source.startswith("*/", index):
                block_comment = False
                index += 2
                continue
        elif quote:
            if source[index] == "\\":
                index += 2
                continue
            if source[index] == quote:
                quote = ""
        else:
            if source.startswith("//", index):
                newline = source.find("\n", index)
                if newline < 0:
                    break
                index = newline
                continue
            if source.startswith("/*", index):
                block_comment = True
                index += 2
                continue
            if source[index] in "\"'":
                quote = source[index]
            else:
                operator = next((value for value in REPLACEMENTS if source.startswith(value, index)), None)
                if operator:
                    if len(operator) == 1 and (
                        index == 0
                        or index + 1 >= len(source)
                        or not source[index - 1].isspace()
                        or not source[index + 1].isspace()
                    ):
                        # Exclude List<T> type delimiters; spaced single-angle
                        # operators are the project's comparison convention.
                        index += 1
                        continue
                    sites.append(Site(index, operator, line, index - line_start + 1))
                    index += len(operator)
                    continue
        if source[index] == "\n":
            line += 1
            line_start = index + 1
        index += 1
    return sites


def select_sites(sites: list[Site], limit: int) -> list[Site]:
    if limit >= len(sites):
        return sites
    # Even spacing makes the sample deterministic while spanning the entire
    # compiler rather than privileging hand-picked checks near one subsystem.
    return [sites[(position * len(sites)) // limit] for position in range(limit)]


CHECKS = (
    [os.sys.executable, "tests/diagnostics.py"],
    [os.sys.executable, "tests/conformance.py"],
    [os.sys.executable, "tests/regressions.py"],
    [os.sys.executable, "tests/compiler-hardening.py"],
    [os.sys.executable, "tests/list-access.py"],
    [os.sys.executable, "tests/list-literals.py",
     "ListLiterals.test_constants_flush_before_dynamic_effects",
     "ListLiterals.test_large_literal_has_bounded_instruction_count"],
    [os.sys.executable, "tests/linkage.py", "LanguageLinkage.test_ordinary_names_do_not_interpose_c_dependencies"],
    [os.sys.executable, "tests/binary-expression-ownership.py"],
    [os.sys.executable, "tests/readonly-parameters.py"],
    [os.sys.executable, "tests/source-map.py",
     "SourceMaps.test_full_integer_positions_shared_paths_and_sparse_legacy_origins",
     "SourceMaps.test_default_source_uses_two_coordinates_per_token_at_large_sizes",
     "SourceMaps.test_path_indices_are_sparse_and_preserve_gaps_resets_and_named_eof"],
    [os.sys.executable, "tests/symbol-order.py"],
    [os.sys.executable, "tests/fuzz.py", "--cases", "30", "--program-cases", "8"],
    ["sh", "tests/run-module-tests.sh"],
)


def run(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 45) -> subprocess.CompletedProcess[str] | None:
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=os.name != "nt")
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        stdout, stderr = process.communicate(timeout=10)
    result = subprocess.CompletedProcess(command, process.returncode,
                                         stdout.decode("utf-8", errors="backslashreplace"),
                                         stderr.decode("utf-8", errors="backslashreplace"))
    result.timed_out = timed_out
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=int(os.environ.get("MINYAR_MUTATION_LIMIT", "16")))
    parser.add_argument("--minimum-score", type=float, default=float(os.environ.get("MINYAR_MIN_MUTATION_SCORE", "0")))
    parser.add_argument("--baseline-compiler", type=Path, default=ROOT / "build/minyarc")
    arguments = parser.parse_args()
    if arguments.limit < 1:
        parser.error("--limit must be positive")
    if not math.isfinite(arguments.minimum_score) or not 0 <= arguments.minimum_score <= 100:
        parser.error("--minimum-score must be finite and between 0 and 100")
    original = SOURCE.read_text(encoding="utf-8")
    all_sites = discover(original)
    selected = select_sites(all_sites, arguments.limit)
    outcomes: list[dict[str, object]] = []
    commands: list[dict[str, object]] = []
    evidence_root = ROOT / "build/mutation"
    evidence_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="campaign-", dir=evidence_root))
    (temporary / "original.min").write_text(original, encoding="utf-8")
    gate_failure = ""
    baseline_passed = False

    def execute(command, *, phase, env=None):
        started = time.monotonic()
        try:
            result = run(command, env=env)
        except (OSError, subprocess.SubprocessError) as error:
            commands.append({"phase": phase, "command": command, "error": str(error)})
            raise
        timed_out = result is None or getattr(result, "timed_out", False)
        commands.append({"phase": phase, "command": command, "timeout_seconds": 45,
                         "elapsed_seconds": round(time.monotonic() - started, 3),
                         "timed_out": timed_out, "status": result.returncode if result else None,
                         "stdout": result.stdout if result else None, "stderr": result.stderr if result else None,
                         "compiler": env.get("MINYAR_TEST_COMPILER") if env else None,
                         "compiler_source": env.get("MINYAR_TEST_SOURCE") if env else None,
                         "runtime": env.get("MINYAR_TEST_RUNTIME") if env else None})
        return None if timed_out else result

    def environment_for(compiler, source):
        environment = dict(os.environ)
        environment.update(MINYAR_TEST_COMPILER=str(compiler), MINYAR_TEST_SOURCE=str(source),
                           MINYAR_TEST_RUNTIME=str(PROGRAM_RUNTIME))
        return environment

    try:
        baseline_environment = environment_for(arguments.baseline_compiler.resolve(), SOURCE)
        for check in CHECKS:
            result = execute(check, phase="baseline", env=baseline_environment)
            if result is None or result.returncode != 0:
                gate_failure = f"baseline failed: {' '.join(check)}"
                break
        else:
            baseline_passed = True

        for number, site in enumerate(selected if baseline_passed else []):
            replacement = REPLACEMENTS[site.operator]
            mutated = original[: site.offset] + replacement + original[site.offset + len(site.operator) :]
            source = temporary / f"mutant-{number}.min"
            llvm = temporary / f"mutant-{number}.ll"
            compiler = temporary / f"mutant-{number}"
            source.write_text(mutated, encoding="utf-8")
            row = {"site": site.label, "offset": site.offset, "line": site.line, "column": site.column,
                   "operator": site.operator, "replacement": replacement, "source": str(source)}
            built = execute([str(STAGE0), str(source), "-o", str(llvm)], phase=site.label + ":build")
            if built is None or built.returncode != 0:
                row.update(outcome="build_timeout" if built is None else "stillborn", stage="compile")
                outcomes.append(row)
                continue
            linked = execute([CLANG, "-O0", "-Wno-override-module", str(llvm), str(COMPILER_RUNTIME), *MATH_FLAGS, "-o", str(compiler)],
                             phase=site.label + ":link")
            if linked is None or linked.returncode != 0:
                row.update(outcome="build_timeout" if linked is None else "stillborn", stage="link")
                outcomes.append(row)
                continue
            killed_by = ""
            for check in CHECKS:
                result = execute(check, phase=site.label + ":test", env=environment_for(compiler, source))
                if result is None or result.returncode != 0:
                    killed_by = "timeout: " + " ".join(check) if result is None else " ".join(check)
                    break
            row.update(outcome="killed" if killed_by else "survived", killed_by=killed_by)
            outcomes.append(row)
            print(f"{number + 1}/{len(selected)} {site.label}: {row['outcome']}", flush=True)
    except (OSError, subprocess.SubprocessError) as error:
        gate_failure = f"campaign infrastructure failed: {error}"

    viable = [row for row in outcomes if row["outcome"] in ("killed", "survived")]
    killed = [row for row in viable if row["outcome"] == "killed"]
    score = round(100.0 * len(killed) / len(viable), 2) if viable else None
    if not gate_failure:
        if any(row["outcome"] == "build_timeout" for row in outcomes):
            gate_failure = "mutant builds timed out; campaign is incomplete"
        elif not viable:
            gate_failure = "no viable mutants were tested"
        elif 100.0 * len(killed) / len(viable) < arguments.minimum_score:
            gate_failure = f"mutation score {score}% is below required {arguments.minimum_score}%"
    report = {"source_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
              "baseline_compiler": str(arguments.baseline_compiler.resolve()), "baseline_passed": baseline_passed,
              "discovered_sites": len(all_sites), "selected_sites": len(selected),
              "viable_mutants": len(viable), "killed_mutants": len(killed),
              "stillborn_mutants": sum(row["outcome"] == "stillborn" for row in outcomes),
              "build_timeouts": sum(row["outcome"] == "build_timeout" for row in outcomes),
              "minimum_score_percent": arguments.minimum_score, "score_percent": score,
              "gate_failure": gate_failure, "evidence_directory": str(temporary),
              "outcomes": outcomes, "commands": commands}
    report["artifact_sha256"] = {
        str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        for path in (arguments.baseline_compiler, STAGE0, COMPILER_RUNTIME, PROGRAM_RUNTIME)
    }
    report_path = ROOT / "build/mutation-score.json"
    report_text = json.dumps(report, indent=2) + "\n"
    report_path.write_text(report_text, encoding="utf-8")
    (temporary / "results.json").write_text(report_text, encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in ("outcomes", "commands")}, indent=2))
    print(f"mutation evidence: {temporary}")
    if gate_failure:
        print(f"mutation gate failed: {gate_failure}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
