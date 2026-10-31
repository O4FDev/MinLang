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
         [--against DIR] [--keep-going]

`--against DIR` builds a second Minyar tree too, counts instructions for both,
and alternates the wall samples between the two binaries, so a merge can be
judged on one run instead of two sequential ones.

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


def stage(spec, tree, args, work, prepared, clang, tag):
    """Build the project with TREE and keep a copy of its workload executable.

    Building twice into the same project copy would overwrite the first tree's
    binaries, so each stage copies its executable out to `build/realworld/ab`.
    """
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
    log = os.path.join(project_work, f"build-{tag}.log")
    environment = dict(os.environ)
    environment.update(spec.get("env", {}))
    environment["MINYAR_ROOT"] = tree
    environment["MINYAR_CLANG"] = clang
    environment["LLVM_CC"] = clang
    environment["MINYAR_PARALLEL_THREADS"] = str(THREADS)
    if spec.get("prerequisite"):
        command = resolve(spec["prerequisite"], tree, project, work, "", prepared, clang)
        with open(os.path.join(project_work, f"prerequisite-{tag}.log"), "w") as out:
            result = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT, env=environment)
        if result.returncode != 0:
            raise Failure(f"{name}: prerequisite failed")
    stamp_file = os.path.join(project, spec["artifact"] + ".rw-tree")
    if args.no_build:
        artifact = os.path.join(project, spec["artifact"])
        if not os.path.exists(artifact):
            raise Failure(f"{name}: --no-build but {artifact} is missing")
        built_by = open(stamp_file).read().strip() if os.path.exists(stamp_file) else ""
        if built_by != tree_stamp(tree):
            raise Failure(f"{name}: --no-build but {artifact} was built by another tree; run without --no-build")
        row["build_seconds"] = None
    else:
        row["build_seconds"], artifact, _ = build_project(spec, tree, project, work, log, clang)
        with open(stamp_file, "w") as f:
            f.write(tree_stamp(tree))
    if name == "neo-db":
        prepared["bench"], _fixture = prepare_neo_db(project, tree, clang, work)
    else:
        prepared["bench"] = ""
    prepared["payload"] = vtebench_payload(project) if name == "minyar-terminal" else ""
    executable = resolve([spec["executable"]], tree, project, work, artifact, prepared, clang)[0] \
        if spec.get("executable") else artifact
    if not os.path.exists(executable):
        raise Failure(f"{name}: workload executable {executable} is missing")
    argv = resolve(spec["workload"], tree, project, work, artifact, prepared, clang)
    stdin_path = (spec["stdin"].replace("@DATA@", os.path.join(work, "data")).replace("@TREE@", tree)
                  if spec.get("stdin") else None)
    if stdin_path and not os.path.exists(stdin_path):
        raise Failure(f"{name}: workload input {stdin_path} is missing")
    stored_dir = os.path.join(work, "ab", f"{name}-{tag}")
    os.makedirs(stored_dir, exist_ok=True)
    stored = os.path.join(stored_dir, os.path.basename(executable))
    with open(executable, "rb") as src, open(stored, "wb") as dst:
        dst.write(src.read())
    os.chmod(stored, 0o755)
    return {"row": row, "executable": stored, "argv": argv, "environment": environment,
            "stdin_path": stdin_path, "work": project_work, "tag": tag,
            "reset": [path.replace("@WORK@", work).replace("@TREE@", tree) for path in spec.get("reset", [])],
            "tree": tree}


def measure_once(stage_, timeout=None):
    reset_paths(stage_["reset"])
    stream = open(stage_["stdin_path"], "rb") if stage_["stdin_path"] else subprocess.DEVNULL
    started = time.perf_counter()
    try:
        result = subprocess.run([stage_["executable"], *stage_["argv"]], stdin=stream,
                                capture_output=True, env=stage_["environment"], timeout=timeout)
    finally:
        if stage_["stdin_path"]:
            stream.close()
    seconds = time.perf_counter() - started
    if result.returncode != 0:
        raise Failure(f"{stage_['executable']}: workload failed (rc={result.returncode})\n"
                      + result.stderr.decode(errors="replace")[-2000:])
    return seconds, result.stdout


def run_stage(spec, stage_, work, repeats):
    """Instruction count (twice, must agree) and the output digest of one stage."""
    name, tag = spec["name"], stage_["tag"]
    project_work = os.path.join(work, name)
    ir, first_output, ir_seconds = cachegrind(stage_["executable"], stage_["argv"], stage_["environment"],
                                              project_work, f"{name}-{tag}", stage_["reset"], stage_["stdin_path"])
    digest = check_output(spec, first_output)
    second_ir, second_output, _ = cachegrind(stage_["executable"], stage_["argv"], stage_["environment"],
                                             project_work, f"{name}-{tag}-2", stage_["reset"], stage_["stdin_path"])
    tolerance = spec.get("ir_tolerance", 0.0)
    if abs(second_ir - ir) > tolerance * max(ir, second_ir):
        raise Failure(f"{name}: instruction count is not deterministic ({ir} then {second_ir}"
                      f", tolerance {tolerance:.4%})")
    if spec.get("stable_output", True) and hashlib.sha256(second_output).hexdigest() != digest:
        raise Failure(f"{name}: workload output is not deterministic")
    samples = []
    for _ in range(repeats):
        seconds, output = measure_once(stage_)
        if spec.get("stable_output", True) and hashlib.sha256(output).hexdigest() != digest:
            raise Failure(f"{name}: workload output differs outside cachegrind")
        samples.append(seconds)
    return {"ir": min(ir, second_ir), "output_sha256": digest, "wall_seconds": samples,
            "cachegrind_seconds": ir_seconds, "executable": stage_["executable"], "argv": stage_["argv"],
            "build_seconds": stage_["row"].get("build_seconds")}


def wall_pair(stages, repeats):
    """Wall samples for two stages, alternating which stage runs first."""
    keys = list(stages)
    samples = {key: [] for key in keys}
    digests = {key: None for key in keys}
    for index in range(repeats):
        order = keys if index % 2 == 0 else list(reversed(keys))
        for key in order:
            seconds, output = measure_once(stages[key])
            samples[key].append(seconds)
            if digests[key] is None:
                digests[key] = hashlib.sha256(output).hexdigest()
    return samples, digests


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
        wall = statistics.median(row["wall_seconds"]) * 1000
        spread = (max(row["wall_seconds"]) - min(row["wall_seconds"])) * 1000
        base_wall = base.get("wall_median")
        print(f"{row['name']:<18}"
              f"{(f'{build:.1f}' if build is not None else '--'):>9}"
              f"{fmt_ratio(ratio(build, base.get('build_seconds'))):>7}"
              f"{row['ir'] / 1e6:>12,.1f}M{fmt_ratio(ratio(row['ir'], base.get('ir'))):>7}"
              f"{wall:>11.1f}{spread:>9.1f}{fmt_ratio(ratio(wall / 1000, base_wall)):>7}"
              f"  ok", flush=True)


def print_pair(rows, against):
    """One line per project: the tree under test against the `--against` tree."""
    print(f"{'project':<18}{'build a':>8}{'b':>8}{'ratio':>7}{'Ir a':>13}{'b':>13}{'ratio':>7}"
          f"{'wall a':>9}{'b':>9}{'ratio':>7}  status", flush=True)
    for row in rows:
        if "error" in row:
            print(f"{row['name']:<18} ERROR {row['error'].splitlines()[0]}", flush=True)
            continue
        a, b = row["a"], row["b"]
        build_a, build_b = a.get("build_seconds"), b.get("build_seconds")
        wall_a, wall_b = statistics.median(a["wall_seconds"]) * 1000, statistics.median(b["wall_seconds"]) * 1000
        print(f"{row['name']:<18}"
              f"{(f'{build_a:.1f}' if build_a is not None else '--'):>8}"
              f"{(f'{build_b:.1f}' if build_b is not None else '--'):>8}"
              f"{fmt_ratio(ratio(build_a, build_b)):>7}"
              f"{a['ir'] / 1e6:>12,.1f}M{b['ir'] / 1e6:>12,.1f}M{fmt_ratio(ratio(a['ir'], b['ir'])):>7}"
              f"{wall_a:>9.1f}{wall_b:>9.1f}{fmt_ratio(ratio(wall_a, wall_b)):>7}  ok", flush=True)
    ok = [row for row in rows if "error" not in row]
    if ok:
        ir_geo = geomean([row["a"]["ir"] / row["b"]["ir"] for row in ok])
        build_geo = geomean([row["a"]["build_seconds"] / row["b"]["build_seconds"] for row in ok
                             if row["a"].get("build_seconds") and row["b"].get("build_seconds")])
        wall_geo = geomean([statistics.median(row["a"]["wall_seconds"]) / statistics.median(row["b"]["wall_seconds"])
                            for row in ok])
        print(f"{'geomean':<18}{'':>30}{'':>13}{'':>13}{'':>7}{'':>9}{'':>9}{'':>7}  "
              f"build {fmt_ratio(build_geo)}  Ir {fmt_ratio(ir_geo)}  wall {fmt_ratio(wall_geo)}"
              f"  ({len(ok)} projects, {against} is b)", flush=True)
        return {"ir": ir_geo, "build": build_geo, "wall": wall_geo}
    return {"ir": None, "build": None, "wall": None}


def summarize(results, baseline):
    base_projects = (baseline or {}).get("projects", {})
    ir_geo = geomean([row["ir"] / base_projects[row["name"]]["ir"] for row in results
                      if "ir" in row and base_projects.get(row["name"], {}).get("ir")])
    build_geo = geomean([row["build_seconds"] / base_projects[row["name"]]["build_seconds"] for row in results
                         if row.get("build_seconds") and base_projects.get(row["name"], {}).get("build_seconds")])
    wall_geo = geomean([statistics.median(row["wall_seconds"]) / base_projects[row["name"]]["wall_median"]
                        for row in results
                        if "wall_seconds" in row and base_projects.get(row["name"], {}).get("wall_median")])
    ok = [row for row in results if "ir" in row]
    if ok:
        comparable = [row["name"] for row in ok if base_projects.get(row["name"], {}).get("ir")]
        if comparable:
            worst = max(comparable, key=lambda name: next(
                row["ir"] for row in ok if row["name"] == name) / base_projects[name]["ir"])
            print(f"worst project: {worst} "
                  f"{fmt_ratio(next(row['ir'] for row in ok if row['name'] == worst) / base_projects[worst]['ir'])}",
                  flush=True)
    return {"ir": ir_geo, "build": build_geo, "wall": wall_geo}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tree", default=REPO, help="Minyar tree under test (default: this checkout)")
    parser.add_argument("--projects", default="/home/agent/swarm/realworld",
                        help="directory holding the read-only project copies")
    parser.add_argument("--against", help="second Minyar tree; both are built and wall samples alternate")
    parser.add_argument("--only", action="append", default=[], help="project names, comma separated")
    parser.add_argument("--json", help="write the full report here")
    parser.add_argument("--baseline", default=os.path.join(HERE, "baseline.json"))
    parser.add_argument("--write-baseline", help="record this run as the baseline")
    parser.add_argument("--repeat", type=int, default=5, help="wall samples per workload")
    parser.add_argument("--no-build", action="store_true", help="reuse existing artifacts, skip builds")
    parser.add_argument("--keep-going", action="store_true", help="record failures and continue")
    args = parser.parse_args()
    args.tree = os.path.abspath(args.tree)
    if args.against:
        args.against = os.path.abspath(args.against)
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
    other = None
    if args.against:
        other_clang = default_clang(args.against)
        other = {"tree": tree_identity(args.against, other_clang),
                 "warmup_seconds": warm_tree(args.against, other_clang, work)}
    print(f"tree {identity['path']} commit {identity['commit'][:12] or 'unknown'}"
          f"  projects {args.projects}  baseline {identity_commit(baseline)}"
          f"  warm-up {warmed:.1f}s", flush=True)
    if other:
        print(f"against {other['tree']['path']} commit {other['tree']['commit'][:12] or 'unknown'}"
              f"  warm-up {other['warmup_seconds']:.1f}s", flush=True)
    results = []
    for spec in specs:
        try:
            if args.against:
                results.append(measure_pair(spec, args, work, prepared, clang, other_clang))
            else:
                staged = stage(spec, args.tree, args, work, prepared, clang, "a")
                row = dict(staged["row"])
                row.update(run_stage(spec, staged, work, args.repeat))
                results.append(row)
        except (Failure, subprocess.CalledProcessError) as error:
            results.append({"name": spec["name"], "error": str(error)})
            if not args.keep_going:
                (print_pair if args.against else print_rows)(results, args.against or baseline)
                sys.exit(f"{spec['name']}: {error}")
    if args.against:
        print_pair(results, args.against)
        totals = pair_totals(results)
    else:
        print_rows(results, baseline)
        totals = summarize(results, baseline)
    doc = {"tree": identity, "threads": THREADS, "warmup_seconds": warmed,
           "projects_root": os.path.abspath(args.projects),
           "inputs": inputs_document(prepared),
           "geomean": totals, "projects": results}
    if other:
        doc["against"] = other["tree"]
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(doc, f, indent=1)
    if args.write_baseline:
        base = {"tree": identity, "inputs": doc["inputs"],
                "geomean": {"ir": 1.0, "build": 1.0, "wall": 1.0},
                "projects": {row["name"]: {
                    "build_seconds": row.get("build_seconds"),
                    "ir": row.get("ir"),
                    "wall_median": statistics.median(row["wall_seconds"]) if row.get("wall_seconds") else None,
                    "output_sha256": row.get("output_sha256"),
                    "commit": row.get("commit")}
                    for row in results if "ir" in row}}
        with open(args.write_baseline, "w") as f:
            json.dump(base, f, indent=1)
        print(f"wrote baseline {args.write_baseline}", flush=True)
    failed = [row for row in results if "error" in row]
    return 1 if failed else 0


def measure_pair(spec, args, work, prepared, clang, other_clang):
    """Build both trees, count instructions for both, then interleave wall samples."""
    a = stage(spec, args.tree, args, work, dict(prepared), clang, "a")
    b = stage(spec, args.against, args, work, dict(prepared), other_clang, "b")
    measured_a = run_stage(spec, a, work, 0)
    measured_b = run_stage(spec, b, work, 0)
    if spec.get("stable_output", True) and measured_a["output_sha256"] != measured_b["output_sha256"]:
        raise Failure(f"{spec['name']}: the two trees produce different workload output")
    samples, digests = wall_pair({"a": a, "b": b}, args.repeat)
    for key, measured in (("a", measured_a), ("b", measured_b)):
        if spec.get("stable_output", True) and digests[key] != measured["output_sha256"]:
            raise Failure(f"{spec['name']}: wall output differs from the counted output")
        measured["wall_seconds"] = samples[key]
    return {"name": spec["name"], "commit": a["row"].get("commit"), "a": measured_a, "b": measured_b}


def pair_totals(results):
    ok = [row for row in results if "error" not in row]
    if not ok:
        return {"ir": None, "build": None, "wall": None}
    return {"ir": geomean([row["a"]["ir"] / row["b"]["ir"] for row in ok]),
            "build": geomean([row["a"]["build_seconds"] / row["b"]["build_seconds"] for row in ok
                              if row["a"].get("build_seconds") and row["b"].get("build_seconds")]),
            "wall": geomean([statistics.median(row["a"]["wall_seconds"]) / statistics.median(row["b"]["wall_seconds"])
                             for row in ok])}


def inputs_document(prepared):
    return {"query_rows": QUERY_ROWS, "sales_sha256": file_hash(prepared["sales"]),
            "js_sha256": file_hash(prepared["js"]), "sandbox_requests": SANDBOX_REQUESTS,
            "sandbox_sha256": file_hash(prepared["requests"]),
            "sim_cases": SIM_CASES, "neo_db_rows": NEO_DB_ROWS,
            "neo_db_iterations": NEO_DB_ITERATIONS, "js_fuel": JS_FUEL,
            "sql": SQL, "sandbox_lines": SANDBOX_REQUESTS}


def identity_commit(baseline):
    if not baseline:
        return "none"
    return (baseline.get("tree", {}).get("commit") or "unknown")[:12]


if __name__ == "__main__":
    sys.exit(main())
