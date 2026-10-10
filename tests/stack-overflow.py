#!/usr/bin/env python3
"""Regression checks for graceful compiler and program call-depth failures."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from clang_helpers import clang_command
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
        linked = run(clang_command([CLANG, "-O0", *LINK_FLAGS, "-Wno-override-module", str(llvm), str(RUNTIME), "-o", str(executable)]))
        assert linked.returncode == 0, linked.stderr
        program_result = run([str(executable)])
        assert program_result.returncode == 1, (
            f"deep program returned {program_result.returncode}: {program_result.stderr}"
        )
        assert program_result.stdout == f"{safe_depth}\n", program_result.stdout
        assert program_result.stderr == MESSAGE, program_result.stderr

        # Functions that call no Minyar function carry no call-depth check of
        # their own (so LLVM can inline them); they run in the reserve the
        # caller's check left. A leaf doing runtime Text work at the deepest
        # allowed frame must still finish, and the overflow still stops cleanly.
        leaves = temporary / "leaves.min"
        (temporary / "helpers.min").write_text(
            "public function twice(value: Integer): Integer { return value * 2 }\n", encoding="utf-8")
        leaves.write_text(
            'use "./helpers.min" as helpers\n'
            "function leaf(value: Integer): Integer {\n"
            '    let text = "value " + Text(value) + " " + Text(value * 3)\n'
            "    return text.length\n"
            "}\n"
            "function caller(value: Integer): Integer { return helpers.twice(value) }\n"
            # More temporaries than a leaf may have: its frame could outgrow
            # the reserve unoptimized, so it keeps its own check.
            "function large(value: Integer): Integer { return " + " + ".join(["value * 3"] * 600) + " }\n"
            "function descend(depth: Integer): Integer {\n"
            "    if depth == 0 { return leaf(7) }\n"
            "    return leaf(depth) - leaf(depth) + descend(depth - 1)\n"
            "}\n"
            f"print(descend({safe_depth}) + caller(1) + large(0))\n"
            "print(descend(100000000))\n",
            encoding="utf-8",
        )
        leaves_llvm = temporary / "leaves.ll"
        compiled = run([str(COMPILER), str(leaves), str(leaves_llvm)])
        assert compiled.returncode == 0, compiled.stderr
        ir = leaves_llvm.read_text()

        def body(name: str) -> str:
            found = re.search(r"^define [^\n]*@\.minyar\.fn\.(?:minyar_module_\d+_)?" + name + r"\(.*?^\}", ir, re.M | re.S)
            assert found, name
            return found.group(0)

        assert "@minyar_stack_enter" not in body("leaf") and "@minyar_stack_leave" not in body("leaf"), body("leaf")
        assert body("descend").count("call void @minyar_stack_enter()") == 1, body("descend")
        assert body("caller").count("call void @minyar_stack_enter()") == 1, body("caller")
        assert body("large").count("call void @minyar_stack_enter()") == 1, "a large leaf keeps its check"
        prepare_llvm_for_link(leaves_llvm, LINK_FLAGS)
        leaves_executable = temporary / "leaves"
        linked = run(clang_command([CLANG, "-O0", *LINK_FLAGS, "-Wno-override-module", str(leaves_llvm), str(RUNTIME),
                                    "-o", str(leaves_executable)]))
        assert linked.returncode == 0, linked.stderr
        leaves_result = run([str(leaves_executable)])
        assert (leaves_result.returncode, leaves_result.stdout, leaves_result.stderr) == (1, "12\n", MESSAGE), leaves_result

    print("compiler and generated-program stack overflows stop cleanly")


if __name__ == "__main__":
    main()
