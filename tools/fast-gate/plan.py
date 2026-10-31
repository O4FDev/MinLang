#!/usr/bin/env python3
"""plan.py TREE TARGET... > plan.json

Computes the plan `make check-in-parallel CHECKS="TARGET..."` would run in TREE, the way tools/check-runner.min does:
the checks (phony targets, aggregates expanded through their phony prerequisites), each check's shared builds
("goals": its non-phony prerequisites that are targets, plus its stale prerequisites with recipes) and each goal's
closure of stale prerequisites ("members"). Run it in the tree after `make build/minyarc`, with the gate's
environment, exactly where check-in-parallel would plan. Mirrors check-runner.min `database`, `addCheck` and
`prepare`; keep the three in step with it.
"""
import json
import os
import subprocess
import sys


def runner_environment():
    env = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL")}
    env["MINYAR_TEST_JOBS"] = "1"
    env["MINYAR_TEST_SHARED_HOST"] = "1"
    env["DEBUGINFOD_URLS"] = ""
    return env


def database(source):
    rules, order, phony = {}, [], []
    active, target, current = False, True, None
    for line in source.split("\n"):
        if line == "# Files":
            active = True
            continue
        if line.startswith("# files hash-table stats"):
            break
        if not active:
            continue
        if line == "":
            target, current = True, None
            continue
        if line == "# Not a target:":
            target = False
            continue
        if line.startswith("\t"):
            if current is not None:
                current["recipe"] = True
            continue
        if line.startswith("#"):
            if current is not None and line.startswith("#  Phony target"):
                current["phony"] = True
            if current is not None and line.startswith("#  Needs to be updated"):
                current["stale"] = True
            continue
        colon = line.find(":")
        if colon <= 0 or "=" in line:
            continue
        name = line[:colon]
        if len(name.split()) != 1:
            continue
        start = colon + 1
        if start < len(line) and line[start] == ":":
            start += 1
        prerequisites = [item for item in line[start:].split() if item != "|"]
        if name == ".PHONY":
            phony.extend(prerequisites)
            continue
        current = rules.get(name)
        if current is None:
            current = {"name": name, "prerequisites": prerequisites, "phony": False, "recipe": False, "target": target, "stale": False}
            rules[name] = current
            order.append(name)
        else:
            current["prerequisites"].extend(prerequisites)
    if not active:
        sys.exit("plan.py: make printed no file database")
    for name in phony:
        if name in rules:
            rules[name]["phony"] = True
    return rules


def make_database(tree, env, arguments):
    result = subprocess.run(["make", "-j1"] + arguments, cwd=tree, env=env, capture_output=True, text=True, errors="replace")
    if result.returncode > 1:
        sys.exit("plan.py: make database failed\n" + result.stderr[-4000:])
    return database(result.stdout)


def plan(tree, targets):
    env = runner_environment()
    rules = make_database(tree, env, ["-pq", "FORCE"])
    checks, goals = {}, {}
    check_order, goal_order = [], []

    def add_goal(name):
        if name not in goals:
            goals[name] = {"name": name, "members": {}}
            goal_order.append(name)

    def add_check(target):
        if target in checks:
            return
        rule = rules.get(target)
        if rule is None:
            sys.exit("plan.py: missing check target: " + target)
        if not rule["phony"]:
            sys.exit("plan.py: not a phony check target: " + target)
        check = {"label": target, "children": [], "goals": []}
        checks[target] = check
        check_order.append(target)
        for prerequisite in rule["prerequisites"]:
            child = rules.get(prerequisite)
            if child is None:
                continue
            if child["phony"]:
                add_check(prerequisite)
                if prerequisite not in check["children"]:
                    check["children"].append(prerequisite)
            elif child["target"]:
                add_goal(prerequisite)
                if prerequisite not in check["goals"]:
                    check["goals"].append(prerequisite)

    for target in targets:
        add_check(target)
    # prepare(): stale prerequisites with recipes become goals; each goal's members are its stale closure.
    stale = make_database(tree, env, ["-pqk"] + goal_order + check_order)
    for label in check_order:
        rule = stale.get(label)
        if rule is None:
            continue
        for item in rule["prerequisites"]:
            prerequisite = stale.get(item)
            if prerequisite is None:
                continue
            if not prerequisite["phony"] and prerequisite["stale"] and prerequisite["recipe"]:
                add_goal(item)
                if item not in checks[label]["goals"]:
                    checks[label]["goals"].append(item)

    def closure(name, members):
        if name in members or name not in stale:
            return
        rule = stale[name]
        if rule["phony"] or not rule["stale"]:
            return
        members[name] = rule["recipe"]
        for item in rule["prerequisites"]:
            closure(item, members)

    for name in goal_order:
        closure(name, goals[name]["members"])
    own_recipe = {label: bool(rules[label]["recipe"]) for label in check_order}
    return {
        "targets": targets,
        "checks": [dict(checks[label], recipe=own_recipe[label]) for label in check_order],
        "goals": [goals[name] for name in goal_order],
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    json.dump(plan(os.path.abspath(sys.argv[1]), sys.argv[2:]), sys.stdout, indent=1)
    sys.stdout.write("\n")
