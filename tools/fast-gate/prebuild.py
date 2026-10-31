#!/usr/bin/env python3
"""prebuild.py TREE PLAN.json GOAL-TIMES.tsv LANES MIN_MS: build the gate's slow shared builds ahead of the shards.

Runs, in TREE, `make -j1 GOAL` for every shared build of the plan whose reference time is at least MIN_MS, in up to
LANES concurrent makes. Two builds run at once only when their stale closures (plan.py "members" built by a recipe)
are disjoint, the rule check-in-parallel uses, so no file is ever built by two makes. The environment is the check
runner's. A failed build is left for the shards' runners, which build and report it exactly as on one box.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import runner_environment  # noqa: E402
from pack import read_times  # noqa: E402


def main():
    tree, plan_path, times_path, lanes, minimum = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    plan = json.load(open(plan_path))
    times = read_times(times_path, 1)
    goals = sorted((goal for goal in plan["goals"] if times.get(goal["name"], 0) >= minimum),
                   key=lambda goal: -times[goal["name"]])
    members = {goal["name"]: {m for m, recipe in goal["members"].items() if recipe} for goal in goals}
    env = runner_environment()
    pending, running, built = list(goals), {}, set()
    started = time.monotonic()
    while pending or running:
        for name, process in list(running.items()):
            if process.poll() is not None:
                del running[name]
                print(f"{time.monotonic() - started:6.1f} s {name}: exit {process.returncode}", flush=True)
                if process.returncode == 0:
                    built |= members[name]
        for goal in list(pending):
            if len(running) >= lanes:
                break
            busy = set().union(*(members[name] for name in running)) if running else set()
            if (members[goal["name"]] - built) & busy:
                continue
            pending.remove(goal)
            log = open(os.path.join(os.path.dirname(os.path.abspath(plan_path)), "prebuild-" + goal["name"].replace("/", "_") + ".log"), "w")
            running[goal["name"]] = subprocess.Popen(["make", "-j1", goal["name"]], cwd=tree, env=env, stdout=log, stderr=subprocess.STDOUT)
        time.sleep(0.2)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    main()
