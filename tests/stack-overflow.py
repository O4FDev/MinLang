#!/usr/bin/env python3
"""Regression checks for graceful compiler and program call-depth failures."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from llvm_sanitizer import prepare_llvm_for_link


ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get("MINYAR_TEST_COMPILER", ROOT / "build/minyarc")).resolve()
RUNTIME = Path(os.environ.get("MINYAR_TEST_RUNTIME", ROOT / "build/minyar-runtime.o")).resolve()
CLANG = os.environ.get("MINYAR_TEST_CLANG", "clang")
LINK_FLAGS = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))
MESSAGE = "Minyar stopped: the program exceeded the maximum call depth.\n"


def run(command: list[str], *, timeout: float = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="minyar-stack-overflow-") as directory:
        temporary = Path(directory)

        nested = temporary / "nested.min"
        nested.write_text("print(" + "(" * 10_000 + "1" + ")" * 10_000 + ")\n", encoding="utf-8")
        compiler_result = run([str(COMPILER), str(nested), str(temporary / "nested.ll")])
        assert compiler_result.returncode in (0, 1), compiler_result
        if compiler_result.returncode == 1:
            assert compiler_result.stderr == MESSAGE, compiler_result.stderr
        else:
            assert compiler_result.stderr == "", compiler_result.stderr

        exhausting = temporary / "exhausting.min"
        exhausting.write_text(
            "print(" + "(" * 100_000 + "1" + ")" * 100_000 + ")\n",
            encoding="utf-8",
        )
        exhausted = run([str(COMPILER), str(exhausting), str(temporary / "exhausting.ll")])
        assert exhausted.returncode == 1, (
            f"exhausting compiler input returned {exhausted.returncode}: {exhausted.stderr}"
        )
        assert exhausted.stderr == MESSAGE, exhausted.stderr

        # CPython's interactive compiler also stresses this distinct recursive
        # parser path. Both native and sanitized self-hosted compilers must
        # retain the emitted call-depth guards on this path.
        unary = temporary / "unary.min"
        unary.write_text("print(" + "-" * 100_000 + "1)\n", encoding="utf-8")
        unary_llvm = temporary / "unary.ll"
        unary_result = run([str(COMPILER), str(unary), str(unary_llvm)])
        assert unary_result.returncode in (0, 1), unary_result
        assert unary_result.stdout == "", unary_result
        if unary_result.returncode == 1:
            assert unary_result.stderr == MESSAGE, unary_result
            assert not unary_llvm.exists()
        else:
            # Stack availability and backend frame sizes vary. Successful
            # compilation must still produce the independently known result.
            assert unary_result.stderr == "", unary_result
            prepare_llvm_for_link(unary_llvm, LINK_FLAGS)
            unary_executable = temporary / "unary"
            linked = run([CLANG, "-O0", *LINK_FLAGS, "-Wno-override-module", str(unary_llvm),
                          str(RUNTIME), "-o", str(unary_executable)], timeout=60)
            assert linked.returncode == 0, linked.stderr
            result = run([str(unary_executable)])
            assert (result.returncode, result.stdout, result.stderr) == (0, "1\n", ""), result

        safe_depth = 5000
        recursive = temporary / "recursive.min"
        recursive.write_text(
            "function descend(depth: Integer): Integer {\n"
            "    if depth == 0 { return 0 }\n"
            "    return 1 + descend(depth - 1)\n"
            "}\n"
            f"print(descend({safe_depth}))\n"
            "print(descend(100000000))\n",
            encoding="utf-8",
        )
        llvm = temporary / "recursive.ll"
        compiled = run([str(COMPILER), str(recursive), str(llvm)])
        assert compiled.returncode == 0, compiled.stderr
        prepare_llvm_for_link(llvm, LINK_FLAGS)
        executable = temporary / "recursive"
        linked = run([CLANG, "-O0", *LINK_FLAGS, "-Wno-override-module", str(llvm), str(RUNTIME), "-o", str(executable)])
        assert linked.returncode == 0, linked.stderr
        program_result = run([str(executable)])
        assert program_result.returncode == 1, (
            f"deep program returned {program_result.returncode}: {program_result.stderr}"
        )
        assert program_result.stdout == f"{safe_depth}\n", program_result.stdout
        assert program_result.stderr == MESSAGE, program_result.stderr

    print("compiler and generated-program stack overflows stop cleanly")


if __name__ == "__main__":
    main()
