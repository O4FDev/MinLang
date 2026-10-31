#!/usr/bin/env python3
"""dev-check: run exactly the gate checks a change can affect, against a warm prebuilt tree.

Selection is derived from recorded dependencies, not from a hand-written map:
- `index` runs the gate (check-in-parallel) once on the base tree under strace and records, per
  check, every path its processes opened, stat'ed or executed and every directory they listed.
- `run` finds the changed sources (content hashes against the indexed base), asks Make which
  build outputs the change makes stale (its real dependency graph, including the .ll.d import
  files), and selects every check that touched a changed source or stale output, listed a
  directory that gained or lost a file, or whose Make rule or variables changed. Checks without a
  clean base trace always run. The selected checks run through check-in-parallel.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "build" / "dev-check"
SKIP_TOP = {".git", "build", "target"}
INDEX_SCHEMA = 2
GATE_REMINDER = "Run the full gate (make check-in-parallel CHECKS=check-portable) before merging."


def say(*parts):
    print("dev-check:", *parts, flush=True)


# ---------------------------------------------------------------------------- sources

def source_files(root):
    result = []
    for directory, names, files in os.walk(root):
        relative_dir = os.path.relpath(directory, root)
        if relative_dir == ".":
            names[:] = [name for name in names if name not in SKIP_TOP]
            relative_dir = ""
        names[:] = [name for name in names if name != "__pycache__"]
        for name in files:
            if name.endswith(".pyc") or (relative_dir == "" and name == ".bb-files"):
                continue
            path = os.path.join(relative_dir, name) if relative_dir else name
            if os.path.islink(os.path.join(root, path)) or os.path.isfile(os.path.join(root, path)):
                result.append(path)
    return result


def manifest(root, cache=None):
    """path -> [sha256, mtime_ns]; reuses cached hashes when size and mtime match."""
    cache = cache or {}
    result = {}
    for path in source_files(root):
        full = os.path.join(root, path)
        status = os.lstat(full)
        old = cache.get(path)
        if old and len(old) >= 3 and old[1] == status.st_mtime_ns and old[2] == status.st_size:
            result[path] = [old[0], status.st_mtime_ns, status.st_size]
            continue
        hasher = hashlib.sha256()
        if os.path.islink(full):
            hasher.update(b"link:" + os.readlink(full).encode())
        else:
            with open(full, "rb") as source:
                for chunk in iter(lambda: source.read(1 << 20), b""):
                    hasher.update(chunk)
        result[path] = [hasher.hexdigest(), status.st_mtime_ns, status.st_size]
    return result


# ---------------------------------------------------------------------------- make database

def make_database(root, aggregate):
    environment = clean_environment()
    # Ask about FORCE (as the check runner does) so no goal triggers implicit-rule search: the printed
    # rules are then the explicit ones only and do not depend on which goals were asked about.
    text = subprocess.run(["make", "-pnq", "--no-print-directory", "FORCE"], cwd=root, env=environment,
                          capture_output=True, text=True, errors="replace").stdout
    variables, rules, phony = {}, {}, set()
    section = None
    current = None
    origin = ""
    for line in text.split("\n"):
        if line.startswith("# Variables"):
            section = "variables"; continue
        if line.startswith("# Files"):
            section = "files"; continue
        if line.startswith("# Pattern-specific") or line.startswith("# Directories") or line.startswith("# VPATH"):
            section = None; continue
        if line.startswith("# Implicit Rules"):
            section = "implicit"; continue
        if section == "variables":
            if line.startswith("# "):
                origin = line
                continue
            if not origin.startswith("# makefile"):
                continue
            match = re.match(r"^([A-Za-z_.][A-Za-z0-9_.\-]*) (?::{1,3}=|\+=|\?=|=) ?(.*)$", line)
            if match and match.group(1) not in ("MAKEFLAGS", "MFLAGS", "MAKECMDGOALS", "CURDIR", "MAKE_RESTARTS", "MAKEFILE_LIST",
                                                  ".VARIABLES", "MAKE_COMMAND", "MAKEOVERRIDES", "GNUMAKEFLAGS"):
                variables[match.group(1)] = match.group(2)
            continue
        if section in ("files", "implicit"):
            if line.startswith("\t"):
                if current is not None:
                    rules[current]["recipe"].append(line[1:])
                continue
            if not line or line.startswith("#"):
                if line.startswith("#  Phony target") and current is not None:
                    phony.add(current)
                continue
            match = re.match(r"^([^:#=\s][^:=]*?):{1,2}(?!=)\s*(.*)$", line)
            if match:
                name = match.group(1).strip()
                prerequisites = match.group(2).split("|")[0].split()
                order_only = match.group(2).split("|")[1].split() if "|" in match.group(2) else []
                if name == "Makefile" or name.endswith((".mk", ".d")):
                    current = None
                    continue  # makefiles themselves; their effect is in the rules and variables
                key = ("pattern:" + name) if "%" in name else name
                rules[key] = {"prerequisites": prerequisites, "order_only": order_only, "recipe": []}
                current = key
                if name == ".PHONY":
                    phony.update(prerequisites)
            else:
                current = None
    return {"variables": variables, "rules": rules, "phony": sorted(phony)}


def checks_of(database, aggregate):
    """Phony check targets the runner would run for an aggregate (leaves and nested phony prerequisites)."""
    phony = set(database["phony"])
    rules = database["rules"]
    seen, order = set(), []
    stack = list(reversed(aggregate))
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in phony:
            order.append(name)
            rule = rules.get(name, {"prerequisites": []})
            stack.extend(reversed([item for item in rule["prerequisites"] if item in phony]))
    return [name for name in order if name not in aggregate or rules.get(name, {}).get("recipe")]


def rule_text(database, name):
    rule = database["rules"].get(name)
    if rule is None:
        return None
    return " ".join(rule["prerequisites"]) + " | " + " ".join(rule["order_only"]) + "\n" + "\n".join(rule["recipe"])


def file_prerequisites(database, checks):
    phony = set(database["phony"])
    result = set()
    for name in checks:
        for item in database["rules"].get(name, {"prerequisites": []})["prerequisites"]:
            if item not in phony:
                result.add(item)
    return sorted(result)


def variable_references(text):
    return set(re.findall(r"\$[({]([A-Za-z_][A-Za-z0-9_.\-]*)", text)) | set(re.findall(r"\$([A-Za-z_])(?![A-Za-z0-9_])", text))


# ---------------------------------------------------------------------------- strace parsing

LINE = re.compile(r"^(\d+) (.*)$")
CALL = re.compile(r"^(?:<\.\.\. )?([a-z0-9_]+)(?: resumed>)?\(?(.*)$")
STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
RESULT = re.compile(r"= (-?\d+)(?: [A-Z]+.*)?$")
PATH_CALLS = {"open", "openat", "openat2", "creat", "stat", "lstat", "newfstatat", "fstatat64", "statx", "access",
              "faccessat", "faccessat2", "readlink", "readlinkat", "execve", "execveat", "truncate", "chdir"}
CLONES = {"clone", "clone3", "fork", "vfork"}


def unescape(text):
    return text.encode("latin-1", "backslashreplace").decode("unicode_escape").encode("latin-1", "replace").decode("utf-8", "replace")


def parse_trace(trace, root, checks):
    root = str(root).rstrip("/")
    checks = set(checks)
    parent, check_of_pid, exe_of_pid, root_make = {}, {}, {}, set()
    cloned_at, parsed_until = {}, {}
    # Pass 1: process tree and check roots. A check's own `make -j1 check-x` process parses the
    # Makefile first ($(wildcard), $(shell find ...), -include of .d files); those effects reach the
    # check only through Make's rules and variables, which `run` compares directly, so the parse
    # phase (and processes it spawns) is not recorded as the check's file use.
    with open(trace, errors="replace") as source:
        for number, line in enumerate(source):
            match = LINE.match(line)
            if not match:
                continue
            pid, rest = int(match.group(1)), match.group(2)
            call = CALL.match(rest)
            if not call:
                continue
            name = call.group(1)
            if name in CLONES and "= " in rest and "<unfinished" not in rest:
                result = RESULT.search(rest)
                if result and int(result.group(1)) > 0:
                    parent.setdefault(int(result.group(1)), pid)
                    cloned_at.setdefault(int(result.group(1)), number)
            elif pid in root_make and name in ("open", "openat"):
                strings = STRING.findall(rest)
                if strings:
                    path = unescape(strings[0])
                    if path.endswith((".mk", ".d", "/Makefile")) or path == "Makefile":
                        parsed_until[pid] = number
            elif name == "execve" and not rest.startswith("<..."):
                strings = STRING.findall(rest)
                if strings:
                    exe_of_pid.setdefault(pid, []).append(os.path.basename(unescape(strings[0])))
                    argv = [unescape(item) for item in strings[1:]]
                    if (os.path.basename(unescape(strings[0])) == "make" and "-j1" in argv and argv
                            and argv[-1] in checks):
                        check_of_pid[pid] = argv[-1]
                        root_make.add(pid)

    def owner(pid):
        seen = 0
        if pid in root_make:
            return None  # the check's Make itself: parse and prerequisite stats
        while pid is not None and seen < 10000:
            up = parent.get(pid)
            if up in root_make and cloned_at.get(pid, -1) < parsed_until.get(up, -1):
                return None  # spawned by $(shell ...) while Make parsed
            if pid in check_of_pid:
                return check_of_pid[pid]
            pid = up
            seen += 1
        return None

    cache = {}
    reads = {name: set() for name in checks}
    listed = {name: set() for name in checks}
    executed = {name: set() for name in checks}
    cwd = {}
    pending = {}
    pending_directory, directories = {}, {}
    with open(trace, errors="replace") as source:
        for line in source:
            match = LINE.match(line)
            if not match:
                continue
            pid, rest = int(match.group(1)), match.group(2)
            if rest.startswith("<..."):
                # Resumed calls carry no new path; their start line was recorded.
                result = RESULT.search(rest)
                if pid in pending and "chdir" in rest:
                    if result and result.group(1) == "0":
                        cwd[pid] = pending.pop(pid)
                elif pid in pending_directory and "open" in rest:
                    if result and int(result.group(1)) >= 0:
                        directories.setdefault(pid, {})[int(result.group(1))] = pending_directory.pop(pid)
                continue
            call = CALL.match(rest)
            if not call or call.group(1) not in PATH_CALLS:
                continue
            name = call.group(1)
            if pid not in cache:
                cache[pid] = owner(pid)
            check = cache[pid]
            strings = STRING.findall(rest)
            if not strings:
                continue
            path = unescape(strings[0])
            if pid not in cwd:
                ancestor = parent.get(pid)
                cwd[pid] = cwd.get(ancestor, root) if ancestor is not None else root
            if not path.startswith("/"):
                base = cwd[pid]
                if name in ("openat", "openat2", "newfstatat", "faccessat", "faccessat2", "readlinkat", "statx", "execveat"):
                    first = call.group(2).split(",", 1)[0].strip()
                    if first != "AT_FDCWD":
                        base = None
                        if first.isdigit():
                            walk = pid
                            while walk is not None and base is None:
                                base = directories.get(walk, {}).get(int(first))
                                walk = parent.get(walk)
                        if base is None:
                            continue  # relative to a descriptor we did not see opened
                path = os.path.normpath(os.path.join(base, path))
            if name in ("open", "openat", "openat2") and "O_DIRECTORY" in rest:
                if "<unfinished" in rest:
                    pending_directory[pid] = path
                else:
                    result = RESULT.search(rest)
                    if result and int(result.group(1)) >= 0:
                        directories.setdefault(pid, {})[int(result.group(1))] = path
            if name == "chdir":
                if "<unfinished" in rest:
                    pending[pid] = path
                elif RESULT.search(rest) and RESULT.search(rest).group(1) == "0":
                    cwd[pid] = path
                continue
            if check is None:
                continue
            if path != root and not path.startswith(root + "/"):
                continue
            relative = path[len(root) + 1:] if path != root else "."
            if relative.startswith("build/check-in-parallel/") or relative.startswith("build/dev-check/"):
                continue
            exe = (exe_of_pid.get(pid) or [""])[-1]
            if exe == "make" and (relative == "Makefile" or relative.endswith(".mk") or relative.endswith(".d")):
                if pid in root_make or relative.endswith(".d"):
                    continue  # the check's own Make parse; covered by the rule comparison
            if "O_DIRECTORY" in rest:
                listed[check].add(relative)
            elif name in ("execve", "execveat"):
                executed[check].add(relative)
                reads[check].add(relative)
            else:
                reads[check].add(relative)
    return reads, listed, executed


# ---------------------------------------------------------------------------- helpers

def clean_environment():
    environment = os.environ.copy()
    for name in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEFILES", "GNUMAKEFLAGS"):
        environment.pop(name, None)
    return environment


def trace_environment(root):
    """LeakSanitizer stops the world with ptrace and aborts under a tracer. Its documented hook
    __lsan_is_turned_off, preloaded, skips only the exit-time leak scan, which reads no repository files,
    so traced sanitizer checks record the same dependencies. Pass/fail of a check that only failed traced
    is taken from an untraced run."""
    environment = clean_environment()
    STATE.mkdir(parents=True, exist_ok=True)
    source, library = STATE / "lsan-off.c", STATE / "lsan-off.so"
    source.write_text("int __lsan_is_turned_off(void) { return 1; }\n")
    compiler = environment.get("LLVM_CC") or "cc"
    if subprocess.run([compiler, "-shared", "-fPIC", "-O1", str(source), "-o", str(library)],
                      capture_output=True).returncode == 0:
        environment["LD_PRELOAD"] = str(library)
    return environment


def latest_results(root):
    runs = sorted((root / "build" / "check-in-parallel").glob("run-*/results.json"), key=lambda path: path.stat().st_mtime)
    if not runs:
        return None, None
    data = json.loads(runs[-1].read_text())
    times = {}
    tsv = runs[-1].parent / "times.tsv"
    if tsv.exists():
        for line in tsv.read_text().splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 4:
                times[parts[0]] = {"wall_ms": int(parts[1]), "cpu_ms": int(parts[2]), "passed": parts[3] == "true"}
    return data, times


def load_index(path):
    data = json.loads(Path(path).read_text())
    if data.get("schema") != INDEX_SCHEMA:
        raise SystemExit(f"dev-check: index {path} has schema {data.get('schema')}, expected {INDEX_SCHEMA}; rebuild it")
    paths = data["paths"]
    for check in data["checks"].values():
        for key in ("reads", "listed", "executed"):
            check[key] = {paths[item] for item in check[key]}
    return data


# ---------------------------------------------------------------------------- commands

def command_index(arguments):
    root = ROOT
    STATE.mkdir(parents=True, exist_ok=True)
    aggregate = arguments.checks.split()
    database = make_database(root, aggregate)
    checks = checks_of(database, aggregate)
    say(f"indexing {len(checks)} checks of {' '.join(aggregate)} under strace with {arguments.jobs} jobs")
    base = manifest(root)
    trace = Path(arguments.trace or (STATE / "trace.log"))
    started = time.time()
    if not arguments.reuse_trace:
        command = ["strace", "-f", "-qq", "--seccomp-bpf", "-s", "4096", "-o", str(trace),
                   "-e", "trace=%file,%process", "make", "--no-print-directory", "check-in-parallel",
                   "CHECKS=" + " ".join(aggregate), f"CHECK_JOBS={arguments.jobs}"]
        status = subprocess.run(command, cwd=root, env=trace_environment(root)).returncode
        say(f"traced gate exited {status} after {time.time() - started:.0f} s")
    results, times = latest_results(root)
    if arguments.results_log:
        # A runner console log of the traced gate (the runner keeps only its latest run directory).
        results, times = {"checks": []}, {}
        for line in Path(arguments.results_log).read_text(errors="replace").splitlines():
            match = re.match(r"^(check-[^:\s]+): (passed|FAILED) wall_ms=(\d+).*?rss_kib=([\d.]+) ([\d.]+)", line)
            if match:
                times[match.group(1)] = {"wall_ms": int(match.group(3)), "passed": match.group(2) == "passed",
                                         "cpu_ms": int((float(match.group(4)) + float(match.group(5))) * 1000)}
            elif re.match(r"^(check-[^:\s]+): FAILED", line):
                times[line.split(":")[0]] = {"wall_ms": 0, "cpu_ms": 0, "passed": False}
    times = dict(times or {})
    passed = {item["target"]: item["passed"] for item in (results or {}).get("checks", [])}
    passed.update({name: entry["passed"] for name, entry in times.items()})
    traces = [trace]
    untraced_pass = {}
    # The aggregate's own recipe cannot run without all of its prerequisites; it is selected statically.
    failed = [name for name in checks if not passed.get(name, False) and name not in aggregate]
    if failed and (not arguments.reuse_trace or arguments.retry):
        # Retry failures alone under the tracer (load or ordering), then untraced to tell a base failure
        # from a check that cannot run under strace. Either way they are selected on every run.
        retry = trace.with_name(trace.stem + "-retry.log")
        # LeakSanitizer stops the world with ptrace, which fails under a tracer; leak detection reads no
        # repository files, so the retry records the same dependencies without it.
        retry_environment = trace_environment(root)
        retry_environment["ASAN_OPTIONS"] = "detect_leaks=0"
        say(f"retrying {len(failed)} failed check(s) under strace: {' '.join(failed)}")
        subprocess.run(["strace", "-f", "-qq", "--seccomp-bpf", "-s", "4096", "-o", str(retry), "-e", "trace=%file,%process",
                        "make", "--no-print-directory", "check-in-parallel", "CHECKS=" + " ".join(failed),
                        f"CHECK_JOBS={arguments.jobs}"], cwd=root, env=retry_environment)
        traces.append(retry)
        _, retry_times = latest_results(root)  # results.json lists failures only; times.tsv lists every check
        for name, timing in (retry_times or {}).items():
            if name in failed and timing["passed"]:
                passed[name] = True
                times[name] = timing
        still = [name for name in failed if not passed.get(name)]
        if still:
            say(f"running {len(still)} check(s) untraced: {' '.join(still)}")
            subprocess.run(["make", "--no-print-directory", "check-in-parallel", "CHECKS=" + " ".join(still),
                            f"CHECK_JOBS={arguments.jobs}"], cwd=root, env=clean_environment())
            _, plain_times = latest_results(root)
            for name, timing in (plain_times or {}).items():
                if name in still:
                    untraced_pass[name] = timing["passed"]
    elif arguments.reuse_trace and trace.with_name(trace.stem + "-retry.log").exists():
        traces.append(trace.with_name(trace.stem + "-retry.log"))
    reads, listed, executed = {name: set() for name in checks}, {name: set() for name in checks}, {name: set() for name in checks}
    for item in traces:
        more = parse_trace(item, root, checks)
        for target, extra in zip((reads, listed, executed), more):
            for name in checks:
                target[name] |= extra[name]
    table, numbers = [], {}

    def number(path):
        if path not in numbers:
            numbers[path] = len(table); table.append(path)
        return numbers[path]

    entries = {}
    for check in checks:
        timing = times.get(check, {})
        status = passed.get(check, False)
        entries[check] = {
            "static": check in aggregate,
            "passed": bool(status) or untraced_pass.get(check, False) or check in aggregate,
            # A phony check without a recipe has nothing of its own to observe.
            "traced": bool(status) and bool(reads[check] or listed[check] or not database["rules"].get(check, {}).get("recipe")),
            "wall_ms": timing.get("wall_ms", 0), "cpu_ms": timing.get("cpu_ms", 0),
            "reads": sorted(number(path) for path in reads[check]),
            "listed": sorted(number(path) for path in listed[check]),
            "executed": sorted(number(path) for path in executed[check]),
        }
    index = {"schema": INDEX_SCHEMA, "aggregate": aggregate, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "gate_wall_s": round(time.time() - started), "manifest": base, "paths": table,
             "rules": {name: rule_text(database, name) for name in database["rules"]},
             "variables": database["variables"], "checks": entries}
    output = Path(arguments.output or (STATE / "index.json"))
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, sort_keys=True))
    temporary.replace(output)
    (STATE / "built.json").write_text(json.dumps(base))
    for stale in ("base.json", "base-make.json"):
        if (STATE / stale).exists():
            (STATE / stale).unlink()
    untraced = [name for name, entry in entries.items() if not entry["traced"]]
    failed = [name for name, entry in entries.items() if not entry["passed"]]
    say(f"wrote {output}: {len(entries)} checks, {len(table)} paths; {len(failed)} not passing at base, {len(untraced)} untraced")
    for name in failed:
        say("  not passing at base (always selected):", name)
    return 0


def base_manifest(index):
    """The tree a change is measured against: the indexed base, or the tree recorded by `rebase`."""
    rebased = STATE / "base.json"
    return json.loads(rebased.read_text()) if rebased.exists() else index["manifest"]


def changed_sources(root, index, only, built_path):
    base = base_manifest(index)
    built = json.loads(built_path.read_text()) if built_path.exists() else base
    bb_files = root / ".bb-files"
    if bb_files.exists():
        # bb copies files but never deletes; a base file missing from the synced list was deleted.
        synced = set(bb_files.read_text().splitlines())
        for path in base:
            if path not in synced and (root / path).exists() and not path.startswith(".") and path != "tools/dev-check.py":
                (root / path).unlink()
    current = manifest(root, built)
    changed = sorted(path for path in set(base) | set(current)
                     if (base.get(path) or [None])[0] != (current.get(path) or [None])[0])
    # Give Make content-true timestamps: synced files keep the copy's mtime, which may be older than
    # outputs built from other content (false up-to-date) or newer than outputs of the same content.
    now = time.time_ns()
    for path, entry in current.items():
        previous = built.get(path)
        target = previous[1] if previous and previous[0] == entry[0] else None
        if target is None:
            target = now
        if entry[1] != target:
            os.utime(root / path, ns=(target, target), follow_symlinks=False)
            entry[1] = target
    added = [path for path in changed if path not in base]
    removed = [path for path in changed if path not in current]
    if only:
        prefixes = [item.rstrip("/") for item in only]
        keep = [path for path in changed if any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)]
        ignored = [path for path in changed if path not in keep]
        changed = keep
    else:
        ignored = []
    return changed, added, removed, ignored, current


def stale_outputs(root, targets, database=None):
    """Build outputs the working tree makes stale, by Make's own graph.

    Targets that depend on FORCE (the toolchain stamp, Cargo builds) always "need remaking" in a dry run
    but rewrite their output only when something changed, so run those for real first, count them stale
    only if their output changed, and tell the dry run to treat them as old (-o)."""
    if not targets:
        return set(), ""
    stale, forced = set(), []
    if database is not None:
        forced = [name for name, rule in database["rules"].items()
                  if "FORCE" in rule["prerequisites"] and (root / name).exists()]
    if forced:
        before = {name: (root / name).stat().st_mtime_ns for name in forced}
        subprocess.run(["make", "--no-print-directory", "-s", *forced], cwd=root, env=clean_environment(),
                       stdout=subprocess.DEVNULL)
        stale |= {name for name in forced if not (root / name).exists() or (root / name).stat().st_mtime_ns != before[name]}
    options = [item for name in forced for item in ("-o", name)]
    result = subprocess.run(["make", "-n", "--debug=b", "--no-print-directory", *options, *targets], cwd=root,
                            env=clean_environment(), capture_output=True, text=True, errors="replace")
    stale |= set(re.findall(r"Must remake target '([^']+)'", result.stdout))
    return stale - {"FORCE"}, result.stderr


def select(index, database, checks, changed, added, removed, stale):
    reasons = {}
    changed_set = set(changed) | set(stale)
    parents = set()
    for path in list(added) + list(removed):
        parts = path.split("/")
        for depth in range(len(parts)):
            parents.add("/".join(parts[:depth]) or ".")
    # Make rules and variables that changed relative to the index.
    rebased = STATE / "base-make.json"
    if rebased.exists() and index.get("manifest") is not None:
        recorded = json.loads(rebased.read_text())
        old_rules, old_variables = recorded["rules"], recorded["variables"]
    else:
        old_rules, old_variables = index["rules"], index["variables"]
    new_rules = {name: rule_text(database, name) for name in database["rules"]}
    changed_rules = {name for name in set(old_rules) | set(new_rules) if old_rules.get(name) != new_rules.get(name)}
    changed_variables = {name for name in set(old_variables) | set(database["variables"])
                         if old_variables.get(name) != database["variables"].get(name)}
    # A variable whose definition mentions a changed variable changes too.
    grew = True
    while grew:
        grew = False
        for name, value in database["variables"].items():
            if name not in changed_variables and variable_references(value) & changed_variables:
                changed_variables.add(name); grew = True
    pattern_changed = any(name.startswith("pattern:") for name in changed_rules) or any(
        variable_references(text or "") & changed_variables for name, text in new_rules.items() if name.startswith("pattern:"))
    phony = set(database["phony"])

    def closure(check):
        seen, stack = set(), [check]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            rule = database["rules"].get(name)
            if rule:
                stack.extend(rule["prerequisites"] + rule["order_only"])
        return seen

    for check in checks:
        why = []
        entry = index["checks"].get(check)
        if entry is None:
            why.append("new check (no base trace)")
        elif entry.get("static"):
            # An aggregate goal's own recipe: its file prerequisites and the paths its recipe names.
            rule = database["rules"].get(check, {"prerequisites": [], "recipe": []})
            named = set(rule["prerequisites"]) | {token.strip('"\'') for line in rule["recipe"] for token in line.split()}
            hits = sorted(named & changed_set)
            if hits:
                why.append("its own recipe uses " + ", ".join(hits[:4]) + " (runs the whole aggregate)")
        else:
            if not entry["passed"]:
                why.append("not passing at base")
            elif not entry["traced"]:
                why.append("no base trace")
            hits = sorted(entry["reads"] & changed_set)
            if hits:
                why.append("uses " + ", ".join(hits[:4]) + (f" (+{len(hits) - 4})" if len(hits) > 4 else ""))
            lists = sorted(entry["listed"] & parents)
            if lists:
                why.append("lists " + ", ".join(lists[:3]) + " (a file was added or removed)")
        if changed_rules or changed_variables:
            names = closure(check)
            rule_hits = sorted(names & changed_rules)
            if rule_hits:
                why.append("make rule changed: " + ", ".join(rule_hits[:3]))
            texts = " ".join(new_rules.get(name) or "" for name in names)
            variable_hits = sorted(variable_references(texts) & changed_variables)
            if variable_hits:
                why.append("make variable changed: " + ", ".join(variable_hits[:3]))
            if pattern_changed and any(name not in phony and name not in database["rules"] or
                                       (name in database["rules"] and not database["rules"][name]["recipe"] and name not in phony)
                                       for name in names):
                why.append("make pattern rule changed")
        if why:
            reasons[check] = why
    return reasons, changed_rules, changed_variables


def command_rebase(arguments):
    """Build what the current tree makes stale, then measure later changes against this tree."""
    root = ROOT
    index_path = Path(arguments.index or os.environ.get("DEV_CHECK_INDEX") or (STATE / "index.json"))
    index = load_index(index_path)
    built_path = STATE / "built.json"
    changed, _, _, _, current = changed_sources(root, index, None, built_path)
    database = make_database(root, index["aggregate"])
    prerequisites = file_prerequisites(database, checks_of(database, index["aggregate"]))
    stale, _ = stale_outputs(root, prerequisites, database)
    targets = [item for item in prerequisites if item in stale]
    say(f"{len(changed)} changed source(s); rebuilding {len(targets)} stale prerequisite(s)")
    if targets:
        status = subprocess.run(["make", "-k", "--no-print-directory", *targets], cwd=root, env=clean_environment()).returncode
        if status != 0:
            say("build failed; base not recorded"); return status
    built_path.write_text(json.dumps(current))
    (STATE / "base.json").write_text(json.dumps(current))
    (STATE / "base-make.json").write_text(json.dumps({
        "rules": {name: rule_text(database, name) for name in database["rules"]}, "variables": database["variables"]}))
    say(f"recorded the current tree as the base ({len(current)} files)")
    return 0


def command_run(arguments):
    root = ROOT
    started = time.time()
    index_path = Path(arguments.index or os.environ.get("DEV_CHECK_INDEX") or (STATE / "index.json"))
    if not index_path.exists():
        say(f"no dependency index at {index_path}; build one with `make dev-check-index` on the warm base tree")
        return 2
    index = load_index(index_path)
    STATE.mkdir(parents=True, exist_ok=True)
    built_path = STATE / "built.json"
    changed, added, removed, ignored, current = changed_sources(root, index, arguments.only, built_path)
    aggregate = index["aggregate"]
    database = make_database(root, aggregate)
    checks = checks_of(database, aggregate)
    prerequisites = file_prerequisites(database, checks)
    stale, _ = stale_outputs(root, prerequisites, database)
    stale_build = sorted(path for path in stale if path.startswith("build/"))
    compiler = sorted(path for path in changed if path.startswith(("compiler/", "bootstrap/")))
    if arguments.only and ignored:
        say(f"--only: ignoring {len(ignored)} other changed path(s), e.g. {', '.join(ignored[:3])}")
        stale_build = [path for path in stale_build]  # stale outputs still reflect every change on disk
    reasons, changed_rules, changed_variables = select(index, database, checks, changed, added, removed, stale_build)
    runner_changed = "build/tooling/tools/check-in-parallel" in stale
    if runner_changed:
        reasons = {check: (reasons.get(check) or []) + ["the check runner itself changed"] for check in checks}
    selected = [check for check in checks if check in reasons]
    print(f"Changed sources ({len(changed)}):" + ("" if changed else " none"))
    for path in changed[:40]:
        print("  " + path + (" (added)" if path in added else " (removed)" if path in removed else ""))
    if len(changed) > 40:
        print(f"  ... {len(changed) - 40} more")
    if compiler:
        print("Compiler sources changed: build/minyarc is rebuilt by its normal self-host stages (stage0 only if bootstrap/ changed);")
        print("  every check that compiles Minyar code is affected, so expect close to the full gate.")
    print(f"Stale build outputs: {len(stale_build)}" + (" (" + ", ".join(stale_build[:6]) + (" ..." if len(stale_build) > 6 else "") + ")" if stale_build else ""))
    if changed_rules or changed_variables:
        print(f"Make changes: {len(changed_rules)} rule(s), {len(changed_variables)} variable(s): " +
              ", ".join(sorted(changed_rules)[:5] + sorted(changed_variables)[:5]))
    estimate = sum(index["checks"].get(check, {}).get("cpu_ms", 0) for check in selected) / 1000
    print(f"Selected {len(selected)} of {len(checks)} checks (base CPU about {estimate:.0f} s):")
    for check in selected:
        print(f"  {check}: " + "; ".join(reasons[check]))
    benchmarks = select_benchmarks(root, changed, stale_build)
    if benchmarks:
        print(f"Affected benchmark programs ({len(benchmarks)}): " + " ".join(benchmarks[:30]) + (" ..." if len(benchmarks) > 30 else ""))
    if arguments.plan:
        print(f"Plan only ({time.time() - started:.1f} s). " + GATE_REMINDER)
        return 0
    status, failed = 0, []
    if selected:
        command = ["make", "--no-print-directory", "check-in-parallel", "CHECKS=" + " ".join(selected), f"CHECK_JOBS={arguments.jobs}"]
        status = subprocess.run(command, cwd=root, env=clean_environment()).returncode
        results, _ = latest_results(root)
        failed = [item["target"] for item in (results or {}).get("checks", []) if not item["passed"]]
        if status != 0 and not failed:
            failed = ["(runner failed before reporting checks)"]
    if arguments.bench and benchmarks:
        bench_status = run_benchmarks(root, benchmarks, arguments.bench_base)
        if bench_status != 0 and not failed:
            failed = ["(benchmark outputs differ from the C reference)"]
    # Record what the build now reflects so the next run gives Make true timestamps.
    built_path.write_text(json.dumps(current))
    elapsed = time.time() - started
    base_red_all = bool(failed) and all(name in index["checks"] and not index["checks"][name]["passed"] for name in failed)
    verdict = "GREEN" if not failed else ("BASE-RED" if base_red_all else "RED")
    (STATE / "last.json").write_text(json.dumps({
        "verdict": verdict, "seconds": round(elapsed, 1), "changed": changed, "ignored": ignored,
        "stale": stale_build, "selected": {check: reasons[check] for check in selected}, "failed": failed,
        "considered": len(checks), "benchmarks": benchmarks}, indent=1))
    scope = f"{len(selected)} affected check(s)"
    if arguments.only and ignored:
        scope += f" for --only {' '.join(arguments.only)} ({len(ignored)} other changed path(s) NOT covered)"
    if failed:
        base_red = [name for name in failed if name in index["checks"] and not index["checks"][name]["passed"]]
        if len(base_red) == len(failed):
            print(f"BASE-RED: only checks that already fail at the indexed base failed: {' '.join(failed)} "
                  f"({elapsed:.0f} s). Not caused by this change, but the gate is red. " + GATE_REMINDER)
            return 3
        print(f"RED: {len(failed)} of {len(selected)} failed: " + " ".join(failed))
        if base_red:
            print("  of which already failing at base: " + " ".join(base_red))
        print(f"dev-check RED in {elapsed:.0f} s. " + GATE_REMINDER)
        return 1
    if not selected:
        print(f"GREEN: no gate check can observe this change ({len(checks)} checks considered) in {elapsed:.0f} s. " + GATE_REMINDER)
        return 0
    print(f"GREEN: {scope} passed in {elapsed:.0f} s. " + GATE_REMINDER)
    return 0


def run_benchmarks(root, benchmarks, base_path):
    """Instruction counts (cachegrind) of the affected compare programs against a recorded base run."""
    names = [item.split("/", 1)[1] for item in benchmarks if item.startswith("compare/")]
    if not names:
        print("Benchmarks: no affected benchmarks/compare programs (bothmodes programs are listed only).")
        return 0
    output = STATE / "compare.json"
    command = ["python3", "benchmarks/compare/run.py", "--only", ",".join(names), "--json", str(output)]
    print("Benchmarks: " + " ".join(command))
    status = subprocess.run(command, cwd=root, env=clean_environment(), stdout=subprocess.DEVNULL).returncode
    if status != 0 or not output.exists():
        print(f"Benchmarks: compare run failed (exit {status})")
        return 1
    new = {item["name"]: item for item in json.loads(output.read_text())["programs"]}
    base = {}
    if base_path and Path(base_path).exists():
        base = {item["name"]: item for item in json.loads(Path(base_path).read_text())["programs"]}
    bad = 0
    print(f"  {'program':<14} {'same':<5} {'minyar Ir':>14} {'base Ir':>14} {'change':>8}")
    for name in names:
        item = new.get(name)
        if item is None:
            print(f"  {name:<14} missing"); bad += 1; continue
        ir = item.get("ir", {}).get("minyar")
        old = base.get(name, {}).get("ir", {}).get("minyar")
        change = f"{(ir / old - 1) * 100:+.2f}%" if ir and old else "n/a"
        same = "yes" if item.get("identical") else "NO"
        bad += 0 if item.get("identical") else 1
        print(f"  {name:<14} {same:<5} {ir or 0:>14,} {old or 0:>14,} {change:>8}")
    return 1 if bad else 0


def select_benchmarks(root, changed, stale_build):
    """Benchmark programs whose sources import a changed module, or all of them for compiler/runtime changes."""
    programs = []
    for suite in ("compare", "bothmodes"):
        directory = root / "benchmarks" / suite
        if directory.is_dir():
            programs += [f"{suite}/{item.name}" for item in sorted(directory.iterdir()) if item.is_dir()]
    if not programs:
        return []
    core = [path for path in changed if path.startswith(("compiler/", "bootstrap/", "runtime/"))]
    core += [path for path in stale_build if path in ("build/minyarc", "build/minyar-runtime.o", "build/minyarc-modules")]
    if core:
        return programs
    library = {}
    library_root = root / "library"
    for path in library_root.rglob("*.min") if library_root.is_dir() else []:
        name = path.stem
        library[name] = set(re.findall(r'use\s+"([^"]+)"', path.read_text(errors="replace")))
    touched = {Path(path).stem for path in changed if path.startswith("library/") and path.endswith(".min")}
    grew = True
    while grew:
        grew = False
        for name, imports in library.items():
            if name not in touched and {Path(item).stem for item in imports} & touched:
                touched.add(name); grew = True
    result = []
    for program in programs:
        directory = root / "benchmarks" / program
        hit = any(path.startswith(f"benchmarks/{program}/") for path in changed)
        if not hit and touched:
            for source in directory.rglob("*.min"):
                imports = {Path(item).stem for item in re.findall(r'use\s+"([^"]+)"', source.read_text(errors="replace"))}
                if imports & touched:
                    hit = True; break
        if hit:
            result.append(program)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="select and run the affected checks (default)")
    run.add_argument("--only", nargs="+", help="claim only these changed paths or directories")
    run.add_argument("--plan", action="store_true", help="print the selection without running checks")
    run.add_argument("--jobs", type=int, default=int(os.environ.get("CHECK_JOBS", "4")))
    run.add_argument("--index", help="dependency index (default build/dev-check/index.json or $DEV_CHECK_INDEX)")
    run.add_argument("--bench", action="store_true", help="also measure Ir of affected benchmarks/compare programs")
    run.add_argument("--bench-base", default=os.environ.get("DEV_CHECK_BENCH_BASE"),
                     help="compare.json of the base for Ir deltas (default $DEV_CHECK_BENCH_BASE)")
    rebase = sub.add_parser("rebase", help="build the current tree and measure later changes against it")
    rebase.add_argument("--index")
    index = sub.add_parser("index", help="trace the gate on the base tree and write the dependency index")
    index.add_argument("--checks", default="check-portable")
    index.add_argument("--jobs", type=int, default=8)
    index.add_argument("--trace")
    index.add_argument("--output")
    index.add_argument("--reuse-trace", action="store_true", help="parse an existing trace instead of running the gate")
    index.add_argument("--results-log", help="with --reuse-trace: take base results from this runner console log")
    index.add_argument("--retry", action="store_true", help="with --reuse-trace: still retry the checks that failed")
    arguments = parser.parse_args(sys.argv[1:] if len(sys.argv) > 1 and sys.argv[1] in ("run", "index", "rebase", "-h", "--help") else ["run", *sys.argv[1:]])
    if arguments.command == "index":
        return command_index(arguments)
    if arguments.command == "rebase":
        return command_rebase(arguments)
    return command_run(arguments)


if __name__ == "__main__":
    sys.exit(main())
