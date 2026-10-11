#!/usr/bin/env python3
"""Bounded sequential additive-proof TDD; no upstream test source copied."""
import argparse, hashlib, json, os, platform, signal, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from cycle_runtime import engine_source

def counters():
    rows = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    values = list(map(int, rows))
    # Guest time is already included in user/nice by Linux.
    total = sum(values[:8])
    return total, values[3] + values[4]
def run(command, environment, output, label, resource):
    proc = subprocess.Popen(command, cwd=ROOT, env=environment, start_new_session=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    previous = counters() if platform.system() == "Linux" else None
    started = time.monotonic()
    stopped = False
    maximum = 0
    while proc.poll() is None:
        time.sleep(.25)
        if previous:
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
            os.killpg(proc.pid, signal.SIGKILL)
            break
    stdout, stderr = proc.communicate()
    (output / (label + ".stdout")).write_text(stdout)
    (output / (label + ".stderr")).write_text(stderr)
    resource.append({"label": label, "maximum_aggregate_cpu_percent": maximum})
    return {"label": label, "status": proc.returncode, "stdout": stdout, "stderr": stderr,
            "seconds": time.monotonic() - started, "argv": command}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sanitize", action="store_true")
    p.add_argument("--profiles", nargs="+", choices=["system", "fixed", "lazy", "eager"],
                   default=["system", "fixed", "lazy", "eager"])
    p.add_argument("--budgets", type=int, nargs="+", choices=[1, 32, 1024], default=[1, 32, 1024])
    p.add_argument("--nodes", type=int, nargs="+", choices=[32, 256, 2048], default=[32, 256, 2048])
    p.add_argument("--evidence", type=Path, required=True)
    args = p.parse_args()
    out = args.evidence.resolve(); out.mkdir(parents=True, exist_ok=True)
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build/managed-graphs-engine.c").write_text(engine_source(ROOT))
    headers = sorted((ROOT / "runtime").glob("*.h"))
    inputs = [ROOT/"tests/cycle-additive.c", Path(__file__).resolve(),
              ROOT/"tools/cycle_runtime.py", ROOT/"runtime/minyar_runtime.c", *headers]
    report = {"passed": False, "sanitize": args.sanitize, "cases": [], "resources": [],
              "source_sha256": {str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                                for f in inputs}}
    environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    options = {"system":["-DMINYAR_SYSTEM_HEAP=1"], "fixed":["-DMINYAR_BOUNDED_HEAP=1"],
               "lazy":["-DMINYAR_BOUNDED_HEAP=1","-DMINYAR_LAZY_HEAP=1"], "eager":[]}
    flags = (["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer"]
             if args.sanitize else ["-O2"])
    historical = "rc_cycle_edge_insert" not in (ROOT/"runtime/minyar_cycles.h").read_text()
    report["historical_barrier_adapter"] = historical
    try:
        for profile in args.profiles:
            for budget in ([32] if profile == "eager" else args.budgets):
                label = profile+"-k"+str(budget)
                binary = out/label
                command = [os.environ.get("MINYAR_TEST_CLANG","clang"), *flags, "-std=c11",
                           "-Wall","-Wextra","-Werror","-iquote",str(ROOT/"runtime"),
                           *options[profile], "-DMINYAR_BOUNDED_HEAP_BYTES=1048576",
                           "-DMINYAR_RC_POLL_BUDGET="+str(budget)]
                if historical:
                    command.append("-Drc_cycle_edge_insert=rc_cycle_edge_add")
                command += [str(ROOT/"tests/cycle-additive.c"),"-lm","-o",str(binary)]
                phases = [("compile",command)] + [(f"run-n{n}",[str(binary),str(n)]) for n in args.nodes]
                for phase, argv in phases:
                    case = run(argv, environment, out, label+"-"+phase, report["resources"])
                    if binary.is_file():
                        case["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
                    report["cases"].append(case)
                    print(case["label"]+": "+str(case["status"])+" "+case["stderr"].strip(),flush=True)
                    if case["status"]: raise AssertionError(case["label"])
        report["passed"] = True
    finally:
        (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__ == "__main__":main()
