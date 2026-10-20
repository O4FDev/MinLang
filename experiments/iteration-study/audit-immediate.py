#!/usr/bin/env python3
"""Audit saved immediate-for IR; does not compile, link, or measure a program."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path, help="Completed --output study directory")
parser.add_argument("--expect-setup-records", type=int, choices=[0, 2], required=True)
args = parser.parse_args()


def require(condition, message):
    if not condition:
        raise SystemExit(message)


symbol = r'("(?:[^"\\]|\\.)*"|[-A-Za-z$._0-9]+)'
function_pattern = re.compile(r'^define\b[^\n]*@' + symbol + r'\([^\n]*\)[^\n]*\{\n(.*?)^\}', re.M | re.S)
call_pattern = re.compile(r'\b(?:call|invoke)\b[^@\n]*@' + symbol + r'\(')
factory_pattern = re.compile(r'minyar_sequence_(?:map|filter)_\d+_make(?:$|\|)')


def calls(body):
    result = Counter()
    for line in body.splitlines():
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        match = call_pattern.search(line)
        if match:
            result[match.group(1).strip('"')] += 1
    return result


def record_sites(direct):
    return sum(count for name, count in direct.items() if name.startswith("minyar_record_new"))


def setup_sites(direct, definitions):
    factories = {}
    through_factories = 0
    for name, count in direct.items():
        if not factory_pattern.search(name):
            continue
        require(name in definitions, "Missing called recipe factory body: " + name)
        body_calls = calls(definitions[name])
        require(not any(factory_pattern.search(target) for target in body_calls), "Unexpected nested factory body: " + name)
        sites = record_sites(body_calls)
        require(sites == 1, "A called one-source recipe factory must contain one record allocation site: " + name)
        factories[name] = {"call_sites": count, "record_sites_per_factory": sites}
        through_factories += count * sites
    direct_records = record_sites(direct)
    return {
        "direct_record_allocation_sites": direct_records,
        "called_recipe_factories": factories,
        "record_sites_in_called_factories": through_factories,
        "accounted_record_allocation_sites": direct_records + through_factories,
    }


def named(name, wanted):
    return f"|{wanted}|" in name or name.endswith("_" + wanted) or name in {wanted, ".minyar.fn." + wanted}


summary = json.loads((args.directory / "summary.json").read_text())
source_hash = hashlib.sha256((args.directory / "source.min").read_bytes()).hexdigest()
require(summary.get("source_sha256") == source_hash, "Saved fixture differs from its recorded source hash")
require(summary.get("ownership_mode") in {"legacy", "scope-owners"}, "Missing explicit ownership mode")
expected_runs = [([], "3104\n3104\n"), (["a", "b", "c"], "3300\n3300\n")]
require(len(summary["runs"]) == 2, "Immediate fixture needs exactly two dynamic inputs")
for observed, (arguments, output) in zip(summary["runs"], expected_runs):
    require(observed["arguments"] == arguments and observed["stdout"] == output and observed["status"] == 0,
            "Immediate fixture changed its 64/process-argument output oracle")

report = {
    "ownership_mode": summary["ownership_mode"],
    "compiler_sha256": summary["compiler_sha256"],
    "source_sha256": source_hash,
    "expected_fused_setup_record_sites": args.expect_setup_records,
    "counts": {},
    "limits": [
        "All counts are static instruction/call sites, not runtime allocation counts or retired instructions.",
        "A called one-record factory site is charged its one allocation site; uncalled definitions are not charged.",
        "The existing whole-function and natural-loop call maps are retained without filtering scope operations.",
    ],
}
for tag, filename in [("raw", "scalar.raw.ll"), ("O2", "scalar.O2.ll")]:
    llvm = (args.directory / filename).read_text()
    definitions = {}
    for function in function_pattern.finditer(llvm):
        name = function.group(1).strip('"')
        require(name not in definitions, "Duplicate LLVM definition: " + name)
        definitions[name] = function.group(2)
    selected = summary[tag]["selected_functions"]
    result = {}
    for wanted in ["fused", "handwritten"]:
        names = [name for name in selected if named(name, wanted)]
        require(len(names) == 1, f"{tag}: extractor must capture exactly one {wanted} function")
        name = names[0]
        require(name in definitions, f"{tag}: selected function body is missing: {name}")
        evidence = selected[name]
        require(dict(calls(definitions[name])) == evidence["whole_function"]["direct_call_sites"],
                f"{tag}: whole-body call map differs from the actual {wanted} IR")
        require(evidence["whole_function"]["indirect_call_sites"] == 0, f"{tag}: indirect scalar dispatch in {wanted}")
        require(len(evidence["natural_loops"]) == 1, f"{tag}: {wanted} must expose its one dynamic traversal")
        whole = setup_sites(evidence["whole_function"]["direct_call_sites"], definitions)
        expected = args.expect_setup_records if wanted == "fused" else 0
        require(whole["accounted_record_allocation_sites"] == expected,
                f"{tag}: {wanted} whole-body setup record sites differ from {expected}")
        loop_sites = []
        for loop in evidence["natural_loops"]:
            require(loop["indirect_call_sites"] == 0, f"{tag}: indirect call in {wanted} loop")
            loop_setup = setup_sites(loop["direct_call_sites"], definitions)
            require(loop_setup["accounted_record_allocation_sites"] == 0,
                    f"{tag}: {wanted} allocated a recipe record inside its traversal")
            loop_sites.append({"header": loop["header"], **loop_setup})
        if tag == "raw":
            for target in ["shifted", "selected", "combined"]:
                sites = sum(count for callee, count in evidence["whole_function"]["direct_call_sites"].items() if named(callee, target))
                require(sites == 1, f"raw: {wanted} must call original {target} once statically")
        result[wanted] = {
            "symbol": name,
            "whole_function": evidence["whole_function"],
            "natural_loops": evidence["natural_loops"],
            "whole_body_setup": whole,
            "loop_setup": loop_sites,
        }
    report["counts"][tag] = result

destination = args.directory / "setup-sites.json"
destination.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
print("Setup-site audit: " + str(destination.resolve()))
