#!/usr/bin/env python3
"""Independent CFG-oracle checks before running generated compiler programs."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "peer_control", ROOT / "scripts/peer-research-control.py")
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)


class ControlModelHarness(unittest.TestCase):
    def test_a_cycle_does_not_imply_fallthrough(self):
        graph = {"entry": 0, "exit": 2, "edges": {0: [1], 1: [0], 2: []}}
        self.assertFalse(CONTROL.fallthrough_reachable(graph))
        graph["edges"][1].append(2)
        self.assertTrue(CONTROL.fallthrough_reachable(graph))

    def test_broken_graph_targets_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "target"):
            CONTROL.fallthrough_reachable(
                {"entry": 0, "exit": 1, "edges": {0: [99], 1: []}})

    def test_unreachable_break_does_not_create_an_exit(self):
        body = [{"kind": "while", "condition": "true", "body": [
            {"kind": "return", "value": 41}, {"kind": "break"}]}]
        self.assertFalse(CONTROL.fallthrough_reachable(CONTROL.build_graph(body)))
        body[0]["body"].reverse()
        self.assertTrue(CONTROL.fallthrough_reachable(CONTROL.build_graph(body)))

    def test_inner_break_does_not_exit_the_outer_loop(self):
        for kind in ("while", "for"):
            with self.subTest(kind=kind):
                inner = {"kind": kind, "condition": "true", "body": [{"kind": "break"}]}
                body = [{"kind": "while", "condition": "true", "body": [
                    inner, {"kind": "return", "value": 42}]}]
                self.assertFalse(CONTROL.fallthrough_reachable(CONTROL.build_graph(body)))

    def test_conditional_return_and_continue_have_no_fallthrough(self):
        body = [{"kind": "while", "condition": "true", "body": [
            {"kind": "if", "then": [{"kind": "return", "value": 43}],
             "else": [{"kind": "continue"}]}]}]
        self.assertFalse(CONTROL.fallthrough_reachable(CONTROL.build_graph(body)))

    def test_unknown_loop_condition_keeps_the_zero_iteration_exit(self):
        body = [{"kind": "while", "condition": "flag", "body": [
            {"kind": "return", "value": 44}]}]
        self.assertTrue(CONTROL.fallthrough_reachable(CONTROL.build_graph(body)))
        body.append({"kind": "return", "value": 45})
        self.assertFalse(CONTROL.fallthrough_reachable(CONTROL.build_graph(body)))

    def test_correlated_conditions_are_inconclusive_in_the_graph(self):
        body = [
            {"kind": "if", "then": [{"kind": "return", "value": 1}], "else": []},
            {"kind": "if", "then": [], "else": [{"kind": "return", "value": 2}]},
        ]
        result = CONTROL.classify_case(body, CONTROL.build_graph(body))
        self.assertIsNone(result["expected_accept"])
        self.assertEqual(result["classification"], "inconclusive_graph_overapproximation")
        self.assertEqual(result["execution_oracle"]["false"]["value"], 2)
        self.assertEqual(result["execution_oracle"]["true"]["value"], 1)

    def test_a_concrete_fallthrough_witness_requires_rejection(self):
        body = [{"kind": "if", "then": [{"kind": "return", "value": 1}], "else": []}]
        result = CONTROL.classify_case(body, CONTROL.build_graph(body))
        self.assertIs(result["expected_accept"], False)
        self.assertEqual(result["classification"], "concrete_fallthrough")

    def test_conflicting_oracles_are_rejected(self):
        closed = {"entry": 1, "exit": 0, "edges": {0: [], 1: [1]}}
        with self.assertRaisesRegex(ValueError, "contradict"):
            CONTROL.classify_case([], closed)

    def test_seeded_generation_is_deterministic_and_bounded(self):
        for seed in range(32):
            with self.subTest(seed=seed):
                first = CONTROL.generate_case(seed, node_budget=24)
                self.assertEqual(first, CONTROL.generate_case(seed, node_budget=24))
                self.assertLessEqual(len(first["graph"]["edges"]), 3 * 24 + 1)
                reachable = CONTROL.fallthrough_reachable(first["graph"])
                if first["expected_accept"] is True:
                    self.assertFalse(reachable)
                elif first["expected_accept"] is False:
                    self.assertTrue(reachable)
                    self.assertIn("fallthrough", [result["outcome"] for result
                                  in first["execution_oracle"].values()])
                else:
                    self.assertTrue(reachable)
                    self.assertNotIn("fallthrough", [result["outcome"] for result
                                     in first["execution_oracle"].values()])
                self.assertIn("function value(flag: Boolean): Integer", first["source"])

    def test_a_valid_diagnostic_does_not_link(self):
        case = CONTROL.case_from_body(7, [])
        commands = []
        def runner(command, *, timeout):
            commands.append(command)
            return subprocess.CompletedProcess(command, 1, "", "must return a value on every path")
        with tempfile.TemporaryDirectory() as directory:
            result = CONTROL.verify_case(case, Path(directory), Path("compiler"), Path("runtime.o"),
                                         "clang", runner=runner)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(commands), 1)

    def test_an_unexpected_acceptance_is_retained_as_a_failure(self):
        case = CONTROL.case_from_body(7, [])
        def runner(command, *, timeout):
            Path(command[2]).write_text("invalid success output")
            return subprocess.CompletedProcess(command, 0, "", "")
        with tempfile.TemporaryDirectory() as directory:
            result = CONTROL.verify_case(case, Path(directory), Path("compiler"), Path("runtime.o"),
                                         "clang", runner=runner)
            self.assertTrue(Path(result["source"]).exists())
        self.assertEqual(result["failure"], "unexpected_accept")

    def test_native_outputs_are_checked_at_both_optimizations(self):
        case = CONTROL.case_from_body(7, [{"kind": "return", "value": 42}])
        commands = []
        def runner(command, *, timeout):
            commands.append(command)
            if command[0] == "compiler":
                Path(command[2]).write_text("test LLVM placeholder")
            output = case["expected_stdout"] if len(command) == 1 else ""
            return subprocess.CompletedProcess(command, 0, output, "")
        with tempfile.TemporaryDirectory() as directory:
            result = CONTROL.verify_case(case, Path(directory), Path("compiler"), Path("runtime.o"),
                                         "clang", runner=runner)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(commands), 5)
        self.assertIn("-O0", commands[1])
        self.assertIn("-O2", commands[3])

    def test_a_timeout_is_not_an_assertion_failure(self):
        def runner(command, *, timeout):
            raise subprocess.TimeoutExpired(command, timeout)
        with tempfile.TemporaryDirectory() as directory:
            result = CONTROL.verify_case(CONTROL.case_from_body(7, []), Path(directory),
                                         Path("compiler"), Path("runtime.o"), "clang", runner=runner)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["failure"], "process_timeout")

    def test_missing_executable_is_retained_as_an_infrastructure_error(self):
        def runner(command, *, timeout):
            raise FileNotFoundError("missing compiler")
        with tempfile.TemporaryDirectory() as directory:
            result = CONTROL.verify_case(CONTROL.case_from_body(7, []), Path(directory),
                                         Path("compiler"), Path("runtime.o"), "clang", runner=runner)
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertEqual(result["failure"], "process_setup")
        self.assertIn("missing compiler", result["commands"][0]["infrastructure_error"])

    def test_minimization_keeps_a_real_failure_and_bounds_attempts(self):
        body = [{"kind": "return", "value": 42},
                {"kind": "while", "condition": "true", "body": [{"kind": "continue"}]}]
        def retains_failure(candidate):
            return any(row["kind"] == "return" and row["value"] == 42 for row in candidate)
        minimized, attempts = CONTROL.minimize_body(body, retains_failure, max_attempts=20)
        self.assertEqual(minimized, [{"kind": "return", "value": 42}])
        self.assertLessEqual(attempts, 20)
        unchanged, attempts = CONTROL.minimize_body(body, retains_failure, max_attempts=0)
        self.assertEqual(unchanged, body)
        self.assertEqual(attempts, 0)

    def test_simplification_does_not_emit_a_stray_loop_transfer(self):
        body = [{"kind": "while", "condition": "true", "body": [{"kind": "break"}]}]
        for candidate in CONTROL.simplifications(body):
            CONTROL.build_graph(candidate)
            self.assertNotEqual(candidate, [{"kind": "break"}])


if __name__ == "__main__":
    unittest.main()
