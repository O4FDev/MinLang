#!/usr/bin/env python3
"""Bounded control-flow programs with CFG and AST execution oracles.

The graph oracle searches explicit successor edges, including backedges. It does
not copy the compiler's block-return flags. The execution oracle separately
interprets the AST and calls only terminating generated functions. Conditions
are Boolean parameters or the literal true; this adds no language syntax.
The graph overapproximates correlated conditions and counted-loop exits. A
concrete execution witness is required before a generated rejection is asserted.
"""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def fallthrough_reachable(graph):
    edges = {int(key): list(targets) for key, targets in graph["edges"].items()}
    entry, exit_node = graph["entry"], graph["exit"]
    if entry not in edges or exit_node not in edges:
        raise ValueError("graph entry or exit target is missing")
    for targets in edges.values():
        if any(target not in edges for target in targets):
            raise ValueError("graph successor target is missing")
    pending, reached = [entry], set()
    while pending:
        node = pending.pop()
        if node == exit_node:
            return True
        if node not in reached:
            reached.add(node)
            pending.extend(edges[node])
    return False


def build_graph(statements):
    edges = {0: []}

    def node(targets=()):
        number = len(edges)
        edges[number] = list(targets)
        return number

    def block(rows, following, loop=None, depth=0):
        if depth > 32:
            raise ValueError("control nesting exceeds the model bound")
        for row in reversed(rows):
            kind = row["kind"]
            if kind == "return":
                following = node()
            elif kind in ("break", "continue"):
                if loop is None:
                    raise ValueError("loop transfer has no target")
                following = node([loop[0 if kind == "break" else 1]])
            elif kind == "if":
                then = block(row["then"], following, loop, depth + 1)
                otherwise = block(row["else"], following, loop, depth + 1)
                following = node([then, otherwise])
            elif kind in ("while", "for"):
                condition = node()
                step = node([condition]) if kind == "for" else condition
                body = block(row["body"], step, (following, step), depth + 1)
                edges[condition] = [body]
                if kind == "for" or row["condition"] != "true":
                    edges[condition].append(following)
                following = condition
            else:
                raise ValueError("unknown control statement: " + kind)
        return following

    entry = block(statements, 0)
    return {"entry": entry, "exit": 0, "edges": edges}


class Transfer(Exception):
    def __init__(self, kind, value=None):
        self.kind, self.value = kind, value


def interpret(statements, flag, max_steps=1000):
    remaining = max_steps

    def tick():
        nonlocal remaining
        remaining -= 1
        if remaining < 0:
            raise Transfer("diverges")

    def block(rows):
        for row in rows:
            tick()
            kind = row["kind"]
            if kind == "return":
                raise Transfer("return", row["value"])
            if kind in ("break", "continue"):
                raise Transfer(kind)
            if kind == "if":
                block(row["then"] if flag else row["else"])
            elif kind == "while":
                while row["condition"] == "true" or flag:
                    tick()
                    try:
                        block(row["body"])
                    except Transfer as transfer:
                        if transfer.kind == "break":
                            break
                        if transfer.kind != "continue":
                            raise
            elif kind == "for":
                for _ in range(2):
                    try:
                        block(row["body"])
                    except Transfer as transfer:
                        if transfer.kind == "break":
                            break
                        if transfer.kind != "continue":
                            raise

    try:
        block(statements)
    except Transfer as transfer:
        return {"outcome": transfer.kind, "value": transfer.value}
    return {"outcome": "fallthrough", "value": None}


def classify_case(body, graph):
    reachable = fallthrough_reachable(graph)
    outcomes = {str(flag).lower(): interpret(body, flag) for flag in (False, True)}
    witnessed = any(result["outcome"] == "fallthrough" for result in outcomes.values())
    if not reachable and witnessed:
        raise ValueError("graph and execution oracles contradict each other")
    if not reachable:
        accepted, classification = True, "graph_proves_no_fallthrough"
    elif witnessed:
        accepted, classification = False, "concrete_fallthrough"
    else:
        accepted, classification = None, "inconclusive_graph_overapproximation"
    return {"expected_accept": accepted, "classification": classification,
            "execution_oracle": outcomes}


def emit(statements):
    names = 0

    def block(rows, depth):
        nonlocal names
        lines = []
        indent = "    " * depth
        for row in rows:
            kind = row["kind"]
            if kind == "return":
                lines.append(indent + "return " + str(row["value"]))
            elif kind in ("break", "continue"):
                lines.append(indent + kind)
            elif kind == "if":
                lines += [indent + "if flag {", *block(row["then"], depth + 1),
                          indent + "} else {", *block(row["else"], depth + 1), indent + "}"]
            else:
                if kind == "for":
                    names += 1
                    head = f"for item{names} in 0..2"
                else:
                    head = "while " + row["condition"]
                lines += [indent + head + " {", *block(row["body"], depth + 1), indent + "}"]
        return lines

    return "\n".join(block(statements, 1))


def case_from_body(seed, body):
    graph = build_graph(body)
    classification = classify_case(body, graph)
    accepted, outcomes = classification["expected_accept"], classification["execution_oracle"]
    calls = [flag for flag, result in outcomes.items()
             if accepted is not False and result["outcome"] == "return"]
    marker = seed & 0x7FFFFFFF
    source = "function value(flag: Boolean): Integer {\n" + emit(body) + "\n}\n"
    source += f"print({marker})\n" + "".join(f"print(value({flag}))\n" for flag in calls)
    expected = str(marker) + "\n" + "".join(str(outcomes[flag]["value"]) + "\n" for flag in calls)
    return {"seed": seed, "body": body, "graph": graph, **classification,
            "calls": calls, "source": source,
            "expected_stdout": expected, "source_sha256": hashlib.sha256(source.encode()).hexdigest()}


def generate_case(seed, node_budget=32):
    if type(node_budget) is not int or not 1 <= node_budget <= 256:
        raise ValueError("node budget must be between 1 and 256")
    rng = random.Random(seed)
    remaining = node_budget

    def forest(depth=0, loop_depth=0):
        nonlocal remaining
        result = []
        for _ in range(rng.randrange(4 if depth == 0 else 3)):
            if not remaining:
                break
            remaining -= 1
            choices = ["return", "if", "if", "while", "while", "for"]
            if loop_depth:
                choices += ["break", "continue"]
            if depth >= 5:
                choices = ["return", *(["break", "continue"] if loop_depth else [])]
            kind = rng.choice(choices)
            row = {"kind": kind}
            if kind == "return":
                row["value"] = rng.randint(-500, 500)
            elif kind == "if":
                row.update(then=forest(depth + 1, loop_depth),
                           **{"else": forest(depth + 1, loop_depth)})
            elif kind in ("while", "for"):
                row.update(condition=rng.choice(["true", "true", "flag"]),
                           body=forest(depth + 1, loop_depth + 1))
            result.append(row)
        return result

    body = forest()
    if remaining and rng.choice([False, True]):
        body.append({"kind": "return", "value": rng.randint(-500, 500)})
    return case_from_body(seed, body)


def run_command(command, *, timeout):
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=os.name != "nt")
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        stdout, stderr = process.communicate(timeout=10)
        raise subprocess.TimeoutExpired(command, timeout, stdout, stderr)
    return subprocess.CompletedProcess(command, process.returncode,
                                       stdout.decode("utf-8", errors="backslashreplace"),
                                       stderr.decode("utf-8", errors="backslashreplace"))


def verify_case(case, directory, compiler, runtime, clang, *, runner=run_command):
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "case.min"
    source.write_text(case["source"], encoding="utf-8")
    source.with_suffix(".expected.stdout").write_text(case["expected_stdout"], encoding="utf-8")
    llvm = source.with_suffix(".ll")
    report = {"status": "passed", "source": str(source), "commands": []}

    def execute(command, timeout):
        started = time.monotonic()
        try:
            result = runner(command, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            report["commands"].append({"command": command, "timeout_seconds": timeout,
                                       "elapsed_seconds": time.monotonic() - started,
                                       "status": None, "timed_out": True,
                                       "stdout": repr(error.stdout), "stderr": repr(error.stderr)})
            raise
        except OSError as error:
            report["commands"].append({"command": command, "timeout_seconds": timeout,
                                       "elapsed_seconds": time.monotonic() - started,
                                       "status": None, "timed_out": False,
                                       "infrastructure_error": str(error)})
            raise
        report["commands"].append({"command": command, "timeout_seconds": timeout,
                                   "elapsed_seconds": time.monotonic() - started,
                                   "status": result.returncode, "timed_out": False,
                                   "stdout": result.stdout, "stderr": result.stderr})
        return result

    def fail(kind):
        report.update(status="failed", failure=kind)
        return report

    try:
        compiled = execute([str(compiler), str(source), str(llvm)], 10)
        if compiled.returncode == 1:
            if llvm.exists():
                return fail("rejected_source_left_output")
            if "must return a value on every path" not in compiled.stderr:
                return fail("invalid_diagnostic")
            if case["expected_accept"] is True:
                return fail("unexpected_reject")
            return report
        if compiled.returncode != 0:
            return fail("compiler_process_failure")
        if case["expected_accept"] is False:
            return fail("unexpected_accept")
        if not llvm.exists():
            return fail("missing_llvm_output")
        if compiled.stdout or compiled.stderr:
            return fail("unexpected_compiler_output")
        flags = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))
        math_flags = [] if os.name == "nt" else ["-lm"]
        for optimization in ("-O0", "-O2"):
            executable = directory / (optimization[1:] + (".exe" if os.name == "nt" else ""))
            linked = execute([clang, optimization, *flags, "-Wno-override-module",
                              str(llvm), str(runtime), *math_flags, "-o", str(executable)], 30)
            if linked.returncode != 0:
                return fail("llvm_or_link_failure")
            executed = execute([str(executable)], 10)
            if executed.returncode != 0:
                return fail("native_process_failure")
            if executed.stdout != case["expected_stdout"] or executed.stderr:
                return fail("native_output_mismatch")
    except subprocess.TimeoutExpired:
        report.update(status="timeout", failure="process_timeout")
    except OSError:
        report.update(status="infrastructure_error", failure="process_setup")
    return report


def simplifications(body):
    def blocks(rows, path=()):
        yield path, rows
        for index, row in enumerate(rows):
            for field in ("then", "else", "body"):
                if field in row:
                    yield from blocks(row[field], (*path, index, field))

    for path, rows in blocks(body):
        for index, row in enumerate(rows):
            replacements = [[]] + [row[field] for field in ("then", "else", "body")
                                    if field in row]
            for replacement in replacements:
                candidate = copy.deepcopy(body)
                target = candidate
                for part in path:
                    target = target[part]
                target[index:index + 1] = copy.deepcopy(replacement)
                try:
                    build_graph(candidate)
                except ValueError:
                    continue
                yield candidate


def minimize_body(body, retains_failure, *, max_attempts=64):
    candidate, attempts = copy.deepcopy(body), 0
    while attempts < max_attempts:
        reduced = False
        for smaller in simplifications(candidate):
            if attempts >= max_attempts:
                break
            attempts += 1
            if retains_failure(smaller):
                candidate, reduced = smaller, True
                break
        if not reduced:
            break
    return candidate, attempts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=lambda text: int(text, 0), default=0x435447)
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--nodes", type=int, default=32)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/peer-research/control")
    parser.add_argument("--execute", action="store_true", help="Compile and check generated cases serially")
    parser.add_argument("--compiler", type=Path,
                        default=Path(os.environ.get("MINYAR_TEST_COMPILER", ROOT / "build/minyarc")))
    parser.add_argument("--runtime", type=Path,
                        default=Path(os.environ.get("MINYAR_TEST_RUNTIME", ROOT / "build/minyar-runtime.o")))
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", "clang"))
    parser.add_argument("--minimize-attempts", type=int, default=64)
    args = parser.parse_args()
    if not 1 <= args.count <= 10000 or not 1 <= args.nodes <= 256 or not 0 <= args.minimize_attempts <= 256:
        parser.error("count 1..10000, nodes 1..256 and minimize attempts 0..256 required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="generated-", dir=args.output_dir)).resolve()
    cases = [generate_case(args.seed + number, args.nodes) for number in range(args.count)]
    for number, case in enumerate(cases):
        (work / f"case-{number}.min").write_text(case["source"])
    report = {"status": "generated_not_executed", "scope": __doc__, "cases": cases,
              "started_utc": datetime.now(timezone.utc).isoformat(), "execution": []}
    report_path = work / "results.json"

    def save():
        temporary = report_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(report_path)

    save()
    if not args.execute:
        print(f"Generated {len(cases)} bounded cases; no compiler execution: {work}")
        return
    args.compiler, args.runtime = args.compiler.resolve(), args.runtime.resolve()
    if not args.compiler.is_file() or not args.runtime.is_file():
        parser.error("execution requires existing compiler and runtime files")
    sources = [Path(__file__), args.compiler, args.runtime,
               ROOT / "compiler/compiler.min", ROOT / "bootstrap/stage0.c", *sorted((ROOT / "runtime").glob("*.[ch]"))]
    report["source_hashes_start"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    report["environment"] = {key: value for key, value in os.environ.items()
                             if key.startswith("MINYAR_") or key in ("CC", "CLANG", "LLVM_OPT")}
    report["status"] = "running"
    save()
    for number, case in enumerate(cases):
        result = verify_case(case, work / f"executed-{number}", args.compiler, args.runtime, args.clang)
        report["execution"].append(result)
        save()
        if result["status"] != "passed":
            if result["status"] in ("timeout", "infrastructure_error"):
                # Scheduling failures are retained, without spending repeated
                # timeouts trying to minimize a supposed semantic failure.
                break
            original_kind = result["failure"]
            reductions = []
            def retains_failure(body):
                smaller = case_from_body(case["seed"], body)
                if smaller["expected_accept"] != case["expected_accept"]:
                    return False
                trial = verify_case(smaller, work / f"reduce-{len(reductions)}",
                                    args.compiler, args.runtime, args.clang)
                reductions.append(trial)
                return trial["status"] == result["status"] and trial.get("failure") == original_kind
            body, attempts = minimize_body(case["body"], retains_failure,
                                           max_attempts=args.minimize_attempts)
            report["minimized"] = {"case": case_from_body(case["seed"], body),
                                   "attempts": attempts, "execution": reductions}
            (work / "minimized.min").write_text(report["minimized"]["case"]["source"], encoding="utf-8")
            break
    report["source_hashes_end"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    report["changed_sources_during_run"] = [path for path, digest in report["source_hashes_start"].items()
                                           if report["source_hashes_end"][path] != digest]
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    report["status"] = "passed" if len(report["execution"]) == len(cases) and all(
        result["status"] == "passed" for result in report["execution"]) else "failed"
    if report["execution"][-1]["status"] in ("timeout", "infrastructure_error"):
        report["status"] = "incomplete"
    if report["changed_sources_during_run"]:
        report["status"] = "source_changed"
    save()
    print(f"Control-flow campaign {report['status']}: {len(report['execution'])}/{len(cases)} cases; {work}")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
