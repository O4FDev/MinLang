#!/usr/bin/env python3
"""Inject compiler faults and check that the tests detect them."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "compiler.min"
RUNTIME_SOURCE = ROOT / "runtime" / "minyar_runtime.c"
RUNTIME = ROOT / "build" / "minyar-runtime.o"
if not RUNTIME.exists():
    RUNTIME = RUNTIME_SOURCE
STAGE0 = ROOT / "build" / "stage0"
CLANG = os.environ.get("MINYAR_TEST_CLANG", "clang")


def run(command: list[str], *, timeout: float = 30, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, env=env)


def replace_once(source: str, before: str, after: str, name: str) -> str:
    occurrences = source.count(before)
    if occurrences != 1:
        raise AssertionError(f"mutation '{name}' expected one source location, found {occurrences}")
    return source.replace(before, after, 1)


def compiler_mutations(temporary: Path) -> None:
    original = SOURCE.read_text(encoding="utf-8")
    mutations = {
        "allow-cycles": (
            "if moduleStates[existing] == 1 {",
            "if moduleStates[existing] == 2 {",
        ),
        "invert-visibility": (
            "if declarationPublic[declaration] == 0 {",
            "if declarationPublic[declaration] != 0 {",
        ),
        "allow-module-side-effects": (
            "if !isEntry {\n                    fail(canonicalPath",
            "if isEntry {\n                    fail(canonicalPath",
        ),
        "break-parent-paths": (
            "activeParts = activeParts - 1",
            "activeParts = activeParts + 1",
        ),
        "reject-valid-entry-points": (
            "if topLevelStatements && mainFunction >= 0 {",
            "if topLevelStatements || mainFunction >= 0 {",
        ),
        "break-indexed-lookups": (
            "let symbol = symbolReturnTypes[count + middle]",
            "let symbol = symbolReturnTypes[count]",
        ),
    }
    for name, (before, after) in mutations.items():
        source = replace_once(original, before, after, name)
        mutant_source = temporary / f"compiler-{name}.min"
        mutant_llvm = temporary / f"compiler-{name}.ll"
        mutant = temporary / f"compiler-{name}"
        mutant_source.write_text(source, encoding="utf-8")
        seeded = run([str(STAGE0), str(mutant_source), "-o", str(mutant_llvm)])
        if seeded.returncode != 0:
            raise AssertionError(f"could not build compiler mutant '{name}':\n{seeded.stderr}")
        linked = run([CLANG, "-O0", "-Wno-override-module", str(mutant_llvm), str(RUNTIME), "-o", str(mutant)])
        if linked.returncode != 0:
            raise AssertionError(f"could not link compiler mutant '{name}':\n{linked.stderr}")
        environment = os.environ.copy()
        environment["MINYAR_TEST_COMPILER"] = str(mutant)
        tested = run(["sh", "tests/run-module-tests.sh"], timeout=45, env=environment)
        if tested.returncode == 0:
            raise AssertionError(f"compiler mutant survived: {name}")
        print(f"killed compiler mutant: {name}")


def runtime_mutations(temporary: Path) -> None:
    compiler = ROOT / "build" / "minyarc"
    programs = {
        "list-boundary": ROOT / "tests" / "runtime" / "lists.min",
        "reject-valid-arithmetic": ROOT / "examples" / "language-tour.min",
        "reject-valid-division": ROOT / "tests" / "runtime" / "division-valid.min",
        "break-text-equality": ROOT / "examples" / "language-tour.min",
        "reject-valid-text-slice": ROOT / "tests" / "runtime" / "text-indexing.min",
    }
    runtime_source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    # Mutations reject valid operations: failures must be caught without
    # executing a deliberately broken memory or division safety guard.
    mutations = {
        "list-boundary": (
            "long long minyar_list_get(const MinyarList *list, long long position) {\n    if ((unsigned long long)position >= (unsigned long long)list->length)",
            "long long minyar_list_get(const MinyarList *list, long long position) {\n    if ((unsigned long long)position >= (unsigned long long)(list->length - 1))",
        ),
        "reject-valid-arithmetic": ("if (overflowed)\n", "if (!overflowed)\n"),
        "reject-valid-division": ("if (right == 0)\n", "if (right != 0)\n"),
        "break-text-equality": (
            "left->byte_length == right->byte_length",
            "left->byte_length != right->byte_length",
        ),
        "reject-valid-text-slice": (
            "if (start < 0 || end < start || end > text->character_length)",
            "if (start < 0 || end < start || end >= text->character_length)",
        ),
    }
    for name, source in programs.items():
        llvm = temporary / f"runtime-{name}.ll"
        compiled = run([str(compiler), str(source), str(llvm)])
        if compiled.returncode != 0:
            raise AssertionError(f"could not prepare runtime mutant '{name}':\n{compiled.stderr}")
        before, after = mutations[name]
        mutated_runtime = replace_once(runtime_source, before, after, name)
        runtime_file = temporary / f"runtime-{name}.c"
        executable = temporary / f"runtime-{name}"
        runtime_file.write_text(mutated_runtime, encoding="utf-8")
        linked = run([CLANG, "-O0", "-Wno-override-module", str(llvm), str(runtime_file), "-I", str(ROOT / "runtime"), "-o", str(executable)])
        if linked.returncode != 0:
            raise AssertionError(f"could not link runtime mutant '{name}':\n{linked.stderr}")
        result = run([str(executable)])
        survived = False
        if name == "list-boundary":
            survived = result.returncode == 0 and result.stdout == "42\nMinyar\n"
        elif name == "reject-valid-division":
            survived = result.returncode == 0 and result.stdout == "21\n2\n"
        elif name in ("break-text-equality", "reject-valid-arithmetic"):
            survived = result.returncode == 0 and result.stdout == "The answer is\n42\n3\n2\n1\n"
        else:
            survived = result.returncode == 0
        if survived:
            raise AssertionError(f"runtime mutant survived: {name}")
        print(f"killed runtime mutant: {name}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="minyar-mutation-") as directory:
        temporary = Path(directory)
        compiler_mutations(temporary)
        runtime_mutations(temporary)
    print("all seeded compiler and runtime mutants were killed")


if __name__ == "__main__":
    main()
