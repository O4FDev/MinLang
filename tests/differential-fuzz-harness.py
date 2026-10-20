#!/usr/bin/env python3
"""Fault-injection and independent oracle checks for differential-fuzz.py."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("differential-fuzz.py")
MODULE_SPEC = importlib.util.spec_from_file_location("minyar_differential_fuzz", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
fuzz = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = fuzz
MODULE_SPEC.loader.exec_module(fuzz)


class IntegerOracleTests(unittest.TestCase):
    def test_signed64_boundaries_and_multiple_wraps(self):
        examples = (
            (0, 0), (-1, -1), (fuzz.MINIMUM, -(1 << 63)),
            (fuzz.MAXIMUM, (1 << 63) - 1), (1 << 63, -(1 << 63)),
            ((1 << 64) - 1, -1), (1 << 64, 0),
            (-(1 << 63) - 1, (1 << 63) - 1),
            ((1 << 130) + 17, 17), (-(1 << 130) - 17, -17),
        )
        for value, expected in examples:
            with self.subTest(value=value):
                self.assertEqual(fuzz.signed(value), expected)

    def test_division_truncates_toward_zero_without_float_rounding(self):
        examples = (
            (7, 3, 2), (-7, 3, -2), (7, -3, -2), (-7, -3, 2),
            (1, -3, 0), (-1, 3, 0), (0, -7, 0),
            ((1 << 63) - 1, 3, 3074457345618258602),
            (-(1 << 63), 3, -3074457345618258602),
        )
        for left, right, expected in examples:
            with self.subTest(left=left, right=right):
                actual = fuzz.quotient(left, right)
                self.assertEqual(actual, expected)
                remainder = left - actual * right
                self.assertLess(abs(remainder), abs(right))
                self.assertTrue(remainder == 0 or (remainder > 0) == (left > 0))
        with self.assertRaises(ZeroDivisionError):
            fuzz.quotient(1, 0)

    def expression(self, operator, left, right):
        rng = mock.Mock()
        rng.randrange.return_value = 1
        rng.choice.side_effect = [left, right, operator]
        return fuzz.expression(rng, 1, [left, right])

    def test_generated_division_guards_invalid_inputs_and_models_remainder(self):
        examples = (
            ("/", -7, 3, -2, "(left / right)"),
            ("%", -7, 3, -1, "(left % right)"),
            ("%", 7, -3, 1, "(left % right)"),
            ("/", 7, 0, 2, "(left / 3)"),
            ("/", -(1 << 63), -1, -3074457345618258602, "(left / 3)"),
            ("%", -(1 << 63), -1, -2, "(left % 3)"),
        )
        for operator, left, right, value, text in examples:
            with self.subTest(operator=operator, left=left, right=right):
                result = self.expression(operator, fuzz.Expression("left", left),
                                         fuzz.Expression("right", right))
                self.assertEqual((result.text, result.value), (text, value))

    def test_checked_overflow_is_omitted_and_wrapping_overflow_is_modeled(self):
        left = fuzz.Expression("maximum", (1 << 63) - 1)
        right = fuzz.Expression("one", 1)
        self.assertEqual(self.expression("+", left, right), left)
        wrapped = self.expression("wrappingAdd", left, right)
        self.assertEqual(wrapped.value, -(1 << 63))
        self.assertEqual(wrapped.text, "wrappingAdd(maximum, one)")


class GenerationTests(unittest.TestCase):
    def test_every_family_is_deterministic_and_has_observable_checks(self):
        self.assertEqual(set(fuzz.FAMILIES),
                         {"arithmetic", "control", "aliases", "maps", "bytes", "callbacks",
                          "choices"})
        global_state = random.getstate()
        for family in fuzz.FAMILIES:
            for size in (1, 12):
                with self.subTest(family=family, size=size):
                    case = fuzz.Case(family, 0x20261020, size)
                    first = fuzz.generate_case(case)
                    self.assertEqual(first, fuzz.generate_case(case))
                    self.assertTrue(first.body)
                    self.assertTrue(first.expected)
                    checks = sum(line.strip().startswith(("checkInteger(", "checkText(",
                                                         "checkBoolean(")) for line in first.body)
                    self.assertEqual(checks, len(first.expected))
                    labels = []
                    for line in first.body:
                        if line.strip().startswith(("checkInteger(", "checkText(", "checkBoolean(")):
                            label = re.search(r', ("(?:[^"\\]|\\.)*")\)$', line)
                            self.assertIsNotNone(label, line)
                            labels.append(json.loads(label.group(1)))
                    self.assertEqual(labels, [f"{family}:{case.seed}:{index}"
                                              for index in range(len(first.expected))])
                    source, expected = fuzz.render([case])
                    self.assertIn(f"// {family}, seed {case.seed}, size {size}\n", source)
                    self.assertIn("function fuzzCase0() {", source)
                    self.assertTrue(source.endswith("fuzzCase0()\n"))
                    self.assertEqual(expected,
                                     ("\n".join(first.expected) + "\n").encode("utf-8"))
        self.assertEqual(random.getstate(), global_state)

    def test_check_literals_preserve_boolean_and_unicode_stdout(self):
        block = fuzz.Block()
        block.check("truth", True)
        block.check("falsehood", False)
        block.check("message", 'café λ 🌙 "quoted"')
        block.check("number", -(1 << 63))
        self.assertEqual(block.expected,
                         ["case:0=true", "case:1=false", 'case:2=café λ 🌙 "quoted"',
                          "case:3=-9223372036854775808"])
        self.assertEqual(block.body[:2],
                         ['checkBoolean(truth, true, "case:0")',
                          'checkBoolean(falsehood, false, "case:1")'])
        self.assertIn('\\"quoted\\"', block.body[2])

    def test_observation_labels_survive_removing_an_earlier_family(self):
        selected = fuzz.Case("aliases", 0xC0DE, 4)
        original, _ = fuzz.render([fuzz.Case("arithmetic", 17, 2), selected])
        reduced, _ = fuzz.render([selected])
        pattern = r'check(?:Integer|Text|Boolean)\([^\n]+, "(aliases:49374:\d+)"\)'
        original_labels = re.findall(pattern, original)
        self.assertTrue(original_labels)
        self.assertEqual(original_labels, re.findall(pattern, reduced))
        self.assertEqual(len(original_labels), len(set(original_labels)))

    def test_saved_spec_replays_identical_source_and_exact_expected_bytes(self):
        cases = [fuzz.Case(family, 1000 + index, 7)
                 for index, family in enumerate(fuzz.FAMILIES)]
        with tempfile.TemporaryDirectory(prefix="minyar-fuzz-harness-") as temporary:
            root = Path(temporary)
            path, expected = fuzz.save_program(root / "initial", cases)
            spec = json.loads((path.parent / "spec.json").read_text(encoding="utf-8"))
            self.assertEqual(spec["version"], 1)
            replay = [fuzz.Case(**item) for item in spec["cases"]]
            replay_path, replay_expected = fuzz.save_program(root / "replay", replay)
            self.assertEqual(path.read_bytes(), replay_path.read_bytes())
            self.assertEqual(expected, replay_expected)
            self.assertEqual((path.parent / "expected.stdout").read_bytes(), expected)
            self.assertEqual(spec["cases"], [dataclasses.asdict(case) for case in cases])

    def test_replay_main_uses_recorded_cases_once(self):
        cases = [fuzz.Case("aliases", 0xC0DE, 9), fuzz.Case("bytes", 7, 3)]
        with tempfile.TemporaryDirectory(prefix="minyar-fuzz-harness-") as temporary:
            root = Path(temporary)
            _, _ = fuzz.save_program(root / "input", cases)
            compiler = root / "compiler"
            compiler.write_bytes(b"compiler identity fixture")
            argv = [str(MODULE_PATH), "--compiler-stage2", str(compiler),
                    "--compiler-stage3", str(compiler), "--programs", "11", "--size", "99",
                    "--replay", str(root / "input/spec.json"),
                    "--output-dir", str(root / "output")]
            with (mock.patch.object(sys, "argv", argv),
                  mock.patch.object(fuzz, "prepare_runtimes", return_value={}),
                  mock.patch.object(fuzz, "check_program", return_value=[]) as checked,
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(fuzz.main(), 0)
            checked.assert_called_once()
            self.assertEqual(checked.call_args.args[1], cases)
            reports = list((root / "output").glob("campaign-*/results.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["programs_passed"], 1)

    def test_repeatable_replay_preserves_each_recorded_program_in_order(self):
        programs = [[fuzz.Case("aliases", 0xC0DE, 9), fuzz.Case("bytes", 7, 3)],
                    [fuzz.Case("choices", 99, 5)]]
        with tempfile.TemporaryDirectory(prefix="minyar-fuzz-harness-") as temporary:
            root = Path(temporary)
            compiler = root / "compiler"
            compiler.write_bytes(b"compiler identity fixture")
            argv = [str(MODULE_PATH), "--compiler-stage2", str(compiler),
                    "--compiler-stage3", str(compiler), "--programs", "11", "--size", "99",
                    "--output-dir", str(root / "output")]
            for index, cases in enumerate(programs):
                fuzz.save_program(root / f"input-{index}", cases)
                argv.extend(("--replay", str(root / f"input-{index}/spec.json")))
            with (mock.patch.object(sys, "argv", argv),
                  mock.patch.object(fuzz, "prepare_runtimes", return_value={}),
                  mock.patch.object(fuzz, "check_program", return_value=[]) as checked,
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(fuzz.main(), 0)
            self.assertEqual([call.args[1] for call in checked.call_args_list], programs)
            self.assertEqual([call.args[2].name for call in checked.call_args_list],
                             ["program-0000", "program-0001"])
            reports = list((root / "output").glob("campaign-*/results.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["programs_passed"], 2)

    def test_alias_oracle_matches_independent_object_graph_replay(self):
        block = fuzz.generate_case(fuzz.Case("aliases", 0xC0DE, 48))
        records = {}
        bindings = {}
        observed = []
        operations = set()
        for line in block.body:
            creation = re.fullmatch(
                r'let (first|other) = FuzzCell \{ number: (-?\d+); '
                r'text: ("(?:[^"\\]|\\.)*"); values: \[(-?\d+)\] \}', line)
            if creation:
                name, number, text, value = creation.groups()
                records[name] = {"number": int(number), "text": json.loads(text),
                                 "values[0]": int(value)}
                continue
            if line == "let roots = [first, first, other]":
                bindings["roots"] = ["first", "first", "other"]
                continue
            if line == "let alias = roots":
                bindings["alias"] = bindings["roots"]
                continue
            if line == "let fork = roots.appended(first)":
                bindings["fork"] = bindings["roots"][:] + ["first"]
                continue
            replacement = re.fullmatch(r"roots\[(\d+)\] = alias\[(\d+)\]", line)
            if replacement:
                target, source = map(int, replacement.groups())
                bindings["roots"][target] = bindings["alias"][source]
                operations.add("slot")
                continue
            mutation = re.fullmatch(r"alias\[(\d+)\]\.(number|text) = (.+)", line)
            if mutation:
                position, field, value = mutation.groups()
                records[bindings["alias"][int(position)]][field] = json.loads(value)
                operations.add(field)
                continue
            if line in ("roots = []", "alias = []"):
                bindings[line.split()[0]] = []
                continue
            checkpoint = re.fullmatch(
                r'check(Integer|Text)\((roots|fork)\[(\d+)\]\.(number|text|values\[0\]), '
                r'(.+), ("(?:[^"\\]|\\.)*")\)',
                line)
            self.assertIsNotNone(checkpoint, f"unmodeled alias operation: {line}")
            kind, root, position, field, expected, label = checkpoint.groups()
            actual = records[bindings[root][int(position)]][field]
            self.assertEqual(actual, json.loads(expected), line)
            self.assertEqual(kind, "Text" if isinstance(actual, str) else "Integer")
            self.assertEqual(json.loads(label), f"aliases:49374:{len(observed)}")
            observed.append(f"aliases:49374:{len(observed)}={actual}")
        self.assertEqual(operations, {"number", "text", "slot"})
        self.assertEqual(observed, block.expected)
        self.assertEqual(bindings["roots"], [])
        self.assertEqual(bindings["alias"], [])
        self.assertEqual(bindings["fork"], ["first", "first", "other", "first"])

    def test_map_set_oracle_matches_independent_operation_replay(self):
        seed = 0xC0DE
        block = fuzz.generate_case(fuzz.Case("maps", seed, 12))
        records = {}
        sequences = {}
        maps = {}
        sets = {}
        text_maps = {}
        observed = []

        def text(expression):
            return "".join(json.loads(part) for part in expression.split(" + "))

        def key(expression):
            if expression in records:
                return tuple(records[expression])
            inline = re.fullmatch(
                r'FuzzKey \{ label: (.+); number: (-?\d+) \}', expression)
            self.assertIsNotNone(inline, f"unmodeled map key: {expression}")
            return text(inline.group(1)), int(inline.group(2))

        def evaluate(term):
            indexed = re.fullmatch(r'(table|tableAlias)\[(.+)\]\[0\]', term)
            if indexed:
                return maps[indexed.group(1)][key(indexed.group(2))][0]
            item = re.fullmatch(r'(\w+)\[0\]', term)
            if item and item.group(1) in sequences:
                return sequences[item.group(1)][0]
            lookup = re.fullmatch(r'evaluation\[("(?:[^"\\]|\\.)*")\]', term)
            if lookup:
                return text_maps["evaluation"][json.loads(lookup.group(1))]
            length = re.fullmatch(r'(\w+)\.length', term)
            if length:
                name = length.group(1)
                return len(maps[name] if name in maps else sets[name])
            method = re.fullmatch(r'(\w+)\.(has|contains|remove)\((.+)\)', term)
            if method:
                name, operation, argument = method.groups()
                frozen = key(argument)
                container = maps[name] if name in maps else sets[name]
                present = frozen in container
                if operation == "remove" and present:
                    if name in maps:
                        del container[frozen]
                    else:
                        container.remove(frozen)
                return present
            self.fail(f"unmodeled map observation: {term}")

        for line in block.body:
            checkpoint = re.fullmatch(
                r'check(Integer|Text|Boolean)\((.*), '
                r'(true|false|-?\d+|"(?:[^"\\]|\\.)*"), '
                r'("(?:[^"\\]|\\.)*")\)', line)
            if checkpoint:
                kind, term, expected_text, label_text = checkpoint.groups()
                actual = evaluate(term)
                expected = json.loads(expected_text)
                self.assertEqual(actual, expected, line)
                actual_kind = ("Boolean" if isinstance(actual, bool) else
                               "Text" if isinstance(actual, str) else "Integer")
                self.assertEqual(kind, actual_kind, line)
                label = json.loads(label_text)
                self.assertEqual(label, f"maps:{seed}:{len(observed)}")
                displayed = actual if isinstance(actual, str) else fuzz.literal(actual)
                observed.append(f"{label}={displayed}")
                continue

            creation = re.fullmatch(
                r'let (\w+) = FuzzKey \{ label: (.+); number: (-?\d+) \}', line)
            if creation:
                name, label, number = creation.groups()
                records[name] = [text(label), int(number)]
                continue
            sequence = re.fullmatch(r'let (value\d*|saved\d*) = \[(.+)\]', line)
            if sequence:
                sequences[sequence.group(1)] = [text(sequence.group(2))]
                continue
            if line == "let table: Map<FuzzKey, List<Text>> = Map()":
                maps["table"] = {}
                continue
            if line == "let tableAlias = table":
                maps["tableAlias"] = maps["table"]
                continue
            if line == "let names: Set<FuzzKey> = Set()":
                sets["names"] = set()
                continue
            if line == "let namesAlias = names":
                sets["namesAlias"] = sets["names"]
                continue
            if line == "let evaluation = Map<Text, Text>()":
                text_maps["evaluation"] = {}
                continue
            evaluation_store = re.fullmatch(
                r'evaluation\[("(?:[^"\\]|\\.)*")\] = (.+)', line)
            if evaluation_store:
                text_maps["evaluation"][json.loads(evaluation_store.group(1))] = text(
                    evaluation_store.group(2))
                continue
            if line == 'evaluation[evaluation["key"]] = fuzzReset(evaluation)':
                frozen_text_key = text_maps["evaluation"]["key"]
                text_maps["evaluation"].clear()
                text_maps["evaluation"][frozen_text_key] = "after!"
                continue
            assignment = re.fullmatch(
                r'(table|tableAlias)\[(.+)\] = (value\d*|saved\d*)', line)
            if assignment:
                container, argument, sequence_name = assignment.groups()
                maps[container][key(argument)] = sequences[sequence_name]
                continue
            addition = re.fullmatch(r'(names|namesAlias)\.add\((.+)\)', line)
            if addition:
                sets[addition.group(1)].add(key(addition.group(2)))
                continue
            mutation = re.fullmatch(r'(\w+)\.(label|number) = (.+)', line)
            if mutation:
                name, field, value = mutation.groups()
                records[name][0 if field == "label" else 1] = (
                    text(value) if field == "label" else int(value))
                continue
            saved = re.fullmatch(
                r'let (saved\d*) = (table|tableAlias)\[(.+)\]', line)
            if saved:
                name, container, argument = saved.groups()
                sequences[name] = maps[container][key(argument)]
                continue
            clear = re.fullmatch(r'(table|tableAlias|names|namesAlias)\.clear\(\)', line)
            if clear:
                name = clear.group(1)
                (maps[name] if name in maps else sets[name]).clear()
                continue
            sequence_store = re.fullmatch(r'(\w+)\[0\] = (.+)', line)
            if sequence_store and sequence_store.group(1) in sequences:
                sequences[sequence_store.group(1)][0] = text(sequence_store.group(2))
                continue
            self.fail(f"unmodeled map operation: {line}")

        self.assertEqual(observed, block.expected)
        source = "\n".join(block.body)
        self.assertIn("let tableAlias = table", source)
        self.assertIn("let namesAlias = names", source)
        self.assertIn('label: "ke" + "y"', source)
        self.assertRegex(source, r'key\d+\.label = "changed-')
        self.assertIn('evaluation[evaluation["key"]] = fuzzReset(evaluation)', source)
        self.assertRegex(source, r"tableAlias\.remove\(FuzzKey \{")
        self.assertRegex(source, r"tableAlias\[FuzzKey \{")
        self.assertGreaterEqual(source.count("tableAlias.clear()"), 2)
        self.assertIn("namesAlias.clear()", source)
        self.assertRegex(source, r"saved\d+\[0\] = \"saved-")
        rendered, _ = fuzz.render([fuzz.Case("maps", seed, 1)])
        self.assertIn("record FuzzKey { label: Text; number: Integer }", rendered)
        self.assertIn("function fuzzReset(table: Map<Text, Text>): Text", rendered)

    def test_map_check_identity_is_stable_while_size_shrinks(self):
        seed = 0x20261020
        small = fuzz.generate_case(fuzz.Case("maps", seed, 1))
        large = fuzz.generate_case(fuzz.Case("maps", seed, 12))

        def checks(block):
            result = {}
            for line in block.body:
                match = re.fullmatch(
                    r'check(Integer|Text|Boolean)\((.*), (.+), '
                    r'("(?:[^"\\]|\\.)*")\)', line)
                if match:
                    result[json.loads(match.group(4))] = match.groups()[:3]
            return result

        small_checks = checks(small)
        large_checks = checks(large)
        self.assertTrue(small_checks)
        self.assertEqual(small_checks, {label: large_checks[label] for label in small_checks})


class FingerprintTests(unittest.TestCase):
    def test_changed_diagnostics_are_distinct_but_evidence_paths_are_stable(self):
        with tempfile.TemporaryDirectory(prefix="minyar-fuzz-harness-") as temporary:
            root = Path(temporary)

            def observed(name, diagnostic):
                directory = root / name
                directory.mkdir()
                stdout, stderr = directory / "stdout", directory / "stderr"
                stdout.write_bytes(b"")
                stderr.write_bytes(str(directory).encode("utf-8") + b"/program.min: " + diagnostic)
                result = {"status": 1, "timed_out": False, "output_limited": False,
                          "stdout": str(stdout), "stderr": str(stderr)}
                failure = fuzz.command_failure(result, "compile", "stage3")
                return dataclasses.replace(
                    failure, fingerprint=fuzz.result_fingerprint(result, directory))

            original = observed("original", b"borrowed payload was released\n")
            moved = observed("shrink", b"borrowed payload was released\n")
            unrelated = observed("different", b"cannot resolve a method\n")
            self.assertEqual(original.signature, unrelated.signature)
            self.assertEqual(original.reproduction, moved.reproduction)
            self.assertNotEqual(original.reproduction, unrelated.reproduction)
            self.assertNotEqual(original.detail, moved.detail)

    def test_first_oracle_difference_survives_prefix_removal_but_not_a_new_mismatch(self):
        expected = b"prefix\n42\n99\n"
        original_detail, original_fingerprint = fuzz.output_difference(expected, b"prefix\n41\n99\n")
        shifted_detail, shifted_fingerprint = fuzz.output_difference(b"42\n99\n", b"41\n99\n")
        other_detail, other_fingerprint = fuzz.output_difference(expected, b"prefix\n42\n98\n")
        original = fuzz.Failure("run-oracle", "stage3-eager-O2",
                                original_detail, original_fingerprint)
        shifted = fuzz.Failure("run-oracle", "stage3-eager-O2",
                               shifted_detail, shifted_fingerprint)
        unrelated = fuzz.Failure("run-oracle", "stage3-eager-O2",
                                 other_detail, other_fingerprint)
        self.assertEqual(original.signature, unrelated.signature)
        self.assertNotEqual(original.detail, shifted.detail)
        self.assertEqual(original.reproduction, shifted.reproduction)
        self.assertNotEqual(original.reproduction, unrelated.reproduction)

    def test_oracle_fingerprints_preserve_line_endings_and_missing_literal_lines(self):
        examples = ((b"42\n", b"42"), (b"42\n", b"42\r\n"),
                    (b"", b"<missing>\n"), (b"<missing>\n", b""))
        fingerprints = []
        for expected, actual in examples:
            with self.subTest(expected=expected, actual=actual):
                detail, fingerprint = fuzz.output_difference(expected, actual)
                self.assertTrue(detail)
                self.assertTrue(fingerprint)
                fingerprints.append(fingerprint)
        self.assertEqual(len(fingerprints), len(set(fingerprints)))
        with self.assertRaises(ValueError):
            fuzz.output_difference(b"same\n", b"same\n")

    def test_main_shrinker_rejects_equal_signatures_with_different_fingerprints(self):
        variants = (("compile-status", "stage3", "first diagnostic", "another diagnostic"),
                    ("run-oracle", "stage3-eager-O2", "first oracle difference", "another difference"))
        for kind, configuration, detail, changed_detail in variants:
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory(prefix="minyar-fuzz-harness-") as temporary:
                    root = Path(temporary)
                    compiler = root / "compiler"
                    compiler.write_bytes(b"compiler identity fixture")
                    original = fuzz.Failure(kind, configuration, detail, "original-fingerprint")
                    changed = fuzz.Failure(kind, configuration, changed_detail, "different-fingerprint")
                    self.assertEqual(original.signature, changed.signature)
                    argv = [str(MODULE_PATH), "--compiler-stage2", str(compiler),
                            "--compiler-stage3", str(compiler), "--programs", "1", "--size", "2",
                            "--shrink-attempts", "1", "--output-dir", str(root / "output")]

                    def check_reproduction(cases, reproduces, budget):
                        self.assertEqual(budget, 1)
                        self.assertFalse(reproduces(cases[:-1]))
                        return cases, 1

                    with (mock.patch.object(sys, "argv", argv),
                          mock.patch.object(fuzz, "prepare_runtimes", return_value={}),
                          mock.patch.object(fuzz, "check_program",
                                            side_effect=[[original], [changed]]) as checked,
                          mock.patch.object(fuzz, "reduce_cases",
                                            side_effect=check_reproduction) as reduced,
                          contextlib.redirect_stdout(io.StringIO())):
                        self.assertEqual(fuzz.main(), 1)
                    reduced.assert_called_once()
                    self.assertEqual(checked.call_count, 2)
                    self.assertEqual(checked.call_args.args[-1], configuration)


class ReductionTests(unittest.TestCase):
    def test_reducer_keeps_failure_predicate_and_does_not_mutate_input(self):
        cases = [fuzz.Case("arithmetic", seed, 16) for seed in range(6)]
        original = cases.copy()
        candidates = []

        def reproduces(candidate):
            self.assertTrue(candidate)
            candidates.append(candidate.copy())
            return any(case.seed == 2 and case.size >= 3 for case in candidate)

        reduced, attempts = fuzz.reduce_cases(cases, reproduces, 64)
        self.assertEqual(cases, original)
        self.assertEqual(attempts, len(candidates))
        self.assertLessEqual(attempts, 64)
        self.assertEqual(len(reduced), 1)
        self.assertEqual(reduced[0].seed, 2)
        self.assertGreaterEqual(reduced[0].size, 3)
        self.assertLess(reduced[0].size, 16)
        self.assertEqual(reduced[0].size, 3)

    def test_size_reduction_reaches_the_exact_failure_threshold(self):
        sizes = []

        def reproduces(candidate):
            self.assertEqual(len(candidate), 1)
            sizes.append(candidate[0].size)
            return candidate[0].size >= 3

        original = [fuzz.Case("aliases", 0xC0DE, 16)]
        reduced, attempts = fuzz.reduce_cases(original, reproduces, 32)
        self.assertEqual(reduced, [fuzz.Case("aliases", 0xC0DE, 3)])
        self.assertEqual(sizes, [1, 2, 3])
        self.assertEqual(attempts, 3)
        self.assertEqual(original[0].size, 16)

    def test_reducer_obeys_zero_and_small_budgets(self):
        cases = [fuzz.Case("control", seed, 12) for seed in range(8)]
        for budget in (0, 1, 2, 5):
            with self.subTest(budget=budget):
                predicate = mock.Mock(return_value=False)
                reduced, attempts = fuzz.reduce_cases(cases, predicate, budget)
                self.assertEqual(reduced, cases)
                self.assertEqual(attempts, predicate.call_count)
                self.assertLessEqual(attempts, budget)
                if budget == 0:
                    predicate.assert_not_called()

    def test_reducer_never_submits_an_empty_program(self):
        candidates = []

        def accepts(candidate):
            candidates.append(candidate.copy())
            self.assertTrue(candidate)
            return True

        reduced, attempts = fuzz.reduce_cases(
            [fuzz.Case("bytes", seed, 9) for seed in range(4)], accepts, 32)
        self.assertEqual(len(reduced), 1)
        self.assertEqual(reduced[0].size, 1)
        self.assertEqual(attempts, len(candidates))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="minyar-fuzz-harness-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.logs = self.root / "logs"
        self.logs.mkdir()
        self.runner = fuzz.Runner(self.logs, 10)

    def executable(self, name, source):
        path = self.root / name
        path.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -c " +
                        shlex.quote(source) + ' "$@"\n', encoding="utf-8")
        path.chmod(0o755)
        return path

    def compiler(self, name="compiler", output=b"; fake LLVM\n", status=0):
        source = "from pathlib import Path\nimport sys\n"
        if output is not None:
            source += f"Path(sys.argv[2]).write_bytes({output!r})\n"
        source += f"sys.exit({status})\n"
        return self.executable(name, source)

    def linker(self, mode="exact"):
        source = f'''from pathlib import Path
import shlex
import sys
output = Path(sys.argv[sys.argv.index("-o") + 1])
llvm = next(Path(arg) for arg in sys.argv[1:] if arg.endswith(".ll"))
stdout = (llvm.parent / "expected.stdout").read_bytes()
mode = {mode!r}
if mode == "mismatch":
    stdout += b"unexpected output\\n"
stderr = b"\\xffdiagnostic\\x00\\n" if mode == "stderr" else b""
status = 19 if mode == "status" else 0
program = ("import os, sys; os.write(1, " + repr(stdout) +
           "); os.write(2, " + repr(stderr) + "); sys.exit(" + repr(status) + ")")
output.write_text("#!/bin/sh\\nexec " + shlex.quote(sys.executable) + " -c " +
                  shlex.quote(program) + "\\n", encoding="utf-8")
output.chmod(0o755)
'''
        return self.executable("linker-" + mode, source)

    def runtimes(self, full=False):
        path = self.root / "runtime.o"
        path.write_bytes(b"fake runtime")
        if not full:
            return {("eager", "O0"): path}
        return {(memory, optimization): path for memory in ("eager", "arena")
                for optimization in ("O0", "O2")}

    def test_runner_and_command_reject_nonfinite_or_nonpositive_deadlines(self):
        for duration in (float("nan"), float("inf"), -float("inf"), 0, -1):
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(ValueError, "positive finite"):
                    fuzz.Runner(self.logs, duration)
                with mock.patch.object(fuzz.subprocess, "Popen") as opened:
                    with self.assertRaisesRegex(ValueError, "positive finite"):
                        self.runner.command(["must-not-execute"], "invalid-deadline", duration)
                    opened.assert_not_called()
        self.assertEqual(self.runner.commands, [])
        self.assertEqual(list(self.logs.iterdir()), [])

    def test_cli_rejects_nonfinite_deadlines_before_creating_a_campaign(self):
        for index, duration in enumerate(("nan", "inf", "-inf", "0", "-1")):
            with self.subTest(duration=duration):
                output = self.root / f"invalid-cli-{index}"
                argv = [str(MODULE_PATH), f"--timeout={duration}", "--output-dir", str(output)]
                diagnostics = io.StringIO()
                with (mock.patch.object(sys, "argv", argv),
                      mock.patch.object(fuzz, "Runner") as runner,
                      contextlib.redirect_stderr(diagnostics)):
                    with self.assertRaises(SystemExit) as rejected:
                        fuzz.main()
                self.assertEqual(rejected.exception.code, 2)
                self.assertIn("timeout must be positive", diagnostics.getvalue())
                runner.assert_not_called()
                self.assertFalse(output.exists())

    def test_runner_rejects_nonpositive_output_limits(self):
        for limit in (0, -1):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(ValueError, "output limit must be positive"):
                    fuzz.Runner(self.logs, 10, output_limit=limit)

    def test_exact_output_limit_is_allowed_without_truncation(self):
        payload = bytes(range(256))
        runner = fuzz.Runner(self.logs, 10, output_limit=len(payload))
        result = runner.command([sys.executable, "-c", f"import os; os.write(1, {payload!r})"],
                                "exact-output-limit")
        self.assertEqual(result["status"], 0)
        self.assertFalse(result["output_limited"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(Path(result["stdout"]).read_bytes(), payload)
        self.assertEqual(Path(result["stderr"]).read_bytes(), b"")
        self.assertIsNone(fuzz.command_failure(result, "run", "fixture"))

    def test_output_limit_is_combined_across_stdout_and_stderr(self):
        stdout, stderr = b"\x00\xffoutput-abcde", b"\xfeerror-uvwxyz"
        limit = 17
        runner = fuzz.Runner(self.logs, 10, output_limit=limit)
        source = f"import os; os.write(1, {stdout!r}); os.write(2, {stderr!r})"
        result = runner.command([sys.executable, "-c", source], "combined-output-limit")
        actual_stdout = Path(result["stdout"]).read_bytes()
        actual_stderr = Path(result["stderr"]).read_bytes()
        self.assertTrue(result["output_limited"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(len(actual_stdout) + len(actual_stderr), limit)
        self.assertTrue(stdout.startswith(actual_stdout))
        self.assertTrue(stderr.startswith(actual_stderr))
        self.assertEqual(fuzz.command_failure(result, "run", "fixture").signature,
                         ("run-output-limit", "fixture"))

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "fork") and hasattr(signal, "SIGALRM"),
                         "process groups and the fixture watchdog require POSIX")
    def test_output_limit_kills_descendant_and_retains_exact_prefix(self):
        payload = bytes(range(256)) * 4
        lock = self.root / "descendant.lock"
        source = f'''import fcntl, os, signal
ready_read, ready_write = os.pipe()
child = os.fork()
if child == 0:
    os.close(ready_read)
    with open({str(lock)!r}, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        signal.alarm(10)
        os.write(ready_write, b"ready")
        os.close(ready_write)
        signal.pause()
    os._exit(0)
os.close(ready_write)
os.read(ready_read, 1)
os.close(ready_read)
os.write(1, {payload!r})
os.waitpid(child, 0)
'''
        runner = fuzz.Runner(self.logs, 10, output_limit=257)
        result = runner.command([sys.executable, "-c", source], "descendant-output-limit")
        self.assertTrue(result["output_limited"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["status"], -signal.SIGKILL)
        self.assertLess(result["elapsed_seconds"], 8)
        self.assertEqual(Path(result["stdout"]).read_bytes(), payload[:257])
        self.assertEqual(Path(result["stderr"]).read_bytes(), b"")
        self.assertEqual(fuzz.command_failure(result, "run", "fixture").signature,
                         ("run-output-limit", "fixture"))
        # One blocking lock acquisition proves the descendant released its resource.
        # If only the leader was killed, its child holds the lock until the 10s alarm.
        observer = ("import fcntl; " + f"held = open({str(lock)!r}, 'r'); " +
                    "fcntl.flock(held, fcntl.LOCK_EX)")
        subprocess.run([sys.executable, "-c", observer], check=True, capture_output=True, timeout=3)

    @unittest.skipUnless(os.name == "posix" and hasattr(signal, "SIGALRM"),
                         "the fixture watchdog requires POSIX")
    def test_deadline_still_applies_after_child_closes_output_pipes(self):
        source = "import os, signal; os.close(1); os.close(2); signal.alarm(10); signal.pause()"
        result = self.runner.command([sys.executable, "-c", source], "closed-output-deadline", 0.25)
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["output_limited"])
        self.assertEqual(result["status"], -signal.SIGKILL)
        self.assertLess(result["elapsed_seconds"], 3)
        self.assertEqual(Path(result["stdout"]).read_bytes(), b"")
        self.assertEqual(Path(result["stderr"]).read_bytes(), b"")

    def test_command_retains_exact_bytes_status_and_metadata(self):
        stdout, stderr = b"\x00\xffout\r\n", b"\xfeerror\x00\n"
        arguments = [sys.executable, "-c",
                     f"import os, sys; os.write(1, {stdout!r}); "
                     f"os.write(2, {stderr!r}); sys.exit(7)"]
        result = self.runner.command(arguments, "binary-output")
        self.assertEqual(result["status"], 7)
        self.assertFalse(result["timed_out"])
        self.assertEqual(Path(result["stdout"]).read_bytes(), stdout)
        self.assertEqual(Path(result["stderr"]).read_bytes(), stderr)
        self.assertEqual(result["argv"], arguments)
        recorded = json.loads((self.logs / "commands.json").read_text(encoding="utf-8"))
        self.assertEqual(recorded, [result])
        failure = fuzz.command_failure(result, "run", "fixture")
        self.assertEqual(failure.signature, ("run-status", "fixture"))
        self.assertIn("\\xfe", failure.detail)

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "fork") and hasattr(signal, "SIGALRM"),
                         "process groups and the fixture watchdog require POSIX")
    def test_timeout_kills_descendant_holding_pipes_and_preserves_bytes(self):
        stdout, stderr = b"\x00\xffparent\n", b"\xfeerror\x00\n"
        source = f'''import os, signal
os.write(1, {stdout!r})
os.write(2, {stderr!r})
child = os.fork()
if child == 0:
    signal.alarm(10)
    os.write(1, b"child-ready\\n")
    signal.pause()
    os._exit(0)
os.waitpid(child, 0)
'''
        result = self.runner.command([sys.executable, "-c", source], "descendant-timeout", 2)
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["status"], -signal.SIGKILL)
        self.assertEqual(result["timeout_seconds"], 2)
        # Killing only the leader leaves the child's pipes open until its 10s alarm.
        self.assertLess(result["elapsed_seconds"], 8)
        self.assertEqual(Path(result["stdout"]).read_bytes(), stdout + b"child-ready\n")
        self.assertEqual(Path(result["stderr"]).read_bytes(), stderr)
        self.assertEqual(fuzz.command_failure(result, "run", "fixture").signature,
                         ("run-timeout", "fixture"))

    def test_unlaunchable_command_is_recorded_as_a_failure(self):
        result = self.runner.command([str(self.root / "missing")], "missing-command")
        self.assertEqual(result["status"], -1)
        self.assertFalse(result["timed_out"])
        self.assertTrue(Path(result["stderr"]).read_bytes())
        self.assertEqual(fuzz.command_failure(result, "compile", "stage2").signature,
                         ("compile-status", "stage2"))

    def test_successful_compiler_without_nonempty_llvm_is_rejected(self):
        for index, output in enumerate((None, b"")):
            with self.subTest(output=output):
                compiler = self.compiler("compiler-" + str(index), output=output)
                before = len(self.runner.commands)
                failures = fuzz.check_program(
                    self.runner, [fuzz.Case("arithmetic", 7, 1)],
                    self.root / ("program-" + str(index)), {"stage2": str(compiler)},
                    str(self.root / "must-not-link"), self.runtimes())
                self.assertEqual([failure.signature for failure in failures],
                                 [("compile-output", "stage2")])
                self.assertEqual(len(self.runner.commands), before + 1)

    def test_missing_compiler_output_cannot_reuse_stale_llvm(self):
        directory = self.root / "program"
        directory.mkdir()
        stale = directory / "stage2.ll"
        stale.write_bytes(b"; stale LLVM from a prior successful compiler\n")
        failures = fuzz.check_program(
            self.runner, [fuzz.Case("arithmetic", 7, 1)], directory,
            {"stage2": str(self.compiler(output=None))},
            str(self.root / "must-not-link"), self.runtimes())
        self.assertEqual([failure.signature for failure in failures],
                         [("compile-output", "stage2")])
        self.assertFalse(stale.exists())
        self.assertEqual(len(self.runner.commands), 1)

    def test_missing_or_empty_linker_output_is_rejected_before_execution(self):
        compiler = str(self.compiler())
        for index, output in enumerate((None, b"")):
            with self.subTest(output=output):
                source = "from pathlib import Path\nimport sys\n"
                if output is not None:
                    source += f"Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes({output!r})\n"
                linker = self.executable(f"missing-linker-{index}", source)
                before = len(self.runner.commands)
                failures = fuzz.check_program(
                    self.runner, [fuzz.Case("bytes", 12, 2)], self.root / f"program-{index}",
                    {"stage2": compiler}, str(linker), self.runtimes())
                self.assertEqual([failure.signature for failure in failures],
                                 [("link-output", "stage2-eager-O0")])
                self.assertEqual(len(self.runner.commands), before + 2)
                self.assertTrue(self.runner.commands[-1]["label"].endswith("-link"))

    def test_missing_linker_output_cannot_reuse_stale_executable(self):
        directory = self.root / "program"
        directory.mkdir()
        stale = directory / "stage2-eager-O0"
        stale.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        stale.chmod(0o755)
        linker = self.executable("no-output-linker", "import sys; sys.exit(0)")
        failures = fuzz.check_program(
            self.runner, [fuzz.Case("arithmetic", 7, 1)], directory,
            {"stage2": str(self.compiler())}, str(linker), self.runtimes())
        self.assertEqual([failure.signature for failure in failures],
                         [("link-output", "stage2-eager-O0")])
        self.assertFalse(stale.exists())
        self.assertEqual(len(self.runner.commands), 2)

    def test_compiler_nonzero_status_is_rejected_even_with_llvm(self):
        failures = fuzz.check_program(
            self.runner, [fuzz.Case("control", 11, 2)], self.root / "program",
            {"stage2": str(self.compiler(status=37))},
            str(self.root / "must-not-link"), self.runtimes())
        self.assertEqual([failure.signature for failure in failures],
                         [("compile-status", "stage2")])
        self.assertEqual(len(self.runner.commands), 1)

    def test_fake_toolchain_positive_control_visits_all_eight_configurations(self):
        compiler = str(self.compiler())
        cases = [fuzz.Case(family, index + 100, 3)
                 for index, family in enumerate(fuzz.FAMILIES)]
        failures = fuzz.check_program(
            self.runner, cases, self.root / "program",
            {"stage2": compiler, "stage3": compiler}, str(self.linker()), self.runtimes(full=True))
        self.assertEqual(failures, [])
        expected = {f"stage{stage}-{memory}-{optimization}-run" for stage in (2, 3)
                    for memory in ("eager", "arena") for optimization in ("O0", "O2")}
        self.assertEqual({command["label"] for command in self.runner.commands
                          if command["label"].endswith("-run")}, expected)
        self.assertEqual(len(self.runner.commands), 18)
        self.assertEqual(json.loads((self.root / "program/failures.json").read_text()), [])

    def test_fake_program_oracle_stderr_and_status_failures_are_rejected(self):
        compiler = str(self.compiler())
        for mode, expected_kind in (("mismatch", "run-oracle"), ("stderr", "run-stderr"),
                                    ("status", "run-status")):
            with self.subTest(mode=mode):
                failures = fuzz.check_program(
                    self.runner, [fuzz.Case("bytes", 12, 2)], self.root / ("program-" + mode),
                    {"stage2": compiler}, str(self.linker(mode)), self.runtimes())
                self.assertEqual([failure.signature for failure in failures],
                                 [(expected_kind, "stage2-eager-O0")])

    def test_failed_link_is_rejected_without_running_an_executable(self):
        linker = self.executable("failed-linker", "import sys; sys.exit(23)")
        failures = fuzz.check_program(
            self.runner, [fuzz.Case("choices", 17, 1)], self.root / "program",
            {"stage2": str(self.compiler())}, str(linker), self.runtimes())
        self.assertEqual([failure.signature for failure in failures],
                         [("link-status", "stage2-eager-O0")])
        self.assertEqual(len(self.runner.commands), 2)

    def test_reducer_configuration_filter_runs_only_the_requested_cell(self):
        compiler = str(self.compiler())
        failures = fuzz.check_program(
            self.runner, [fuzz.Case("aliases", 19, 2)], self.root / "program",
            {"stage2": compiler, "stage3": compiler}, str(self.linker()),
            self.runtimes(full=True), only="stage3-arena-O2")
        self.assertEqual(failures, [])
        self.assertEqual([command["label"] for command in self.runner.commands],
                         ["program-stage3-compile", "stage3-arena-O2-link", "stage3-arena-O2-run"])

    def test_stage_only_filter_invokes_only_the_selected_compiler(self):
        compiler = str(self.compiler())
        failures = fuzz.check_program(
            self.runner, [fuzz.Case("aliases", 19, 2)], self.root / "program",
            {"stage2": compiler, "stage3": compiler}, str(self.root / "must-not-link"),
            self.runtimes(full=True), only="stage3")
        self.assertEqual(failures, [])
        self.assertEqual([command["label"] for command in self.runner.commands],
                         ["program-stage3-compile"])
        self.assertFalse((self.root / "program/stage2.ll").exists())
        self.assertTrue((self.root / "program/stage3.ll").is_file())


if __name__ == "__main__":
    unittest.main()
