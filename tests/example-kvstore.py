#!/usr/bin/env python3
"""Build and exercise examples/kvstore: its unit tests, the SIGKILL recovery
test, the disk module's own tests, the CLI, and `minyar sim` torn-write
universes. A planted durability bug must make the simulation fail."""
import os
from pathlib import Path
import shutil
import subprocess

if not __debug__:
    raise SystemExit("example checks require assertions; remove Python -O")

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "minyar"
WORK = ROOT / "build/example-kvstore"
SCALE = int(os.environ.get("MINYAR_TEST_TIMEOUT_SCALE", "1"))
ENVIRONMENT = dict(os.environ)
for key in ("MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKELEVEL"):
    ENVIRONMENT.pop(key, None)


def run(arguments, cwd, status=0, timeout=600):
    result = subprocess.run([str(item) for item in arguments], cwd=cwd, env=ENVIRONMENT, text=True,
                            capture_output=True, timeout=timeout * SCALE)
    assert result.returncode == status, (arguments, result.returncode, result.stdout, result.stderr)
    return result.stdout


def fresh(name):
    project = WORK / name
    shutil.rmtree(project, ignore_errors=True)
    shutil.copytree(ROOT / "examples/kvstore", project, ignore=shutil.ignore_patterns("target"))
    return project


project = fresh("project")
tests = run([LAUNCHER, "test"], project)
assert "kill test passed" in tests and "0 failed" in tests, tests
assert "a torn tail at every byte offset keeps the complete prefix" in tests, tests

store = project / "target/cli-store"
run([LAUNCHER, "build"], project)
binary = project / "target/debug/kvstore"
run([binary, store, "put", "harbour", "light"], project)
run([binary, store, "put", "tide", "high"], project)
assert run([binary, store, "delete", "tide"], project) == "true\n"
run([binary, store, "compact"], project)
run([binary, store, "put", "moon", "full"], project)
assert run([binary, store, "list"], project) == "harbour=light\nmoon=full\n"
assert run([binary, store, "get", "harbour"], project) == "light\n"
run([binary, store, "get", "tide"], project, status=1)

simulated = run([LAUNCHER, "sim", "crash", "--seeds", "300"], project)
assert "300" in simulated, simulated

# Without syncing the directory after creating the log, a crash can lose the
# whole log, acknowledged writes included. The simulation must catch it.
planted = fresh("planted")
source = planted / "src/store.min"
original = source.read_text(encoding="utf-8")
guard = "    if created { try storage.syncDirectory(directory) }\n"
assert original.count(guard) == 1
source.write_text(original.replace(guard, ""), encoding="utf-8")
caught = subprocess.run([str(LAUNCHER), "sim", "crash", "--seeds", "300"], cwd=planted, env=ENVIRONMENT,
                        text=True, capture_output=True, timeout=600 * SCALE)
assert caught.returncode == 1, (caught.returncode, caught.stdout, caught.stderr)
assert "lost acknowledged" in caught.stdout + caught.stderr, (caught.stdout, caught.stderr)

module = WORK / "disk-tests"
run([LAUNCHER, "--test-mode", ROOT / "library/disk.min", "-o", module], ROOT)
run([module], ROOT)

shutil.rmtree(WORK, ignore_errors=True)
print("kvstore example: unit, SIGKILL, CLI, 300 simulated crashes and a planted durability bug passed")
