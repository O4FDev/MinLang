#!/usr/bin/env python3
"""Piped transcript acceptance tests for the persistent native REPL."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


if not __debug__:
    raise SystemExit("REPL checks require Python assertions; remove -O")


TRANSCRIPT = r'''print("ONCE")
function initial(): Integer { print("INITIALIZED ONCE"); return 7 }
let saved: Integer = initial()
saved
let count = 10
count += 5
count
function score(): Integer { return count * 2 }
score()
count = 4
score()
use "text" as text
count
public function publicScore(): Integer { return count + 100 }
publicScore()
for count in 0..2 { print(count) }
count
function score(): Integer {
    return count * 3
}
score()
function add(count: Integer): Integer { return count + 1 }
add(8)
let greeting = "a lantern · λ"
greeting += "!"
greeting
let labels: List<Text> = ["first", "second"]
labels[0] = "changed"
print(labels[0])
let rejected: Integer = "wrong type"
let rejected = 99
rejected
function score(): Integer { return "wrong result" }
score()
missingFunction(3)
print(count)
print("literal count; @main(; // braces { stay in text")
record Unsupported { field: Integer }
parallel function unsupported(): Integer { return 1 }
use "./outside.min" as outside
use "/tmp/outside.min" as outside
use #"text"# as rawText
use "te\(count)" as interpolated
print("AFTER IMPORT REJECTIONS")
print("AFTER REJECTIONS")
saved
greeting
let sharedName = "Ada"
let nameAlias: Text = sharedName
let sharedWords: List<Text> = ["left", "right"]
let wordsAlias: List<Text> = sharedWords
sharedName += "!"
print("persistent \(sharedName), \(count)")
function interpolationEcho(value: Text): Text { return value }
print("nested=\("inner \(sharedName)")")
print("ordinary/triple=\(interpolationEcho("""
    inside \(sharedName)
    """))")
print("""
    triple/ordinary=\("inside \(count)")
    triple/triple=\(interpolationEcho("""
        inside \(sharedName)
        """))
    """)
print("commented=\((count + 3) /* count ) " \(missingInComment) */ + 2)")
print("line-comment=\(
    // sharedName ) " \(missingInLineComment)
    count + 5
)")
print("escaped \(sharedName) without a marker is ordinary text")
print("escaped \\(sharedName); live \(sharedName)")
print("slash then live: \\\(sharedName)")
print("nested escape=\(interpolationEcho("\\(sharedName) / \(sharedName)"))")
print(#"raw \(sharedName) \n "quoted" \(_repl_cell_0)"#)
print(#"""
    raw triple \(sharedName) \n
      "quoted" \(count)
    """#)
function localInterpolation(sharedName: Text, count: Integer): Text { return "local \(sharedName) / \(count) / \(greeting)" }
print(localInterpolation("Local", 8))
let interpolationCalls = 0
function nextInterpolation(): Integer { interpolationCalls += 1; return interpolationCalls }
print("effects: \(nextInterpolation()) | \("nested \(nextInterpolation())") | \(nextInterpolation())")
print("effects counted: \(interpolationCalls)")
let rendered: Text = "captured=\(sharedName)"
sharedWords[0] = "changed"
print("alias \(nameAlias), words \(wordsAlias[0]), length \(wordsAlias.length)")
sharedName = "replaced"
sharedWords = ["replacement"]
wordsAlias[1] = "retained"
print("kept \(wordsAlias[0]) / \(wordsAlias[1]); new \(sharedWords[0]); text \(nameAlias) / \(sharedName)")
rendered
print("invalid \(nextInterpolation()) / \(missingInterpolationValue + count)")
print("reserved \(_repl_cell_0[0])")
print("nested reserved \("inside \(_repl_cell_0[0])")")
print("literal _repl_cell_0 and \(count /* _repl_cell_0 */)")
print("AFTER INTERPOLATION REJECTION: \(count) / \(interpolationCalls)")
print("still kept: \(rendered), \(wordsAlias[0]), \(nameAlias)")
:reset
count
:quit
print("AFTER QUIT")
'''

EXPECTED = r'''ONCE
INITIALIZED ONCE
7
15
30
8
4
104
4
12
9
a lantern · λ!
changed
99
12
4
literal count; @main(; // braces { stay in text
AFTER IMPORT REJECTIONS
AFTER REJECTIONS
7
a lantern · λ!
persistent Ada!, 4
nested=inner Ada!
ordinary/triple=inside Ada!
triple/ordinary=inside 4
triple/triple=inside Ada!
commented=9
line-comment=9
escaped Ada! without a marker is ordinary text
escaped \(sharedName); live Ada!
slash then live: \Ada!
nested escape=\(sharedName) / Ada!
raw \(sharedName) \n "quoted" \(_repl_cell_0)
raw triple \(sharedName) \n
  "quoted" \(count)
local Local / 8 / a lantern · λ!
effects: 1 | nested 2 | 3
effects counted: 3
alias Ada, words changed, length 2
kept changed / retained; new replacement; text Ada / replaced
captured=Ada!
literal _repl_cell_0 and 4
AFTER INTERPOLATION REJECTION: 4 / 3
still kept: captured=Ada!, changed, Ada
4
'''

TRANSCRIPT_BYTES = TRANSCRIPT.encode("utf-8")
EXPECTED_BYTES = EXPECTED.encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("launcher", nargs="?", default=str(Path(__file__).resolve().parents[1] / "minyar"))
    parser.add_argument("--profile", choices=("all", "debug", "release"), default="all")
    arguments = parser.parse_args()
    scale = int(os.environ.get("MINYAR_TEST_TIMEOUT_SCALE", "1"))
    assert 1 <= scale <= 20, "MINYAR_TEST_TIMEOUT_SCALE must be from 1 to 20"
    launcher = str(Path(arguments.launcher).resolve())
    for release in (False, True):
        if arguments.profile != "all" and arguments.profile != ("release" if release else "debug"):
            continue
        command = [launcher, "repl"] + (["--release"] if release else [])
        result = subprocess.run(command, input=TRANSCRIPT_BYTES, capture_output=True, timeout=600 * scale)
        assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
        assert result.stdout == EXPECTED_BYTES, (command, result.stdout, result.stderr)
        errors = result.stderr.decode("utf-8", errors="replace")
        assert "error:" in errors, "real compiler rejections must be visible"
        assert "layouts and module declarations require a source file" in errors, errors
        assert errors.count("imports require an ordinary quoted bundled package name") == 4, errors
        assert "a local binding cannot shadow session value 'count' yet" in errors, errors
        assert "missingInterpolationValue" in errors, errors
        assert errors.count("names beginning with _repl_ are reserved for session storage") == 2, errors
        assert "restart minyar repl to reset native code and managed state" in errors, errors
        assert "cannot load this submission" not in errors, errors
        assert "Minyar stopped" not in errors, errors
        print("REPL " + ("release/O2" if release else "debug/O0") + ": persistent mutations, "
              "function replacement, owned Text/list values, multiline input, exact-once effects "
              "interpolation, alias retention and rejection recovery passed", flush=True)
    helped = subprocess.run([launcher, "repl", "--help"], text=True, capture_output=True, timeout=30 * scale)
    assert helped.returncode == 0 and "Minyar native REPL" in helped.stdout, helped
    eof = subprocess.run([launcher, "repl"], input='print("EOF exits")\n', text=True,
                         capture_output=True, timeout=60 * scale)
    assert eof.returncode == 0 and eof.stdout == "EOF exits\n", eof


if __name__ == "__main__":
    main()
