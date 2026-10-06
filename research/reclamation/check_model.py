#!/usr/bin/env python3
"""Finite abstract scheduling checks; these are not a verification of C code.

Each task has a finite amount of work. Object arrivals go on a recent stack;
an immutable captured batch gets alternating service. The model intentionally
excludes unary/batched shortcuts, allocation, and memory representation.
"""
from collections import deque
from dataclasses import dataclass
import itertools
import unittest


@dataclass
class Task:
    remaining: int
    visits: int = 0


class Scheduler:
    def __init__(self, next_queue=0, recent_turn=0):
        self.recent = deque()
        self.old = deque()
        self.frames = deque()
        self.chunks = deque()
        self.next_queue = next_queue
        self.recent_turn = recent_turn

    def tick(self):
        for offset in range(3):
            queue = (self.next_queue + offset) % 3
            if (bool(self.old or self.recent), bool(self.frames), bool(self.chunks))[queue]:
                break
        else:
            return None
        self.next_queue = (queue + 1) % 3
        if queue == 0:
            if not self.old:
                self.old, self.recent = self.recent, deque()
            tasks = self.recent if self.recent_turn and self.recent else self.old
            self.recent_turn ^= 1
        else:
            tasks = self.frames if queue == 1 else self.chunks
        task = tasks[0]
        task.remaining -= 1
        task.visits += 1
        if not task.remaining:
            tasks.popleft()
        return queue, task

    def poll(self, requested, configured):
        return [event for _ in range(min(requested, configured))
                if (event := self.tick()) is not None]


class SchedulingChecks(unittest.TestCase):
    def test_ready_queues_get_service_within_three_units(self):
        for phase in range(3):
            s = Scheduler(phase)
            s.recent.append(Task(100)); s.frames.append(Task(100)); s.chunks.append(Task(100))
            self.assertEqual({s.tick()[0] for _ in range(3)}, {0, 1, 2})

    def test_captured_head_progresses_under_continuous_arrivals(self):
        for phase, parity in itertools.product(range(3), range(2)):
            s = Scheduler(phase, parity)
            oldest = Task(10000)
            s.old.append(oldest); s.frames.append(Task(10000)); s.chunks.append(Task(10000))
            for _ in range(100):
                before = oldest.visits
                for _ in range(6):
                    s.recent.appendleft(Task(10000))
                    s.tick()
                self.assertGreaterEqual(oldest.visits - before, 1)

    def test_every_member_of_a_captured_batch_finishes(self):
        for phase, parity in itertools.product(range(3), range(2)):
            s = Scheduler(phase, parity)
            captured = [Task(n) for n in [7, 1, 9, 3]]
            s.old.extend(captured)
            s.frames.append(Task(10000)); s.chunks.append(Task(10000))
            for _ in range(6 * sum(t.remaining for t in captured)):
                s.recent.appendleft(Task(10000))
                s.tick()
            self.assertTrue(all(t.remaining == 0 for t in captured))

    def test_budget_and_partition_invariance(self):
        for k in [1, 2, 8, 32, 1024]:
            for request in [0, 1, 3, 32, 2048]:
                s = Scheduler(); s.recent.append(Task(10000))
                self.assertEqual(len(s.poll(request, k)), min(request, k))
        def initial():
            s = Scheduler(); s.recent.extend([Task(17), Task(19)])
            s.frames.append(Task(31)); s.chunks.append(Task(13)); return s
        a, b = initial(), initial()
        one = [q for q, _ in a.poll(80, 1024)]
        split = [q for n in [1, 3, 2, 17, 32, 25] for q, _ in b.poll(n, 32)]
        self.assertEqual(one, split)

    def test_lifo_counterexample(self):
        old = Task(1)
        stack = [old]
        for _ in range(10000):
            stack.append(Task(1))
            stack[-1].remaining -= 1
            stack.pop()
        self.assertEqual(old.remaining, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
