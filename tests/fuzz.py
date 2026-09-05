#!/usr/bin/env python3
"""Deterministic grammar and module-graph fuzzing for Minyar."""

from __future__ import annotations

import argparse
import os
import random
import string
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPILER = ROOT / "build" / "minyarc"
RUNTIME_SOURCE = ROOT / "runtime" / "minyar_runtime.c"
RUNTIME = ROOT / "build" / "minyar-runtime.o"
if not RUNTIME.exists():
    RUNTIME = RUNTIME_SOURCE


def run(command: list[str], *, timeout: float = 8, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def expression(random: random.Random, depth: int = 0) -> tuple[str, int]:
    if depth >= 4 or random.random() < 0.32:
        value = random.randint(-50, 50)
        return str(value) if value >= 0 else f"({value})", value
    left_source, left = expression(random, depth + 1)
    right_source, right = expression(random, depth + 1)
    operator = random.choice(["+", "-", "*"])
    value = left + right if operator == "+" else left - right if operator == "-" else left * right
    if abs(value) > 1_000_000_000:
        return expression(random, depth + 1)
    return f"({left_source} {operator} {right_source})", value


def check_expression_batch(compiler: Path, clang: str, cases: int, temporary: Path, seed: int) -> None:
    random = globals()["random"].Random(seed)
    generated = [expression(random) for _ in range(cases)]
    source = temporary / "expressions.min"
    source.write_text("".join(f"print({text})\n" for text, _ in generated), encoding="utf-8")
    llvm = temporary / "expressions.ll"
    executable = temporary / "expressions"
    compiled = run([str(compiler), str(source), str(llvm)], timeout=max(8, cases / 20))
    if compiled.returncode != 0:
        raise AssertionError(f"valid generated expressions failed:\n{compiled.stderr}")
    linked = run(
        [clang, "-O0", "-Wno-override-module", str(llvm), str(RUNTIME), "-o", str(executable)],
        timeout=30,
    )
    if linked.returncode != 0:
        raise AssertionError(f"generated LLVM was rejected:\n{linked.stderr}")
    executed = run([str(executable)])
    expected = "".join(f"{value}\n" for _, value in generated)
    if executed.returncode != 0 or executed.stdout != expected:
        raise AssertionError("generated arithmetic changed meaning between Minyar and native execution")


def check_hostile_sources(compiler: Path, cases: int, temporary: Path, timeout: float) -> None:
    random = globals()["random"].Random(0xBAD5EED)
    alphabet = string.ascii_letters + string.digits + "(){}[],:;.+-*/!<>=&|_'\" \\n\\t"
    known_internal_failures = ("List position", "Text position", "record position", "Segmentation fault", "Assertion")
    for index in range(cases):
        source = temporary / f"hostile-{index}.min"
        size = random.randint(0, 100)
        source.write_text("".join(random.choice(alphabet) for _ in range(size)), encoding="utf-8")
        try:
            result = run([str(compiler), str(source), str(temporary / f"hostile-{index}.ll")], timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise AssertionError(f"compiler hung on hostile input {index}: {source.read_text()!r}") from error
        if result.returncode < 0:
            raise AssertionError(f"compiler died from signal {-result.returncode} on hostile input {index}")
        if any(fragment in result.stderr for fragment in known_internal_failures):
            raise AssertionError(
                f"internal failure leaked for hostile input {index}: {source.read_text()!r}\n{result.stderr}"
            )
        if result.returncode not in (0, 1):
            raise AssertionError(f"unexpected compiler status {result.returncode} on hostile input {index}")


def check_regression_corpus(compiler: Path, temporary: Path) -> None:
    forbidden = ("List position", "Text position", "record position", "Segmentation fault", "Assertion")
    for source in sorted((ROOT / "tests" / "fuzz-regressions").glob("*.min")):
        result = run([str(compiler), str(source), str(temporary / f"{source.stem}.ll")], timeout=2)
        if result.returncode < 0 or any(fragment in result.stderr for fragment in forbidden):
            raise AssertionError(f"fuzz regression returned for {source.name}:\n{result.stderr}")


def check_generated_module_chain(compiler: Path, clang: str, modules: int, temporary: Path) -> None:
    module_dir = temporary / "module-chain"
    module_dir.mkdir()
    (module_dir / "module0.min").write_text(
        "public function value(): Integer {\n    return 1\n}\n", encoding="utf-8"
    )
    for index in range(1, modules):
        (module_dir / f"module{index}.min").write_text(
            f'use "./module{index - 1}.min" as previous\n\n'
            "public function value(): Integer {\n"
            "    return previous.value() + 1\n"
            "}\n",
            encoding="utf-8",
        )
    entry = module_dir / "main.min"
    entry.write_text(
        f'use "./nested/../module{modules - 1}.min" as last\n\nprint(last.value())\n', encoding="utf-8"
    )
    (module_dir / "nested").mkdir()
    first = temporary / "module-chain-first.ll"
    second = temporary / "module-chain-second.ll"
    for output in (first, second):
        compiled = run([str(compiler), str(entry), str(output)])
        if compiled.returncode != 0:
            raise AssertionError(f"generated module chain failed:\n{compiled.stderr}")
    if first.read_bytes() != second.read_bytes():
        raise AssertionError("compiling the same module graph twice was not deterministic")
    executable = temporary / "module-chain-program"
    linked = run(
        [clang, "-O0", "-Wno-override-module", str(first), str(RUNTIME), "-o", str(executable)],
        timeout=30,
    )
    if linked.returncode != 0:
        raise AssertionError(f"module-chain LLVM was rejected:\n{linked.stderr}")
    executed = run([str(executable)])
    if executed.returncode != 0 or executed.stdout != f"{modules}\n":
        raise AssertionError("generated module chain produced the wrong native result")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", type=Path, default=DEFAULT_COMPILER)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--cases", type=int, default=int(os.environ.get("MINYAR_FUZZ_CASES", "200")))
    parser.add_argument("--hostile-timeout", type=float, default=2.0)
    arguments = parser.parse_args()
    compiler = arguments.compiler.resolve()
    with tempfile.TemporaryDirectory(prefix="minyar-fuzz-") as directory:
        temporary = Path(directory)
        remaining = arguments.cases
        batch = 0
        while remaining > 0:
            batch_size = min(200, remaining)
            check_expression_batch(compiler, arguments.clang, batch_size, temporary, 0x4D494E594152 + batch)
            remaining -= batch_size
            batch += 1
        check_hostile_sources(compiler, arguments.cases, temporary, arguments.hostile_timeout)
        check_regression_corpus(compiler, temporary)
        check_generated_module_chain(compiler, arguments.clang, 24, temporary)
    print(f"deterministic fuzzing passed: {arguments.cases} expressions, {arguments.cases} hostile inputs, 24 modules")


if __name__ == "__main__":
    main()
