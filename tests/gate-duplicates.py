#!/usr/bin/env python3
"""Fail when two checks in one gate run the same command line, or a check in a gate runs nothing.

A command repeated by two phony checks of one aggregate is either wasted gate time (the same test on the same
inputs, run twice) or a race (two checks the runner starts side by side rewriting one shared file). Both have
happened: three targets each rebuilt the errors stage3 compiler for the same smoke programs, and the io-lines
check and its sanitizer variant rewrote one stdin file. This reads Make's database without running anything,
so it checks what the gates would run, not how a recipe is spelled. A check with no recipe and no child checks
passes without testing anything, which is how a split piece that lost its command would look.
"""
import collections
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
TARGET = re.compile(r"^([^:#=\s][^:=]*?)::?(?!=)\s*(.*)$")
# Lines that expand differently per target ($@ and friends) and bookkeeping that may legitimately repeat.
AUTOMATIC = re.compile(r"\$[@*<^?]|\$\([@*<^?][DF]?\)")
IGNORED = ("echo ", "rm ", "rm -", "mkdir ", "set -e; rm -rf")


def database(directory):
    environment = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEFILES")}
    result = subprocess.run(["make", "-qp", "__minyar_no_goal__"], cwd=directory, env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    if "# Files" not in result.stdout:
        raise SystemExit("make -qp printed no database:\n" + result.stderr)
    return result.stdout


def parse(text):
    deps, recipes = collections.defaultdict(list), collections.defaultdict(list)
    target, files = None, False
    for line in text.split("\n"):
        if line.startswith("# Files"):
            files = True
            continue
        if not files:
            continue
        if line == "":
            target = None
            continue
        if line.startswith("#"):
            continue
        if line.startswith("\t"):
            if target is not None:
                recipes[target].append(line[1:].strip())
            continue
        match = TARGET.match(line)
        if match is None or line.startswith("."):
            target = None
            continue
        names = match.group(1).split()
        target = names[0] if len(names) == 1 else None
        for name in names:
            deps[name].extend(match.group(2).split("|")[0].split())
    return deps, recipes


def duplicates(deps, recipes, aggregate):
    reached, stack = set(), [aggregate]
    while stack:
        name = stack.pop()
        if name not in reached:
            reached.add(name)
            stack.extend(item for item in deps.get(name, []) if item.startswith("check"))
    owners = collections.defaultdict(set)
    for name in reached:
        for command in recipes.get(name, []):
            command = command.lstrip("@-+ ")
            if command and not AUTOMATIC.search(command) and not command.startswith(IGNORED):
                owners[command].add(name)
    return reached, sorted((command, sorted(names)) for command, names in owners.items() if len(names) > 1)


def empty(deps, recipes, reached, aggregate):
    return sorted(name for name in reached if name != aggregate
                  and not any(command.strip() for command in recipes.get(name, []))
                  and not any(item.startswith("check") for item in deps.get(name, [])))


def self_test():
    with tempfile.TemporaryDirectory() as directory:
        Path(directory, "Makefile").write_text(
            ".PHONY: check check-a check-b check-c check-d check-e\n"
            "check: check-a check-b check-c check-d\n"
            "check-a:\n\t./build/tests/same --flag\n"
            "check-b:\n\t@./build/tests/same --flag\n"
            "check-c check-d:\n\t./build/tests/piece $@\n"
            "check-d: check-e\n"
            "check-e:\n\tprintf 'x' > build/shared.bin\n"
            "check-f:\n\tprintf 'x' > build/shared.bin\n"
            "check-g: build/input\n", encoding="utf-8")
        deps, recipes = parse(database(directory))
        reached, found = duplicates(deps, recipes, "check")
        assert reached == {"check", "check-a", "check-b", "check-c", "check-d", "check-e"}, reached
        assert found == [("./build/tests/same --flag", ["check-a", "check-b"])], found
        assert empty(deps, recipes, reached, "check") == [], reached
        assert empty(deps, recipes, reached | {"check-g"}, "check") == ["check-g"]
        deps["check"].append("check-f")
        _, found = duplicates(deps, recipes, "check")
        assert ("printf 'x' > build/shared.bin", ["check-e", "check-f"]) in found, found


def main(aggregates):
    self_test()
    deps, recipes = parse(database(ROOT))
    failed = False
    for aggregate in aggregates:
        reached, found = duplicates(deps, recipes, aggregate)
        if len(reached) < 2:
            print(f"{aggregate}: no checks found in the Make database")
            failed = True
        for command, names in found:
            print(f"{aggregate}: {len(names)} checks run the same command ({', '.join(names)}):\n    {command}")
            failed = True
        for name in empty(deps, recipes, reached, aggregate):
            print(f"{aggregate}: {name} runs no command and has no child checks")
            failed = True
        print(f"{aggregate}: {len(reached)} checks, {len(found)} repeated commands")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["check-portable"]))
