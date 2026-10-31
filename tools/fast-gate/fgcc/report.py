#!/usr/bin/env python3
"""report.py LOG.jsonl...: summarise fgcc logs (one per pass or shard).

Per log: invocations, cacheable share, results (run/miss/hit/verified/MISMATCH), compile seconds by result, the
seconds hits saved (the matching misses' duration), the top reasons an invocation was not cacheable, and how many
cacheable invocations repeat a key already seen in the same log (duplicates a shared cache would serve).
"""
import collections
import json
import sys


def main():
    first_seen = {}
    for path in sys.argv[1:]:
        rows = [json.loads(line) for line in open(path) if line.strip()]
        results = collections.Counter(r["res"] for r in rows)
        seconds = collections.Counter()
        for r in rows:
            seconds[r["res"]] += r["d"]
        reasons = collections.Counter((r.get("why") or "").split(" ")[0] + " " + " ".join((r.get("why") or "").split(" ")[1:2]) for r in rows if not r["ok"])
        cost = {}
        for r in rows:
            if r["res"] in ("miss", "run") and r.get("key"):
                cost.setdefault(r["key"], r["d"])
        for key, value in cost.items():
            first_seen.setdefault(key, value)
        saved = sum(first_seen.get(r["key"], 0) - r["d"] for r in rows if r["res"] in ("hit", "verified") and r.get("key"))
        keys = collections.Counter(r["key"] for r in rows if r.get("key"))
        repeats = sum(n - 1 for n in keys.values() if n > 1)
        cacheable = sum(1 for r in rows if r["ok"])
        print(f"== {path}")
        print(f"  invocations {len(rows)}, cacheable {cacheable} ({100 * cacheable / max(1, len(rows)):.0f}%), "
              f"distinct keys {len(keys)}, repeated keys within this log {repeats}")
        print("  results: " + ", ".join(f"{k} {v} ({seconds[k]:.0f} s)" for k, v in sorted(results.items())))
        print(f"  seconds saved by hits (vs the first compile of each key): {saved:.0f}")
        print(f"  mean analysis overhead {sum(r['ad'] for r in rows) / max(1, len(rows)) * 1000:.1f} ms")
        print("  not cacheable: " + ", ".join(f"{k.strip()} {v}" for k, v in reasons.most_common(8)))


if __name__ == "__main__":
    main()
