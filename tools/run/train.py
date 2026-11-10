#!/usr/bin/env python3
"""train.py RUN_DIR [--base]: the merge train of an overnight run (docs/overnight-runs.md).

Takes every queued landing request ($RUN_DIR/queue/*.req, written by land.sh), stacks them on the run branch in the
train worktree, runs ONE gate for the stack in the gate VM (vmgate.sh) and fast-forwards and pushes the run branch on
green. On red it reruns only the failing checks on each lane alone to find the culprit, gates the innocent lanes
together again, and splits the stack when no lane reproduces the failure alone. A gate log counts only if its first
line names the commit under test. --base gates the run branch once and writes base.fail and base.ready: checks that
already fail on the base are not held against any lane.
"""
import glob, os, subprocess, sys, time

if len(sys.argv) < 2:
    sys.exit("usage: train.py RUN_DIR [--base]")
C = os.path.abspath(sys.argv[1])
ENV = {}
for line in open(os.path.join(C, "env")):
    key, _, value = line.strip().partition("=")
    if key and not key.startswith("#"):
        ENV[key] = value.strip("'\"")
MAIN = ENV["MINYAR_RUN_REPO"]
BRANCH = ENV.get("MINYAR_RUN_BRANCH", "v2")
VM = ENV.get("MINYAR_GATE_VM", "rpcgate")
TRAIN = os.path.join(C, "train")
GATES = os.path.join(C, "gate")  # under the host home, so the OrbStack VM sees the same path
VMGATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vmgate.sh")

def sh(*a, cwd=MAIN, check=False):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode: raise RuntimeError(f"{a}: {r.stderr}")
    return r

def log(m):
    with open(os.path.join(C, "logs", "train.log"), "a") as f: f.write(time.strftime("%H:%M:%S ") + m + "\n")

def result(req, text):
    with open(os.path.join(C, "queue", "done", req["id"] + ".res.tmp"), "w") as f: f.write(text + "\n")
    os.rename(os.path.join(C, "queue", "done", req["id"] + ".res.tmp"), os.path.join(C, "queue", "done", req["id"] + ".res"))
    os.remove(req["path"]); log(f"{req['lane']} {text.splitlines()[0]}")

def stack(reqs):
    """cherry-pick each request onto the train head; returns the ones that applied."""
    sh("git", "checkout", "-q", "--detach", BRANCH, cwd=TRAIN, check=True)
    ok = []
    for r in reqs:
        before = sh("git", "rev-parse", "HEAD", cwd=TRAIN).stdout.strip()
        base = sh("git", "merge-base", "HEAD", r["sha"], cwd=TRAIN).stdout.strip()
        n = sh("git", "rev-list", "--count", f"{base}..{r['sha']}", cwd=TRAIN).stdout.strip()
        if n == "0": result(r, "LAND-RED: nothing to land (already in " + BRANCH + ")"); continue
        p = sh("git", "-c", "core.hooksPath=/dev/null", "cherry-pick", "--empty=drop", f"{base}..{r['sha']}", cwd=TRAIN)
        if p.returncode:
            sh("git", "cherry-pick", "--abort", cwd=TRAIN); sh("git", "reset", "-q", "--hard", before, cwd=TRAIN)
            result(r, "LAND-RED: your commits conflict with " + BRANCH + " or with a lane landing just ahead of you. Run `git rebase " + BRANCH + "` in your worktree after the current train finishes, resolve, re-run your narrow checks, then land again.")
            continue
        ok.append(r)
    return ok

def gate(reqs, checks=()):
    """full gate, or only `checks` when given. Returns (head, new failures or None, kept log)."""
    head = sh("git", "rev-parse", "HEAD", cwd=TRAIN).stdout.strip()
    sh("git", "branch", "-f", "train/candidate", head, cwd=TRAIN, check=True)
    name = "mini" if checks else "land"
    os.makedirs(GATES, exist_ok=True)
    g = os.path.join(GATES, f"gate-{name}.log")
    log(f"gating {head[:9]} = " + " + ".join(r["lane"] for r in reqs) + (f" (only {len(checks)} checks)" if checks else ""))
    if os.path.exists(g): os.remove(g)  # never judge a stack by the previous gate's log
    vm = subprocess.run(["orb", "-m", VM, "bash", VMGATE, "train/candidate", TRAIN, g, *checks], capture_output=True, text=True)
    if vm.returncode: log(f"vmgate exit {vm.returncode}: {vm.stderr.strip()[-300:]}")
    txt = open(g, errors="replace").read() if os.path.exists(g) else ""
    if not txt.startswith(f"gate {head}"): txt = "stale or missing gate log: the VM gate did not start for this commit\n"
    keep = os.path.join(C, "logs", f"gate-{head[:9]}{'-mini' if checks else ''}.log"); open(keep, "w").write(txt)
    if "GATE-EXIT" not in txt: return head, None, keep
    fails = sorted({l.strip() for l in txt.splitlines() if l.startswith("Failed check")})
    base = {l.strip() for l in open(os.path.join(C, "base.fail"))}
    new = [f for f in fails if f not in base]
    if not fails and "GATE-EXIT 0" not in txt: new = ["gate exited non-zero without a 'Failed check' line (build failure?): see the log tail"]
    return head, new, keep

def land(head, reqs):
    m = sh("git", "merge", "-q", "--ff-only", head)
    if m.returncode:
        for r in reqs: result(r, "LAND-RED: gate was green but the " + BRANCH + " checkout could not fast-forward: " + m.stderr.strip())
        return
    p = sh("git", "push", "-q", "origin", BRANCH)
    for r in reqs:
        with open(os.path.join(C, "LANDED"), "a") as f: f.write(f"{time.strftime('%H:%M')} {r['lane']} {r['sha'][:9]} -> {BRANCH} {head[:9]}\n")
        result(r, f"LAND-GREEN: your commits up to {r['sha'][:9]} are in {BRANCH} (now {head[:9]})" + ("" if not p.returncode else ", push failed and will be retried") +
               f". Run `git rebase {BRANCH}` in your worktree before continuing (already-landed commits drop out).")

def run(reqs):
    reqs = [r for r in reqs if os.path.exists(r["path"])]
    newest = {}
    for r in reqs: newest[r["lane"]] = r
    for r in reqs:
        if newest[r["lane"]] is not r: result(r, "LAND-RED: superseded by your newer landing request " + newest[r["lane"]]["sha"][:9])
    reqs = [r for r in reqs if newest[r["lane"]] is r]
    for r in reqs:  # a lane that queued again while its older request waited: gate only the newest
        later = [p for p in glob.glob(os.path.join(C, "queue", "*-" + r["lane"] + ".req")) if os.path.basename(p)[:-4] > r["id"]]
        if later: result(r, "LAND-RED: superseded by your newer landing request"); 
    reqs = [r for r in reqs if os.path.exists(r["path"])]
    ok = stack(reqs)
    if not ok: return
    head, new, keep = gate(ok)
    if new is None:
        for r in ok: result(r, f"LAND-RED: the gate did not finish (infrastructure). Log {keep}. Retry once; if it repeats, say so in your report.")
    elif not new: land(head, ok)
    elif len(ok) == 1: result(ok[0], "LAND-RED: checks failing on your branch that pass on base:\n" + "\n".join(new) + f"\nlog: {keep}")
    else:
        # Red stack: rerun only the failing checks on each lane alone (minutes, warm tree) to find who broke
        # them, then full-gate the innocent lanes together once.
        names = [f.split(": ", 1)[1] for f in new if f.startswith("Failed check: ")]
        if not names:
            log("red train without check names, gating one by one")
            for r in ok: run([r])
            return
        log("red train, attributing: " + " ".join(names)[:300])
        innocent = []
        for r in ok:
            if not stack([r]): continue
            h, n, k = gate([r], names)
            if n: result(r, "LAND-RED: checks failing on your branch that pass on base (rerun alone after a red stacked gate):\n" + "\n".join(n) + f"\nlog: {k}\nfull stacked log: {keep}")
            elif n is None: result(r, f"LAND-RED: the gate did not finish (infrastructure). Log {k}. Retry once.")
            else: innocent.append(r)
        if not innocent: return
        if len(innocent) < len(ok): run(innocent)      # culprit removed: gate the rest together, attributing again if needed
        elif len(innocent) == 1: run(innocent)
        else:                                          # nobody fails alone: an interaction or a flake, so split the stack
            log("no single lane reproduces it; splitting the stack")
            half = len(innocent) // 2
            run(innocent[:half]); run(innocent[half:])

def base():
    """Gate the run branch alone once; its failures are the baseline every landing is compared with."""
    sh("git", "checkout", "-q", "--detach", BRANCH, cwd=TRAIN, check=True)
    open(os.path.join(C, "base.fail"), "w").close()
    head, new, keep = gate([{"lane": "base"}])
    if new is None:
        sys.exit(f"base gate did not finish; see {keep}")
    fails = sorted({l.strip() for l in open(keep, errors="replace") if l.startswith("Failed check")})
    open(os.path.join(C, "base.fail"), "w").write("".join(f + "\n" for f in fails))
    open(os.path.join(C, "base.ready"), "w").close()
    log(f"base {head[:9]}: {len(fails)} failing checks recorded in base.fail")


if "--base" in sys.argv[2:]:
    base()
    sys.exit(0)
while True:
    paths = sorted(glob.glob(os.path.join(C, "queue", "*.req")))
    if not paths or not os.path.exists(os.path.join(C, "base.ready")): time.sleep(15); continue
    reqs = []
    for p in paths:
        lane, sha = open(p).read().split()
        reqs.append({"id": os.path.basename(p)[:-4], "path": p, "lane": lane, "sha": sha})
    try: run(reqs)
    except Exception as e:
        log(f"ERROR {e}")
        for r in reqs:
            if os.path.exists(r["path"]): result(r, f"LAND-RED: train error ({e}); retry once")
