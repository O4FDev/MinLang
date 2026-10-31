#!/usr/bin/env python3
"""fast_gate.py TREE [options]: run Minyar's full gate for TREE across on-demand DigitalOcean shard boxes.

Creates SHARDS droplets from the shard snapshot image (named shard-<run>-<i>, tagged test-shard), sends each the tree
as a delta against the image's base copy, runs tools/fast-gate/shard-run.sh on every shard, merges the per-shard
results into one verdict for every check of the gate and deletes every droplet of the run on any exit.

The verdict of a check is the verdict its own shard's runner gave it; an aggregate passes when its own recipe passed
and every check under it passed, as on one box. Prints the plan's check count, the failed checks and the wall time.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.path.expanduser("~/.ssh/brief_crawl_do")
SSH = ["ssh", "-i", KEY, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
       "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=8"]
BASE = "/home/agent/base"
FG = "/home/agent/fg"
TREE = "/home/agent/swarm/gate"
CACHE_ROOT = "/home/agent/fgc"
FG_FILES = ["plan.py", "pack.py", "prebuild.py", "shard-run.sh", "cache-run.sh", "checks.txt", "times.tsv", "goal-times.tsv", "shim/make"]

started = time.monotonic()
log_lock = threading.Lock()


def say(message):
    with log_lock:
        print(f"[{time.monotonic() - started:6.1f}s] {message}", flush=True)


def run(command, check=True, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(command[:6])}... failed ({result.returncode}): {result.stderr.strip()[-800:]}")
    return result


def doctl(*arguments):
    return run(["doctl", *arguments, "--output", "json"]).stdout


class Shards:
    """The droplets of one run. delete() removes exactly the droplets named shard-<run>-* tagged test-shard."""

    def __init__(self, run_id, count, image, size, region, key_id):
        self.run_id, self.count = run_id, count
        self.names = [f"shard-{run_id}-{index}" for index in range(count)]
        self.image, self.size, self.region, self.key_id = image, size, region, key_id
        self.deleted = False
        self.lock = threading.Lock()

    def create(self):
        run(["doctl", "compute", "droplet", "create", *self.names, "--size", self.size, "--image", str(self.image),
             "--region", self.region, "--ssh-keys", str(self.key_id), "--tag-names", "test-shard", "--output", "json"])

    def mine(self):
        droplets = json.loads(doctl("compute", "droplet", "list", "--tag-name", "test-shard") or "[]")
        prefix = f"shard-{self.run_id}-"
        return [d for d in droplets if d["name"].startswith(prefix) and "test-shard" in (d.get("tags") or [])]

    def addresses(self):
        found = {}
        for droplet in self.mine():
            if droplet["status"] != "active":
                continue
            for network in droplet["networks"]["v4"]:
                if network["type"] == "public":
                    found[droplet["name"]] = network["ip_address"]
        return found

    def delete(self):
        with self.lock:
            if self.deleted:
                return
            self.deleted = True
        for attempt in range(5):
            try:
                ids = [str(d["id"]) for d in self.mine()]
                if not ids:
                    say(f"shards deleted (run {self.run_id})")
                    return
                run(["doctl", "compute", "droplet", "delete", "-f", *ids])
            except Exception as error:  # keep trying: a leaked shard costs money until the guard reaps it
                say(f"delete attempt {attempt + 1} failed: {error}")
            time.sleep(3)
        say(f"WARNING: could not confirm deletion of shard-{self.run_id}-*; the test-shard-guard reaps them after 2 h")


def find_cache(choice):
    if choice == "none":
        return None
    name = "shard-cache" if choice == "auto" else choice
    for droplet in json.loads(doctl("compute", "droplet", "list") or "[]"):
        if droplet["name"] == name and droplet["status"] == "active":
            addresses = {n["type"]: n["ip_address"] for n in droplet["networks"]["v4"]}
            return {"name": name, "public": addresses["public"], "private": addresses["private"]}
    if choice != "auto":
        raise RuntimeError(f"no active droplet named {name}")
    return None


def ssh(ip, command, check=True, timeout=None):
    return run(SSH + [f"agent@{ip}", command], check=check, timeout=timeout)


def tree_files(tree):
    listing = run(["git", "-C", tree, "ls-files", "-z", "--cached", "--others", "--exclude-standard"]).stdout
    return sorted(path for path in listing.split("\0") if path and os.path.lexists(os.path.join(tree, path)))


def wait_ssh(ip):
    while ssh(ip, "true", check=False, timeout=15).returncode != 0:
        time.sleep(1)


def sync_tree(ip, tree, files, dest):
    """Make dest on ip an exact copy of the tree's files: a hard-linked copy of the image's base tree is the rsync
    basis (rsync replaces changed files and never writes into the basis), then files the tree lacks are removed."""
    ssh(ip, f"rm -rf {dest} && mkdir -p {os.path.dirname(dest)} && cp -al {BASE} {dest}")
    run(["rsync", "-a", "-c", "--from0", "--files-from=-", "-e", " ".join(SSH), tree + "/", f"agent@{ip}:{dest}/"],
        input="\0".join(files))
    # The single-box gates are seeded by the loop's `bb`, which leaves its file list as .bb-files in the tree root.
    listing = "".join(path + "\n" for path in files)
    run(SSH + [f"agent@{ip}", f"cat > {dest}/.bb-files && cd {dest} && find . -path ./build -prune -o \\( -type f -o -type l \\) -print | "
               f"sed 's|^\\./||' | sort > /tmp/have-$$ && sort .bb-files > /tmp/want-$$ && echo .bb-files >> /tmp/want-$$ && "
               f"sort -o /tmp/want-$$ /tmp/want-$$ && comm -23 /tmp/have-$$ /tmp/want-$$ | tr '\\n' '\\0' | xargs -0 -r rm -f && "
               f"find . -mindepth 1 -type d -empty -delete; rm -f /tmp/have-$$ /tmp/want-$$"], input=listing)


def upload_tools(ip, dest, args):
    ssh(ip, f"rm -rf {dest} && mkdir -p {dest}/shim {dest}/out")
    sources = [os.path.join(HERE, name) for name in FG_FILES if name not in ("shim/make", "checks.txt")]
    run(["rsync", "-a", "-e", " ".join(SSH)] + sources + [os.path.join(args.out, "checks.txt"), f"agent@{ip}:{dest}/"])
    run(["rsync", "-a", "-e", " ".join(SSH), os.path.join(HERE, "shim", "make"), f"agent@{ip}:{dest}/shim/make"])


def prepare_cache(cache, tree, files, args, run_id, timeline):
    """Start the cache box's part at once: it builds and plans while the shards boot."""
    root = f"{CACHE_ROOT}/{run_id}"
    # Keep the two latest earlier runs for debugging; older ones go.
    ssh(cache["public"], f"mkdir -p {CACHE_ROOT} && cd {CACHE_ROOT} && ls -1t | tail -n +3 | xargs -r rm -rf")
    sync_tree(cache["public"], tree, files, f"{root}/tree")
    timeline["synced"] = time.monotonic() - started
    upload_tools(cache["public"], f"{root}/fg", args)
    ssh(cache["public"], f"setsid nohup bash {root}/fg/cache-run.sh {run_id} {args.shards} {args.jobs} > {root}/run.log 2>&1 < /dev/null &")
    timeline["launched"] = time.monotonic() - started


def prepare_shard(ip, tree, files, index, args, timeline):
    wait_ssh(ip)
    timeline["ssh"] = time.monotonic() - started
    if args.cache:
        ssh(ip, f"rm -rf {TREE} && mkdir -p /home/agent/swarm && cp -al {BASE} {TREE}")
    else:
        sync_tree(ip, tree, files, TREE)
    upload_tools(ip, FG, args)
    timeline["synced"] = time.monotonic() - started


def run_shard(ip, index, args, timeline):
    cache = f"FAST_GATE_CACHE={args.cache['private']} FAST_GATE_RUN={args.run_id} " if args.cache else ""
    command = (f"{cache}setsid nohup bash {FG}/shard-run.sh {TREE} {index} {args.shards} {args.jobs} > {FG}/run.log 2>&1 < /dev/null & "
               f"until grep -q SHARD-DONE {FG}/out/status 2>/dev/null; do sleep 1; done")
    while True:
        result = ssh(ip, command if "launched" not in timeline else command.split(" & ", 1)[1], check=False)
        timeline["launched"] = True
        if result.returncode == 0:
            break
        say(f"shard {index}: ssh dropped ({result.returncode}); reconnecting")
        time.sleep(2)
    timeline["done"] = time.monotonic() - started
    local = os.path.join(args.out, f"shard-{index}")
    os.makedirs(local, exist_ok=True)
    run(["rsync", "-a", "-e", " ".join(SSH), f"agent@{ip}:{FG}/out/", local + "/"], check=False)
    return local


def merge(args, shard_dirs):
    plans, assignments, results, problems = {}, None, {}, []
    for index, local in enumerate(shard_dirs):
        status = open(os.path.join(local, "status")).read() if os.path.exists(os.path.join(local, "status")) else ""
        for line in status.splitlines():
            if " PLANNED " in line:
                plans[index] = line.split()[2:4]
        try:
            assignment = json.load(open(os.path.join(local, "assignment.json")))
        except (OSError, ValueError):
            problems.append(f"shard {index}: no plan ({status.splitlines()[-2:] if status else 'no status'})")
            continue
        if assignments is None:
            assignments = assignment
        mine = set(assignment["assignment"][index]["checks"])
        try:
            table = [line.rstrip("\n").split("\t") for line in open(os.path.join(local, "times.tsv"))][1:]
        except OSError:
            problems.append(f"shard {index}: no results ({status.splitlines()[-2:]})")
            continue
        seen = set()
        for target, wall, cpu, passed in table:
            if target in mine:
                results[target] = {"passed": passed == "true", "wall_ms": int(wall), "cpu_ms": int(cpu), "shard": index}
                seen.add(target)
        for target in sorted(mine - seen):
            problems.append(f"shard {index}: no result for {target}")
        gate_log = os.path.join(local, "gate.log")
        if os.path.exists(gate_log) and "Failed check: toolchain-stamp" in open(gate_log, errors="replace").read():
            results.setdefault("toolchain-stamp", {"passed": False, "wall_ms": 0, "cpu_ms": 0, "shard": index})
    if len(set(map(tuple, plans.values()))) > 1:
        problems.append(f"shards planned differently: {plans}")
    plan = json.load(open(os.path.join(shard_dirs[0], "plan.json"))) if os.path.exists(os.path.join(shard_dirs[0], "plan.json")) else None
    final = {}
    if plan:
        children = {check["label"]: check["children"] for check in plan["checks"]}

        def verdict(label, depth=0):
            if label in final:
                return final[label]
            own = results.get(label, {}).get("passed", False)
            final[label] = own and all(verdict(child, depth + 1) for child in children[label])
            return final[label]

        for check in plan["checks"]:
            verdict(check["label"])
            if check["label"] not in results:
                problems.append(f"no shard ran {check['label']}")
    if "toolchain-stamp" in results:
        final["toolchain-stamp"] = False
    return plan, final, results, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("tree")
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--image", default=open(os.path.join(HERE, "image.txt")).read().split()[0])
    parser.add_argument("--size", default="s-8vcpu-16gb-amd")
    parser.add_argument("--region", default="lon1")
    parser.add_argument("--key-id", default="59947268")
    parser.add_argument("--out", default=None)
    parser.add_argument("--checks", default=open(os.path.join(HERE, "checks.txt")).read().strip(),
                        help="the gate's CHECKS (default: tools/fast-gate/checks.txt, the single-box gate's list)")
    parser.add_argument("--cache", default="auto", help="the shard-cache box: auto (the droplet named shard-cache, if any), none, or NAME")
    parser.add_argument("--keep", action="store_true", help="leave the shards running (debugging only)")
    parser.add_argument("--hosts", default="", help="comma-separated existing boxes to use as shards instead of creating droplets (debugging only; never deleted)")
    args = parser.parse_args()
    tree = os.path.abspath(args.tree)
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S") + f"{os.getpid() % 100:02d}"
    args.out = args.out or os.path.expanduser(f"~/Projects/minyar-fast-tests/runs/{run_id}")
    os.makedirs(args.out, exist_ok=True)
    open(os.path.join(args.out, "checks.txt"), "w").write(args.checks + "\n")
    args.run_id = run_id
    args.cache = find_cache(args.cache)
    shards = Shards(run_id, args.shards, args.image, args.size, args.region, args.key_id)
    if args.hosts:
        hosts = args.hosts.split(",")
        args.shards, args.keep = len(hosts), True
        shards = Shards(run_id, len(hosts), args.image, args.size, args.region, args.key_id)
        shards.create = lambda: None
        shards.addresses = lambda: {f"shard-{run_id}-{index}": ip for index, ip in enumerate(hosts)}

    def cleanup(*_):
        if not args.keep:
            shards.delete()
        if _:
            sys.exit(130)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGHUP, cleanup)
    say(f"fast gate {run_id}: {tree} on {args.shards} x {args.size} (image {args.image}), results in {args.out}")
    try:
        creator = threading.Thread(target=shards.create)
        creator.start()
        files = tree_files(tree)
        say(f"tree: {len(files)} files")
        cache_timeline = {}
        if args.cache:
            say(f"cache box {args.cache['name']} {args.cache['public']} (VPC {args.cache['private']}) builds and plans")
            cache_thread = threading.Thread(target=prepare_cache, args=(args.cache, tree, files, args, run_id, cache_timeline))
            cache_thread.start()
        creator.join()
        say("droplets requested")
        timelines = [dict() for _ in range(args.shards)]
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=args.shards)
        futures, started_shards = {}, set()
        while len(started_shards) < args.shards:
            for name, ip in shards.addresses().items():
                index = int(name.rsplit("-", 1)[1])
                if index in started_shards:
                    continue
                started_shards.add(index)
                timelines[index]["active"] = time.monotonic() - started
                say(f"shard {index} active at {ip}")

                def work(ip=ip, index=index):
                    prepare_shard(ip, tree, files, index, args, timelines[index])
                    say(f"shard {index} synced")
                    return run_shard(ip, index, args, timelines[index])

                futures[index] = pool.submit(work)
            if time.monotonic() - started > 600:
                raise RuntimeError("shards did not become active within 600 s")
            time.sleep(2)
        if args.cache:
            cache_thread.join()
        shard_dirs = [None] * args.shards
        for index, future in futures.items():
            shard_dirs[index] = future.result()
            say(f"shard {index} done")
    finally:
        cleanup()
    plan, final, results, problems = merge(args, shard_dirs)
    elapsed = time.monotonic() - started
    with open(os.path.join(args.out, "merged.tsv"), "w") as out:
        out.write("target\twall_ms\tcpu_ms\tpassed\tshard\n")
        for label in sorted(final):
            r = results.get(label, {})
            out.write(f"{label}\t{r.get('wall_ms', 0)}\t{r.get('cpu_ms', 0)}\t{str(final[label]).lower()}\t{r.get('shard', -1)}\n")
    json.dump({"timelines": timelines, "elapsed_s": elapsed, "problems": problems}, open(os.path.join(args.out, "summary.json"), "w"), indent=1)
    for index, timeline in enumerate(timelines):
        say(f"shard {index}: " + " ".join(f"{k}={v:.0f}" for k, v in timeline.items() if isinstance(v, float)))
    failed = sorted(label for label, ok in final.items() if not ok)
    count = len(plan["checks"]) if plan else 0
    for problem in problems:
        print(f"PROBLEM: {problem}")
    for label in failed:
        print(f"Failed check: {label}")
    verdict = "PASSED" if plan and not failed and not problems else "FAILED"
    print(f"FAST GATE {verdict}: {count} checks in the plan, {len(results)} run on {args.shards} shards, "
          f"{len(failed)} failed, {len(problems)} problems; wall {elapsed:.0f} s; results {args.out}/merged.tsv")
    return 0 if verdict == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
