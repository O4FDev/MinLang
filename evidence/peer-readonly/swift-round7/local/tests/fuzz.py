#!/usr/bin/env python3
"""Deterministic grammar and module-graph fuzzing for Minyar."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shlex
import signal
import string
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPILER = Path(os.environ.get("MINYAR_TEST_COMPILER", ROOT / "build" / "minyarc"))
RUNTIME_SOURCE = ROOT / "runtime" / "minyar_runtime.c"
RUNTIME = Path(os.environ.get("MINYAR_TEST_RUNTIME", ROOT / "build" / "minyar-runtime.o"))
if "MINYAR_TEST_RUNTIME" not in os.environ and not RUNTIME.exists():
    RUNTIME = RUNTIME_SOURCE
LINK_FLAGS = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))
MATH_FLAGS = [] if os.name == "nt" else ["-lm"]
COMMANDS: list[dict[str, object]] = []
INTERNAL_FAILURES = ("List position", "Text position", "record position", "Segmentation fault", "Assertion",
                     "AddressSanitizer", "UndefinedBehaviorSanitizer", "runtime error:")


def run(command: list[str], *, timeout: float = 8, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
    COMMANDS.append({"command": command, "cwd": str(cwd), "timeout_seconds": timeout,
                     "elapsed_seconds": round(time.monotonic() - started, 3),
                     "status": result.returncode, "timed_out": timed_out,
                     "stdout": result.stdout, "stderr": result.stderr})
    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout, result.stdout, result.stderr)
    return result


def assert_execution(result: subprocess.CompletedProcess[str], expected: str, context: str) -> None:
    if result.returncode != 0 or result.stdout != expected or result.stderr:
        raise AssertionError(f"{context}: status={result.returncode}, expected={expected!r}, "
                             f"stdout={result.stdout!r}, stderr={result.stderr!r}")


def expression(random: random.Random, depth: int = 0) -> tuple[str, int]:
    if depth >= 4 or random.random() < 0.32:
        value = random.randint(-50, 50)
        return str(value) if value >= 0 else f"({value})", value
    left_source, left = expression(random, depth + 1)
    right_source, right = expression(random, depth + 1)
    operator = random.choice(["+", "-", "*", "/", "%"])
    if operator in ("/", "%") and right == 0:
        operator = "+"
    quotient = (abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1) if right else 0
    value = {"+": lambda: left + right, "-": lambda: left - right,
             "*": lambda: left * right, "/": lambda: quotient,
             "%": lambda: left - quotient * right}[operator]()
    if abs(value) > 1_000_000_000:
        return expression(random, depth + 1)
    return f"({left_source} {operator} {right_source})", value


def check_expression_batch(compiler: Path, clang: str, cases: int, temporary: Path, seed: int) -> None:
    random = globals()["random"].Random(seed)
    generated = [expression(random) for _ in range(cases)]
    source = temporary / f"expressions-{seed}.min"
    source.write_text("".join(f"print({text})\n" for text, _ in generated), encoding="utf-8")
    llvm = source.with_suffix(".ll")
    compiled = run([str(compiler), str(source), str(llvm)], timeout=max(8, cases / 20))
    if compiled.returncode != 0:
        raise AssertionError(f"valid generated expressions failed:\n{compiled.stderr}")
    expected = "".join(f"{value}\n" for _, value in generated)
    source.with_suffix(".expected.stdout").write_text(expected, encoding="utf-8")
    execute_llvm(clang, llvm, expected)


def execute_llvm(clang: str, llvm: Path, expected: str) -> None:
    for optimization in ("-O0", "-O2"):
        executable = llvm.with_name(f"{llvm.stem}-{optimization[2:]}")
        linked = run([clang, optimization, *LINK_FLAGS, "-Wno-override-module", str(llvm),
                      str(RUNTIME), *MATH_FLAGS, "-o", str(executable)], timeout=30)
        if linked.returncode != 0:
            raise AssertionError(f"{llvm.name} rejected at {optimization}:\n{linked.stderr}")
        assert_execution(run([str(executable)]), expected, f"{llvm.name} changed meaning at {optimization}")


def semantic_program(cases: int, seed: int, outlined: bool) -> tuple[str, str]:
    """Python's unbounded integers model only deliberately defined Minyar operations."""
    rng = random.Random(seed)
    lines = ["function identity(value: Integer): Integer { return value }",
             "function mark(values: List<Integer>): Boolean { values.add(1); return true }",
             "function sumOdd(limit: Integer): Integer {",
             "    let total = 0",
             "    for value in 0..100 {",
             "        if value >= limit { break }",
             "        if value % 2 == 0 { continue }",
             "        total = total + value",
             "    }",
             "    return total",
             "}"]
    expected: list[str] = []
    boundaries = [-9223372036854775808, -9223372036854775807, -1, 0, 1, 9223372036854775806, 9223372036854775807]
    for value in boundaries:
        term = f"identity({value})" if outlined else f"({value})"
        lines.append(f"print({term} + 0)")
        expected.append(str(value))
    for index in range(cases):
        source, value = expression(rng)
        term = f"identity({source})" if outlined else source
        lines += [f"print({term})", f"print(({term} + 7) - 7)"]
        expected += [str(value), str(value)]
        left, right = rng.randint(-1000, 1000), rng.randint(-1000, 1000)
        for operator, result in [("<", left < right), ("<=", left <= right), (">", left > right),
                                 (">=", left >= right), ("==", left == right), ("!=", left != right)]:
            lines.append(f"print(({left}) {operator} ({right}))")
            expected.append(str(result).lower())
        limit = rng.randrange(0, 20)
        lines.append(f"print(sumOdd({limit}))")
        expected.append(str(sum(value for value in range(limit) if value % 2)))
        lines += [f"let state{index}: List<Integer> = []", f"print(false && mark(state{index}))",
                  f"print(true || mark(state{index}))", f"print(state{index}.length)",
                  f"print(true && mark(state{index}))", f"print(false || mark(state{index}))",
                  f"print(state{index}.length)"]
        expected += ["false", "true", "0", "true", "true", "2"]
        shift = rng.randrange(0, 8)
        lines += [f"print(({left}) >> {shift})", f"print(({left}) ^ ({right}))"]
        expected += [str(left >> shift), str(left ^ right)]
        byte_value = rng.randrange(-32768, 32768)
        lines += [f"let bytes{index} = Bytes(1)", f"bytes{index}.addInt16({byte_value})",
                  f"let alias{index} = bytes{index}", f"alias{index}[0] = 255",
                  f"print(bytes{index}[0])", f"print(bytes{index}.getInt16(1))",
                  f"print(bytes{index}[1])", f"print(bytes{index}[2])"]
        expected += ["255", str(byte_value), str(byte_value & 255), str((byte_value >> 8) & 255)]
        numerator = rng.randint(-1000, 1000)
        lines.append(f"print(Integer(Float({numerator}) / 4.0))")
        expected.append(str((abs(numerator) // 4) * (-1 if numerator < 0 else 1)))
    return "\n".join(lines) + "\n", "\n".join(expected) + "\n"


def check_semantic_relations(compiler: Path, clang: str, cases: int, temporary: Path, seed: int) -> None:
    for outlined in (False, True):
        source_text, expected = semantic_program(cases, seed, outlined)
        source = temporary / f"semantic-{'outlined' if outlined else 'direct'}.min"
        source.write_text(source_text, encoding="utf-8")
        source.with_suffix(".expected.stdout").write_text(expected, encoding="utf-8")
        llvm = source.with_suffix(".ll")
        result = run([str(compiler), str(source), str(llvm)], timeout=max(20, cases))
        if result.returncode != 0:
            raise AssertionError(f"valid semantic program rejected: {result.stderr}")
        execute_llvm(clang, llvm, expected)


def check_language_surface(compiler: Path, clang: str, cases: int, temporary: Path, seed: int) -> None:
    """Generate typed programs spanning the ordinary language, not just expressions."""
    rng = random.Random(seed)
    source_lines = [
        "record FuzzPair { left: Integer; right: Integer }",
        "record FuzzBox { label: Text; values: List<Integer>; pair: FuzzPair }",
        "function total(values: List<Integer>): Integer {",
        "    let result = 0",
        "    let position = 0",
        "    while position < values.length {",
        "        result = result + values[position]",
        "        position = position + 1",
        "    }",
        "    return result",
        "}",
        "function choose(left: Integer, right: Integer, takeLeft: Boolean): Integer {",
        "    if takeLeft { return left } else { return right }",
        "}",
    ]
    expected: list[str] = []
    labels = ["ascii", "éclair", "界", "🙂", "e\u0301"]
    for index in range(cases):
        original_values = [rng.randint(-500, 500) for _ in range(rng.randint(1, 6))]
        replacement = rng.randint(-500, 500)
        appended = rng.randint(-500, 500)
        replace_at = rng.randrange(len(original_values))
        values = list(original_values)
        values[replace_at] = replacement
        left, right = rng.randint(-1000, 1000), rng.randint(-1000, 1000)
        take_left = bool(rng.getrandbits(1))
        label = rng.choice(labels) + str(index)
        prefix_length = rng.randrange(len(label) + 1)
        name = f"values{index}"
        source_lines.append(f"let {name}: List<Integer> = []")
        for value in original_values:
            source_lines.append(f"{name}.add({value})")
        source_lines.append(f"{name}[{replace_at}] = {replacement}")
        source_lines.append(f"let pair{index} = FuzzPair {{ left: {left}; right: {right} }}")
        source_lines.append(
            f'let box{index} = FuzzBox {{ label: "{label}" + ""; values: {name}; pair: pair{index} }}'
        )
        source_lines.append(f"print(total(box{index}.values))")
        source_lines.append(f"let appended{index} = box{index}.values.appended({appended})")
        source_lines.append(f"print(total(appended{index}))")
        source_lines.append(f"print(box{index}.values.length)")
        source_lines.append(
            f"print(choose(box{index}.pair.left, box{index}.pair.right, {'true' if take_left else 'false'}))"
        )
        source_lines.append(f"print(box{index}.label.slice(0, {prefix_length}))")
        source_lines.append(f"let pieces{index}: List<Text> = []")
        midpoint = len(label) // 2
        source_lines.append(f'pieces{index}.add("{label[:midpoint]}")')
        source_lines.append(f'pieces{index}.add("{label[midpoint:]}")')
        source_lines.append(f"print(joinText(pieces{index}) == box{index}.label)")
        expected.extend(
            [str(sum(values)), str(sum(values) + appended), str(len(values)),
             str(left if take_left else right), label[:prefix_length], "true"]
        )

    source = temporary / "language-surface.min"
    source.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
    llvm = temporary / "language-surface.ll"
    compiled = run([str(compiler), str(source), str(llvm)], timeout=max(20, cases))
    if compiled.returncode != 0:
        raise AssertionError(f"valid generated language program failed:\n{compiled.stderr}\n{source.read_text()}")
    expected_text = "\n".join(expected) + "\n"
    source.with_suffix(".expected.stdout").write_text(expected_text, encoding="utf-8")
    for optimization in ("-O0", "-O2"):
        executable = temporary / f"language-surface-{optimization[2:]}"
        linked = run(
            [clang, optimization, *LINK_FLAGS, "-Wno-override-module", str(llvm), str(RUNTIME), *MATH_FLAGS, "-o", str(executable)],
            timeout=30,
        )
        if linked.returncode != 0:
            raise AssertionError(f"generated language LLVM was rejected at {optimization}:\n{linked.stderr}")
        executed = run([str(executable)])
        assert_execution(executed, expected_text, f"generated language program changed meaning at {optimization}")


def check_hostile_sources(compiler: Path, cases: int, temporary: Path, timeout: float, seed: int = 0xBAD5EED) -> None:
    random = globals()["random"].Random(seed)
    alphabet = string.ascii_letters + string.digits + "(){}[],:;.+-*/!<>=&|_'\" \n\t"
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
        if any(fragment in result.stderr for fragment in INTERNAL_FAILURES):
            raise AssertionError(
                f"internal failure leaked for hostile input {index}: {source.read_text()!r}\n{result.stderr}"
            )
        if result.returncode not in (0, 1):
            raise AssertionError(f"unexpected compiler status {result.returncode} on hostile input {index}")


def check_regression_corpus(compiler: Path, temporary: Path) -> None:
    sources = sorted((ROOT / "tests" / "fuzz-regressions").glob("*.min"))
    if not sources:
        raise AssertionError("the rejecting fuzz regression corpus is empty")
    for source in sources:
        result = run([str(compiler), str(source), str(temporary / f"{source.stem}.ll")], timeout=2)
        if result.returncode != 1 or result.stdout or not result.stderr or any(fragment in result.stderr for fragment in INTERNAL_FAILURES):
            raise AssertionError(f"fuzz regression returned for {source.name}:\n{result.stderr}")


def check_seed_corpus(compiler: Path, clang: str, temporary: Path) -> None:
    root = ROOT / "tests/fuzz-corpus"
    seeds = json.loads((root / "seeds.json").read_text(encoding="utf-8"))
    actual = {path.name for path in (root / "inputs").iterdir() if path.is_file()}
    if not seeds or actual != set(seeds):
        raise AssertionError("every AFL seed must have an explicit semantic or rejecting oracle in seeds.json")
    for name, expected in sorted(seeds.items()):
        source = temporary / f"seed-{name}"
        source.write_bytes((root / "inputs" / name).read_bytes())
        llvm = source.with_suffix(".ll")
        result = run([str(compiler), str(source), str(llvm)])
        if expected is None:
            if result.returncode != 1 or result.stdout or not result.stderr or any(fragment in result.stderr for fragment in INTERNAL_FAILURES):
                raise AssertionError(f"rejecting AFL seed {name} returned {result.returncode}: {result.stderr}")
        else:
            if result.returncode != 0:
                raise AssertionError(f"valid AFL seed {name} rejected: {result.stderr}")
            source.with_suffix(".expected.stdout").write_text(expected, encoding="utf-8")
            execute_llvm(clang, llvm, expected)


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
    execute_llvm(clang, first, f"{modules}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", type=Path, default=DEFAULT_COMPILER)
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--cases", type=int, default=int(os.environ.get("MINYAR_FUZZ_CASES", "200")))
    parser.add_argument("--hostile-timeout", type=float, default=2.0)
    parser.add_argument("--program-cases", type=int, default=None)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=0x4D494E594152)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "fuzz")
    arguments = parser.parse_args()
    if arguments.cases < 1 or (arguments.program_cases is not None and arguments.program_cases < 1):
        parser.error("case counts must be positive")
    if not 0 < arguments.hostile_timeout < float("inf"):
        parser.error("--hostile-timeout must be positive and finite")
    compiler = arguments.compiler.resolve()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="campaign-", dir=arguments.output_dir.resolve()))
    COMMANDS.clear()
    program_cases = arguments.program_cases
    if program_cases is None:
        program_cases = max(8, min(40, arguments.cases // 5))
    report = {"seed": arguments.seed, "expressions": arguments.cases,
              "program_cases": program_cases, "compiler": str(compiler), "runtime": str(RUNTIME.resolve()),
              "clang": arguments.clang, "link_flags": LINK_FLAGS, "math_flags": MATH_FLAGS,
              "hostile_timeout_seconds": arguments.hostile_timeout, "commands": COMMANDS}
    try:
        report["compiler_sha256"] = hashlib.sha256(compiler.read_bytes()).hexdigest()
        report["runtime_sha256"] = hashlib.sha256(RUNTIME.read_bytes()).hexdigest()
        remaining = arguments.cases
        batch = 0
        while remaining > 0:
            batch_size = min(200, remaining)
            check_expression_batch(compiler, arguments.clang, batch_size, temporary, arguments.seed + batch)
            remaining -= batch_size
            batch += 1
        check_language_surface(compiler, arguments.clang, program_cases, temporary, arguments.seed ^ 0x53555246414345)
        check_semantic_relations(compiler, arguments.clang, program_cases, temporary, arguments.seed ^ 0x53454D414E544943)
        check_hostile_sources(compiler, arguments.cases, temporary, arguments.hostile_timeout, arguments.seed ^ 0xBAD5EED)
        check_regression_corpus(compiler, temporary)
        check_seed_corpus(compiler, arguments.clang, temporary)
        check_generated_module_chain(compiler, arguments.clang, 24, temporary)
        report["status"] = "passed"
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        report.update(status="failed", failure=f"{type(error).__name__}: {error}")
        print(report["failure"], file=os.sys.stderr)
    finally:
        (temporary / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"fuzz evidence: {temporary}", flush=True)
    if report["status"] != "passed":
        return 1
    print(
        f"deterministic fuzzing passed: {arguments.cases} expressions, "
        f"{program_cases} full-language cases, {program_cases} semantic cases in two forms, "
        f"{arguments.cases} hostile inputs, 24 modules (all valid programs at O0/O2)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
