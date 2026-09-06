#!/usr/bin/env python3
"""Feature-indexed executable conformance cases for the language specification."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get("MINYAR_TEST_COMPILER", ROOT / "build/minyarc")).resolve()
RUNTIME = Path(os.environ.get("MINYAR_TEST_RUNTIME", ROOT / "build/minyar-runtime.o")).resolve()
CLANG = os.environ.get("MINYAR_TEST_CLANG", "clang")
LINK_FLAGS = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))


def main() -> None:
    cases = sorted((ROOT / "tests" / "conformance").glob("*/program.min"))
    if not cases:
        raise AssertionError("the conformance tree is empty")
    with tempfile.TemporaryDirectory(prefix="minyar-conformance-") as directory:
        temporary = Path(directory)
        for index, source in enumerate(cases):
            expected = source.with_name("expected.stdout").read_bytes()
            llvm = temporary / f"{index}.ll"
            compile_result = subprocess.run(
                [str(COMPILER), str(source), str(llvm)], cwd=ROOT, capture_output=True, timeout=15
            )
            if compile_result.returncode != 0:
                raise AssertionError(f"{source.parent.name} did not compile:\n{compile_result.stderr.decode()}")
            for optimization in ("-O0", "-O2"):
                executable = temporary / f"{index}-{optimization[2:]}"
                link_result = subprocess.run(
                    [CLANG, optimization, *LINK_FLAGS, "-Wno-override-module", str(llvm), str(RUNTIME), "-o", str(executable)],
                    cwd=ROOT,
                    capture_output=True,
                    timeout=30,
                )
                if link_result.returncode != 0:
                    raise AssertionError(f"{source.parent.name} failed to link at {optimization}:\n{link_result.stderr.decode()}")
                run_result = subprocess.run([str(executable)], cwd=ROOT, capture_output=True, timeout=10)
                if run_result.returncode != 0 or run_result.stdout != expected or run_result.stderr:
                    raise AssertionError(
                        f"{source.parent.name} failed at {optimization}: status={run_result.returncode}, "
                        f"stdout={run_result.stdout!r}, stderr={run_result.stderr!r}"
                    )
    print(f"{len(cases)} feature-indexed conformance programs passed at O0 and O2")


if __name__ == "__main__":
    main()
