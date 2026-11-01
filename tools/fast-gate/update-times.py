#!/usr/bin/env python3
"""update-times.py RUN-DIR...: refresh the packing tables (times.tsv, goal-times.tsv) from fast-gate runs.

Takes, from every shard of the given runs, the checks that shard ran (its times.tsv rows for its assignment) and the
shared builds it built (gate.log `prerequisite NAME: passed ... cpu_user/system/rss_kib=U S R` lines that took more
than a few milliseconds), and merges them over the current tables: a measured check time replaces the old one; a
shared build keeps the largest time seen (it is cheap when another build already made its prerequisites).
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read(path, columns):
    rows = {}
    if os.path.exists(path):
        for line in open(path):
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= columns and fields[1].isdigit():
                rows[fields[0]] = fields[1:columns]
    return rows


def main():
    checks = read(os.path.join(HERE, "times.tsv"), 4)
    goals = read(os.path.join(HERE, "goal-times.tsv"), 2)
    pattern = re.compile(r"^prerequisite (\S+): passed wall_ms=(\d+) .*cpu_user/system/rss_kib=([0-9.]+) ([0-9.]+) ")
    for run in sys.argv[1:]:
        for shard in sorted(glob.glob(os.path.join(run, "**", "shard-*"), recursive=True)):
            try:
                assignment = json.load(open(os.path.join(shard, "assignment.json")))
                index = int(os.path.basename(shard).split("-")[1])
                mine = set(assignment["assignment"][index]["checks"])
                table = [line.rstrip("\n").split("\t") for line in open(os.path.join(shard, "times.tsv"))][1:]
            except (OSError, ValueError, KeyError, IndexError):
                continue
            for target, wall, cpu, passed in table:
                if target in mine:
                    checks[target] = [wall, cpu, passed]
            for line in open(os.path.join(shard, "gate.log"), errors="replace"):
                match = pattern.match(line)
                if match and int(match.group(2)) > 50:
                    # A shared build's time depends on which of its prerequisites another build already made, so keep
                    # the largest seen: the packer must assume it can be the one doing the work.
                    measured = int((float(match.group(3)) + float(match.group(4))) * 1000)
                    goals[match.group(1)] = [str(max(measured, int(goals.get(match.group(1), ["0"])[0])))]
    with open(os.path.join(HERE, "times.tsv"), "w") as out:
        out.write("target\twall_ms\tcpu_ms\tpassed\n")
        for target, (wall, cpu, passed) in sorted(checks.items(), key=lambda item: -int(item[1][0])):
            out.write(f"{target}\t{wall}\t{cpu}\t{passed}\n")
    with open(os.path.join(HERE, "goal-times.tsv"), "w") as out:
        for name, (cpu,) in sorted(goals.items()):
            out.write(f"{name}\t{cpu}\n")
    print(f"times.tsv: {len(checks)} checks; goal-times.tsv: {len(goals)} shared builds")


if __name__ == "__main__":
    main()
