#!/usr/bin/env python3
"""Four-language comparison suite: Minyar against C, C++ and Rust.

Every directory under benchmarks/compare/ holding a main.min is one program,
with main.c, main.cpp and main.rs peers that must print byte-identical output.
Its `sizes` file holds two Integers, the full and the small workload. When the
directory has a gen.c, that generator writes the input file (`gen N > input`)
and each program receives the file's path; otherwise it receives N itself.

  run.py [--only NAME] [--tree DIR] [--json OUT] [--perf] [--jobs N]
      Builds all four with fixed flags, checks output identity and prints
      retired instructions (cachegrind Ir, --cache-sim=no, all threads) and the
      ratio minyar / min(c, cpp, rust), with a geomean line. Reference Ir is
      cached by source hash and compiler version in build/compare-cache/.
      --perf adds wall times (n=3, interleaved; median and spread).
      --profile keeps cg_annotate function tables for Minyar and the fastest
      reference in build/compare/NAME/*.annotate.txt and prints the top lines.
  run.py --check [--only NAME] [--tree DIR]
      Correctness only, on the host: builds Minyar at O0 (--debug) and release
      and checks each against the C reference on the small workload.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
THREADS = 4  # every parallel program uses exactly this many threads
LANGS = ("minyar", "c", "cpp", "rust")
REFS = ("c", "cpp", "rust")
X86 = platform.machine() in ("x86_64", "AMD64")
ARCH = ["-march=x86-64-v3"] if X86 else []


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def capture(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()


def tool_version(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return "missing"


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
    src = os.path.join(HERE, name, {"c": "main.c", "cpp": "main.cpp", "rust": "main.rs"}[lang])
    if lang == "c":
        cmd = [cc(), "-O3" if optimise else "-O2", *ARCH, src, "-o", out, "-lm", "-pthread"]
    elif lang == "cpp":
        cmd = [cxx(), "-O3", *ARCH, "-std=c++20", src, "-o", out, "-pthread"]
    else:
        cmd = ["rustc", "-C", "opt-level=3", *(["-C", "target-cpu=x86-64-v3"] if X86 else []),
               "-C", "codegen-units=1", "-C", "lto=fat", "-C", "panic=abort", "--edition", "2021",
               src, "-o", out]
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


def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def env_for_run():
    env = dict(os.environ)
    env["MINYAR_PARALLEL_THREADS"] = str(THREADS)
    return env


def run_output(exe, arg):
    return subprocess.run([exe, arg], check=True, capture_output=True, env=env_for_run()).stdout


def cachegrind(exe, arg, work, tag):
    out_file = os.path.join(work, f"cachegrind.{tag}.out")
    r = subprocess.run(["valgrind", "--tool=cachegrind", "--cache-sim=no", f"--cachegrind-out-file={out_file}",
                        exe, arg], capture_output=True, env=env_for_run())
    if r.returncode != 0:
        raise RuntimeError(f"{exe}: cachegrind run failed\n" + r.stderr.decode(errors="replace")[-2000:])
    with open(out_file) as f:
        for line in f:
            if line.startswith("summary:"):
                return int(line.split()[1]), r.stdout
    raise RuntimeError(f"{out_file}: no summary line")


def ref_cache_key(lang, name, arg_desc):
    h = hashlib.sha256()
    for part in (lang, name, arg_desc, tool_version([cc(), "--version"]), tool_version([cxx(), "--version"]),
                 tool_version(["rustc", "--version"]), tool_version(["valgrind", "--version"]), " ".join(ARCH)):
        h.update(part.encode() + b"\0")
    for f in ("main.c", "main.cpp", "main.rs", "gen.c", "sizes"):
        p = os.path.join(HERE, name, f)
        if os.path.exists(p):
            h.update(f.encode() + file_hash(p).encode())
    return h.hexdigest()[:24]


def measure_program(name, args, results):
    work = os.path.join(REPO, "build", "compare", name)
    os.makedirs(work, exist_ok=True)
    cache_dir = os.path.join(REPO, "build", "compare-cache")
    os.makedirs(cache_dir, exist_ok=True)
    full, _ = sizes(name)
    arg = prepare_input(name, full, work)
    row = {"name": name, "ir": {}, "identical": True, "outputs": {}}
    exes = {}
    try:
        build_minyar(args.tree, name, os.path.join(work, "minyar"), "--release")
        exes["minyar"] = os.path.join(work, "minyar")
        for lang in REFS:
            exes[lang] = os.path.join(work, lang)
            key = ref_cache_key(lang, name, str(full))
            cached = os.path.join(cache_dir, f"{name}-{lang}-{key}.json")
            if os.path.exists(cached) and not args.perf:
                with open(cached) as f:
                    data = json.load(f)
                row["ir"][lang] = data["ir"]
                row["outputs"][lang] = data["output_sha256"]
                continue
            build_ref(lang, name, exes[lang])
            ir, out = cachegrind(exes[lang], arg, work, lang)
            row["ir"][lang] = ir
            row["outputs"][lang] = hashlib.sha256(out).hexdigest()
            with open(cached, "w") as f:
                json.dump({"ir": ir, "output_sha256": row["outputs"][lang]}, f)
        ir, out = cachegrind(exes["minyar"], arg, work, "minyar")
        row["ir"]["minyar"] = ir
        row["outputs"]["minyar"] = hashlib.sha256(out).hexdigest()
        with open(os.path.join(work, "minyar.out"), "wb") as f:
            f.write(out)
        row["identical"] = len(set(row["outputs"].values())) == 1
        row["ratio"] = ir / min(row["ir"][lang] for lang in REFS)
        row["fastest_ref"] = min(REFS, key=lambda lang: row["ir"][lang])
        if args.profile:
            row["profile"] = {}
            for lang in ("minyar", row["fastest_ref"]):
                out_file = os.path.join(work, f"cachegrind.{lang}.out")
                if not os.path.exists(out_file):
                    cachegrind(exes[lang] if os.path.exists(exes[lang]) else build_and_path(lang, name, exes), arg, work, lang)
                text = subprocess.run(["cg_annotate", "--auto=no", out_file], capture_output=True, text=True).stdout
                with open(os.path.join(work, f"{lang}.annotate.txt"), "w") as f:
                    f.write(text)
                row["profile"][lang] = top_functions(text)
        if args.perf:
            row["wall"] = wall_times(exes, arg)
            best = min(statistics.median(row["wall"][lang]) for lang in REFS)
            row["wall_ratio"] = statistics.median(row["wall"]["minyar"]) / best
    except (RuntimeError, subprocess.CalledProcessError) as e:
        row["error"] = str(e)
    results[name] = row
    return row


def build_and_path(lang, name, exes):
    build_ref(lang, name, exes[lang])
    return exes[lang]


def top_functions(annotate, count=15):
    """The leading entries of cg_annotate's Function:file summary."""
    lines, inside = [], False
    for line in annotate.splitlines():
        if line.startswith("-- Function:file summary"):
            inside = True
        elif inside and line.startswith(">"):
            match = re.match(r">\s*([\d,]+)\s+\(\s*([\d.]+)%.*?\)\s+(.*)", line)
            if match:
                lines.append({"ir": int(match.group(1).replace(",", "")), "percent": float(match.group(2)),
                              "function": match.group(3).rsplit(":", 1)[0]})
            if len(lines) == count:
                break
    return lines


def wall_times(exes, arg, repeats=3):
    walls = {lang: [] for lang in LANGS}
    for _ in range(repeats):
        for lang in LANGS:
            start = time.perf_counter()
            subprocess.run([exes[lang], arg], check=True, stdout=subprocess.DEVNULL, env=env_for_run())
            walls[lang].append(time.perf_counter() - start)
    return walls


def fmt_ir(n):
    return f"{n / 1e6:,.1f}M"


def print_row(row, perf):
    if "error" in row:
        print(f"{row['name']:<16} ERROR {row['error'].splitlines()[0]}", flush=True)
        return
    ir = row["ir"]
    line = (f"{row['name']:<16} {'yes' if row['identical'] else 'NO':<4} "
            + " ".join(f"{fmt_ir(ir[lang]):>12}" for lang in LANGS)
            + f" {row['ratio']:>7.2f}  {row['fastest_ref']}")
    if perf:
        w = row["wall"]
        line += " " + " ".join(f"{statistics.median(w[lang]) * 1000:>8.1f}ms±{(max(w[lang]) - min(w[lang])) * 500:.1f}"
                               for lang in LANGS)
        line += f" {row['wall_ratio']:>6.2f}"
    print(line, flush=True)
    for lang, entries in row.get("profile", {}).items():
        print(f"    {lang} top functions:")
        for e in entries:
            print(f"      {e['percent']:5.1f}% {e['ir'] / 1e6:10.1f}M  {e['function']}")


def measure(args):
    names = programs(args.only)
    header = f"{'program':<16} {'same':<4} " + " ".join(f"{lang + ' Ir':>12}" for lang in LANGS) + f" {'ratio':>7}  best"
    if args.perf:
        header += " " + " ".join(f"{lang + ' wall':>14}" for lang in LANGS) + "  wallx"
    print(header, flush=True)
    results = {}
    if args.jobs > 1 and not args.perf:
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            for row in pool.map(lambda n: measure_program(n, args, results), names):
                print_row(row, False)
                sys.stdout.flush()
    else:
        for name in names:
            print_row(measure_program(name, args, results), args.perf)
    ok = [r for r in results.values() if "ratio" in r]
    if ok:
        geo = math.exp(sum(math.log(r["ratio"]) for r in ok) / len(ok))
        print(f"{'geomean':<16} {'':<4} " + " " * (13 * len(LANGS)) + f" {geo:>7.2f}  ({len(ok)} programs)")
    if args.json:
        doc = {"tree": os.path.abspath(args.tree), "threads": THREADS,
               "tree_commit": subprocess.run(["git", "-C", args.tree, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
               "toolchains": {"c": tool_version([cc(), "--version"]), "cpp": tool_version([cxx(), "--version"]),
                              "rust": tool_version(["rustc", "--version"]), "valgrind": tool_version(["valgrind", "--version"])},
               "programs": [results[n] for n in names]}
        if ok:
            doc["geomean_ratio"] = geo
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(doc, f, indent=1)
    bad = [r for r in results.values() if "error" in r or not r["identical"]]
    return 1 if bad else 0


def check_program(name, tree):
    work = os.path.join(REPO, "build", "compare-check", name)
    os.makedirs(work, exist_ok=True)
    _, small = sizes(name)
    arg = prepare_input(name, small, work)
    build_ref("c", name, os.path.join(work, "c"), optimise=False)
    expected = run_output(os.path.join(work, "c"), arg)
    problems = []
    for mode, exe in (("--debug", "minyar-o0"), ("--release", "minyar-release")):
        path = os.path.join(work, exe)
        try:
            build_minyar(tree, name, path, mode)
            got = run_output(path, arg)
        except (RuntimeError, subprocess.CalledProcessError) as e:
            problems.append(f"{mode}: {str(e).splitlines()[0]}")
            continue
        if got != expected:
            with open(path + ".out", "wb") as f:
                f.write(got)
            with open(os.path.join(work, "c.out"), "wb") as f:
                f.write(expected)
            problems.append(f"{mode}: output differs from C ({path}.out vs {work}/c.out)")
    return name, problems


def check(args):
    names = programs(args.only)
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max(1, args.jobs)) as pool:
        for name, problems in pool.map(lambda n: check_program(n, args.tree), names):
            print(f"{name:<16} {'ok' if not problems else 'FAIL'}", flush=True)
            for p in problems:
                print(f"    {p}")
            failed += bool(problems)
    print(f"check-benchmarks-compare: {len(names) - failed}/{len(names)} programs match C at O0 and release")
    return 1 if failed else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", action="append", help="program name(s), comma-separated or repeated")
    p.add_argument("--tree", default=REPO, help="Minyar tree whose ./minyar builds the programs")
    p.add_argument("--json", help="write results as JSON")
    p.add_argument("--perf", action="store_true", help="also measure wall time, n=3 interleaved")
    p.add_argument("--profile", action="store_true", help="print cg_annotate top functions for Minyar and the fastest reference")
    p.add_argument("--jobs", type=int, default=0, help="concurrent programs (default: 2 for Ir, CPU count for --check)")
    p.add_argument("--check", action="store_true", help="correctness only: O0 and release Minyar against C, small input")
    args = p.parse_args()
    args.tree = os.path.abspath(args.tree)
    if args.jobs == 0:
        args.jobs = min(8, os.cpu_count() or 2) if args.check else 2
    if not args.check and not shutil.which("valgrind"):
        sys.exit("run.py needs valgrind (cachegrind); use --check for correctness only")
    sys.exit(check(args) if args.check else measure(args))


if __name__ == "__main__":
    main()
