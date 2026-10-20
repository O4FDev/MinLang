#!/usr/bin/env python3
"""Check compiler error codes and explanations through both public entry points."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


if not __debug__:
    raise SystemExit("explanation checks require Python assertions; remove -O")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("compiler", type=Path)
parser.add_argument("launcher", type=Path)
options = parser.parse_args()
compiler = options.compiler.resolve()
launcher = options.launcher.resolve()
repository = Path(__file__).resolve().parents[1]

# These identities are an independent compatibility oracle. Rewording a title,
# message, help note or example must not renumber an existing error family.
CODES = (
    "E0001",
    "E0101", "E0102", "E0103", "E0104",
    "E0201", "E0202", "E0203", "E0204", "E0205", "E0206",
    "E0301", "E0302", "E0303", "E0304", "E0305", "E0306", "E0307",
    "E0401", "E0402", "E0403", "E0404", "E0405", "E0406", "E0407",
    "E0408", "E0409", "E0410", "E0411",
    "E0501", "E0502",
    "E0601", "E0602", "E0603",
    "E0701",
)
FIELDS = {
    "version", "severity", "code", "message", "file", "line", "column",
    "endLine", "endColumn", "sourceLine", "label", "help",
}
USAGE = "usage: minyar explain CODE\n"


with tempfile.TemporaryDirectory(prefix="minyar explain · outside project '") as temporary:
    root = Path(temporary).resolve()
    assert not (root / "Minyar.toml").exists()
    prefixes = ([str(compiler), "--explain"], [str(launcher), "explain"])
    environment = dict(os.environ)
    # The launcher may query Make during source-checkout bootstrap. This child
    # does not own the enclosing make's jobserver descriptors or recursion state.
    for key in ("MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKELEVEL"):
        environment.pop(key, None)

    def run(arguments, timeout=30):
        result = subprocess.run(arguments, cwd=root, text=True, encoding="utf-8",
                                env=environment, capture_output=True, timeout=timeout)
        return result

    def successful(prefix, *arguments):
        result = run([*prefix, *arguments], timeout=120)
        assert result.returncode == 0, (prefix, arguments, result)
        assert result.stderr == "", (prefix, arguments, result.stderr)
        assert result.stdout.endswith("\n"), (prefix, arguments, result.stdout)
        return result.stdout

    compiled = 0

    def compile_program(name, source):
        global compiled
        path = root / f"{name}.min"
        output = root / f"{name}.ll"
        path.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
        result = run([str(compiler), str(path), str(output), "--library", str(repository / "library")])
        assert result.returncode == 0 and result.stdout == result.stderr == "", (
            "valid explanation or boundary program", name, source, result)
        assert output.is_file() and output.stat().st_size > 0, ("successful program emitted LLVM", name)
        compiled += 1

    raw_listing = successful(prefixes[0], "--list")
    assert successful(prefixes[1], "--list") == raw_listing
    assert successful(prefixes[0], "--list") == raw_listing
    titles = {}
    for line in raw_listing.splitlines():
        match = re.fullmatch(r"(E\d{4})\s+(.+)", line)
        assert match, ("one code and plain title per line", line)
        code, title = match.groups()
        title = title.strip(" \t:—-")
        assert code not in titles and title, ("unique named error family", line)
        titles[code] = title
    assert tuple(titles) == CODES, ("stable complete catalogue order", tuple(titles))

    for code, title in titles.items():
        explanation = successful(prefixes[0], code)
        assert code in explanation and title in explanation, (code, title, explanation)
        assert len(explanation.splitlines()) >= 4, ("explanation and example", code, explanation)
        assert re.search(r"\b(?:let|constant|function|record|choice|if|for|while|use|print|return|match)\b",
                         explanation), ("concrete Minyar example", code, explanation)
        assert successful(prefixes[1], code) == explanation, ("launcher/compiler explanation parity", code)
        examples = re.findall(r"^```minyar[ \t]*\n(.*?)^```[ \t]*(?:\n|$)", explanation,
                              flags=re.MULTILINE | re.DOTALL)
        assert examples, ("fenced Minyar example", code, explanation)
        for index, example in enumerate(examples, 1):
            # Native declarations such as E0205 need their host symbols only
            # when linked. Every published sample must still compile to LLVM.
            compile_program(f"example-{code}-{index}", example)

    assert successful(prefixes[0], "E0301") == successful(prefixes[0], "E0301")
    assert successful(prefixes[1], "E0401") == successful(prefixes[0], "E0401")
    for prefix in prefixes:
        for option in ("--help", "-h"):
            assert successful(prefix, option).startswith(USAGE), (prefix, option)
        for arguments in ([], ["E0301", "extra"]):
            result = run([*prefix, *arguments], timeout=120)
            assert result.returncode == 2 and result.stdout == "" and result.stderr == USAGE, (
                "exact operand validation outside a project", prefix, arguments, result)
        for code in ("E9999", "not-a-code", "E9999; $(touch SHOULD_NOT_EXIST)"):
            result = run([*prefix, code], timeout=120)
            expected = (f"unknown error code: {code}\n"
                        "Use minyar explain --list to list the available codes.\n")
            assert result.returncode == 2 and result.stdout == "" and result.stderr == expected, (
                "exact unknown-code diagnostic", prefix, code, result)
    assert not (root / "SHOULD_NOT_EXIST").exists(), "explanation operands are literal arguments"

    checked = 0

    def diagnostic(source, code, expected_help=None, has_excerpt=True,
                   expected_message=None, expected_span=None, expected_source_lines=None,
                   diagnostic_file=None, exact_output=False):
        global checked
        origin = source if diagnostic_file is None else diagnostic_file
        checked += 1
        output = root / f"rejected-{checked}.ll"
        command = [str(compiler), str(source), str(output), "--library", str(repository / "library")]
        human = run(command)
        machine = run([*command, "--error-format", "json"])
        assert human.returncode == machine.returncode == 1, (source, code, human, machine)
        assert human.stdout == machine.stdout == "", (source, human.stdout, machine.stdout)
        assert not output.exists(), ("rejected input emitted LLVM", source)
        assert human.stderr.startswith("error: ") and human.stderr.endswith("\n"), (source, human.stderr)
        assert len(machine.stderr.splitlines()) == 1, (source, machine.stderr)
        value = json.loads(machine.stderr)
        assert set(value) == FIELDS and value["version"] == 1, (source, value)
        assert value["severity"] == "error" and value["code"] == code, (source, code, value)
        assert value["message"] == human.stderr.splitlines()[0][7:], (source, value, human.stderr)
        if expected_message is not None:
            assert value["message"] == expected_message, ("exact primary message", source, value)
        assert value["file"] == str(origin), (source, origin, value)
        assert value["line"] >= 1 and value["column"] >= 1, (source, value)
        assert value["endLine"] == value["line"] and value["endColumn"] >= value["column"], (source, value)
        assert f"  --> {origin}:{value['line']}:{value['column']}\n" in human.stderr, (source, origin, value, human.stderr)
        hints = re.findall(r"(?m)^ += help: (.+)$", human.stderr)
        assert hints and value["help"] == hints, ("same nonempty actionable help", source, value, human.stderr)
        if expected_help is not None:
            assert hints == [expected_help], ("preserve a specific spelling suggestion", source, hints)
        links = re.findall(r"(?m)^ += explain: minyar explain (E\d{4})$", human.stderr)
        assert links == [code], ("exact discoverable explanation code", source, code, human.stderr)
        assert human.stderr.rstrip().endswith(f"= explain: minyar explain {code}"), (source, human.stderr)
        if has_excerpt:
            assert "^" in human.stderr and " | " in human.stderr, ("source excerpt and caret", source, human.stderr)
        if expected_source_lines is not None:
            assert value["line"] <= len(expected_source_lines), ("source line exists", source, value)
            expected_source = expected_source_lines[value["line"] - 1]
            assert value["sourceLine"] == expected_source, ("original JSON source excerpt", source, value)
            assert f" {value['line']} | {expected_source}\n" in human.stderr, (
                "same original source excerpt in text and JSON", source, value, human.stderr)
        if expected_span is not None:
            observed = (value["line"], value["column"], value["endLine"], value["endColumn"])
            assert observed == expected_span, ("independent complete token range", source, expected_span, value)
            rows = human.stderr.splitlines()
            underline = re.search(r"\^+", rows[4])
            assert underline and underline.start() == rows[3].find("| ") + 2 + value["column"] - 1, (
                "caret starts at the offending token", source, human.stderr)
            assert len(underline.group()) == value["endColumn"] - value["column"], (
                "entire offending token is underlined", source, human.stderr)
        if exact_output:
            assert expected_message is not None and expected_help is not None
            assert expected_span is not None and expected_source_lines is not None
            line, column, end_line, end_column = expected_span
            source_line = expected_source_lines[line - 1]
            expected_json = {
                "version": 1, "severity": "error", "code": code, "message": expected_message,
                "file": str(origin), "line": line, "column": column,
                "endLine": end_line, "endColumn": end_column, "sourceLine": source_line,
                "label": "", "help": [expected_help],
            }
            assert value == expected_json, ("complete independent JSON diagnostic", source, value, expected_json)
            margin = " " * (len(str(line)) + 2)
            expected_text = (
                f"error: {expected_message}\n  --> {origin}:{line}:{column}\n"
                f"{margin}|\n {line} | {source_line}\n"
                f"{margin}| " + " " * (column - 1) + "^" * (end_column - column) + "\n"
                f"{margin}= help: {expected_help}\n"
                f"{margin}= explain: minyar explain {code}\n"
            )
            assert human.stderr == expected_text, ("complete independent text diagnostic", source, human.stderr, expected_text)
        return value

    # Existing rejections prove code identities across unrelated front-end
    # paths. Complete presentation remains covered by check-diagnostics.
    for relative, code, hint in (
        ("tests/diagnostics/cases/suggest-value.min", "E0301", "did you mean `lantern`?"),
        ("tests/diagnostics/cases/suggest-function.min", "E0302", "did you mean `portrait`?"),
        ("tests/diagnostics/cases/suggest-type.min", "E0303", "did you mean `Integer`?"),
        ("tests/diagnostics/cases/suggest-field-read.min", "E0304", "did you mean `light`?"),
        ("tests/diagnostics/cases/suggest-method.min", "E0305", "did you mean `ignite`?"),
        ("tests/errors/type-mismatch.min", "E0401", None),
        ("tests/diagnostics/cases/reject-list-store-type.min", "E0401", None),
        ("tests/errors/condition-must-be-boolean.min", "E0402", None),
        ("tests/errors/malformed-expression.min", "E0201", None),
        ("tests/errors/mixed-entry-points.min", "E0206", None),
        ("tests/errors/duplicate-function.min", "E0501", None),
        ("tests/errors/record-missing-field.min", "E0701", None),
        ("tests/diagnostics/cases/missing-choice-cases.min", "E0601", None),
        ("tests/diagnostics/cases/reject-empty-choice.min", "E0602", None),
        ("tests/diagnostics/cases/reject-native-mixed-body.min", "E0205", None),
        ("tests/diagnostics/cases/reject-else-without-if.min", "E0204", None),
        ("tests/diagnostics/cases/reject-statements-without-separator.min", "E0203", None),
        ("tests/diagnostics/cases/reject-unterminated-text.min", "E0104", None),
        ("tests/diagnostics/cases/non-ascii-identifier.min", "E0103", None),
    ):
        diagnostic(repository / relative, code, hint)

    # Independent short programs exercise the weaker message families without
    # copying production wording or deriving expected codes from the catalogue.
    for name, source, code in (
        ("unknown-value", "print(missing)\n", "E0301"),
        ("unknown-binary-literal", "print(binary_literal)\n", "E0301"),
        ("unknown-closing-literal", "print(closing_literal)\n", "E0301"),
        ("print-arguments", "print()\n", "E0404"),
        ("operator", "print(true * false)\n", "E0406"),
        ("list-elements", 'let lights = [1, "two"]\n', "E0405"),
        ("immutable", "constant light = 1\nlight = 2\n", "E0407"),
        ("nothing-binding", 'function shine() { print("light") }\nlet light = shine()\n', "E0409"),
        ("missing-return", "function glow(): Integer { print(1) }\n", "E0403"),
        ("iteration", "for light in true { print(light) }\n", "E0410"),
        ("list-equality", "let lights = [1]\nprint(lights == lights)\n", "E0411"),
        ("missing-closing-field", "record literal { closing: Integer }\nlet value = literal {}\n", "E0701"),
    ):
        path = root / f"{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, code)

    # Existing rejection messages outside the golden corpus keep the same
    # published families. Counts take precedence over builtin type expectations.
    for name, source, code in (
        ("octal-invalid-digit", "print(0o8)\n", "E0104"),
        ("decimal-leading-zero", "print(0755)\n", "E0104"),
        ("octal-decimal-point", "print(0o7.5)\n", "E0104"),
        ("hex-decimal-point", "print(0xFF.5)\n", "E0104"),
        ("float-missing-exponent", "print(1.5e)\n", "E0104"),
        ("float-overflow", "print(1.0e999)\n", "E0104"),
        ("and-left-type", "print(1 && true)\n", "E0406"),
        ("and-right-type", "print(true && 1)\n", "E0406"),
        ("or-left-type", "print(1 || false)\n", "E0406"),
        ("or-right-type", "print(false || 1)\n", "E0406"),
        ("print-value-type", "print([1])\n", "E0401"),
        ("text-value-type", "Text([1])\n", "E0401"),
        ("fail-value-type", "fail(42)\n", "E0401"),
        ("exit-value-type", 'exit("zero")\n', "E0401"),
        ("join-text-value-type", "joinText(1)\n", "E0401"),
        ("builtin-count-precedence", "exit()\n", "E0404"),
        ("callback-missing-argument",
         "let callback = function(value: Integer): Integer { return value }\ncallback()\n", "E0404"),
        ("callback-extra-argument",
         "let callback = function(): Integer { return 1 }\ncallback(2)\n", "E0404"),
        ("method-missing-argument",
         "record Box { value: Integer }\nfunction Box.read(amount: Integer) {}\n"
         "Box { value: 0 }.read()\n", "E0404"),
        ("method-extra-argument",
         "record Box { value: Integer }\nfunction Box.read(amount: Integer) {}\n"
         "Box { value: 0 }.read(1, 2)\n", "E0404"),
    ):
        path = root / f"followup-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, code, expected_source_lines=source.splitlines())

    # Logical type failures use the offending operand's first token. Compound
    # operands retain the single-token presentation, on their first source line.
    for name, source, side, operator, span in (
        ("and-left", "print(41 && true)\n", "left", "&&", (1, 7, 1, 9)),
        ("and-right", "print(true && 41)\n", "right", "&&", (1, 15, 1, 17)),
        ("or-left", "print(41 || false)\n", "left", "||", (1, 7, 1, 9)),
        ("or-right", "print(false || 41)\n", "right", "||", (1, 16, 1, 18)),
        ("multiline-and-left", "print(\n    41 && true\n)\n", "left", "&&", (2, 5, 2, 7)),
        ("multiline-and-right", "print(\n    true &&\n    41\n)\n", "right", "&&", (3, 5, 3, 7)),
        ("multiline-or-left", "print(\n    41 || false\n)\n", "left", "||", (2, 5, 2, 7)),
        ("multiline-or-right", "print(\n    false ||\n    41\n)\n", "right", "||", (3, 5, 3, 7)),
        ("grouped-and-left", "print((41 + 1) && true)\n", "left", "&&", (1, 7, 1, 8)),
        ("grouped-and-right", "print(true && (41 + 1))\n", "right", "&&", (1, 15, 1, 16)),
        ("grouped-or-left", "print((41 + 1) || false)\n", "left", "||", (1, 7, 1, 8)),
        ("grouped-or-right", "print(false || (41 + 1))\n", "right", "||", (1, 16, 1, 17)),
        ("chained-and", "print(true && false && 41)\n", "right", "&&", (1, 24, 1, 26)),
        ("chained-or", "print(false || true || 41)\n", "right", "||", (1, 24, 1, 26)),
        ("mixed-inner-left", "print(true || 41 && false)\n", "left", "&&", (1, 15, 1, 17)),
        ("mixed-inner-right", "print(false && 41 || true)\n", "right", "&&", (1, 16, 1, 18)),
        ("spanning-and-right", "print(\n    true && (41 +\n        1)\n)\n", "right", "&&", (2, 13, 2, 14)),
        ("spanning-or-left", "print(\n    (41 +\n        1) || false\n)\n", "left", "||", (2, 5, 2, 6)),
        ("nested-or-right", "print(true && (false || 41))\n", "right", "||", (1, 25, 1, 27)),
        ("nested-and-right", "print(false || (true && 41))\n", "right", "&&", (1, 25, 1, 27)),
    ):
        path = root / f"boolean-span-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, "E0406", expected_span=span, expected_source_lines=source.splitlines(),
                   expected_message=f"the {side} side of {operator} must be Boolean; "
                                    "expected Boolean, found Integer")

    # Type failures point at the supplied value. Count failures continue to
    # point at the call name and take precedence over type validation.
    for name, source, primary, span in (
        ("print-list", "print([1])\n",
         "print expects one Integer, Float, Text, Character, or Boolean value; found List<Integer>",
         (1, 7, 1, 8)),
        ("text-list", "Text([1])\n",
         "Text expects one Integer, Float, Text, Character, Boolean, or Bytes value; found List<Integer>",
         (1, 6, 1, 7)),
        ("fail-integer", "fail(42)\n", "fail expects one Text argument; found Integer",
         (1, 6, 1, 8)),
        ("exit-text", 'exit("zero")\n', "exit expects one Integer argument; found Text",
         (1, 6, 1, 12)),
        ("join-integer", "joinText(1)\n", "joinText expects one List<Text> argument; found Integer",
         (1, 10, 1, 11)),
        ("nested-call", 'print("first")\nfail(Integer("3"))\n',
         "fail expects one Text argument; found Integer", (2, 6, 2, 13)),
        ("record-name", "record Lantern { light: Integer }\nprint(Lantern { light: 3 })\n",
         "print expects one Integer, Float, Text, Character, or Boolean value; found Lantern",
         (2, 7, 2, 14)),
        ("count-before-type", 'exit("zero", "one")\n',
         "exit expects 1 argument, but received 2", (1, 1, 1, 5)),
    ):
        path = root / f"builtin-span-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, "E0404" if name == "count-before-type" else "E0401",
                   expected_message=primary, expected_span=span,
                   expected_source_lines=source.splitlines())

    for index, literal in enumerate(("0b102", "1__0", "1.5_0", "0xFF_FF"), 1):
        path = root / f"malformed-number-{index}.min"
        prefix = "let count = "
        path.write_text(f"{prefix}{literal}\n", encoding="utf-8")
        first = len(prefix) + 1
        value = diagnostic(path, "E0104", expected_span=(1, first, 1, first + len(literal)))
        assert value["sourceLine"] == prefix + literal, (literal, value)

    interpolation = root / "empty-interpolation.min"
    interpolation.write_text(r'print("a \()")' + "\n", encoding="utf-8")
    diagnostic(interpolation, "E0408", expected_message="text interpolation is missing a value")

    choice = "choice Weather { Clear; Rain(drops: Integer); Storm(name: Text, drops: Integer, windy: Boolean) }\n"
    for name, constructor, case, count, extra, signature in (
        ("no-payload-extra", "Weather.Clear(1)", "Clear", 0, True, ""),
        ("one-payload-missing", "Weather.Rain()", "Rain", 1, False, "Rain(drops: Integer)"),
        ("one-payload-extra", "Weather.Rain(1, 2)", "Rain", 1, True, "Rain(drops: Integer)"),
        ("many-payloads-missing", "Weather.Storm()", "Storm", 3, False,
         "Storm(name: Text, drops: Integer, windy: Boolean)"),
        ("many-payloads-few", 'Weather.Storm("Dawn", 3)', "Storm", 3, False,
         "Storm(name: Text, drops: Integer, windy: Boolean)"),
        ("many-payloads-trailing-few", 'Weather.Storm("Dawn",)', "Storm", 3, False,
         "Storm(name: Text, drops: Integer, windy: Boolean)"),
        ("many-payloads-extra", 'Weather.Storm("Dawn", 3, true, 4)', "Storm", 3, True,
         "Storm(name: Text, drops: Integer, windy: Boolean)"),
    ):
        path = root / f"choice-{name}.min"
        path.write_text(choice + f"let weather = {constructor}\n", encoding="utf-8")
        noun = "payload value" if count == 1 else "payload values"
        problem = "more" if extra else "fewer"
        message = f"choice case '{case}' expects {count} {noun}, but {problem} were provided"
        help_text = ("supply each value in declaration order: " + signature if count else
                     "this case has no payload; remove the values inside its parentheses")
        diagnostic(path, "E0603", expected_message=message, expected_help=help_text)

    compile_program("choice-trailing-comma", choice +
                    'let rain = Weather.Rain(3,)\n'
                    'let storm = Weather.Storm("Dawn", 3, true,)\n'
                    'let clear = Weather.Clear()\n')

    for case, constructor in (("empty", "Weather.Clear("), ("filled", "Weather.Rain(3")):
        path = root / f"choice-unclosed-{case}.min"
        path.write_text(choice + f"let weather = {constructor}", encoding="utf-8")
        diagnostic(path, "E0202")

    # These positions are independently counted from the original programs.
    # Prefix comments contain Unicode; LF/CRLF must retain the same scalar spans.
    prefix = "// a quiet sky: é🙂\n\n"
    body_message = "a declaration is missing its '{ ... }' body"
    close_message = "a declaration is missing its closing '}'"
    body_repair = "add { ... } after this declaration's header"
    close_repair = "add '}' to close the body that starts here"
    for name, source, message, repair, span in (
        ("function-body", prefix + "function shine(): Integer", body_message, body_repair, (3, 1, 3, 9)),
        ("record-body", prefix + "record Window", body_message, body_repair, (3, 1, 3, 7)),
        ("function-close", prefix + "function shine(): Integer {\n    return 3\n",
         close_message, close_repair, (3, 27, 3, 28)),
        ("record-close", prefix + "record Window {\n    light: Integer\n",
         close_message, close_repair, (3, 15, 3, 16)),
        ("callback-body", prefix + "let shine = function(): Integer",
         "callback is missing its body", body_repair, (3, 13, 3, 21)),
        ("callback-close", prefix + "let shine = function(): Integer {\n    return 3\n",
         "callback body is missing its closing brace", close_repair, (3, 33, 3, 34)),
    ):
        for ending, separator in (("lf", "\n"), ("crlf", "\r\n")):
            path = root / f"delimiter-{name}-{ending}.min"
            path.write_bytes(source.replace("\n", separator).encode("utf-8"))
            diagnostic(path, "E0202", expected_message=message, expected_help=repair,
                       expected_span=span, expected_source_lines=source.splitlines())

    imported = root / "broken-module.min"
    importer = root / "delimiter-importer.min"
    importer.write_text('use "./broken-module.min" as broken\nprint(1)\n', encoding="utf-8")
    for name, source, message, repair, span in (
        ("body", prefix + "public function shine(): Integer", body_message, body_repair, (3, 8, 3, 16)),
        ("close", prefix + "public function shine(): Integer {\n    return 3\n",
         close_message, close_repair, (3, 34, 3, 35)),
    ):
        for ending, separator in (("lf", "\n"), ("crlf", "\r\n")):
            imported.write_bytes(source.replace("\n", separator).encode("utf-8"))
            diagnostic(importer, "E0202", expected_message=message, expected_help=repair,
                       expected_span=span, expected_source_lines=source.splitlines(),
                       diagnostic_file=imported)

    compile_program("delimiter-valid-declarations", prefix +
                    "record Window {\n    light: Integer\n}\n" +
                    "function shine(): Integer {\n    return 3\n}\nprint(shine())\n")
    compile_program("delimiter-valid-callback", prefix +
                    "let shine = function(): Integer {\n    return 3\n}\nprint(shine())\n")
    compile_program("delimiter-valid-nested-callback", prefix +
                    "let shine = function(value: Integer): Integer {\n" +
                    "    let inner = function(value: Integer): Integer { return value }\n" +
                    "    return inner(value)\n}\nprint(shine(3))\n")

    # Follow-on to errors-more-families.patch: saved argument starts retain the
    # original first-token ranges, even when argument parsing advances state.
    position_flag = "function flag(): Boolean { return false }\n"
    position_problem = 'record Problem { message: Text }\nlet bad = Problem { message: "bad" }\n'
    list_position_message = "List.slice positions must be Integers; expected Integer, found Boolean"
    truncate_position_message = "List.truncate positions must be Integers; expected Integer, found Boolean"
    text_position_message = "Text.slice positions must be Integers; expected Integer, found Boolean"
    list_position_repair = "use Integer positions, such as values.slice(0, values.length)"
    truncate_position_repair = "use an Integer length, such as values.truncate(0)"
    text_position_repair = "use Integer positions, such as text.slice(0, text.length)"
    for name, source, message, repair, span in (
        ("truncate-direct", "let values = [1]\nvalues.truncate(true)\n",
         truncate_position_message, truncate_position_repair, (2, 17, 2, 21)),
        ("list-start-direct", "let values = [1]\nvalues.slice(false, 1)\n",
         list_position_message, list_position_repair, (2, 14, 2, 19)),
        ("list-end-direct", "let values = [1]\nvalues.slice(0, false)\n",
         list_position_message, list_position_repair, (2, 17, 2, 22)),
        ("text-start-direct", 'print("harbour".slice(false, 1))\n',
         text_position_message, text_position_repair, (1, 23, 1, 28)),
        ("text-end-direct", 'print("harbour".slice(0, false))\n',
         text_position_message, text_position_repair, (1, 26, 1, 31)),
        ("truncate-call", position_flag + "let values = [1]\nvalues.truncate(flag())\n",
         truncate_position_message, truncate_position_repair, (3, 17, 3, 21)),
        ("list-start-call", position_flag + "let values = [1]\nvalues.slice(flag(), 1)\n",
         list_position_message, list_position_repair, (3, 14, 3, 18)),
        ("list-end-call", position_flag + "let values = [1]\nvalues.slice(0, flag())\n",
         list_position_message, list_position_repair, (3, 17, 3, 21)),
        ("text-start-call", position_flag + 'print("harbour".slice(flag(), 1))\n',
         text_position_message, text_position_repair, (2, 23, 2, 27)),
        ("text-end-call", position_flag + 'print("harbour".slice(0, flag()))\n',
         text_position_message, text_position_repair, (2, 26, 2, 30)),
        ("list-start-multiline", "let values = [1]\nvalues.slice(\n    false,\n    1\n)\n",
         list_position_message, list_position_repair, (3, 5, 3, 10)),
        ("text-end-multiline", 'print("harbour".slice(\n    0,\n    false\n))\n',
         text_position_message, text_position_repair, (3, 5, 3, 10)),
        ("text-both-invalid", 'print("harbour".slice(false, true))\n',
         text_position_message, text_position_repair, (1, 23, 1, 28)),
        ("list-start-before-later-name", "let values = [1]\nvalues.slice(false, missing)\n",
         list_position_message, list_position_repair, (2, 14, 2, 19)),
        ("text-record-name", position_problem + 'print("harbour".slice(bad, 1))\n',
         "Text.slice positions must be Integers; expected Integer, found Problem",
         text_position_repair, (3, 23, 3, 26)),
        ("text-list-type", 'print("harbour".slice(0, [1]))\n',
         "Text.slice positions must be Integers; expected Integer, found List<Integer>",
         text_position_repair, (1, 26, 1, 27)),
        ("truncate-record-name", position_problem + "let values = [1]\nvalues.truncate(bad)\n",
         "List.truncate positions must be Integers; expected Integer, found Problem",
         truncate_position_repair, (4, 17, 4, 20)),
    ):
        path = root / f"position-anchor-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, "E0410", expected_message=message, expected_help=repair,
                   expected_span=span, expected_source_lines=source.splitlines())

    # Text keeps its existing parse/closing-token priority before type checks.
    for name, source, code, message, span in (
        ("text-later-name-before-type", 'print("harbour".slice(false, missing))\n', "E0301",
         "I can't find a value named 'missing'", (1, 30, 1, 37)),
        ("text-close-before-type", 'print("harbour".slice(false, 1, 2))\n', "E0202",
         "expected ')', found ','", (1, 31, 1, 32)),
    ):
        path = root / f"position-anchor-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, code, expected_message=message, expected_span=span,
                   expected_source_lines=source.splitlines())

    compile_program("position-anchor-valid-nested",
                    "function start(): Integer { return 0 }\n"
                    "function finish(): Integer { return 1 }\n"
                    "let values = [1, 2]\nlet middle = values.slice(start(), finish())\n"
                    'values.truncate(finish())\nprint("harbour".slice(start(), finish()))\n')

    # Existing-suite seeds exercise exact emitting templates in their existing
    # families. These are classification/repair tests, not new span policies.
    generic_repair = "use the same type for every value bound to this type parameter"
    constant_repair = "change the initializer or the constant's declared type so they agree"
    for name, source, code, message, repair in (
        ("list-slice-start", "let values = [1]\nvalues.slice(false, 1)\n", "E0410",
         "List.slice positions must be Integers; expected Integer, found Boolean",
         "use Integer positions, such as values.slice(0, values.length)"),
        ("list-slice-end", "let values = [1]\nvalues.slice(0, false)\n", "E0410",
         "List.slice positions must be Integers; expected Integer, found Boolean",
         "use Integer positions, such as values.slice(0, values.length)"),
        ("list-truncate", "let values = [1]\nvalues.truncate(true)\n", "E0410",
         "List.truncate positions must be Integers; expected Integer, found Boolean",
         "use an Integer length, such as values.truncate(0)"),
        ("text-slice-start", 'print("harbour".slice(false, 1))\n', "E0410",
         "Text.slice positions must be Integers; expected Integer, found Boolean", "use Integer positions, such as text.slice(0, text.length)"),
        ("text-slice-end", 'print("harbour".slice(0, false))\n', "E0410",
         "Text.slice positions must be Integers; expected Integer, found Boolean", "use Integer positions, such as text.slice(0, text.length)"),
        ("generic-call", "function choose<Item>(left: Item, right: Item): Item { return left }\n"
         'print(choose(1, "two"))\n', "E0401",
         "type argument 'Item' is used inconsistently: Integer and Text", generic_repair),
        ("generic-record", "record Same<Item> { left: Item; right: Item }\n"
         'let value = Same { left: 1; right: "two" }\n', "E0401",
         "type argument 'Item' is used inconsistently: Integer and Text", generic_repair),
        ("constant-type", 'constant COUNT: Integer = "many"\n', "E0401",
         "the value for constant 'COUNT' is Text, not Integer", constant_repair),
        ("global-literal-type", "global TABLE: List<Integer> = 1\n", "E0401",
         "the value for constant 'TABLE' is Integer, not List<Integer>", constant_repair),
        ("duplicate-parameter", "function same<Item, Item>(value: Item): Item { return value }\n", "E0501",
         "type parameter 'Item' is declared twice",
         "give each type parameter a distinct name, or remove the repeated parameter"),
        ("duplicate-alias", "type Reading = Integer\ntype Reading = Text\n", "E0501",
         "module declares type 'Reading' more than once",
         "use one declaration for this type name, or rename one of the declarations"),
        ("duplicate-named-test", 'test "same" {}\ntest "same" {}\n', "E0501",
         "this module already has a test with that name",
         "give each test in this module a different name, or remove the repeated test"),
    ):
        path = root / f"family-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, code, expected_message=message, expected_help=repair,
                   expected_source_lines=source.splitlines())

    private_module = root / "family-private.min"
    private_module.write_text(
        "public record Secret { private hiddenLight: Integer }\n"
        "public type Treasure = Secret\n"
        "public function create(): Secret { return Secret { hiddenLight: 42 } }\n", encoding="utf-8")
    for construction in ("Secret", "Treasure"):
        source = ('use "./family-private.min" as vault\n'
                  f"let forged = vault.{construction} {{}}\n")
        path = root / f"family-private-{construction}.min"
        path.write_text(source, encoding="utf-8")
        value = diagnostic(path, "E0307",
                           expected_help="call a public factory function from the module that declares this record",
                           expected_source_lines=source.splitlines())
        assert value["message"].startswith("record '") and value["message"].endswith(
            "' has private fields, so only its own module can create one"), value
        assert "hiddenLight" not in value["message"] and all(
            "hiddenLight" not in note for note in value["help"]), value
    compile_program("family-public-factory", 'use "./family-private.min" as vault\nlet value = vault.create()\n')

    # Message-template words inside ordinary names or paths must not take
    # precedence over the compiler's actual unknown-name/source-read problem.
    for name, source, code in (
        ("unknown-generic-words", "print(type_argument_Item_is_used_inconsistently)\n", "E0301"),
        ("unknown-private-words", "print(has_private_fields)\n", "E0301"),
        ("unknown-duplicate-words", "module_declares_type()\n", "E0302"),
    ):
        path = root / f"family-collision-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, code, expected_source_lines=source.splitlines())
    for name in ("record 'Secret' has private fields, so only its own module can create one.min",
                 "type argument 'Item' is used inconsistently: Integer and Text.min"):
        diagnostic(root / name, "E0101", has_excerpt=False)

    compile_program("family-valid-ranges", "let values = [1, 2]\nlet middle = values.slice(0, 1)\n"
                    'values.truncate(1)\nprint("harbour".slice(0, 3))\n')
    compile_program("family-valid-generic-alias-shadow", "type Item = Text\n"
                    "function identity<Item>(value: Item): Item { return value }\n"
                    "constant COUNT: Integer = 3\nprint(identity(COUNT))\n")
    compile_program("family-distinct-named-tests", 'test "dawn" {}\ntest "night" {}\n')

    # The five try diagnostics retain their semantic priority and primary
    # prefixes. All ranges below are counted from these literal source strings.
    enclosing_repair = "use try inside a function returning Result, or handle this Result with match"
    operand_repair = "pass a Result value to try; use an ordinary value directly without try"
    payload_repair = "handle the Result with match and convert its error to the enclosing error type"
    protocol_primary = "try context needs an error type with a public withContext(Text) method returning the same error type"
    protocol_repair = "provide a public withContext(Text) method returning the same error type, or handle the Result with match"
    context_repair = 'use a Text expression after else, such as "reading the configuration"'
    for name, source, primary, repair, span in (
        ("top-level", "// leading source\n\nlet value = try Ok<Integer, Text>(1)\n",
         "try requires a Result-returning function", enclosing_repair, (3, 13, 3, 16)),
        ("enclosing-integer", "function bad(): Integer {\n    let value = try 42\n    return 0\n}\n",
         "try requires a Result-returning function; found Integer", enclosing_repair, (2, 17, 2, 20)),
        ("enclosing-nothing", "function bad() {\n    try Ok<Integer, Text>(1)\n}\n",
         "try requires a Result-returning function; found Nothing", enclosing_repair, (2, 5, 2, 8)),
        ("integer-operand", "function bad(): Result<Integer, Text> {\n    let value = try 42\n    return Ok(value)\n}\n",
         "try needs a Result; found Integer", operand_repair, (2, 21, 2, 23)),
        ("parenthesized-operand", "function bad(): Result<Integer, Text> {\n    let value = try (42)\n    return Ok(value)\n}\n",
         "try needs a Result; found Integer", operand_repair, (2, 21, 2, 22)),
        ("call-operand", "function read(): Integer { return 1 }\nfunction bad(): Result<Integer, Text> {\n"
         "    let value = try read()\n    return Ok(value)\n}\n",
         "try needs a Result; found Integer", operand_repair, (3, 21, 3, 25)),
        ("error-payload", "function bad(): Result<Integer, Integer> {\n"
         '    let value = try Err<Integer, Text>("bad")\n    return Ok(value)\n}\n',
         "try error type must match the enclosing Result error type; expected Integer, found Text",
         payload_repair, (2, 17, 2, 20)),
    ):
        path = root / f"try-types-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, "E0401", expected_message=primary, expected_help=repair,
                   expected_span=span, expected_source_lines=source.splitlines(), exact_output=True)

    for name, context_expression in (("missing-protocol", '"reading"'),
                                     ("protocol-before-context-type", "42")):
        source = ('function read(): Result<Integer, Text> { return Err("bad") }\n'
                  "function bad(): Result<Integer, Text> {\n"
                  f"    let value = try read() else {context_expression}\n"
                  "    return Ok(value)\n}\n")
        path = root / f"try-types-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, "E0401", expected_message=protocol_primary + "; found Text",
                   expected_help=protocol_repair, expected_span=(3, 28, 3, 32),
                   expected_source_lines=source.splitlines(), exact_output=True)

    problem = "record Problem { message: Text }\n"
    reader = 'function read(): Result<Integer, Problem> { return Err(Problem { message: "bad" }) }\n'
    wrapper = ('function bad(): Result<Integer, Problem> {\n'
               '    let value = try read() else "reading"\n    return Ok(value)\n}\n')
    source = problem + reader + wrapper
    path = root / "try-types-record-without-protocol.min"
    path.write_text(source, encoding="utf-8")
    diagnostic(path, "E0401", expected_message=protocol_primary + "; found Problem",
               expected_help=protocol_repair, expected_span=(4, 28, 4, 32),
               expected_source_lines=source.splitlines(), exact_output=True)

    for name, method, found in (
        ("wrong-protocol-parameter", "public function Problem.withContext(context: Integer): Problem { return self }\n",
         "(Integer) -> Problem"),
        ("wrong-protocol-result", "public function Problem.withContext(context: Text): Text { return context }\n",
         "(Text) -> Text"),
        ("missing-protocol-parameter", "public function Problem.withContext(): Problem { return self }\n",
         "() -> Problem"),
        ("extra-protocol-parameter", "public function Problem.withContext(context: Text, count: Integer): Problem { return self }\n",
         "(Text, Integer) -> Problem"),
    ):
        source = problem + method + reader + wrapper
        path = root / f"try-types-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, "E0401", expected_message=protocol_primary + "; expected (Text) -> Problem, found " + found,
                   expected_help=protocol_repair, expected_span=(5, 28, 5, 32),
                   expected_source_lines=source.splitlines(), exact_output=True)

    method = "public function Problem.withContext(context: Text): Problem { return self }\n"
    for name, expression, found, span in (
        ("integer-context", "42", "Integer", (5, 33, 5, 35)),
        ("list-context", "[1]", "List<Integer>", (5, 33, 5, 34)),
        ("nested-context", "number()", "Integer", (6, 33, 6, 39)),
    ):
        number = "function number(): Integer { return 42 }\n" if name == "nested-context" else ""
        source = (problem + method + reader + number + "function bad(): Result<Integer, Problem> {\n"
                  f"    let value = try read() else {expression}\n    return Ok(value)\n}}\n")
        path = root / f"try-types-{name}.min"
        path.write_text(source, encoding="utf-8")
        diagnostic(path, "E0401", expected_message="try context must be Text; expected Text, found " + found,
                   expected_help=context_repair, expected_span=span,
                   expected_source_lines=source.splitlines(), exact_output=True)

    compile_program("try-types-valid-propagation",
                    'function read(good: Boolean): Result<Integer, Text> { if good { return Ok(3) }; return Err("dark") }\n'
                    "function outer(good: Boolean): Result<Integer, Text> { let value = try read(good); return Ok(value + 1) }\n"
                    'match outer(true) { Ok(value) { print(value) } Err(error) { print(error) } }\n'
                    'match outer(false) { Ok(value) { print(value) } Err(error) { print(error) } }\n')
    compile_program("try-types-valid-context", problem +
                    'public function Problem.withContext(context: Text): Problem { return Problem { message: context + ": " + self.message } }\n' +
                    'function read(good: Boolean): Result<Integer, Problem> { if good { return Ok(1) }; return Err(Problem { message: "dark" }) }\n' +
                    'function context(): Text { print("context evaluated"); return "reading" }\n' +
                    'function outer(good: Boolean): Result<Integer, Problem> { let value = try read(good) else context(); return Ok(value) }\n' +
                    'match outer(true) { Ok(value) { print(value) } Err(error) { print(error.message) } }\n' +
                    'match outer(false) { Ok(value) { print(value) } Err(error) { print(error.message) } }\n')

    # Same spelling does not make records from different modules identical.
    # Seed: ResultReview.test_review_same_record_spelling_in_distinct_modules_is_not_same_error.
    identity_left = root / "identity-left.min"
    identity_right = root / "identity-right.min"
    identity_left.write_text(
        'public record Failure { text: Text }\n'
        'public function failRead(): Result<Integer, Failure> {\n'
        '    return Err<Integer, Failure>(Failure { text: "left" })\n'
        '}\n', encoding="utf-8")
    identity_right.write_text('public record Failure { text: Text }\n', encoding="utf-8")
    identity_source = (
        'use "./identity-left.min" as left\n'
        'use "./identity-right.min" as right\n'
        'function wrong(): Result<Integer, right.Failure> {\n'
        '    let n = try left.failRead()\n'
        '    return Ok<Integer, right.Failure>(n)\n'
        '}\n')
    identity_path = root / "same-name-result-error.min"
    identity_path.write_text(identity_source, encoding="utf-8")
    identity_primary = (
        "try error type must match the enclosing Result error type; "
        "expected Failure, found Failure (these are different types)")
    identity_diagnostic = diagnostic(
        identity_path, "E0401",
        expected_help="handle the Result with match and convert its error to the enclosing error type",
        expected_message=identity_primary, expected_span=(4, 13, 4, 16),
        expected_source_lines=identity_source.splitlines())
    # The location header/file field may name a temporary test source; the
    # primary must never expose snapshot filenames or declaration origins.
    assert identity_diagnostic["label"] == "", identity_diagnostic
    for leaked in ("/tmp/", "/private/tmp/", "minyar-lsp-", "document-",
                   str(identity_left), str(identity_right),
                   "identity-left.min", "identity-right.min",
                   "minyar_module_", "minyar_generic_", "minyar_result_type_", ".minyar.fn."):
        assert leaked not in identity_diagnostic["message"], ("nominal identity primary leaked implementation data", leaked, identity_diagnostic)

    # The method exists, but its return record belongs to the other module.
    # Both signatures pretty-print identically; signature validation must
    # still precede the also-invalid Integer context expression after else.
    identity_protocol_left = root / "identity-protocol-left.min"
    identity_protocol_left.write_text(
        'use "./identity-right.min" as right\n'
        'public record Failure { text: Text }\n'
        'public function Failure.withContext(message: Text): right.Failure {\n'
        '    return right.Failure { text: self.text + message }\n'
        '}\n'
        'public function failRead(): Result<Integer, Failure> {\n'
        '    return Err<Integer, Failure>(Failure { text: "left" })\n'
        '}\n', encoding="utf-8")
    identity_protocol_source = (
        'use "./identity-protocol-left.min" as left\n'
        'use "./identity-right.min" as right\n'
        'function wrong(): Result<Integer, left.Failure> {\n'
        '    let n = try left.failRead() else 42\n'
        '    return Ok<Integer, left.Failure>(n)\n'
        '}\n')
    identity_protocol_path = root / "same-name-context-return.min"
    identity_protocol_path.write_text(identity_protocol_source, encoding="utf-8")
    identity_protocol_primary = (
        "try context needs an error type with a public withContext(Text) method returning the same error type; "
        "expected (Text) -> Failure, found (Text) -> Failure (these are different types)")
    identity_protocol_diagnostic = diagnostic(
        identity_protocol_path, "E0401",
        expected_help="provide a public withContext(Text) method returning the same error type, or handle the Result with match",
        expected_message=identity_protocol_primary, expected_span=(4, 33, 4, 37),
        expected_source_lines=identity_protocol_source.splitlines())
    assert identity_protocol_diagnostic["label"] == "", identity_protocol_diagnostic
    for leaked in ("/tmp/", "/private/tmp/", "minyar-lsp-", "document-",
                   str(identity_protocol_left), str(identity_right),
                   "identity-protocol-left.min", "identity-right.min",
                   "minyar_module_", "minyar_generic_", "minyar_result_type_", ".minyar.fn."):
        assert leaked not in identity_protocol_diagnostic["message"], ("protocol identity primary leaked implementation data", leaked, identity_protocol_diagnostic)


    missing = root / "missing source.min"
    diagnostic(missing, "E0101", has_excerpt=False)
    diagnostic(root / "invalid UTF-8.min", "E0101", has_excerpt=False)
    invalid = root / "invalid utf8.min"
    invalid.write_bytes(b"// a valid first line\nprint(\xff)\n")
    value = diagnostic(invalid, "E0102")
    assert (value["line"], value["column"]) == (2, 7), value
    assert not (root / "Minyar.toml").exists() and not (root / "target").exists(), (
        "explanations never create a project or build directory in the invoking directory")

print(f"Error explanations: {len(CODES)} stable codes through compiler and launcher; "
      f"{compiled} valid examples/boundaries and {checked} rejection code/help pairs, "
      "source-read failures and exact CLI errors passed")
