#!/usr/bin/env python3
"""Where one plain `minyar run --watch` rebuild spends its time.

Builds benchmarks/livepatch/server once, edits its reply text, then runs the
same rebuild the watcher runs per edit (`project-cli build`) under
`strace -f -e trace=execve` and prints each program it started, with its start
offset and lifetime, plus the total. Linux only. Usage: timeline.py [rounds]
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path.cwd()
TOOL = ROOT / "build/tooling/tools/project-cli"


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    environment = dict(os.environ, MINYAR_PROJECT_DIR=str(ROOT))
    with tempfile.TemporaryDirectory(prefix="editloop-timeline-", dir="/var/tmp") as temporary:
        project = Path(temporary) / "server"
        (project / "src").mkdir(parents=True)
        shutil.copy(ROOT / "benchmarks/livepatch/server/Minyar.toml", project / "Minyar.toml")
        source = project / "src/main.min"
        shutil.copy(ROOT / "benchmarks/livepatch/server/src/main.min", source)
        build = [str(TOOL), "build", "--manifest-path", str(project)]
        subprocess.run(build, check=True, env=environment, capture_output=True)
        for round in range(rounds):
            text = source.read_text()
            source.write_text(text.replace('"version=' + str(round + 1) + ' served="', '"version=' + str(round + 2) + ' served="'))
            trace = Path(temporary) / ("trace-" + str(round))
            started = time.monotonic()
            subprocess.run(["strace", "-f", "-ttt", "-e", "trace=execve", "-e", "signal=none", "-s", "160", "-o", str(trace)] + build,
                           check=True, env=environment, capture_output=True)
            total = time.monotonic() - started
            plain = time.monotonic()
            source.write_text(source.read_text().replace('"version=' + str(round + 2) + ' served="', '"version=' + str(round + 3) + ' served="'))
            subprocess.run(build, check=True, env=environment, capture_output=True)
            untraced = time.monotonic() - plain
            source.write_text(source.read_text().replace('"version=' + str(round + 3) + ' served="', '"version=' + str(round + 2) + ' served="'))
            starts, ends, names = {}, {}, {}
            for line in trace.read_text().splitlines():
                match = re.match(r"(\d+) +([\d.]+) (.*)", line)
                if not match:
                    continue
                pid, stamp, rest = int(match.group(1)), float(match.group(2)), match.group(3)
                if rest.startswith("execve(") and "= -1" not in rest:
                    names[pid] = rest.split('"')[1]
                    arguments = re.findall(r'"((?:[^"\\]|\\.)*)"', rest.split("], ", 1)[0])
                    names[pid] = " ".join([arguments[0]] + arguments[2:])
                    starts[pid] = stamp
                elif "+++ exited" in rest:
                    ends[pid] = stamp
            if os.environ.get("TIMELINE_RAW"):
                print(trace.read_text()[:3000])
            first = min(starts.values())
            print("round", round + 1, "traced %.3f s, untraced %.3f s" % (total, untraced))
            for pid in sorted(starts, key=starts.get):
                lifetime = ends.get(pid, starts[pid]) - starts[pid]
                if lifetime >= 0.01:
                    print("  +%.3f %.3f s %s" % (starts[pid] - first, lifetime, names[pid].replace(str(ROOT), "$ROOT")))


if __name__ == "__main__":
    main()
