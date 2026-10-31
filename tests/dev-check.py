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
        f'202 openat(AT_FDCWD, "{root}/build/tooling/tests/a.out", O_WRONLY|O_CREAT|O_TRUNC, 0644) = 4',
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
    reads, listed, executed, goals, inspected, inspectors, writes, writers, outside = dev.parse_trace(trace, tree, ["check-a"])
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
    expect(inspectors["check-a"] == {path: {"a"} for path in ("tests/a.min", "docs/guide.md", "library/json.min",
                                                             "library/missing.min")},
           f"an inspector of a data read is recorded: {inspectors['check-a']}")
    expect(outside["check-a"] == {"/tmp/scratch/x.min"},
           f"tree-external reads are recorded (a cache must not reuse this check): {outside['check-a']}")
    expect(writers["check-a"] == {"a"} and "build/tooling/tests/a.out" in writes["check-a"],
           f"a check's own writing programs are recorded: {writers['check-a']}")


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


def functions():
    c = """#include "x.h"
#define LIMIT 4 /* macro */
struct pair { int a; int b; };
static const int table[] = { 1, 2 };
static inline __attribute__((always_inline)) int add(int a, int b) { return a + b; }
int scale(struct pair p) {
    if (p.a > LIMIT) { return p.b; } // comment
    return add(p.a, "}"[0]);
}
"""
    base = dev.function_snapshot(c, "c")
    expect(set(base["functions"]) == {"add", "scale"}, f"C functions: {sorted(base['functions'])}")
    names, why = diff(base, c.replace("return p.b;", "return p.b + 1;"), "c")
    expect(names == {"scale"} and why is None, f"a body edit names its function: {names} {why}")
    names, why = diff(base, c.replace("// comment", "// other words"), "c")
    expect(names == set() and why is None, f"comment edits change nothing: {names} {why}")
    _, why = diff(base, c.replace("LIMIT 4", "LIMIT 5"), "c")
    expect(why is not None, "a macro edit widens")
    _, why = diff(base, c.replace("{ 1, 2 }", "{ 1, 3 }"), "c")
    expect(why is not None, "a table edit widens")
    _, why = diff(base, c.replace("int scale(struct pair p)", "long scale(struct pair p)"), "c")
    expect(why is not None, "a signature edit widens")
    minyar = """use "text" as text
let limit = 4
function grow(value: Integer): Integer {
    let doubled = value * 2 // twice
    return doubled + limit
}
public function shrink(value: Integer): Integer { return value / 2 }
"""
    base = dev.function_snapshot(minyar, "minyar")
    expect(set(base["functions"]) == {"grow", "shrink"}, f"Minyar functions: {sorted(base['functions'])}")
    names, why = diff(base, minyar.replace("value * 2", "value * 3"), "minyar")
    expect(names == {"grow"} and why is None, f"Minyar body edit: {names} {why}")
    _, why = diff(base, minyar.replace("let limit = 4", "let limit = 5"), "minyar")
    expect(why is not None, "a top-level constant edit widens")
    expect(dev.coverage_name(".minyar.fn.minyar_module_12d08f43ace44eb8_grow") == ("minyar", "grow"), "compiler names")
    expect(dev.coverage_name("runtime/minyar_runtime.c;add") == ("c", "add"), "static C names")


def diff(base, text, language):
    with tempfile.TemporaryDirectory() as temporary:
        path = "compiler/a.min" if language == "minyar" else "runtime/a.c"
        (Path(temporary) / path).parent.mkdir(parents=True)
        (Path(temporary) / path).write_text(text)
        names, why = dev.changed_functions(Path(temporary), {path: base}, [path])
        return (names or {}).get(language, set()), why


def coverage_shim(tree):
    """The instrumented-gate clang shim: what it instruments, and which runtime/compiler uses it must keep logged so
    the check is never treated as covered by function counters it does not have."""
    import subprocess
    real, data = tree / "real-clang", tree / "cov"
    (data / "_lost").mkdir(parents=True)
    real.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{tree}/calls.log"\n')
    real.chmod(0o755)
    shim = ROOT / "tools" / "dev-check-coverage" / "clang"
    environment = {"DEVCHECK_REAL_CLANG": str(real), "DEVCHECK_COV_DATA": str(data), "DEVCHECK_COV_CHECK": "check-x",
                   "PATH": os.environ.get("PATH", "/bin:/usr/bin")}

    def run(*arguments):
        (tree / "calls.log").unlink(missing_ok=True)
        subprocess.run(["sh", str(shim), *arguments], env=environment, check=True)
        call = (tree / "calls.log").read_text().strip() if (tree / "calls.log").exists() else ""
        log = (data / "_uninstrumented.log")
        return call, (log.read_text() if log.exists() else "")

    call, log = run("-O2", "-S", "-emit-llvm", "runtime/minyar_runtime.c", "-o", "x.ll")
    expect("-fprofile-generate" in call and "pgo-instrument-entry" in call,
           f"emitted IR of runtime code is instrumented, so a program built from it keeps its counters: {call}")
    expect("emitted, not run" not in log, f"an instrumented emit is covered: {log}")
    call, log = run("-E", "-dM", "-iquote", "runtime", "runtime.c")
    expect("fprofile" not in call and "emitted, not run" not in log,
           f"-E -dM prints only the macro table: no counters, and no uncovered use to report: {call} {log}")
    call, log = run("-M", "runtime.c")
    expect("fprofile" not in call and "emitted, not run" not in log, f"-M names only files: {call} {log}")
    call, log = run("-E", "runtime.c")
    expect("emitted, not run" in log, f"preprocessed text can show a function body: {log}")
    call, log = run("-O2", "--target=x86_64-unknown-none-elf", "-c", "runtime.c", "-o", "y.o")
    expect("fprofile" not in call and "emitted, not run" in log,
           f"a freestanding target cannot link the profile runtime: {call} {log}")
    call, log = run("-O2", "runtime.c", "-o", "prog")
    expect("--wrap=_exit" in call and "-fprofile-generate" in call, f"a link gets the profile runtime: {call}")


def generator_reads(tree):
    """A check whose program also writes build outputs is building from the changed compiler or runtime source: the
    cut-off measures what it generates and the coverage index sees what it runs, so the read is not a data assertion.
    A reader that wrote nothing in the tree (sha256sum for a cache key, a printer) still selects its check."""
    (tree / "runtime").mkdir()
    source = "int keep(void) { return 1; }\nint change(void) { return 2; }\n"
    before = dev.function_snapshot(source, "c")
    (tree / "runtime" / "a.c").write_text(source.replace("return 2;", "return 3;"))
    coverage = {"names": ["runtime/a.c;keep", "runtime/a.c;change"], "universe": [0, 1], "top": [], "lost": [],
                "snapshots": {"runtime/a.c": before},
                "checks": {name: {"covered": [], "complete": True, "why": ""} for name in ("check-build", "check-hash")}}
    index = {"checks": {
        "check-build": {"inspected": {"runtime/a.c"}, "inspectors": {"runtime/a.c": ["clang-driver"]},
                        "writers": ["clang-driver", "make"]},
        "check-hash": {"inspected": {"runtime/a.c"}, "inspectors": {"runtime/a.c": ["sha256sum"]},
                       "writers": ["minyar"]},
        "check-plain": {"inspected": {"runtime/a.c"}},
    }}
    note, reasons, _ = dev.function_selection(tree, index, coverage, ["check-build", "check-hash", "check-plain"],
                                              ["runtime/a.c"], [])
    expect(note is None and "check-build" not in reasons, f"a generating reader is not a data use: {note} {reasons}")
    expect("inspects runtime/a.c" in "; ".join(reasons.get("check-hash", [])),
           f"a hashing reader still selects: {reasons}")
    expect("inspects runtime/a.c" in "; ".join(reasons.get("check-plain", [])),
           f"without recorded inspectors the read counts: {reasons}")


def shards():
    """--shard K/N: the selected checks, bin-packed longest-first, cost about the same on each box."""
    index = {"checks": {f"check-{i}": {"cpu_ms": cpu} for i, cpu in enumerate([100, 90, 80, 70, 60, 50])}}
    bins = dev.shard_plan(index, list(index["checks"]), 3)
    loads = [sum(index["checks"][check]["cpu_ms"] for check in items) for items in bins]
    expect(sorted(check for items in bins for check in items) == sorted(index["checks"]),
           f"every selected check lands in exactly one shard: {bins}")
    expect(max(loads) - min(loads) <= 100, f"shards are balanced: {loads}")


functions()
with tempfile.TemporaryDirectory(prefix="dev-check-test ") as temporary:
    tree = Path(temporary)
    trace_attribution(tree)
    coverage_shim(tree)
    (tree / "gen").mkdir()
    generator_reads(tree / "gen")
    selection()
    (tree / "t").mkdir()
    timestamps(tree / "t")

shards()
for failure in failures:
    print("FAIL:", failure)
print("dev-check selector tests:", "failed" if failures else "passed")
raise SystemExit(1 if failures else 0)
