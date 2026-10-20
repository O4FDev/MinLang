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
                   expected_message=None, expected_span=None, expected_source_lines=None):
        global checked
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
        assert value["file"] == str(source), (source, value)
        assert value["line"] >= 1 and value["column"] >= 1, (source, value)
        assert value["endLine"] == value["line"] and value["endColumn"] >= value["column"], (source, value)
        assert f"  --> {source}:{value['line']}:{value['column']}\n" in human.stderr, (source, value, human.stderr)
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
                "caret starts at the numeric literal", source, human.stderr)
            assert len(underline.group()) == value["endColumn"] - value["column"], (
                "entire malformed numeric literal is underlined", source, human.stderr)
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
