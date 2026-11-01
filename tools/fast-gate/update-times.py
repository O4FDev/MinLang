#!/usr/bin/env python3
"""update-times.py RUN-DIR...: refresh the packing tables (times.tsv, goal-times.tsv) from fast-gate runs.

Takes, from every shard of the given runs, the checks that shard ran (its times.tsv rows for its assignment) and the
shared builds it built (gate.log `prerequisite NAME: passed ... cpu_user/system/rss_kib=U S R` lines that took more
than a few milliseconds), and merges them over the current tables: a measured check takes the median of its times in
the given runs (shard boxes are shared-CPU: one check's time can double from one run to the next), less the time the
shim held it for deferred shared builds; a shared build keeps the largest time seen (it is cheap when another build
already made its prerequisites).
"""
import glob
import json
import os
import re
import statistics
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


def held(shard):
    """How long the shim held each waiting check of a shard (ms): from its start to its "ready" stamp, or, in runs
    before that stamp, to the end of the deferred builds it waited for."""
    waiters, starts, ready = {}, {}, {}
    try:
        for line in open(os.path.join(shard, "waiters.txt")):
            fields = line.split()
            if len(fields) == 2:
                waiters[fields[0]] = fields[1].split(",")
        for line in open(os.path.join(shard, "timeline")):
            fields = line.split()
            if len(fields) == 2:
                starts.setdefault(fields[1], float(fields[0]))
            elif len(fields) == 3 and fields[2] == "ready":
                ready.setdefault(fields[1], float(fields[0]))
    except OSError:
        return {}
    result = {}
    for label, groups in waiters.items():
        if label not in starts:
            continue
        end = ready.get(label)
        if end is None:
            exits = [os.path.join(shard, f"deferred-{group}.exit") for group in groups]
            if not all(os.path.exists(path) for path in exits):
                continue
            end = max(os.path.getmtime(path) for path in exits)
        result[label] = max(0, int((end - starts[label]) * 1000))
    return result


def main():
    checks = read(os.path.join(HERE, "times.tsv"), 4)
    samples = {}
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
            waits = held(shard)
            for target, wall, cpu, passed in table:
                if target in mine:
                    samples.setdefault(target, []).append((max(1, int(wall) - waits.get(target, 0)), int(cpu), passed))
            for line in open(os.path.join(shard, "gate.log"), errors="replace"):
                match = pattern.match(line)
                if match and int(match.group(2)) > 50:
                    # A shared build's time depends on which of its prerequisites another build already made, so keep
                    # the largest seen: the packer must assume it can be the one doing the work.
                    measured = int((float(match.group(3)) + float(match.group(4))) * 1000)
                    goals[match.group(1)] = [str(max(measured, int(goals.get(match.group(1), ["0"])[0])))]
    for target, rows in samples.items():
        checks[target] = [str(int(statistics.median(row[0] for row in rows))), str(int(statistics.median(row[1] for row in rows))), rows[-1][2]]
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
