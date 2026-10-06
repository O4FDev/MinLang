#!/usr/bin/env python3
"""Finite executable accounting oracle, not a verifier of compiled C.

Mirrors the bounded runtime's owner slots, three queues and unary pair fusion.
No compiler, allocation, timing or source-program execution occurs here.
Methods named enter/new/local/keep/leave/step isolate ownership transitions;
automatic public-ABI service hooks are omitted. Only explicit poll calls and
release(service=True) add service. Trace replay must respect that kernel scope.
See research/2026-10-memory/literature-accounting.md for assumptions/mapping.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
from collections import Counter, deque
from dataclasses import dataclass, field
import unittest


@dataclass
class Object:
    name: str
    kind: str
    fields: list = field(default_factory=list)
    owners: int = 1
    cursor: int = 0
    dead: bool = False
    freed: bool = False
    backing: str | None = None


@dataclass
class Frame:
    capacity: int
    declared: int
    values: dict = field(default_factory=dict)
    written: list = field(default_factory=list)
    chunks: list = field(default_factory=list)


class Model:
    def __init__(self, ceiling=32, optimized=False):
        self.ceiling = ceiling
        self.optimized = optimized
        self.objects = {}
        self.roots = Counter()
        self.live_frames = []
        self.frames = deque()
        self.chunks = deque()
        self.cache = []
        self.old = deque()
        self.recent = []
        self.active = None
        self.next_queue = self.recent_turn = self.pending = 0
        self.frees = self.units = 0
        self.trace = []

    def new(self, name, kind="record", fields=(), backing=None):
        assert name not in self.objects
        self.objects[name] = Object(name, kind, list(fields), backing=backing)
        self.roots[name] += 1
        for child in list(fields) + ([backing] if backing else []):
            if child:
                self.objects[child].owners += 1
        self.check()
        return name

    def _enqueue(self, name):
        obj = self.objects[name]
        obj.dead = True
        obj.cursor = 0
        self.recent.insert(0, name)
        self.pending += 1

    def _finish(self, name):
        obj = self.objects[name]
        assert obj.owners == 0 and not obj.freed
        assert obj.kind == "text" or obj.cursor == len(obj.fields)
        obj.freed = True
        self.frees += 1

    def _drop(self, name):
        if name is None:
            return 0
        obj = self.objects[name]
        assert obj.owners > 0 and not obj.dead and not obj.freed
        obj.owners -= 1
        if obj.owners:
            return 0
        if obj.kind == "text":
            self._finish(name)
            if obj.backing:
                root = self.objects[obj.backing]
                assert root.kind == "text" and root.backing is None
                root.owners -= 1
                if not root.owners:
                    self._enqueue(root.name)
            return 1
        if not obj.fields:
            self._finish(name)
            return 1
        self._enqueue(name)
        return 0

    def release(self, name, service=False):
        assert self.roots[name] > 0
        self.roots[name] -= 1
        immediate = self._drop(name)
        work = immediate
        if service:
            work += self.poll(self.ceiling - immediate)
        self.check()
        return work

    def enter(self, declared):
        frame = self.cache.pop() if self.cache else Frame(declared, declared)
        frame.capacity = max(frame.capacity, declared)
        frame.declared = declared
        # Reset exactly the declared prefix. Stale storage elsewhere is inert.
        for i in range(declared):
            frame.values[i] = None
        frame.written = []
        assert not frame.chunks
        self.live_frames.append(frame)
        return frame

    def local(self, index, name, take=False):
        frame = self.live_frames[-1]
        assert 0 <= index < frame.declared
        previous = frame.values.get(index)
        if name and not take:
            self.objects[name].owners += 1
        if name and take:
            assert self.roots[name] > 0
            self.roots[name] -= 1
        if name is not None and index not in frame.written:
            frame.written.append(index)
        frame.values[index] = name
        self._drop(previous)
        self.check()

    def move(self, index):
        frame = self.live_frames[-1]
        name = frame.values[index]
        frame.values[index] = None
        if name:
            self.roots[name] += 1
        self.check()
        return name

    def keep(self, name):
        frame = self.live_frames[-1]
        assert self.roots[name] > 0
        self.roots[name] -= 1
        if not frame.chunks or len(frame.chunks[-1]) == 8:
            frame.chunks.append([])
        frame.chunks[-1].append(name)
        self.check()

    def step(self):
        frame = self.live_frames[-1]
        count = sum(map(len, frame.chunks))
        self.chunks.extend(frame.chunks)
        self.pending += count // 8 + (count % 8 != 0)
        frame.chunks = []
        self.check()

    def leave(self):
        self.step()
        frame = self.live_frames.pop()
        self.frames.append(frame)
        self.pending += 1
        self.check()

    # Public RC operations: preserve the actual pre/post service placement.
    # Object constructors and allocator costs remain outside this model.
    def public_enter(self, declared):
        work = self.poll(self.ceiling)
        self.enter(declared)
        return work

    def public_local(self, index, name, take=False):
        before = self.frees
        self.local(index, name, take)
        immediate = self.frees - before
        assert immediate <= 1
        return immediate + self.poll(self.ceiling - immediate)

    def public_keep(self, name):
        frame = self.live_frames[-1]
        work = 0
        if not frame.chunks or len(frame.chunks[-1]) == 8:
            work += self.poll(self.ceiling)
        self.keep(name)
        return work + self.poll(self.ceiling)

    def public_step(self):
        self.step()
        return self.poll(self.ceiling)

    def public_leave(self):
        self.leave()
        return self.poll(self.ceiling)

    def _old_unit(self):
        if self.active is None:
            self.active = self.old.popleft()
        obj = self.objects[self.active]
        if obj.cursor < len(obj.fields):
            child = obj.fields[obj.cursor]
            obj.cursor += 1
            self._drop(child)
            return
        self._finish(self.active)
        self.pending -= 1
        self.active = None

    def _recent_unit(self):
        name = self.recent[0]
        obj = self.objects[name]
        if obj.cursor < len(obj.fields):
            child = obj.fields[obj.cursor]
            obj.cursor += 1
            self._drop(child)
            return
        self.recent.pop(0)
        self._finish(name)
        self.pending -= 1

    def _object_unit(self):
        if self.active is None and not self.old:
            self.old.extend(self.recent)
            self.recent = []
        recent = self.recent_turn
        self.recent_turn ^= 1
        active = self.objects[self.active] if self.active else None
        finish_unary = (not self.old and active and active.kind == "record"
                        and len(active.fields) == active.cursor == 1)
        if recent and self.recent and not finish_unary:
            self._recent_unit()
        else:
            self._old_unit()

    def _frame_unit(self):
        frame = self.frames[0]
        if frame.written:
            index = frame.written.pop()
            child = frame.values[index]
            frame.values[index] = None  # Physical C storage may stay stale.
            self._drop(child)
            return
        self.frames.popleft()
        self.cache.append(frame)  # Abstracts the byte-limited cache admission.
        self.pending -= 1

    def _chunk_unit(self):
        chunk = self.chunks[0]
        if chunk:
            self._drop(chunk.pop())
            return
        self.chunks.popleft()
        self.pending -= 1

    def _pair_run(self, remaining):
        if remaining < 2 or self.pending != 1 or self.active:
            return 0
        name = self.old[0] if self.old else self.recent[0]
        obj = self.objects[name]
        if obj.kind != "record" or len(obj.fields) != 1 or obj.cursor:
            return 0
        self.old.clear()
        self.recent.clear()
        self.active = name
        work = 0
        while True:
            obj = self.objects[self.active]
            child_name = obj.fields[0]
            child = self.objects[child_name] if child_name else None
            # Published pair refinement: transient carried owner is private.
            carry = (remaining - work >= 4 and child and child.owners == 1
                     and child.kind == "record" and len(child.fields) == 1)
            obj.cursor = 1
            if carry:
                child.owners = 0
                child.dead = True
                self._finish(obj.name)
                self.active = child.name
                work += 2
                self.check()  # Semantic pair boundary; C carries private state.
                continue
            self.recent_turn ^= 1
            self._drop(child_name)
            self.recent_turn ^= 1
            self._finish(obj.name)
            self.pending -= 1
            self.active = None
            return work + 2

    def _list_run(self, remaining):
        if self.recent or not self.active:
            return 0
        obj = self.objects[self.active]
        if obj.kind != "list":
            return 0
        count = min(remaining, len(obj.fields) - obj.cursor)
        work = 0
        for _ in range(count):
            self.recent_turn ^= 1
            child = obj.fields[obj.cursor]
            obj.cursor += 1
            self._drop(child)
            work += 1
            self.check()
            if self.recent:
                break
        return work

    def poll(self, budget):
        budget = min(budget, self.ceiling)
        work = 0
        object_only = not self.frames and not self.chunks
        while work < budget and self.pending:
            if object_only:
                before = self.frees
                paired = self._pair_run(budget - work) if self.optimized else 0
                if paired:
                    assert self.frees - before <= paired
                    work += paired
                    self.check()
                    continue
                listed = self._list_run(budget - work) if self.optimized else 0
                if listed:
                    assert self.frees - before <= listed
                    work += listed
                    continue
                queue = 0
            else:
                queue = self.next_queue
                for _ in range(3):
                    ready = [bool(self.active or self.old or self.recent),
                             bool(self.frames), bool(self.chunks)]
                    if ready[queue]:
                        break
                    queue = (queue + 1) % 3
                self.next_queue = (queue + 1) % 3
            before = self.frees
            [self._object_unit, self._frame_unit, self._chunk_unit][queue]()
            assert self.frees - before <= 1
            work += 1
            self.trace.append(queue)
            self.check()
        if object_only and work:
            self.next_queue = 1
        self.units += work
        assert work <= budget
        return work

    def check(self):
        tasks = list(self.old) + self.recent + ([self.active] if self.active else [])
        assert len(tasks) == len(set(tasks)), "duplicate task membership"
        assert self.pending == len(tasks) + len(self.frames) + len(self.chunks), "task count"
        owners = Counter({k: v for k, v in self.roots.items() if v})
        for obj in self.objects.values():
            if obj.freed:
                continue
            if obj.dead:
                assert obj.name in tasks and obj.owners == 0
            else:
                assert obj.owners > 0 and obj.name not in tasks
            for child in obj.fields[obj.cursor if obj.dead else 0:]:
                if child:
                    owners[child] += 1
            if obj.backing:
                owners[obj.backing] += 1
        for frame in self.live_frames + list(self.frames):
            assert len(frame.written) == len(set(frame.written))
            for index in frame.written:
                if frame.values[index]:
                    owners[frame.values[index]] += 1
            for chunk in frame.chunks:
                for child in chunk:
                    owners[child] += 1
        for chunk in self.chunks:
            for child in chunk:
                owners[child] += 1
        for name, obj in self.objects.items():
            assert obj.owners == owners[name], (name, obj.owners, owners[name])
            if obj.freed:
                assert not owners[name]

    def snapshot(self):
        return (self.pending, self.next_queue, self.recent_turn, self.active,
                tuple(self.old), tuple(self.recent), self.frees,
                tuple((k, o.owners, o.cursor, o.dead, o.freed)
                      for k, o in sorted(self.objects.items())),
                tuple(tuple((i, f.values[i]) for i in f.written) for f in self.frames),
                tuple(tuple(c) for c in self.chunks))

    def drain(self):
        bound = 10 + 4 * (len(self.objects) + sum(len(o.fields) for o in self.objects.values())
                          + sum(len(f.written) + 1 for f in self.frames)
                          + sum(len(c) + 1 for c in self.chunks))
        for _ in range(bound):
            if not self.pending:
                return
            assert self.poll(1) == 1
        raise AssertionError("finite workload failed to drain")


_SOURCE_TOKENS = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    r'|\w+|<<=|>>=|\.\.\.|->|==|!=|<=|>=|&&|\|\||\+\+|--|\+=|-=' 
    r'|\*=|/=|%=|&=|\|=|\^=|<<|>>|::|[^\s]')


def audited_source_fingerprint(source, functions=None):
    """Comment/whitespace-insensitive freshness aid, not a C semantic proof.

    Whole RC fragments or named audited functions only. Raw file hashes remain
    provenance. Unrelated compiler/native functions do not stale this audit.
    """
    tokens = list(_SOURCE_TOKENS.finditer(source))
    if functions:
        masked = list(source)
        for token in tokens:
            value = token.group()
            if value.startswith(('//', '/*', '"', "'")):
                masked[token.start():token.end()] = ' ' * len(value)
        masked = ''.join(masked)
        excerpts = []
        for name in functions:
            found = []
            for match in re.finditer(r'\b' + re.escape(name) + r'\s*\(', masked):
                start = match.end() - 1
                depth = 1
                position = start + 1
                while depth and position < len(masked):
                    depth += (masked[position] == '(') - (masked[position] == ')')
                    position += 1
                while position < len(masked) and masked[position].isspace():
                    position += 1
                if position == len(masked) or masked[position] != '{':
                    continue
                depth = 1
                end = position + 1
                while depth and end < len(masked):
                    depth += (masked[end] == '{') - (masked[end] == '}')
                    end += 1
                assert depth == 0
                beginning = source.rfind('\n', 0, match.start()) + 1
                found.append(source[beginning:end])
            assert found, 'audited function missing: ' + name
            excerpts.extend(found)
        source = '\n'.join(excerpts)
    normalized = [token.group() for token in _SOURCE_TOKENS.finditer(source)
                  if not token.group().startswith(('//', '/*'))]
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False).encode()).hexdigest()


def capture_trace_state(model, label):
    """Copy all mutable state; later polling must not rewrite old evidence."""
    return {'label': label, 'pending_tasks': model.pending,
            'managed_destructions': model.frees, 'active_object': model.active,
            'next_queue': model.next_queue, 'recent_turn': model.recent_turn,
            'old': list(model.old), 'recent': list(model.recent),
            'frames': len(model.frames), 'chunks': [len(c) for c in model.chunks],
            'objects': {k: {'owners': v.owners, 'cursor': v.cursor,
                            'dead': v.dead, 'freed': v.freed}
                        for k, v in model.objects.items()}}


class AccountingTests(unittest.TestCase):
    def test_poll_clamps_oversized_request_to_configured_budget(self):
        for ceiling in (1, 2, 5, 32):
            model = Model(ceiling)
            model.new('wide', fields=[None] * 100)
            model.release('wide')
            self.assertEqual(model.poll(2**64 - 1), ceiling)
            self.assertEqual(model.units, ceiling)
            model.drain()
            self.assertEqual(model.frees, 1)

    def test_trace_snapshots_do_not_alias_later_mutations(self):
        model = Model(1)
        model.enter(0)
        model.new('root', 'text')
        model.new('view', 'text', backing='root')
        model.release('root')
        model.keep('view')
        model.step()
        snapshot = capture_trace_state(model, 'before view visit')
        original = copy.deepcopy(snapshot)
        model.poll(1)
        self.assertEqual(model.recent, ['root'])
        self.assertEqual(snapshot, original)
        self.assertEqual(snapshot['recent'], [])
        self.assertEqual(snapshot['objects']['root']['owners'], 1)

    def test_production_source_matches_audited_snapshot(self):
        root = Path(__file__).resolve().parent.parent
        manifest = root / 'research/2026-10-memory/literature-accounting-source-map.json'
        for path, entry in json.loads(manifest.read_text())['sources'].items():
            actual = audited_source_fingerprint((root / path).read_text(), entry.get('functions'))
            self.assertEqual(actual, entry['audited_token_sha256'], path + ': audited mechanism is stale; '
                             'review changed source and explicitly repin the manifest. '
                             'Model success alone does not verify changed production code.')

    def test_source_fingerprint_ignores_comments_but_detects_body_change(self):
        before = 'void audited(int n) { /* old */ if (n) work(1); }\nvoid other() { x(); }'
        comments = before.replace('/* old */', '/* new\ncomment */')
        unrelated = before.replace('x();', 'y();')
        changed = before.replace('work(1)', 'work(2)')
        fingerprint = audited_source_fingerprint(before, ['audited'])
        self.assertEqual(fingerprint, audited_source_fingerprint(comments, ['audited']))
        self.assertEqual(fingerprint, audited_source_fingerprint(unrelated, ['audited']))
        self.assertNotEqual(fingerprint, audited_source_fingerprint(changed, ['audited']))

    def test_public_rc_hooks_view_chunk_and_replacement(self):
        for budget in (1, 2, 5, 32):
            model = Model(budget)
            model.new('root', 'text')
            model.new('view', 'text', backing='root')
            model.new('local', 'text')
            model.new('replacement', 'text')
            self.assertLessEqual(model.public_enter(1), budget)
            self.assertLessEqual(model.release('root', service=True), budget)
            self.assertLessEqual(model.public_keep('view'), 2 * budget)
            before = model.frees
            self.assertLessEqual(model.public_step(), budget)
            self.assertLessEqual(model.frees - before, budget)
            self.assertLessEqual(model.public_local(0, 'local', take=True), budget)
            self.assertLessEqual(model.public_local(0, 'replacement', take=True), budget)
            self.assertLessEqual(model.public_leave(), budget)
            model.drain()
            self.assertEqual(model.frees, 4)

    def test_partial_chunk_counter(self):
        for size in (1, 7, 8, 9, 15, 16, 17):
            m = Model()
            m.enter(0)
            for i in range(size):
                m.keep(m.new(str(i), "text"))
            m.step()
            self.assertEqual(m.pending, (size + 7) // 8)
            m.drain()
            self.assertEqual(m.frees, size)

    def test_view_root_separate_destructions(self):
        m = Model(1)
        m.enter(0)
        m.new("root", "text")
        m.new("view", "text", backing="root")
        m.release("root")
        m.keep("view")
        m.step()
        before = m.frees
        self.assertEqual(m.poll(1), 1)
        self.assertEqual(m.frees - before, 1)
        self.assertEqual(m.pending, 2)  # Empty chunk plus queued owning Text.
        m.drain()
        self.assertEqual(m.frees, 2)

    def test_sparse_move_replace_and_cache_reuse(self):
        m = Model()
        for declared in (12, 2, 16):
            frame = m.enter(declared)
            name = m.new(str(declared), "text")
            m.local(declared - 1, name, take=True)
            self.assertEqual(m.move(declared - 1), name)
            m.local(declared - 1, name)
            m.local(declared - 1, name)  # Written index must remain unique.
            self.assertEqual(frame.written, [declared - 1])
            m.move(declared - 1)
            m.leave()
            before = m.units
            m.drain()
            self.assertEqual(m.units - before, 2)  # Null visit + frame finish.
            m.release(name)
            m.release(name)
        self.assertEqual(m.frees, 3)

    def test_three_queues_continue_with_budget_one(self):
        m = Model(1)
        m.enter(1)
        m.new("leaf", "text")
        m.new("wide", fields=["leaf"] * 30)
        m.release("leaf")
        m.release("wide")
        for i in range(8):
            m.keep(m.new("temp" + str(i), "text"))
        m.local(0, m.new("local", "text"), take=True)
        m.leave()
        for _ in range(6):
            self.assertEqual(m.poll(1), 1)
        self.assertEqual(m.trace[:6], [0, 1, 2, 0, 1, 2])
        m.drain()
        self.assertEqual(m.frees, 11)

    def test_old_batch_survives_continual_arrivals(self):
        m = Model(1)
        m.new("old", fields=[None] * 128)
        m.release("old")
        m.poll(1)
        for i in range(100):
            m.new("arrival" + str(i), fields=[None] * 3)
            m.release("arrival" + str(i))
            m.poll(1)
        self.assertGreaterEqual(m.objects["old"].cursor, 51)
        m.drain()
        self.assertEqual(m.frees, 101)

    def test_pair_fusion_public_boundary_refinement(self):
        comparisons = 0
        for length in (1, 2, 3, 7, 12):
            for terminal in ("text", "scalar", "shared", "null", "wide"):
                for budget in (1, 2, 3, 4, 5, 7, 16):
                    m = Model(32)
                    child = None
                    if terminal != "null":
                        child = m.new("end", "text" if terminal == "text" else "record",
                                      [None] * 3 if terminal == "wide" else [])
                    for i in range(length):
                        parent = m.new("n" + str(i), fields=[child])
                        if child and not (i == 0 and terminal == "shared"):
                            m.release(child)
                        child = parent
                    m.release(child)
                    fused = copy.deepcopy(m)
                    fused.optimized = True
                    while m.pending:
                        self.assertEqual(m.poll(budget), fused.poll(budget))
                        self.assertEqual(m.snapshot(), fused.snapshot())
                        comparisons += 1
                    if terminal == "shared":
                        m.release("end")
                        fused.release("end")
                    self.assertEqual(m.frees, fused.frees)
        self.assertGreater(comparisons, 100)

    def test_invariant_rejects_deliberate_model_mutants(self):
        m = Model()
        m.new("leaf", "text")
        m.new("parent", fields=["leaf"])
        m.release("leaf")
        m.release("parent")
        for mutate in (lambda x: setattr(x, "pending", x.pending - 1),
                       lambda x: x.recent.append("parent"),
                       lambda x: setattr(x.objects["leaf"], "owners", 0),
                       lambda x: setattr(x.objects["parent"], "cursor", 1)):
            bad = copy.deepcopy(m)
            mutate(bad)
            with self.assertRaises(AssertionError):
                bad.check()

    def test_list_batch_stops_on_new_task_and_later_queue_arrivals(self):
        for budget in (1, 2, 3, 5, 7, 16):
            for special in (0, 1, 7, 18):
                m = Model(32)
                leaves = []
                for i in range(19):
                    name = "leaf" + str(i)
                    if i == special:
                        m.new("root", "text")
                        m.new(name, "text", backing="root")
                        m.release("root")
                    else:
                        m.new(name, "record", [None] * 2 if i % 7 == 0 else [])
                    leaves.append(name)
                m.new("list", "list", leaves)
                for name in leaves:
                    m.release(name)
                m.release("list")
                fused = copy.deepcopy(m)
                fused.optimized = True
                for model in (m, fused):
                    model.poll(budget)
                    before = model.snapshot()
                    self.assertEqual(model.poll(0), 0)
                    self.assertEqual(before, model.snapshot())
                    model.enter(2)
                    model.local(1, model.new("local", "text"), take=True)
                    model.keep(model.new("temp", "text"))
                    model.leave()
                self.assertEqual(m.snapshot(), fused.snapshot())
                while m.pending:
                    self.assertEqual(m.poll(budget), fused.poll(budget))
                    self.assertEqual(m.snapshot(), fused.snapshot())
                self.assertEqual(m.frees, 23)

    def test_task_count_does_not_measure_remaining_work(self):
        costs = []
        for arity in (1, 128, 8193):
            m = Model()
            m.new("record", fields=[None] * arity)
            m.release("record")
            self.assertEqual(m.pending, 1)
            m.drain()
            costs.append(m.units)
        self.assertEqual(costs, [2, 129, 8194])

    def test_record_cursor_encoding_preserves_reference_flags(self):
        # Direct representation contract: upper7 cursor bits, lower1 map bit.
        # This does not execute C pointer arithmetic or validate record layout.
        for length in (1, 2, 3, 8, 127, 128, 129, 1024):
            for cursor in sorted(set((0, 1, min(127, length), min(128, length), length))):
                flags = [int(i % 3 == 0) for i in range(length)]
                encoded = flags[:]
                value = cursor
                for i in range(min(length, 10)):  # ceil(64/7).
                    encoded[i] = flags[i] | ((value & 127) << 1)
                    value >>= 7
                decoded = sum((encoded[i] >> 1) << (7 * i)
                              for i in range(min(length, 10)))
                self.assertEqual(decoded, cursor)
                self.assertEqual([byte & 1 for byte in encoded], flags)


if __name__ == "__main__":
    unittest.main(verbosity=2)
