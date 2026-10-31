#!/usr/bin/env python3
"""Selector tests for tools/dev-check.py: trace attribution, Make comparison and content-true timestamps."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("dev_check", ROOT / "tools" / "dev-check.py")
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)
failures = []


def expect(condition, message):
    if not condition:
        failures.append(message)


def trace_attribution(tree):
    root = str(tree)
    lines = [
        f'100 execve("/usr/bin/make", ["make", "check-in-parallel"], 0x1 /* 3 vars */) = 0',
        f'100 clone3({{flags=CLONE_VM}}, 88 <unfinished ...>',
        f'100 <... clone3 resumed>) = 200',
        f'200 execve("/usr/bin/make", ["make", "-j1", "check-a"], 0x1 /* 3 vars */) = 0',
        # The check's own Make parse: Makefile, a $(shell find tests) child, then a .d include.
        f'200 openat(AT_FDCWD, "Makefile", O_RDONLY) = 3',
        f'200 clone(child_stack=NULL) = 201',
        f'201 openat(AT_FDCWD, "tests", O_RDONLY|O_DIRECTORY) = 3',
        f'200 openat(AT_FDCWD, "build/tooling/tests/a.ll.d", O_RDONLY) = 3',
        f'200 newfstatat(AT_FDCWD, "build/tooling/tests/a", {{st_mode=S_IFREG}}, 0) = 0',
        # Recipe: the harness reads a fixture, lists a directory and opens a file relative to it.
        f'200 clone(child_stack=NULL) = 202',
        f'202 execve("{root}/build/tooling/tests/a", ["a"], 0x1 /* 3 vars */) = 0',
        f'202 openat(AT_FDCWD, "{root}/tests/a.min", O_RDONLY) = 4',
        f'202 openat(AT_FDCWD, "docs", O_RDONLY|O_DIRECTORY <unfinished ...>',
        f'202 <... openat resumed>) = 5',
        f'202 openat(5, "guide.md", O_RDONLY) = 6',
        f'202 chdir("library") = 0',
        f'202 openat(AT_FDCWD, "json.min", O_RDONLY) = 7',
        f'202 openat(AT_FDCWD, "/tmp/scratch/x.min", O_RDONLY) = 8',
        f'202 openat(AT_FDCWD, "{root}/library/missing.min", O_RDONLY) = -1 ENOENT (No such file or directory)',
        # A nested Make that builds a goal: its parse and stats are covered by the goal's rules.
        f'202 clone(child_stack=NULL) = 203',
        f'203 execve("/usr/bin/make", ["make", "-s", "build/minyarc"], 0x1 /* 3 vars */) = 0',
        f'203 openat(AT_FDCWD, "Makefile", O_RDONLY) = 3',
        f'203 openat(AT_FDCWD, "{root}/build-support/a.mk", O_RDONLY) = 3',
        f'203 newfstatat(AT_FDCWD, "{root}/compiler/compiler.min", {{st_mode=S_IFREG}}, 0) = 0',
        # A Make that prints its database depends on every makefile: its reads count.
        f'202 clone(child_stack=NULL) = 204',
        f'204 execve("/usr/bin/make", ["make", "-pnq", "FORCE"], 0x1 /* 3 vars */) = 0',
        f'204 openat(AT_FDCWD, "{root}/build-support/b.mk", O_RDONLY) = 3',
        # A shared build outside every check is not attributed.
        f'100 clone(child_stack=NULL) = 300',
        f'300 openat(AT_FDCWD, "{root}/compiler/compiler.min", O_RDONLY) = 3',
    ]
    trace = tree / "trace.log"
    trace.write_text("\n".join(lines) + "\n")
    reads, listed, executed, goals, inspected = dev.parse_trace(trace, tree, ["check-a"])
    reads, listed = reads["check-a"], listed["check-a"]
    expect(goals["check-a"] == {"build/minyarc"}, f"nested Make goals: {goals['check-a']}")
    expect("build-support/a.mk" not in reads and "compiler/compiler.min" not in reads, "a building Make's parse leaked")
    expect("build-support/b.mk" in reads, "a database-printing Make must keep its makefile reads")
    expect("tests/a.min" in reads, f"fixture read missing: {sorted(reads)}")
    expect("docs/guide.md" in reads, "directory-descriptor relative open not resolved")
    expect("library/json.min" in reads, "open after chdir not resolved")
    expect("library/missing.min" in reads, "failed lookups must count: a new file there changes behaviour")
    expect("build/tooling/tests/a" in executed["check-a"], "executed harness missing")
    expect(listed == {"docs"}, f"only the recipe's listing counts, got {sorted(listed)}")
    expect("Makefile" not in reads and "build/tooling/tests/a.ll.d" not in reads, "Make parse leaked into reads")
    expect("compiler/compiler.min" not in reads, "a shared build was attributed to a check")


def database(rules, variables=None, phony=()):
    return {"rules": {name: {"prerequisites": prerequisites, "order_only": [], "recipe": recipe}
                      for name, (prerequisites, recipe) in rules.items()},
            "variables": variables or {}, "phony": sorted(phony)}


def selection():
    base_rules = {"check-portable": (["check-a", "check-b", "check-c"], []),
                  "check-a": (["build/a"], ["./build/a"]), "check-b": (["build/b"], ["$(LIMITED) ./build/b"]),
                  "check-c": (["build/c"], ["./build/c"])}
    phony = {"check-portable", "check-a", "check-b", "check-c"}
    old = database(base_rules, {"LIMITED": "sh limits.sh"}, phony)
    index = {"rules": {name: dev.rule_text(old, name) for name in old["rules"]}, "variables": old["variables"],
             "checks": {
                 "check-a": {"passed": True, "traced": True, "reads": {"tests/a.min", "build/a"}, "listed": set(), "executed": set()},
                 "check-b": {"passed": True, "traced": True, "reads": {"build/b"}, "listed": {"tests"}, "executed": set()},
                 "check-c": {"passed": True, "traced": True, "reads": {"build/c"}, "listed": set(), "executed": set()},
             }}
    checks = dev.checks_of(old, ["check-portable"])
    expect(checks == ["check-a", "check-b", "check-c"], f"aggregate expansion: {checks}")
    reasons, _, _ = dev.select(index, old, checks, ["tests/a.min"], [], [], [])
    expect(set(reasons) == {"check-a"}, f"source read selects only its reader: {reasons}")
    reasons, _, _ = dev.select(index, old, checks, [], [], [], ["build/c"])
    expect(set(reasons) == {"check-c"}, f"stale output selects its user: {reasons}")
    reasons, _, _ = dev.select(index, old, checks, ["tests/new.sh"], ["tests/new.sh"], [], [])
    expect(set(reasons) == {"check-b"}, f"added file selects the directory lister: {reasons}")
    reasons, _, _ = dev.select(index, old, checks, ["docs/x.md"], [], [], [])
    expect(not reasons, f"an unobserved file selects nothing: {reasons}")
    new_variable = database(base_rules, {"LIMITED": "sh other.sh"}, phony)
    reasons, _, _ = dev.select(index, new_variable, checks, [], [], [], [])
    expect(set(reasons) == {"check-b"}, f"variable change selects its users: {reasons}")
    changed_rule = dict(base_rules, **{"check-c": (["build/c"], ["./build/c --strict"])})
    reasons, _, _ = dev.select(index, database(changed_rule, {"LIMITED": "sh limits.sh"}, phony), checks, [], [], [], [])
    expect(set(reasons) == {"check-c"}, f"recipe change selects its check: {reasons}")
    added = dict(base_rules, **{"check-portable": (["check-a", "check-b", "check-c", "check-d"], []), "check-d": ([], ["true"])})
    new = database(added, {"LIMITED": "sh limits.sh"}, phony | {"check-d"})
    reasons, _, _ = dev.select(index, new, dev.checks_of(new, ["check-portable"]), [], [], [], [])
    expect("check-d" in reasons, f"a new check always runs: {reasons}")
    index["checks"]["check-a"]["passed"] = False
    reasons, _, _ = dev.select(index, old, checks, [], [], [], [])
    expect(not reasons, f"a check red at base is not rerun for an unrelated change: {reasons}")
    reasons, _, _ = dev.select(index, old, checks, ["tests/a.min"], [], [], [])
    expect(set(reasons) == {"check-a"}, f"a check red at base reruns when its partial trace is hit: {reasons}")
    index["checks"]["check-a"].update(passed=True, traced=False)
    reasons, _, _ = dev.select(index, old, checks, [], [], [], [])
    expect(set(reasons) == {"check-a"}, f"a passing check without a trace always runs: {reasons}")


def timestamps(tree):
    (tree / "a.min").write_text("one")
    (tree / "b.min").write_text("two")
    os.utime(tree / "a.min", ns=(10**18, 10**18))
    os.utime(tree / "b.min", ns=(10**18, 10**18))
    base = dev.manifest(tree)
    index = {"manifest": base}
    state = tree / "build" / "dev-check"
    state.mkdir(parents=True)
    old_state, dev.STATE = dev.STATE, state
    try:
        built = state / "built.json"
        # A synced copy: same content with a newer mtime, and a real edit with an older mtime.
        os.utime(tree / "a.min", ns=(2 * 10**18, 2 * 10**18))
        (tree / "b.min").write_text("changed")
        os.utime(tree / "b.min", ns=(10, 10))
        changed, added, removed, _, current = dev.changed_sources(tree, index, None, built)
        expect(changed == ["b.min"], f"content decides what changed: {changed}")
        expect(os.stat(tree / "a.min").st_mtime_ns == 10**18, "unchanged content must get its built mtime back")
        expect(os.stat(tree / "b.min").st_mtime_ns > 10**18, "edited content must look newer than every output")
        built.write_text(json.dumps(current))
        # Revert to base content after building the edit: outputs reflect the edit, so it must look new again.
        (tree / "b.min").write_text("two")
        os.utime(tree / "b.min", ns=(10**18, 10**18))
        changed, _, _, _, _ = dev.changed_sources(tree, index, None, built)
        expect(changed == [], f"reverted content is unchanged against the base: {changed}")
        expect(os.stat(tree / "b.min").st_mtime_ns > 10**18, "a revert after a build must still rebuild")
        changed, _, _, ignored, _ = dev.changed_sources(tree, index, ["docs"], built)
    finally:
        dev.STATE = old_state


with tempfile.TemporaryDirectory(prefix="dev-check-test ") as temporary:
    tree = Path(temporary)
    trace_attribution(tree)
    selection()
    (tree / "t").mkdir()
    timestamps(tree / "t")

for failure in failures:
    print("FAIL:", failure)
print("dev-check selector tests:", "failed" if failures else "passed")
raise SystemExit(1 if failures else 0)
