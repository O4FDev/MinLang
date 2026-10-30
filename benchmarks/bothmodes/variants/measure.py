#!/usr/bin/env python3
"""Serial cost of the both-modes form: each program's main.min against variants
that write the same work the serial way (or that drop one parallel feature),
all at MINYAR_PARALLEL_THREADS=1. Prints cachegrind Ir (--cache-sim=no), the
ratio variant / main.min and whether the outputs are identical, then the top
functions of main.min at 1 thread for the programs in --profile.

  measure.py [--tree DIR] [--only NAME] [--profile NAME,...]
  measure.py --cpu [--threads N]
      After run.py: CPU time (user + system) against wall time of the Minyar
      program and par.rs at N threads (default 4), n=3, from getrusage of the
      child; utilisation = CPU / wall shows workers spinning or idling.
"""
import argparse
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import run as bothmodes  # noqa: E402

PAIRS = {
    "sort": ["sort-serial-idiom"],
    "mapreduce": ["mapreduce-serial-idiom"],
    "forkjoin": ["forkjoin-choice-tree"],
    "textindex": ["textindex-serial-idiom", "textindex-thread-runtime"],
    "topk": ["topk-plain-loop", "topk-ordinary-functions"],
    "server": ["server-no-threads"],
}


def build(tree, source, out):
    with open(out + ".log", "w") as f:
        r = subprocess.run([os.path.join(tree, "minyar"), "--release", source, "-o", out], stdout=f,
                           stderr=subprocess.STDOUT, cwd=tree)
    if r.returncode:
        sys.exit(f"build failed: {source} (see {out}.log)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tree", default=bothmodes.REPO)
    p.add_argument("--only", action="append")
    p.add_argument("--profile", default="")
    p.add_argument("--cpu", action="store_true")
    p.add_argument("--threads", type=int, default=4)
    args = p.parse_args()
    if args.cpu:
        return cpu(args)
    tree = os.path.abspath(args.tree)
    names = [n for n in PAIRS if not args.only or n in ",".join(args.only).split(",")]
    print(f"{'program':<10} {'variant':<26} {'Ir':>12} {'x main':>7} same", flush=True)
    for name in names:
        work = os.path.join(bothmodes.REPO, "build", "bothmodes-variants", name)
        os.makedirs(work, exist_ok=True)
        full, _ = bothmodes.sizes(name)
        arg = bothmodes.prepare_input(name, full, work)
        base = os.path.join(work, "main")
        build(tree, os.path.join(bothmodes.HERE, name, "main.min"), base)
        base_ir, base_out = bothmodes.cachegrind(base, arg, work, "main", 1)
        print(f"{name:<10} {'main.min':<26} {base_ir / 1e6:>11,.1f}M {1.0:>7.3f} -", flush=True)
        for variant in PAIRS[name]:
            exe = os.path.join(work, variant)
            build(tree, os.path.join(HERE, variant + ".min"), exe)
            ir, out = bothmodes.cachegrind(exe, arg, work, variant, 1)
            same = hashlib.sha256(out).digest() == hashlib.sha256(base_out).digest()
            print(f"{name:<10} {variant:<26} {ir / 1e6:>11,.1f}M {ir / base_ir:>7.3f} {'yes' if same else 'NO'}", flush=True)
        if name in args.profile.split(","):
            text = subprocess.run(["cg_annotate", "--auto=no", os.path.join(work, "cachegrind.main.out")],
                                  capture_output=True, text=True).stdout
            for entry in bothmodes_top(text):
                print(f"    {entry}", flush=True)


def cpu(args):
    import resource
    import statistics
    import time
    print(f"{'program':<10} {'exe':<7} {'wall ms':>9} {'cpu ms':>9} {'cpu/wall':>8}  (threads {args.threads}, median of 3)")
    for name in bothmodes.programs(args.only):
        work = os.path.join(bothmodes.REPO, "build", "bothmodes", name)
        full, _ = bothmodes.sizes(name)
        arg = bothmodes.prepare_input(name, full, work)
        for exe in ("minyar", "par"):
            walls, cpus = [], []
            for _ in range(3):
                before = resource.getrusage(resource.RUSAGE_CHILDREN)
                start = time.perf_counter()
                subprocess.run([os.path.join(work, exe), arg], check=True, stdout=subprocess.DEVNULL,
                               env=bothmodes.env_threads(args.threads))
                walls.append(time.perf_counter() - start)
                after = resource.getrusage(resource.RUSAGE_CHILDREN)
                cpus.append(after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime)
            w, c = statistics.median(walls), statistics.median(cpus)
            print(f"{name:<10} {exe:<7} {w * 1000:>9.1f} {c * 1000:>9.1f} {c / w:>8.2f}", flush=True)


def bothmodes_top(text, count=12):
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("-- Function:file summary"):
            inside = True
        elif inside and line.startswith(">"):
            lines.append(line[1:].strip())
            if len(lines) == count:
                break
    return lines


if __name__ == "__main__":
    main()
