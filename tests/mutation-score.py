#!/usr/bin/env python3
"""Deterministic operator-mutation score over automatically discovered compiler sites."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "compiler.min"
STAGE0 = ROOT / "build" / "stage0"
COMPILER_RUNTIME = ROOT / "build" / "minyar-compiler-runtime.ll"
PROGRAM_RUNTIME = ROOT / "build" / "minyar-runtime.o"
CLANG = os.environ.get("MINYAR_TEST_CLANG", "clang")
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


def run(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 45) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=int(os.environ.get("MINYAR_MUTATION_LIMIT", "16")))
    parser.add_argument("--minimum-score", type=float, default=float(os.environ.get("MINYAR_MIN_MUTATION_SCORE", "0")))
    arguments = parser.parse_args()
    if arguments.limit < 1:
        parser.error("--limit must be positive")
    original = SOURCE.read_text(encoding="utf-8")
    all_sites = discover(original)
    selected = select_sites(all_sites, arguments.limit)
    outcomes: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="minyar-mutation-score-") as directory:
        temporary = Path(directory)
        for number, site in enumerate(selected):
            replacement = REPLACEMENTS[site.operator]
            mutated = original[: site.offset] + replacement + original[site.offset + len(site.operator) :]
            source = temporary / f"mutant-{number}.min"
            llvm = temporary / f"mutant-{number}.ll"
            compiler = temporary / f"mutant-{number}"
            source.write_text(mutated, encoding="utf-8")
            built = run([str(STAGE0), str(source), "-o", str(llvm)])
            if built is None or built.returncode != 0:
                outcomes.append({"site": site.label, "outcome": "stillborn"})
                continue
            linked = run([CLANG, "-O0", "-Wno-override-module", str(llvm), str(COMPILER_RUNTIME), "-o", str(compiler)])
            if linked is None or linked.returncode != 0:
                outcomes.append({"site": site.label, "outcome": "stillborn"})
                continue
            environment = dict(os.environ)
            environment.update(MINYAR_TEST_COMPILER=str(compiler), MINYAR_TEST_RUNTIME=str(PROGRAM_RUNTIME))
            checks = (
                [os.sys.executable, "tests/diagnostics.py"],
                [os.sys.executable, "tests/conformance.py"],
                [os.sys.executable, "tests/regressions.py"],
                [os.sys.executable, "tests/binary-expression-ownership.py"],
                [os.sys.executable, "tests/fuzz.py", "--cases", "30", "--program-cases", "8"],
                ["sh", "tests/run-module-tests.sh"],
            )
            killed_by = ""
            for check in checks:
                result = run(check, env=environment)
                if result is None:
                    killed_by = "timeout"
                    break
                if result.returncode != 0:
                    killed_by = " ".join(check[:2])
                    break
            outcome = "killed" if killed_by else "survived"
            outcomes.append({"site": site.label, "outcome": outcome, "killed_by": killed_by})
            print(f"{number + 1}/{len(selected)} {site.label}: {outcome}", flush=True)

    viable = [row for row in outcomes if row["outcome"] != "stillborn"]
    killed = [row for row in viable if row["outcome"] == "killed"]
    score = round(100.0 * len(killed) / len(viable), 2) if viable else 100.0
    report = {
        "discovered_sites": len(all_sites),
        "selected_sites": len(selected),
        "viable_mutants": len(viable),
        "killed_mutants": len(killed),
        "score_percent": score,
        "outcomes": outcomes,
    }
    report_path = ROOT / "build" / "mutation-score.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "outcomes"}, indent=2))
    print(f"mutation evidence: {report_path}")
    if score < arguments.minimum_score:
        print(f"mutation score {score}% is below required {arguments.minimum_score}%", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
