#!/usr/bin/env python3
"""agree.py RUN-DIR [RECORDED-DIR]: compare a multi-tree fast-gate run with the recorded single-box gates.

recorded.tsv (next to this script) lists the recorded gates: name, commit, gate targets, and the record, either a
check-in-parallel times.tsv under RECORDED-DIR (default recorded/ here, copied from the gate boxes), or for gates whose
table was overwritten, `failed:` with the listed failures and `count:` with the number of checks (every other check
of that gate passed). A run directory's trees are matched to recorded gates by commit. Prints, per tree, the check
counts, the failures on each side and every disagreement, then one summary line.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def verdicts(path):
    rows = [line.rstrip("\n").split("\t") for line in open(path)]
    return {row[0]: row[3] == "true" for row in rows[1:] if len(row) >= 4}


def main():
    run = sys.argv[1]
    recorded_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "recorded")
    gates = {}
    for line in open(os.path.join(HERE, "recorded.tsv")):
        if line.startswith("#") or not line.strip():
            continue
        name, commit, targets, record = line.rstrip("\n").split("\t")
        gates[commit] = (name, targets, record)
    trees = sorted(d for d in os.listdir(run) if os.path.isdir(os.path.join(run, d)) and os.path.exists(os.path.join(run, d, "summary.json")))
    total, agreeing = 0, 0
    for tree in trees:
        summary = json.load(open(os.path.join(run, tree, "summary.json")))
        commit = subprocess.run(["git", "-C", summary["tree"], "rev-parse", "--short=9", "HEAD"], capture_output=True, text=True).stdout.strip()
        fast = verdicts(os.path.join(run, tree, "merged.tsv"))
        if commit not in gates:
            print(f"{tree}: commit {commit} has no recorded gate")
            continue
        name, targets, record = gates[commit]
        if record.startswith("failed:"):
            failed_part, count_part = record.split(" count:")
            failed = set(filter(None, failed_part[len("failed:"):].split(",")))
            recorded = {label: label not in failed for label in fast}
            for label in failed - set(fast):
                recorded[label] = False
            count = int(count_part)
        else:
            recorded = verdicts(os.path.join(recorded_dir, record))
            count = len(recorded)
        if summary["checks"].split() != targets.split():
            print(f"{tree}: WARNING gated with '{summary['checks']}', recorded gate used '{targets}'")
        disagree = sorted(label for label in set(fast) | set(recorded) if fast.get(label) != recorded.get(label))
        same_count = len(fast) == count
        total += 1
        ok = not disagree and same_count and not summary["problems"]
        agreeing += ok
        fast_red = sorted(label for label, passed in fast.items() if not passed)
        rec_red = sorted(label for label, passed in recorded.items() if not passed)
        print(f"{'AGREE' if ok else 'DISAGREE'} {name} {commit}: fast {len(fast)} checks, recorded {count}; "
              f"red fast {len(fast_red)} / recorded {len(rec_red)}: {' '.join(fast_red) or 'none'}")
        for label in disagree:
            show = lambda value: "missing" if value is None else ("pass" if value else "FAIL")
            print(f"    {label}: fast {show(fast.get(label))}, recorded {show(recorded.get(label))}")
        for problem in summary["problems"]:
            print(f"    problem: {problem}")
    print(f"AGREEMENT: {agreeing} of {total} recorded gates agree check for check")
    return 0 if total and agreeing == total else 1


if __name__ == "__main__":
    sys.exit(main())
