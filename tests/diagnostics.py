#!/usr/bin/env python3
"""Byte-for-byte golden tests for the compiler's complete diagnostics."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get("MINYAR_TEST_COMPILER", ROOT / "build/minyarc")).resolve()
DIAGNOSTICS = ROOT / "tests" / "diagnostics"
SUITES = (
    (ROOT / "tests" / "errors", DIAGNOSTICS / "expected" / "errors"),
    (ROOT / "tests" / "fuzz-regressions", DIAGNOSTICS / "expected" / "fuzz-regressions"),
    (DIAGNOSTICS / "cases", DIAGNOSTICS / "expected" / "cases"),
)


def main() -> None:
    checked = 0
    with tempfile.TemporaryDirectory(prefix="minyar-diagnostics-") as directory:
        temporary = Path(directory)
        for sources, expected_directory in SUITES:
            for source in sorted(sources.glob("*.min")):
                expected_path = expected_directory / f"{source.stem}.stderr"
                if not expected_path.is_file():
                    raise AssertionError(f"missing diagnostic golden file for {source.relative_to(ROOT)}")
                output = temporary / f"{checked}.ll"
                result = subprocess.run(
                    [str(COMPILER), str(source.relative_to(ROOT)), str(output)],
                    cwd=ROOT,
                    capture_output=True,
                    timeout=10,
                )
                expected = expected_path.read_bytes()
                if b", column " not in expected:
                    raise AssertionError(
                        f"{source.name}: diagnostic golden must assert an exact column"
                    )
                if result.returncode != 1:
                    raise AssertionError(f"{source.name}: expected status 1, got {result.returncode}")
                if result.stdout:
                    raise AssertionError(f"{source.name}: unexpected standard output: {result.stdout!r}")
                if result.stderr != expected:
                    raise AssertionError(
                        f"{source.name}: diagnostic drift\nexpected {expected!r}\nactual   {result.stderr!r}"
                    )
                if output.exists():
                    raise AssertionError(f"{source.name}: invalid input left LLVM output behind")
                checked += 1
    print(f"{checked} complete compiler diagnostics match byte-for-byte golden files")


if __name__ == "__main__":
    main()
