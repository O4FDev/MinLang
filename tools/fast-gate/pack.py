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
DEFER_MS = 20000  # shared builds at least this slow are built beside the runner instead of before every check


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
    # A check split into pieces keeps its old name as their aggregate: until the pieces have times of their own, they
    # share the old check's time (less any of its children that have their own) and the aggregate costs nothing.
    check_ms, wall_ms = dict(check_ms), dict(wall_ms)
    for check in checks:
        label, children = check["label"], check["children"]
        unknown = [child for child in children if child not in check_ms]
        if label in check_ms and unknown:
            known_cpu = sum(check_ms[child] for child in children if child in check_ms)
            known_wall = sum(wall_ms.get(child, check_ms[child]) for child in children if child in check_ms)
            for child in unknown:
                check_ms[child] = max(1000, (check_ms[label] - known_cpu) // len(unknown))
                wall_ms[child] = max(1000, (wall_ms.get(label, check_ms[label]) - known_wall) // len(unknown))
            check_ms[label], wall_ms[label] = 1000, 1000
    # An aggregate with a recipe of its own (check-portable runs compiler-behavior on the stage3 IR) starts only after its
    # direct children on the same shard pass; on a shard without them it starts at once.
    by_label = {check["label"]: check for check in checks}
    own_parents = {}
    for check in checks:
        if check["children"] and check.get("recipe"):
            for child in check["children"]:
                own_parents.setdefault(child, []).append(check["label"])
    siblings = {}
    for check in checks:
        if len(check["children"]) > 1:
            for child in check["children"]:
                siblings.setdefault(child, set()).update(c for c in check["children"] if c != child)

    def cost(check):
        # Runner slot time: a check holds its slot for its whole wall time, and several cores when it uses them.
        label = check["label"]
        if label in check_ms:
            return max(check_ms[label], wall_ms.get(label, 0))
        return 1000 if check["children"] else DEFAULT_CHECK_MS

    def length(check):
        return wall_ms.get(check["label"], cost(check))

    def waiting(check):
        # Wall time spent not computing, mostly behind the launcher's build/bootstrap.lock: serial on one shard.
        label = check["label"]
        if label in check_ms and label in wall_ms and wall_ms[label] - check_ms[label] > 20000:
            return wall_ms[label] - check_ms[label]
        return 0

    # The shared builds a check makes a shard run: its own, plus every build that shares a not-prebuilt prerequisite
    # with them (the runner serialises those, so the shard keeps them).
    def recipe_members(name):
        return {m for m, recipe in goals[name]["members"].items() if recipe and m not in prebuilt} if name in goals else set()

    effective = {}
    for check in checks:
        need = set(check["goals"])
        changed = True
        while changed:
            changed = False
            members = set().union(*(recipe_members(name) for name in need)) if need else set()
            for name in goals:
                if name not in need and recipe_members(name) & members:
                    need.add(name)
                    changed = True
        effective[check["label"]] = need

    # Aggregates with a recipe of their own go first, so the cost of each child placed beside one includes the chain it
    # makes (see chain_end): the recipe waits for its children on the same shard.
    order = sorted(checks, key=lambda check: (not (check["children"] and check.get("recipe")), -cost(check), check["label"]))
    # A shard's runner starts no check before all its shared builds are done, so a shard finishes at about
    # (shared-build phase) + (check phase): each the larger of its longest item and its total over the jobs, and the
    # check phase at least the waiting its checks do behind the shard's one launcher lock.
    goal_sum, goal_max = [0] * shards, [0] * shards
    load, longest, locked = [0] * shards, [0] * shards, [0] * shards
    deferred_max, waiter_end, tail = [0] * shards, [0] * shards, [0] * shards
    owned = [set() for _ in range(shards)]
    assigned = [set() for _ in range(shards)]

    def heavy(name):
        return goal_ms.get(name, DEFAULT_GOAL_MS) >= DEFER_MS

    def chain_end(index, parent, extra=None):
        # An own recipe starts once its children on the same shard are done; they run first (their critical path holds
        # it), so it ends about when they would on their own plus its own length.
        children = [by_label[c] for c in by_label[parent]["children"] if c in assigned[index]] + ([extra] if extra else [])
        if not children:
            return 0
        return max(sum(cost(c) for c in children) / jobs, max(length(c) for c in children)) + length(by_label[parent])

    def tail_with(index, check):
        # The latest end of an own recipe's chain on this shard with this check placed.
        value = tail[index]
        label = check["label"]
        if check["children"] and check.get("recipe"):
            value = max(value, chain_end(index, label))
        for parent in own_parents.get(label, []):
            if parent in assigned[index]:
                value = max(value, chain_end(index, parent, check))
        return value

    def finish(index, extra_goals, check_cost, check_length=0, check_wait=0, check_heavy=0, waits=False, check_tail=None):
        # Light shared builds run before any check; heavy ones run beside the checks on one core, and a check that
        # needs one ("waiter") cannot finish before it is built.
        light = [ms for ms in extra_goals if ms < DEFER_MS]
        gs = goal_sum[index] + sum(light)
        gm = max([goal_max[index]] + light)
        dmax = max(deferred_max[index], check_heavy)
        ends = max(waiter_end[index], dmax + check_length if waits else 0)
        chains = tail[index] if check_tail is None else check_tail
        checks_phase = max((load[index] + check_cost + sum(ms for ms in extra_goals if ms >= DEFER_MS)) / jobs,
                           longest[index], check_length, locked[index] + check_wait, ends, chains)
        return max(gm, gs / jobs) + checks_phase

    for check in order:
        best, best_value = 0, None
        for index in range(shards):
            extra = [goal_ms.get(name, DEFAULT_GOAL_MS) for name in effective[check["label"]] if name not in owned[index]]
            needs_heavy = [goal_ms.get(name, DEFAULT_GOAL_MS) for name in effective[check["label"]] if heavy(name)]
            value = finish(index, extra, cost(check), length(check), waiting(check), max(needs_heavy or [0]), bool(needs_heavy),
                           tail_with(index, check))
            # Pieces of one split check share their inputs and the launcher lock: keep them on different shards.
            value += 0.5 * length(check) * len(siblings.get(check["label"], set()) & assigned[index])
            if best_value is None or value < best_value:
                best, best_value = index, value
        needs_heavy = [goal_ms.get(name, DEFAULT_GOAL_MS) for name in effective[check["label"]] if heavy(name)]
        for name in effective[check["label"]]:
            if name not in owned[best]:
                owned[best].add(name)
                if heavy(name):
                    load[best] += goal_ms.get(name, DEFAULT_GOAL_MS)
                    deferred_max[best] = max(deferred_max[best], goal_ms.get(name, DEFAULT_GOAL_MS))
                else:
                    goal_sum[best] += goal_ms.get(name, DEFAULT_GOAL_MS)
                    goal_max[best] = max(goal_max[best], goal_ms.get(name, DEFAULT_GOAL_MS))
        if needs_heavy:
            waiter_end[best] = max(waiter_end[best], max(needs_heavy) + length(check))
        tail[best] = tail_with(best, check)
        load[best] += cost(check)
        longest[best] = max(longest[best], length(check))
        locked[best] += waiting(check)
        assigned[best].add(check["label"])

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
        mine = assigned[index]
        # Deferred: the shard's heavy shared builds and every needed build that shares a prerequisite with them or
        # depends on them. shard-run.sh builds them in one background make; the shim finishes them at once for the
        # runner and holds each check that needs one until that make is done. Nothing else touches their files.
        deferred = {name for name in needed if heavy(name)}
        changed = True
        while changed:
            changed = False
            touched = set(deferred).union(*(recipe_members(name) for name in deferred)) if deferred else set()
            for name in needed - deferred:
                if recipe_members(name) & touched:
                    deferred.add(name)
                    changed = True
        # Independent deferred chains (no shared prerequisite between them) build in separate makes, in parallel; a
        # check waits only for the chains it needs.
        groups = []
        for name in sorted(deferred, key=lambda n: -goal_ms.get(n, DEFAULT_GOAL_MS)):
            reach = recipe_members(name) | {name}
            joined = [g for g in groups if g["reach"] & reach]
            merged = {"names": {name}, "reach": reach}
            for g in joined:
                merged["names"] |= g["names"]
                merged["reach"] |= g["reach"]
                groups.remove(g)
            groups.append(merged)
        waiters = {}
        for label in sorted(mine):
            needs = [str(k) for k, g in enumerate(groups) if effective[label] & g["names"]]
            if needs:
                waiters[label] = needs
        skip = [label for label in all_checks if label not in mine] + [name for name in goals if name not in needed or name in deferred]
        result.append({
            "shard": index,
            "checks": sorted(mine),
            "goals": sorted(needed),
            "deferred": [sorted(g["names"]) for g in groups],
            "waiters": waiters,
            "estimate_s": round(finish(index, [], 0) / 1000, 1),
            "skip": skip,
        })
    # check-in-parallel starts the checks it knows to be longest first (build/tooling/check-durations: label, wall ms,
    # cpu ms); a fresh tree has no history and would start them last, leaving one long check running alone at the end.
    # The estimate is the check's critical path: its own length plus its slowest shared build, so a long build that only
    # a quick check needs (build/scope-compiler-stage3.ll for check-scope-fixed-point) still starts first.
    # A check that waits for a deferred heavy build gets no boost for it: it would only sleep in a runner slot. A child
    # of an own recipe on the same shard carries that recipe's path too, so the shard runs it before unrelated checks.
    shard_of = {label: index for index in range(shards) for label in assigned[index]}

    def path(label):
        after = [path(parent) for parent in own_parents.get(label, []) if shard_of.get(parent) == shard_of.get(label)]
        return length(by_label[label]) + max(after or [0])

    durations = {}
    for check in checks:
        slowest = max([goal_ms.get(name, 0) for name in check["goals"] if name not in prebuilt and not heavy(name)] or [0])
        durations[check["label"]] = [path(check["label"]) + slowest, cost(check)]
    return {"shards": shards, "jobs": jobs, "checks": len(all_checks), "goals": len(goals), "assignment": result,
            "durations": durations}


if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    plan = json.load(open(sys.argv[1]))
    json.dump(pack(plan, read_times(sys.argv[2], 2), read_times(sys.argv[3], 1), int(sys.argv[4]), int(sys.argv[5]),
                   read_times(sys.argv[2], 1)), sys.stdout, indent=1)
    sys.stdout.write("\n")
