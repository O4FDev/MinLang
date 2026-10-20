#!/usr/bin/env python3
"""Seeded, independently checked programs across compiler and runtime variants."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import selectors
import signal
import subprocess
import tempfile
import time
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
MINIMUM = -(1 << 63)
MAXIMUM = (1 << 63) - 1
FAMILIES = ("arithmetic", "control", "aliases", "maps", "bytes", "callbacks", "choices")


def signed(value: int) -> int:
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)


def quotient(left: int, right: int) -> int:
    value = abs(left) // abs(right)
    return -value if (left < 0) != (right < 0) else value


def literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


@dataclasses.dataclass(frozen=True)
class Expression:
    text: str
    value: int


def expression(rng: random.Random, depth: int, leaves: list[Expression]) -> Expression:
    if depth == 0 or rng.randrange(4) == 0:
        return rng.choice(leaves)
    left = expression(rng, depth - 1, leaves)
    right = expression(rng, depth - 1, leaves)
    operator = rng.choice(("+", "-", "*", "/", "%", "&", "|", "^", ">>",
                           "wrappingAdd", "wrappingSubtract", "wrappingMultiply"))
    if operator in ("/", "%"):
        if right.value == 0 or (left.value == MINIMUM and right.value == -1):
            right = Expression("3", 3)
        value = quotient(left.value, right.value)
        if operator == "%":
            value = left.value - value * right.value
    elif operator == ">>":
        count = rng.randrange(64)
        right = Expression(str(count), count)
        value = left.value >> count
    elif operator in ("+", "wrappingAdd"):
        value = left.value + right.value
    elif operator in ("-", "wrappingSubtract"):
        value = left.value - right.value
    elif operator in ("*", "wrappingMultiply"):
        value = left.value * right.value
    elif operator == "&":
        value = left.value & right.value
    elif operator == "|":
        value = left.value | right.value
    else:
        value = left.value ^ right.value
    if operator.startswith("wrapping"):
        return Expression(f"{operator}({left.text}, {right.text})", signed(value))
    if not MINIMUM <= value <= MAXIMUM:
        return left
    return Expression(f"({left.text} {operator} {right.text})", value)


@dataclasses.dataclass(frozen=True)
class Case:
    family: str
    seed: int
    size: int


@dataclasses.dataclass
class Block:
    name: str = "case"
    body: list[str] = dataclasses.field(default_factory=list)
    expected: list[str] = dataclasses.field(default_factory=list)

    def check(self, term: str, value: int | str | bool) -> None:
        kind = "Boolean" if isinstance(value, bool) else "Text" if isinstance(value, str) else "Integer"
        label = f"{self.name}:{len(self.expected)}"
        self.body.append(f"check{kind}({term}, {literal(value)}, {literal(label)})")
        displayed = value if isinstance(value, str) else literal(value)
        self.expected.append(f"{label}={displayed}")


def generate_case(case: Case) -> Block:
    rng = random.Random(case.seed)
    block = Block(f"{case.family}:{case.seed}")
    lines = block.body
    check = block.check
    size = case.size
    first, second = rng.randint(-1000, 1000), rng.randint(-1000, 1000)
    if case.family == "arithmetic":
        lines.extend((f"let left = {first}", f"let right = {second}"))
        leaves = [Expression("left", first), Expression("right", second)]
        leaves += [Expression(f"({value})", value) for value in
                   (MINIMUM, MAXIMUM, -1, 0, 1, rng.randint(-100, 100))]
        for _ in range(size):
            result = expression(rng, 3, leaves)
            check(result.text, result.value)
        check("wrappingAdd(9223372036854775807, 1)", MINIMUM)
        check("wrappingSubtract(-9223372036854775808, 1)", MAXIMUM)
    elif case.family == "control":
        limit = rng.randint(2, size + 3)
        stop = rng.randint(1, limit)
        divisor = rng.randint(2, 5)
        lines.extend(("let total = 0", f"for index in 0..{limit} {{",
                      f"    if index == {stop} {{ break }}",
                      f"    if index % {divisor} == 0 {{ continue }}",
                      f"    total += index * {first}", "}"))
        check("total", sum(i * first for i in range(stop) if i % divisor))
        lines.extend(("let state = FuzzCell { number: 0; text: \"\"; values: [] }",
                      "let unusedA = false && mark(state)", "let unusedB = true || mark(state)"))
        check("state.number", 0)
        lines.extend(("let unusedC = true && mark(state)", "let unusedD = false || mark(state)"))
        check("state.number", 2)
        lines.extend(("let outer = 0", "let turns = 0", f"while outer < {limit} {{",
                      "    outer += 1", "    let inner = 0", "    while inner < outer {",
                      "        inner += 1", "        if inner % 2 == 0 { continue }",
                      "        turns += 1", "    }", "}"))
        check("turns", sum((i + 1) // 2 for i in range(1, limit + 1)))
    elif case.family == "aliases":
        cells = [{"number": first, "text": "old"}, {"number": second, "text": "new"}]
        roots = [cells[0], cells[0], cells[1]]
        lines.extend((f"let first = FuzzCell {{ number: {first}; text: \"old\"; values: [{first}] }}",
                      f"let other = FuzzCell {{ number: {second}; text: \"new\"; values: [{second}] }}",
                      "let roots = [first, first, other]", "let alias = roots",
                      "let fork = roots.appended(first)"))
        fork = roots.copy() + [cells[0]]
        for _ in range(size):
            position = rng.randrange(3)
            operation = rng.randrange(3)
            if operation == 0:
                value = rng.randint(-10000, 10000)
                lines.append(f"alias[{position}].number = {value}")
                roots[position]["number"] = value
            elif operation == 1:
                source = rng.randrange(3)
                lines.append(f"roots[{position}] = alias[{source}]")
                roots[position] = roots[source]
            else:
                value = rng.choice(("kept", "hello", "café", "λ"))
                lines.append(f"alias[{position}].text = {literal(value)}")
                roots[position]["text"] = value
            for index in range(3):
                check(f"roots[{index}].number", roots[index]["number"])
                check(f"fork[{index}].number", fork[index]["number"])
                check(f"fork[{index}].text", fork[index]["text"])
        lines.extend(("roots = []", "alias = []"))
        check("fork[3].number", cells[0]["number"])
        check("fork[3].values[0]", first)
    elif case.family == "maps":
        lines.extend((
            'let original = FuzzKey { label: "ke" + "y"; number: 7 }',
            'let value = ["kept" + "!"]',
            "let table: Map<FuzzKey, List<Text>> = Map()",
            "let tableAlias = table",
            "let names: Set<FuzzKey> = Set()",
            "let namesAlias = names",
            "table[original] = value",
            "names.add(original)",
            'original.label = "changed" + "!"',
            "original.number = 8",
            'let stored = FuzzKey { label: "key"; number: 7 }',
            "let saved = table[stored]",
            "tableAlias.clear()",
            'saved[0] = "changed"',
        ))
        check("value[0]", "changed")
        check("table.length", 0)
        check("names.contains(stored)", True)
        check("names.contains(original)", False)
        check("namesAlias.remove(stored)", True)
        check("names.length", 0)
        lines.extend((
            "let evaluation = Map<Text, Text>()",
            'evaluation["key"] = "borrowed" + "!"',
            'evaluation[evaluation["key"]] = fuzzReset(evaluation)',
        ))
        check('evaluation["borrowed!"]', "after!")

        key_count = 8
        keys: list[list[object]] = []
        payloads: dict[int, list[str]] = {}
        for index in range(key_count):
            label = f"key-{index}-{rng.randrange(1000)}"
            number = rng.randint(-1000, 1000)
            payload = f"value-{index}-{rng.randrange(1000)}!"
            keys.append([label, number])
            payloads[index] = [payload]
            label_prefix = f"key-{index}-"
            lines.append(f"let key{index} = FuzzKey {{ label: {literal(label_prefix)} + "
                         f"{literal(label[len(label_prefix):])}; number: {number} }}")
            lines.append(f"let value{index} = [{literal(payload[:-1])} + \"!\"]")

        mapped: dict[tuple[str, int], int] = {}
        members: set[tuple[str, int]] = set()

        def key_term(key: tuple[str, int]) -> str:
            return f"FuzzKey {{ label: {literal(key[0])}; number: {key[1]} }}"

        for step in range(size):
            key_index = rng.randrange(key_count)
            value_index = rng.randrange(key_count)
            frozen = (str(keys[key_index][0]), int(keys[key_index][1]))
            lines.append(f"table[key{key_index}] = value{value_index}")
            lines.append(f"names.add(key{key_index})")
            mapped[frozen] = value_index
            members.add(frozen)

            new_number = int(keys[key_index][1]) + rng.randint(1, 1000) + step
            label_suffix = rng.randrange(1000)
            new_label = f"changed-{step}-{label_suffix}"
            lines.append(f"key{key_index}.label = {literal(f'changed-{step}-')} + "
                         f"{literal(str(label_suffix))}")
            lines.append(f"key{key_index}.number = {new_number}")
            keys[key_index][0] = new_label
            keys[key_index][1] = new_number
            current = (new_label, new_number)
            check(f"tableAlias.has({key_term(frozen)})", True)
            check(f"namesAlias.contains({key_term(frozen)})", True)
            check(f"table.has({key_term(current)})", current in mapped)

            lines.append(f"let saved{step} = tableAlias[{key_term(frozen)}]")
            saved_id = mapped[frozen]
            disposition = step % 3
            if disposition == 0:
                check(f"tableAlias.remove({key_term(frozen)})", True)
                del mapped[frozen]
            elif disposition == 1:
                replacement = (saved_id + 1 + rng.randrange(key_count - 1)) % key_count
                lines.append(f"tableAlias[{key_term(frozen)}] = value{replacement}")
                mapped[frozen] = replacement
            else:
                lines.append("tableAlias.clear()")
                mapped.clear()

            changed = f"saved-{step}-{rng.randrange(1000)}"
            lines.append(f"saved{step}[0] = {literal(changed)}")
            payloads[saved_id][0] = changed
            check(f"value{saved_id}[0]", changed)
            if frozen in mapped:
                check(f"table[{key_term(frozen)}][0]", payloads[mapped[frozen]][0])

            set_disposition = step % 3
            if set_disposition == 0:
                check(f"namesAlias.remove({key_term(frozen)})", True)
                members.remove(frozen)
            elif set_disposition == 1:
                lines.append("namesAlias.clear()")
                members.clear()
            else:
                check(f"names.contains({key_term(frozen)})", True)
            check("table.length", len(mapped))
            check("namesAlias.length", len(members))
    elif case.family == "bytes":
        count = rng.randint(1, size + 1)
        values = [rng.randrange(256) for _ in range(count)]
        lines.extend(("let data = Bytes()",))
        for value in values:
            lines.append(f"data.add({value})")
        lines.append("let alias = data")
        for _ in range(size):
            index = rng.randrange(len(values))
            value = rng.randrange(256)
            lines.append(f"alias[{index}] = {value}")
            values[index] = value
        for index, value in enumerate(values):
            check(f"data[{index}]", value)
        signed_word = rng.randint(-32768, 32767)
        lines.append(f"data.addInt16({signed_word})")
        check(f"alias.getInt16({count})", signed_word)
        check(f"data[{count}]", signed_word & 255)
        check(f"data[{count + 1}]", (signed_word >> 8) & 255)
        text = rng.choice(("café", "λ水", "hello", "🌙"))
        lines.append(f"let text = {literal(text)}")
        check("Text(Bytes(text))", text)
        check("text.length", len(text))
    elif case.family == "callbacks":
        lines.extend((f"let state = FuzzCell {{ number: {first}; text: \"captured\"; values: [] }}",
                      f"let offset = {second}",
                      "let callback = function(value: Integer): Integer {",
                      "    state.number += value", "    return state.number + offset", "}",
                      "let callbacks = [callback, callback]"))
        current = first
        for _ in range(size):
            value = rng.randint(-100, 100)
            position = rng.randrange(2)
            current += value
            check(f"callbacks[{position}]({value})", current + second)
        lines.extend(("let kept = callbacks[0]", "callbacks = []", "state.text = \"alive\""))
        check("kept(1)", current + 1 + second)
        check("state.text", "alive")
    elif case.family == "choices":
        lines.extend((f"let state = FuzzCell {{ number: {first}; text: \"payload\"; values: [] }}",
                      "let values: List<FuzzChoice> = [FuzzChoice.Full(state), FuzzChoice.Empty]"))
        for index in range(size):
            value = rng.randint(-1000, 1000)
            lines.extend((f"state.number = {value}", f"let kept{index} = values[0]",
                          "values[0] = FuzzChoice.Empty", f"match kept{index} {{",
                          "    Full(payload) {"))
            check("payload.number", value)
            check("payload.text", "payload")
            lines.extend(("    }", "    Empty { fail(\"lost choice payload\") }", "}",
                          "values[0] = FuzzChoice.Full(state)"))
        check("choiceValue(FuzzChoice.Empty)", -1)
    else:
        raise ValueError(f"unknown family: {case.family}")
    return block


PRELUDE = '''// Generated by tests/differential-fuzz.py. Integers are checked against a Python oracle.
record FuzzCell { number: Integer; text: Text; values: List<Integer> }
record FuzzKey { label: Text; number: Integer }
choice FuzzChoice { Full(payload: FuzzCell); Empty }
function mark(state: FuzzCell): Boolean { state.number += 1; return true }
function fuzzReset(table: Map<Text, Text>): Text { table.clear(); return "after" + "!" }
function choiceValue(value: FuzzChoice): Integer {
    match value { Full(payload) { return payload.number } Empty { return -1 } }
}
function checkInteger(actual: Integer, expected: Integer, label: Text) {
    print(label + "=" + Text(actual))
    if actual != expected { fail("integer oracle mismatch at " + label) }
}
function checkText(actual: Text, expected: Text, label: Text) {
    print(label + "=" + actual)
    if actual != expected { fail("text oracle mismatch at " + label) }
}
function checkBoolean(actual: Boolean, expected: Boolean, label: Text) {
    print(label + "=" + Text(actual))
    if actual != expected { fail("boolean oracle mismatch at " + label) }
}
'''


def render(cases: list[Case]) -> tuple[str, bytes]:
    parts = [PRELUDE]
    expected = []
    for index, case in enumerate(cases):
        block = generate_case(case)
        parts.append(f"// {case.family}, seed {case.seed}, size {case.size}\nfunction fuzzCase{index}() {{\n")
        parts.extend(f"    {line}\n" for line in block.body)
        parts.append("}\n")
        expected.extend(block.expected)
    parts.extend(f"fuzzCase{index}()\n" for index in range(len(cases)))
    return "".join(parts), ("\n".join(expected) + "\n").encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_program(directory: Path, cases: list[Case]) -> tuple[Path, bytes]:
    directory.mkdir(parents=True, exist_ok=True)
    source, expected = render(cases)
    path = directory / "program.min"
    path.write_text(source, encoding="utf-8")
    (directory / "expected.stdout").write_bytes(expected)
    write_json(directory / "spec.json", {"version": 1, "cases": [dataclasses.asdict(case) for case in cases]})
    return path, expected


@dataclasses.dataclass(frozen=True)
class Failure:
    kind: str
    configuration: str
    detail: str
    fingerprint: str = ""

    @property
    def signature(self) -> tuple[str, str]:
        return self.kind, self.configuration

    @property
    def reproduction(self) -> tuple[str, str, str]:
        return self.kind, self.configuration, self.fingerprint or self.detail


class Runner:
    def __init__(self, directory: Path, timeout: float, output_limit: int = 16 * 1024 * 1024):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("command timeout must be a positive finite number")
        if output_limit < 1:
            raise ValueError("command output limit must be positive")
        self.directory = directory
        self.timeout = timeout
        self.output_limit = output_limit
        self.commands: list[dict] = []

    def command(self, arguments: list[str], label: str, timeout: float | None = None) -> dict:
        log = self.directory / f"command-{len(self.commands):05d}"
        stdout_path = log.with_suffix(".stdout")
        stderr_path = log.with_suffix(".stderr")
        duration = self.timeout if timeout is None else timeout
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("command timeout must be a positive finite number")
        started = time.monotonic()
        result = {"argv": arguments, "cwd": str(ROOT), "label": label,
                  "timeout_seconds": duration, "output_limit_bytes": self.output_limit,
                  "timed_out": False, "output_limited": False}
        stdout_path.write_bytes(b"")
        stderr_path.write_bytes(b"")
        try:
            process = subprocess.Popen(arguments, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
            assert process.stdout is not None and process.stderr is not None
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ, stdout_path)
            selector.register(process.stderr, selectors.EVENT_READ, stderr_path)
            written = 0
            command_deadline = started + duration
            read_deadline = command_deadline
            terminating = False
            with stdout_path.open("ab") as stdout_file, stderr_path.open("ab") as stderr_file:
                files = {stdout_path: stdout_file, stderr_path: stderr_file}
                while selector.get_map():
                    remaining = read_deadline - time.monotonic()
                    if remaining <= 0:
                        if not terminating:
                            result["timed_out"] = True
                            terminating = True
                            read_deadline = time.monotonic() + 5
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            continue
                        break
                    events = selector.select(remaining)
                    if not events:
                        continue
                    for key, _ in events:
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                            continue
                        available = self.output_limit - written
                        files[key.data].write(chunk[:max(0, available)])
                        written += min(len(chunk), max(0, available))
                        if len(chunk) > available:
                            result["output_limited"] = True
                            terminating = True
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            break
                    if result["output_limited"]:
                        break
            for key in list(selector.get_map().values()):
                selector.unregister(key.fileobj)
                key.fileobj.close()
            selector.close()
            try:
                if terminating:
                    process.wait(timeout=5)
                else:
                    process.wait(timeout=max(0, command_deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            result["status"] = process.returncode
        except OSError as error:
            stderr_path.write_bytes(str(error).encode("utf-8", errors="backslashreplace"))
            result["status"] = -1
        result.update(elapsed_seconds=round(time.monotonic() - started, 4),
                      stdout=str(stdout_path), stderr=str(stderr_path))
        self.commands.append(result)
        write_json(self.directory / "commands.json", self.commands)
        return result


def command_failure(result: dict, phase: str, configuration: str) -> Failure | None:
    if result["timed_out"]:
        return Failure(phase + "-timeout", configuration, "process group killed at deadline", "deadline")
    if result["output_limited"]:
        return Failure(phase + "-output-limit", configuration,
                       f"combined output exceeded {result['output_limit_bytes']} bytes",
                       str(result["output_limit_bytes"]))
    if result["status"] != 0:
        diagnostic = Path(result["stderr"]).read_bytes()
        return Failure(phase + "-status", configuration,
                       diagnostic.decode("utf-8", errors="backslashreplace")[-4000:],
                       f"{result['status']}:" + hashlib.sha256(diagnostic).hexdigest())
    return None


def result_fingerprint(result: dict, directory: Path) -> str:
    """Identify one failure while allowing its evidence directory to change."""
    marker = str(directory).encode("utf-8")
    diagnostic = Path(result["stderr"]).read_bytes().replace(marker, b"<case>")
    oracle = re.search(
        rb"(?:integer|text|boolean) oracle mismatch at ([^\r\n]+)", diagnostic)
    identity = b"oracle:" + oracle.group(1) if oracle else hashlib.sha256(diagnostic).digest()
    return hashlib.sha256(str(result["status"]).encode("ascii") + b"\0" + identity).hexdigest()


def output_difference(expected: bytes, actual: bytes) -> tuple[str, str]:
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    for index in range(max(len(expected_lines), len(actual_lines))):
        expected_line = expected_lines[index] if index < len(expected_lines) else None
        actual_line = actual_lines[index] if index < len(actual_lines) else None
        if expected_line != actual_line:
            expected_identity = b"missing" if expected_line is None else b"present\0" + expected_line
            actual_identity = b"missing" if actual_line is None else b"present\0" + actual_line
            pair = expected_identity + b"\0" + actual_identity
            detail = (f"stdout differs at observation {index}: expected {expected_line!r}, "
                      f"observed {actual_line!r}")
            return detail, hashlib.sha256(pair).hexdigest()
    raise ValueError("output difference requested for equal transcripts")


def runtime_source() -> str:
    # Keep this transformation in step with tools/test-runtime.min::cycleSource.
    source = (ROOT / "runtime/minyar_runtime.c").read_text(encoding="utf-8")
    for before, after in (("minyar_rc.h", "minyar_cycle_rc.h"),
                          ("minyar_collections.h", "minyar_cycle_collections.h")):
        directive = f'#include "{before}"'
        if source.count(directive) != 1:
            raise ValueError(f"expected exactly one {directive}")
        source = source.replace(directive, f'#include "{after}"')
    return ("#define MINYAR_SORT_GRAPH 1\n#define MINYAR_MAP_CYCLE_RUNTIME 1\n"
            "#define MINYAR_NOINLINE __attribute__((noinline))\n" + source +
            '\n#include "minyar_callbacks.h"\n')


def prepare_runtimes(runner: Runner, clang: str) -> dict[tuple[str, str], Path]:
    engine = runtime_source()
    contract = (ROOT / "tests/memory-contracts-runtime.c").read_text(encoding="utf-8")
    directive = '#include "../runtime/minyar_runtime.c"'
    if contract.count(directive) != 1:
        raise ValueError("ownership contract must include the engine exactly once")
    runtimes = {}
    for memory in ("eager", "arena"):
        path = runner.directory / f"runtime-{memory}.c"
        path.write_text(contract.replace(directive, engine) if memory == "eager" else engine,
                        encoding="utf-8")
        for optimization in ("O0", "O2"):
            target = runner.directory / f"runtime-{memory}-{optimization}.o"
            command = [clang, "-" + optimization, "-Wno-override-module", "-iquote", str(ROOT / "runtime")]
            if memory == "arena":
                command.append("-DMINYAR_COMPILER_ARENA=1")
            command.extend(("-c", str(path), "-o", str(target)))
            result = runner.command(command, f"runtime-{memory}-{optimization}", max(120, runner.timeout))
            failure = command_failure(result, "runtime-build", f"{memory}-{optimization}")
            if failure:
                raise RuntimeError(f"{failure.kind}: {failure.configuration}: {failure.detail}")
            runtimes[memory, optimization] = target
    return runtimes


def check_program(runner: Runner, cases: list[Case], directory: Path, compilers: dict[str, str],
                  clang: str, runtimes: dict[tuple[str, str], Path],
                  only: str | None = None) -> list[Failure]:
    source, expected = save_program(directory, cases)
    failures = []
    for stage, compiler in compilers.items():
        if only and not only.startswith(stage):
            continue
        llvm = directory / f"{stage}.ll"
        llvm.unlink(missing_ok=True)
        result = runner.command([compiler, str(source), str(llvm), "--library", str(ROOT / "library")],
                                f"{directory.name}-{stage}-compile")
        failure = command_failure(result, "compile", stage)
        if failure:
            failure = dataclasses.replace(failure, fingerprint=result_fingerprint(result, directory))
        if not failure and (not llvm.is_file() or llvm.stat().st_size == 0):
            failure = Failure("compile-output", stage, "compiler produced no LLVM", "missing-llvm")
        if failure:
            failures.append(failure)
            continue
        if only == stage:
            continue
        for (memory, optimization), runtime in runtimes.items():
            configuration = f"{stage}-{memory}-{optimization}"
            if only and only != stage and configuration != only:
                continue
            executable = directory / configuration
            executable.unlink(missing_ok=True)
            result = runner.command([clang, "-" + optimization, "-Wno-override-module", str(llvm),
                                     str(runtime), "-lm", "-o", str(executable)], configuration + "-link")
            failure = command_failure(result, "link", configuration)
            if failure:
                failure = dataclasses.replace(failure, fingerprint=result_fingerprint(result, directory))
            if not failure and (not executable.is_file() or executable.stat().st_size == 0):
                failure = Failure("link-output", configuration, "linker produced no executable",
                                  "missing-executable")
            if not failure:
                result = runner.command([str(executable)], configuration + "-run")
                failure = command_failure(result, "run", configuration)
                if failure:
                    failure = dataclasses.replace(failure,
                                                  fingerprint=result_fingerprint(result, directory))
                if not failure and Path(result["stderr"]).read_bytes():
                    diagnostic = Path(result["stderr"]).read_bytes()
                    failure = Failure("run-stderr", configuration, "successful program wrote diagnostics",
                                      hashlib.sha256(diagnostic).hexdigest())
                actual = Path(result["stdout"]).read_bytes()
                if not failure and actual != expected:
                    detail, fingerprint = output_difference(expected, actual)
                    failure = Failure("run-oracle", configuration, detail, fingerprint)
            if failure:
                failures.append(failure)
    write_json(directory / "failures.json", [dataclasses.asdict(failure) for failure in failures])
    return failures


def reduce_cases(cases: list[Case], reproduces: Callable[[list[Case]], bool], budget: int) -> tuple[list[Case], int]:
    """Delete independent functions, then shrink each retained generator's size."""
    current = cases.copy()
    attempts = 0
    granularity = 2
    while len(current) > 1 and attempts < budget:
        width = (len(current) + granularity - 1) // granularity
        changed = False
        for start in range(0, len(current), width):
            candidate = current[:start] + current[start + width:]
            if not candidate:
                continue
            attempts += 1
            if reproduces(candidate):
                current = candidate
                granularity = max(2, granularity - 1)
                changed = True
                break
            if attempts >= budget:
                break
        if not changed:
            if granularity >= len(current):
                break
            granularity = min(len(current), granularity * 2)
    for index in range(len(current)):
        for size in range(1, current[index].size):
            if attempts >= budget:
                break
            candidate = current.copy()
            candidate[index] = dataclasses.replace(candidate[index], size=size)
            attempts += 1
            if reproduces(candidate):
                current = candidate
                break
    return current, attempts


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--seed", type=lambda value: int(value, 0), default=0x4D494E)
    result.add_argument("--programs", type=int, default=8)
    result.add_argument("--size", type=int, default=12)
    result.add_argument("--compiler-stage2", default=str(ROOT / "build/minyarc"))
    result.add_argument("--compiler-stage3", default=str(ROOT / "build/minyarc-fuzz-stage3"))
    result.add_argument("--clang", default=os.environ.get("LLVM_CC", "clang"))
    result.add_argument("--timeout", type=float, default=30)
    result.add_argument("--shrink-attempts", type=int, default=32)
    result.add_argument("--output-dir", type=Path, default=ROOT / "build/differential-fuzz")
    result.add_argument("--replay", action="append", type=Path, default=[])
    return result


def main() -> int:
    options = parser().parse_args()
    if (options.programs < 1 or options.size < 1 or not math.isfinite(options.timeout) or
            options.timeout <= 0 or options.shrink_attempts < 0):
        parser().error("programs, size and timeout must be positive; shrink-attempts must be nonnegative")
    options.output_dir.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="campaign-", dir=options.output_dir)).resolve()
    runner = Runner(directory, options.timeout)
    compilers = {"stage2": str(Path(options.compiler_stage2).resolve()),
                 "stage3": str(Path(options.compiler_stage3).resolve())}
    program_count = len(options.replay) if options.replay else options.programs
    report = {"version": 1, "seed": options.seed, "programs_requested": program_count,
              "size": options.size, "matrix": ["stage2", "stage3", "eager", "arena", "O0", "O2"],
              "programs_passed": 0, "status": "running", "compilers": compilers}
    if options.replay:
        report["replays"] = [str(path.resolve()) for path in options.replay]
    print(f"differential fuzz evidence: {directory}", flush=True)
    try:
        report["compiler_sha256"] = {stage: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                     for stage, path in compilers.items()}
        runtimes = prepare_runtimes(runner, options.clang)
        rng = random.Random(options.seed)
        for index in range(program_count):
            cases = [Case(family, rng.getrandbits(63), options.size) for family in FAMILIES]
            if options.replay:
                spec = json.loads(options.replay[index].read_text(encoding="utf-8"))
                if spec["version"] != 1 or not spec["cases"]:
                    raise ValueError("replay needs a nonempty version 1 case specification")
                cases = [Case(**case) for case in spec["cases"]]
            program_dir = directory / f"program-{index:04d}"
            failures = check_program(runner, cases, program_dir, compilers, options.clang, runtimes)
            if failures:
                failure = failures[0]
                report["failures"] = [dataclasses.asdict(item) for item in failures]
                attempt = 0

                def reproduces(candidate: list[Case]) -> bool:
                    nonlocal attempt
                    attempt += 1
                    found = check_program(runner, candidate, directory / f"shrink-{attempt:04d}",
                                          compilers, options.clang, runtimes, failure.configuration)
                    return any(item.reproduction == failure.reproduction for item in found)

                reduced, attempts = reduce_cases(cases, reproduces, options.shrink_attempts)
                save_program(directory / "minimized", reduced)
                report.update(status="failed", shrink_attempts=attempts,
                              minimized_cases=len(reduced), failure_program=str(program_dir))
                print(f"FAIL {failure.configuration}: {failure.kind}; minimized to {len(reduced)} case(s)", flush=True)
                return 1
            report["programs_passed"] += 1
            write_json(directory / "results.json", report)
            print(f"PASS program {index + 1}: {len(cases)} families, 8 configurations", flush=True)
        report["status"] = "passed"
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        report.update(status="infrastructure-failure", error=str(error))
        print(f"FAIL infrastructure: {error}", flush=True)
        return 2
    finally:
        report["commands"] = len(runner.commands)
        report["elapsed_seconds"] = round(sum(item["elapsed_seconds"] for item in runner.commands), 3)
        write_json(directory / "results.json", report)


if __name__ == "__main__":
    raise SystemExit(main())
