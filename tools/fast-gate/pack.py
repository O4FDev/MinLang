#!/usr/bin/env python3
"""pack.py PLAN.json TIMES.tsv GOAL-TIMES.tsv SHARDS JOBS > assignment.json

Packs a check plan (plan.py) onto SHARDS shards of JOBS parallel checks each, longest first by the reference times
(check-in-parallel's times.tsv: target, wall_ms, cpu_ms; goal times: name, cpu_ms). A shard pays once for each shared
build its checks need. Deterministic: every shard can run it on the same inputs and agree on the assignment.

Each shard gets its checks, the shared builds those checks need, and a skip list for the make shim (every other check
and shared build of the plan). A shared build that shares a recipe-built prerequisite with a needed one is kept too,
so the runner still serialises them exactly as it would on one box; prerequisites built before the runner starts
(plan.py "prebuilt": the compiler and the runner itself) do not count.
"""
import json
import sys

DEFAULT_CHECK_MS = 20000
DEFAULT_GOAL_MS = 2000


def read_times(path, column):
    times = {}
    try:
        for line in open(path):
            fields = line.rstrip("\n").split("\t")
            if len(fields) > column and fields[column].isdigit():
                times[fields[0]] = int(fields[column])
    except OSError:
        pass
    return times


def pack(plan, check_ms, goal_ms, shards, jobs, wall_ms=None):
    wall_ms = wall_ms or {}
    goals = {goal["name"]: goal for goal in plan["goals"]}
    prebuilt = set(plan.get("prebuilt", []))
    checks = plan["checks"]
    # A check split into pieces keeps its old name as their aggregate: until the pieces have times of their own, each
    # gets an equal share of the old check's time.
    check_ms, wall_ms = dict(check_ms), dict(wall_ms)
    for check in checks:
        label, children = check["label"], check["children"]
        if label in check_ms and children and not any(child in check_ms for child in children):
            for child in children:
                check_ms[child] = check_ms[label] // len(children)
                wall_ms[child] = wall_ms.get(label, check_ms[label]) // len(children)
            check_ms[label], wall_ms[label] = 1000, 1000

    def cost(check):
        label = check["label"]
        if label in check_ms:
            return check_ms[label]
        if check["children"]:
            return 1000
        return DEFAULT_CHECK_MS

    def length(check):
        # A check given several slots (peer suites) takes less wall time than CPU time.
        return min(cost(check), wall_ms.get(check["label"], cost(check)))

    order = sorted(checks, key=lambda check: (-cost(check), check["label"]))
    # A shard's runner starts no check before all its shared builds are done, so a shard finishes at about
    # (shared-build phase) + (check phase), each the larger of its longest item and its total over the jobs.
    goal_sum, goal_max = [0] * shards, [0] * shards
    load, longest = [0] * shards, [0] * shards
    owned = [set() for _ in range(shards)]
    assigned = [[] for _ in range(shards)]

    def finish(index, extra_goals, check_cost, check_length=0):
        gs = goal_sum[index] + sum(extra_goals)
        gm = max([goal_max[index]] + extra_goals)
        return max(gm, gs / jobs) + max((load[index] + check_cost) / jobs, max(longest[index], check_length))

    for check in order:
        best, best_finish = 0, None
        for index in range(shards):
            extra = [goal_ms.get(name, DEFAULT_GOAL_MS) for name in check["goals"] if name not in owned[index]]
            value = finish(index, extra, cost(check), length(check))
            if best_finish is None or value < best_finish:
                best, best_finish = index, value
        for name in check["goals"]:
            if name not in owned[best]:
                owned[best].add(name)
                goal_sum[best] += goal_ms.get(name, DEFAULT_GOAL_MS)
                goal_max[best] = max(goal_max[best], goal_ms.get(name, DEFAULT_GOAL_MS))
        load[best] += cost(check)
        longest[best] = max(longest[best], length(check))
        assigned[best].append(check["label"])

    result = []
    all_checks = [check["label"] for check in checks]
    for index in range(shards):
        needed = set(owned[index])
        changed = True
        while changed:
            changed = False
            built = set()
            for name in needed:
                built.update(member for member, recipe in goals[name]["members"].items() if recipe and member not in prebuilt)
            for name, goal in goals.items():
                if name in needed:
                    continue
                if any(recipe and member in built and member not in prebuilt for member, recipe in goal["members"].items()):
                    needed.add(name)
                    changed = True
        mine = set(assigned[index])
        skip = [label for label in all_checks if label not in mine] + [name for name in goals if name not in needed]
        result.append({
            "shard": index,
            "checks": sorted(mine),
            "goals": sorted(needed),
            "estimate_s": round(finish(index, [], 0) / 1000, 1),
            "skip": skip,
        })
    return {"shards": shards, "jobs": jobs, "checks": len(all_checks), "goals": len(goals), "assignment": result}


if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    plan = json.load(open(sys.argv[1]))
    json.dump(pack(plan, read_times(sys.argv[2], 2), read_times(sys.argv[3], 1), int(sys.argv[4]), int(sys.argv[5]),
                   read_times(sys.argv[2], 1)), sys.stdout, indent=1)
    sys.stdout.write("\n")
