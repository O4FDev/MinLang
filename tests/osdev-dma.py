#!/usr/bin/env python3
"""Independent contract gate for affine DMA source flow and the real runtime.

No compiler is built here. Select already built candidate artifacts with
MINYAR_TEST_COMPILER, MINYAR_TEST_RUNTIME, MINYAR_TEST_CLANG and
MINYAR_TEST_LINK_FLAGS. C misuse deliberately bypasses the source checker;
it is runtime evidence, not a claim that unsafe C is statically checked.
"""

import argparse
from dataclasses import dataclass
import hashlib
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


ROOT = Path(__file__).resolve().parent.parent
GROUPS = ("compile", "control", "runtime", "sanitizer", "artifacts")
TIMEOUT = 60
MAX_CAPTURE = 1024 * 1024
LEVELS = ("-O0", "-O2")
IMPORTS = 'use "dma" as dma\nuse "dma/model" as model\n'
CHECK = '''
function check(condition: Boolean, message: Text) {
    if !condition { fail(message) }
}
'''


def program(body, declarations="", imports=True):
    return ((IMPORTS if imports else "") + CHECK + declarations + "\nfunction main(): Integer {\n" +
            body + '\nprint("DMA-PASS")\nreturn 0\n}\n')


@dataclass(frozen=True)
class Positive:
    name: str
    body: str
    declarations: str = ""
    execute: bool = True
    imports: bool = True
    options: tuple = ()
    link_flags: tuple = ()
    custom_source: str | None = None

    @property
    def source(self):
        if self.custom_source is not None:
            return self.custom_source
        return program(self.body, self.declarations, self.imports)


PREPARE = '''
function prepare(cpu: dma.Cpu): dma.Cpu {
    dma.store8(cpu, 0, 41)
    return cpu
}
'''
IDENTITY = 'function identity<Item>(value: Item): Item { return value }\n'
USER_LOAD = '''
function load8(cpu: dma.Cpu): Integer {
    let answer = dma.load8(cpu, 0)
    dma.dispose(cpu)
    return answer
}
'''
DMA_METER_METHOD = '''
record Meter { value: Integer }
function Meter.read(): Integer {
    let cpu = dma.allocate(16, 16)
    dma.store8(cpu, 0, self.value)
    let answer = dma.load8(cpu, 0)
    dma.dispose(cpu)
    return answer
}
'''
POSITIVES = (
    Positive("cpu-borrow", '''
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 17)
dma.store8(cpu, 15, 255)
check(dma.load8(cpu, 0) == 17, "first byte")
check(dma.load8(cpu, 15) == 255, "last byte")
dma.dispose(cpu)
'''),
    Positive("model-roundtrip", '''
let queue = model.modelQueue()
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 17)
dma.store8(cpu, 1, 23)
let copy = dma.copyOut(cpu, 0, 2)
check(copy.length == 2 && copy[0] == 17 && copy[1] == 23, "initial copy")
let pending = dma.submit(queue, cpu, 16)
check(!dma.ready(pending), "IRQ or elapsed time is not a CQ witness")
check(!dma.ready(pending), "poll before completion remains false")
let payload = Bytes(4)
payload[0] = 81
payload[1] = 0
payload[2] = 254
payload[3] = 99
check(model.modelDeliver(queue, payload), "delivery accepted")
check(dma.ready(pending), "completed CQ acquired")
check(dma.ready(pending), "cached ready witness")
let finished = dma.reclaim(pending, 1)
check(dma.load8(finished, 0) == 81, "acquired first byte")
check(dma.load8(finished, 1) == 0, "acquired zero byte")
check(dma.load8(finished, 2) == 254, "acquired unsigned byte")
check(dma.load8(finished, 3) == 99, "acquired last byte")
check(copy[0] == 17 && copy[1] == 23, "copy does not alias device payload")
copy[0] = 7
check(dma.load8(finished, 0) == 81, "copy writes do not alias CPU")
dma.store8(finished, 0, 42)
check(copy[0] == 7, "CPU writes do not alias copy")
let after = dma.copyOut(finished, 0, 4)
dma.dispose(finished)
check(copy[0] == 7 && copy[1] == 23, "old copy survives disposal")
check(after.length == 4 && after[0] == 42 && after[3] == 99, "fresh copy survives disposal")
'''),
    Positive("model-zero-completion", '''
let queue = model.modelQueue()
let cpu = dma.allocate(16, 16)
let pending = dma.submit(queue, cpu, 16)
let empty = Bytes(0)
check(model.modelDeliver(queue, empty), "zero-byte completion")
check(dma.ready(pending), "zero-byte CQ is a completion")
let finished = dma.reclaim(pending, 0)
let copy = dma.copyOut(finished, 0, 0)
check(copy.length == 0, "completed CPU exposes zero bytes")
dma.dispose(finished)
'''),
    Positive("model-repeated-generations", '''
let queue = model.modelQueue()
let cpu = dma.allocate(16, 16)
let first = dma.submit(queue, cpu, 16)
let a = Bytes(1)
a[0] = 19
check(model.modelDeliver(queue, a), "first generation")
let one = dma.reclaim(first, 1)
check(dma.load8(one, 0) == 19, "first generation payload")
let second = dma.submit(queue, one, 1)
check(!dma.ready(second), "old publication does not complete next generation")
let b = Bytes(1)
b[0] = 67
check(model.modelDeliver(queue, b), "second generation")
let two = dma.reclaim(second, 1)
check(dma.load8(two, 0) == 67, "second generation payload")
let third = dma.submit(queue, two, 1)
check(!dma.ready(third), "second publication does not complete third generation")
check(model.modelDeliver(queue, a), "third generation")
let three = dma.reclaim(third, 1)
check(dma.load8(three, 0) == 19, "third generation payload")
dma.dispose(three)
'''),
    Positive("model-delivery-guards", '''
let queue = model.modelQueue()
let payload = Bytes(4)
check(!model.modelDeliver(queue, payload), "no active request")
let cpu = dma.allocate(16, 16)
let pending = dma.submit(queue, cpu, 16)
let oversized = Bytes(17)
check(!model.modelDeliver(queue, oversized), "oversized delivery is not published")
check(!dma.ready(pending), "rejected delivery cannot authorize reclaim")
check(model.modelDeliver(queue, payload), "valid delivery still works")
check(!model.modelDeliver(queue, payload), "duplicate delivery rejected")
let finished = dma.reclaim(pending, 1)
dma.dispose(finished)
check(!model.modelDeliver(queue, payload), "no active request after reclaim")
'''),
    Positive("helper-move", '''
let cpu = dma.allocate(16, 16)
cpu = prepare(cpu)
check(dma.load8(cpu, 0) == 41, "RHS transfer precedes rebinding")
let moved = cpu
check(dma.load8(moved, 0) == 41, "let alias moves")
dma.dispose(moved)
''', PREPARE),
    Positive("rebind-disposed", '''
let cpu = dma.allocate(16, 16)
let other = dma.allocate(16, 16)
dma.store8(other, 0, 73)
dma.dispose(cpu)
cpu = other
check(dma.load8(cpu, 0) == 73, "dead destination can receive a move")
dma.dispose(cpu)
'''),
    Positive("pending-helper", '''
let queue = model.modelQueue()
let cpu = dma.allocate(16, 16)
let pending = send(queue, cpu)
let bytes = Bytes(1)
bytes[0] = 31
check(model.modelDeliver(queue, bytes), "helper-owned pending delivered")
let result = collect(pending)
check(dma.load8(result, 0) == 31, "helper returns one CPU obligation")
dma.dispose(result)
''', '''
function send(queue: dma.Queue, cpu: dma.Cpu): dma.Pending {
    let pending = dma.submit(queue, cpu, 16)
    return pending
}
function collect(pending: dma.Pending): dma.Cpu {
    let cpu = dma.reclaim(pending, 1)
    return cpu
}
'''),
    Positive("if-join", '''
let cpu = dma.allocate(16, 16)
if choose(true) { cpu = prepare(cpu) } else { cpu = prepare(cpu) }
check(dma.load8(cpu, 0) == 41, "both continuing arms return ownership")
dma.dispose(cpu)
''', PREPARE + 'function choose(value: Boolean): Boolean { return value }\n'),
    Positive("early-return", '''
let first = dma.allocate(16, 16)
consume(first, true)
let second = dma.allocate(16, 16)
consume(second, false)
''', '''
function consume(cpu: dma.Cpu, early: Boolean) {
    if early { dma.dispose(cpu); return }
    dma.dispose(cpu)
}
'''),
    Positive("shadow", '''
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 13)
if true {
    let cpu = dma.allocate(16, 16)
    dma.store8(cpu, 0, 29)
    check(dma.load8(cpu, 0) == 29, "inner LCID")
    dma.dispose(cpu)
}
check(dma.load8(cpu, 0) == 13, "outer LCID remains live")
dma.dispose(cpu)
'''),
    Positive("generic-identity", '''
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 37)
let moved = identity<dma.Cpu>(cpu)
check(dma.load8(moved, 0) == 37, "concrete generic consumes and returns")
dma.dispose(moved)
''', IDENTITY),
    Positive("immutable-parameter", '''
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 53)
check(peekAndDispose(cpu) == 53, "immutable parameter has a logical ID")
''', '''
function peekAndDispose(cpu: dma.Cpu): Integer {
    let answer = dma.load8(cpu, 0)
    dma.dispose(cpu)
    return answer
}
'''),
    Positive("user-load8-consumes", '''
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 61)
check(load8(cpu) == 61, "ordinary same-name helper consumes")
''', USER_LOAD),
    Positive("retire", '''
let queue = model.modelQueue()
let cpu = dma.allocate(16, 16)
let pending = dma.submit(queue, cpu, 16)
check(!dma.ready(pending), "incomplete")
dma.retire(pending)
let late = Bytes(1)
check(!model.modelDeliver(queue, late), "retired MODEL queue refuses late delivery")
'''),
    Positive("scalar-aggregate", '''
let items: List<Integer> = [1, 2]
let box = Box { value: items[0] }
check(box.value == 1, "scalar aggregate syntax control")
''', 'record Box { value: Integer }\n'),
    Positive("scalar-capture", '''
let value = 17
let callback: () -> Integer = function() { return value }
check(callback() == 17, "scalar closure syntax control")
'''),
    Positive("scalar-global", 'check(VALUE == 17, "scalar global syntax control")\n',
             'global VALUE: Integer = 17\n'),
    Positive("ordinary-record-compare", '''
let left = Key { value: 7 }
let right = Key { value: 7 }
check(left == right, "ordinary record equality remains available")
let counts = Map<Text, Integer>()
counts["key"] = 13
check(counts["key"] == 13, "ordinary Map syntax remains available")
''', 'record Key { value: Integer }\n'),
    Positive("queue-alias-helper", '''
let queue = model.modelQueue()
let alias = relay(queue)
let cpu = dma.allocate(16, 16)
let pending = dma.submit(alias, cpu, 16)
let bytes = Bytes(1)
bytes[0] = 47
check(model.modelDeliver(queue, bytes), "Queue alias is reusable")
let finished = dma.reclaim(pending, 1)
check(dma.load8(finished, 0) == 47, "Queue parameter/return retains identity")
dma.dispose(finished)
check(!model.modelDeliver(alias, bytes), "both Queue bindings remain usable")
''', '''
function relay(queue: dma.Queue): dma.Queue {
    let alias = queue
    return alias
}
'''),
    Positive("scalar-native", 'check(true, "native signature syntax control")\n',
             'function foreign(value: Integer): Integer { native "dma_test_unknown" }\n', False),
    Positive("two-scalars", 'check(combine(2, 3) == 5, "two parameter syntax control")\n',
             'function combine(left: Integer, right: Integer): Integer { return left + right }\n'),
    Positive("scalar-loop", 'let count = 0\nwhile count < 2 { count += 1 }\ncheck(count == 2, "scalar loop")\n'),
    Positive("ordinary-thread-parallel-identifiers", 'check(thread(17) == 17 && parallel(19) == 19, "ordinary names")\n',
             'function thread(value: Integer): Integer { return value }\nfunction parallel(value: Integer): Integer { return value }\n'),
    Positive("scalar-thread-declaration", 'check(true, "worker syntax control")\n', '''
thread function worker(seed: Integer, input: FrozenBytes, channel: BytesChannel): Integer {
    return seed
}
''', execute=False, imports=False),
    Positive("irq-main-coexist", '''
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 7)
dma.dispose(cpu)
''', 'interrupt function tick(vector: Integer) handles(32) { signalInterrupt(0) }\n',
             execute=False, options=("--freestanding", "--kernel-target", "x86_64")),
    Positive("dma-main-unused-parallel-chain", '''
let cpu = dma.allocate(16, 16)
dma.store8(cpu, 0, 83)
check(dma.load8(cpu, 0) == 83, "ordinary DMA remains available")
dma.dispose(cpu)
''', '''
parallel function unrelatedLeaf(first: Integer, second: Integer): Integer {
    return first + second
}
parallel function unrelatedMiddle(first: Integer, second: Integer): Integer {
    return unrelatedLeaf(first, second)
}
parallel function unrelatedRoot(first: Integer, second: Integer) {
    let value = unrelatedMiddle(first, second)
}
'''),
    Positive("ordinary-allocate-helper-chain", 'ordinaryRoot(17, 29)\n', '''
function ordinaryLeaf(first: Integer, second: Integer): Integer {
    let cpu = dma.allocate(16, 16)
    dma.store8(cpu, 0, first)
    let value = dma.load8(cpu, 0)
    dma.dispose(cpu)
    return value
}
function ordinaryMiddle(first: Integer, second: Integer): Integer {
    return ordinaryLeaf(first, second)
}
function ordinaryRoot(first: Integer, second: Integer) {
    let value = ordinaryMiddle(first, second)
}
'''),
    Positive("ordinary-model-queue-helper-chain", 'ordinaryRoot(17, 29)\n', '''
function ordinaryLeaf(first: Integer, second: Integer): Integer {
    let queue = model.modelQueue()
    return first + second
}
function ordinaryMiddle(first: Integer, second: Integer): Integer {
    return ordinaryLeaf(first, second)
}
function ordinaryRoot(first: Integer, second: Integer) {
    let value = ordinaryMiddle(first, second)
}
'''),
    Positive("dma-main-scalar-callback-chain", '''
let callback: (Integer) -> Integer = function(value) { return scalarMiddle(value) }
check(callback(37) == 37, "scalar callback helper graph")
let cpu = dma.allocate(16, 16)
dma.dispose(cpu)
''', '''
function scalarLeaf(value: Integer): Integer { return value }
function scalarMiddle(value: Integer): Integer { return scalarLeaf(value) }
'''),
    Positive("ordinary-for-model-queue", '''
let output = [0, 0, 0, 0]
for index in 0..output.length {
    let queue = model.modelQueue()
    output[index] = index
}
check(output[0] == 0 && output[3] == 3, "ordinary loop permits nonaffine Queue locals")
'''),
    Positive("dma-main-scalar-parallel-for", '''
let output = [0, 0, 0, 0]
parallel for index in 0..output.length {
    output[index] = index
}
check(output[0] == 0 && output[3] == 3, "pure parallel range")
let cpu = dma.allocate(16, 16)
dma.dispose(cpu)
''', link_flags=("-pthread",)),
    Positive("test-expect-ordinary-record-equality", "", execute=False, options=("--test-mode",),
             custom_source=IMPORTS + '''
record TestKey { value: Integer }
test "ordinary records" {
    let left = TestKey { value: 7 }
    let right = TestKey { value: 7 }
    expect(left == right)
}
'''),
    Positive("ordinary-method-dma", '''
let meter = Meter { value: 37 }
check(meter.read() == 37, "ordinary record method can own local DMA")
''', DMA_METER_METHOD),
    Positive("dma-main-scalar-method-callback", '''
let meter = Meter { value: 37 }
let callback: () -> Integer = function() { return meter.read() }
check(callback() == 37, "ordinary record capture and scalar method remain valid")
let cpu = dma.allocate(16, 16)
dma.dispose(cpu)
''', '''
record Meter { value: Integer }
function Meter.read(): Integer { return self.value }
'''),
)
POSITIVE_BY_NAME = {case.name: case for case in POSITIVES}


@dataclass(frozen=True)
class Negative:
    name: str
    body: str
    control: str
    concepts: tuple
    declarations: str = ""
    type_error: bool = False
    options: tuple = ()
    categories: tuple = ("dma", "affine")
    extra_controls: tuple = ()
    context_categories: tuple = ()
    custom_source: str | None = None

    @property
    def source(self):
        if self.custom_source is not None:
            return self.custom_source
        return program(self.body, self.declarations)


CPU = 'let cpu = dma.allocate(16, 16)\n'
PENDING = 'let queue = model.modelQueue()\n' + CPU + 'let pending = dma.submit(queue, cpu, 16)\n'
COMPLETE = PENDING + 'let payload = Bytes(1)\ncheck(model.modelDeliver(queue, payload), "delivery")\n'
NEGATIVES = (
    Negative("old-cpu-after-submit", PENDING + 'let value = dma.load8(cpu, 0)\ndma.retire(pending)\n',
             "retire", ("mov", "consum", "live", "availab", "own")),
    Negative("old-alias-after-submit", CPU + '''
let alias = cpu
let queue = model.modelQueue()
let pending = dma.submit(queue, alias, 16)
let value = dma.load8(cpu, 0)
dma.retire(pending)
''', "helper-move", ("mov", "consum", "live", "availab", "own")),
    Negative("double-submit", PENDING + 'let again = dma.submit(queue, cpu, 16)\ndma.retire(pending)\ndma.retire(again)\n',
             "retire", ("mov", "consum", "live", "availab", "own")),
    Negative("double-reclaim", COMPLETE + '''
let first = dma.reclaim(pending, 1)
let second = dma.reclaim(pending, 1)
dma.dispose(first)
dma.dispose(second)
''', "model-roundtrip", ("mov", "consum", "live", "availab", "own")),
    Negative("double-dispose", CPU + 'dma.dispose(cpu)\ndma.dispose(cpu)\n',
             "cpu-borrow", ("mov", "consum", "live", "availab", "own")),
    Negative("pending-load", PENDING + 'let value = dma.load8(pending, 0)\ndma.retire(pending)\n',
             "retire", ("type", "cpu", "pending"), type_error=True),
    Negative("branch-asymmetry", 'asymmetric(true)\n', "if-join", ("branch", "join", "state", "live", "own"), '''
function asymmetric(condition: Boolean) {
    let cpu = dma.allocate(16, 16)
    if condition { dma.dispose(cpu) }
    dma.dispose(cpu)
}
'''),
    Negative("overwrite-live", CPU + 'let other = dma.allocate(16, 16)\ncpu = other\ndma.dispose(cpu)\n',
             "rebind-disposed", ("overwrit", "live", "releas", "obligation", "own")),
    Negative("unreleased-cpu", CPU, "cpu-borrow", ("exit", "scope", "live", "dispos", "releas", "obligation", "own")),
    Negative("unreleased-pending", PENDING, "retire", ("exit", "scope", "live", "retir", "releas", "obligation", "own")),
    Negative("early-return-live", 'forget(true)\n', "early-return", ("return", "exit", "live", "obligation", "own"), '''
function forget(early: Boolean) {
    let cpu = dma.allocate(16, 16)
    if early { return }
    dma.dispose(cpu)
}
'''),
    Negative("dead-branch-list-escape", CPU + 'if false { let hidden = [cpu] }\ndma.dispose(cpu)\n',
             "scalar-aggregate", ("list", "aggregate", "contain", "escape", "stor")),
    Negative("list-escape", CPU + 'let hidden = [cpu]\ndma.dispose(cpu)\n',
             "scalar-aggregate", ("list", "aggregate", "contain", "escape", "stor")),
    Negative("record-escape", CPU + 'let hidden = Box { value: cpu }\n',
             "scalar-aggregate", ("record", "field", "aggregate", "contain", "escape", "stor"),
             'record Box { value: dma.Cpu }\n'),
    Negative("closure-capture", CPU + '''
let callback: () -> Integer = function() { return dma.load8(cpu, 0) }
let value = callback()
dma.dispose(cpu)
''', "scalar-capture", ("captur", "closure", "callback", "escape")),
    Negative("global-escape", 'dma.dispose(GLOBAL_CPU)\n', "scalar-global",
             ("global", "escape", "stor"), 'global GLOBAL_CPU: dma.Cpu = dma.allocate(16, 16)\n'),
    Negative("unknown-native", CPU + 'let result = foreign(cpu)\ndma.dispose(result)\n', "scalar-native",
             ("native", "provider", "trusted", "escape", "unknown"),
             'function foreign(value: dma.Cpu): dma.Cpu { native "dma_test_unknown" }\n'),
    Negative("forged-borrow-name", CPU + 'let result = load8(cpu)\ndma.dispose(cpu)\n',
             "user-load8-consumes", ("mov", "consum", "live", "availab", "own"), USER_LOAD),
    Negative("two-affine-parameters", CPU + 'let other = dma.allocate(16, 16)\nconsumeBoth(cpu, other)\n',
             "two-scalars", ("parameter", "argument", "one", "signature"), '''
function consumeBoth(left: dma.Cpu, right: dma.Cpu) {
    dma.dispose(left)
    dma.dispose(right)
}
'''),
    Negative("generic-old-alias", CPU + 'let moved = identity<dma.Cpu>(cpu)\nlet value = dma.load8(cpu, 0)\ndma.dispose(moved)\n',
             "generic-identity", ("mov", "consum", "live", "availab", "own"), IDENTITY),
    Negative("shadow-moved-outer", CPU + '''
let moved = cpu
if true { let cpu = dma.allocate(16, 16); dma.dispose(cpu) }
let value = dma.load8(cpu, 0)
dma.dispose(moved)
''', "shadow", ("mov", "consum", "live", "availab", "own")),
    Negative("loop-holds-capability", CPU + 'let count = 0\nwhile count < 2 { let value = dma.load8(cpu, 0); count += 1 }\ndma.dispose(cpu)\n',
             "scalar-loop", ("loop", "backedge", "unsupported")),
    Negative("worker-local-allocate", 'check(true, "worker body still checked")\n',
             "scalar-thread-declaration", ("thread", "parallel", "serial"), '''
thread function worker(seed: Integer, input: FrozenBytes, channel: BytesChannel): Integer {
    let cpu = dma.allocate(16, 16)
    dma.dispose(cpu)
    return seed
}
'''),
    Negative("worker-local-model-queue", 'check(true, "worker queue factory still checked")\n',
             "scalar-thread-declaration", ("thread", "parallel", "serial"), '''
thread function worker(seed: Integer, input: FrozenBytes, channel: BytesChannel): Integer {
    let queue = model.modelQueue()
    return seed
}
'''),
    Negative("irq-reaches-dma", CPU + 'dma.dispose(cpu)\n', "irq-main-coexist",
             ("managed", "alloc", "dma", "native"), '''
interrupt function tick(vector: Integer) handles(32) {
    let cpu = dma.allocate(16, 16)
    dma.dispose(cpu)
}
''', options=("--freestanding", "--kernel-target", "x86_64"), categories=("interrupt", "irq")),
    Negative("queue-equality", '''
let left = model.modelQueue()
let right = model.modelQueue()
let equal = left == right
''', "ordinary-record-compare", ("opaque", "compar", "equal", "operator")),
    Negative("queue-map-key", 'let values = Map<dma.Queue, Integer>()\n',
             "ordinary-record-compare", ("opaque", "map", "container", "stor", "key", "hash")),
    Negative("queue-record-field", 'let queue = model.modelQueue()\nlet box = Box { value: queue }\n',
             "scalar-aggregate", ("opaque", "record", "field", "aggregate", "stor"),
             'record Box { value: dma.Queue }\n'),
    Negative("queue-global", 'check(true, "opaque global forbidden")\n', "scalar-global",
             ("opaque", "global", "stor"), 'global GLOBAL_QUEUE: dma.Queue = model.modelQueue()\n'),
    Negative("parallel-helper-allocate", 'parallelRoot(17, 29)\n',
             "ordinary-allocate-helper-chain", ("parallel", "managed", "alloc", "native", "serial", "ownership"), '''
parallel function parallelLeaf(first: Integer, second: Integer): Integer {
    let cpu = dma.allocate(16, 16)
    dma.store8(cpu, 0, first)
    let value = dma.load8(cpu, 0)
    dma.dispose(cpu)
    return value
}
parallel function parallelMiddle(first: Integer, second: Integer): Integer {
    return parallelLeaf(first, second)
}
parallel function parallelRoot(first: Integer, second: Integer) {
    let value = parallelMiddle(first, second)
}
''', extra_controls=("dma-main-unused-parallel-chain",), context_categories=("parallel",)),
    Negative("parallel-helper-model-queue", 'parallelRoot(17, 29)\n',
             "ordinary-model-queue-helper-chain", ("parallel", "managed", "native", "serial", "ownership"), '''
parallel function parallelLeaf(first: Integer, second: Integer): Integer {
    let queue = model.modelQueue()
    return first + second
}
parallel function parallelMiddle(first: Integer, second: Integer): Integer {
    return parallelLeaf(first, second)
}
parallel function parallelRoot(first: Integer, second: Integer) {
    let value = parallelMiddle(first, second)
}
''', extra_controls=("dma-main-unused-parallel-chain",), context_categories=("parallel",)),
    Negative("callback-helper-allocate", '''
let callback: (Integer) -> Integer = function(value) { return callbackMiddle(value) }
check(callback(37) == 37, "callback body is scalar; helper reaches DMA")
''', "ordinary-allocate-helper-chain", ("callback", "closure", "context", "serial", "ownership"), '''
function callbackLeaf(value: Integer): Integer {
    let cpu = dma.allocate(16, 16)
    dma.store8(cpu, 0, value)
    let answer = dma.load8(cpu, 0)
    dma.dispose(cpu)
    return answer
}
function callbackMiddle(value: Integer): Integer { return callbackLeaf(value) }
''', extra_controls=("dma-main-scalar-callback-chain",)),
    Negative("parallel-for-model-queue", '''
let output = [0, 0, 0, 0]
parallel for index in 0..output.length {
    let queue = model.modelQueue()
    output[index] = index
}
''', "ordinary-for-model-queue", ("parallel", "managed", "native", "serial", "ownership"),
             extra_controls=("dma-main-scalar-parallel-for",), context_categories=("parallel",)),
    Negative("test-expect-queue-equality", "", "test-expect-ordinary-record-equality", ("opaque",),
             options=("--test-mode",), categories=("dma",), custom_source=IMPORTS + '''
test "opaque queues" {
    let queue = model.modelQueue()
    expect(queue == queue)
}
'''),
    Negative("callback-method-allocate", '''
let meter = Meter { value: 37 }
let callback: () -> Integer = function() { return meter.read() }
check(callback() == 37, "scalar record method reaches DMA from callback")
''', "ordinary-method-dma", ("callback", "closure", "context", "serial", "ownership"),
             DMA_METER_METHOD, extra_controls=("dma-main-scalar-method-callback",)),
)


# Independent runtime misuse: these sources use only the public helper surface.
# No DMA registry fields, cookies, private symbols, or copied runtime algorithm.
C_SOURCE = r'''
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#define MINYAR_SYSTEM_HEAP 1
#ifdef NDEBUG
#undef NDEBUG
#endif
#include DMA_RUNTIME_SOURCE
#include <assert.h>

static void drain_releases(void) {
#ifdef MINYAR_BOUNDED_RC
    for (int i = 0; i < 4096; ++i) if (!minyar_rc_poll(256)) break;
#endif
}

static __attribute__((noinline)) unsigned char raw_read(volatile unsigned char *address, size_t offset) {
    return address[offset];
}

static void fault_site(void) {
    fputs("DMA-TEST-OP\n", stderr);
    fflush(stderr);
}

static MinyarBytes *payload(void) {
    MinyarBytes *bytes = minyar_bytes_new(4);
    minyar_bytes_set(bytes, 0, 81);
    minyar_bytes_set(bytes, 1, 0);
    minyar_bytes_set(bytes, 2, 254);
    minyar_bytes_set(bytes, 3, 99);
    return bytes;
}

/* Explicit unsafe C device fixture, not real DMA. The four actual Bytes are
 * owned by a managed record; the public bridge must retain that ring owner.
 * Reading the published descriptor is how this model obtains the DMA address.
 * No private registry field or opaque handle field is inspected. */
static int retire_pins_hardware(void) {
    MinyarRecord *owner = minyar_record_new(4);
    uintptr_t ranges[4];
    const size_t sizes[4] = {32, 16, 16, 2};
    const size_t aligns[4] = {16, 2, 4, 2};
    for (long long i = 0; i < 4; ++i) {
        MinyarBytes *bytes = minyar_bytes_new((long long)(sizes[i] + aligns[i] - 1));
        uintptr_t first = (uintptr_t)bytes->bytes;
        ranges[i] = (first + aligns[i] - 1) & ~(uintptr_t)(aligns[i] - 1);
        minyar_record_set_take(owner, i, (long long)(uintptr_t)bytes);
    }
    MinyarRecord *queue = minyar_dma_unsafeVirtioQueue(owner,
        (long long)ranges[0], (long long)ranges[1], (long long)ranges[2],
        (long long)ranges[3], 1, 0);
    MinyarRecord *cpu = minyar_dma_allocate(64, 64);
    MinyarRecord *pending = minyar_dma_submit(queue, cpu, 64);
    uint64_t address = 0;
    uint32_t length = 0;
    uint16_t flags = 0, published = 0;
    memcpy(&address, (const void *)ranges[0], sizeof(address));
    memcpy(&length, (const void *)(ranges[0] + 8), sizeof(length));
    memcpy(&flags, (const void *)(ranges[0] + 12), sizeof(flags));
    memcpy(&published, (const void *)(ranges[1] + 2), sizeof(published));
    assert(address && length == 64 && flags == 2 && published == 1);
    minyar_dma_retire(pending);
    minyar_rc_release(cpu);
    minyar_rc_release(pending);
    minyar_rc_release(owner);
    minyar_rc_release(queue);
    drain_releases();
    for (int i = 0; i < 1024; ++i) {
        MinyarBytes *churn = minyar_bytes_new(64 + i % 128);
        minyar_bytes_set(churn, 0, i % 256);
        minyar_rc_release(churn);
    }
    drain_releases();
    volatile unsigned char *device = (volatile unsigned char *)(uintptr_t)address;
    device[0] = 91;
    device[63] = 17;
    /* A late device may also access its published rings after retirement. */
    assert(*(volatile uint32_t *)(ranges[0] + 8) == 64);
    *(volatile uint32_t *)(ranges[2] + 4) = 0;
    *(volatile uint32_t *)(ranges[2] + 8) = 64;
    *(volatile uint16_t *)(ranges[2] + 2) = 1;
    assert(device[0] == 91 && device[63] == 17);
    puts("DMA-C-PASS");
    return 0;
}

static int repeated_generations(const char *mode) {
    MinyarRecord *queue = minyar_dma_model_modelQueue();
    MinyarRecord *cpu = minyar_dma_allocate(16, 16);
    MinyarRecord *old_cpu = cpu;
    MinyarRecord *old_pending = NULL;
    minyar_rc_retain(old_cpu);
    for (int i = 0; i < 64; ++i) {
        MinyarRecord *pending = minyar_dma_submit(queue, cpu, 4);
        if (i == 0) { old_pending = pending; minyar_rc_retain(old_pending); }
        assert(!minyar_dma_ready(pending));
        MinyarBytes *bytes = payload();
        minyar_bytes_set(bytes, 0, i);
        assert(minyar_dma_model_modelDeliver(queue, bytes));
        cpu = minyar_dma_reclaim(pending, 1);
        assert(minyar_dma_load8(cpu, 0) == i);
    }
    if (!strcmp(mode, "old-cpu-after-generations")) { fault_site(); return (int)minyar_dma_load8(old_cpu, 0); }
    if (!strcmp(mode, "old-pending-after-generations")) { fault_site(); return minyar_dma_ready(old_pending) ? 91 : 92; }
    assert(!strcmp(mode, "generations-control"));
    minyar_dma_dispose(cpu);
    puts("DMA-C-PASS");
    return 0;
}

int main(int argc, char **argv) {
    assert(argc == 2);
    const char *mode = argv[1];
    if (!strcmp(mode, "asan-control")) {
        volatile size_t offset = 2;
        unsigned char *data = malloc(1);
        assert(data);
        data[0] = 7;
        volatile unsigned char observed = raw_read(data, offset);
        free(data);
        return observed;
    }
    if (!strcmp(mode, "asan-rc-control")) {
        MinyarBytes *bytes = minyar_bytes_new(64);
        volatile unsigned char *address = (volatile unsigned char *)bytes->bytes;
        minyar_rc_release(bytes);
        drain_releases();
        return raw_read(address, 0);
    }
    if (!strcmp(mode, "ubsan-control")) {
        volatile long long value = LLONG_MAX;
        value += 1;
        return (int)value;
    }
    if (!strcmp(mode, "retire-pins-hardware")) return retire_pins_hardware();
    if (!strcmp(mode, "generations-control") || !strcmp(mode, "old-cpu-after-generations") ||
        !strcmp(mode, "old-pending-after-generations")) return repeated_generations(mode);
    void *queue = minyar_dma_model_modelQueue();
    void *cpu = minyar_dma_allocate(16, 16);
    minyar_dma_store8(cpu, 0, 17);
    minyar_dma_store8(cpu, 15, 255);
    if (!strcmp(mode, "load-negative")) { fault_site(); return (int)minyar_dma_load8(cpu, -1); }
    if (!strcmp(mode, "load-past-end")) { fault_site(); return (int)minyar_dma_load8(cpu, 16); }
    if (!strcmp(mode, "store-past-end")) { fault_site(); minyar_dma_store8(cpu, 16, 1); return 90; }
    if (!strcmp(mode, "store-negative-value")) { fault_site(); minyar_dma_store8(cpu, 0, -1); return 90; }
    if (!strcmp(mode, "store-large-value")) { fault_site(); minyar_dma_store8(cpu, 0, 256); return 90; }
    if (!strcmp(mode, "copy-overflow")) { fault_site(); (void)minyar_dma_copyOut(cpu, 15, LLONG_MAX); return 90; }
    if (!strcmp(mode, "submit-too-long")) { fault_site(); (void)minyar_dma_submit(queue, cpu, 17); return 90; }
    if (!strcmp(mode, "disposed-cpu")) {
        minyar_rc_retain(cpu);
        minyar_dma_dispose(cpu);
        fault_site();
        return (int)minyar_dma_load8(cpu, 0);
    }
    MinyarBytes *copy = minyar_dma_copyOut(cpu, 0, 1);
    minyar_rc_retain(cpu); /* Deliberately retain the old handle across moves. */
    void *pending = minyar_dma_submit(queue, cpu, 16);
    if (!strcmp(mode, "submitted-cpu")) { fault_site(); return (int)minyar_dma_load8(cpu, 0); }
    if (!strcmp(mode, "double-submit")) { fault_site(); (void)minyar_dma_submit(queue, cpu, 16); return 90; }
    if (!strcmp(mode, "pending-load")) { fault_site(); return (int)minyar_dma_load8(pending, 0); }
    if (!strcmp(mode, "pending-dispose")) { fault_site(); minyar_dma_dispose(pending); return 90; }
    if (!strcmp(mode, "timeout")) { fault_site(); (void)minyar_dma_reclaim(pending, 0); return 90; }
    if (!strcmp(mode, "negative-spins")) { fault_site(); (void)minyar_dma_reclaim(pending, -1); return 90; }
    if (!strcmp(mode, "excessive-spins")) { fault_site(); (void)minyar_dma_reclaim(pending, 1000001); return 90; }
    if (!strcmp(mode, "retired-pending")) {
        minyar_rc_retain(pending);
        minyar_dma_retire(pending);
        fault_site();
        return minyar_dma_ready(pending) ? 91 : 92;
    }
    assert(!minyar_dma_ready(pending));
    assert(!minyar_dma_ready(pending));
    MinyarBytes *bytes = !strncmp(mode, "zero-", 5) ? minyar_bytes_new(0) : payload();
    assert(minyar_dma_model_modelDeliver(queue, bytes));
    if (!strncmp(mode, "corrupt-", 8)) {
        int kind = atoi(mode + 8);
        assert(kind >= 0 && kind <= 6);
        minyar_dma_model_modelCorrupt(queue, kind, -1);
        fault_site();
        (void)minyar_dma_reclaim(pending, 1);
        return 90;
    }
    if (!strcmp(mode, "publication-not-advanced")) {
        minyar_dma_model_modelCorrupt(queue, 6, 0);
        fault_site();
        (void)minyar_dma_reclaim(pending, 0);
        return 90;
    }
    assert(minyar_dma_ready(pending));
    assert(minyar_dma_ready(pending));
    minyar_rc_retain(pending);
    void *finished = minyar_dma_reclaim(pending, 1);
    if (!strcmp(mode, "reclaimed-pending")) { fault_site(); return minyar_dma_ready(pending) ? 91 : 92; }
    if (!strcmp(mode, "double-reclaim")) { fault_site(); (void)minyar_dma_reclaim(pending, 1); return 90; }
    if (!strcmp(mode, "old-cpu-after-roundtrip")) { fault_site(); return (int)minyar_dma_load8(cpu, 0); }
    if (!strcmp(mode, "short-load-suffix")) { fault_site(); return (int)minyar_dma_load8(finished, 4); }
    if (!strcmp(mode, "short-store-suffix")) { fault_site(); minyar_dma_store8(finished, 4, 1); return 90; }
    if (!strcmp(mode, "short-copy-suffix")) { fault_site(); (void)minyar_dma_copyOut(finished, 3, 2); return 90; }
    if (!strcmp(mode, "zero-load")) { fault_site(); return (int)minyar_dma_load8(finished, 0); }
    if (!strcmp(mode, "zero-control")) {
        MinyarBytes *empty = minyar_dma_copyOut(finished, 0, 0);
        assert(minyar_bytes_length(empty) == 0);
        minyar_dma_dispose(finished);
        puts("DMA-C-PASS");
        return 0;
    }
    assert(minyar_dma_load8(finished, 0) == 81);
    assert(minyar_dma_load8(finished, 1) == 0);
    assert(minyar_dma_load8(finished, 2) == 254);
    assert(minyar_dma_load8(finished, 3) == 99);
    assert(minyar_bytes_get(copy, 0) == 17);
    minyar_dma_store8(finished, 0, 42);
    assert(minyar_bytes_get(copy, 0) == 17);
    MinyarBytes *fresh = minyar_dma_copyOut(finished, 0, 4);
    minyar_dma_dispose(finished);
    if (!strcmp(mode, "double-dispose")) { fault_site(); minyar_dma_dispose(finished); return 90; }
    if (!strcmp(mode, "stale-after-reallocation")) {
        void *replacement = minyar_dma_allocate(16, 16);
        minyar_dma_store8(replacement, 0, 113);
        fault_site();
        return (int)minyar_dma_load8(finished, 0);
    }
    assert(minyar_bytes_get(copy, 0) == 17);
    assert(minyar_bytes_get(fresh, 0) == 42 && minyar_bytes_get(fresh, 3) == 99);
    assert(!strcmp(mode, "control"));
    puts("DMA-C-PASS");
    return 0;
}
'''
C_FAILURES = (
    "load-negative", "load-past-end", "store-past-end", "store-negative-value",
    "store-large-value", "copy-overflow", "submit-too-long", "disposed-cpu",
    "submitted-cpu", "double-submit", "pending-load", "pending-dispose", "timeout", "retired-pending",
    "reclaimed-pending", "double-reclaim", "old-cpu-after-roundtrip", "double-dispose",
    "negative-spins", "excessive-spins", "short-load-suffix", "short-store-suffix", "short-copy-suffix",
    "zero-load", "old-cpu-after-generations", "old-pending-after-generations", "stale-after-reallocation",
    *(f"corrupt-{kind}" for kind in range(7)), "publication-not-advanced",
)
SANITIZER_ERROR = re.compile(r"AddressSanitizer|UndefinedBehaviorSanitizer|runtime error:|LeakSanitizer")
FRONTEND_FAULT = re.compile(
    r"internal (?:compiler )?(?:error|failure)|List position|segmentation fault|assertion.*failed|"
    r"expected (?:an? |the )?(?:expression|identifier|token|[\"'])|"
    r"unknown (?:function|type|name)|cannot find (?:module|function)|can't find (?:module|function)",
    re.IGNORECASE)


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(part)
    return hasher.hexdigest()


class Gate:
    def __init__(self, args, directory):
        self.args = args
        self.directory = directory
        self.environment = os.environ.copy()
        self.commands = []
        self.checks = []
        self.compiled = {}
        self.serial = 0
        self.compiler = self.tool("MINYAR_TEST_COMPILER", str(ROOT / "build/minyarc"))
        self.clang = self.tool("MINYAR_TEST_CLANG", "clang")
        self.runtime = Path(os.environ.get("MINYAR_TEST_RUNTIME", str(ROOT / "build/minyar-runtime.o"))).resolve()
        self.runtime_source = Path(os.environ.get("MINYAR_TEST_RUNTIME_SOURCE", str(ROOT / "runtime/minyar_runtime.c"))).resolve()
        self.library = Path(os.environ.get("MINYAR_TEST_DMA_LIBRARY", str(ROOT / "library"))).resolve()
        self.flags = shlex.split(os.environ.get("MINYAR_TEST_LINK_FLAGS", ""))
        self.cflags = shlex.split(os.environ.get("MINYAR_TEST_RUNTIME_CFLAGS", ""))
        self.artifacts = {}

    def tool(self, variable, fallback):
        selected = os.environ.get(variable, fallback)
        resolved = shutil.which(selected)
        if not resolved:
            raise ValueError(f"{variable}: executable not found: {selected}")
        return str(Path(resolved).resolve())

    def selected(self, name):
        return not self.args.case or any(part in name for part in self.args.case)

    def check(self, group, name, success, detail=""):
        self.checks.append(dict(group=group, name=name, passed=bool(success), detail=detail))
        print(f"{group}/{name}: {'passed' if success else 'FAILED'}", flush=True)
        if not success and detail:
            print(detail[:6000], file=sys.stderr, flush=True)
        return success

    def invoke(self, label, command, environment=None):
        self.serial += 1
        stem = self.directory / f"command-{self.serial:04d}"
        stdout_path = stem.with_suffix(".stdout")
        stderr_path = stem.with_suffix(".stderr")
        started = time.perf_counter()
        timed_out = False
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=ROOT, env=environment or self.environment,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                process.wait(timeout=self.args.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        output = []
        oversized = False
        for path in (stdout_path, stderr_path):
            with path.open("rb") as stream:
                data = stream.read(MAX_CAPTURE + 1)
            oversized |= len(data) > MAX_CAPTURE
            output.append(data[:MAX_CAPTURE].decode("utf-8", "replace"))
        status = 124 if timed_out else process.returncode
        record = dict(label=label, argv=command, status=status, timed_out=timed_out,
                      elapsed_seconds=time.perf_counter() - started,
                      stdout=str(stdout_path), stderr=str(stderr_path), oversized=oversized)
        self.commands.append(record)
        return status, output[0], output[1], timed_out or oversized

    def compile(self, label, source, directory=None, options=()):
        directory = directory or self.directory / label
        directory.mkdir(exist_ok=True)
        input_path, llvm = directory / "case.min", directory / "case.ll"
        input_path.write_text(source, encoding="utf-8")
        command = [self.compiler, str(input_path), str(llvm), "--library", str(self.library), *options]
        status, stdout, stderr, broken = self.invoke(label + "/compile", command)
        return llvm, status, stdout, stderr, broken

    def positive_compile(self, name, group):
        if name in self.compiled:
            return self.compiled[name]
        case = POSITIVE_BY_NAME[name]
        llvm, status, stdout, stderr, broken = self.compile("valid-" + name, case.source, options=case.options)
        success = (not broken and status == 0 and not stdout and not stderr and
                   llvm.is_file() and "define " in llvm.read_text(encoding="utf-8"))
        self.check(group, name + "/compile-control", success,
                   f"status={status}\n{stdout}{stderr}")
        self.compiled[name] = llvm if success else None
        return self.compiled[name]

    def reject(self, case, group, directory=None):
        llvm, status, stdout, stderr, broken = self.compile("reject-" + case.name, case.source, directory, case.options)
        # File paths and quoted source lines contain case/type names too. Only
        # actual diagnostic messages may establish the expected effect category.
        messages = "\n".join(line.strip() for line in stderr.splitlines()
                             if line.lstrip().startswith(("error:", "note:")))
        lowered = messages.lower()
        category = any(re.search(r"\b" + re.escape(word) + r"\b", lowered) for word in case.categories)
        context_category = any(re.search(r"\b" + re.escape(word) + r"\b", lowered) for word in case.context_categories)
        category = category or context_category
        if case.type_error:
            category |= "type" in lowered and ("pending" in lowered or "cpu" in lowered)
        concept = any(word in lowered for word in case.concepts)
        location = bool(re.search(r"\.min:[0-9]+:[0-9]+", stderr))
        protection = "expected semantic rejection"
        if "dma ownership:" in lowered:
            protection = "DMA ownership rejection"
        elif re.search(r"\bdma\b", lowered):
            protection = "DMA marker/native/context rejection"
        elif context_category:
            protection = "existing parallel context/effect rejection"
        success = (not broken and status == 1 and not stdout and category and concept and
                   location and not FRONTEND_FAULT.search(stderr) and not llvm.exists())
        return self.check(group, case.name, success,
                          f"status={status}, protection={protection}, category={category}, semantic concept={concept}, "
                          f"source location={location}, LLVM survives={llvm.exists()}\n{stdout}{stderr}")

    def compile_group(self):
        for case in NEGATIVES:
            if self.selected(case.name):
                controls = [self.positive_compile(name, "compile")
                            for name in (case.control, *case.extra_controls)]
                if any(control is None for control in controls):
                    self.check("compile", case.name, False, "blocked by failed valid control")
                else:
                    self.reject(case, "compile")

    def execute_language(self, name, group):
        llvm = self.positive_compile(name, group)
        if llvm is None:
            return
        if not self.runtime.is_file():
            raise ValueError(f"MINYAR_TEST_RUNTIME: missing actual runtime object: {self.runtime}")
        for level in LEVELS:
            label = name + "/" + level[1:]
            executable = llvm.parent / ("case-" + level[1:])
            command = [self.clang, level, "-Wno-override-module", *self.flags, *POSITIVE_BY_NAME[name].link_flags,
                       str(llvm), str(self.runtime), "-lm", "-o", str(executable)]
            status, stdout, stderr, broken = self.invoke(label + "/link", command)
            if not self.check(group, label + "/link", not broken and status == 0,
                              f"status={status}\n{stdout}{stderr}"):
                continue
            status, stdout, stderr, broken = self.invoke(label + "/run", [str(executable)])
            self.check(group, label + "/run", not broken and status == 0 and stdout == "DMA-PASS\n" and not stderr,
                       f"status={status}\n{stdout}{stderr}")

    def control_group(self):
        for case in POSITIVES:
            if self.selected(case.name):
                if case.execute:
                    self.execute_language(case.name, "control")
                else:
                    self.positive_compile(case.name, "control")

    def c_group(self, sanitized):
        group = "sanitizer" if sanitized else "runtime"
        if not self.runtime_source.is_file():
            raise ValueError(f"MINYAR_TEST_RUNTIME_SOURCE: missing runtime C source: {self.runtime_source}")
        source = self.directory / (group + "-unsafe.c")
        # The C preprocessor interprets this as a header name, not a shell word.
        if any(character in str(self.runtime_source) for character in ('"', "\\", "\n", "\r")):
            raise ValueError("runtime source header path contains an unsupported quote, slash escape or newline")
        source.write_text(C_SOURCE.replace("DMA_RUNTIME_SOURCE", json.dumps(str(self.runtime_source), ensure_ascii=False)), encoding="utf-8")
        environment = dict(self.environment)
        if sanitized:
            # Quarantined allocations intentionally remain pinned. This group
            # checks memory access/UB, and makes no leak-free shutdown claim.
            environment["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1:abort_on_error=0"
            environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        for level in LEVELS:
            label = "unsafe-c/" + level[1:]
            executable = self.directory / (group + "-" + level[1:])
            instrumentation = (["-fsanitize=address,undefined", "-fno-sanitize-recover=all"] if sanitized else [])
            command = [self.clang, "-std=c11", "-g", level, "-fno-omit-frame-pointer",
                       "-Werror=implicit-function-declaration", "-Wno-unused-function", *self.cflags,
                       *self.flags, *instrumentation, str(source), "-lm", "-o", str(executable)]
            status, stdout, stderr, broken = self.invoke(group + "/" + label + "/build", command)
            if not self.check(group, label + "/build", not broken and status == 0,
                              f"status={status}\n{stdout}{stderr}"):
                continue
            status, stdout, stderr, broken = self.invoke(group + "/" + label + "/control", [str(executable), "control"], environment)
            if not self.check(group, label + "/control", not broken and status == 0 and stdout == "DMA-C-PASS\n" and not stderr,
                              f"status={status}\n{stdout}{stderr}"):
                continue
            for mode in ("zero-control", "generations-control", "retire-pins-hardware"):
                status, stdout, stderr, broken = self.invoke(group + "/" + label + "/" + mode, [str(executable), mode], environment)
                self.check(group, label + "/" + mode, not broken and status == 0 and stdout == "DMA-C-PASS\n" and not stderr,
                           f"status={status}\n{stdout}{stderr}")
            if sanitized:
                for mode, diagnostic in (("asan-control", r"AddressSanitizer: heap-buffer-overflow"),
                                         ("asan-rc-control", r"AddressSanitizer: heap-use-after-free"),
                                         ("ubsan-control", r"runtime error: signed integer overflow")):
                    status, stdout, stderr, broken = self.invoke(group + "/" + label + "/" + mode, [str(executable), mode], environment)
                    self.check(group, label + "/" + mode, not broken and status != 0 and bool(re.search(diagnostic, stderr)),
                               f"status={status}\n{stdout}{stderr}")
            for mode in C_FAILURES:
                if not self.selected("unsafe-c/" + mode):
                    continue
                status, stdout, stderr, broken = self.invoke(group + "/" + label + "/" + mode, [str(executable), mode], environment)
                reached = stderr.count("DMA-TEST-OP\n") == 1
                after_site = stderr.partition("DMA-TEST-OP\n")[2]
                self.check(group, label + "/" + mode,
                           not broken and status == 1 and not stdout and reached and "DMA " in after_site and
                           not SANITIZER_ERROR.search(stderr), f"status={status}\n{stdout}{stderr}")

    def artifact_group(self):
        if not self.selected("stale-llvm"):
            return
        directory = self.directory / "stale-artifact"
        directory.mkdir()
        llvm = directory / "case.ll"
        llvm.write_text("STALE-DMA-ARTIFACT\n", encoding="utf-8")
        valid = POSITIVE_BY_NAME["cpu-borrow"].source
        (directory / "valid-source.min").write_text(valid, encoding="utf-8")
        llvm, status, stdout, stderr, broken = self.compile("stale-valid", valid, directory)
        success = (not broken and status == 0 and not stdout and not stderr and llvm.is_file() and
                   "define " in llvm.read_text() and "STALE-DMA-ARTIFACT" not in llvm.read_text())
        if not self.check("artifacts", "stale-llvm/valid-replaces-poison", success,
                          f"status={status}\n{stdout}{stderr}"):
            return
        self.artifacts["prior_valid_llvm_sha256"] = digest(llvm)
        case = next(case for case in NEGATIVES if case.name == "double-dispose")
        (directory / "rejected-source.min").write_text(case.source, encoding="utf-8")
        self.reject(case, "artifacts", directory)

    def result(self, started):
        selected = {}
        for label, value in (("harness", Path(__file__)), ("compiler", Path(self.compiler)), ("clang", Path(self.clang)),
                             ("runtime_object", self.runtime), ("runtime_source", self.runtime_source)):
            selected[label] = dict(path=str(value), sha256=digest(value) if value.is_file() else None)
        return dict(selected=selected, library=str(self.library), link_flags=self.flags, runtime_cflags=self.cflags,
                    groups=self.args.group, filters=self.args.case, elapsed_seconds=time.perf_counter() - started,
                    checks=self.checks, commands=self.commands, artifacts=self.artifacts,
                    limitations=["C coherent ring fixture is not real hardware; no no-heap or unsafe-native isolation claim.",
                                 "Sanitizers instrument the included C runtime; selected Minyar runtime object is unchanged.",
                                 "A timeout diagnostic alone does not prove quarantine lifetime.",
                                 "Fresh allocation after disposal tests stale history, not proof that a private registry slot was reused.",
                                 "No allocator/epoch wrap or hardware generation echo is forced through a private test hook."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=GROUPS, action="append", help="repeat to select groups; default all")
    parser.add_argument("--case", action="append", default=[], help="case-name substring; controls remain mandatory")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="per-command seconds, 1..60")
    parser.add_argument("--output-dir", type=Path, help="new or empty artifact directory; always retained")
    parser.add_argument("--list", action="store_true", help="print case names without invoking tools")
    args = parser.parse_args()
    args.group = list(dict.fromkeys(args.group or GROUPS))
    if not 1 <= args.timeout <= TIMEOUT:
        parser.error("--timeout must be between 1 and 60 seconds")
    if args.list:
        for case in POSITIVES:
            print("control " + case.name)
        for case in NEGATIVES:
            print("compile " + case.name + " (control: " + case.control + ")")
        for name in ("control", "zero-control", "generations-control", "retire-pins-hardware", *C_FAILURES):
            print("runtime,sanitizer unsafe-c/" + name)
        print("sanitizer unsafe-c/asan-control\nsanitizer unsafe-c/asan-rc-control\nsanitizer unsafe-c/ubsan-control\nartifacts stale-llvm")
        return 0
    available = ([case.name for case in POSITIVES] + [case.name for case in NEGATIVES] +
                 ["unsafe-c/" + name for name in ("control", "zero-control", "generations-control", "retire-pins-hardware",
                                                    "asan-control", "asan-rc-control", "ubsan-control", *C_FAILURES)] +
                 ["stale-llvm"])
    for part in args.case:
        if not any(part in name for name in available):
            parser.error("--case matches no fixture: " + part)
    directory = args.output_dir or Path(tempfile.mkdtemp(prefix="minyar-dma-evidence-"))
    directory = directory.resolve()
    if directory.exists() and any(directory.iterdir()):
        parser.error("--output-dir must be new or empty")
    directory.mkdir(parents=True, exist_ok=True)
    gate = None
    started = time.perf_counter()
    try:
        gate = Gate(args, directory)
        for group in args.group:
            if group == "compile":
                gate.compile_group()
            elif group == "control":
                gate.control_group()
            elif group == "runtime":
                for name in ("model-roundtrip", "model-zero-completion", "model-repeated-generations", "model-delivery-guards"):
                    if gate.selected(name):
                        gate.execute_language(name, group)
                gate.c_group(False)
            elif group == "sanitizer":
                gate.c_group(True)
            else:
                gate.artifact_group()
        if not gate.checks:
            gate.check("selection", "nonempty", False, "filters selected no checks")
        result = gate.result(started)
        (directory / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        passed = sum(check["passed"] for check in gate.checks)
        print(f"osdev DMA: {passed}/{len(gate.checks)} checks passed; {len(gate.commands)} commands; "
              f"{result['elapsed_seconds']:.2f}s; artifacts: {directory}", flush=True)
        return 0 if passed == len(gate.checks) else 1
    except (OSError, ValueError) as error:
        if gate is not None:
            gate.check("harness", "configuration-or-io", False, str(error))
            result = gate.result(started)
            (directory / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"osdev DMA: {error}; artifacts: {directory}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
