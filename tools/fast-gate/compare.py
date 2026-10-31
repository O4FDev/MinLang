#!/usr/bin/env python3
"""compare.py FAST.tsv RECORDED.tsv [RECORDED-STATUS]: check-for-check agreement of a fast gate with a recorded gate.

FAST.tsv is a fast gate's merged.tsv; RECORDED.tsv a single-box check-in-parallel times.tsv (target, wall_ms, cpu_ms,
passed). RECORDED-STATUS, if given, is that gate's status file: a `Failed check: toolchain-stamp` line there counts
as a failed toolchain-stamp check. Prints one line per disagreement and a summary; exits 1 unless every check of
either gate has the same verdict in both.
"""
import sys


def verdicts(path):
    rows = [line.rstrip("\n").split("\t") for line in open(path)]
    return {row[0]: row[3] == "true" for row in rows[1:] if len(row) >= 4}


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    fast, recorded = verdicts(sys.argv[1]), verdicts(sys.argv[2])
    if len(sys.argv) == 4 and "Failed check: toolchain-stamp" in open(sys.argv[3]).read():
        recorded["toolchain-stamp"] = False
    fast.setdefault("toolchain-stamp", True) if "toolchain-stamp" in recorded else None
    disagree = 0
    for label in sorted(set(fast) | set(recorded)):
        a, b = fast.get(label), recorded.get(label)
        if a != b:
            disagree += 1
            show = lambda v: "missing" if v is None else ("pass" if v else "FAIL")
            print(f"DISAGREE {label}: fast {show(a)}, recorded {show(b)}")
    failed_fast = sorted(k for k, v in fast.items() if not v)
    failed_recorded = sorted(k for k, v in recorded.items() if not v)
    print(f"checks: fast {len(fast)}, recorded {len(recorded)}; failed: fast {len(failed_fast)}, recorded {len(failed_recorded)}; "
          f"disagreements {disagree}")
    print("failed in both: " + (" ".join(sorted(set(failed_fast) & set(failed_recorded))) or "none"))
    print("AGREE" if disagree == 0 else "DISAGREE")
    return 0 if disagree == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
