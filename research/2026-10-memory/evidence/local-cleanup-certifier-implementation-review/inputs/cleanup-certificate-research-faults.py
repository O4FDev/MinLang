"""Generate separate checker defects; run unchanged expectations serially.

This tool mutates checker source, never LLVM execution or oracle expectations.
Seven preregistered fault families must each produce an actual failing test.
"""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/2026-10-memory/evidence/local-cleanup-certifier-prototype"
SOURCE = ROOT / "tests/cleanup-certificate-research.py"
TESTS = ROOT / "tests/cleanup-certificate-research-tests.py"
BASE = SOURCE.read_text()
FIXTURE_PATH = ROOT / "research/2026-10-memory/evidence/local-cleanup-certifier-design"


def replace_once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def mutants():
    pure = replace_once(BASE, "def borrower(fn, summaries):\n", "def borrower(fn, summaries):\n    return dict(requirements={}, effects=[], return_tag=TOP, may_terminate=False, has_guard_effect=False, loops=[], dataflow={})\n")
    double = replace_once(BASE, 'if gen["sealed"]:\n                    fail("producer_token_already_transferred", ins.site)',
                          'if gen["sealed"]:\n                    pass  # deliberately permit duplicate transfer')
    # Ignore a frame detachment specifically in a continuing cyclic block, at
    # both borrower effect classification and the loop-neutrality gate.
    cyclic = replace_once(BASE, "def borrower(fn, summaries):\n", "def borrower(fn, summaries):\n    ignored = {id(i) for b, block in fn.blocks.items() for i in block if i.target == 'minyar_rc_step' and any(t in fn.dominators[b] for t in fn.successors[b])}\n")
    cyclic = replace_once(cyclic, "for b, block in fn.blocks.items():\n        for ins in block:\n            if ins.op == \"store\"", "for b, block in fn.blocks.items():\n        for ins in block:\n            if id(ins) in ignored:\n                continue\n            if ins.op == \"store\"")
    cyclic = replace_once(cyclic, 'if ins.op == "call":\n                if ins.target in summaries:', 'if ins.op == "call":\n                if ins.target == "minyar_rc_step":\n                    continue\n                if ins.target in summaries:')
    cyclic = replace_once(cyclic, 'hblock, lblock = fn.blocks[header], fn.blocks[latch]', 'hblock, lblock = fn.blocks[header], [i for i in fn.blocks[latch] if i.target != "minyar_rc_step"]')
    cyclic = replace_once(cyclic, 'if ins.op != "call":\n                continue\n            if ins.target == "minyar_stack_leave"', 'if ins.op != "call" or ins.target == "minyar_rc_step":\n                continue\n            if ins.target == "minyar_stack_leave"')
    finalizers = replace_once(BASE, 'visits, finalizers = sum(map(len, chunks)), len(chunks) + 1', 'visits, finalizers = sum(map(len, chunks)), 0')
    elements = replace_once(BASE, 'visits, finalizers = sum(map(len, chunks)), len(chunks) + 1', 'visits, finalizers = sum(g["length"] for g in generations.values()), len(chunks) + 1')
    polls = replace_once(BASE, 'work = visits + finalizers', 'work = max(0, visits + finalizers - 32)  # deliberately subtract automatic poll budget')
    bypass = BASE + "\n_original_analyze = analyze\ndef analyze(ir, entry, **options):\n    if entry == '.minyar.fn.minyar_module_1_snow':\n        return json.loads(Path(" + repr(str(EVIDENCE / "actual-certificate.json")) + ").read_text())\n    return _original_analyze(ir, entry, **options)\n"
    return dict(assume_application_pure=pure, duplicate_keep=double,
                ignore_backedge_effect=cyclic, omit_finalizers=finalizers,
                count_scalar_elements=elements, subtract_polls=polls,
                original_name_bypass=bypass)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fault", choices=list(mutants()))
    parser.add_argument("--collect", action="store_true", help="collect already completed bounded worker evidence")
    parser.add_argument("--label-prefix", default="fault")
    args = parser.parse_args()
    directory = EVIDENCE / "faults"
    directory.mkdir(exist_ok=True)
    records = []
    targets = dict(assume_application_pure=("callee_effect", "put_rc_leave"),
        duplicate_keep=("N_double_keep", "duplicate"),
        ignore_backedge_effect=("N_loop_effect", "backedge_step"),
        omit_finalizers=("M_owner8", "independent"),
        count_scalar_elements=("M_payload", "independent_length5"),
        subtract_polls=("P_actual", "archived"),
        original_name_bypass=("N_early_step", "before_pick"))
    test_hash = hashlib.sha256(TESTS.read_bytes()).hexdigest()
    for name, source in mutants().items():
        if name != args.fault:
            continue
        # Relocate archived copies without changing their reviewed source input.
        source = replace_once(source, 'DESIGN = Path(__file__).resolve().parents[1] / "research/2026-10-memory/evidence/local-cleanup-certifier-design"',
                              "DESIGN = Path(" + repr(str(FIXTURE_PATH)) + ")")
        path = directory / (name + ".py")
        path.write_text(source)
        label = args.label_prefix + "-" + name
        command = [sys.executable, str(ROOT / "tests/cleanup-certificate-research-run.py"),
                   label, "--checker", str(path)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30) if not args.collect else None
        gate = json.loads((EVIDENCE / (label + ".json")).read_text())
        result = json.loads((EVIDENCE / (label + ".log")).read_text())
        failures = [r for r in result["results"] if not r["passed"]]
        target = next(r for r in result["results"] if (r["record"], r["variant"]) == targets[name])
        # Error text embeds certificates for wrongly accepted negatives. Numeric
        # wrong-answer cases also calibrate finalizers/elements/poll defects.
        record = dict(fault=name, mutant_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      unchanged_tests_sha256=test_hash, command=command,
                      returncode=gate["returncode"], gate=gate,
                      failed_cases=[dict(record=r["record"], variant=r["variant"], error=r["error"])
                                    for r in failures], failed_count=len(failures),
                      semantic_target=target,
                      calibrated=not target["passed"] and target["observed_status"] == "conditional_component_certificate"
                          and gate["returncode"] == 1 and gate["violation"] is None)
        records.append(record)
        print(name, "calibrated=" + str(record["calibrated"]), "failed=" + str(len(failures)), flush=True)
        if hashlib.sha256(TESTS.read_bytes()).hexdigest() != test_hash:
            raise RuntimeError("expectations changed during calibration")
    (EVIDENCE / (args.label_prefix + "-calibration-" + args.fault + ".json")).write_text(json.dumps(records[0], indent=2) + "\n")
    return 0 if all(r["calibrated"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
