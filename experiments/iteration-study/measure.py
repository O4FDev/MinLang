#!/usr/bin/env python3
"""Run only through bx; preserve dynamic scalar-pipeline codegen evidence."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

if sys.platform != "linux":
    raise SystemExit("Run this measurement only through bx on Linux.")

parser = argparse.ArgumentParser()
parser.add_argument("--build", action="store_true", help="Build once on this remote box before measuring")
parser.add_argument("--scope-owners", action="store_true", help="Compile this study with scope ownership lowering")
parser.add_argument("--output", type=Path, metavar="DIR", help="Artifact directory (default: build/iteration-study, or build/iteration-study-scope with --scope-owners)")
args = parser.parse_args()
out = args.output if args.output is not None else Path("build/iteration-study-scope" if args.scope_owners else "build/iteration-study")
out.mkdir(parents=True, exist_ok=True)
source = Path("experiments/iteration-study/scalar.min")
shutil.copyfile(source, out / "source.min")
commands = []


def run(command, stem, *, required=True, timeout=120):
    command = [str(part) for part in command]
    commands.append(shlex.join(command))
    (out / "commands.log").write_text("\n".join(commands) + "\n")
    result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    (out / (stem + ".stdout")).write_text(result.stdout)
    (out / (stem + ".stderr")).write_text(result.stderr)
    (out / (stem + ".status")).write_text(str(result.returncode) + "\n")
    if required and result.returncode:
        raise SystemExit(f"Failed ({result.returncode}): {shlex.join(command)}\n{result.stderr}")
    return result


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if args.build:
    run(["make", "-j8", "build/minyarc", "build/minyar-runtime.o"], "build", timeout=600)
if not Path("build/minyarc").is_file() or not Path("build/minyar-runtime.o").is_file():
    raise SystemExit("Build artifacts are absent; rerun through bx with --build.")

compiler_sha256 = sha256_file(Path("build/minyarc"))
source_sha256 = sha256_file(source)
clang = run(["sh", "tools/toolchain.sh", "default-clang"], "compiler-path").stdout.strip()
version = run([clang, "--version"], "clang-version").stdout.strip()
compile_command = ["./build/minyarc", source, out / "scalar.raw.ll", "--library", "library"]
if args.scope_owners:
    compile_command.append("--scope-owners")
run(compile_command, "compile")
run([clang, "-O2", "-S", "-emit-llvm", "-Wno-override-module", out / "scalar.raw.ll", "-o", out / "scalar.O2.ll"], "optimize")
run([clang, "-O2", "-S", "-Wno-override-module", out / "scalar.raw.ll", "-o", out / "scalar.O2.s"], "assembly")
run([clang, "-O2", "-Wno-override-module", out / "scalar.raw.ll", "build/minyar-runtime.o", "-lm", "-o", out / "scalar"], "link")
runs = []
for number, arguments in enumerate([[], ["a", "b", "c"]]):
    result = run([(out / "scalar").resolve(), *arguments], "run-" + str(number))
    lines = result.stdout.splitlines()
    if len(lines) != 2 or lines[0] != lines[1]:
        raise SystemExit("Fused/handwritten output differs: " + repr(result.stdout))
    runs.append({"arguments": arguments, "stdout": result.stdout, "status": result.returncode})

# This probes only counter availability. It does not measure either loop.
perf = shutil.which("perf")
if perf:
    result = run([perf, "stat", "-e", "instructions:u", "--", "true"], "perf-probe", required=False)
    perf_result = {"available": result.returncode == 0, "status": result.returncode, "diagnostic": result.stderr}
else:
    perf_result = {"available": False, "diagnostic": "perf is not installed"}

symbol = r'("(?:[^"\\]|\\.)*"|[-A-Za-z$._0-9]+)'
function_pattern = re.compile(r'^define\b[^\n]*@' + symbol + r'\([^\n]*\)[^\n]*\{\n(.*?)^\}', re.M | re.S)
call_pattern = re.compile(r'\b(?:call|invoke)\b[^@\n]*@' + symbol + r'\(')
label_pattern = re.compile(r'^([-A-Za-z$._0-9]+):')


def count(lines):
    instructions = [line for line in lines if line.strip() and not line.lstrip().startswith(";")]
    calls = Counter()
    indirect = 0
    for line in instructions:
        if not re.search(r'\b(?:call|invoke)\b', line):
            continue
        match = call_pattern.search(line)
        if match:
            calls[match.group(1).strip('"')] += 1
        elif re.search(r'\b(?:call|invoke)\b[^\n]*%[-A-Za-z$._0-9]+\(', line):
            indirect += 1
    return {"instruction_lines": len(instructions), "direct_call_sites": dict(sorted(calls.items())), "indirect_call_sites": indirect}


def natural_loops(blocks):
    labels = list(blocks)
    if not labels:
        return []
    successors = {name: set(re.findall(r'\blabel %([-A-Za-z$._0-9]+)', "\n".join(lines))) & blocks.keys() for name, lines in blocks.items()}
    predecessors = defaultdict(set)
    for name, after in successors.items():
        for target in after:
            predecessors[target].add(name)
    reachable = set()
    pending = [labels[0]]
    while pending:
        name = pending.pop()
        if name not in reachable:
            reachable.add(name)
            pending.extend(successors[name])
    entry = labels[0]
    dominators = {name: ({name} if name == entry else set(reachable)) for name in reachable}
    changed = True
    while changed:
        changed = False
        for name in reachable - {entry}:
            before = predecessors[name] & reachable
            shared = set.intersection(*(dominators[p] for p in before)) if before else set()
            updated = {name} | shared
            if updated != dominators[name]:
                dominators[name] = updated
                changed = True
    loops = defaultdict(set)
    for tail in reachable:
        for head in successors[tail]:
            if head not in dominators[tail]:
                continue
            nodes = {head, tail}
            pending = [] if head == tail else [tail]
            while pending:
                name = pending.pop()
                for before in predecessors[name] & reachable:
                    if before not in nodes:
                        nodes.add(before)
                        pending.append(before)
            if any(head not in dominators[name] for name in nodes):
                raise ValueError("Natural-loop member is not dominated by its header: " + head)
            loops[head].update(nodes)
    return [{"header": head, "blocks": [name for name in labels if name in nodes], **count([line for name in labels if name in nodes for line in blocks[name]])} for head, nodes in loops.items()]


def generated_name(name):
    prefix = ".minyar.fn."
    return name[len(prefix):] if name.startswith(prefix) else name


def extract(path, tag):
    text = path.read_text()
    selected = {}
    all_names = []
    for match in function_pattern.finditer(text):
        name, body = match.groups()
        name = name.strip('"')
        all_names.append(name)
        if not ("|fused|" in name or "|handwritten|" in name or name.endswith("_fused") or name.endswith("_handwritten") or name in {"fused", "handwritten"} or generated_name(name).startswith("minyar_sequence_fold_")):
            continue
        blocks = {}
        current = "entry"
        for line in body.splitlines():
            label = label_pattern.match(line)
            if label:
                current = label.group(1)
                blocks.setdefault(current, [])
            else:
                blocks.setdefault(current, []).append(line)
        key = "handwritten" if "handwritten" in name else "fused" if "fused" in name else name
        (out / (key + "." + tag + ".ll")).write_text(match.group(0) + "\n")
        selected[name] = {"whole_function": count([line for lines in blocks.values() for line in lines]), "natural_loops": natural_loops(blocks)}
    return {"selected_functions": selected, "apply_wrapper_definitions": [name for name in all_names if generated_name(name).startswith("minyar_sequence_") and name.endswith("_apply")]}


summary = {
    "cwd": os.getcwd(),
    "clang": version,
    "fixture": str(source),
    "ownership_mode": "scope-owners" if args.scope_owners else "legacy",
    "output": str(out),
    "compiler": "./build/minyarc",
    "compiler_sha256": compiler_sha256,
    "source_sha256": source_sha256,
    "runs": runs,
    "perf_probe": perf_result,
    "raw": extract(out / "scalar.raw.ll", "raw"),
    "O2": extract(out / "scalar.O2.ll", "O2"),
    "limits": [
        "Instruction and call counts are static IR sites, not retired instructions or runtime timings.",
        "Natural-loop sets include conditional blocks, so one call site need not run for every item.",
        "The full program prints both variants; no whole-process performance comparison is claimed.",
        "The existing runtime object is linked separately; no LTO elimination of opaque runtime calls is assumed.",
        "The ownership mode records the requested lowering; conservative function fallbacks may retain legacy ownership calls.",
    ],
}
(out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
report = ["# Scalar sequence codegen study", "", "```text", version, "```", "", "Source:", "", "```minyar", source.read_text().rstrip(), "```", "", "Commands:", "", "```sh", "\n".join(commands), "```", "", "Results:", "", "```json", json.dumps(summary, indent=2), "```", ""]
(out / "summary.md").write_text("\n".join(report))
print(json.dumps(summary, indent=2))
print("Artifacts: " + str(out.resolve()))
