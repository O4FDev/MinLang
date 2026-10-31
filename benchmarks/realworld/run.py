#!/usr/bin/env python3
"""Real-world suite: other Minyar projects' own builds and workloads.

Every project below is a separate Minyar program built with the Minyar tree
under test. For each one the suite records

  * build seconds   -- a clean build of the project with the tree's toolchain,
  * workload Ir     -- retired instructions of one fixed workload (cachegrind
                       --tool=cachegrind --cache-sim=no, deterministic),
  * workload wall   -- median of N fresh-process runs with min/max spread.

The workloads are the projects' own: neo-db's embedded engine benchmark,
minyar-query's CSV SQL engine, minyar-js running a fixed script, minyar-terminal
replaying a pinned vtebench payload, minyar-sandbox's policy session loop and
minyar-sim's native universe benchmark. Inputs are deterministic and generated
here, never tuned per program.

  run.py [--tree DIR] [--projects DIR] [--only NAME[,NAME]] [--json OUT]
         [--repeat N] [--no-build] [--baseline FILE] [--write-baseline FILE]
         [--keep-going] [--profile]

`--projects` names the directory holding read-only copies of the upstream
projects (see sync-projects.sh). Their identity is the commit recorded in each
copy's `.rw-commit`; the suite refuses a copy whose recorded commit differs from
the pinned one in projects.py.
"""
import argparse
import hashlib
import json
import math
import os
import platform
import re
import shlex
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(HERE, "data")
THREADS = 1  # single-threaded workloads: the serial baseline
SQL = ("SELECT region, category, sum(quantity * price) AS revenue, count(*) AS orders "
       "FROM sales WHERE shipdate >= '1995-01-01' AND shipdate < '1996-01-01' "
       "GROUP BY region, category ORDER BY revenue DESC LIMIT 10")
QUERY_ROWS = 200000
JS_FUEL = 100000000
SIM_CASES = 100000
SANDBOX_REQUESTS = 20000
NEO_DB_ROWS = 2000
NEO_DB_ITERATIONS = 8000


class Failure(RuntimeError):
    pass


def default_clang(tree):
    selected = os.environ.get("MINYAR_CLANG") or os.environ.get("LLVM_CC")
    if selected:
        return selected
    try:
        found = subprocess.run(["sh", os.path.join(tree, "tools", "toolchain.sh"), "default-clang"],
                               capture_output=True, text=True).stdout.strip()
    except OSError:
        found = ""
    return found or "clang-23"


def tree_stamp(tree):
    """Identity of everything in the tree that decides generated code.

    Covers the compiler binary (its own hash, so a rebuild is visible), every
    runtime source, and the selected Clang. `minyar --version` alone is not
    enough: a runtime-only change keeps the same source hash.
    """
    digest = hashlib.sha256()
    digest.update(tool_version([os.path.join(tree, "minyar"), "--version"]).encode() + b"\0")
    digest.update(default_clang(tree).encode() + b"\0")
    for built in (os.path.join(tree, "build", "minyarc"),
                  os.path.join(tree, "build", "tooling", "tools", "clang-driver")):
        if os.path.exists(built):
            with open(built, "rb") as f:
                digest.update(hashlib.sha256(f.read()).digest())
    for area in ("runtime", "library"):
        for root, directories, files in os.walk(os.path.join(tree, area)):
            directories.sort()
            for name in sorted(files):
                if name.endswith((".c", ".h", ".min")):
                    path = os.path.join(root, name)
                    digest.update(os.path.relpath(path, tree).encode() + b"\0")
                    with open(path, "rb") as f:
                        digest.update(hashlib.sha256(f.read()).digest())
    return digest.hexdigest()[:24]


def tool_version(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return "missing"


def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ---------------------------------------------------------------- data inputs

LIFECYCLE = [
    ("created", "start"), ("created", "stop"), ("running", "exec"), ("running", "snapshot"),
    ("running", "stop"), ("stopped", "start"), ("stopped", "fork"), ("created", "delete"),
    ("deleted", "start"), ("failed", "delete"), ("bogus", "start"), ("running", "bogus"),
]
SESSIONS = [("999999999", "250"), ("3600000000000", "1250"), ("1", "7"), ("0", "0"),
            ("86400000000000", "1000000"), ("123456789", "99")]


def sandbox_requests(count):
    """Deterministic policy-session input: state transitions and billing asks."""
    state = 0x5A17_0000_0000_0001
    lines = []
    for _ in range(count):
        state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        choice = (state >> 33) % 16
        if choice < 12:
            source, action = LIFECYCLE[choice]
            lines.append(f"transition {source} {action}")
        else:
            total, rate = SESSIONS[choice - 12]
            lines.append(f"usage {total} {rate}")
    return ("\n".join(lines) + "\n").encode()


def prepare_data(work):
    """Write every generated workload input once; they are pure functions of the constants."""
    os.makedirs(work, exist_ok=True)
    sales = os.path.join(work, f"sales-{QUERY_ROWS}.csv")
    stamp = sales + ".src"
    digest = file_hash(os.path.join(DATA, "query_gen.py")) + str(QUERY_ROWS)
    if not (os.path.exists(sales) and os.path.exists(stamp) and open(stamp).read() == digest):
        subprocess.run([sys.executable, os.path.join(DATA, "query_gen.py"), sales, str(QUERY_ROWS)], check=True)
        with open(stamp, "w") as f:
            f.write(digest)
    js = os.path.join(work, "js_workload.js")
    if not os.path.exists(js) or file_hash(js) != file_hash(os.path.join(DATA, "js_workload.js")):
        with open(os.path.join(DATA, "js_workload.js"), "rb") as src, open(js, "wb") as dst:
            dst.write(src.read())
    requests = os.path.join(work, f"sandbox-{SANDBOX_REQUESTS}.txt")
    body = sandbox_requests(SANDBOX_REQUESTS)
    stamp = requests + ".src"
    digest = file_hash_text(body)
    if not (os.path.exists(requests) and os.path.exists(stamp) and open(stamp).read() == digest):
        with open(requests, "wb") as f:
            f.write(body)
        with open(stamp, "w") as f:
            f.write(digest)
    return {"sales": sales, "js": js, "requests": requests}


def file_hash_text(data):
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------- cross-project

def warm_tree(tree, clang, work):
    """Build the tree's runtime and driver once, before any timed build.

    A new compiler identity makes the launcher rebuild the configured runtime
    and the link driver; charging that to whichever project happens to build
    first would make the build column meaningless.
    """
    source = os.path.join(work, "warmup.min")
    if not os.path.exists(source):
        with open(source, "w") as f:
            f.write("function main(): Integer { return 0 }\n")
    env = dict(os.environ)
    env["MINYAR_CLANG"] = clang
    env["LLVM_CC"] = clang
    started = time.perf_counter()
    result = subprocess.run([os.path.join(tree, "minyar"), "--release", source,
                             "-o", os.path.join(work, "warmup")],
                            capture_output=True, env=env, text=True)
    if result.returncode != 0:
        raise Failure("warm-up build failed\n" + (result.stdout + result.stderr)[-2000:])
    return time.perf_counter() - started


def tree_identity(tree, clang):
    try:
        commit = subprocess.run(["git", "-C", tree, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    return {"path": os.path.abspath(tree), "commit": commit,
            "compiler": tool_version([os.path.join(tree, "minyar"), "--version"]),
            "tree_stamp": tree_stamp(tree) if os.path.isdir(tree) else "",
            "valgrind": tool_version(["valgrind", "--version"]),
            "clang": tool_version([clang, "--version"]),
            "platform": platform.platform(), "machine": platform.machine()}


def vtebench_payload(project):
    """The largest pinned vtebench payload: a dense-cell screen updated in place."""
    bench = os.path.join(project, "bench", "vtebench")
    payloads = sorted((p for p in os.listdir(bench) if p.startswith("dense_cells-") and p.endswith(".bin")),
                      key=lambda p: os.path.getsize(os.path.join(bench, p)))
    if not payloads:
        raise Failure(f"{project}: no dense_cells payload under bench/vtebench")
    return os.path.join(bench, payloads[-1])


# ------------------------------------------------------------------- building

def clean_paths(project, paths):
    for path in paths:
        full = os.path.join(project, path)
        if os.path.isdir(full):
            subprocess.run(["rm", "-rf", full], check=True)


def build_project(spec, tree, project, work, log, clang):
    env = dict(os.environ)
    env.update(spec.get("env", {}))
    env["MINYAR_ROOT"] = tree
    env["MINYAR_SDK"] = tree
    env["MINYAR_CLANG"] = clang
    env["LLVM_CC"] = clang
    env["MINYAR_PARALLEL_THREADS"] = str(THREADS)
    command = [part.replace("@TREE@", tree).replace("@WORK@", work).replace("@PROJECT@", project)
               .replace("@CLANG@", clang) for part in spec["build"]]
    clean_paths(project, spec.get("clean", []))
    os.makedirs(os.path.join(project, "build"), exist_ok=True)
    started = time.perf_counter()
    with open(log, "w") as out:
        out.write("+ " + " ".join(shlex.quote(c) for c in command) + "\n")
        out.flush()
        result = subprocess.run(command, cwd=project, stdout=out, stderr=subprocess.STDOUT, env=env)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise Failure(f"{spec['name']}: build failed (rc={result.returncode}); see {log}\n"
                      + tail(log, 3000))
    artifact = os.path.join(project, spec["artifact"])
    if not os.path.exists(artifact):
        raise Failure(f"{spec['name']}: build produced no {spec['artifact']}")
    return elapsed, artifact, env


def tail(path, limit):
    try:
        with open(path, errors="replace") as f:
            data = f.read()
        return data[-limit:]
    except OSError:
        return ""


# ----------------------------------------------------------------- measuring

def reset_paths(paths):
    for path in paths or []:
        if os.path.isdir(path):
            subprocess.run(["rm", "-rf", path], check=True)


def cachegrind(artifact, argv, env, work, tag, reset=(), stdin_path=None):
    reset_paths(reset)
    out_file = os.path.join(work, f"cachegrind.{tag}.out")
    stream = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
    started = time.perf_counter()
    try:
        result = subprocess.run(["valgrind", "--tool=cachegrind", "--cache-sim=no",
                                 f"--cachegrind-out-file={out_file}", artifact, *argv],
                                capture_output=True, env=env, stdin=stream)
    finally:
        if stdin_path:
            stream.close()
    if result.returncode != 0:
        raise Failure(f"{artifact}: cachegrind run failed (rc={result.returncode})\n"
                      + result.stderr.decode(errors="replace")[-3000:])
    with open(out_file) as f:
        for line in f:
            if line.startswith("summary:"):
                return int(line.split()[1]), result.stdout, time.perf_counter() - started
    raise Failure(f"{out_file}: no summary line")


def wall_times(artifact, argv, env, stdin_path, repeats, reset=()):
    samples = []
    outputs = []
    for _ in range(repeats):
        reset_paths(reset)
        stream = open(stdin_path, "rb") if stdin_path else subprocess.DEVNULL
        try:
            started = time.perf_counter()
            result = subprocess.run([artifact, *argv], stdin=stream, capture_output=True, env=env)
            samples.append(time.perf_counter() - started)
        finally:
            if stdin_path:
                stream.close()
        if result.returncode != 0:
            raise Failure(f"{artifact}: workload failed (rc={result.returncode})\n"
                          + result.stderr.decode(errors="replace")[-2000:])
        outputs.append(result.stdout)
    return samples, outputs


def check_output(spec, data):
    """Verify the workload did the expected work; returns the output sha256."""
    digest = hashlib.sha256(data).hexdigest()
    for needle in spec.get("contains", []):
        if needle.encode() not in data:
            raise Failure(f"{spec['name']}: output is missing {needle!r}")
    for needle in spec.get("absent", []):
        if needle.encode() in data:
            raise Failure(f"{spec['name']}: output unexpectedly contains {needle!r}")
    if len(data) == 0 and spec.get("nonempty", True):
        raise Failure(f"{spec['name']}: workload produced no output")
    return digest


# ---------------------------------------------------------------- projections

PROJECTS = [
    {
        "name": "neo-db",
        "repo": "neo-db",
        "commit": "e521f7512dd0f08a9ca18d179b42e929ebbaca9d",
        "build": ["@TREE@/minyar", "build", "--release", "--locked"],
        "clean": ["target"],
        "artifact": "target/release/neo-db",
        # The project's own in-process engine benchmark, built from its sources
        # with the same dependency library roots the package manifest uses.
        "executable": "@BENCH@",
        "workload": ["@WORK@/neo-db-data", str(NEO_DB_ITERATIONS)],
        "contains": [f"rows {NEO_DB_ROWS} "],
        # Opening a database reads the monotonic clock, so a few branches differ.
        "ir_tolerance": 0.001,
    },
    {
        "name": "minyar-query",
        "repo": "minyar-query",
        "commit": "6cddc423abb90c387154dba9c406fc1df1008801",
        "build": ["sh", "tools/build.sh", "release"],
        "clean": ["target"],
        "artifact": "target/query",
        "workload": ["--table", f"sales=@DATA@/sales-{QUERY_ROWS}.csv", "--sql", SQL,
                     "--repeat", "1"],
        "env": {"MINYAR_PARALLEL_THREADS": str(THREADS)},
        "contains": ["region,category,revenue,orders"],
    },
    {
        "name": "minyar-js",
        "repo": "minyar-js",
        "commit": "ef1ee526137a715f44990a96fe2a25324839d258",
        "build": ["make", "-j4", "MINYAR_ROOT=@TREE@", "CLANG=@CLANG@"],
        "clean": ["build"],
        "artifact": "build/minyar-js",
        "prerequisite": ["make", "-C", "@TREE@", "-j4", "build/minyar-default-runtime.o"],
        "workload": ["--fuel", str(JS_FUEL), "@DATA@/js_workload.js"],
        "contains": ["550 3989"],
    },
    {
        "name": "minyar-terminal",
        "repo": "minyar-terminal",
        "commit": "d226a371b926e9ef3e2aa4ee4f4407c018e9a942",
        "build": ["@TREE@/minyar", "--release", "src/main.min", "-o", "build/terminal"],
        "clean": ["build"],
        "artifact": "build/terminal",
        "workload": ["@PAYLOAD@", "120", "40", "1000", "4096"],
        "contains": ["\"version\":1"],
    },
    {
        "name": "minyar-sandbox",
        "repo": "minyar-sandbox",
        "commit": "01e478946d331094537ed185597e171e704ce110",
        "build": ["@TREE@/minyar", "src/main.min", "-o", "build/sandbox-policy"],
        "clean": ["build"],
        "artifact": "build/sandbox-policy",
        "env": {"MINYAR_CLANG_FLAGS": "-O2 -pthread -Wno-override-module"},
        "workload": ["serve"],
        "stdin": f"@DATA@/sandbox-{SANDBOX_REQUESTS}.txt",
        "contains": ["\"allowed\":true"],
    },
    {
        "name": "minyar-sim",
        "repo": "minyar-sim",
        "commit": "267e4b3074dae045f07c209e675e83db93a48603",
        "build": ["sh", "scripts/build-native.sh"],
        "clean": ["build"],
        "artifact": "build/native/sim-O2",
        "workload": ["bench", str(SIM_CASES)],
        "contains": [f"\"cases\":{SIM_CASES}"],
    },
]


NEO_DB_SOURCES = ("src", "sdk", "extensions", "bench/embedded")
NEO_DB_LIBRARIES = ["--library", "sdk/src", "--library", "extensions/vector/src",
                    "--library", "extensions/uuid-ossp/src", "--library", "extensions/feed-redact/src"]


def neo_db_source_hash(project):
    digest = hashlib.sha256()
    for area in NEO_DB_SOURCES:
        for root, directories, files in os.walk(os.path.join(project, area)):
            directories.sort()
            for name in sorted(files):
                if name.endswith((".min", ".toml")):
                    path = os.path.join(root, name)
                    digest.update(os.path.relpath(path, project).encode() + b"\0")
                    with open(path, "rb") as f:
                        digest.update(hashlib.sha256(f.read()).digest())
    return digest.hexdigest()


def neo_db_compile(project, tree, clang, source, output, stamp_key):
    """Compile one neo-db program, cached by compiler and project sources.

    Each compilation is a thin-LTO build of the whole engine (minutes), so the
    suite rebuilds only when the compiler identity or the sources change.
    """
    stamp_path = output + ".stamp"
    stamp = tree_stamp(tree) + "|" + neo_db_source_hash(project) + "|" + stamp_key
    if os.path.exists(output) and os.path.exists(stamp_path) and open(stamp_path).read() == stamp:
        return output
    env = dict(os.environ)
    env["MINYAR_ROOT"] = tree
    env["MINYAR_CLANG"] = clang
    env["LLVM_CC"] = clang
    command = [os.path.join(tree, "minyar"), "--release", *NEO_DB_LIBRARIES, source, "-o", output]
    started = time.perf_counter()
    result = subprocess.run(command, cwd=project, capture_output=True, env=env, text=True)
    if result.returncode != 0:
        raise Failure(f"neo-db: {source} build failed\n" + (result.stdout + result.stderr)[-3000:])
    with open(stamp_path, "w") as f:
        f.write(stamp)
    print(f"  neo-db: built {source} in {time.perf_counter() - started:.1f}s", flush=True)
    return output


def prepare_neo_db(project, tree, clang, work):
    """Return (read-only workload executable, prepared database directory).

    The database is loaded once by neo-db's own embedded benchmark and is a
    fixture, like `pgbench -i`: only the read workload is measured. The fixture
    stamp covers the project sources and row count, not the compiler, because the
    on-disk format is the project's, not the compiler's.
    """
    build = os.path.join(project, "build")
    os.makedirs(os.path.join(project, "bench", "realworld"), exist_ok=True)
    os.makedirs(build, exist_ok=True)
    driver = os.path.join(project, "bench", "realworld", "read.min")
    with open(os.path.join(DATA, "neo_db_read.min"), "rb") as src, open(driver, "wb") as dst:
        dst.write(src.read())
    read = neo_db_compile(project, tree, clang, "bench/realworld/read.min", os.path.join(build, "neo_read"),
                          f"read.{NEO_DB_ITERATIONS}")
    loader = neo_db_compile(project, tree, clang, "bench/embedded/embed_bench.min",
                            os.path.join(build, "embed_bench"), "embed_bench")
    data = os.path.join(work, "neo-db-data")
    fixture_stamp = data + ".stamp"
    stamp = neo_db_source_hash(project) + "|" + str(NEO_DB_ROWS)
    if not (os.path.exists(data) and os.path.exists(fixture_stamp) and open(fixture_stamp).read() == stamp):
        subprocess.run(["rm", "-rf", data], check=False)
        os.makedirs(os.path.dirname(data), exist_ok=True)
        started = time.perf_counter()
        result = subprocess.run([loader, data, str(NEO_DB_ROWS), "1"], capture_output=True, text=True,
                                env={**os.environ, "MINYAR_ROOT": tree})
        if result.returncode != 0:
            raise Failure("neo-db: fixture load failed\n" + (result.stdout + result.stderr)[-3000:])
        with open(fixture_stamp, "w") as f:
            f.write(stamp)
        print(f"  neo-db: loaded {NEO_DB_ROWS} fixture rows in {time.perf_counter() - started:.1f}s", flush=True)
    return read, data


def resolve(spec, tree, project, work, artifact, prepared, clang):
    values = {"@TREE@": tree, "@WORK@": work, "@DATA@": os.path.join(work, "data"),
              "@PROJECT@": project, "@ARTIFACT@": artifact, "@CLANG@": clang,
              "@BENCH@": prepared.get("bench", ""), "@PAYLOAD@": prepared.get("payload", "")}
    argv = []
    for part in spec:
        for key, value in values.items():
            part = part.replace(key, value)
        argv.append(part)
    return argv


def measure(spec, args, work, prepared, clang):
    name = spec["name"]
    project = os.path.join(args.projects, spec["repo"])
    if not os.path.isdir(project):
        raise Failure(f"{name}: no project copy at {project}")
    recorded = ""
    commit_file = os.path.join(project, ".rw-commit")
    if os.path.exists(commit_file):
        recorded = open(commit_file).read().strip()
    if recorded and not recorded.startswith(spec["commit"][:12]):
        raise Failure(f"{name}: copy is at {recorded}, suite pins {spec['commit'][:12]}")
    row = {"name": name, "commit": recorded or spec["commit"], "repo": project}
    project_work = os.path.join(work, name)
    os.makedirs(project_work, exist_ok=True)
    log = os.path.join(project_work, "build.log")
    environment = dict(os.environ)
    environment.update(spec.get("env", {}))
    environment["MINYAR_ROOT"] = args.tree
    environment["MINYAR_CLANG"] = clang
    environment["LLVM_CC"] = clang
    environment["MINYAR_PARALLEL_THREADS"] = str(THREADS)
    if spec.get("prerequisite"):
        command = resolve(spec["prerequisite"], args.tree, project, work, "", prepared, clang)
        with open(os.path.join(project_work, "prerequisite.log"), "w") as out:
            result = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT, env=environment)
        if result.returncode != 0:
            raise Failure(f"{name}: prerequisite failed")
    if args.no_build:
        artifact = os.path.join(project, spec["artifact"])
        if not os.path.exists(artifact):
            raise Failure(f"{name}: --no-build but {artifact} is missing")
        row["build_seconds"] = None
    else:
        row["build_seconds"], artifact, _ = build_project(spec, args.tree, project, work, log, clang)
    if name == "neo-db":
        prepared["bench"], _fixture = prepare_neo_db(project, args.tree, clang, work)
    else:
        prepared["bench"] = ""
    prepared["payload"] = vtebench_payload(project) if name == "minyar-terminal" else ""
    if name == "neo-db":
        os.makedirs(os.path.join(work, "neo-db-data"), exist_ok=True)
    executable = resolve([spec["executable"]], args.tree, project, work, artifact, prepared, clang)[0] \
        if spec.get("executable") else artifact
    argv = resolve(spec["workload"], args.tree, project, work, artifact, prepared, clang)
    if not os.path.exists(executable):
        raise Failure(f"{name}: workload executable {executable} is missing")
    stdin_path = (spec["stdin"].replace("@DATA@", os.path.join(work, "data")).replace("@TREE@", args.tree)
                  if spec.get("stdin") else None)
    if stdin_path and not os.path.exists(stdin_path):
        raise Failure(f"{name}: workload input {stdin_path} is missing")
    reset = [path.replace("@WORK@", work).replace("@TREE@", args.tree) for path in spec.get("reset", [])]
    ir, first_output, ir_seconds = cachegrind(executable, argv, environment, project_work, name, reset, stdin_path)
    digest = check_output(spec, first_output)
    # A second identical run proves the workload and its output are deterministic.
    second_ir, second_output, _ = cachegrind(executable, argv, environment, project_work, name + "-2", reset, stdin_path)
    tolerance = spec.get("ir_tolerance", 0.0)
    if abs(second_ir - ir) > tolerance * max(ir, second_ir):
        raise Failure(f"{name}: instruction count is not deterministic ({ir} then {second_ir}"
                      f", tolerance {tolerance:.4%})")
    ir = min(ir, second_ir)
    if spec.get("stable_output", True) and hashlib.sha256(second_output).hexdigest() != digest:
        raise Failure(f"{name}: workload output is not deterministic")
    samples, outputs = wall_times(executable, argv, environment, stdin_path, args.repeat, reset)
    if spec.get("stable_output", True) and hashlib.sha256(outputs[0]).hexdigest() != digest:
        raise Failure(f"{name}: workload output differs outside cachegrind")
    row.update({
        "ir": ir,
        "output_sha256": digest,
        "wall_seconds": samples,
        "wall_median": statistics.median(samples),
        "wall_min": min(samples),
        "wall_max": max(samples),
        "cachegrind_seconds": ir_seconds,
        "executable": executable,
        "argv": argv,
    })
    return row


# ------------------------------------------------------------------ reporting

def ratio(value, base):
    if value is None or not base:
        return None
    return value / base


def fmt_ratio(value):
    return "  --  " if value is None else f"{value:5.2f}x"


def geomean(values):
    values = [v for v in values if v]
    if not values:
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))


def print_rows(results, baseline):
    base_projects = (baseline or {}).get("projects", {})
    header = (f"{'project':<18}{'build s':>9}{'xbase':>7}{'Ir':>13}{'xbase':>7}"
              f"{'wall ms':>11}{'spread':>9}{'xbase':>7}  status")
    print(header, flush=True)
    for row in results:
        base = base_projects.get(row["name"], {})
        if "error" in row:
            print(f"{row['name']:<18} ERROR {row['error'].splitlines()[0]}", flush=True)
            continue
        build = row.get("build_seconds")
        wall = row["wall_median"] * 1000
        spread = (row["wall_max"] - row["wall_min"]) * 1000
        print(f"{row['name']:<18}"
              f"{(f'{build:.1f}' if build is not None else '--'):>9}"
              f"{fmt_ratio(ratio(build, base.get('build_seconds'))):>7}"
              f"{row['ir'] / 1e6:>12,.1f}M{fmt_ratio(ratio(row['ir'], base.get('ir'))):>7}"
              f"{wall:>11.1f}{spread:>9.1f}{fmt_ratio(ratio(wall, base.get('wall_median', 0) * 1000 if base.get('wall_median') else None)):>7}"
              f"  ok", flush=True)


def summarize(results, baseline):
    base = (baseline or {}).get("geomean", {})
    irs = [r["ir"] for r in results if "ir" in r and (baseline or {}).get("projects", {}).get(r["name"], {}).get("ir")]
    builds = [r["build_seconds"] for r in results if r.get("build_seconds")
              and (baseline or {}).get("projects", {}).get(r["name"], {}).get("build_seconds")]
    walls = [r["wall_median"] for r in results if "wall_median" in r
             and (baseline or {}).get("projects", {}).get(r["name"], {}).get("wall_median")]
    base_projects = (baseline or {}).get("projects", {})
    ir_geo = geomean([r["ir"] / base_projects[r["name"]]["ir"] for r in results
                      if "ir" in r and base_projects.get(r["name"], {}).get("ir")])
    build_geo = geomean([r["build_seconds"] / base_projects[r["name"]]["build_seconds"] for r in results
                         if r.get("build_seconds") and base_projects.get(r["name"], {}).get("build_seconds")])
    wall_geo = geomean([r["wall_median"] / base_projects[r["name"]]["wall_median"] for r in results
                        if "wall_median" in r and base_projects.get(r["name"], {}).get("wall_median")])
    ok = [r for r in results if "ir" in r]
    if ok:
        worst = max(ok, key=lambda r: r["ir"] / base_projects[r["name"]]["ir"]
                    if base_projects.get(r["name"], {}).get("ir") else 1)
        line = f"{'geomean':<18}{'':>16}{'':>7}{'':>13}"
        print(f"{'geomean':<18}{'':>16}{'':>7}{'':>13}{'':>7}{'':>11}{'':>9}{'':>7}  "
              f"build {fmt_ratio(build_geo)}  Ir {fmt_ratio(ir_geo)}  wall {fmt_ratio(wall_geo)}"
              f"  ({len(ok)} projects)", flush=True)
        if base_projects.get(worst["name"], {}).get("ir"):
            print(f"worst project: {worst['name']} {fmt_ratio(worst['ir'] / base_projects[worst['name']]['ir'])}",
                  flush=True)
    return {"ir": ir_geo, "build": build_geo, "wall": wall_geo}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tree", default=REPO, help="Minyar tree under test (default: this checkout)")
    parser.add_argument("--projects", default="/home/agent/swarm/realworld",
                        help="directory holding the read-only project copies")
    parser.add_argument("--only", action="append", default=[], help="project names, comma separated")
    parser.add_argument("--json", help="write the full report here")
    parser.add_argument("--baseline", default=os.path.join(HERE, "baseline.json"))
    parser.add_argument("--write-baseline", help="record this run as the baseline")
    parser.add_argument("--repeat", type=int, default=5, help="wall samples per workload")
    parser.add_argument("--no-build", action="store_true", help="reuse existing artifacts, skip builds")
    parser.add_argument("--keep-going", action="store_true", help="record failures and continue")
    args = parser.parse_args()
    args.tree = os.path.abspath(args.tree)
    work = os.path.join(args.tree, "build", "realworld")
    os.makedirs(work, exist_ok=True)
    prepared = prepare_data(os.path.join(work, "data"))
    wanted = [name for item in args.only for name in item.split(",") if name]
    if wanted:
        known = {spec["name"] for spec in PROJECTS}
        missing = [name for name in wanted if name not in known]
        if missing:
            sys.exit(f"unknown project(s): {', '.join(missing)}")
    specs = [spec for spec in PROJECTS if not wanted or spec["name"] in wanted]
    baseline = None
    if args.baseline and os.path.exists(args.baseline):
        with open(args.baseline) as f:
            baseline = json.load(f)
    clang = default_clang(args.tree)
    identity = tree_identity(args.tree, clang)
    warmed = warm_tree(args.tree, clang, work)
    print(f"tree {identity['path']} commit {identity['commit'][:12] or 'unknown'}"
          f"  projects {args.projects}  baseline {identity_commit(baseline)}"
          f"  warm-up {warmed:.1f}s", flush=True)
    results = []
    for spec in specs:
        try:
            results.append(measure(spec, args, work, prepared, clang))
        except (Failure, subprocess.CalledProcessError) as error:
            row = {"name": spec["name"], "error": str(error)}
            results.append(row)
            if not args.keep_going:
                print_rows(results, baseline)
                sys.exit(f"{spec['name']}: {error}")
    print_rows(results, baseline)
    totals = summarize(results, baseline)
    doc = {"tree": identity, "threads": THREADS, "warmup_seconds": warmed, "projects_root": os.path.abspath(args.projects),
           "inputs": {"query_rows": QUERY_ROWS, "sales_sha256": file_hash(prepared["sales"]),
                      "js_sha256": file_hash(prepared["js"]), "sandbox_requests": SANDBOX_REQUESTS,
                      "sandbox_sha256": file_hash(prepared["requests"]),
                      "sim_cases": SIM_CASES, "neo_db_rows": NEO_DB_ROWS,
                      "neo_db_iterations": NEO_DB_ITERATIONS, "js_fuel": JS_FUEL,
                      "sql": SQL, "sandbox_lines": SANDBOX_REQUESTS},
           "geomean": totals, "projects": results}
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(doc, f, indent=1)
    if args.write_baseline:
        base = {"tree": identity, "inputs": doc["inputs"],
                "geomean": {"ir": 1.0, "build": 1.0, "wall": 1.0},
                "projects": {r["name"]: {key: r.get(key) for key in
                                         ("build_seconds", "ir", "wall_median", "output_sha256", "commit")}
                             for r in results if "ir" in r}}
        with open(args.write_baseline, "w") as f:
            json.dump(base, f, indent=1)
        print(f"wrote baseline {args.write_baseline}", flush=True)
    failed = [r for r in results if "error" in r]
    return 1 if failed else 0


def identity_commit(baseline):
    if not baseline:
        return "none"
    return (baseline.get("tree", {}).get("commit") or "unknown")[:12]


if __name__ == "__main__":
    sys.exit(main())
