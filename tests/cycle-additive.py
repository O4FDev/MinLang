#!/usr/bin/env python3
"""Bounded sequential additive-proof TDD; no upstream test source copied."""
import argparse, hashlib, json, os, platform, signal, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from cycle_runtime import publish_engine
from clang_helpers import asan_leak_options, windows_host
from test_evidence import terminate_process_tree, test_jobs
from concurrent.futures import ThreadPoolExecutor

def profile_selection(requested, windows):
    unsupported = ([{"profile": "lazy",
                     "reason": "The lazy heap profile requires a POSIX mmap backend; Windows is not supported."}]
                   if windows else [])
    if windows and requested is not None and "lazy" in requested:
        raise ValueError(unsupported[0]["reason"])
    return (requested if requested is not None else
            (["system", "fixed", "eager"] if windows else
             ["system", "fixed", "lazy", "eager"])), unsupported


def counters():
    rows = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    values = list(map(int, rows))
    # Guest time is already included in user/nice by Linux.
    total = sum(values[:8])
    return total, values[3] + values[4]
def cpu_guard():
    """Opt-in courtesy pause for shared hosts (MINYAR_CYCLE_CPU_GUARD=1).

    Runners already bound their own concurrency; under their load the pause
    only stalls cases against the same wall deadline."""
    return platform.system() == "Linux" and os.environ.get("MINYAR_CYCLE_CPU_GUARD") == "1"


def run(command, environment, output, label, resource):
    proc = subprocess.Popen(command, cwd=ROOT, env=environment, start_new_session=not windows_host(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    started = time.monotonic()
    if cpu_guard():
        previous = counters()
        stopped = False
        maximum = 0
        while proc.poll() is None:
            time.sleep(.25)
            current = counters()
            delta = current[0] - previous[0]
            usage = 100 * (1 - (current[1] - previous[1]) / delta) if delta else 0
            maximum = max(maximum, usage)
            previous = current
            if usage >= 75 and not stopped:
                os.killpg(proc.pid, signal.SIGSTOP); stopped = True
                resource.append({"label": label, "action": "pause", "aggregate_cpu_percent": usage})
            elif stopped and usage < 60:
                os.killpg(proc.pid, signal.SIGCONT); stopped = False
                resource.append({"label": label, "action": "resume", "aggregate_cpu_percent": usage})
            if time.monotonic() - started > 180:
                terminate_process_tree(proc)
                break
        stdout, stderr = proc.communicate(timeout=10)
        resource.append({"label": label, "maximum_aggregate_cpu_percent": maximum})
    else:
        try:
            stdout, stderr = proc.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            terminate_process_tree(proc)
            stdout, stderr = proc.communicate(timeout=10)
        resource.append({"label": label, "cpu_guard": False})
    (output / (label + ".stdout")).write_text(stdout)
    (output / (label + ".stderr")).write_text(stderr)
    return {"label": label, "status": proc.returncode, "stdout": stdout, "stderr": stderr,
            "seconds": time.monotonic() - started, "argv": command}


def run_groups(groups, execute):
    """Run independent case groups bounded by test_jobs(); report in plan order.

    Each group is a sequence of dependent phases (compile, then its runs), so
    only whole groups overlap. The first failing group in plan order raises."""
    with ThreadPoolExecutor(max_workers=test_jobs()) as pool:
        futures = [pool.submit(execute, group) for group in groups]
        return [future.result() for future in futures]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sanitize", action="store_true")
    p.add_argument("--fixture", choices=["cycle-additive.c", "cycle-registry-growth.c", "cycle-leaf-churn.c", "cycle-captured-retirement.c", "cycle-fresh-mark-retirement.c", "cycle-detached-first-insertion.c", "cycle-full-mark-zero.c"], default="cycle-additive.c")
    p.add_argument("--case", choices=["all", "registered", "callbacks", "streaming", "safety", "active"], default="all")
    p.add_argument("--profiles", nargs="+", choices=["system", "fixed", "lazy", "eager"],
                   default=None)
    p.add_argument("--budgets", type=int, nargs="+", choices=[1, 32, 1024], default=[1, 32, 1024])
    p.add_argument("--nodes", type=int, nargs="+", choices=[32, 256, 512, 2048], default=[32, 256, 2048])
    p.add_argument("--evidence", type=Path, required=True)
    args = p.parse_args()
    try:
        profiles, unsupported = profile_selection(args.profiles, windows_host())
    except ValueError as error:
        p.error(str(error))
    if args.fixture in ("cycle-captured-retirement.c", "cycle-fresh-mark-retirement.c", "cycle-full-mark-zero.c"):
        if args.case != "all":
            p.error("dead-owner retirement owns its complete C schedule")
        if args.profiles is not None and "eager" in args.profiles:
            p.error("dead-owner retirement certifies bounded cleanup; eager RC is unchanged")
        profiles = [profile for profile in profiles if profile != "eager"]
        unsupported.append({"profile": "eager",
                            "reason": "Dead-owner certificates use bounded cleanup; eager RC is unchanged."})
    if args.fixture == "cycle-detached-first-insertion.c":
        if args.case != "all":
            p.error("detached first insertion owns its full positive and negative schedule")
        if any(budget > 32 for budget in args.budgets) or any(n < 512 for n in args.nodes):
            p.error("detached first insertion requires --budgets 1 32 and --nodes 512 2048")
        if args.profiles is not None and "eager" in args.profiles:
            p.error("detached first insertion observes bounded full-build phases")
        profiles = [profile for profile in profiles if profile != "eager"]
        unsupported.append({"profile": "eager",
                            "reason": "Detached first insertion observes bounded full-build phases."})
    if args.fixture == "cycle-full-mark-zero.c":
        if any(budget > 32 for budget in args.budgets) or any(n < 512 for n in args.nodes):
            p.error("full MARK zero retirement requires --budgets 1 32 and --nodes 512 2048")
    out = args.evidence.resolve(); out.mkdir(parents=True, exist_ok=True)
    (ROOT / "build").mkdir(exist_ok=True)
    publish_engine(ROOT)
    headers = sorted((ROOT / "runtime").glob("*.h"))
    inputs = [ROOT/"tests/cycle-additive.c", ROOT/"tests"/args.fixture, Path(__file__).resolve(),
              ROOT/"tools/cycle_runtime.py", ROOT/"tests/clang_helpers.py",
              ROOT/"tests/test_evidence.py", ROOT/"runtime/minyar_runtime.c", *headers]
    if args.fixture in ("cycle-captured-retirement.c", "cycle-fresh-mark-retirement.c",
                        "cycle-detached-first-insertion.c", "cycle-full-mark-zero.c"):
        inputs.append(ROOT/"tests/cycle-leaf-churn.c")
    if args.fixture == "cycle-full-mark-zero.c":
        inputs.append(ROOT/"tests/cycle-detached-first-insertion.c")
    report = {"passed": False, "sanitize": args.sanitize, "cases": [], "resources": [],
              "profiles": profiles, "unsupported_profiles": unsupported,
              "source_sha256": {str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                                for f in inputs}}
    environment = dict(os.environ, ASAN_OPTIONS=asan_leak_options()+":halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    options = {"system":["-DMINYAR_SYSTEM_HEAP=1"], "fixed":["-DMINYAR_BOUNDED_HEAP=1"],
               "lazy":["-DMINYAR_BOUNDED_HEAP=1","-DMINYAR_LAZY_HEAP=1"], "eager":[]}
    flags = (["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer"]
             if args.sanitize else ["-O2"])
    historical = "rc_cycle_edge_insert" not in (ROOT/"runtime/minyar_cycles.h").read_text()
    report["historical_barrier_adapter"] = historical
    report["bounded_heap_bytes"] = 4194304 if args.fixture == "cycle-registry-growth.c" else 1048576
    groups = []
    for profile in profiles:
        for budget in ([32] if profile == "eager" else args.budgets):
            label = profile+"-k"+str(budget)
            binary = out/(label+(".exe" if windows_host() else ""))
            command = [os.environ.get("MINYAR_TEST_CLANG","clang"), *flags, "-std=c11",
                       "-Wall","-Wextra","-Werror","-iquote",str(ROOT/"runtime"),
                       *options[profile], "-DMINYAR_BOUNDED_HEAP_BYTES="+str(
                           4194304 if args.fixture == "cycle-registry-growth.c" else 1048576),
                       "-DMINYAR_RC_POLL_BUDGET="+str(budget)]
            if historical:
                command.append("-Drc_cycle_edge_insert=rc_cycle_edge_add")
            command += [str(ROOT/"tests"/args.fixture),"-lm","-o",str(binary)]
            phases = [("compile", command)]
            for n in args.nodes:
                if args.fixture == "cycle-detached-first-insertion.c":
                    for phase in (1, 2, 3):
                        for copied in (0, 1):
                            phases.append((f"run-n{n}-detached-p{phase}-copy{copied}",
                                           [str(binary), str(n), "detached", str(phase), str(copied)]))
                        for mode in ("internal", "exposed", "registered-descendant", "self-cycle"):
                            phases.append((f"run-n{n}-{mode}-p{phase}",
                                           [str(binary), str(n), mode, str(phase), "1"]))
                        if phase >= 2:
                            phases.append((f"run-n{n}-anchor-take-p{phase}",
                                           [str(binary), str(n), "anchor-take", str(phase), "0"]))
                else:
                    phases.append((f"run-n{n}", [str(binary), str(n), args.case]))
            groups.append((label, binary, phases))

    def execute(group):
        label, binary, phases = group
        cases, resources, binary_sha256 = [], [], None
        for phase, argv in phases:
            case = run(argv, environment, out, label+"-"+phase, resources)
            if binary.is_file():
                binary_sha256 = binary_sha256 or hashlib.sha256(binary.read_bytes()).hexdigest()
                case["binary_sha256"] = binary_sha256
            cases.append(case)
            print(case["label"]+": "+str(case["status"])+" "+case["stderr"].strip(),flush=True)
            if case["status"]: return cases, resources, case["label"]
        return cases, resources, None

    try:
        failures = []
        for cases, resources, failed in run_groups(groups, execute):
            report["cases"] += cases
            report["resources"] += resources
            if failed: failures.append(failed)
        if failures: raise AssertionError(", ".join(failures))
        report["passed"] = True
    finally:
        (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__ == "__main__":main()
