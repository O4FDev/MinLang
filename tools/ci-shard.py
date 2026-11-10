#!/usr/bin/env python3
"""ci-shard: print the checks of one CI shard of a Make aggregate, for `make check-in-parallel CHECKS=...`.

    python3 tools/ci-shard.py check-portable 2 4                  # shard 2 of 4 (counted from 1)
    python3 tools/ci-shard.py "check-portable check-sanitize" 1 8  # several aggregates, each check once
    python3 tools/ci-shard.py --list check-portable               # every check with its weight
    python3 tools/ci-shard.py --verdict --status 2 build/ci.log     # judge a run against the known failures

Each aggregate is expanded through phony prerequisites that have no recipe (pure aggregates such as check-portable),
down to the checks that do work; an aggregate with a recipe of its own is one of them. Those are packed onto the shards longest first, using the wall times measured on
the CI runners (tools/ci-times.tsv), then those the local gate recorded (tools/fast-gate/times.tsv); an unknown check
weighs 60 s. `--record-times LOG...` rewrites tools/ci-times.tsv from CI logs. The answer depends only on the tree, so every
shard computes the same split and together they run each check once. check-in-parallel still builds whatever
prerequisites a shard's checks need.

--verdict reads runner output (check-in-parallel or check-linux) and compares the failed checks with
tools/ci-known-failures.txt, the same way land.sh compares a gate with the base's failures: it exits 1 when a check
fails that is not listed, or when the run failed without naming a failed check (a build error). It still prints every
listed failure, and every listed check that passed so it can be removed from the list.
"""
import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Wall times measured on the CI runners (tools/ci-times.tsv, refreshed with --record-times), then the local gate's.
TIMES = [ROOT / "tools" / "ci-times.tsv", ROOT / "tools" / "fast-gate" / "times.tsv"]
KNOWN = ROOT / "tools" / "ci-known-failures.txt"
UNKNOWN_MS = 60000


def database():
    """Return (phony targets, {target: (prerequisites, has_recipe)}) from Make's own database."""
    out = subprocess.run(["make", "-pRrq", "-f", "Makefile", "__ci_shard_no_such_target__"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    rules, phony = {}, set()
    current, files, skip = None, False, False
    for line in out.split("\n"):
        if line == "# Files":
            files = True
            continue
        if not files:
            continue
        if line.startswith("# Not a target"):
            skip = True
            continue
        if line.startswith("\t"):
            if current is not None and not skip:
                prerequisites, _ = rules[current]
                rules[current] = (prerequisites, True)
            continue
        if not line or line.startswith("#"):
            if not line:
                current, skip = None, False
            continue
        head, sep, rest = line.partition(":")
        if not sep or rest.startswith("=") or "=" in head:
            continue
        names = head.split()
        prerequisites = rest.lstrip(":").split("|")[0].split(";")[0].split()
        if names == [".PHONY"]:
            phony.update(prerequisites)
            continue
        if skip or len(names) != 1:
            current = None
            continue
        current = names[0]
        old, recipe = rules.get(current, ([], False))
        rules[current] = (old + prerequisites, recipe)
    return phony, rules


def checks_of(aggregate, phony, rules):
    if aggregate not in rules:
        sys.exit(f"ci-shard: no Make target {aggregate}")
    found, seen, stack = [], set(), [aggregate]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        prerequisites, recipe = rules.get(name, ([], False))
        if recipe:
            found.append(name)  # a check that does work; its phony prerequisites are checks of their own
            if name != aggregate:
                continue
        stack.extend(p for p in reversed(prerequisites) if p in phony)
    return sorted(set(found))


def weights():
    times = {}
    for path in TIMES:
        if path.exists():
            for line in path.read_text().split("\n")[1:]:
                fields = line.split("\t")
                if len(fields) >= 2 and fields[1].isdigit():
                    times.setdefault(fields[0], int(fields[1]))
    return times


def pack(checks, count):
    times = weights()
    shards = [[0, index, []] for index in range(count)]
    for name in sorted(checks, key=lambda c: (-times.get(c, UNKNOWN_MS), c)):
        shard = min(shards, key=lambda s: (s[0], s[1]))
        shard[0] += times.get(name, UNKNOWN_MS)
        shard[2].append(name)
    return shards, times


def record_times(logs):
    times = {}
    for log in logs:
        for line in open(log, errors="replace"):
            match = re.match(r"^(check-[\w-]+): (?:passed|FAILED) wall_ms=(\d+)", re.sub(r"^\S+Z ", "", line))
            if match:
                times[match.group(1)] = max(times.get(match.group(1), 0), int(match.group(2)))
    TIMES[0].write_text("target\twall_ms\n" + "".join(f"{k}\t{times[k]}\n" for k in sorted(times)))


def known_failures():
    known = {}
    for line in KNOWN.read_text().split("\n") if KNOWN.exists() else []:
        name, _, reason = line.partition("#")
        if name.strip():
            known[name.strip()] = reason.strip()
    return known


def verdict(logs, status):
    failed, passed = set(), set()
    for log in logs:
        for line in open(log, errors="replace"):
            line = re.sub(r"^\S+Z ", "", line.rstrip("\n"))  # GitHub log timestamps
            match = re.match(r"^Failed check: (\S+)$", line) or re.match(r"^(?:prerequisite )?(\S+): FAILED\b", line)
            if match:
                failed.add(match.group(1))
            match = re.match(r"^(?:prerequisite )?(\S+): passed\b", line)
            if match:
                passed.add(match.group(1))
    known = known_failures()

    def listed(name):  # an entry may be a shell pattern such as check-stack-ownership-*
        return next((pattern for pattern in known if fnmatch.fnmatchcase(name, pattern)), None)

    new = sorted(name for name in failed if not listed(name))
    still = sorted(name for name in failed if listed(name))
    fixed = sorted(name for name in passed - failed if name in known)
    report = []
    for name in new:
        report.append(f"NEW FAILURE {name}")
    for name in still:
        report.append(f"known failure {name}: {known[listed(name)]}")
    for name in fixed:
        report.append(f"now passing {name}: remove it from tools/ci-known-failures.txt")
    if status and not failed:
        report.append(f"the run exited {status} without naming a failed check (build or runner error)")
    text = "\n".join(report) + ("\n" if report else "")
    sys.stdout.write(text or "no failures\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and report:
        with open(summary, "a") as handle:
            handle.write("```\n" + text + "```\n")
    return 1 if new or (status and not failed) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("arguments", nargs="+", help="AGGREGATES INDEX COUNT; AGGREGATES with --list; LOG... with --verdict")
    parser.add_argument("--list", action="store_true", help="print every check with its weight in ms")
    parser.add_argument("--verdict", action="store_true", help="judge runner logs against the known failures")
    parser.add_argument("--status", type=int, default=0, help="with --verdict: the runner's exit status")
    parser.add_argument("--record-times", action="store_true", help="rewrite tools/ci-times.tsv from runner logs")
    args = parser.parse_args()
    if args.verdict:
        sys.exit(verdict(args.arguments, args.status))
    if args.record_times:
        record_times(args.arguments)
        return
    phony, rules = database()
    checks = sorted({c for aggregate in args.arguments[0].split() for c in checks_of(aggregate, phony, rules)})
    if args.list:
        times = weights()
        for name in checks:
            print(f"{times.get(name, UNKNOWN_MS)}\t{name}")
        return
    try:
        index, count = int(args.arguments[1]), int(args.arguments[2])
    except (IndexError, ValueError):
        parser.error("give AGGREGATES INDEX COUNT")
    if not 1 <= index <= count or len(args.arguments) != 3:
        parser.error("give AGGREGATES INDEX COUNT with 1 <= INDEX <= COUNT")
    shards, _ = pack(checks, count)
    print(" ".join(shards[index - 1][2]))


if __name__ == "__main__":
    main()
