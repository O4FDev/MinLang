#!/usr/bin/env python3
"""pack.py PLAN.json TIMES.tsv GOAL-TIMES.tsv SHARDS JOBS [EXTRA] > assignment.json

Packs a check plan (plan.py) onto SHARDS shards of JOBS parallel checks each, longest first by the reference times
(check-in-parallel's times.tsv: target, wall_ms, cpu_ms; goal times: name, cpu_ms). A shard pays once for each shared
build its checks need. Deterministic: every shard can run it on the same inputs and agree on the assignment.

Each shard gets its checks, the shared builds those checks need, and a skip list for the make shim (every other check
and shared build of the plan). A shared build that shares a recipe-built prerequisite with a needed one is kept too,
so the runner still serialises them exactly as it would on one box; prerequisites built before the runner starts
(plan.py "prebuilt": the compiler and the runner itself) do not count.

EXTRA (SLOTS@SPEED, e.g. 4@0.7) adds one more logical shard, index SHARDS: the shard-cache box, which runs SLOTS checks
at SPEED times a shard core's speed once it has built and planned, EXTRA_HEAD_MS before the shards are up.
"""
import json
import re
import sys

DEFAULT_CHECK_MS = 20000
DEFAULT_GOAL_MS = 2000
DEFER_MS = 20000  # shared builds at least this slow are built beside the runner instead of before every check
ROUNDS = 12  # greedy passes; each later one handicaps the shards the one before left above the mean
# tools/check-runner.min exclusive(): these start only once no other check is running on the shard, also where the shim
# finishes them at once, so an aggregate above one (check-portable) starts only once its whole shard has drained.
EXCLUSIVE = {"check-net-udp-offload", "check-net-udp-offload-sanitize", "check-peer-edge-cids", "check-peer-edge-cids-sanitize"}
# The shard-cache box is another CPU model with half a shard's memory: it takes only short checks with known times, none
# that measures time or budgets or uses a sanitizer build, and none that waits for a deferred heavy build.
EXTRA_HEAD_MS = 10000
EXTRA_MAX_MS = 45000
EXTRA_EXCLUDE = re.compile(r"bench|ablation|budget|perform|timing|measure|sanitize|bakeoff|stress|scaling")


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


def pack(plan, check_ms, goal_ms, shards, jobs, wall_ms=None, extra=None):
    wall_ms = wall_ms or {}
    count = shards + (1 if extra else 0)
    slots = [jobs] * shards + ([extra[0]] if extra else [])
    speed = [1.0] * shards + ([extra[1]] if extra else [])
    head = [0] * shards + ([EXTRA_HEAD_MS] if extra else [])
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
    # An aggregate with a recipe of its own (check-portable runs compiler-behavior on the stage3 IR) starts only after
    # every check below it on the same shard passes (a skipped aggregate in between still waits for its children there).
    by_label = {check["label"]: check for check in checks}
    below = {}

    def descendants(label):
        if label not in below:
            below[label] = set()
            for child in by_label[label]["children"]:
                below[label] |= {child} | descendants(child)
        return below[label]

    drains = {label for label in by_label if descendants(label) & EXCLUSIVE}
    holds = {label for label, check in by_label.items() if check["children"] and check.get("recipe")} | (EXCLUSIVE & set(by_label))
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

    # Aggregates with a recipe of their own go first, so the cost of each check placed beside one includes the wait it
    # adds to that recipe (chain_end).
    order = sorted(checks, key=lambda check: (not (check["children"] and check.get("recipe")), -cost(check), check["label"]))
    # A shard's runner starts no check before all its shared builds are done, so a shard finishes at about
    # (shared-build phase) + (check phase): each the larger of its longest item and its total over the jobs, and the
    # check phase at least the waiting its checks do behind the shard's one launcher lock.
    goal_sum, goal_max = [0] * count, [0] * count
    load, longest, locked = [0] * count, [0] * count, [0] * count
    deferred_max, waiter_end, tail = [0] * count, [0] * count, [0] * count
    owned = [set() for _ in range(count)]
    assigned = [set() for _ in range(count)]
    state = [goal_sum, goal_max, load, longest, locked, deferred_max, waiter_end, tail, owned, assigned]

    def heavy(name):
        return goal_ms.get(name, DEFAULT_GOAL_MS) >= DEFER_MS

    def chain_end(index, label, extra=None):
        # When a check that waits for others on its shard ends, with extra placed there too. An exclusive check, or an
        # aggregate above one, runs after the shard has drained; another own recipe after its descendants here, which the
        # runner starts first (their priority includes it).
        own = length(by_label[label])
        if label in drains or label in EXCLUSIVE:
            return (load[index] + (cost(extra) if extra else 0)) / slots[index] + own
        here = [by_label[c] for c in descendants(label) & assigned[index]]
        if extra and extra["label"] in descendants(label):
            here.append(extra)
        if not here:
            return 0
        return max(sum(cost(c) for c in here) / slots[index], max(length(c) for c in here)) + own

    def tail_with(index, check):
        # The latest such end on this shard with this check placed.
        value = 0
        for label in holds & assigned[index]:
            value = max(value, chain_end(index, label, check))
        if check["label"] in holds:
            value = max(value, chain_end(index, check["label"]))
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
        checks_phase = max((load[index] + check_cost + sum(ms for ms in extra_goals if ms >= DEFER_MS)) / slots[index],
                           longest[index], check_length, locked[index] + check_wait, ends, chains)
        return max(gm, gs / slots[index]) + checks_phase - head[index]

    def eligible(index, check):
        label = check["label"]
        return index < shards or (label in check_ms and not EXTRA_EXCLUDE.search(label) and label not in holds and
                                  length(check) <= EXTRA_MAX_MS and not any(heavy(name) for name in effective[label]))

    def place(check, handicap):
        best, best_value = 0, None
        for index in range(count):
            if not eligible(index, check):
                continue
            pace = speed[index]
            extra = [goal_ms.get(name, DEFAULT_GOAL_MS) / pace for name in effective[check["label"]] if name not in owned[index]]
            needs_heavy = [goal_ms.get(name, DEFAULT_GOAL_MS) for name in effective[check["label"]] if heavy(name)]
            value = finish(index, extra, cost(check) / pace, length(check) / pace, waiting(check), max(needs_heavy or [0]),
                           bool(needs_heavy), tail_with(index, check)) + handicap[index]
            # Pieces of one split check share their inputs and the launcher lock: keep them on different shards.
            value += 0.5 * length(check) * len(siblings.get(check["label"], set()) & assigned[index])
            if best_value is None or value < best_value:
                best, best_value = index, value
        needs_heavy = [goal_ms.get(name, DEFAULT_GOAL_MS) for name in effective[check["label"]] if heavy(name)]
        pace = speed[best]
        for name in effective[check["label"]]:
            if name not in owned[best]:
                owned[best].add(name)
                if heavy(name):
                    load[best] += goal_ms.get(name, DEFAULT_GOAL_MS)
                    deferred_max[best] = max(deferred_max[best], goal_ms.get(name, DEFAULT_GOAL_MS))
                else:
                    goal_sum[best] += goal_ms.get(name, DEFAULT_GOAL_MS) / pace
                    goal_max[best] = max(goal_max[best], goal_ms.get(name, DEFAULT_GOAL_MS) / pace)
        if needs_heavy:
            waiter_end[best] = max(waiter_end[best], max(needs_heavy) + length(check))
        tail[best] = tail_with(best, check)
        load[best] += cost(check) / pace
        longest[best] = max(longest[best], length(check) / pace)
        locked[best] += waiting(check)
        assigned[best].add(check["label"])

    # Greedy longest-first cannot take back an early placement, so a shard can end well above the rest (the one with
    # check-portable, which waits for its whole shard). Later passes handicap such shards; the best pass is kept.
    handicap, kept = [0.0] * count, None
    for _ in range(ROUNDS):
        for item in state:
            item[:] = [set() if isinstance(item[0], set) else 0 for _ in range(count)]
        for check in order:
            place(check, handicap)
        estimates = [finish(index, [], 0) for index in range(count)]
        if kept is None or max(estimates) < kept[0]:
            kept = (max(estimates), [[set(x) if isinstance(x, set) else x for x in item] for item in state])
        mean = sum(estimates) / count
        handicap = [h + (e - mean) / 2 for h, e in zip(handicap, estimates)]
    for item, saved in zip(state, kept[1]):
        item[:] = saved

    result = []
    all_checks = [check["label"] for check in checks]
    for index in range(count):
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
    # A check that waits for a deferred heavy build gets no boost for it: it would only sleep in a runner slot.
    durations = {}
    for check in checks:
        slowest = max([goal_ms.get(name, 0) for name in check["goals"] if name not in prebuilt and not heavy(name)] or [0])
        durations[check["label"]] = [length(check) + slowest, cost(check)]
    return {"shards": count, "regular": shards, "jobs": jobs, "extra": extra, "checks": len(all_checks), "goals": len(goals),
            "assignment": result, "durations": durations}


if __name__ == "__main__":
    if len(sys.argv) not in (6, 7):
        sys.exit(__doc__)
    plan = json.load(open(sys.argv[1]))
    extra = None
    if len(sys.argv) == 7 and sys.argv[6]:
        extra_slots, _, extra_speed = sys.argv[6].partition("@")
        extra = (int(extra_slots), float(extra_speed or 1))
    json.dump(pack(plan, read_times(sys.argv[2], 2), read_times(sys.argv[3], 1), int(sys.argv[4]), int(sys.argv[5]),
                   read_times(sys.argv[2], 1), extra), sys.stdout, indent=1)
    sys.stdout.write("\n")
