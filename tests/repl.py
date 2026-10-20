#!/usr/bin/env python3
"""Piped transcript acceptance tests for the persistent native REPL."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


if not __debug__:
    raise SystemExit("REPL checks require Python assertions; remove -O")


TRANSCRIPT = '''print("ONCE")
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
use "te\\(count)" as interpolated
print("AFTER IMPORT REJECTIONS")
print("AFTER REJECTIONS")
saved
greeting
:reset
count
:quit
print("AFTER QUIT")
'''

EXPECTED = '''ONCE
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
4
'''


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
        result = subprocess.run(command, input=TRANSCRIPT, text=True, encoding="utf-8",
                                capture_output=True, timeout=600 * scale)
        assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
        assert result.stdout == EXPECTED, (command, result.stdout, result.stderr)
        assert "error:" in result.stderr, "real compiler rejections must be visible"
        assert "layouts and module declarations require a source file" in result.stderr, result.stderr
        assert result.stderr.count("imports require an ordinary quoted bundled package name") == 4, result.stderr
        assert "a local binding cannot shadow session value 'count' yet" in result.stderr, result.stderr
        assert "restart minyar repl to reset native code and managed state" in result.stderr, result.stderr
        assert "cannot load this submission" not in result.stderr, result.stderr
        assert "Minyar stopped" not in result.stderr, result.stderr
        print("REPL " + ("release/O2" if release else "debug/O0") + ": persistent mutations, "
              "function replacement, owned Text/list values, multiline input, exact-once effects "
              "and rejection recovery passed", flush=True)
    helped = subprocess.run([launcher, "repl", "--help"], text=True, capture_output=True, timeout=30 * scale)
    assert helped.returncode == 0 and "Minyar native REPL" in helped.stdout, helped
    eof = subprocess.run([launcher, "repl"], input='print("EOF exits")\n', text=True,
                         capture_output=True, timeout=60 * scale)
    assert eof.returncode == 0 and eof.stdout == "EOF exits\n", eof


if __name__ == "__main__":
    main()
