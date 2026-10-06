"""Independent semantic expectations, authored before the checker.

The historical expected-derivation is an oracle document, never checker input.
Run via cleanup-certificate-research-run.py for bounded serial evidence.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "research/2026-10-memory/evidence/local-cleanup-certifier-design"
REAL = (DESIGN / "inputs/application/application.ll").read_text()
ENTRY = ".minyar.fn.minyar_module_1_snow"
PICK = ".minyar.fn.minyar_module_1_pick"
GET = ".minyar.list.get.checked"


def body_change(ir, symbol, old, new):
    # Fixture construction only; the analyzer must tokenize and reconstruct CFG.
    pattern = r"define[^\n]*@" + re.escape(symbol) + r"\([^\n]*\) [^{]*\{\n.*?^\}"
    match = re.search(pattern, ir, re.M | re.S)
    assert match, symbol
    body = match.group()
    assert body.count(old) == 1, (symbol, old, body.count(old))
    return ir[:match.start()] + body.replace(old, new) + ir[match.end():]


def root_change(old, new):
    return body_change(REAL, ENTRY, old, new)


DECL = """declare void @minyar_stack_enter()
declare void @minyar_stack_leave()
declare void @minyar_rc_enter(i64)
declare void @minyar_rc_leave()
declare void @minyar_rc_step()
declare void @minyar_rc_keep(ptr)
declare ptr @minyar_list_new()
declare void @minyar_list_add(ptr, i64)
"""


def owners(n, length=1):
    lines = [DECL, "define void @component() {", "start:",
             "call void @minyar_stack_enter()", "call void @minyar_rc_enter(i64 0)"]
    for i in range(n):
        lines.append(f"%owner{i} = call ptr @minyar_list_new()")
        lines.extend(f"call void @minyar_list_add(ptr %owner{i}, i64 {j - 7})"
                     for j in range(length))
        lines.append(f"call void @minyar_rc_keep(ptr %owner{i})")
    lines += ["call void @minyar_rc_step()", "call void @minyar_rc_leave()",
              "call void @minyar_stack_leave()", "ret void", "}"]
    return "\n".join(lines)


def cases():
    rows = []

    def add(record, variant, ir=REAL, expected="rejected", entry=ENTRY, **options):
        rows.append(dict(record=record, variant=variant, ir=ir, expected=expected,
                         entry=entry, options=options))

    add("P_actual", "archived", expected=4)
    # All app/helper names and all local/block identifiers, including references.
    names = re.findall(r"define[^\n]*@([\w.]+)\(", REAL)
    rename = {name: f"app{index}" for index, name in enumerate(names)}
    renamed = re.sub(r"@([\w.]+)", lambda m: "@" + rename.get(m[1], m[1]), REAL)
    local_names = sorted(set(re.findall(r"%([\w.]+)", renamed) +
                             re.findall(r"^([\w.]+):", renamed, re.M)))
    local_map = {name: f"id{i}" for i, name in enumerate(local_names)}
    renamed = re.sub(r"%([\w.]+)", lambda m: "%" + local_map[m[1]], renamed)
    renamed = re.sub(r"^([\w.]+):", lambda m: local_map[m[1]] + ":", renamed, flags=re.M)
    renamed = renamed.replace("  ", " \t ").replace("\n", " ; fixture comment\n")
    add("M_rename", "all_identifiers_comments_spacing", renamed, 4, rename[ENTRY])
    extra = "%third = call ptr @minyar_list_new()\ncall void @minyar_list_add(ptr %third, i64 -42)\ncall void @minyar_rc_keep(ptr %third)\n"
    add("M_owner3", "real_plus_owner", root_change("  call void @minyar_rc_step()", extra + "  call void @minyar_rc_step()"), 5)
    for n, work in [(3, 5), (8, 10), (9, 12)]:
        add(f"M_owner{n}", "independent", owners(n), work, "component")
    for length in [0, 2, 5, 33]:
        add("M_payload", f"independent_length{length}", owners(2, length), 4, "component")
    add("M_payload", "real_literals", REAL.replace("15793661", "-981").replace("2.4e-1", "1.2e-2"), 4)
    add("M_payload", "real_extra_scalar", root_change("  call void @minyar_rc_keep(ptr %value.1)", "  call void @minyar_list_add(ptr %value.1, i64 22)\n  call void @minyar_rc_keep(ptr %value.1)"), 4)
    add("M_leave_only", "no_step", root_change("  call void @minyar_rc_step()\n", ""), 4)
    add("N_double_keep", "duplicate", root_change("  call void @minyar_rc_keep(ptr %value.1)", "  call void @minyar_rc_keep(ptr %value.1)\n  call void @minyar_rc_keep(ptr %value.1)"))
    add("N_missing_keep", "missing", root_change("  call void @minyar_rc_keep(ptr %value.2)\n", ""))
    add("N_external_keep", "borrowed_bytes", root_change("  call void @minyar_rc_step()", "  call void @minyar_rc_keep(ptr %argument.0)\n  call void @minyar_rc_step()"))
    for args, decl in [("", ""), ("ptr %value.1", "ptr")]:
        add("N_unknown_call", "zero_arguments" if not args else "pointer", "declare void @opaque(" + decl + ")\n" + root_change("  call void @minyar_rc_step()", "  call void @opaque(" + args + ")\n  call void @minyar_rc_step()"))
    for op in ["retain", "borrow", "release", "poll"]:
        arg = "" if op == "poll" else "ptr %value.1"
        declaration = "declare void @minyar_rc_" + op + "(" + ("" if op == "poll" else "ptr") + ")\n" if op in ["release", "poll"] else ""
        add("N_retain_release", op, declaration + root_change("  call void @minyar_rc_step()", f"  call void @minyar_rc_{op}({arg})\n  call void @minyar_rc_step()"))
    for op in ["references", "add_take"]:
        args = "ptr %value.1" + (", i64 0" if op == "add_take" else "")
        add("N_reference", op, root_change("  call void @minyar_rc_keep(ptr %value.1)", f"  call void @minyar_list_{op}({args})\n  call void @minyar_rc_keep(ptr %value.1)"))
    for rec, val in [("N_fresh_return", "%value.1"), ("N_external_return", "%argument.0")]:
        ir = root_change("  ret void", f"  ret ptr {val}")
        ir = ir.replace("define void @" + ENTRY, "define ptr @" + ENTRY)
        if rec == "N_external_return":
            ir = body_change(ir, ENTRY, "  call void @minyar_rc_leave()", "  call void @minyar_rc_retain(ptr %argument.0)\n  call void @minyar_rc_leave()")
        add(rec, "pointer_return", ir)
    for variant, instruction in [
            ("global", "store ptr %value.1, ptr @export"),
            ("scalar_cell", "%cell = alloca i64\nstore ptr %value.1, ptr %cell"),
            ("ptrtoint_cell", "%cell = alloca i64\n%erased = ptrtoint ptr %value.1 to i64\nstore i64 %erased, ptr %cell"),
            ("ptrtoint_list", "%erased = ptrtoint ptr %value.1 to i64\ncall void @minyar_list_add(ptr %value.2, i64 %erased)"),
            ("inttoptr", "%forged = inttoptr i64 4 to ptr"),
            ("bitcast_ptr", "%forged = bitcast ptr %value.1 to ptr")]:
        rec = "N_pointer_store" if variant in ["global", "scalar_cell"] else "N_launder"
        add(rec, variant, "@export = private global ptr null\n" + root_change("  call void @minyar_rc_step()", instruction + "\n  call void @minyar_rc_step()"))
    add("N_lens_escape", "opaque_backing", "declare void @opaque(ptr)\n" + body_change(REAL, GET, "  %slot =", "  call void @opaque(ptr %values)\n  %slot ="))
    for variant, instruction in [("retain", "call void @minyar_rc_retain(ptr %argument.1)"),
                                 ("step", "call void @minyar_rc_step()"),
                                 ("allocation", "%fresh = call ptr @minyar_list_new()"),
                                 ("recursive", f"%again = call i64 @{PICK}(double %argument.0, ptr %argument.1, ptr %argument.2)"),
                                 ("bytes_write", "call void @minyar_bytes_set(ptr %argument.1, i64 0, i64 1)")]:
        add("N_loop_effect", variant, body_change(REAL, PICK, "for.body.1:\n", "for.body.1:\n  " + instruction + "\n"))
    for step in [0, 2, -1]:
        add("N_loop_rank", f"step{step}", body_change(REAL, PICK, "add nsw i64 %value.10, 1", f"add nsw i64 %value.10, {step}"))
    for variant, instruction in [("counter_write", "store i64 7, ptr %local.3"),
                                 ("limit_write", "store i64 7, ptr %local.4"),
                                 ("index_write", "store i64 7, ptr %local.5"),
                                 ("pointer_phi", "%merged = phi ptr [ %argument.1, %entry ], [ %argument.2, %for.step.2 ]")]:
        add("N_loop_rank", variant, body_change(REAL, PICK, "  %value.4 = load", instruction + "\n  %value.4 = load"))
    add("N_loop_rank", "second_backedge", body_change(REAL, PICK, "  br label %for.step.2", "  br label %for.condition.0"))
    add("N_loop_rank", "wrong_bound", body_change(REAL, PICK, "store i64 %value.0, ptr %local.4", "store i64 8, ptr %local.4"))
    add("N_guard", "continuing_leave", body_change(REAL, PICK, "for.step.2:\n", "for.step.2:\ncall void @minyar_stack_leave()\n"))
    add("N_guard", "missing_return_leave", body_change(REAL, PICK, "  call void @minyar_stack_leave()\n  ret i64 %value.9", "  ret i64 %value.9"))
    add("N_early_step", "before_pick", root_change("  %value.5 = call", "  call void @minyar_rc_step()\n  %value.5 = call"))
    for variant, ins in [("append", "call void @minyar_list_add(ptr %value.1, i64 2)"),
                         ("read", "%later = call i64 @.minyar.list.length(ptr %value.1)")]:
        add("N_early_step", variant, root_change("  call void @minyar_rc_step()", "  call void @minyar_rc_step()\n" + ins))
    for variant, replacement in [("missing", ""), ("double", "  call void @minyar_rc_leave()\n  call void @minyar_rc_leave()\n")]:
        add("N_leave", variant, root_change("  call void @minyar_rc_leave()\n", replacement))
    for value in ["1", "%argument.1", "9223372036854775808"]:
        add("N_leave", "slots_" + value, root_change("@minyar_rc_enter(i64 0)", "@minyar_rc_enter(i64 " + value + ")"))
    for variant, old, new in [("removed_guard", "br i1 %get.valid, label %good, label %bad", "br label %good"),
                              ("signed_guard", "icmp ult", "icmp slt"),
                              ("field", "i32 0, i32 1", "i32 0, i32 2"),
                              ("slot_type", "getelementptr i64,", "getelementptr i32,"),
                              ("inbounds", "getelementptr i64,", "getelementptr inbounds i64,"),
                              ("wrong_index", "ptr %values, i64 %position", "ptr %values, i64 0")]:
        add("N_getter_guard", variant, body_change(REAL, GET, old, new))
    for profile in ["eager", "arena", "stack_owner", "system_k1"]:
        add("N_profile", profile, profile=profile)
    add("N_profile", "catalog_digest", catalog_sha256="0" * 64)
    add("N_profile", "source_digest", runtime_hashes={"minyar_runtime.c": "0" * 64})
    for variant, value in [("large_integer", "9223372036854775808"), ("huge_literal", "9" * 2000), ("nonfinite", "1.0e999")]:
        ir = root_change("i64 15793661", "i64 " + value) if variant != "nonfinite" else root_change("double 2.4e-1", "double " + value)
        add("N_arithmetic", variant, ir)
    add("N_arithmetic", "input_limit", ";" + "x" * (8 * 1024 * 1024))
    for variant, old, new in [("poison", "i64 15793661", "i64 poison"),
                              ("undef", "i64 15793661", "i64 undef"),
                              ("duplicate_ssa", "%value.2 = call ptr", "%value.1 = call ptr"),
                              ("type", "ptr %value.1, i64 15793661", "i64 %value.1, i64 15793661"),
                              ("tail", "ret void", "ret void\nfence seq_cst"),
                              ("extra_operand", "i64 15793661)", "i64 15793661, i64 2)"),
                              ("missing_target", "ret void", "br label %absent"),
                              ("undefined", "i64 15793661", "i64 %undefined"),
                              ("unknown_opcode", "ret void", "%v = freeze i64 3\nret void"),
                              ("indirect_call", "call void @minyar_rc_step()", "call void %argument.0()"),
                              ("call_modifier", "call void @minyar_rc_step()", "tail call void @minyar_rc_step()")]:
        add("N_grammar", variant, root_change(old, new))
    add("N_grammar", "duplicate_symbol", REAL + "\ndeclare void @minyar_rc_step()\n")
    add("N_grammar", "runtime_shadow", REAL.replace("declare void @minyar_rc_step()", "define void @minyar_rc_step() {\nentry:\nret void\n}"))
    add("N_grammar", "alias", REAL + "\n@alias = alias void (), ptr @minyar_rc_step\n")
    add("N_grammar", "truncated_body", root_change("  ret void\n}", "  ret void\n"))
    add("N_grammar", "getter_nondominating", body_change(REAL, GET, "  %get.valid =", "  %early = load i64, ptr %slot\n  %get.valid ="))
    add("N_grammar", "duplicate_block", body_change(REAL, GET, "good:", "entry:"))
    add("C_unprotected", "context_closed", conclusion="context_closed", external_protection=False)
    add("C_unprotected", "process_closed", conclusion="process_closed")
    add("C_unprotected", "unfulfilled_conditional", expected=4, external_protection=False)
    add("C_outside_debt", "arbitrary_debt", expected=4, outside_debt="arbitrary")
    for symbol in ["build", "drawTile", "main"]:
        selected = next((s for s in names if s.endswith("_" + symbol)), "main")
        add("unsupported_corpus", symbol, entry=selected)
    # No reliance on reachability pruning of false branches or silent parser skips.
    add("callee_effect", "put_rc_leave", body_change(REAL, ".minyar.fn.minyar_module_1_put", "  ret void", "call void @minyar_rc_leave()\n  ret void"))
    add("callee_effect", "unreachable_store", body_change(REAL, GET, "bad:\n", "unused:\nstore ptr %list, ptr %list\nret i64 0\nbad:\n"))
    # Additional parser/dataflow/proof gates, specified before corresponding repairs.
    for variant, old, new in [
            ("load_width", "load i64, ptr %slot", "load i32, ptr %slot"),
            ("base_operand_type", "ptr %list, i32 0", "i64 0, i32 0"),
            ("uninitialized", "%value = load i64, ptr %slot", "%cell = alloca i64\n%value = load i64, ptr %cell"),
            ("cell_escape", "%value = load i64, ptr %slot", "%cell = alloca i64\n%value = call i64 @minyar_list_get(ptr %cell, i64 0)")]:
        ir = body_change(REAL, GET, old, new)
        if variant == "load_width":
            ir = body_change(ir, GET, "ret i64 %value", "ret i64 0")
        add("additional_parser", variant, ir)
    add("additional_parser", "nested_type", owners(1).replace("i64 -7", "{" * 1100 + "i64" + "}" * 1100 + " -7"), entry="component")
    # Valid types with deliberate cell and guard violations in acyclic callees.
    add("additional_dataflow", "entry_uninitialized", body_change(REAL, ".minyar.fn.minyar_module_3_hash", "  store i64 %value.2, ptr %local.3\n", ""))
    add("additional_dataflow", "late_enter", body_change(REAL, GET, "  ret i64 %value", "call void @minyar_stack_enter()\ncall void @minyar_stack_leave()\n  ret i64 %value"))
    add("additional_dataflow", "detached_guard_leave", body_change(REAL, ".minyar.fn.minyar_module_3_hash", "  %local.3 = alloca i64", "call void @minyar_stack_leave()\ncall void @minyar_stack_enter()\n  %local.3 = alloca i64"))
    add("additional_loop", "write_in_returning_arm", body_change(REAL, PICK, "if.then.4:\n", "if.then.4:\ncall void @minyar_bytes_set(ptr %argument.1, i64 0, i64 2)\n"))
    # A wrapper must substitute and carry a nested counted-loop obligation.
    wrapped = """define i64 @forward(ptr %limits, ptr %colours, double %x) {
entry:
%r = call i64 @.minyar.fn.minyar_module_1_pick(double %x, ptr %colours, ptr %limits)
ret i64 %r
}
""" + root_change("@.minyar.fn.minyar_module_1_pick(double %value.0, ptr %value.1, ptr %value.2)", "@forward(ptr %value.2, ptr %value.1, double %value.0)")
    add("additional_loop", "wrapper_substitution", wrapped, 4)
    for variant, old, new in [("readonly_effects", "ret i64 %value.9", "ret i64 %value.9"),
                              ("latch_nsw_wrong", "add nsw i64 %value.10, 1", "sub nsw i64 %value.10, -1")]:
        if variant != "readonly_effects":
            add("additional_loop", variant, body_change(REAL, PICK, old, new))
    # Resource ceilings are exercised with independently formed text, not changed limits.
    many_blocks = "define void @component() {\n" + "\n".join(
        f"b{i}:\nbr label %b{i + 1}" for i in range(256)) + "\nb256:\nret void\n}"
    add("N_arithmetic", "block_limit", many_blocks, entry="component")
    large_root = owners(1).replace("ret void", "\n".join(f"%scalar{i} = add i64 0, 1" for i in range(20001)) + "\nret void")
    add("N_arithmetic", "instruction_limit", large_root, entry="component")
    many_defs = "\n".join(f"define void @f{i}() {{\nentry:\ncall void @f{i + 1}()\nret void\n}}" for i in range(128)) + "\ndefine void @f128() {\nentry:\nret void\n}"
    add("N_arithmetic", "definition_limit", many_defs, entry="f0")
    return rows


def run(module_path):
    spec = importlib.util.spec_from_file_location("cleanup_checker", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    results = []
    for case in cases():
        try:
            result = module.analyze(case["ir"], case["entry"], **case["options"])
            expected = case["expected"]
            if expected == "rejected":
                assert result["status"] == "rejected", result
                assert result.get("reason") and result.get("location"), result
                assert "work" not in result, result
            else:
                assert result["status"] == "conditional_component_certificate", result
                assert result["work"]["W_full_service_component"] == expected, result
                assert result["work"]["W_full_service_component"] == result["work"]["V"] + result["work"]["F"]
                assert result["assumptions"] and result["obligations"] and result["runtime_premises"]
                assert "remaining_after_return" not in result and "process_poll_count" not in result
                if case["entry"] == ENTRY or case["record"] == "M_rename":
                    assert len(result["definitions"]) == (14 if case["variant"] == "wrapper_substitution" else 13)
                    external = result["external_requirements"]
                    assert any(x["representation"] == "Bytes" and x["status"] == "required_not_discharged" for x in external)
                    assert result["loops"] and result["loops"][0]["maximum_iterations"] == 2
                if case["record"] == "M_owner8":
                    assert list(map(len, result["chunks"])) == [8]
                if case["record"] == "M_owner9":
                    assert list(map(len, result["chunks"])) == [8, 1]
                if case["record"] == "P_actual":
                    assert [g["length"] for g in result["generations"]] == [3, 2]
                    assert [g["capacity"] for g in result["generations"]] == [4, 2]
                    assert result["boundary"]["line"] == 1057
                    assert result["frame"]["written_locals"] == 0
            error = None
        except Exception as exc:
            result = None
            error = f"{type(exc).__name__}: {str(exc)[:1800]}"
        results.append({k: case[k] for k in ["record", "variant", "entry", "expected", "options"]} | {
            "input_sha256": hashlib.sha256(case["ir"].encode()).hexdigest(),
            "passed": error is None, "error": error,
            "observed_status": result.get("status") if result else None,
            "rejection": result if result and result["status"] == "rejected" else None})
    summary = dict(cases=len(results), passed=sum(x["passed"] for x in results),
                   failed=sum(not x["passed"] for x in results), results=results)
    print(json.dumps(summary, indent=2))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(run(Path(os.environ.get("CLEANUP_RESEARCH_CHECKER", Path(__file__).with_name("cleanup-certificate-research.py")))))
