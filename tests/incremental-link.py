#!/usr/bin/env python3
"""Watch rebuilds link cached partitions (tools/link-partitions.min).

Builds gallery programs with and without MINYAR_INCREMENTAL_LINK=1 and checks
that both binaries behave the same, then edits a program twice (a literal, then
a function body) and checks that each rebuild recompiled at most two partition
objects and runs the edited code.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCALE = int(os.environ.get("MINYAR_TEST_TIMEOUT_SCALE", "1"))
PROGRAMS = ["capabilities", "choice", "community-garden", "configuration", "constellations", "contracts", "generics",
            "generic-records", "generic-results", "handles", "iteration", "lanterns", "last-use-returns", "methods",
            "mutable-scalar-records", "night-watch-values", "first-light"]


def build(launcher, source, output, incremental):
    environment = dict(os.environ)
    environment.pop("MINYAR_INCREMENTAL_LINK", None)
    if incremental:
        environment["MINYAR_INCREMENTAL_LINK"] = "1"
    return subprocess.run([str(launcher), "--debug", "--incremental", str(source), "-o", str(output)], env=environment,
                          capture_output=True, timeout=300 * SCALE)


def run(binary):
    try:
        return subprocess.run([str(binary)], stdin=subprocess.DEVNULL, capture_output=True, timeout=20 * SCALE)
    except subprocess.TimeoutExpired:
        return None


def objects(binary):
    cache = binary.parent / ".minyar-link" / binary.name
    return {path.name: path.stat().st_mtime_ns for path in cache.glob("*.o")}


def main():
    launcher = Path(sys.argv[1]).resolve()
    gallery = launcher.parent / "examples/gallery"
    compared = 0
    with tempfile.TemporaryDirectory(prefix="minyar-incremental-link-") as temporary:
        work = Path(temporary)
        for name in PROGRAMS:
            source = gallery / (name + ".min")
            if not source.is_file():
                continue
            whole, split = work / ("whole-" + name), work / ("split-" + name)
            first = build(launcher, source, whole, False)
            second = build(launcher, source, split, True)
            assert (first.returncode == 0) == (second.returncode == 0), (name, first.stderr[-2000:], second.stderr[-2000:])
            if first.returncode != 0:
                continue
            # Up to 33 objects: the data partition and 32 code partitions (identical ones share an object).
            assert 2 <= len(objects(split)) <= 33, (name, "expected partition objects", objects(split))
            expected, actual = run(whole), run(split)
            if expected is None:
                assert actual is None, name
                continue
            assert (actual.returncode, actual.stdout) == (expected.returncode, expected.stdout), (name, expected, actual)
            compared += 1
        assert compared >= 10, ("too few gallery programs compared", compared)
        # Edits recompile only the partitions they touch.
        source = work / "lanterns.min"
        source.write_text((gallery / "lanterns.min").read_text())
        binary = work / "lanterns"
        assert build(launcher, source, binary, True).returncode == 0
        baseline = run(binary).stdout
        before = objects(binary)
        text = source.read_text()
        assert "keeps a light for evening" in text
        source.write_text(text.replace("keeps a light for evening", "keeps a lamp for evening"))
        built = build(launcher, source, binary, True)
        assert built.returncode == 0, built.stderr[-2000:]
        after = objects(binary)
        changed = [name for name in after if before.get(name) != after[name]]
        assert 1 <= len(changed) <= 2, ("a literal edit recompiles its partition only", changed)
        assert run(binary).stdout == baseline.replace(b"keeps a light", b"keeps a lamp"), run(binary).stdout
        before = after
        text = source.read_text()
        assert "lantern.evenings += 1" in text
        source.write_text(text.replace("lantern.evenings += 1", "lantern.evenings += 2"))
        built = build(launcher, source, binary, True)
        assert built.returncode == 0, built.stderr[-2000:]
        after = objects(binary)
        changed = [name for name in after if before.get(name) != after[name]]
        assert 1 <= len(changed) <= 2, ("a function body edit recompiles at most two partitions", changed)
        assert b"Ada keeps a lamp for evening 4" in run(binary).stdout, run(binary).stdout
    print("incremental link: " + str(compared) + " gallery programs behave the same as whole links; edits recompile one or two partitions")


if __name__ == "__main__":
    main()
