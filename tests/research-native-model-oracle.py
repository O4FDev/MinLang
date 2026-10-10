#!/usr/bin/env python3
"""Immediate logical ownership oracle, independent of runtime RC scheduling."""
from dataclasses import dataclass, field
import random


@dataclass
class Object:
    kind: int
    children: list[int]


@dataclass
class Frame:
    locals: list[int]
    temporaries: list[int] = field(default_factory=list)


class Oracle:
    def __init__(self):
        self.objects = {}
        self.roots = [0] * 64
        self.frames = []

    def require(self, condition, reason):
        if not condition:
            raise ValueError(reason)

    def require_live(self, identity):
        self.require(identity == 0 or identity in self.live(), 'dead or unknown object')

    def descendants(self, identity):
        todo = [identity] if identity else []
        result = set()
        while todo:
            node = todo.pop()
            if node not in result:
                result.add(node)
                todo.extend(child for child in self.objects[node].children if child)
        return result

    def apply(self, operation):
        name, *args = operation
        if name == 'new':
            kind, identity, slot, *children = args
            self.require(kind in (1, 2, 3), 'unknown object kind')
            self.require(identity == len(self.objects) + 1, 'nonmonotonic generation')
            self.require(0 <= slot < 64 and not self.roots[slot], 'occupied root slot')
            self.require(kind != 1 or not children, 'scalar record has children')
            for child in children:
                self.require_live(child)
                self.require(child < identity, 'edge violates DAG order')
            self.objects[identity] = Object(kind, list(children))
            self.roots[slot] = identity
        elif name == 'alias':
            identity, slot = args
            self.require_live(identity)
            self.require(identity and 0 <= slot < 64 and not self.roots[slot], 'invalid alias slot')
            self.roots[slot] = identity
        elif name == 'drop':
            slot, = args
            self.require(0 <= slot < 64 and self.roots[slot], 'empty root drop')
            self.roots[slot] = 0
        elif name == 'enter':
            count, = args
            self.require(0 <= count <= 64 and len(self.frames) < 8, 'invalid frame size/depth')
            self.frames.append(Frame([0] * count))
        elif name in ('local', 'local_take', 'move'):
            self.require(bool(self.frames), 'no active frame')
            slot, value = args
            frame = self.frames[-1]
            self.require(0 <= slot < len(frame.locals), 'invalid local slot')
            if name == 'local':
                self.require_live(value)
                frame.locals[slot] = value
            elif name == 'local_take':
                self.require(0 <= value < 64 and self.roots[value], 'empty transferred root')
                frame.locals[slot], self.roots[value] = self.roots[value], 0
            else:
                self.require(0 <= value < 64 and not self.roots[value] and frame.locals[slot], 'invalid moved local')
                self.roots[value], frame.locals[slot] = frame.locals[slot], 0
        elif name in ('borrow', 'keep', 'step', 'leave'):
            self.require(bool(self.frames), 'no active frame')
            frame = self.frames[-1]
            if name == 'borrow':
                identity, = args
                self.require_live(identity)
                self.require(bool(identity), 'null borrow')
                frame.temporaries.append(identity)
            elif name == 'keep':
                slot, = args
                self.require(0 <= slot < 64 and self.roots[slot], 'empty temporary transfer')
                frame.temporaries.append(self.roots[slot])
                self.roots[slot] = 0
            elif name == 'step':
                frame.temporaries.clear()
            else:
                self.frames.pop()
        elif name in ('replace', 'append'):
            identity = args[0]
            self.require_live(identity)
            self.require(bool(identity), 'null parent')
            obj = self.objects[identity]
            child = args[-1]
            self.require_live(child)
            self.require(identity not in self.descendants(child), 'edge closes an ownership cycle')
            if name == 'replace':
                _, position, _ = args
                self.require(obj.kind in (2, 3) and 0 <= position < len(obj.children), 'invalid edge position')
                obj.children[position] = child
            else:
                self.require(obj.kind == 3, 'append requires List')
                obj.children.append(child)
        elif name == 'poll':
            self.require(len(args) == 1 and 0 <= args[0] <= (1 << 64) - 1, 'invalid poll request')
        else:
            raise ValueError('unknown operation: ' + name)

    def live(self):
        todo = [identity for identity in self.roots if identity]
        for frame in self.frames:
            todo.extend(identity for identity in frame.locals if identity)
            todo.extend(frame.temporaries)
        result = set()
        while todo:
            identity = todo.pop()
            if identity not in result:
                result.add(identity)
                todo.extend(child for child in self.objects[identity].children if child)
        return result

    def digest(self):
        digest = 1469598103934665603
        for identity in sorted(self.live()):
            obj = self.objects[identity]
            values = [identity, obj.kind, len(obj.children) + (obj.kind != 3)]
            if obj.kind != 3:
                values.append(identity * 1009 + 17)
            values.extend(obj.children)
            for value in values:
                digest = ((digest ^ value) * 1099511628211) & ((1 << 64) - 1)
        return digest


OPCODES = {name: i + 1 for i, name in enumerate((
    'new', 'alias', 'drop', 'enter', 'local', 'local_take', 'move',
    'borrow', 'keep', 'step', 'leave', 'replace', 'append', 'poll'))}


def encode(operations, stats=None):
    """Every target-state oracle is computed before native replay, never from RC."""
    oracle = Oracle()
    lines = []
    census = {'operations': len(operations), 'operation_counts': {}, 'object_kinds': {},
              'constructed_reference_slots': 0, 'appended_reference_slots': 0,
              'peak_logical_live': 0, 'peak_active_frames': 0, 'peak_active_temporaries': 0}
    for operation in operations:
        oracle.apply(operation)
        live = sorted(oracle.live())
        args = list(operation[1:])
        values = [OPCODES[operation[0]], len(args), *args, len(live), *live, oracle.digest()]
        lines.append(' '.join(map(str, values)))
        name = operation[0]
        census['operation_counts'][name] = census['operation_counts'].get(name, 0) + 1
        if name == 'new':
            kind = str(operation[1])
            census['object_kinds'][kind] = census['object_kinds'].get(kind, 0) + 1
            census['constructed_reference_slots'] += len(operation) - 4
        if name == 'append':
            census['appended_reference_slots'] += 1
        census['peak_logical_live'] = max(census['peak_logical_live'], len(live))
        census['peak_active_frames'] = max(census['peak_active_frames'], len(oracle.frames))
        census['peak_active_temporaries'] = max(census['peak_active_temporaries'], sum(len(frame.temporaries) for frame in oracle.frames))
    if stats is not None:
        stats.update(census)
    return '\n'.join(lines) + '\n'


def generate(seed, steps):
    """Valid public API operations, with sparse/wide/alias boundary prefixes."""
    random_source = random.Random(seed)
    operations = []
    oracle = Oracle()

    def emit(operation):
        oracle.apply(operation)  # Invalid premises are generator failures.
        operations.append(operation)

    emit(('enter', 9))
    emit(('new', 1, 1, 0))
    emit(('new', 2, 2, 1, *([1, 0, 1] * 43)))
    emit(('new', 3, 3, 2, *([2] * 65)))
    emit(('local', 8, 3))
    emit(('local_take', 0, 1))
    for _ in range(17):
        emit(('borrow', 1))
    emit(('drop', 0))
    emit(('drop', 2))
    emit(('step',))
    emit(('poll', (1 << 64) - 1))
    emit(('move', 0, 4))
    emit(('drop', 4))
    emit(('local', 8, 0))
    emit(('leave',))
    for _ in range(steps):
        live = sorted(oracle.live())
        empty = [i for i, value in enumerate(oracle.roots) if not value]
        occupied = [i for i, value in enumerate(oracle.roots) if value]
        frame = oracle.frames[-1] if oracle.frames else None
        choices = ['poll'] * 2
        if empty:
            choices += ['new'] * 5
        if live and empty:
            choices += ['alias']
        if occupied:
            choices += ['drop'] * 3
        if len(oracle.frames) < 4:
            choices += ['enter']
        if frame:
            choices += ['leave', 'step']
            if live:
                choices += ['borrow'] * 3
            if occupied:
                choices += ['keep']
            if frame.locals:
                choices += ['local'] * 2
                if occupied:
                    choices += ['local_take']
                if empty and any(frame.locals):
                    choices += ['move']
        parents = [i for i in live if oracle.objects[i].kind in (2, 3)]
        replaceable = [i for i in parents if oracle.objects[i].children]
        lists = [i for i in parents if oracle.objects[i].kind == 3 and len(oracle.objects[i].children) < 129]
        if replaceable:
            choices += ['replace'] * 2
        if lists:
            choices += ['append']
        name = random_source.choice(choices)
        if name == 'new':
            kind = random_source.choice([1, 2, 3])
            size = random_source.choice([0, 1, 2, 3, 7, 8, 9, 16]) if kind != 1 else 0
            children = [random_source.choice([0, *live]) for _ in range(size)]
            op = (name, kind, len(oracle.objects) + 1, random_source.choice(empty), *children)
        elif name == 'alias':
            op = (name, random_source.choice(live), random_source.choice(empty))
        elif name == 'drop':
            op = (name, random_source.choice(occupied))
        elif name == 'enter':
            op = (name, random_source.choice([0, 1, 2, 8, 9, 16]))
        elif name in ('leave', 'step'):
            op = (name,)
        elif name == 'borrow':
            op = (name, random_source.choice(live))
        elif name == 'keep':
            op = (name, random_source.choice(occupied))
        elif name == 'local':
            op = (name, random_source.randrange(len(frame.locals)), random_source.choice([0, *live]))
        elif name == 'local_take':
            op = (name, random_source.randrange(len(frame.locals)), random_source.choice(occupied))
        elif name == 'move':
            op = (name, random_source.choice([i for i, value in enumerate(frame.locals) if value]), random_source.choice(empty))
        elif name in ('replace', 'append'):
            identity = random_source.choice(replaceable if name == 'replace' else lists)
            child = random_source.choice([0, *(i for i in live if identity not in oracle.descendants(i))])
            op = ((name, identity, random_source.randrange(len(oracle.objects[identity].children)), child)
                  if name == 'replace' else (name, identity, child))
        else:
            op = ('poll', random_source.choice([0, 1, 2, 8, 32, 33, (1 << 64) - 1]))
        emit(op)
    while oracle.frames:
        emit(('leave',))
    for i, value in enumerate(oracle.roots):
        if value:
            emit(('drop', i))
    emit(('poll', (1 << 64) - 1))
    assert not oracle.live()
    return operations
