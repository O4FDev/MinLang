#!/usr/bin/env python3
"""Exercise declaration, call-resolution, and module scaling adversarially."""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

try:
    import resource
except ImportError:
    resource = None


ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "build" / "minyarc"


def compile_source(source: Path, output: Path) -> float:
    before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
    started = time.monotonic()
    result = subprocess.run(
        [str(COMPILER), str(source), str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        raise AssertionError(f"scaling input failed:\n{result.stderr}")
    if before:
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        return (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    return elapsed


def declaration_program(path: Path, count: int, call_last: bool) -> None:
    target = "target()" if call_last else "1"
    functions = "".join(
        f"function f{index}(): Integer {{\n    return {target}\n}}\n\n"
        for index in range(count)
    )
    if call_last:
        functions += "function target(): Integer {\n    return 42\n}\n\n"
    path.write_text(functions + "print(f0())\n", encoding="utf-8")


def module_program(directory: Path, count: int) -> Path:
    directory.mkdir()
    (directory / "module0.min").write_text(
        "public function value(): Integer {\n    return 1\n}\n", encoding="utf-8"
    )
    for index in range(1, count):
        (directory / f"module{index}.min").write_text(
            f'use "./module{index - 1}.min" as previous\n\n'
            "public function value(): Integer {\n"
            "    return previous.value() + 1\n"
            "}\n",
            encoding="utf-8",
        )
    entry = directory / "main.min"
    entry.write_text(
        f'use "./module{count - 1}.min" as last\n\nprint(last.value())\n',
        encoding="utf-8",
    )
    return entry


with tempfile.TemporaryDirectory(prefix="minyar-scaling-") as temporary_name:
    temporary = Path(temporary_name)
    measurements: list[tuple[str, float]] = []
    for name, count, calls in (
        ("250 declarations", 250, False),
        ("2000 declarations", 2000, False),
        ("250 adversarial calls", 250, True),
        ("2000 adversarial calls", 2000, True),
    ):
        source = temporary / f"{name.replace(' ', '-')}.min"
        declaration_program(source, count, calls)
        measurements.append((name, compile_source(source, source.with_suffix(".ll"))))
    entry = module_program(temporary / "modules", 200)
    measurements.append(("200-module graph", compile_source(entry, temporary / "modules.ll")))

for name, seconds in measurements:
    if seconds > 5:
        raise SystemExit(f"{name} used {seconds:.2f}s; scaling limit is 5s")
print("compiler scaling verified: " + ", ".join(f"{name} {seconds:.3f}s" for name, seconds in measurements))
