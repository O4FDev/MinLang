"""Research-only typed LLVM subset checker; never executes/evaluates input.

API: analyze(saved_ir, arbitrary_entry, **context_options) -> JSON-compatible dict.
CLI: python3 tests/cleanup-certificate-research.py saved.ll entry
Runtime effects are pinned premises; application effects are body-derived.
"""
import argparse
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re

DESIGN = Path('/Users/luke/Projects/Minyar-Lang/research/2026-10-memory/evidence/local-cleanup-certifier-design')
CATALOG_SHA = "f9c729a50575e3e2c5d1b91b6761648aea62bdc3ce4afcaaf37c69d023c63158"
PROFILE = "system_incremental_k32_64"
MAX_I64, MAX_SIZE = (1 << 63) - 1, (1 << 64) - 1
INPUT_LIMIT, TOKEN_LIMIT = 8 * 1024 * 1024, 500000
DEFINITION_LIMIT, BLOCK_LIMIT, INSTRUCTION_LIMIT, ITERATION_LIMIT = 128, 256, 20000, 200000
TOP, PAIR, LAYOUT = ("OtherScalar",), "{i64,i1}", "{ptr,i64,i64}"
ABI = {
    "minyar_list_new": ("ptr", (), (), "P1"),
    "minyar_list_add": ("void", ("ptr", "i64"), (), "P2"),
    "minyar_rc_enter": ("void", ("i64",), (), "P3"),
    "minyar_rc_keep": ("void", ("ptr",), (), "P4"),
    "minyar_rc_step": ("void", (), (), "P5"),
    "minyar_rc_leave": ("void", (), (), "P5"),
    "minyar_list_get": ("i64", ("ptr", "i64"), (), "P8"),
    "minyar_bytes_set": ("void", ("ptr", "i64", "i64"), (), "P9"),
    "minyar_stack_enter": ("void", (), (), "P10"),
    "minyar_stack_leave": ("void", (), (), "P10"),
    "minyar_fail_integer_overflow": ("void", (), ("cold", "noreturn"), "P11"),
    "minyar_fail_integer_division": ("void", ("i64",), ("cold", "noreturn"), "P11"),
    "minyar_check_clamp_integer": ("void", ("i64", "i64"), (), "P11"),
    "minyar_check_shift": ("void", ("i64",), (), "P11"),
    "llvm.sadd.with.overflow.i64": (PAIR, ("i64", "i64"), (), "P11"),
    "llvm.ssub.with.overflow.i64": (PAIR, ("i64", "i64"), (), "P11"),
    "llvm.smul.with.overflow.i64": (PAIR, ("i64", "i64"), (), "P11"),
}
RUNTIME_HASHES = {
    "minyar_runtime.c": "c4e78f59096e0af8926c8d06febb9277e8c7cb7e5de8fc63b907d3afb613fcb4",
    "minyar_rc.h": "5d57a4494b2dc244d279ce8fbd50101184e1a7b46215f3c51f35766d4fccef9b",
    "minyar_bounded_rc.h": "7d40e4f2469150840b4527a85f4234a677ed177803793372fd4104b0e8e7304e",
    "minyar_collections.h": "01ae1e88dbcd98a9f8815a7a8e0508247a19f7f0b912d938544db129191eb4c0",
    "minyar_bytes.h": "58985d5534d76e628a0d43132cabca53aa0b473aa126dfd05012082e827e07a9",
    "minyar_numbers.h": "ce8ac3a34ac9cf59035057d80aa9ac77ed738d9076922b11c9e888d59341620d",
}


class Reject(Exception):
    def __init__(self, reason, location, detail=""):
        self.reason, self.location, self.detail = reason, location, detail


@dataclass(frozen=True)
class Token:
    value: str
    offset: int
    end: int
    line: int
    column: int

    def location(self):
        return dict(offset=self.offset, end=self.end, line=self.line, column=self.column)


def fail(reason, site, detail=""):
    raise Reject(reason, site.location() if isinstance(site, Token) else site, detail)


LEX = re.compile(r'(?P<space>\s+)|(?P<comment>;[^\n]*)|(?P<string>"(?:[^"\\]|\\.)*")|(?P<name>[@%][A-Za-z_.$0-9][A-Za-z_.$0-9-]*)|(?P<number>-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)|(?P<word>[A-Za-z_.$][A-Za-z_.$0-9-]*)|(?P<punct>[{}()[\],=:*])')


def lex(source):
    if len(source.encode("utf-8")) > INPUT_LIMIT:
        fail("analysis_limit", dict(line=1, column=1), "input exceeds 8 MiB")
    if not source.isascii():
        fail("unsupported_grammar", dict(line=1, column=1), "ASCII saved dialect only")
    newlines = [-1] + [m.start() for m in re.finditer("\n", source)]
    result, position = [], 0
    while position < len(source):
        match = LEX.match(source, position)
        line = bisect_right(newlines, position)
        if not match:
            fail("lexical_error", dict(offset=position, line=line, column=position - newlines[line - 1]))
        if match.lastgroup not in {"space", "comment"}:
            result.append(Token(match.group(), position, match.end(), line, position - newlines[line - 1]))
            if len(result) > TOKEN_LIMIT:
                fail("analysis_limit", result[-1], "token limit")
        position = match.end()
    result.append(Token("<eof>", position, position, len(newlines), 1))
    return result


class Cursor:
    def __init__(self, tokens):
        self.tokens, self.index = tokens, 0

    def peek(self, distance=0):
        return self.tokens[min(self.index + distance, len(self.tokens) - 1)]

    def pop(self, expected=None):
        token = self.peek()
        if token.value == "<eof>" or expected is not None and token.value != expected:
            fail("malformed_grammar", token, "expected " + str(expected))
        self.index += 1
        return token

    def accept(self, value):
        if self.peek().value == value:
            self.pop()
            return True
        return False

    def type(self, layout=False):
        token = self.pop()
        if token.value in {"void", "i1", "i32", "i64", "double", "ptr"}:
            return token.value
        if token.value == "{":
            # No recursive types belong to this tiny grammar.
            parts = [self.pop().value]
            while self.accept(","):
                parts.append(self.pop().value)
            self.pop("}")
            result = "{" + ",".join(parts) + "}"
            if result == PAIR or layout and result == LAYOUT:
                return result
        fail("unsupported_type", token)

    def value(self, ty):
        token = self.pop()
        value = token.value
        if value.startswith("%"):
            return value
        if ty in {"ptr", PAIR, "void"}:
            fail("unsupported_value", token, "only singleton SSA pointer/aggregate operands")
        if ty.startswith("i"):
            if value in {"true", "false"} and ty == "i1":
                return 1 if value == "true" else 0
            if not re.fullmatch(r"-?[0-9]+", value) or len(value) > 21:
                fail("unrepresentable_constant", token)
            number, bits = int(value), int(ty[1:])
            if not -(1 << (bits - 1)) <= number <= (1 << bits) - 1 or ty == "i64" and number > MAX_I64:
                fail("unrepresentable_constant", token)
            return number
        if ty == "double" and re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value):
            if len(value) > 128 or not math.isfinite(float(value)):
                fail("unrepresentable_constant", token)
            return float(value)
        fail("unsupported_value", token)

    def operand(self):
        ty = self.type()
        return ty, self.value(ty)


@dataclass
class Instruction:
    site: Token
    result: str | None
    op: str
    ty: str
    operands: list = field(default_factory=list)
    target: str | None = None
    labels: list = field(default_factory=list)
    extra: object = None


@dataclass
class Function:
    site: Token
    name: str
    ret: str
    params: list
    attrs: tuple
    body: list | None
    end: Token
    blocks: dict = field(default_factory=dict)
    definitions: dict = field(default_factory=dict)
    predecessors: dict = field(default_factory=dict)
    successors: dict = field(default_factory=dict)
    dominators: dict = field(default_factory=dict)
    positions: dict = field(default_factory=dict)


def module_index(tokens):
    c = Cursor(tokens)
    functions, symbols = {}, set()
    while c.peek().value != "<eof>":
        start = c.pop()
        if start.value.startswith("@"):
            if start.value in symbols:
                fail("duplicate_symbol", start)
            symbols.add(start.value)
            c.pop("=")
            depth, count = [], 0
            while c.peek().value != "<eof>":
                token = c.peek()
                if not depth and (token.value in {"declare", "define"} or token.value.startswith("@") and c.peek(1).value == "="):
                    break
                token = c.pop()
                count += 1
                if token.value in {"alias", "ifunc"}:
                    fail("unsupported_alias", token)
                if token.value in {"{", "[", "("}:
                    depth.append({"{": "}", "[": "]", "(": ")"}[token.value])
                elif token.value in {"}", "]", ")"}:
                    if not depth or depth.pop() != token.value:
                        fail("malformed_global_framing", token)
            if depth or not count or start.value[1:] in ABI:
                fail("runtime_shadow_or_global_framing", start)
            continue
        if start.value not in {"declare", "define"}:
            fail("unsupported_module_construct", start)
        internal = c.accept("internal")
        return_extension = c.accept("zeroext")
        ret = c.type()
        name_token = c.pop()
        if not name_token.value.startswith("@"):
            fail("malformed_signature", name_token)
        name = name_token.value[1:]
        if name_token.value in symbols:
            fail("duplicate_symbol", name_token)
        symbols.add(name_token.value)
        c.pop("(")
        params = []
        parameter_extensions = []
        if not c.accept(")"):
            while True:
                ty = c.type()
                if c.accept("zeroext"):
                    parameter_extensions.append("parameter_zeroext:" + str(len(params)))
                if ty in {"void", PAIR}:
                    fail("unsupported_signature", name_token)
                param = c.pop().value if c.peek().value.startswith("%") else None
                if start.value == "define" and param is None:
                    fail("malformed_signature", name_token)
                params.append((ty, param))
                if c.accept(")"):
                    break
                c.pop(",")
        attrs = (["return_zeroext"] if return_extension else []) + parameter_extensions
        while c.peek().value in {"alwaysinline", "cold", "noreturn"}:
            attrs.append(c.pop().value)
        body = None
        if start.value == "define":
            if name in ABI:
                fail("runtime_shadow_definition", name_token)
            if attrs not in [[], ["alwaysinline"]]:
                fail("unsupported_attribute", name_token)
            c.pop("{")
            first, depth = c.index, 1
            while depth:
                token = c.pop()
                depth += (token.value == "{") - (token.value == "}")
            body = c.tokens[first:c.index - 1]
        elif internal or any(a not in {"return_zeroext", "cold", "noreturn"} and not a.startswith("parameter_zeroext:") for a in attrs):
            fail("unsupported_attribute", name_token)
        end = c.tokens[c.index - 1]
        functions[name] = Function(start, name, ret, params, tuple(attrs), body, end)
        if name in ABI and (ret, tuple(p[0] for p in params), tuple(attrs)) != ABI[name][:3]:
            fail("catalog_prototype_mismatch", name_token)
    return functions


def instruction(c):
    site, result = c.peek(), None
    if c.peek().value.startswith("%"):
        result = c.pop().value
        c.pop("=")
    opcode = c.pop()
    op, operands, target, labels, extra = opcode.value, [], None, [], None
    if op == "call":
        ty = c.type()
        callee = c.pop()
        if not callee.value.startswith("@"):
            fail("unsupported_call", callee)
        target = callee.value[1:]
        c.pop("(")
        if not c.accept(")"):
            while True:
                operands.append(c.operand())
                if c.accept(")"):
                    break
                c.pop(",")
    elif op == "alloca":
        if c.type() != "i64":
            fail("unsupported_cell", site)
        ty = "ptr"
    elif op in {"load", "store"}:
        if op == "store":
            operands.append(c.operand())
            ty = "void"
        else:
            ty = c.type()
        c.pop(",")
        operands.append(c.operand())
        if operands[-1][0] != "ptr":
            fail("type_mismatch", site)
    elif op == "getelementptr":
        extra = c.type(layout=True)
        c.pop(",")
        operands.append(c.operand())
        if operands[0][0] != "ptr":
            fail("type_mismatch", site)
        if extra == LAYOUT:
            for _ in range(2):
                c.pop(",")
                operands.append(c.operand())
        elif extra == "i64":
            c.pop(",")
            operands.append(c.operand())
        else:
            fail("unsupported_lens", site)
        ty = "ptr"
    elif op in {"add", "sub", "mul", "and", "or", "xor", "ashr", "sdiv", "srem", "fdiv"}:
        extra = "nsw" if c.accept("nsw") else None
        ty = c.type()
        if ty not in ({"double"} if op == "fdiv" else {"i1", "i32", "i64"}):
            fail("unsupported_scalar_type", site)
        operands.append((ty, c.value(ty)))
        c.pop(",")
        operands.append((ty, c.value(ty)))
    elif op in {"icmp", "fcmp"}:
        extra, ty_operand = c.pop().value, c.type()
        if op == "icmp" and (extra not in {"eq", "ne", "slt", "sle", "sgt", "sge", "ult", "ule", "ugt", "uge"} or ty_operand not in {"i1", "i32", "i64"}):
            fail("unsupported_comparison", site)
        if op == "fcmp" and (extra != "olt" or ty_operand != "double"):
            fail("unsupported_comparison", site)
        operands.append((ty_operand, c.value(ty_operand)))
        c.pop(",")
        operands.append((ty_operand, c.value(ty_operand)))
        ty = "i1"
    elif op in {"sitofp", "bitcast"}:
        operands.append(c.operand())
        c.pop("to")
        ty = c.type()
        if op == "sitofp" and (operands[0][0], ty) != ("i64", "double") or op == "bitcast" and (operands[0][0], ty) not in {("i64", "double"), ("double", "i64")}:
            fail("pointer_conversion_or_bad_cast", site)
    elif op == "extractvalue":
        operands.append(c.operand())
        c.pop(",")
        extra = c.value("i32")
        if operands[0][0] != PAIR or extra not in {0, 1}:
            fail("unsupported_extract", site)
        ty = "i64" if extra == 0 else "i1"
    elif op == "select":
        operands.append(c.operand())
        c.pop(",")
        operands.append(c.operand())
        c.pop(",")
        operands.append(c.operand())
        ty = operands[1][0]
        if operands[0][0] != "i1" or ty not in {"i1", "i32", "i64", "double"} or operands[2][0] != ty:
            fail("unsupported_select", site)
    elif op == "br":
        if c.accept("label"):
            labels.append(c.pop().value)
        else:
            operands.append(c.operand())
            if operands[0][0] != "i1":
                fail("type_mismatch", site)
            for _ in range(2):
                c.pop(",")
                c.pop("label")
                labels.append(c.pop().value)
        if any(not label.startswith("%") for label in labels):
            fail("malformed_target", site)
        labels, ty = [label[1:] for label in labels], "void"
    elif op == "ret":
        ty = "void"
        if not c.accept("void"):
            operands.append(c.operand())
            if operands[0][0] == "ptr":
                fail("pointer_return_escape", site)
    elif op == "unreachable":
        ty = "void"
    else:
        fail("unsupported_instruction", opcode, op)
    if (ty != "void") != (result is not None):
        fail("result_type_mismatch", site)
    return Instruction(site, result, op, ty, operands, target, labels, extra)


def reachable(successors, entry, blocked_edge=None):
    found, todo = set(), [entry]
    while todo:
        node = todo.pop()
        if node not in found:
            found.add(node)
            todo.extend(n for n in successors[node] if (node, n) != blocked_edge)
    return found


def parse_function(fn, functions):
    c = Cursor(fn.body + [Token("<eof>", fn.end.offset, fn.end.offset, fn.end.line, fn.end.column)])
    current = None
    for ty, name in fn.params:
        if name in fn.definitions:
            fail("duplicate_ssa", fn.site)
        fn.definitions[name] = (ty, None)
    while c.peek().value != "<eof>":
        if c.peek(1).value == ":":
            label = c.pop()
            c.pop(":")
            if label.value.startswith(("%", "@")) or label.value in fn.blocks or "%" + label.value in fn.definitions:
                fail("duplicate_or_bad_block", label)
            current = label.value
            fn.blocks[current] = []
            if len(fn.blocks) > BLOCK_LIMIT:
                fail("analysis_limit", label, "block limit")
            continue
        if current is None:
            fail("missing_entry_label", c.peek())
        ins = instruction(c)
        if fn.blocks[current] and fn.blocks[current][-1].op in {"ret", "br", "unreachable"}:
            fail("instruction_after_terminator", ins.site)
        fn.positions[id(ins)] = (current, len(fn.blocks[current]))
        fn.blocks[current].append(ins)
        if ins.result:
            if ins.result in fn.definitions or ins.result[1:] in fn.blocks:
                fail("duplicate_ssa", ins.site)
            fn.definitions[ins.result] = (ins.ty, ins)
    if not fn.blocks:
        fail("empty_function", fn.site)
    fn.predecessors = {b: set() for b in fn.blocks}
    for b, instructions in fn.blocks.items():
        if not instructions or instructions[-1].op not in {"br", "ret", "unreachable"}:
            fail("missing_terminator", instructions[-1].site if instructions else fn.site)
        fn.successors[b] = instructions[-1].labels
        for dest in fn.successors[b]:
            if dest not in fn.blocks:
                fail("missing_target", instructions[-1].site)
            fn.predecessors[dest].add(b)
    entry = next(iter(fn.blocks))
    if fn.predecessors[entry]:
        fail("entry_backedge", fn.site)
    # Proposed conservative narrowing: detached blocks reject, even if harmless.
    if reachable(fn.successors, entry) != set(fn.blocks):
        fail("unreachable_selected_block", fn.site)
    all_blocks = set(fn.blocks)
    dom = {b: ({entry} if b == entry else set(all_blocks)) for b in fn.blocks}
    for _ in range(BLOCK_LIMIT + 1):
        updated = {b: ({entry} if b == entry else {b} | set.intersection(*(dom[p] for p in fn.predecessors[b]))) for b in fn.blocks}
        if updated == dom:
            break
        dom = updated
    else:
        fail("analysis_limit", fn.site, "dominance iterations")
    fn.dominators = dom
    for b, instructions in fn.blocks.items():
        for pos, ins in enumerate(instructions):
            for ty, value in ins.operands:
                if isinstance(value, str):
                    definition = fn.definitions.get(value)
                    if definition is None or definition[0] != ty:
                        fail("undefined_or_mistyped_ssa", ins.site, value)
                    if definition[1] is not None:
                        db, dp = fn.positions[id(definition[1])]
                        if db not in dom[b] or db == b and dp >= pos:
                            fail("non_dominating_ssa", ins.site, value)
            if ins.op == "call":
                callee = functions.get(ins.target)
                if callee is None:
                    fail("unresolved_call", ins.site, ins.target)
                if (ins.ty, tuple(t for t, _ in ins.operands)) != (callee.ret, tuple(t for t, _ in callee.params)):
                    fail("call_signature_mismatch", ins.site, ins.target)
                if callee.body is None and ins.target not in ABI:
                    fail("unknown_effect", ins.site, ins.target)
            if ins.op == "ret" and (ins.operands[0][0] if ins.operands else "void") != fn.ret:
                fail("return_signature_mismatch", ins.site)
            if ins.op == "unreachable" and (pos == 0 or instructions[pos - 1].target not in {"minyar_fail_integer_overflow", "minyar_fail_integer_division"}):
                fail("unsupported_unreachable", ins.site)


def call_closure(functions, entry):
    if entry not in functions or functions[entry].body is None:
        fail("missing_entry_definition", dict(line=1, column=1), entry)
    order, active, done, instruction_count = [], set(), set(), 0
    stack = [(entry, False)]
    while stack:
        name, closing = stack.pop()
        if closing:
            active.remove(name)
            done.add(name)
            order.append(name)
            continue
        if name in active:
            fail("recursive_call_graph", functions[name].site)
        if name in done:
            continue
        if len(done | active) >= DEFINITION_LIMIT:
            fail("analysis_limit", functions[name].site, "selected definition limit")
        fn = functions[name]
        if not fn.blocks:
            parse_function(fn, functions)
            instruction_count += sum(map(len, fn.blocks.values()))
            if instruction_count > INSTRUCTION_LIMIT:
                fail("analysis_limit", fn.site, "selected instruction limit")
        active.add(name)
        stack.append((name, True))
        callees = dict.fromkeys(ins.target for block in fn.blocks.values() for ins in block
                                if ins.op == "call" and functions[ins.target].body is not None)
        stack.extend((callee, False) for callee in reversed(callees))
    return order


def tag(value, state):
    return state[1].get(value, TOP) if isinstance(value, str) else ("Constant", value)


def joined(states, site):
    guards = {s[2] for s in states}
    if len(guards) != 1:
        fail("guard_mismatch", site, "incoming depths disagree")
    maps = []
    for index in [0, 1]:
        common = set.intersection(*(set(s[index]) for s in states))
        maps.append({key: states[0][index][key] if all(s[index][key] == states[0][index][key] for s in states) else TOP for key in common})
    return maps[0], maps[1], guards.pop()


def pointers(fn):
    facts = {name: ("Param", index) for index, (ty, name) in enumerate(fn.params) if ty == "ptr"}
    pending = [ins for block in fn.blocks.values() for ins in block if ins.ty == "ptr"]
    for _ in range(len(pending) + 1):
        previous = len(pending)
        for ins in pending[:]:
            if ins.op == "alloca":
                if fn.positions[id(ins)][0] != next(iter(fn.blocks)):
                    fail("nonentry_cell", ins.site)
                fact = ("Cell", ins.result)
            elif ins.op == "call" and ins.target == "minyar_list_new":
                fact = ("Fresh", ins.result)
            elif ins.op == "getelementptr":
                base = facts.get(ins.operands[0][1])
                if base is None:
                    continue
                if ins.extra == LAYOUT and base[0] in {"Param", "Fresh"} and ins.operands[1:] == [("i32", 0), ("i32", 1)]:
                    fact = ("LengthLens", base)
                elif ins.extra == "i64" and base[0] == "BackingLens" and ins.operands[1][0] == "i64":
                    fact = ("SlotLens", base[1], ins.operands[1][1])
                else:
                    fail("invalid_lens", ins.site)
            elif ins.op == "load" and ins.ty == "ptr":
                base = facts.get(ins.operands[0][1])
                if base is None:
                    continue
                if base[0] not in {"Param", "Fresh"}:
                    fail("invalid_backing_lens", ins.site)
                fact = ("BackingLens", base)
            else:
                fail("unsupported_pointer_producer", ins.site)
            facts[ins.result] = fact
            pending.remove(ins)
        if not pending:
            return facts
        if len(pending) == previous:
            fail("unknown_pointer_provenance", pending[0].site)
    fail("analysis_limit", fn.site, "pointer propagation")


def borrower(fn, summaries):
    if fn.ret in {"ptr", PAIR}:
        fail("unsupported_borrower_return", fn.site)
    ptrs = pointers(fn)
    requirements, effects = {}, set()
    forwarded_loops = []
    calls_guard = False

    def require(pointer, representation, effect, site):
        if pointer[0] != "Param":
            fail("borrower_alias_or_owner", site)
        index = pointer[1]
        if index in requirements and requirements[index] != representation:
            fail("inconsistent_pointer_roles", site)
        requirements[index] = representation
        effects.add((effect, index))
        effects.add(("NeedsProtected", index))

    for b, block in fn.blocks.items():
        for ins in block:
            if ins.op == "store" and (ins.operands[0][0] != "i64" or ptrs[ins.operands[1][1]][0] != "Cell"):
                fail("pointer_export_or_backing_mutation", ins.site)
            for ty, value in ins.operands:
                if ty == "ptr":
                    if ins.op not in {"load", "store", "getelementptr", "call"}:
                        fail("pointer_escape", ins.site)
                    if ins.op == "call" and ptrs[value][0] != "Param":
                        fail("cell_or_lens_escape", ins.site)
            if ins.op == "call":
                target = ins.target
                if target in {"minyar_stack_enter", "minyar_stack_leave"}:
                    position = fn.positions[id(ins)][1]
                    if target == "minyar_stack_enter" and (b != next(iter(fn.blocks)) or position != 0):
                        fail("unsupported_guard_placement", ins.site, "guard enter must be first")
                    if target == "minyar_stack_leave" and (position + 2 != len(block) or block[-1].op != "ret"):
                        fail("unsupported_guard_placement", ins.site, "leave immediately before return required")
                    calls_guard = True
                elif target == "minyar_list_get":
                    require(ptrs[ins.operands[0][1]], "ScalarList", "ReadList", ins.site)
                elif target == "minyar_bytes_set":
                    require(ptrs[ins.operands[0][1]], "Bytes", "WriteByte", ins.site)
                elif target in summaries:
                    summary = summaries[target]
                    calls_guard |= summary["has_guard_effect"]
                    for effect, index in summary["effects"]:
                        require(ptrs[ins.operands[index][1]], summary["requirements"][index], effect, ins.site)
                    for witness in summary["loops"]:
                        actual = ptrs[ins.operands[witness["parameter"]][1]]
                        if actual[0] != "Param":
                            fail("loop_argument_alias", ins.site)
                        forwarded_loops.append(dict(witness, parameter=actual[1],
                            forwarding_sites=witness.get("forwarding_sites", []) + [ins.site.location()]))
                elif target not in ABI or ABI[target][3] != "P11":
                    fail("unsupported_borrower_effect", ins.site, target)
            if ins.op == "load":
                fact = ptrs[ins.operands[0][1]]
                if ins.ty not in {"i64", "ptr"}:
                    fail("invalid_load_width", ins.site)
                if ins.ty == "i64" and fact[0] not in {"Cell", "LengthLens", "SlotLens"}:
                    fail("invalid_load_lens", ins.site)
                if fact[0] in {"LengthLens", "SlotLens"}:
                    require(fact[1], "ScalarList", "ReadList", ins.site)
                elif ins.ty == "ptr":
                    require(fact, "ScalarList", "ReadList", ins.site)
            if ins.op == "getelementptr" and ins.extra == LAYOUT:
                require(ptrs[ins.operands[0][1]], "ScalarList", "ReadList", ins.site)

    entry = next(iter(fn.blocks))
    incoming, outgoing = {}, {}
    initial = ({}, {name: TOP for ty, name in fn.params if ty != "ptr"}, 0)

    def transfer(state, block, validate=False):
        cells, values, guard = dict(state[0]), dict(state[1]), state[2]
        state = cells, values, guard
        for ins in block:
            result_tag = TOP
            if ins.op == "load" and ins.ty == "i64":
                fact = ptrs[ins.operands[0][1]]
                if fact[0] == "Cell":
                    if validate and fact[1] not in cells:
                        fail("uninitialized_cell", ins.site)
                    result_tag = cells.get(fact[1], TOP)
                elif fact[0] == "LengthLens":
                    result_tag = ("Length", fact[1])
            elif ins.op == "store":
                cells[ptrs[ins.operands[1][1]][1]] = tag(ins.operands[0][1], state)
            elif ins.op == "call":
                if ins.target == "minyar_stack_enter":
                    if guard != 0:
                        fail("guard_mismatch", ins.site)
                    guard = 1
                elif ins.target == "minyar_stack_leave":
                    if guard != 1:
                        fail("guard_mismatch", ins.site)
                    guard = 0
                elif ins.target in summaries:
                    returned = summaries[ins.target]["return_tag"]
                    if returned[0] == "Length":
                        result_tag = ("Length", ptrs[ins.operands[returned[1][1]][1]])
            elif ins.op == "select":
                a, b = (tag(ins.operands[i][1], state) for i in [1, 2])
                result_tag = a if a == b else TOP
            if ins.result and ins.ty != "ptr":
                values[ins.result] = result_tag
            if validate and ins.op == "ret" and guard != 0:
                fail("guard_mismatch", ins.site)
            state = cells, values, guard
        return state

    todo, iterations = deque([entry]), 0
    while todo:
        b = todo.popleft()
        iterations += 1
        if iterations > ITERATION_LIMIT:
            fail("analysis_limit", fn.site, "dataflow iteration limit")
        states = [outgoing[p] for p in fn.predecessors[b] if p in outgoing]
        if b == entry:
            states.append(initial)
        if not states:
            continue
        state = joined(states, fn.blocks[b][0].site)
        new_out = transfer(state, fn.blocks[b])
        incoming[b] = state
        if outgoing.get(b) != new_out:
            outgoing[b] = new_out
            todo.extend(fn.successors[b])
    for b, block in fn.blocks.items():
        transfer(incoming[b], block, True)
        for ins in block:
            if ins.op == "load" and ins.ty == "i64":
                fact = ptrs[ins.operands[0][1]]
                if fact[0] == "SlotLens":
                    guarded = False
                    for gb, gblock in fn.blocks.items():
                        branch = gblock[-1]
                        if branch.op != "br" or len(branch.labels) != 2:
                            continue
                        test = fn.definitions[branch.operands[0][1]][1] if isinstance(branch.operands[0][1], str) else None
                        if test is None or test.op != "icmp" or test.extra != "ult" or test.operands[0] != ("i64", fact[2]):
                            continue
                        length_tag = outgoing[gb][1].get(test.operands[1][1], TOP)
                        if length_tag == ("Length", fact[1]) and b not in reachable(fn.successors, entry, (gb, branch.labels[0])):
                            guarded = True
                    if not guarded:
                        fail("missing_unsigned_slot_guard", ins.site)
    witnesses = prove_loop(fn, summaries, ptrs, outgoing) + forwarded_loops
    returns = [tag(ins.operands[0][1], outgoing[b]) if ins.operands else TOP
               for b, block in fn.blocks.items() for ins in block if ins.op == "ret"]
    returned = returns[0] if returns and all(t == returns[0] for t in returns) else TOP
    return dict(requirements=requirements, effects=sorted(effects), return_tag=returned,
                has_guard_effect=calls_guard, loops=witnesses,
                dataflow=dict(iterations=iterations, initialized={b: sorted(s[0]) for b, s in incoming.items()}))


def prove_loop(fn, summaries, ptrs, outgoing):
    backedges = [(b, target) for b, targets in fn.successors.items() for target in targets if target in fn.dominators[b]]
    pending = set(fn.blocks)
    while pending:
        ready = {b for b in pending if not any(p in pending and (p, b) not in backedges for p in fn.predecessors[b])}
        if not ready:
            fail("irreducible_or_nested_cfg", fn.site)
        pending -= ready
    flagged = [ins for block in fn.blocks.values() for ins in block if ins.extra == "nsw"]
    if not backedges:
        if flagged:
            fail("unproved_nsw", flagged[0].site)
        return []
    if len(backedges) != 1:
        fail("unsupported_loop", fn.site)
    latch, header = backedges[0]
    loop, todo = {header, latch}, [latch]
    while todo:
        node = todo.pop()
        for pred in fn.predecessors[node]:
            if pred not in loop:
                loop.add(pred)
                todo.append(pred)
    preheaders = fn.predecessors[header] - loop
    if len(preheaders) != 1 or fn.predecessors[header] != preheaders | {latch}:
        fail("unsupported_loop_preheader", fn.site)
    preheader = next(iter(preheaders))
    hblock, lblock = fn.blocks[header], fn.blocks[latch]
    if len(hblock) != 4 or [i.op for i in hblock] != ["load", "load", "icmp", "br"] or len(lblock) != 4 or [i.op for i in lblock] != ["load", "add", "store", "br"]:
        fail("unsupported_loop_shape", fn.site)
    counter_load, limit_load, compare, branch = hblock
    counter, limit = counter_load.operands[0][1], limit_load.operands[0][1]
    if ptrs[counter][0] != "Cell" or ptrs[limit][0] != "Cell" or counter == limit or compare.extra != "slt" or compare.operands != [("i64", counter_load.result), ("i64", limit_load.result)] or branch.operands != [("i1", compare.result)] or len(branch.labels) != 2 or branch.labels[0] not in loop or branch.labels[1] in loop:
        fail("unsupported_loop_condition", compare.site)
    load, increment, store, back = lblock
    if load.operands != [("ptr", counter)] or increment.ty != "i64" or increment.operands != [("i64", load.result), ("i64", 1)] or store.operands != [("i64", increment.result), ("ptr", counter)] or back.labels != [header] or any(ins is not increment for ins in flagged):
        fail("unsupported_loop_rank", increment.site)
    stores = [(b, i) for b, block in fn.blocks.items() for i in block if i.op == "store"]
    counter_stores = [(b, i) for b, i in stores if i.operands[1][1] == counter]
    limit_stores = [(b, i) for b, i in stores if i.operands[1][1] == limit]
    if len(counter_stores) != 2 or not any(b == preheader and i.operands[0] == ("i64", 0) for b, i in counter_stores) or len(limit_stores) != 1 or limit_stores[0][0] != preheader:
        fail("mutable_loop_counter_or_limit", compare.site)
    bound = outgoing[preheader][0].get(limit, TOP)
    if bound[0] != "Length" or bound[1][0] != "Param":
        fail("unknown_loop_length_bound", limit_load.site)
    body_entry = branch.labels[0]
    # Returning arms belong to the iteration region even though they cannot be
    # in the natural cycle. They must not hide a Bytes write or guarded helper.
    region, todo = set(), [body_entry]
    while todo:
        b = todo.pop()
        if b == header or b in region:
            continue
        region.add(b)
        todo.extend(fn.successors[b])
    for b in region:
        for ins in fn.blocks[b]:
            if ins.op != "call":
                continue
            if ins.target == "minyar_stack_leave" and fn.blocks[b][-1].op == "ret":
                continue
            if ins.target in summaries:
                summary = summaries[ins.target]
                if summary["has_guard_effect"] or summary["loops"] or any(effect == "WriteByte" for effect, _ in summary["effects"]):
                    fail("nonneutral_loop_returning_arm", ins.site)
            elif ins.target not in ABI or ABI[ins.target][3] not in {"P8", "P11"}:
                fail("nonneutral_loop_returning_arm", ins.site)
    for b in loop - {header}:
        if body_entry not in fn.dominators[b]:
            fail("unguarded_loop_path", fn.blocks[b][0].site)
        for ins in fn.blocks[b]:
            if ins.op == "call":
                if ins.target in summaries:
                    summary = summaries[ins.target]
                    if summary["has_guard_effect"] or summary["loops"] or any(effect == "WriteByte" for effect, _ in summary["effects"]):
                        fail("nonneutral_loop_call", ins.site)
                elif ins.target not in ABI or ABI[ins.target][3] not in {"P8", "P11"}:
                    fail("nonneutral_loop_call", ins.site)
            if ins.op == "store" and ins is not store:
                cell = ins.operands[1][1]
                all_writes = [(sb, si) for sb, si in stores if si.operands[1][1] == cell]
                if cell in {counter, limit} or ins.operands[0] != ("i64", counter_load.result) or len(all_writes) != 1 or b != body_entry:
                    fail("unsupported_loop_cell_write", ins.site)
    return [dict(function=fn.name, header=header, latch=latch, preheader=preheader,
                 cycle_blocks=sorted(loop), iteration_region=sorted(region), counter=counter, limit_cell=limit,
                 source_parameter=bound[1][1],
                 parameter=bound[1][1], bound_requirement="0 <= Length(parameter) <= LLONG_MAX-1",
                 invariant="0 <= counter <= limit", rank="limit-counter", step=1,
                 every_backedge=[dict(source=latch, target=header)],
                 maximum_iterations=None, status="structurally_inferred_under_assumptions")]


def owning_root(fn, summaries):
    if fn.ret != "void" or len(fn.blocks) != 1:
        fail("unsupported_owning_root", fn.site)
    block = next(iter(fn.blocks.values()))
    def call(ins, name):
        return ins.op == "call" and ins.target == name
    if len(block) < 5 or not call(block[0], "minyar_stack_enter") or not call(block[1], "minyar_rc_enter") or block[1].operands != [("i64", 0)]:
        fail("frame_protocol", fn.site)
    if not (call(block[-3], "minyar_rc_leave") and call(block[-2], "minyar_stack_leave") and block[-1].op == "ret" and not block[-1].operands):
        fail("invalid_closing_suffix", block[-1].site)
    boundary = len(block) - 3
    if boundary > 2 and call(block[boundary - 1], "minyar_rc_step"):
        boundary -= 1
    ptrs = pointers(fn)
    generations, chunks, external, loops = {}, [], {}, []
    service_sites = [block[1].site.location()]

    def instantiate(summary, ins):
        for ty, value in ins.operands:
            if ty == "ptr" and ptrs[value][0] == "Fresh" and not generations[ptrs[value][1]]["sealed"]:
                fail("unprotected_fresh_argument", ins.site)
        for index, representation in summary["requirements"].items():
            fact = ptrs[ins.operands[index][1]]
            if fact[0] == "Fresh":
                gen = generations.get(fact[1])
                if representation != "ScalarList" or gen is None or not gen["sealed"]:
                    fail("unprotected_or_wrong_fresh_argument", ins.site)
            elif fact[0] == "Param":
                parameter = fact[1]
                if parameter in external and external[parameter]["representation"] != representation:
                    fail("inconsistent_pointer_roles", ins.site)
                row = external.setdefault(parameter, dict(parameter=parameter, representation=representation,
                    protection="continuously live outside owner during complete invocation including hidden service",
                    status="required_not_discharged", effects=set(), loop_bounds=[]))
                row["effects"].update(effect for effect, idx in summary["effects"] if idx == index)
            else:
                fail("pointer_argument_escape", ins.site)
        for witness in summary["loops"]:
            fact = ptrs[ins.operands[witness["parameter"]][1]]
            item = dict(witness, call_site=ins.site.location(), instantiated_argument=list(fact))
            if fact[0] == "Fresh":
                length = generations[fact[1]]["length"]
                if not 0 <= length <= MAX_I64 - 1:
                    fail("unrepresentable_loop_bound", ins.site)
                item["maximum_iterations"] = length
            else:
                external[fact[1]]["loop_bounds"].append(witness["bound_requirement"])
            loops.append(item)

    for ins in block[2:boundary]:
        if ins.extra == "nsw":
            fail("unproved_nsw", ins.site)
        if ins.op == "call":
            target = ins.target
            if target == "minyar_list_new":
                generations[ins.result] = dict(id=ins.result, constructor=ins.site.location(),
                    kind="ScalarList", length=0, capacity=0, sealed=False, token="Producer",
                    ownership_word=10, producer_interval=dict(start=ins.site.location(), end=None))
                service_sites.append(ins.site.location())
            elif target == "minyar_list_add":
                fact = ptrs[ins.operands[0][1]]
                gen = generations.get(fact[1]) if fact[0] == "Fresh" else None
                if gen is None or gen["sealed"]:
                    fail("append_requires_fresh_producer", ins.site)
                length, capacity = gen["length"] + 1, gen["capacity"]
                if length > capacity:
                    capacity = 2 if capacity == 0 else capacity * (4 if capacity >= 4096 else 2)
                if length > MAX_I64 or capacity > MAX_I64 or capacity * 8 + 8 > MAX_SIZE:
                    fail("unrepresentable_capacity", ins.site)
                gen["length"], gen["capacity"] = length, capacity
                service_sites.append(ins.site.location())
            elif target == "minyar_rc_keep":
                fact = ptrs[ins.operands[0][1]]
                gen = generations.get(fact[1]) if fact[0] == "Fresh" else None
                if gen is None:
                    fail("unsupported_external_owner_registration", ins.site)
                if gen["sealed"]:
                    fail("producer_token_already_transferred", ins.site)
                if not chunks or len(chunks[-1]) == 8:
                    chunks.append([])
                gen.update(sealed=True, token=dict(chunk=len(chunks) - 1, slot=len(chunks[-1])), keep=ins.site.location())
                gen["producer_interval"]["end"] = ins.site.location()
                gen["active_chunk_protection"] = dict(start=ins.site.location(), end=block[boundary].site.location())
                chunks[-1].append(gen["id"])
                service_sites.append(ins.site.location())
            elif target in summaries:
                instantiate(summaries[target], ins)
            elif target in ABI and ABI[target][3] in {"P8", "P9", "P11"}:
                if target == "minyar_list_get":
                    instantiate(dict(requirements={0: "ScalarList"}, effects=[("ReadList", 0), ("NeedsProtected", 0)], loops=[]), ins)
                elif target == "minyar_bytes_set":
                    instantiate(dict(requirements={0: "Bytes"}, effects=[("WriteByte", 0), ("NeedsProtected", 0)], loops=[]), ins)
            else:
                fail("unsupported_prefix_owner_or_service_effect", ins.site, target)
        elif ins.op not in {"add", "sub", "mul", "and", "or", "xor", "ashr", "sdiv", "srem", "fdiv", "icmp", "fcmp", "sitofp", "bitcast", "select", "extractvalue"}:
            fail("unsupported_root_instruction", ins.site)
    if any(not gen["sealed"] for gen in generations.values()):
        fail("unregistered_producer_at_boundary", block[boundary].site)
    visits, finalizers = sum(map(len, chunks)), len(chunks) + 1
    work = max(0, visits + finalizers - 32)  # deliberately subtract automatic poll budget
    if work > MAX_SIZE:
        fail("unrepresentable_work", block[boundary].site)
    return dict(boundary=dict(**block[boundary].site.location(), position="before instruction",
        policy="first instruction of maximal terminal rc_step?;rc_leave;stack_leave;ret void suffix"),
        generations=list(generations.values()), chunks=chunks,
        frame=dict(activation=block[1].site.location(), written_locals=0, finalizers=1),
        work=dict(V=visits, F=finalizers, Q=0, R=0, E=0, W_full_service_component=work),
        external_requirements=[dict(row, effects=sorted(row["effects"])) for row in external.values()],
        loops=loops, service=dict(prefix_may_service_outside=service_sites,
            producer_and_active_chunks_protect_all_fresh_generations=True,
            suffix="detachment/retirement conserves tickets; service attribution unknown"))


def check_catalog(profile, catalog_sha256, runtime_hashes):
    location = dict(line=1, column=1, input="runtime catalog/profile")
    if profile != PROFILE or catalog_sha256 != CATALOG_SHA:
        fail("unreviewed_profile_or_catalog", location)
    raw = (DESIGN / "runtime-summary-premises.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA:
        fail("catalog_identity_mismatch", location)
    catalog = json.loads(raw)
    if catalog["profile"] != dict(pointer_bits=64, size_t_bits=64, long_long_bits=64,
        system_heap=True, incremental=True, budget=32, arena=False, stack_owner_abi=False):
        fail("catalog_profile_mismatch", location)
    if {symbol for p in catalog["premises"] for symbol in p["symbols"]} != set(ABI):
        fail("catalog_symbol_mismatch", location)
    hashes = {}
    for name, expected in RUNTIME_HASHES.items():
        observed = hashlib.sha256((DESIGN / "inputs/runtime" / name).read_bytes()).hexdigest()
        if observed != expected:
            fail("runtime_source_identity_mismatch", location, name)
        hashes[name] = observed
    if runtime_hashes is not None and runtime_hashes != hashes:
        fail("runtime_source_identity_mismatch", location, "supplied source set differs")
    return catalog, hashes


def analyze(ir, entry, *, profile=PROFILE, catalog_sha256=CATALOG_SHA,
            runtime_hashes=None, conclusion="conditional_component", external_protection=None,
            outside_debt=None):
    """Infer conditional full-service total. Context fields never discharge protection."""
    try:
        if conclusion != "conditional_component":
            fail("unsupported_context_or_process_closure", dict(line=1, column=1), conclusion)
        if not isinstance(ir, str):
            fail("invalid_input", dict(line=1, column=1), "saved IR must be text")
        catalog, hashes = check_catalog(profile, catalog_sha256, runtime_hashes)
        functions = module_index(lex(ir))
        order = call_closure(functions, entry)
        summaries = {}
        for name in order:
            if name != entry:
                summaries[name] = borrower(functions[name], summaries)
        result = owning_root(functions[entry], summaries)
        definitions = []
        for name in order:
            fn = functions[name]
            definitions.append(dict(name=name, start=fn.site.location(), end=fn.end.location(),
                sha256=hashlib.sha256(ir[fn.site.offset:fn.end.end].encode()).hexdigest(),
                blocks=len(fn.blocks), instructions=sum(map(len, fn.blocks.values()))))
        public_summaries = {name: dict(summary, requirements={str(k): v for k, v in summary["requirements"].items()}) for name, summary in summaries.items()}
        return dict(result, status="conditional_component_certificate", schema_version=1,
            analysis_version="research-subset-v0", input_sha256=hashlib.sha256(ir.encode()).hexdigest(),
            entry=entry, profile=profile, catalog_sha256=CATALOG_SHA, runtime_source_sha256=hashes,
            runtime_premises=catalog["premises"], definitions=definitions, borrower_summaries=public_summaries,
            context_request=dict(external_protection=external_protection, outside_debt=outside_debt, automatic_discharge=False),
            assumptions=["valid successful execution: allocation, arithmetic, shift/division, bounds and guard success",
                "reviewed frozen C/runtime ABI summaries, exact linkage, LLVM scalar/intrinsic semantics and optimizer preservation",
                "64-bit system incremental K32, single mutator, no reentrancy, valid representable heap/queue/cache state",
                "external representation and continuously live outside protection requirements hold throughout invocation",
                "fresh generations disjoint from external borrowers; no hidden incoming owner edges",
                "eventual full positive fair service after closing suffix; arbitrary outside debt allowed"],
            obligations={"O1": "implemented subset checks; full LLVM proof unresolved",
                "O2": "trusted reviewed summaries; C/refinement/linking proof unresolved",
                "O3": "finite body effects/dataflow and K witness; independent implementation review pending",
                "O4": "producer/chunk conservation inferred; runtime refinement conditional",
                "O5": "terminal suffix inferred; contextual closure unsupported",
                "O6": "conditional P6/P7 cost mapping, full-service total only",
                "O7": "external protection required_not_discharged; full service assumed",
                "O8": "frozen identities; compiler/LLVM build-chain proof unresolved"},
            nonclaims=["verified LLVM/C/compiler", "whole-program/context/process closure", "completion at return",
                "exact remaining work or process poll count", "allocation admission or byte/RSS bound",
                "wall deadline", "production integration/optimization", "novelty", "measured analysis performance"],
            indexing_limit="unselected bodies framed, signatures indexed; their semantics not validated")
    except Reject as exc:
        return dict(status="rejected", reason=exc.reason, location=exc.location, detail=exc.detail,
                    schema_version=1, analysis_version="research-subset-v0")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return dict(status="rejected", reason="frozen_input_read_error", location=dict(line=1, column=1), detail=str(exc))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("saved_ir", type=Path)
    parser.add_argument("entry")
    parser.add_argument("--profile", default=PROFILE)
    parser.add_argument("--conclusion", default="conditional_component")
    args = parser.parse_args()
    try:
        with args.saved_ir.open("rb") as stream:
            raw = stream.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            result = dict(status="rejected", reason="analysis_limit", location=dict(line=1, column=1))
        else:
            result = analyze(raw.decode("ascii"), args.entry, profile=args.profile, conclusion=args.conclusion)
    except (OSError, UnicodeError) as exc:
        result = dict(status="rejected", reason="input_read_error", location=dict(line=1, column=1), detail=str(exc))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "conditional_component_certificate" else 1


if __name__ == "__main__":
    raise SystemExit(main())
