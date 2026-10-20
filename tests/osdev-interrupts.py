#!/usr/bin/env python3
"""IRQ context and emitted-code qualification. Default emits the source matrix.

On BX, explicitly select --phase parser, compile, ir, host-flags or assembly.
Requires the selected existing compiler; generated fixtures stay outside the checkout.
--phase live-plan describes required future guest proofs, not results.
"""

import argparse
from dataclasses import asdict, dataclass, field
import fnmatch
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


DEFAULT_ROOT = Path(__file__).resolve().parent.parent
TARGETS = {"x86_64": (1, 32, 47, "x86_64-unknown-none-elf"),
           "arm64": (2, 16, 1019, "aarch64-unknown-none-elf")}
PENDING = ".minyar.irq.pending"
PROVENANCE = {
    "sleep": {"reference": "Linux cbbbf7795fc35a740e1d09f3a55aba543b72a8d3",
              "url": "https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux.git/%2B/cbbbf7795fc35a740e1d09f3a55aba543b72a8d3",
              "scope": "Adapted helper-to-blocking-path reproducer; not the complete deferred-memory/PREEMPT_RT bug."},
    "lock": {"reference": "SerenityOS PR27039",
             "url": "https://github.com/SerenityOS/serenity/pull/27039",
             "scope": "Adapted serialization-to-lock reachability; IRQ exclusion does not prove ordinary lock ordering."},
    "allocation": {"reference": "Linux kernel-hacking allocation guidance",
                   "url": "https://github.com/torvalds/linux/blob/master/Documentation/kernel-hacking/hacking.rst",
                   "scope": "Documented sleeping allocation class; initial IRQ rule bans all allocation, not only sleeping allocators."},
    "dma": {"reference": "Linux d760117060cf2e90b5c59c5492cab179a4dbce01",
            "url": "https://kernel.googlesource.com/pub/scm/linux/kernel/git/stable/stable-queue/%2B/f494150665ec7c8557c7e2e4bacd7a64237c5602/releases/6.1.93/net-ena-fix-dma-syncing-in-xdp-path-when-swiotlb-is-on.patch",
            "scope": "Deferred affine DMA fixture. This IRQ checker proves no CPU/device ownership or synchronization property."},
    "address": {"reference": "Redox 22371bebde9446b9d51774c94ebdc3a0f1cf3126",
                "url": "https://github.com/redox-os/kernel/commit/22371bebde9446b9d51774c94ebdc3a0f1cf3126",
                "scope": "Deferred nominal-address/misalignment fixtures; IRQ rejection does not reproduce the complete UART fix."}}


@dataclass
class Case:
    name: str
    group: str
    source: str
    accepts: bool = True
    families: tuple = ()
    chain: tuple = ()
    files: dict = field(default_factory=dict)
    control: str | None = None
    vectors: tuple = ("@VECTOR@",)
    signal_slots: tuple = (0,)
    take_slots: tuple = ()
    target: str | None = None
    options: tuple | None = None
    provenance: str | None = None
    audit: bool = True
    normal_helper: str | None = None
    ordinary_signals: tuple = ()
    host_output: str | None = None
    message: str | None = None


def root(body="signalInterrupt(0)", vector="@VECTOR@", name="irqProof"):
    return f"interrupt function {name}(vector: Integer) handles({vector}) {{ {body} }}\n"


def ordinary(source):
    return re.sub(r"\s+handles\([^\n{}]*\)", "", source.replace("interrupt function ", "function "))


def matrix():
    cases = [Case("signal-zero", "positive", root()),
             Case("signal-last", "positive", root("signalInterrupt(255)"), signal_slots=(255,)),
             Case("last-vector", "positive", root(vector="@LAST@"), vectors=("@LAST@",)),
             Case("named-slot", "positive", "constant SLOT = 7\n" + root("signalInterrupt(SLOT)"), signal_slots=(7,)),
             Case("take-ordinary", "positive", root() + "let observed = takeInterrupt(0)\n", take_slots=(0,)),
             Case("coalescing-stores", "positive", root("signalInterrupt(0); signalInterrupt(0)") + "let first = takeInterrupt(0)\nlet second = takeInterrupt(0)\n", signal_slots=(0, 0), take_slots=(0, 0)),
             Case("scalar-branches", "positive", root("let value = wrappingAdd(vector & 255, 1); if value == 0 { signalInterrupt(0) } else { signalInterrupt(255) }"), signal_slots=(0, 255))]
    cases.extend([
        Case("boolean-locals", "positive", root("let ready: Boolean = vector != 0; let copied: Boolean = ready; if copied { signalInterrupt(0) }")),
        Case("character-locals", "positive", root("let marker: Character = 'λ'; let copied: Character = marker; if copied == 'λ' { signalInterrupt(0) }")),
        Case("short-circuit-and-phi", "positive", root("let ready = vector != 0 && vector < 48; if ready { signalInterrupt(0) }")),
        Case("short-circuit-or-phi", "positive", root("let ready = vector == 0 || vector > 15; if ready { signalInterrupt(0) }")),
        Case("both-return-ifelse", "positive", root("if vector == 0 { signalInterrupt(0); return } else { signalInterrupt(255); return }"), signal_slots=(0, 255)),
        Case("literal-dead-merge", "positive", root("if true { return } else { return }"), signal_slots=()),
        Case("named-scalar-constant", "positive", "constant MASK = 255\n" + root("let value = vector & MASK; if value != 0 { signalInterrupt(0) }")),
        Case("raw-private-layout-field-fits", "positive", 'constant FIRST = 4\nrecord Control native #"register32"# { private threshold: Integer at(FIRST, 3) }\n' + root('let ready = fieldFits(Control, "threshold", vector); if ready { signalInterrupt(0) }')),
    ])
    shared = "function sharedScalar(value: Integer): Integer { return wrappingAdd(value & 255, 1) }\n"
    tail = "let normal = sharedScalar(5)\n"
    cases.append(Case("shared-helper-clone", "positive", shared + root("let value = sharedScalar(vector); if value != 0 { signalInterrupt(0) }") + tail,
                      control=shared + tail, normal_helper=".minyar.fn.sharedScalar"))
    cases.append(Case("scalar-import", "positive", 'use "./helper.min" as helper\n' + root("let value = helper.scalar(vector); if value != 0 { signalInterrupt(0) }"),
                      files={"helper.min": "public function scalar(value: Integer): Integer { return wrappingAdd(value, 1) }\n"}))
    cases.append(Case("scalar-import-space-unicode", "positive", 'use "./scalar café clock.min" as clock\n' + root("let value = clock.scalar(vector); if value != 0 { signalInterrupt(0) }"),
                      files={"scalar café clock.min": "public function scalar(value: Integer): Integer { return wrappingAdd(value, 1) }\n"}))
    cases.append(Case("unreachable-ordinary-effects", "positive",
                      "function unused(value: Integer): Text { let values = [value]; let floating = 1.5; while false {}; return Text(values[0]) }\n" + root()))

    # Every effect case has a plain function control and direct/helper/import
    # variants. A parser/type failure in that control invalidates the fixture.
    effects = [
        ("format-allocation", "", "let text = Text(vector)", ("alloc", "managed", "runtime", "Text"), "allocation"),
        ("bytes-allocation", "", "let bytes = Bytes(8)", ("alloc", "managed", "Bytes"), "allocation"),
        ("list-allocation", "", "let values = [vector]", ("alloc", "managed", "List"), "allocation"),
        ("record-allocation", "record Item { value: Integer }\n", "let item = Item { value: vector }", ("alloc", "managed", "record"), "allocation"),
        ("float-state", "", "let value = Float(vector)", ("Float", "scalar", "floating"), None),
        ("checked-overflow", "", "let value = vector + 1", ("overflow", "failure", "runtime", "checked"), None),
        ("checked-division", "", "let value = 10 / vector", ("division", "failure", "runtime", "checked"), None),
        ("explicit-failure", "", 'fail("bad IRQ")', ("fail", "runtime", "managed", "alloc"), None),
        ("sleep", 'function sleepNanoseconds(value: Integer) { native "system" }\n', "sleepNanoseconds(vector)", ("block", "native", "runtime", "sleep"), "sleep"),
        ("serialization-lock", 'function takeProcessLock() { native "sync" }\n', "takeProcessLock()", ("lock", "native", "runtime"), "lock"),
        ("safe-looking-native", 'function harmless(value: Integer): Integer { native "irqproof" }\n', "let value = harmless(vector)", ("native", "unknown", "runtime"), None),
        ("runtime-provider-name", 'function harmless(value: Integer): Integer { native "runtime" }\n', "let value = harmless(vector)", ("native", "unknown", "runtime"), None),
        ("loop-built-lock", "", "let waiting = true; while waiting { waiting = vector == 0 }", ("loop", "backedge", "bound", "cycle"), "lock"),
        ("range-loop", "", "for item in 0..4 { let value = item & vector }", ("loop", "backedge", "bound", "cycle"), None),
        ("global-scalar", "global shared: Integer = 1\n", "let value = shared", ("global", "initializer"), None),
        ("managed-global", 'global shared: Text = "managed"\n', "let value = shared", ("global", "managed", "Text"), "allocation"),
        ("raw-call-entry", 'use "machine" as machine\n', "machine.callEntry(vector, 0, 0)", ("indirect", "native", "machine", "runtime", "callEntry"), None),
        ("raw-jump", 'use "machine" as machine\n', "machine.jump(vector, 0)", ("indirect", "native", "machine", "runtime", "jump"), None),
        ("raw-atomic-lock", 'use "machine" as machine\n', "let value = machine.atomicAdd(vector, 1)", ("atomic", "native", "machine", "runtime"), "lock"),
        ("raw-address-load", 'use "machine" as machine\n', "let value = machine.load64(vector)", ("address", "native", "machine", "runtime"), None),
    ]
    for name, declarations, body, families, provenance in effects:
        direct = declarations + root(body)
        cases.append(Case(name + "-direct", "effect", direct, False, families,
                          control=ordinary(direct), provenance=provenance))
        helpers = declarations + "function leaf(argument: Integer) { " + body.replace("vector", "argument") + " }\nfunction middle(argument: Integer) { leaf(argument) }\n"
        helper = helpers + root("middle(vector)")
        cases.append(Case(name + "-helper", "effect", helper, False, families,
                          chain=("irqProof", "middle", "leaf"), control=ordinary(helper), provenance=provenance))
        module = declarations + "public function leaf(vector: Integer) { " + body + " }\n"
        imported = 'use "./effect.min" as effect\nfunction middle(value: Integer) { effect.leaf(value) }\n' + root("middle(vector)")
        cases.append(Case(name + "-import", "effect", imported, False, families,
                          chain=("irqProof", "middle", "leaf"), files={"effect.min": module},
                          control=ordinary(imported), provenance=provenance))

    for name, helpers in (
            ("self-recursion", "function recurse(value: Integer) { recurse(value) }\n"),
            ("mutual-recursion", "function recurse(value: Integer) { other(value) }\nfunction other(value: Integer) { recurse(value) }\n")):
        source = helpers + root("recurse(vector)")
        cases.append(Case(name, "effect", source, False, ("recurs", "cycle", "acyclic"),
                          chain=("irqProof", "recurse"), control=ordinary(source)))
    callback = "let callback: Callback<Integer, Integer> = function(value: Integer): Integer { return value }; let ignored = callback(vector)"
    cases.append(Case("indirect-callback", "effect", root(callback), False,
                      ("indirect", "callback", "managed", "alloc"), control=ordinary(root(callback))))
    for name, body in (("literal-dead-managed-branch", "if false { let values = Bytes(8) }"),
                       ("literal-dead-indirect-branch", "if false { " + callback + " }")):
        source = root(body)
        cases.append(Case(name, "effect", source, False,
                          ("indirect", "callback", "managed", "alloc", "source node"), control=ordinary(source)))
    guarded = 'function sleepNanoseconds(value: Integer) { native "system" }\n' + root("if vector != 0 { sleepNanoseconds(vector) }")
    cases.append(Case("runtime-context-guard-does-not-prove-safety", "effect", guarded, False,
                      ("block", "native", "sleep", "runtime"), control=ordinary(guarded), provenance="sleep"))

    for signature in ("()", "(vector: Boolean)", "(vector: Float)", "(vector: Integer, extra: Integer)", "(vector: Text)"):
        cases.append(Case("root-signature-" + str(len(cases)), "signature",
                          f"interrupt function irqProof{signature} handles(@VECTOR@) {{}}\n", False,
                          ("signature", "Integer", "parameter", "argument")))
    for suffix, source in (
            ("return", "interrupt function irqProof(vector: Integer): Integer handles(@VECTOR@) { return vector }\n"),
            ("generic", "interrupt function irqProof<Item>(vector: Integer) handles(@VECTOR@) {}\n"),
            ("method", "record Device { value: Integer }\ninterrupt function Device.irqProof(vector: Integer) handles(@VECTOR@) {}\n"),
            ("native", 'interrupt function irqProof(vector: Integer) handles(@VECTOR@) { native "irqproof" }\n'),
            ("main", "interrupt function main(vector: Integer) handles(@VECTOR@) {}\n")):
        cases.append(Case("root-" + suffix, "signature", source, False, (suffix, "signature", "handler", "root")))
    cases.append(Case("duplicate-vector", "signature", root() + root(name="otherIrq"), False,
                      ("duplicate", "already", "vector", "more than once")))
    for target, invalid in (("x86_64", (-1, 0, 31, 48, 1019, 9223372036854775807)),
                            ("arm64", (-1, 0, 15, 1020, 1023, 9223372036854775807))):
        for vector in invalid:
            cases.append(Case(f"vector-{target}-{vector}", "signature", root(vector=str(vector)), False,
                              ("vector", "range", "maskable"), target=target))
    for operand in ("32.0", "true", "vector"):
        cases.append(Case("nonconstant-vector-" + operand, "signature", root(vector=operand), False,
                          ("constant", "Integer", "vector")))
    for operation in ("signalInterrupt", "takeInterrupt"):
        for slot in ("-1", "256", "vector", "0.0", "true"):
            body = f"{operation}({slot})" if operation == "signalInterrupt" else f"let value = {operation}({slot})"
            source = root(body) if operation == "signalInterrupt" else "function ordinaryTake(vector: Integer) { " + body + " }\n"
            cases.append(Case(operation + "-slot-" + slot, "flags", source, False,
                              ("constant", "slot", "range", "Integer"), vectors=() if operation == "takeInterrupt" else ("@VECTOR@",)))
    cases.append(Case("take-forbidden-in-irq", "flags", root("let value = takeInterrupt(0)"), False,
                      ("ordinary", "take", "context", "acquire")))
    cases.append(Case("ordinary-coalescing-flags", "flags", "signalInterrupt(0)\nsignalInterrupt(0)\nprint(takeInterrupt(0))\nprint(takeInterrupt(0))\nsignalInterrupt(255)\nprint(takeInterrupt(255))\nprint(takeInterrupt(255))\nsignalInterrupt(0)\nprint(takeInterrupt(0))\nprint(takeInterrupt(0))\n",
                      vectors=(), signal_slots=(), take_slots=(0, 0, 255, 255, 0, 0),
                      ordinary_signals=(0, 0, 255, 0), host_output="true\nfalse\ntrue\nfalse\ntrue\nfalse\n"))
    cases.append(Case("ordinary-call-to-root", "flags", root() + "irqProof(@VECTOR@)\n", False,
                      ("call", "entry", "handler", "interrupt")))
    for name, options in (("missing-kernel-target", ("--freestanding",)),
                          ("missing-freestanding", ("--kernel-target", "@TARGET@")),
                          ("unsupported-target", ("--freestanding", "--kernel-target", "riscv64")),
                          ("duplicate-target", ("--freestanding", "--kernel-target", "@TARGET@", "--kernel-target", "@TARGET@"))):
        cases.append(Case(name, "configuration", root(), False, ("target", "freestanding", "kernel"), options=options))

    # No IRQ roots in these ordinary compatibility controls: all contextual names
    # retain ordinary function/local/global meaning, with normal arity/type rules.
    names = "function interrupt(value: Integer): Integer { return value }\nfunction handles(value: Integer): Integer { return value }\nfunction signalInterrupt(value: Integer): Integer { return value }\nfunction takeInterrupt(value: Integer): Integer { return value }\nlet value = interrupt(handles(signalInterrupt(takeInterrupt(7))))\n"
    cases.append(Case("ordinary-named-functions", "compatibility", names, vectors=(), signal_slots=(), audit=False))
    for name in ("interrupt", "handles", "signalInterrupt", "takeInterrupt"):
        cases.append(Case("local-name-" + name, "compatibility", f"let {name}: Callback<Integer, Integer> = function(value: Integer): Integer {{ return value }}\nlet result = {name}(7)\n", vectors=(), signal_slots=(), audit=False))
        cases.append(Case("global-name-" + name, "compatibility", f"global {name}: Callback<Integer, Integer> = function(value: Integer): Integer {{ return value }}\nlet result = {name}(7)\n", vectors=(), signal_slots=(), audit=False))
    cases.append(Case("handles-name-keeps-marker", "compatibility", "function handles(value: Integer): Integer { return value }\n" + root(), signal_slots=(0,)))
    for name in ("signalInterrupt", "takeInterrupt"):
        source = f"function {name}(value: Integer): Integer {{ return wrappingAdd(value, 1) }}\n" + root(f"let value = {name}(vector)")
        cases.append(Case("ordinary-helper-precedence-" + name, "compatibility", source, signal_slots=()))
        shadow = f"let {name}: Callback<Integer, Integer> = function(value: Integer): Integer {{ return value }}; let result = {name}(0)"
        source = root(shadow)
        cases.append(Case("local-shadow-cannot-bypass-effects-" + name, "compatibility", source, False,
                          ("indirect", "callback", "managed", "alloc"), control=ordinary(source)))
    # A handler reads and acknowledges its device through fixed-width MMIO
    # and (x86) port I/O; these compiler intrinsics neither allocate nor wait.
    device = 'use "machine" as machine\n'
    cases.append(Case("device-mmio-acknowledge", "positive", device + root(
        "let status = machine.read32(268435480); if (status & 16) != 0 { machine.write32(268435524, 2047) }; machine.fence(); signalInterrupt(0)")))
    cases.append(Case("device-mmio-widths", "positive", device + root(
        "let a = machine.read8(4096); let b = machine.read16(4098); let c = machine.read64(4104); machine.write8(4096, a); machine.write16(4098, b); machine.write64(4104, c)"), signal_slots=()))
    cases.append(Case("device-port-acknowledge", "positive", device + root(
        "let key = machine.in8(96); machine.out8(32, 32); if key != 0 { signalInterrupt(1) }"), signal_slots=(1,), target="x86_64"))
    cases.append(Case("device-port-on-arm64", "effect", device + root("machine.out8(32, 32)"), False,
                      ("native", "machine", "interrupt-safe"), target="arm64"))
    for name, call in (("halt", "machine.halt()"), ("wait-for-interrupt", "machine.waitForInterrupt()"),
                       ("enable-interrupts", "machine.enableInterrupts()"), ("pause-spin", "machine.pause()")):
        cases.append(Case("device-" + name, "effect", device + root(call), False, ("native", "machine", "block"),
                          control=ordinary(device + root(call))))
    # Exact plain-English reasons for representative real-bug classes.
    messages = {
        "sleep-helper": "sleepNanoseconds -> calls native code (library 'system') that the compiler cannot prove interrupt-safe; it may block, sleep",
        "serialization-lock-helper": "calls native code (library 'sync') that the compiler cannot prove interrupt-safe",
        "loop-built-lock-direct": "loops are not allowed in interrupt context: a wait or spin loop can block forever",
        "format-allocation-helper": "uses managed Text: managed values allocate and change reference counts",
        "float-state-direct": "uses Float, whose floating-point state interrupt entry does not save",
    }
    for case in cases:
        if case.name in messages:
            case.message = messages[case.name]
    if any(not any(case.name == name for case in cases) for name in messages):
        raise Failure("message expectation names an unknown case")
    return cases


LIVE_PLAN = {
    "status": "PROPOSED, NOT IMPLEMENTED OR EXECUTED",
    "common": ["Build the real compiler-produced bridge into a finite guest, not a stand-in C handler.",
               "Load distinct nonzero sentinels into every GPR, a patterned stack region, and save the exact original SP.",
               "Let a real PIT or architectural-timer interrupt arrive at several ordinary-code PCs and at O0/O2.",
               "Verify every GPR, exact restored SP, required stack alignment and all stack sentinels after return.",
               "Signal slot0 twice before consuming: take must return true then false, never an event count.",
               "Interleave one new signal between ordinary takes; it must remain observable (no load/clear lost-update race).",
               "Run with unrelated normal managed work before/after IRQ, proving clones did not mutate its instrumentation.",
               "Finite success marker plus actual accepted QEMU exit; outer timeout, panic, missing sentinel coverage fail.",
               "Retain ELF hash, tool versions, full command, serial bytes, process status and timeout bit."],
    "x86_64": ["Maskable vector32 first, slave-PIC vector40 separately to prove both PIC acknowledgments.",
               "Check rax,rbx,rcx,rdx,rsi,rdi,rbp,r8..r15; compare RFLAGS and return RIP separately.",
               "Set DF before entry; bridge must cld for the language body and iretq must restore original DF.",
               "Check SysV stack alignment at body call, disable red zone in every reachable kernel function.",
               "Processor error-code exceptions/NMI/privilege-switch stacks remain unsupported and are not exercised as IRQs."],
    "arm64": ["Use QEMU virt,gic-version=3 and actual architectural-timer PPI, not a C call to the dispatcher.",
              "Check x0..x30, exact SP, ELR_EL1/SPSR_EL1 restoration, 16-byte body stack alignment, masked nesting.",
              "Check spurious IDs1020..1023 cause no dispatch/EOI that violates GIC protocol; valid IDs are bounds checked.",
              "Vector table alignment2KiB, slot stride128 bytes; save LR and exception state before bl.",
              "FP/NEON is prohibited throughout the checked body/callees until a full vector-state contract exists."],
    "not_proved": ["A serial PASS alone does not prove QEMU exit, GPR preservation, IRQ delivery, DMA ownership or all hardware.",
                   "Existing weak leaf stubs are not the new language interrupt ABI.",
                   "No development-time speedup or whole historical kernel bug prevention is measured."]}


class Failure(Exception):
    pass


def render(text, target):
    _, first, last, _ = TARGETS[target]
    return text.replace("@VECTOR@", str(first)).replace("@LAST@", str(last)).replace("@TARGET@", target)


LLVM_TOKEN = re.compile(r'''\s+|;[^\r\n]*|(?:[@%]|c)?"(?:[^"\\\r\n]|\\[0-9a-fA-F]{2})*"|[@%][-a-zA-Z$._0-9]+|[(){}\[\],=<>:*!]|[^\s;"\\(){}\[\],=<>:*!@%]+''')


def tokens(text):
    """Lex identities/strings atomically; whitespace and comments have no facts."""
    result, position = [], 0
    while position < len(text):
        found = LLVM_TOKEN.match(text, position)
        if found is None:
            raise Failure("invalid or unterminated LLVM token near " + repr(text[position:position + 40]))
        token = found[0]
        position = found.end()
        if not token.isspace() and not token.startswith(";"):
            result.append(token)
    return result


def identifier(token):
    """LLVM identities are byte strings; decode equivalent UTF8/hex spellings."""
    name = token[1:] if token[:1] in ("@", "%") else token
    if not name.startswith('"'):
        return name
    if not name.endswith('"'):
        raise Failure("unterminated LLVM identifier")
    result = bytearray()
    position = 1
    while position < len(name) - 1:
        if name[position] == "\\":
            escaped = name[position + 1:position + 3]
            if len(escaped) != 2 or not re.fullmatch(r"[0-9a-fA-F]{2}", escaped):
                raise Failure("invalid LLVM identifier escape")
            result.append(int(escaped, 16))
            position += 3
        else:
            result.extend(name[position].encode("utf-8"))
            position += 1
    return result.decode("utf-8", errors="surrogateescape")


def balanced(words, start, opening, closing):
    if start >= len(words) or words[start] != opening:
        raise Failure("missing LLVM " + opening)
    depth = 1
    position = start + 1
    while position < len(words):
        depth += (words[position] == opening) - (words[position] == closing)
        if depth == 0:
            return position
        position += 1
    raise Failure("unterminated LLVM " + opening)


def functions(ir):
    words, result, position = tokens(ir), {}, 0
    while position < len(words):
        if words[position] != "define":
            position += 1
            continue
        first = position
        while position < len(words) and not words[position].startswith("@"):
            position += 1
        if position == len(words):
            raise Failure("LLVM definition has no global identity")
        name = identifier(words[position])
        closing = balanced(words, position + 1, "(", ")")
        opening = closing + 1
        while opening < len(words) and words[opening] != "{":
            opening += 1
        end = balanced(words, opening, "{", "}")
        if name in result:
            raise Failure("duplicate LLVM definition: " + name)
        result[name] = (" ".join(words[first:opening + 1]), " ".join(words[opening + 1:end]))
        position = end + 1
    return result


def direct_calls(words):
    calls = []
    for position, token in enumerate(words):
        if token != "call":
            continue
        end = position + 1
        while end < len(words) and words[end] != "(" and words[end][:1] not in ("@", "%"):
            end += 1
        if end >= len(words) or not words[end].startswith("@") or words[end + 1:end + 2] != ["("]:
            raise Failure("indirect or unexplained LLVM call")
        calls.append((identifier(words[end]), end))
    return calls


def flag_operations(words, strict=False):
    addresses, stores, takes, global_uses = {}, [], [], set()
    for position, token in enumerate(words):
        if token != "getelementptr":
            continue
        cursor = position + 1
        if words[cursor:cursor + 1] == ["inbounds"]:
            cursor += 1
        expected = ["[", "256", "x", "i8", "]", ",", "ptr"]
        if words[cursor:cursor + 7] != expected or cursor + 13 >= len(words):
            if strict:
                raise Failure("unclassified IRQ pointer arithmetic")
            continue
        global_position = cursor + 7
        target = words[global_position]
        if not target.startswith("@") or identifier(target) != PENDING:
            if strict:
                raise Failure("IRQ pointer arithmetic outside pending flags")
            continue
        if words[cursor + 8:cursor + 13] != [",", "i64", "0", ",", "i64"]:
            raise Failure("invalid pending flag address indices")
        literal = words[cursor + 13]
        if not re.fullmatch(r"[0-9]+", literal) or not 0 <= int(literal) <= 255:
            raise Failure("pending flag address is not a static slot0..255")
        if position < 2 or words[position - 1] != "=" or not words[position - 2].startswith("%"):
            raise Failure("pending address must be an SSA value")
        addresses[identifier(words[position - 2])] = int(literal)
        global_uses.add(global_position)
    for position, token in enumerate(words):
        if token == "store" and words[position + 1:position + 2] == ["atomic"]:
            expected = ["store", "atomic", "i8", "1", ",", "ptr"]
            if words[position:position + 6] != expected or words[position + 7:position + 11] != ["release", ",", "align", "1"]:
                raise Failure("signal is not an aligned release byte1 store")
            pointer = words[position + 6]
            if not pointer.startswith("%") or identifier(pointer) not in addresses:
                raise Failure("signal pointer is not a proved static pending slot")
            stores.append(addresses[identifier(pointer)])
        if token == "atomicrmw":
            if strict:
                raise Failure("ordinary take/arbitrary RMW reached from IRQ")
            if words[position:position + 3] != ["atomicrmw", "xchg", "ptr"] or words[position + 4:position + 11] != [",", "i8", "0", "acquire", ",", "align", "1"]:
                raise Failure("take is not an aligned acquire byte0 exchange")
            if position < 2 or words[position - 1] != "=":
                raise Failure("take result is missing")
            pointer, result = words[position + 3], identifier(words[position - 2])
            if not pointer.startswith("%") or identifier(pointer) not in addresses:
                raise Failure("take pointer is not a proved static pending slot")
            converted = any(words[index:index + 3] == ["icmp", "ne", "i8"] and
                            words[index + 3].startswith("%") and identifier(words[index + 3]) == result and
                            words[index + 4:index + 6] == [",", "0"]
                            for index in range(max(0, len(words) - 5)))
            if not converted:
                raise Failure("take byte result is not converted to Boolean")
            takes.append(addresses[identifier(pointer)])
    return stores, takes, global_uses


def address_enabled(flags):
    enabled = False
    for flag in flags:
        if flag.startswith("-fsanitize=") and "address" in flag.split("=", 1)[1].split(","):
            enabled = True
        if flag.startswith("-fno-sanitize=") and set(flag.split("=", 1)[1].split(",")) & {"address", "all"}:
            enabled = False
    return enabled


def no_cycle(edges, label):
    active, done = set(), set()

    def visit(node):
        if node in active:
            raise Failure(label + " cycle: " + str(node))
        if node in done:
            return
        active.add(node)
        for child in edges.get(node, ()):
            visit(child)
        active.remove(node)
        done.add(node)
    for node in edges:
        visit(node)


def device_templates(target):
    """Exact compiler-generated device intrinsic bodies an IRQ graph may call.
    Independent of the compiler: one volatile access, port access or fence."""
    result = {}
    for width in ("8", "16", "32", "64"):
        kind = "i" + width
        extend = f"%value = zext {kind} %loaded to i64" if width != "64" else "%value = add i64 %loaded, 0"
        narrow = f"%narrow = trunc i64 %argument.1 to {kind}" if width != "64" else "%narrow = add i64 %argument.1, 0"
        result["read" + width] = (f"%address = inttoptr i64 %argument.0 to ptr\n%loaded = load volatile {kind}, ptr %address, align 1\n"
                                  f"{extend}\nret i64 %value\n")
        result["write" + width] = (f"%address = inttoptr i64 %argument.0 to ptr\n{narrow}\n"
                                   f"store volatile {kind} %narrow, ptr %address, align 1\nret void\n")
    result["fence"] = "fence seq_cst\nret void\n"
    if target == "arm64":
        result["fence-arm64"] = 'call void asm sideeffect "dmb sy", "~{memory}"()\nret void\n'
    if target == "x86_64":
        clobbers = "~{dirflag},~{fpsr},~{flags}"
        for width, register, suffix in (("8", "al", "b"), ("16", "ax", "w"), ("32", "eax", "l")):
            kind = "i" + width
            result["in" + width] = (f'%port = trunc i64 %argument.0 to i16\n%loaded = call {kind} asm sideeffect "in{suffix} $1, $0", '
                                    f'"={{{register}}},{{dx}},{clobbers}"(i16 %port)\n%value = zext {kind} %loaded to i64\nret i64 %value\n')
            result["out" + width] = (f"%port = trunc i64 %argument.0 to i16\n%narrow = trunc i64 %argument.1 to {kind}\n"
                                     f'call void asm sideeffect "out{suffix} $0, $1", "{{{register}}},{{dx}},{clobbers}"({kind} %narrow, i16 %port)\nret void\n')
    return {name: tokens("entry:\n" + body) for name, body in result.items()}


def device_intrinsic(definitions, callee, target):
    """The callee is an ordinary compiled machine intrinsic with an exact body."""
    if callee not in definitions:
        return False
    header, body = definitions[callee]
    words = tokens(body)
    signature = tokens(header)
    if "internal" not in signature or "alwaysinline" not in signature:
        return False
    return any(words == template and callee.endswith("_" + name.split("-")[0]) for name, template in device_templates(target).items())


def audit_ir(ir, case, target):
    definitions = functions(ir)
    metadata = re.findall(r"^; minyar-interrupt: vector=(\d+) root=(\d+) clone=(\S+) target=(\S+)\s*$", ir, re.MULTILINE)
    expected_vectors = sorted(int(render(str(value), target)) for value in case.vectors)
    if sorted(int(row[0]) for row in metadata) != expected_vectors:
        raise Failure("root/vector metadata is absent, duplicated or different from the source fixture")
    roots = []
    for vector, origin, clone, recorded_target in metadata:
        if recorded_target != target or clone != ".minyar.irq.body." + origin:
            raise Failure("IRQ root identity/target metadata mismatch")
        if clone not in definitions:
            raise Failure("root metadata names no actual clone definition")
        roots.append(clone)
    if case.signal_slots or case.take_slots or case.ordinary_signals:
        module = tokens(ir)
        declarations = [position for position, word in enumerate(module) if word.startswith("@") and identifier(word) == PENDING and module[position + 1:position + 2] == ["="]]
        expected = ["=", "internal", "global", "[", "256", "x", "i8", "]", "zeroinitializer", ",", "align", "1"]
        if len(declarations) != 1 or module[declarations[0] + 1:declarations[0] + 13] != expected:
            raise Failure("pending flags must be a private, statically zeroed 256-byte array")
    edges, visited, signal_slots = {}, set(), []
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        header, body = definitions[name]
        signature, words = tokens(header), tokens(body)
        if set(signature) & {"ptr", "...", "half", "bfloat", "float", "double", "fp128", "x86_fp80", "<"}:
            raise Failure("non-scalar IRQ clone signature: " + header)
        global_position = next(index for index, word in enumerate(signature) if word.startswith("@"))
        if name in roots and (signature[global_position - 1] != "void" or
                              signature[global_position + 1:global_position + 3] != ["(", "i64"] or
                              not signature[global_position + 3].startswith("%") or
                              signature[global_position + 4] != ")"):
            raise Failure("IRQ root clone must be exactly (i64)->void")
        if target == "x86_64" and "noredzone" not in signature:
            raise Failure("reachable x86 IRQ clone lacks noredzone: " + name)
        if set(words) & {"half", "bfloat", "float", "double", "fp128", "x86_fp80", "fadd", "fsub", "fmul", "fdiv", "frem", "fptrunc", "fpext", "sitofp", "uitofp", "<"}:
            raise Failure("FP/vector instruction or type in IRQ graph: " + name)
        if set(words) & {"invoke", "callbr", "indirectbr", "landingpad", "resume", "catchswitch"}:
            raise Failure("indirect/recovery control flow in IRQ graph: " + name)
        if set(words) & {"ptrtoint", "inttoptr", "asm", "cmpxchg"}:
            raise Failure("raw address/assembly/RMW escape in IRQ graph")
        stores, _, allowed_globals = flag_operations(words, strict=True)
        signal_slots.extend(stores)
        local_edges, calls = {}, direct_calls(words)
        for callee, position in calls:
            # The frozen first policy permits no llvm.* intrinsic, even pure
            # sounding ones. Never replace proof with a wildcard name exception.
            if device_intrinsic(definitions, callee, target):
                allowed_globals.add(position)
                continue
            if not callee.startswith(".minyar.irq.body.") or callee not in definitions:
                raise Failure("unclassified/non-cloned callee in IRQ graph: " + name + " -> " + callee)
            edges.setdefault(name, []).append(callee)
            pending.append(callee)
            allowed_globals.add(position)
        block = "entry"
        for position, word in enumerate(words):
            if words[position + 1:position + 2] == [":"] and not word.startswith(("@", "%")):
                block = identifier(word)
            local_edges.setdefault(block, [])
            if word == "label" and position + 1 < len(words) and words[position + 1].startswith("%"):
                local_edges[block].append(identifier(words[position + 1]))
            if word.startswith("@") and position not in allowed_globals:
                raise Failure("global/unknown pointer reference in IRQ graph: " + word)
            if word in ("alloca", "load", "store") and words[position + 1:position + 2] in (["ptr"], ["["], ["{"]):
                raise Failure("managed/aggregate stack or memory operation in IRQ graph")
        no_cycle(local_edges, "LLVM backedge in " + name)
    no_cycle(edges, "IRQ call graph")
    if sorted(signal_slots) != sorted(case.signal_slots):
        raise Failure("IRQ release-store slots/count differ from actual source operations")
    if case.take_slots or case.ordinary_signals:
        take_slots = []
        producer_slots = []
        # All ordinary producer/take source operations in these fixtures are in
        # main. Do not count retained original IRQ bodies as ordinary producers.
        for name, (_, body) in definitions.items():
            if name == "main":
                stores, takes, _ = flag_operations(tokens(body))
                producer_slots.extend(stores)
                take_slots.extend(takes)
        if sorted(take_slots) != sorted(case.take_slots):
            raise Failure("ordinary take operations absent or different from source")
        if sorted(producer_slots) != sorted(case.ordinary_signals):
            raise Failure("ordinary producer release stores absent or different from source")
    return roots, visited


def llvm_global(name):
    return '@"' + "".join(chr(byte) if 32 <= byte < 127 and byte not in (34, 92)
                           else "\\" + format(byte, "02X") for byte in name.encode("utf-8")) + '"'


def parser_controls():
    """Synthetic parser controls only; never count these as compiler/ABI proof."""
    unusual = 'module café "clock"\\scalar'
    declaration = llvm_global(unusual)
    escaped_helper = r'@"\2Eminyar.irq.body.2"'
    called_helper = r'@".minyar.irq.body.\32"'
    body = r'''
@.minyar.irq.pending = internal global [256 x i8] zeroinitializer, align 1
define internal void @.minyar.irq.body.1 (i64 %vector) noredzone {
entry:
    call void @HELPER (i64 %vector)
    ret void
}
define internal void @DEFINITION (i64 %argument) noredzone {
entry:
    %"flag\20address" = getelementptr [256 x i8], ptr @.minyar.irq.pending, i64 0, i64 0
    store atomic i8 1, ptr %"flag address" release, align 1
    ret void
}
define i32 @main () {
entry:
    %pointer = getelementptr [256 x i8], ptr @.minyar.irq.pending, i64 0, i64 0
    %"old\20byte" = atomicrmw xchg ptr %pointer, i8 0 acquire, align 1
    %boolean = icmp ne i8 %"old byte", 0
    ret i32 0
}
define internal void @UNUSUAL () {
entry:
    ret void
}
'''.replace("@HELPER", called_helper).replace("@DEFINITION", escaped_helper).replace("@UNUSUAL", declaration)
    for target in TARGETS:
        comment = f"; minyar-interrupt: vector={TARGETS[target][1]} root=1 clone=.minyar.irq.body.1 target={target}\n"
        case = Case("parser-only", "parser", "", take_slots=(0,))
        for separator in (" ", "\t", "\n\t"):
            variant = comment + separator.join(tokens(body)) + "\n"
            if unusual not in functions(variant):
                raise Failure("escaped/Unicode LLVM identity was lost")
            roots, visited = audit_ir(variant, case, target)
            if set(roots) != {".minyar.irq.body.1"} or visited != {".minyar.irq.body.1", ".minyar.irq.body.2"}:
                raise Failure("whitespace/quoted callee changed parser reachability")
        for intrinsic in ("llvm.bswap.i64", "llvm.bitreverse.i64", "llvm.ctpop.i64"):
            mutated = body.replace("ret void", f"%unproved = call i64 @{intrinsic} (i64 1)\n ret void", 1)
            mutated += f"\ndeclare i64 @{intrinsic} (i64)\n"
            try:
                audit_ir(comment + mutated, case, target)
            except Failure as error:
                if "unclassified/non-cloned callee" not in str(error):
                    raise Failure("intrinsic parser control failed for an unrelated reason: " + str(error)) from error
            else:
                raise Failure("LLVM intrinsic name bypassed the frozen zero-intrinsic policy")


class Runner:
    def __init__(self, args, scratch):
        self.args, self.scratch, self.events = args, scratch, []

    def run(self, label, command):
        command = list(map(str, command))
        start = time.monotonic()
        process = subprocess.Popen(command, cwd=self.args.root, env=os.environ.copy(),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding="utf-8", errors="replace", start_new_session=True)
        timed_out = False
        try:
            output, errors = process.communicate(timeout=self.args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self.kill(process)
            output, errors = process.communicate()
        finally:
            if process.poll() is None:
                self.kill(process)
                process.wait()
        status = 124 if timed_out else process.returncode
        log = self.scratch / (str(len(self.events)) + "-" + label)
        log.with_suffix(".stdout").write_text(output)
        log.with_suffix(".stderr").write_text(errors)
        self.events.append(dict(command=command, status=status, timed_out=timed_out,
                                seconds=time.monotonic() - start, label=label))
        (self.scratch / "events.json").write_text(json.dumps(self.events, indent=2) + "\n")
        if timed_out or re.search(r"Sanitizer|runtime error:|Segmentation fault|LLVM ERROR", errors):
            raise Failure(label + ": timeout/internal/sanitizer failure\n" + errors)
        return status, output, errors

    @staticmethod
    def kill(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def compile(self, case, target, control=False):
        directory = self.scratch / (target + "-" + case.name)
        directory.mkdir(exist_ok=True)
        for name, text in case.files.items():
            (directory / name).write_text(render(text, target))
        source = directory / ("control.min" if control else "case.min")
        source.write_text(render(case.control if control else case.source, target))
        llvm = source.with_suffix(".ll")
        options = case.options if case.options is not None else ("--freestanding", "--kernel-target", "@TARGET@")
        command = [self.args.compiler, source, llvm, *[render(option, target) for option in options],
                   "--library", self.args.root / "library"]
        status, output, errors = self.run(target + "-" + case.name + ("-control" if control else ""), command)
        if control or case.accepts:
            if status or output or errors or not llvm.is_file():
                raise Failure(case.name + ": positive/ordinary control failed\n" + output + errors)
            return llvm.read_text()
        if status != 1 or output or llvm.exists() or not errors.strip():
            raise Failure(case.name + ": rejection must be diagnostic status1 with no LLVM\n" + output + errors)
        lower = errors.lower()
        if case.group != "configuration" and not any(word in lower for word in ("interrupt", "irq", "handler")):
            raise Failure(case.name + ": unrelated rejection cannot prove IRQ checking\n" + errors)
        if not any(word.lower() in lower for word in case.families):
            raise Failure(case.name + ": missing expected diagnostic family\n" + errors)
        if any(name.lower() not in lower for name in case.chain):
            raise Failure(case.name + ": missing transitive root-to-effect chain\n" + errors)
        if case.message and case.message not in errors:
            raise Failure(case.name + ": diagnostic must explain the rule: " + case.message + "\n" + errors)
        return None

    def assembly(self, case, target, ir, roots):
        # ABI generation is not implemented. Require actual entry definitions;
        # a successful compile of ordinary clone functions is not an ABI proof.
        definitions = functions(ir)
        entries = ["irq_" + render(str(vector), target) for vector in case.vectors] if target == "x86_64" else ["minyar_irq_dispatch"]
        if any(entry not in definitions for entry in entries):
            raise Failure("ABI DEFERRED: required actual entry bridge absent: " + ", ".join(entries))
        if target == "x86_64" and any("x86_intrcc" not in definitions[entry][0] for entry in entries):
            raise Failure("x86 bridge must be an actual x86_intrcc definition")
        directory = self.scratch / (target + "-" + case.name)
        llvm = directory / "case.ll"
        for level in ("O0", "O2"):
            assembly = directory / (level + ".s")
            flags = ["-mno-red-zone", "-mgeneral-regs-only"] if target == "x86_64" else ["-mgeneral-regs-only"]
            command = [self.args.clang, "--target=" + TARGETS[target][3], *flags, "-" + level,
                       "-S", "-x", "ir", "-Wno-override-module", llvm, "-o", assembly]
            status, output, errors = self.run(target + "-" + case.name + "-" + level, command)
            if status or not assembly.is_file():
                raise Failure("cross-assembly failed\n" + output + errors)
            text = assembly.read_text()
            # Inspect actual instruction lines. This catches accidental FP/NEON
            # in the whole generated probe, not merely an 'fadd' spelling in IR.
            if target == "x86_64":
                if re.search(r"%[xyz]mm\d+|\b(?:fld|fst|fadd|fxsave|fxrstor)\w*\b", text):
                    raise Failure("FP/SIMD instructions in general-register-only probe")
                for entry in entries:
                    body = re.search(r"^" + re.escape(entry) + r":[^\n]*\n(.*?)^\s*\.size\s+" + re.escape(entry) + r"\s*,", text, re.MULTILINE | re.DOTALL)
                    if body is None or not re.search(r"^\s*iretq\s*$", body[1], re.MULTILINE):
                        raise Failure("actual x86 entry lacks iretq epilogue")
                    if not re.search(r"^\s*cld\s*$", body[1], re.MULTILINE):
                        raise Failure("actual x86 entry does not clear DF before language calls")
            elif re.search(r"^\s*(?:f[a-z0-9]+\s|[a-z0-9]+\s+v\d+[.\s,])", text, re.MULTILINE):
                raise Failure("FP/NEON instruction in Arm general-register-only probe")
        # Arm's dispatch is ordinary ABI code. eret/vector-table/GPR/ELR/SPSR
        # preservation lives in the real head.S bridge and still needs live proof.
        print("cross-assembly subset passed; full register/stack/entry proof remains LIVE-PLAN", flush=True)

    def host_flags(self, case, target):
        if case.host_output is None or case.vectors:
            raise Failure("host-flags runs only the ordinary atomic fixture; IRQ roots are never called as ordinary functions")
        directory = self.scratch / (target + "-" + case.name)
        llvm = directory / "case.ll"
        flags = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))
        # Compiler sanitizer and hosted flag runtime sanitizer are distinct from
        # the freestanding IRQ ABI, which has no sanitizer callback contract.
        if address_enabled(flags):
            text = llvm.read_text()
            instrumented = []
            for line in text.splitlines(keepends=True):
                if line.startswith("define ") and "sanitize_address" not in line:
                    if not line.rstrip().endswith("{"):
                        raise Failure("unsupported hosted LLVM header for ASan annotation")
                    brace = line.rfind("{")
                    line = line[:brace] + "sanitize_address " + line[brace:]
                instrumented.append(line)
            llvm.write_text("".join(instrumented))
        for level in ("O0", "O2"):
            program = directory / ("host-" + level)
            status, output, errors = self.run(target + "-host-link-" + level,
                [self.args.clang, "-" + level, *flags, "-Wno-override-module", llvm,
                 self.args.runtime, "-lm", "-o", program])
            if status:
                raise Failure("hosted atomic fixture failed to link\n" + output + errors)
            status, output, errors = self.run(target + "-host-run-" + level, [program])
            if status or output != case.host_output or errors:
                raise Failure("ordinary flags did not coalesce/consume/re-signal correctly\n" + output + errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--phase", choices=("matrix", "parser", "compile", "ir", "assembly", "host-flags", "live-plan"), default="matrix")
    parser.add_argument("--target", action="append", choices=tuple(TARGETS))
    parser.add_argument("--case", action="append", help="case glob; narrowest first, e.g. sleep-helper")
    parser.add_argument("--compiler", default=os.environ.get("MINYAR_TEST_COMPILER", ""))
    parser.add_argument("--clang", default=os.environ.get("MINYAR_TEST_CLANG", ""))
    parser.add_argument("--runtime", default=os.environ.get("MINYAR_TEST_RUNTIME", "build/minyar-runtime.o"))
    parser.add_argument("--sanitized-compiler", action="store_true", help="select already-built build/minyarc-sanitize, never instruments IRQ code")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--artifacts", type=Path, help="empty external directory; success retains it")
    args = parser.parse_args()
    cases = [case for case in matrix() if not args.case or any(fnmatch.fnmatchcase(case.name, pattern) for pattern in args.case)]
    if args.phase == "host-flags":
        cases = [case for case in cases if case.host_output is not None]
    if not cases:
        parser.error("no matrix cases selected")
    if args.phase == "live-plan":
        print(json.dumps(LIVE_PLAN, indent=2))
        return 0
    if args.phase == "matrix":
        print(json.dumps(dict(status="DESIGN ONLY; no compiler/ABI test executed", cases=[asdict(case) for case in cases], provenance=PROVENANCE), indent=2))
        return 0
    if args.phase in ("parser", "ir", "assembly", "host-flags"):
        parser_controls()
    if args.phase == "parser":
        print("synthetic LLVM whitespace/identity/intrinsic parser controls passed; no compiler/ABI execution", flush=True)
        return 0
    if not 0 < args.timeout <= 3600:
        parser.error("timeout must be finite, positive and at most3600s")
    args.root = args.root.resolve()
    selected = args.compiler or str(args.root / ("build/minyarc-sanitize" if args.sanitized_compiler else "build/minyarc"))
    args.compiler = shutil.which(selected)
    if args.compiler is None:
        raise Failure("selected existing compiler is missing; this runner never builds it")
    if args.phase in ("assembly", "host-flags"):
        args.clang = shutil.which(args.clang) if args.clang else None
        if args.clang is None:
            raise Failure("select pinned existing Clang with MINYAR_TEST_CLANG or --clang")
    if args.phase == "host-flags":
        args.runtime = Path(args.runtime)
        if not args.runtime.is_absolute():
            args.runtime = args.root / args.runtime
        if not args.runtime.is_file():
            raise Failure("selected actual runtime object is missing; no runtime build is launched")
    parent = (args.artifacts.parent if args.artifacts else Path(tempfile.gettempdir())).resolve()
    if parent == args.root or args.root in parent.parents:
        raise Failure("generated test data must remain outside product checkout")
    if args.artifacts:
        scratch = args.artifacts.resolve()
        if scratch == args.root or args.root in scratch.parents:
            raise Failure("artifacts cannot be inside product checkout")
        scratch.mkdir(parents=True, exist_ok=True)
        if any(scratch.iterdir()):
            raise Failure("artifacts directory must be empty")
    else:
        scratch = Path(tempfile.mkdtemp(prefix="minyar-irq-", dir=parent))
    passed = False
    try:
        (scratch / "matrix.json").write_text(json.dumps([asdict(case) for case in cases], indent=2) + "\n")
        (scratch / "live-plan.json").write_text(json.dumps(LIVE_PLAN, indent=2) + "\n")
        runner = Runner(args, scratch)
        count = 0
        for target in args.target or TARGETS:
            for case in cases:
                if case.target and case.target != target:
                    continue
                control = runner.compile(case, target, True) if case.control else None
                ir = runner.compile(case, target)
                if ir is not None and case.audit and args.phase in ("ir", "assembly", "host-flags"):
                    roots, visited = audit_ir(ir, case, target)
                    if case.normal_helper:
                        original = functions(control).get(case.normal_helper)
                        normal = functions(ir).get(case.normal_helper)
                        if original is None or normal != original or case.normal_helper in visited:
                            raise Failure("IRQ proof changed the shared ordinary helper body")
                    if args.phase == "assembly" and roots:
                        runner.assembly(case, target, ir, roots)
                    if args.phase == "host-flags":
                        runner.host_flags(case, target)
                count += 1
        print(f"{args.phase}: {count} selected cases passed; ABI/live proof is separate", flush=True)
        passed = True
        return 0
    finally:
        if passed and not args.artifacts:
            shutil.rmtree(scratch)
        else:
            print("IRQ artifacts: " + str(scratch), file=sys.stderr)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Failure, OSError, ValueError) as error:
        print("IRQ FAILED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
