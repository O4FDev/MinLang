#!/usr/bin/env python3
"""estimate.py TREE-RUN-DIR [BOX-READY-S]: project a waves run (--boxes < --shards) to one box per shard.

Every shard's own part is measured from the moment the cache box's build was ready to it (CACHE-READY) to SHARD-DONE:
the pull, the runner, its shared builds and checks. With one box per shard all of them start together once the boxes
are up (BOX-READY-S after the command starts: creation to SSH, default 64 s as measured) and the cache box is done,
so the projected wall time is max(box ready, cache done) + the slowest shard + about 5 s to collect and merge. The
cache box's own shard (pack.py EXTRA) starts when the cache box is done, whatever the shards' boot time.
"""
import json
import os
import sys


def stamps(path):
    found = {}
    for line in open(path):
        fields = line.split()
        if len(fields) >= 2:
            found.setdefault(fields[1], float(fields[0]))
    return found


def main():
    run = sys.argv[1]
    ready = float(sys.argv[2]) if len(sys.argv) > 2 else 64.0
    summary = json.load(open(os.path.join(run, "summary.json")))
    shards = sorted(d for d in os.listdir(run) if d.startswith("shard-"))
    parts, own = [], []
    cache_build = None
    for name in shards:
        status = stamps(os.path.join(run, name, "status"))
        if "SHARD-DONE" not in status:
            print(f"{name}: unfinished")
            continue
        begin = status.get("CACHE-READY", status["START"])
        try:
            regular = json.load(open(os.path.join(run, name, "assignment.json"))).get("regular", 10 ** 6)
        except (OSError, ValueError):
            regular = 10 ** 6
        (own if int(name.split("-")[1]) >= regular else parts).append((status["SHARD-DONE"] - begin, name))
        cache = os.path.join(run, name, "cache-status")
        if cache_build is None and os.path.exists(cache):
            c = stamps(cache)
            cache_build = c.get("CACHE-DONE", 0) - c.get("START", 0)
    sync = summary.get("cache", {}).get("launched", 5.0)
    cache_done = sync + (cache_build or 0)
    parts.sort(reverse=True)
    slowest = parts[0][0]
    projected = max(ready, cache_done) + slowest + 5
    print(f"cache box: synced and started at {sync:.0f} s, built and planned in {cache_build or 0:.0f} s -> done at {cache_done:.0f} s")
    print("shards, pull to done (s): " + ", ".join(f"{n.split('-')[1]}:{d:.0f}" for d, n in parts))
    for duration, name in own:
        print(f"cache box's shard {name.split('-')[1]}: {duration:.0f} s -> done at {cache_done + duration + 5:.0f} s")
        projected = max(projected, cache_done + duration + 5)
    print(f"PROJECTED one box per shard: max(box ready {ready:.0f}, cache done {cache_done:.0f}) + slowest shard {slowest:.0f} + 5"
          f"{', or the cache box shard' if own else ''} = {projected:.0f} s")


if __name__ == "__main__":
    main()
