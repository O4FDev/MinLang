#!/usr/bin/env python3
"""Executable proof checks and counterexamples; NEVER a runtime heap scanner.

The type model overapproximates List/record types as arbitrary directed graphs.
An object constructor may point only at earlier completed objects. A mutation
is allowed only on designated mutable types and when the element type cannot
reach the receiver's type. Kahn's algorithm independently checks the strongest
possible object graph, containing every permitted edge, for each finite case.
"""
import itertools
import unittest


def reachable(edges, start, goal):
    pending, seen = [start], set()
    while pending:
        node = pending.pop()
        if node == goal:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(edges[node])
    return False


def acyclic(edges):
    counts = [sum(target in row for row in edges) for target in range(len(edges))]
    pending = [i for i, count in enumerate(counts) if not count]
    visited = 0
    while pending:
        node = pending.pop()
        visited += 1
        for target in edges[node]:
            counts[target] -= 1
            if not counts[target]:
                pending.append(target)
    return visited == len(edges)


class ProductionContracts(unittest.TestCase):
    def test_constructor_and_type_guard_preserve_acyclicity(self):
        checked = 0
        for bits in range(512):
            types = [{j for j in range(3) if bits & (1 << (i * 3 + j))} for i in range(3)]
            returns = [[reachable(types, j, i) for j in range(3)] for i in range(3)]
            for mutable_bits in range(8):
                for object_types in itertools.product(range(3), repeat=3):
                    graph = [set() for _ in range(3)]
                    for source, source_type in enumerate(object_types):
                        for target, target_type in enumerate(object_types):
                            if target_type not in types[source_type]:
                                continue
                            construction = target < source
                            mutation = mutable_bits & (1 << source_type) and not returns[source_type][target_type]
                            if construction or mutation:
                                graph[source].add(target)
                    self.assertTrue(acyclic(graph), (types, mutable_bits, object_types, graph))
                    checked += 1
        self.assertEqual(checked, 110592)

    def test_only_checking_direct_types_is_unsound(self):
        # Mutable List<A> -> A -> List<B> -> B -> original List<A>.
        types = [{1}, {2}, {3}, {0}]
        self.assertNotIn(0, types[1])
        self.assertTrue(reachable(types, 1, 0))
        self.assertFalse(acyclic(types))

    def test_automatic_weak_cycle_edge_loses_observable_object(self):
        # Absurdly simple proposal: choose one back-edge as non-owning.
        # Root A still semantically reaches B, but B's count becomes zero.
        semantic_edges = [{1}, {0}]
        owning_edges = [set(), {0}]
        roots = {0}
        counts = [int(i in roots) + sum(i in row for row in owning_edges) for i in range(2)]
        self.assertTrue(reachable(semantic_edges, 0, 1))
        self.assertEqual(counts[1], 0)

    def test_fixed_cleanup_slice_does_not_bound_retained_bytes(self):
        # A root of N live cells dies all at once. No future polls implies no
        # future progress. Bounded work per poll is not a bound on dead storage.
        budget = 32
        debts = [max(0, objects - budget) for objects in (100, 10000, 1000000)]
        self.assertEqual(debts, [68, 9968, 999968])

    def test_fixed_pool_fragmentation_is_a_capacity_limit(self):
        # A buddy arena with eight smallest blocks; alternating live blocks
        # prevent any 2-block coalescence despite four free blocks in total.
        free = {0, 2, 4, 6}
        self.assertEqual(len(free), 4)
        self.assertFalse(any({base, base + 1} <= free for base in range(0, 8, 2)))

    def test_constant_per_drop_does_not_bound_frame_leave(self):
        visits_per_drop = 32
        slots = (1, 1024, 1048576)
        work = [count * visits_per_drop for count in slots]
        self.assertEqual(work[-1], 33554432)
        self.assertGreater(work[-1], work[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
