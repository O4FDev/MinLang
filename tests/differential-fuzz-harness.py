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
                         {"arithmetic", "control", "aliases", "maps", "generics", "bytes",
                          "callbacks", "choices"})
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

    def test_generic_generation_is_a_size_stable_prefix(self):
        seed = 0x20261020
        large = fuzz.generate_case(fuzz.Case("generics", seed, 18))
        for size in (1, 2, 5, 6, 7, 12):
            with self.subTest(size=size):
                small = fuzz.generate_case(fuzz.Case("generics", seed, size))
                self.assertEqual(small.body, large.body[:len(small.body)])
                self.assertEqual(small.expected, large.expected[:len(small.expected)])
        rendered, _ = fuzz.render([fuzz.Case("generics", seed, 1)])
        self.assertIn("record FuzzGenericBox<Item> { value: Item }", rendered)
        self.assertIn("function fuzzGenericIdentity<Item>(value: Item): Item", rendered)
        self.assertIn("function fuzzGenericPropagate(", rendered)


@dataclasses.dataclass(frozen=True)
class _GenericsReference:
    kind: str
    identity: int


@dataclasses.dataclass(frozen=True)
class _GenericsVariant:
    name: str
    payload: object = None


class _GenericsSyntax:
    """Parse only the expression/statement vocabulary emitted by this family."""

    token = re.compile(r'\s+|"(?:[^"\\]|\\.)*"|-?\d+|[A-Za-z_][A-Za-z_0-9]*|'
                       r'\+=|[{}\[\](),.:;=+<>]')

    def __init__(self, source):
        self.tokens = []
        position = 0
        while position < len(source):
            matched = self.token.match(source, position)
            if matched is None:
                raise ValueError(f"unknown syntax at {source[position:]!r}")
            if not matched.group().isspace():
                self.tokens.append(matched.group())
            position = matched.end()
        self.position = 0

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, expected=None):
        value = self.peek()
        if value is None or (expected is not None and value != expected):
            raise ValueError(f"expected {expected!r}, found {value!r}")
        self.position += 1
        return value

    def identifier(self):
        value = self.take()
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value) is None:
            raise ValueError(f"expected identifier, found {value!r}")
        return value

    def type_name(self):
        name = self.identifier()
        arities = {"Integer": 0, "Boolean": 0, "Text": 0, "FuzzCell": 0,
                   "List": 1, "Maybe": 1, "Result": 2, "FuzzGenericBox": 1}
        if name not in arities:
            raise ValueError(f"unknown type {name}")
        parameters = []
        if self.peek() == "<":
            self.take("<")
            parameters.append(self.type_name())
            while self.peek() == ",":
                self.take(",")
                parameters.append(self.type_name())
            self.take(">")
        if len(parameters) != arities[name]:
            raise ValueError(f"wrong type arity for {name}")
        return name, tuple(parameters)

    def sequence(self, ending):
        values = []
        if self.peek() != ending:
            values.append(self.expression())
            while self.peek() == ",":
                self.take(",")
                values.append(self.expression())
        self.take(ending)
        return values

    def expression(self):
        node = self.postfix()
        while self.peek() == "+":
            self.take("+")
            node = ("add", node, self.postfix())
        return node

    def postfix(self):
        node = self.atom()
        while self.peek() in ("(", "[", "."):
            operator = self.take()
            if operator == "(":
                node = ("call", node, self.sequence(")"))
            elif operator == "[":
                index = self.expression()
                self.take("]")
                node = ("index", node, index)
            else:
                node = ("field", node, self.identifier())
        return node

    def atom(self):
        value = self.take()
        if value == "(":
            node = self.expression()
            self.take(")")
            return node
        if value == "[":
            return ("list", self.sequence("]"))
        if value == "match":
            subject = self.expression()
            self.take("{")
            arms = {}
            while self.peek() != "}":
                tag = self.identifier()
                if tag not in ("Some", "None", "Ok", "Err") or tag in arms:
                    raise ValueError(f"unknown or duplicate match arm {tag}")
                binding = None
                if self.peek() == "(":
                    self.take("(")
                    binding = self.identifier()
                    self.take(")")
                if (tag == "None") != (binding is None):
                    raise ValueError(f"wrong match binding for {tag}")
                self.take("{")
                branch = self.expression()
                self.take("}")
                arms[tag] = (binding, branch)
            self.take("}")
            if set(arms) not in ({"Some", "None"}, {"Ok", "Err"}):
                raise ValueError("match must cover one supported choice")
            return ("match", subject, arms)
        if value in ("FuzzCell", "FuzzGenericBox") and self.peek() == "{":
            self.take("{")
            fields = {}
            while self.peek() != "}":
                name = self.identifier()
                if name in fields:
                    raise ValueError(f"duplicate record field {name}")
                self.take(":")
                fields[name] = self.expression()
                if self.peek() != ";":
                    break
                self.take(";")
            self.take("}")
            return ("record", value, fields)
        if value.startswith('"'):
            return ("literal", json.loads(value))
        if re.fullmatch(r"-?\d+", value):
            return ("literal", int(value))
        if value in ("true", "false"):
            return ("literal", value == "true")
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value):
            return ("name", value)
        raise ValueError(f"unknown expression token {value!r}")

    def statement(self):
        if self.peek() == "let":
            self.take("let")
            name = self.identifier()
            annotation = None
            if self.peek() == ":":
                self.take(":")
                annotation = self.type_name()
            self.take("=")
            node = ("let", name, annotation, self.expression())
        else:
            expression = self.expression()
            if self.peek() in ("=", "+="):
                operator = self.take()
                node = ("assign", expression, operator, self.expression())
            else:
                node = ("expression", expression)
        if self.peek() is not None:
            raise ValueError(f"unconsumed statement tokens: {self.tokens[self.position:]}")
        return node


class _GenericsReplay:
    """Independent semantics: identities live in a heap, never copied with roots."""

    def __init__(self, seed):
        self.seed = seed
        self.bindings = {}
        self.annotations = {}
        self.heap = {}
        self.observed = []
        self.specializations = set()
        self.propagation_paths = []

    def allocate(self, kind, value):
        reference = _GenericsReference(kind, len(self.heap))
        self.heap[reference.identity] = value
        return reference

    def object(self, reference, kind):
        if not isinstance(reference, _GenericsReference) or reference.kind != kind:
            raise ValueError(f"expected {kind} reference, found {reference!r}")
        return self.heap[reference.identity]

    def field(self, reference, name):
        if name == "length":
            return len(self.object(reference, "List"))
        if (not isinstance(reference, _GenericsReference) or
                reference.kind not in ("FuzzCell", "FuzzGenericBox")):
            raise ValueError("field access needs a supported record")
        record = self.object(reference, reference.kind)
        if name not in record:
            raise ValueError(f"unknown record field {name}")
        return record[name]

    def validate_annotation(self, value, annotation):
        name, parameters = annotation

        def mismatch():
            raise ValueError(f"annotation mismatch: expected {annotation!r}, found {value!r}")

        primitive = {"Integer": int, "Boolean": bool, "Text": str}
        if name in primitive:
            if type(value) is not primitive[name]:
                mismatch()
            return
        if name in ("List", "FuzzCell", "FuzzGenericBox"):
            if not isinstance(value, _GenericsReference) or value.kind != name:
                mismatch()
            contents = self.object(value, name)
            if name == "List":
                for item in contents:
                    self.validate_annotation(item, parameters[0])
            elif name == "FuzzCell":
                if set(contents) != {"number", "text", "values"}:
                    mismatch()
                for field, field_type in (
                        ("number", ("Integer", ())), ("text", ("Text", ())),
                        ("values", ("List", (("Integer", ()),)))):
                    self.validate_annotation(contents[field], field_type)
            else:
                if set(contents) != {"value"}:
                    mismatch()
                self.validate_annotation(contents["value"], parameters[0])
            return
        if not isinstance(value, _GenericsVariant):
            mismatch()
        if name == "Maybe":
            if value.name == "None" and value.payload is None:
                return
            if value.name != "Some":
                mismatch()
            self.validate_annotation(value.payload, parameters[0])
            return
        if name == "Result":
            if value.name not in ("Ok", "Err"):
                mismatch()
            self.validate_annotation(value.payload, parameters[0 if value.name == "Ok" else 1])
            return
        raise ValueError(f"unknown annotation type {name}")

    @staticmethod
    def kind(value):
        if type(value) is bool:
            return "Boolean"
        if type(value) is int:
            return "Integer"
        if type(value) is str:
            return "Text"
        if isinstance(value, _GenericsReference):
            return value.kind
        if isinstance(value, _GenericsVariant):
            return value.name
        raise ValueError(f"unknown modeled value {value!r}")

    def propagate(self, input_value, state):
        record = self.object(state, "FuzzCell")
        record["number"] += 1
        self.object(record["values"], "List").append(1)
        if not isinstance(input_value, _GenericsVariant):
            raise ValueError("propagation needs a Maybe")
        if input_value.name == "None":
            self.propagation_paths.append("None")
            answer = self.allocate("List", ["none!"])
        elif input_value.name == "Some":
            outcome = input_value.payload
            if not isinstance(outcome, _GenericsVariant):
                raise ValueError("Some needs a Result payload")
            if outcome.name == "Err":
                self.propagation_paths.append("Err")
                return outcome
            if outcome.name != "Ok":
                raise ValueError("Some needs Ok or Err")
            self.propagation_paths.append("Ok")
            self.object(outcome.payload, "List")
            answer = outcome.payload
        else:
            raise ValueError("propagation needs Some or None")
        record["number"] += 10
        return _GenericsVariant("Ok", answer)

    def evaluate(self, node, scope=None):
        scope = self.bindings if scope is None else scope
        operation = node[0]
        if operation == "literal":
            return node[1]
        if operation == "name":
            if node[1] == "None":
                return _GenericsVariant("None")
            if node[1] not in scope:
                raise ValueError(f"unknown binding {node[1]}")
            return scope[node[1]]
        if operation == "list":
            return self.allocate("List", [self.evaluate(item, scope) for item in node[1]])
        if operation == "record":
            name = node[1]
            fields = {field: self.evaluate(value, scope) for field, value in node[2].items()}
            if name == "FuzzGenericBox" and set(fields) != {"value"}:
                raise ValueError("unknown FuzzGenericBox constructor shape")
            reference = self.allocate(name, fields)
            if name == "FuzzCell":
                self.validate_annotation(reference, ("FuzzCell", ()))
            return reference
        if operation == "add":
            left, right = self.evaluate(node[1], scope), self.evaluate(node[2], scope)
            if type(left) is not str or type(right) is not str:
                raise ValueError("only emitted Text concatenation is supported")
            return left + right
        if operation == "index":
            sequence = self.object(self.evaluate(node[1], scope), "List")
            index = self.evaluate(node[2], scope)
            if type(index) is not int or not 0 <= index < len(sequence):
                raise ValueError(f"invalid modeled List index {index!r}")
            return sequence[index]
        if operation == "field":
            return self.field(self.evaluate(node[1], scope), node[2])
        if operation == "match":
            choice = self.evaluate(node[1], scope)
            if not isinstance(choice, _GenericsVariant) or choice.name not in node[2]:
                raise ValueError("match subject does not fit its arms")
            name, branch = node[2][choice.name]
            local = dict(scope)
            if name is not None:
                local[name] = choice.payload
            return self.evaluate(branch, local)
        if operation == "call":
            if node[1][0] != "name":
                raise ValueError("unknown indirect or method call")
            name = node[1][1]
            arguments = [self.evaluate(item, scope) for item in node[2]]
            if name in ("Some", "Ok", "Err") and len(arguments) == 1:
                return _GenericsVariant(name, arguments[0])
            if name in ("fuzzGenericIdentity", "fuzzGenericBoxed", "fuzzGenericChecked"):
                if len(arguments) != 1:
                    raise ValueError(f"wrong helper arity for {name}")
                self.specializations.add((name, self.kind(arguments[0])))
                return (_GenericsVariant("Ok", arguments[0]) if name == "fuzzGenericChecked"
                        else arguments[0])
            if name == "fuzzGenericPropagate" and len(arguments) == 2:
                return self.propagate(*arguments)
            raise ValueError(f"unknown function or arity: {name}")
        raise ValueError(f"unknown expression operation {operation}")

    def location(self, node):
        if node[0] == "name" and node[1] in self.bindings:
            return self.bindings, node[1]
        if node[0] == "index":
            sequence = self.object(self.evaluate(node[1]), "List")
            index = self.evaluate(node[2])
            if type(index) is not int or not 0 <= index < len(sequence):
                raise ValueError("invalid assignment index")
            return sequence, index
        if node[0] == "field":
            reference = self.evaluate(node[1])
            if (not isinstance(reference, _GenericsReference) or
                    reference.kind not in ("FuzzCell", "FuzzGenericBox")):
                raise ValueError("field assignment needs a supported record")
            record = self.object(reference, reference.kind)
            if node[2] not in record:
                raise ValueError(f"unknown assignment field {node[2]}")
            return record, node[2]
        raise ValueError("unknown assignment target")

    def execute(self, lines):
        for index, line in enumerate(lines):
            try:
                statement = _GenericsSyntax(line).statement()
                if statement[0] == "let":
                    if statement[1] in self.bindings:
                        raise ValueError(f"duplicate binding {statement[1]}")
                    value = self.evaluate(statement[3])
                    if statement[2] is not None:
                        self.validate_annotation(value, statement[2])
                        self.annotations[statement[1]] = statement[2]
                    self.bindings[statement[1]] = value
                    continue
                if statement[0] == "assign":
                    container, position = self.location(statement[1])
                    value = self.evaluate(statement[3])
                    if statement[2] == "+=":
                        if type(container[position]) is not int or type(value) is not int:
                            raise ValueError("+= needs Integer values")
                        value += container[position]
                    container[position] = value
                    for name, annotation in self.annotations.items():
                        self.validate_annotation(self.bindings[name], annotation)
                    continue
                node = statement[1]
                if (node[0] != "call" or node[1][0] != "name" or
                        node[1][1] not in ("checkInteger", "checkText", "checkBoolean") or
                        len(node[2]) != 3):
                    raise ValueError("unknown statement: expected declaration, assignment or check")
                term, expected_node, label_node = node[2]
                if expected_node[0] != "literal" or label_node[0] != "literal":
                    raise ValueError("check oracle and label must be literals")
                actual, expected, label = self.evaluate(term), expected_node[1], label_node[1]
                kind = node[1][1][5:]
                if self.kind(actual) != kind or self.kind(expected) != kind:
                    raise AssertionError(f"check kind mismatch: {line}")
                if actual != expected:
                    raise AssertionError(f"oracle mismatch: {actual!r} != {expected!r}: {line}")
                wanted = f"generics:{self.seed}:{len(self.observed)}"
                if label != wanted:
                    raise AssertionError(f"check label mismatch: {label!r} != {wanted!r}")
                displayed = ("true" if actual else "false") if type(actual) is bool else str(actual)
                self.observed.append(f"{label}={displayed}")
            except (ValueError, AssertionError) as error:
                raise type(error)(f"generics body line {index}: {error}") from error
        return self.observed.copy()


class GenericsReplayTests(unittest.TestCase):
    def test_replay_retains_and_validates_recursive_annotation_trees(self):
        body = [
            "let integer: Integer = 7",
            "let flag: Boolean = false",
            'let text: Text = "ok"',
            'let cell: FuzzCell = FuzzCell { number: 1; text: "cell"; values: [2] }',
            'let words: List<Text> = ["kept"]',
            "let rows: List<List<Text>> = [words, []]",
            "let optional: Maybe<List<Text>> = Some(words)",
            "let absent: Maybe<List<Text>> = None",
            "let good: Result<Maybe<List<Text>>, FuzzCell> = Ok(optional)",
            "let bad: Result<Integer, List<Boolean>> = Err([true, false])",
            "let boxed: FuzzGenericBox<Maybe<List<Text>>> = "
            "FuzzGenericBox { value: Some(words) }",
            "let scalarBox: FuzzGenericBox<Integer> = FuzzGenericBox { value: integer }",
            "let cellsBox: FuzzGenericBox<List<FuzzCell>> = FuzzGenericBox { value: [cell] }",
            "let resultBox: Result<FuzzGenericBox<Maybe<List<Text>>>, Text> = Ok(boxed)",
            "optional = None",
            "checkText(match boxed.value { Some(value) { value[0] } None { "
            '"invalid" } }, "kept", "generics:0:0")',
            'checkInteger(scalarBox.value, 7, "generics:0:1")',
            'checkInteger(cellsBox.value[0].number, 1, "generics:0:2")',
            'checkBoolean(flag, false, "generics:0:3")',
        ]
        replay = _GenericsReplay(0)
        self.assertEqual(replay.execute(body), ["generics:0:0=kept", "generics:0:1=7",
                                               "generics:0:2=1", "generics:0:3=false"])
        list_text = ("List", (("Text", ()),))
        maybe_list = ("Maybe", (list_text,))
        self.assertEqual(replay.annotations["boxed"], ("FuzzGenericBox", (maybe_list,)))
        self.assertEqual(replay.annotations["good"], ("Result", (maybe_list, ("FuzzCell", ()))))
        self.assertEqual(replay.annotations["rows"], ("List", (list_text,)))

    def test_replay_rejects_corrupt_known_type_annotations_and_payloads(self):
        fixtures = [
            ["let value: Text = 1"],
            ["let value: Integer = true"],
            ["let value: Boolean = 1"],
            ["let value: Text = false"],
            ['let value: FuzzCell = ["x"]'],
            ["let value: List<Text> = [1]"],
            ["let value: List<Integer> = [true]"],
            ['let value: List<List<Text>> = [["x"], [2]]'],
            ["let value: Maybe<Text> = Some(1)"],
            ['let value: Maybe<Text> = Ok("x")'],
            ['let value: Result<Integer, Text> = Ok("wrong")'],
            ["let value: Result<Integer, Text> = Err(1)"],
            ["let value: Result<Integer, Text> = None"],
            ["let value: Result<Maybe<List<Text>>, Text> = Ok(Some([1]))"],
            ["let value: Result<Text, List<Boolean>> = Err([1])"],
            ['let value: FuzzGenericBox<Integer> = FuzzGenericBox { value: "x" }'],
            ["let value: FuzzGenericBox<List<FuzzCell>> = FuzzGenericBox { value: [1] }"],
            ['let value: List<Text> = FuzzGenericBox { value: ["x"] }'],
            'let value: FuzzGenericBox<Text> = FuzzCell { number: 1; text: "x"; values: [] }',
            'let value: FuzzCell = FuzzCell { number: 1; text: "x"; values: ["bad"] }',
            ['let value: Text = "x"', "value = 1"],
            ['let words: List<Text> = ["x"]', "words[0] = 1"],
            ['let cell: FuzzCell = FuzzCell { number: 1; text: "x"; values: [] }',
             "cell.text = 1"],
            ['let words: List<Text> = ["x"]', "let alias = words", "alias[0] = 1"],
            ['let cell: FuzzCell = FuzzCell { number: 1; text: "x"; values: [] }',
             "let alias = cell", "alias.text = 1"],
            ['let box: FuzzGenericBox<Text> = FuzzGenericBox { value: "x" }',
             "let alias = box", "alias.value = 1"],
        ]
        for fixture in fixtures:
            body = [fixture] if isinstance(fixture, str) else fixture
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    _GenericsReplay(0).execute(body)

    def test_generated_alias_operation_writes_distinct_roots_with_nonzero_delta(self):
        for seed in (0, 0xC0DE, 0x20261020):
            for size in (5, 6, 12, 18):
                with self.subTest(seed=seed, size=size):
                    block = fuzz.generate_case(fuzz.Case("generics", seed, size))
                    operations = 0
                    for index, line in enumerate(block.body):
                        assignment = re.fullmatch(
                            r"lists\[(\d+)\] = fuzzGenericBoxed\(lists\[(\d+)\]\)", line)
                        if assignment is None:
                            continue
                        destination, source = map(int, assignment.groups())
                        self.assertNotEqual(destination, source)
                        self.assertEqual(block.body[index + 1],
                                         f"cells[{destination}] = fuzzGenericIdentity(cells[{source}])")
                        mutation = re.fullmatch(
                            rf"cells\[{destination}\]\.number \+= (-?\d+)", block.body[index + 3])
                        self.assertIsNotNone(mutation)
                        self.assertNotEqual(int(mutation.group(1)), 0)
                        operations += 1
                    self.assertEqual(operations, len(range(4, size, 6)))

    def test_generated_generics_oracles_match_independent_source_replay(self):
        for seed in (0, 0xC0DE, 0x20261020):
            for size in (1, 2, 5, 6, 7, 12, 18):
                with self.subTest(seed=seed, size=size):
                    case = fuzz.Case("generics", seed, size)
                    block = fuzz.generate_case(case)
                    replay = _GenericsReplay(seed)
                    observed = replay.execute(block.body)
                    self.assertEqual(observed, block.expected)
                    _, transcript = fuzz.render([case])
                    self.assertEqual(("\n".join(observed) + "\n").encode("utf-8"), transcript)
                    self.assertEqual(set(replay.propagation_paths), {"Ok", "Err", "None"})
                    self.assertTrue({("fuzzGenericBoxed", kind) for kind in
                                     ("Integer", "Text", "List", "FuzzCell")}
                                    <= replay.specializations)
                    self.assertGreaterEqual(len(observed), 20)
                    indexed_trace_checks = []
                    for line in block.body:
                        checkpoint = re.fullmatch(
                            r'checkInteger\(trace\.values\[(\d+)\], 1, '
                            r'"generics:' + str(seed) + r':\d+"\)', line)
                        if checkpoint:
                            indexed_trace_checks.append(int(checkpoint.group(1)))
                    self.assertEqual(indexed_trace_checks,
                                     list(range(len(replay.propagation_paths))))
                    if size == 18:
                        for name in ("scalar0", "savedList1", "savedText2", "savedCell3",
                                     "propagated5", "savedList7", "savedCell9", "propagated17"):
                            self.assertIn(name, replay.bindings)

    def test_replay_checks_each_trace_append_and_rejects_a_wrong_indexed_value(self):
        lines = [
            'let trace = FuzzCell { number: 0; text: "trace"; values: [] }',
            "let absent: Maybe<Result<List<Text>, Text>> = None",
        ]
        for index in range(4):
            lines.append(f"let result{index} = fuzzGenericPropagate(absent, trace)")
            lines.append(f'checkInteger(trace.values[{index}], 1, "generics:0:{index}")')
        replay = _GenericsReplay(0)
        self.assertEqual(replay.execute(lines), [f"generics:0:{index}=1" for index in range(4)])
        self.assertEqual(replay.propagation_paths, ["None"] * 4)
        corrupted = lines.copy()
        index = next(index for index, line in enumerate(corrupted)
                     if line.startswith("checkInteger(trace.values[2]"))
        corrupted[index] = corrupted[index].replace("], 1,", "], 2,")
        with self.assertRaisesRegex(AssertionError, "oracle mismatch"):
            _GenericsReplay(0).execute(corrupted)

    def test_hand_replay_preserves_aliases_escaped_payloads_and_scalar_snapshots(self):
        lines = [
            'let words = ["old" + "!"]',
            "let same = fuzzGenericBoxed(words)",
            "let outcome: Result<List<Text>, Text> = fuzzGenericChecked(words)",
            'let saved = match outcome { Ok(value) { value } Err(error) { ["invalid"] } }',
            'outcome = Err("discarded")',
            'words = ["replacement"]',
            'saved[0] = "kept"',
            'checkText(same[0], "kept", "generics:0:0")',
            'checkText(words[0], "replacement", "generics:0:1")',
            'let cell = FuzzCell { number: 7; text: "record!"; values: [] }',
            "let optional: Maybe<FuzzCell> = Some(fuzzGenericBoxed(cell))",
            "let record = match optional { Some(value) { value } "
            'None { FuzzCell { number: 0; text: "invalid"; values: [] } } }',
            "optional = None",
            'cell = FuzzCell { number: 11; text: "replacement"; values: [] }',
            "record.number += 2",
            'checkInteger(record.number, 9, "generics:0:2")',
            'checkInteger(cell.number, 11, "generics:0:3")',
            "let text = fuzzGenericBoxed(record.text)",
            'record.text = "new text"',
            'checkText(text, "record!", "generics:0:4")',
            "let maybeText: Maybe<Text> = Some(text)",
            'let savedText = match maybeText { Some(value) { value } None { "invalid" } }',
            "maybeText = None",
            'checkText(savedText, "record!", "generics:0:5")',
            "let primitive = fuzzGenericBoxed(7)",
            "let primitiveAlias = primitive",
            "primitive = 11",
            'checkInteger(primitiveAlias, 7, "generics:0:6")',
            "same = fuzzGenericBoxed(same)",
            'same[0] = "self"',
            'checkText(saved[0], "self", "generics:0:7")',
        ]
        replay = _GenericsReplay(0)
        self.assertEqual(replay.execute(lines), [
            "generics:0:0=kept", "generics:0:1=replacement", "generics:0:2=9",
            "generics:0:3=11", "generics:0:4=record!", "generics:0:5=record!",
            "generics:0:6=7", "generics:0:7=self"])
        self.assertEqual(replay.bindings["same"], replay.bindings["saved"])
        self.assertNotEqual(replay.bindings["words"], replay.bindings["saved"])
        self.assertNotEqual(replay.bindings["cell"], replay.bindings["record"])
        self.assertEqual(replay.bindings["optional"], _GenericsVariant("None"))

    def test_hand_replay_models_try_paths_and_fresh_none_payloads(self):
        lines = [
            'let trace = FuzzCell { number: 0; text: "trace"; values: [] }',
            'let payload = ["shared"]',
            "let input: Maybe<Result<List<Text>, Text>> = Some(Ok(payload))",
            "let good = fuzzGenericPropagate(input, trace)",
            "input = None",
            'payload[0] = "changed"',
            "checkText(match good { Ok(value) { value[0] } Err(error) { error } }, "
            '"changed", "generics:0:0")',
            'checkInteger(trace.number, 11, "generics:0:1")',
            'input = Some(Err("stop" + "!"))',
            "let bad = fuzzGenericPropagate(input, trace)",
            "input = None",
            "checkBoolean(match bad { Ok(value) { true } Err(error) { false } }, "
            'false, "generics:0:2")',
            "checkText(match bad { Ok(value) { value[0] } Err(error) { error } }, "
            '"stop!", "generics:0:3")',
            'checkInteger(trace.number, 12, "generics:0:4")',
            "let empty = fuzzGenericPropagate(input, trace)",
            "let first = match empty { Ok(value) { value } "
            'Err(error) { ["invalid"] } }',
            'checkInteger(trace.number, 23, "generics:0:5")',
            'checkInteger(trace.values.length, 3, "generics:0:6")',
            "let another = fuzzGenericPropagate(None, trace)",
            'first[0] = "altered"',
            "checkText(match another { Ok(value) { value[0] } Err(error) { error } }, "
            '"none!", "generics:0:7")',
            'checkInteger(trace.number, 34, "generics:0:8")',
            'checkInteger(trace.values.length, 4, "generics:0:9")',
            'checkInteger(trace.values[0], 1, "generics:0:10")',
        ]
        replay = _GenericsReplay(0)
        self.assertEqual(replay.execute(lines), [
            "generics:0:0=changed", "generics:0:1=11", "generics:0:2=false",
            "generics:0:3=stop!", "generics:0:4=12", "generics:0:5=23",
            "generics:0:6=3", "generics:0:7=none!", "generics:0:8=34",
            "generics:0:9=4", "generics:0:10=1"])
        self.assertEqual(replay.propagation_paths, ["Ok", "Err", "None", "None"])

    def test_replay_rejects_unknown_lines_functions_and_fields(self):
        fixtures = [
            ["print(1)"],
            ["let value = unknown(1)"],
            ["let value = 1 trailing"],
            ["while true {}"],
            ['let cell = FuzzCell { number: 1; text: "x"; values: [] }',
             "cell.unknown = 2"],
            ["let value = 1", "let value = 2"],
            ["let value: Unknown = 1"],
        ]
        for body in fixtures:
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    _GenericsReplay(0).execute(body)

    def test_replay_rejects_corrupted_expected_values_and_labels(self):
        block = fuzz.generate_case(fuzz.Case("generics", 0, 6))
        index = next(index for index, line in enumerate(block.body)
                     if line.startswith("checkInteger("))
        original = block.body[index]
        parsed = re.fullmatch(r'(checkInteger\(.*), (-?\d+), ("[^"]+")\)', original)
        self.assertIsNotNone(parsed)
        corrupted = block.body.copy()
        corrupted[index] = f"{parsed.group(1)}, {int(parsed.group(2)) + 1}, {parsed.group(3)})"
        with self.assertRaisesRegex(AssertionError, "oracle mismatch"):
            _GenericsReplay(0).execute(corrupted)
        corrupted = block.body.copy()
        corrupted[index] = original.replace('"generics:0:0"', '"generics:0:99"')
        self.assertNotEqual(corrupted[index], original)
        with self.assertRaisesRegex(AssertionError, "label mismatch"):
            _GenericsReplay(0).execute(corrupted)


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
