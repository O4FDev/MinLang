#!/usr/bin/env python3
"""Public release ownership, service points and bounded-work accounting."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


ENGINES = ["ordinary", "cycle"]
PROFILES = ["eager", "system-k1", "system-k32", "fixed-k1", "fixed-k32"]
OPTIMIZATIONS = ["0", "2"]
SUCCESS = "public release accounting passed\n"
TRANSCRIPTS = {
    "1": "immortal 1 2 161\nshared 1 1 160\nnull 1 2 160\nlast 1 2 159\n" + SUCCESS,
    "32": "immortal 32 1 145\nshared 32 1 129\nnull 32 1 113\nlast 32 2 97\n" + SUCCESS,
}


def cycle_source(source):
    # Keep the complete transform in sync with tools/test-runtime.min:cycleSource.
    for ordinary, traced in [("minyar_rc.h", "minyar_cycle_rc.h"),
                             ("minyar_collections.h", "minyar_cycle_collections.h")]:
        before = '#include "' + ordinary + '"'
        if source.count(before) != 1:
            raise RuntimeError("cycle runtime include must occur once: " + before)
        source = source.replace(before, '#include "' + traced + '"', 1)
    prefix = ("#define MINYAR_SORT_GRAPH 1\n#define MINYAR_MAP_CYCLE_RUNTIME 1\n"
              "#if defined(__GNUC__) || defined(__clang__)\n"
              "#define MINYAR_NOINLINE __attribute__((noinline))\n"
              "#else\n#define MINYAR_NOINLINE\n#endif\n")
    return prefix + source + '\n#include "minyar_callbacks.h"\n'


def main():
    if not __debug__:
        raise SystemExit("public release checks require Python assertions")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["native", "sanitize"], default="native")
    parser.add_argument("--engine", choices=ENGINES, action="append")
    parser.add_argument("--profile", choices=PROFILES, action="append")
    parser.add_argument("--optimization", choices=OPTIMIZATIONS, action="append")
    options = parser.parse_args()
    selected = {"engines": list(dict.fromkeys(options.engine or ENGINES)),
                "profiles": list(dict.fromkeys(options.profile or PROFILES)),
                "optimizations": list(dict.fromkeys(options.optimization or OPTIMIZATIONS))}
    project = Path(__file__).resolve().parents[1]
    runtime = project / "runtime"
    cc = os.environ.get("MINYAR_TEST_CLANG", "clang")
    output = project / ("build/public-release-" + options.mode)
    output.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="run-", dir=output))
    report_path = root / "results.json"
    # Match Makefile:NATIVE_SANITIZER_LEAKS; every host keeps the C heap oracles.
    environment = dict(os.environ,
                       ASAN_OPTIONS="detect_leaks=" + ("1" if sys.platform.startswith("linux") else "0")
                                    + ":halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    metadata = {"mode": options.mode, "selected": selected, "complete": False,
                "project": str(project), "artifacts": str(root), "compiler": cc,
                "timeouts_seconds": {"build": 120, "run": 30, "version": 10},
                "sanitizer_environment": {key: environment[key]
                                          for key in ("ASAN_OPTIONS", "UBSAN_OPTIONS")},
                "sources_sha256": {}, "commands": [], "results": []}

    def save():
        report_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    def run(command, label, timeout):
        row = {"label": label, "command": command, "timeout_seconds": timeout,
               "exit": None, "stdout": "", "stderr": ""}
        started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=project, env=environment,
                                       text=True, capture_output=True, timeout=timeout)
            row.update(exit=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
        except subprocess.TimeoutExpired as error:
            def decoded(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
            row.update(timed_out=True, stdout=decoded(error.stdout), stderr=decoded(error.stderr))
            raise
        except OSError as error:
            row["error"] = str(error)
            raise
        finally:
            row["elapsed_seconds"] = time.monotonic() - started
            (root / (label + ".stdout")).write_text(row["stdout"])
            (root / (label + ".stderr")).write_text(row["stderr"])
            metadata["commands"].append(row)
            save()
        return row

    print("Public release artifacts: " + str(root), flush=True)
    save()
    try:
        sources = [Path(__file__).resolve(), project / "tests/public-release-runtime.c",
                   project / "tools/test-runtime.min", runtime / "minyar_runtime.c"]
        sources += sorted(runtime.glob("minyar_*.h"))
        metadata["sources_sha256"] = {str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
                                      for path in sources}
        version = run([cc, "--version"], "clang-version", 10)
        assert version["exit"] == 0, version
        for name in selected["engines"]:
            engine = runtime / "minyar_runtime.c"
            if name == "cycle":
                engine = root / "cycle-engine.c"
                engine.write_text(cycle_source((runtime / "minyar_runtime.c").read_text()))
                metadata["cycle_source_sha256"] = hashlib.sha256(engine.read_bytes()).hexdigest()
            for profile in selected["profiles"]:
                flags = []
                expected = SUCCESS
                if profile != "eager":
                    backend, budget = profile.split("-k")
                    flags += ["-DMINYAR_" + ("SYSTEM" if backend == "system" else "BOUNDED") + "_HEAP=1",
                              "-DMINYAR_RC_POLL_BUDGET=" + budget]
                    expected = TRANSCRIPTS[budget]
                if options.mode == "sanitize":
                    flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
                for optimization in selected["optimizations"]:
                    label = name + "-" + profile + "-O" + optimization
                    executable = root / (label + ".exe")
                    dependencies = root / (label + ".d")
                    command = [cc, "-std=c11", "-O" + optimization, "-g", "-Wall", "-Wextra", "-Werror",
                               *flags, "-UNDEBUG", "-iquote", str(runtime),
                               '-DMINYAR_PUBLIC_RELEASE_ENGINE="' + str(engine) + '"',
                               "-MMD", "-MF", str(dependencies),
                               str(project / "tests/public-release-runtime.c"),
                               "-pthread", "-lm", "-o", str(executable)]
                    built = run(command, label + ".build", 120)
                    assert built["exit"] == 0, built
                    selected_header = runtime / ("minyar_cycle_rc.h" if name == "cycle" else "minyar_rc.h")
                    dependency_text = dependencies.read_text().replace("\\\n", "").replace("\\ ", " ")
                    assert str(selected_header) in dependency_text, (label, selected_header, dependency_text)
                    observed = run([str(executable)], label, 30)
                    assert observed["exit"] == 0, observed
                    assert observed["stdout"] == expected and observed["stderr"] == "", observed
                    metadata["results"].append({"label": label, "passed": True,
                                                "selected_header": str(selected_header),
                                                "expected_stdout": expected})
                    save()
                    print(label + ": passed", flush=True)
        metadata["complete"] = True
        print("Public release " + options.mode + ": all selected profiles passed", flush=True)
    except BaseException as error:
        metadata["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
