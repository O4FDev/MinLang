#!/usr/bin/env python3
"""One source, both modes: each Minyar program here runs serially at 1 thread
and in parallel at N threads (MINYAR_PARALLEL_THREADS) from the same source.

Every directory holding a main.min is one program with peers that must print
byte-identical output: main.c, main.cpp and main.rs (the serial references)
and par.rs (the parallel reference: std-only Rust threads, thread count from
MINYAR_PARALLEL_THREADS). `sizes` holds the full and the small workload; with a
gen.c the generator writes the input file (`gen N > input`) and each program
receives its path, otherwise it receives N itself.

  run.py [--only NAME] [--tree DIR] [--json OUT] [--repeats N] [--threads N]
      Serial column: cachegrind Ir (--cache-sim=no) of Minyar at 1 thread over
      min(C, C++, Rust) Ir. Parallel column: wall time of Minyar at --threads
      (default 4) over par.rs at the same thread count, n=--repeats (default 5)
      interleaved runs, median and spread; the Ir of both at that thread count
      (all threads, pool spinning included) is printed too. Wall times of both
      at 1 thread are measured in the same interleaving, for scaling. Prints a
      geomean line for each column. Reference Ir is cached by source hash and
      toolchain in build/bothmodes-cache/.
  run.py --wall-only [--only NAME] [--repeats N] [--threads N]
      Only the wall-time columns, reusing the binaries of the last full run
      (build/bothmodes/NAME; built when missing, e.g. on a host without
      valgrind); prints /proc/loadavg before and after, because
      wall times at N threads mean little on a loaded machine.
  run.py --check [--only NAME] [--tree DIR]
      Correctness only, on the host: Minyar at O0 (--debug) and release, each at
      1 and 4 threads, against the C reference on the small workload.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
REFS = ("c", "cpp", "rust")
SOURCES = {"c": "main.c", "cpp": "main.cpp", "rust": "main.rs", "par": "par.rs"}
X86 = platform.machine() in ("x86_64", "AMD64")
ARCH = ["-march=x86-64-v3"] if X86 else []


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def tool_version(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return "missing"


def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def programs(only):
    names = sorted(d for d in os.listdir(HERE) if os.path.isfile(os.path.join(HERE, d, "main.min")))
    if only:
        wanted = [n for item in only for n in item.split(",") if n]
        missing = [n for n in wanted if n not in names]
        if missing:
            sys.exit(f"unknown program(s): {', '.join(missing)}")
        names = [n for n in names if n in wanted]
    return names


def sizes(name):
    with open(os.path.join(HERE, name, "sizes")) as f:
        full, small = f.read().split()[:2]
    return int(full), int(small)


def cc():
    return os.environ.get("CC", "clang")


def cxx():
    return os.environ.get("CXX", "clang++")


def build_ref(lang, name, out, optimise=True):
    src = os.path.join(HERE, name, SOURCES[lang])
    if lang == "c":
        cmd = [cc(), "-O3" if optimise else "-O2", *ARCH, src, "-o", out, "-lm", "-pthread"]
    elif lang == "cpp":
        cmd = [cxx(), "-O3", *ARCH, "-std=c++20", src, "-o", out, "-pthread"]
    else:
        cmd = ["rustc", "-C", "opt-level=3", *(["-C", "target-cpu=x86-64-v3"] if X86 else []),
               "-C", "codegen-units=1", "-C", "lto=fat", "-C", "panic=abort", "--edition", "2021", src, "-o", out]
    run(cmd, stdout=subprocess.DEVNULL)


def build_minyar(tree, name, out, mode):
    log = out + ".log"
    with open(log, "w") as f:
        r = subprocess.run([os.path.join(tree, "minyar"), mode, os.path.join(HERE, name, "main.min"), "-o", out],
                           stdout=f, stderr=subprocess.STDOUT, cwd=tree)
    if r.returncode != 0:
        with open(log) as f:
            raise RuntimeError(f"{name}: minyar {mode} build failed\n" + f.read()[-3000:])


def prepare_input(name, n, work):
    gen = os.path.join(HERE, name, "gen.c")
    if not os.path.isfile(gen):
        return str(n)
    exe = os.path.join(work, "gen")
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(gen):
        run([cc(), "-O2", gen, "-o", exe])
    path = os.path.join(work, f"input-{n}.txt")
    stamp = path + ".src"
    digest = file_hash(gen)
    if not (os.path.exists(path) and os.path.exists(stamp) and open(stamp).read() == digest):
        with open(path, "wb") as f:
            run([exe, str(n)], stdout=f)
        with open(stamp, "w") as f:
            f.write(digest)
    return path


def env_threads(threads):
    env = dict(os.environ)
    env["MINYAR_PARALLEL_THREADS"] = str(threads)
    return env


def run_output(exe, arg, threads):
    return subprocess.run([exe, arg], check=True, capture_output=True, env=env_threads(threads)).stdout


def cachegrind(exe, arg, work, tag, threads):
    out_file = os.path.join(work, f"cachegrind.{tag}.out")
    r = subprocess.run(["valgrind", "--tool=cachegrind", "--cache-sim=no", f"--cachegrind-out-file={out_file}",
                        exe, arg], capture_output=True, env=env_threads(threads))
    if r.returncode != 0:
        raise RuntimeError(f"{exe}: cachegrind run failed\n" + r.stderr.decode(errors="replace")[-2000:])
    with open(out_file) as f:
        for line in f:
            if line.startswith("summary:"):
                return int(line.split()[1]), r.stdout
    raise RuntimeError(f"{out_file}: no summary line")


def ref_cache_key(lang, name, arg_desc, threads):
    h = hashlib.sha256()
    for part in (lang, name, arg_desc, str(threads), tool_version([cc(), "--version"]), tool_version([cxx(), "--version"]),
                 tool_version(["rustc", "--version"]), tool_version(["valgrind", "--version"]), " ".join(ARCH)):
        h.update(part.encode() + b"\0")
    for f in (*SOURCES.values(), "gen.c", "sizes"):
        p = os.path.join(HERE, name, f)
        if os.path.exists(p):
            h.update(f.encode() + file_hash(p).encode())
    return h.hexdigest()[:24]


def measure_program(name, args):
    work = os.path.join(REPO, "build", "bothmodes", name)
    os.makedirs(work, exist_ok=True)
    cache_dir = os.path.join(REPO, "build", "bothmodes-cache")
    os.makedirs(cache_dir, exist_ok=True)
    full, _ = sizes(name)
    arg = prepare_input(name, full, work)
    row = {"name": name, "threads": args.threads, "ir": {}, "outputs": {}}
    exes = {"minyar": os.path.join(work, "minyar")}
    try:
        build_minyar(args.tree, name, exes["minyar"], "--release")
        for lang in (*REFS, "par"):
            exes[lang] = os.path.join(work, lang)
            build_ref(lang, name, exes[lang])
        # serial references (cached) and the parallel reference at N threads
        for lang, threads, key in [(lang, 1, lang) for lang in REFS] + [("par", args.threads, f"par@{args.threads}")]:
            cached = os.path.join(cache_dir, f"{name}-{key}-{ref_cache_key(lang, name, str(full), threads)}.json")
            if os.path.exists(cached):
                with open(cached) as f:
                    data = json.load(f)
            else:
                ir, out = cachegrind(exes[lang], arg, work, key, threads)
                data = {"ir": ir, "output_sha256": hashlib.sha256(out).hexdigest()}
                with open(cached, "w") as f:
                    json.dump(data, f)
            row["ir"][key] = data["ir"]
            row["outputs"][key] = data["output_sha256"]
        for threads in (1, args.threads):
            key = f"minyar@{threads}"
            ir, out = cachegrind(exes["minyar"], arg, work, key, threads)
            row["ir"][key] = ir
            row["outputs"][key] = hashlib.sha256(out).hexdigest()
            with open(os.path.join(work, f"{key}.out"), "wb") as f:
                f.write(out)
        row["identical"] = len(set(row["outputs"].values())) == 1
        best = min(REFS, key=lambda lang: row["ir"][lang])
        row["fastest_serial_ref"] = best
        row["serial_ratio"] = row["ir"]["minyar@1"] / row["ir"][best]
        row["serial_rust_ratio"] = row["ir"]["minyar@1"] / row["ir"]["rust"]
        row["parallel_ir_ratio"] = row["ir"][f"minyar@{args.threads}"] / row["ir"][f"par@{args.threads}"]
        row["wall"] = wall_times(exes, arg, args.threads, args.repeats)
        med = {k: statistics.median(v) for k, v in row["wall"].items()}
        row["parallel_ratio"] = med[f"minyar@{args.threads}"] / med[f"par@{args.threads}"]
        row["minyar_scaling"] = med["minyar@1"] / med[f"minyar@{args.threads}"]
        row["par_scaling"] = med["par@1"] / med[f"par@{args.threads}"]
    except (RuntimeError, subprocess.CalledProcessError) as e:
        row["error"] = str(e)
    return row


def wall_times(exes, arg, threads, repeats):
    runs = [("minyar", 1), ("minyar", threads), ("par", 1), ("par", threads)]
    walls = {f"{exe}@{t}": [] for exe, t in runs}
    for _ in range(repeats):
        for exe, t in runs:
            start = time.perf_counter()
            subprocess.run([exes[exe], arg], check=True, stdout=subprocess.DEVNULL, env=env_threads(t))
            walls[f"{exe}@{t}"].append(time.perf_counter() - start)
    return walls


def fmt_ir(n):
    return f"{n / 1e6:,.1f}M"


def fmt_wall(values):
    return f"{statistics.median(values) * 1000:.1f}±{(max(values) - min(values)) * 500:.1f}"


def print_row(row):
    if "error" in row:
        print(f"{row['name']:<10} ERROR {row['error'].splitlines()[0]}", flush=True)
        return
    ir, w, n = row["ir"], row["wall"], row["threads"]
    best = row["fastest_serial_ref"]
    print(f"{row['name']:<10} {'yes' if row['identical'] else 'NO':<4} "
          f"{fmt_ir(ir['minyar@1']):>10} {fmt_ir(ir[best]):>10} {best:<4} {row['serial_ratio']:>6.2f} {row['serial_rust_ratio']:>6.2f} | "
          f"{fmt_wall(w[f'minyar@{n}']):>13} {fmt_wall(w[f'par@{n}']):>13} {row['parallel_ratio']:>6.2f} | "
          f"{fmt_ir(ir[f'minyar@{n}']):>10} {fmt_ir(ir[f'par@{n}']):>10} {row['parallel_ir_ratio']:>6.2f} | "
          f"{fmt_wall(w['minyar@1']):>13} {fmt_wall(w['par@1']):>13} {row['minyar_scaling']:>5.2f} {row['par_scaling']:>5.2f}",
          flush=True)


def geomean(values):
    return math.exp(sum(math.log(v) for v in values) / len(values))


def load_average():
    try:
        with open("/proc/loadavg") as f:
            return f.read().strip()
    except OSError:
        return " ".join(f"{x:.2f}" for x in os.getloadavg())


def wall_only(args):
    names = programs(args.only)
    n = args.threads
    print(f"load before: {load_average()}", flush=True)
    print(f"{'program':<10} {f'minyar@{n} ms':>13} {f'rust@{n} ms':>13} {'par':>6} | {'minyar@1 ms':>13} {'rust@1 ms':>13} "
          f"{'m-scl':>5} {'r-scl':>5}", flush=True)
    ratios = []
    for name in names:
        work = os.path.join(REPO, "build", "bothmodes", name)
        full, _ = sizes(name)
        arg = prepare_input(name, full, work)
        exes = {"minyar": os.path.join(work, "minyar"), "par": os.path.join(work, "par")}
        if not os.path.exists(exes["minyar"]):
            build_minyar(args.tree, name, exes["minyar"], "--release")
        if not os.path.exists(exes["par"]):
            build_ref("par", name, exes["par"])
        w = wall_times(exes, arg, n, args.repeats)
        med = {k: statistics.median(v) for k, v in w.items()}
        ratio = med[f"minyar@{n}"] / med[f"par@{n}"]
        ratios.append(ratio)
        print(f"{name:<10} {fmt_wall(w[f'minyar@{n}']):>13} {fmt_wall(w[f'par@{n}']):>13} {ratio:>6.2f} | "
              f"{fmt_wall(w['minyar@1']):>13} {fmt_wall(w['par@1']):>13} {med['minyar@1'] / med[f'minyar@{n}']:>5.2f} "
              f"{med['par@1'] / med[f'par@{n}']:>5.2f}", flush=True)
    print(f"{'geomean':<10} {'':>13} {'':>13} {geomean(ratios):>6.2f}", flush=True)
    print(f"load after: {load_average()}", flush=True)
    return 0


def measure(args):
    names = programs(args.only)
    print(f"load before: {load_average()}", flush=True)
    n = args.threads
    print(f"{'program':<10} {'same':<4} {'minyar@1 Ir':>10} {'serial Ir':>10} {'best':<4} {'serial':>6} {'s-rust':>6} | "
          f"{f'minyar@{n} ms':>13} {f'rust@{n} ms':>13} {'par':>6} | {f'minyar@{n} Ir':>10} {f'rust@{n} Ir':>10} {'Ir x':>6} | "
          f"{'minyar@1 ms':>13} {'rust@1 ms':>13} {'m-scl':>5} {'r-scl':>5}", flush=True)
    rows = []
    for name in names:
        row = measure_program(name, args)
        print_row(row)
        rows.append(row)
    ok = [r for r in rows if "serial_ratio" in r]
    doc = {"tree": os.path.abspath(args.tree), "threads": n, "repeats": args.repeats,
           "tree_commit": subprocess.run(["git", "-C", args.tree, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
           "toolchains": {"c": tool_version([cc(), "--version"]), "cpp": tool_version([cxx(), "--version"]),
                          "rust": tool_version(["rustc", "--version"]), "valgrind": tool_version(["valgrind", "--version"])},
           "programs": rows}
    if ok:
        doc["serial_geomean"] = geomean([r["serial_ratio"] for r in ok])
        doc["parallel_geomean"] = geomean([r["parallel_ratio"] for r in ok])
        doc["serial_rust_geomean"] = geomean([r["serial_rust_ratio"] for r in ok])
        worst = {k: max(ok, key=lambda r: r[k]) for k in ("serial_ratio", "serial_rust_ratio", "parallel_ratio")}
        doc["worst"] = {k: {"ratio": r[k], "name": r["name"]} for k, r in worst.items()}
        print(f"{'geomean':<10} {'':<4} {'':>10} {'':>10} {'':<4} {doc['serial_geomean']:>6.2f} {doc['serial_rust_geomean']:>6.2f} | "
              f"{'':>13} {'':>13} {doc['parallel_geomean']:>6.2f}   ({len(ok)} programs; serial = Ir at 1 thread vs fastest"
              f" and vs Rust, parallel = wall at {n} vs par.rs)")
        print(f"{'worst':<10} {'':<4} {'':>10} {'':>10} {'':<4} {worst['serial_ratio']['serial_ratio']:>6.2f} "
              f"{worst['serial_rust_ratio']['serial_rust_ratio']:>6.2f} | {'':>13} {'':>13} "
              f"{worst['parallel_ratio']['parallel_ratio']:>6.2f}   ({worst['serial_ratio']['name']}, "
              f"{worst['serial_rust_ratio']['name']}, {worst['parallel_ratio']['name']})")
    print(f"load after: {load_average()}", flush=True)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(doc, f, indent=1)
    return 1 if any("error" in r or not r["identical"] for r in rows) else 0


def check_program(name, tree):
    work = os.path.join(REPO, "build", "bothmodes-check", name)
    os.makedirs(work, exist_ok=True)
    _, small = sizes(name)
    arg = prepare_input(name, small, work)
    build_ref("c", name, os.path.join(work, "c"), optimise=False)
    expected = run_output(os.path.join(work, "c"), arg, 1)
    problems = []
    for mode, exe in (("--debug", "minyar-o0"), ("--release", "minyar-release")):
        path = os.path.join(work, exe)
        try:
            build_minyar(tree, name, path, mode)
        except RuntimeError as e:
            problems.append(f"{mode}: {str(e).splitlines()[0]}")
            continue
        for threads in (1, 4):
            try:
                got = run_output(path, arg, threads)
            except subprocess.CalledProcessError as e:
                problems.append(f"{mode} at {threads} threads: exit {e.returncode}")
                continue
            if got != expected:
                with open(f"{path}@{threads}.out", "wb") as f:
                    f.write(got)
                with open(os.path.join(work, "c.out"), "wb") as f:
                    f.write(expected)
                problems.append(f"{mode} at {threads} threads: output differs from C ({path}@{threads}.out vs {work}/c.out)")
    return name, problems


def check(args):
    names = programs(args.only)
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max(1, args.jobs)) as pool:
        for name, problems in pool.map(lambda n: check_program(n, args.tree), names):
            print(f"{name:<10} {'ok' if not problems else 'FAIL'}", flush=True)
            for p in problems:
                print(f"    {p}")
            failed += bool(problems)
    print(f"check-benchmarks-bothmodes: {len(names) - failed}/{len(names)} programs match C at O0 and release, 1 and 4 threads")
    return 1 if failed else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", action="append", help="program name(s), comma-separated or repeated")
    p.add_argument("--tree", default=REPO, help="Minyar tree whose ./minyar builds the programs")
    p.add_argument("--json", help="write results as JSON")
    p.add_argument("--threads", type=int, default=4, help="parallel thread count (default 4)")
    p.add_argument("--repeats", type=int, default=5, help="interleaved wall-time runs per configuration (default 5)")
    p.add_argument("--jobs", type=int, default=0, help="concurrent programs for --check (default: CPU count, at most 6)")
    p.add_argument("--check", action="store_true", help="correctness only: O0 and release Minyar against C, small input")
    p.add_argument("--wall-only", action="store_true", help="only wall times, reusing the last full run's binaries")
    args = p.parse_args()
    args.tree = os.path.abspath(args.tree)
    if args.jobs == 0:
        args.jobs = min(6, os.cpu_count() or 2)
    if args.wall_only:
        sys.exit(wall_only(args))
    if not args.check and not shutil.which("valgrind"):
        sys.exit("run.py needs valgrind (cachegrind); use --check for correctness only")
    sys.exit(check(args) if args.check else measure(args))


if __name__ == "__main__":
    main()
