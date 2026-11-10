#!/usr/bin/env python3
"""garden: report the upkeep this repository needs, in one fast pass that needs no build.

Each section prints findings as `path:line: message` and a count; the last line is a one-row summary so runs
can be compared. Sections (docs/garden.md explains each and what to do about it):

  docs       docs naming Make targets, repository paths or launcher commands that do not exist
  unused     tracked tools/scripts nothing refers to, and Make targets nothing runs
  size       tracked files over the size limit and source files over the line limit
  leftovers  tracked agent artefacts: logs, backups, scratch files, dated notes outside docs/records
  local      ignored files at the top of this working tree (old saves, notes, scratch output)
  todos      TODO/FIXME markers, and dated ones `TODO(YYYY-MM-DD)` past their date
  checks     slowest checks (build/tooling/check-durations), checks CI lists as known failures
             (tools/ci-known-failures.txt), and checks that both passed and failed or timed out in the
             check-runner logs given with --check-log
  deps       pinned toolchain and vendored versions with their age; --online compares upstream tags

`make garden` and `./minyar dev garden` run it. It only reads the tree, except --online, which runs
`git ls-remote` against the public upstream repositories named in the pins.
"""
import argparse
import collections
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.date.today()

# Size limits: a tracked file over BIG_BYTES, or a source file over LONG_LINES lines, is reported.
BIG_BYTES = 2 * 1024 * 1024
LONG_LINES = 8000
SOURCE_SUFFIXES = {".min", ".c", ".h", ".py", ".sh", ".mk", ".mjs", ".swift", ".rs", ".go"}
# Large data that is deliberately tracked (pinned upstream data and recorded study evidence). Keep this list
# short; anything added here should say why in docs/garden.md.
BIG_ALLOWED = ("vendor/", "tests/fixtures/unicode-")
# Places that are records rather than live instructions: their drift is not reported.
HISTORICAL_DOCS = ("docs/records/", "docs/research/", "experiments/", "tests/", "vendor/", "benchmarks/results")
# Known, deliberate exceptions: `<section> <where-prefix> <text in the message>`, one per line, each with a
# `# reason`. Prefer fixing the finding; add a line only when the finding is about another repository or a
# generated project.
ALLOW_FILE = ROOT / "tools" / "garden-allow.txt"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


def tracked():
    return [p for p in git("ls-files", "-z").split("\0") if p]


def is_text(path, limit=BIG_BYTES):
    try:
        if os.path.getsize(path) > limit:
            return False
        with open(path, "rb") as handle:
            return b"\0" not in handle.read(8192)
    except OSError:
        return False


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


class Report:
    def __init__(self, limit):
        self.limit = limit
        self.sections = collections.OrderedDict()
        self.allowed = []
        if ALLOW_FILE.exists():
            for line in read(ALLOW_FILE).splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    section, where, text = (line.split(None, 2) + ["", ""])[:3]
                    self.allowed.append((section, where, text))

    def add(self, section, where, message):
        if any(section == s and where.startswith(w) and t in message for s, w, t in self.allowed):
            return
        self.sections.setdefault(section, []).append((where, message))

    def ensure(self, section):
        self.sections.setdefault(section, [])

    def render(self, out):
        for name, items in self.sections.items():
            out.write(f"== {name}: {len(items)}\n")
            for where, message in items[: self.limit]:
                out.write(f"  {where}: {message}\n" if where else f"  {message}\n")
            if len(items) > self.limit:
                out.write(f"  ... {len(items) - self.limit} more (--limit 0 shows all)\n")
        out.write("garden summary: " + " ".join(f"{k}={len(v)}" for k, v in self.sections.items()) + "\n")


# ---------------------------------------------------------------- Make database

def make_targets():
    """Return (targets, prerequisite names) from Make's own database, so generated rules count too."""
    result = subprocess.run(["make", "-pRrq", "-f", "Makefile", "__garden_no_such_target__"], cwd=ROOT,
                            capture_output=True, text=True)
    targets, prerequisites = set(), set()
    skip = False
    for line in result.stdout.splitlines():
        if line.startswith("# Not a target"):
            skip = True
            continue
        if not line or line.startswith(("#", "\t")) or "=" in line.split(":", 1)[0]:
            continue
        match = re.match(r"^([^\s:#=][^:=]*?):{1,2}(?!=)(.*)$", line)
        if not match:
            continue
        if skip:
            skip = False
            continue
        names = match.group(1).split()
        rest = match.group(2).split("|")[0].split(";")[0]
        if all(name.startswith(".") for name in names):
            continue  # .PHONY, .NOTPARALLEL and other special targets are not dependencies
        for name in names:
            targets.add(name)
        for name in rest.split():
            prerequisites.add(name)
    return targets, prerequisites


# ---------------------------------------------------------------- corpus

TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*")


class Corpus:
    """Token → files index over every tracked text file, for 'does anything mention X' questions."""

    def __init__(self, files):
        self.where = collections.defaultdict(set)
        self.text = {}
        for path in files:
            full = ROOT / path
            if not is_text(full):
                continue
            body = read(full)
            self.text[path] = body
            for token in set(TOKEN.findall(body)):
                self.where[token].add(path)
                stripped = token.rstrip(".")
                if stripped != token:
                    self.where[stripped].add(path)

    def mentions(self, token, exclude=()):
        return {p for p in self.where.get(token, ()) if p not in exclude}


# ---------------------------------------------------------------- docs

CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
PATHLIKE = re.compile(r"^(?:\./)?([a-z][\w.-]*/[\w./+-]*[\w+-])/?$")


def doc_files(files):
    for path in files:
        if not path.endswith(".md") or path.startswith(HISTORICAL_DOCS):
            continue
        if path.count("/") == 0 or path.startswith("docs/") or path.endswith("README.md"):
            yield path


def launcher_words():
    body = read(ROOT / "minyar")
    words = set(re.findall(r"^\s{4}([a-z][a-z-]*)\)", body, re.M))
    words |= set(re.findall(r"(--[a-z][a-z0-9-]*)", body))
    return words


def code_fragments(body):
    """Yield (line number, code text) for inline code spans and fenced block lines."""
    fence = False
    for number, line in enumerate(body.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            yield number, line, True
        else:
            for span in CODE_SPAN.findall(line):
                yield number, span, False
            for link in LINK.findall(line):
                yield number, "\0link\0" + link, False


def check_docs(report, files, targets):
    exists = set(files)
    directories = {str(Path(p).parent) for p in files}
    for p in list(directories):
        while p not in ("", "."):
            p = str(Path(p).parent)
            directories.add(p)
    tops = {p.split("/", 1)[0] for p in files if "/" in p}
    launcher = launcher_words()
    for doc in doc_files(files):
        body = read(ROOT / doc)
        for number, fragment, fenced in code_fragments(body):
            where = f"{doc}:{number}"
            if fragment.startswith("\0link\0"):
                link = fragment[6:].split("#", 1)[0]
                if not link or re.match(r"^[a-z]+:", link) or link.startswith("/"):
                    continue
                resolved = os.path.normpath(os.path.join(os.path.dirname(doc), link))
                if resolved.startswith("build/") or resolved.startswith(".."):
                    continue
                if resolved not in exists and resolved not in directories:
                    report.add("docs", where, f"link to missing file {link}")
                continue
            # make TARGET... in command position; `make -C dir` names another Makefile's targets
            command_text = re.sub(r"\s#.*$", "", fragment) if fenced else fragment
            for command in re.split(r"&&|\|\||;|\|", command_text):
                try:
                    words = shlex.split(command)
                except ValueError:
                    words = command.split()
                while words and (words[0] in ("$", "sudo", "env", "time") or re.match(r"^[A-Z_][A-Z0-9_]*=", words[0])
                                 or words[0].endswith("/heavy")):
                    words = words[1:]
                if not words or words[0] != "make" or "-C" in words or "-f" in words:
                    continue
                for word in words[1:]:
                    if word.startswith("-") or "=" in word or any(ch in word for ch in "$<>*`'\"("):
                        continue
                    # an upper-case word is a placeholder such as check-NAME
                    if re.match(r"^[a-z][a-z0-9_.-]*$", word) and word not in targets:
                        report.add("docs", where, f"`make {word}`: no such Make target")
            # a bare check-* / measure-* name in a code span
            if not fenced and re.fullmatch(r"(check|measure)-[a-z0-9][a-z0-9-]*", fragment) and fragment not in targets:
                report.add("docs", where, f"`{fragment}`: no such Make target")
            # ./minyar SUBCOMMAND / --flag
            for word in re.findall(r"(?:^|\s)(?:\./)?minyar\s+([a-z-][a-z0-9-]*)", fragment):
                if word.startswith("--") and word not in launcher and not any_mentions_flag(word):
                    report.add("docs", where, f"`minyar {word}`: flag appears nowhere in the sources")
            # repository paths
            for token in re.split(r"[\s,;:()'\"=]+", fragment):
                match = PATHLIKE.match(token)
                if not match:
                    continue
                path = match.group(1).rstrip(".")
                top = path.split("/", 1)[0]
                if top not in tops or any(ch in token for ch in "*<>{}$%") or "/target/" in path:
                    continue
                if re.search(r"(^|/)(N{3,}|X{3,}|YYYY)|/[A-Z]+/?$", path):
                    continue  # placeholders such as NNNN-name.json or VERSION
                local = os.path.normpath(os.path.join(os.path.dirname(doc), path))
                if path in exists or path in directories or local in exists or local in directories:
                    continue
                # build outputs and globs named by stem are fine when a source exists with a suffix
                if any((path + suffix) in exists for suffix in (".min", ".c", ".py", ".sh", ".mk", ".md")):
                    continue
                report.add("docs", where, f"names {path}, which does not exist")


_FLAG_CACHE = {}


def any_mentions_flag(flag):
    if flag not in _FLAG_CACHE:
        found = subprocess.run(["git", "-C", str(ROOT), "grep", "-q", "-F", "--", flag, "--", "compiler", "tools",
                                "minyar", "runtime"], capture_output=True).returncode == 0
        _FLAG_CACHE[flag] = found
    return _FLAG_CACHE[flag]


# ---------------------------------------------------------------- unused

UNUSED_DIRS = ("tools/", "scripts/", "build-support/", "install/")


def check_unused(report, files, corpus, targets, prerequisites):
    for path in files:
        if not path.startswith(UNUSED_DIRS) or path.count("/") != 1:
            continue
        name = path.rsplit("/", 1)[1]
        if name.startswith(".") or name.endswith(".md") or path.endswith(".mk"):
            continue  # every build-support/*.mk is included by the Makefile wildcard
        users = corpus.mentions(name, exclude={path})
        stem = name.rsplit(".", 1)[0]
        # tools built by Make are named by their output path build/tooling/<dir>/<stem>
        built = corpus.mentions(stem, exclude={path}) if name.endswith(".min") else set()
        code_users = {u for u in users | built if not u.endswith(".md")}
        if not users and not built:
            report.add("unused", path, "nothing in the repository mentions this file")
        elif not code_users:
            report.add("unused", path, "mentioned only in docs (" + ", ".join(sorted(users | built)[:3]) + ")")
    # Make targets that no rule depends on, no recipe or variable runs, and no doc or CI file names.
    mk_mentions = collections.Counter()
    for path, body in corpus.text.items():
        if not (path.endswith(".mk") or path == "Makefile"):
            continue
        for line in body.splitlines():
            if line.startswith(".PHONY"):
                continue
            header = re.match(r"^([^\s:#=][^:=]*?):(?!=)", line)
            text = line[header.end():] if header else line
            for token in set(TOKEN.findall(text)):
                mk_mentions[token] += 1
    for target in sorted(targets):
        if any(ch in target for ch in "/%$.") or target.startswith("."):
            continue
        if target in prerequisites or mk_mentions[target]:
            continue
        outside = {p for p in corpus.where.get(target, ()) if not (p.endswith(".mk") or p == "Makefile")}
        if not outside:
            report.add("unused", f"make {target}", "no rule, recipe, doc, script or workflow refers to this target")


# ---------------------------------------------------------------- size

def check_size(report, files):
    for path in files:
        full = ROOT / path
        try:
            size = full.stat().st_size
        except OSError:
            continue
        if size > BIG_BYTES and not path.startswith(BIG_ALLOWED):
            report.add("size", path, f"{size / 1048576:.1f} MiB tracked")
        elif Path(path).suffix in SOURCE_SUFFIXES and size > 200_000 and is_text(full):
            body = read(full)
            lines = body.count("\n")
            if lines > LONG_LINES and "DO NOT EDIT" not in body[:400]:  # generated sources are exempt
                report.add("size", path, f"{lines} lines")


# ---------------------------------------------------------------- leftovers

LEFTOVER = re.compile(r"(\.(log|orig|rej|bak|swp|tmp|out)$|~$|(^|/)nohup\.out$|-before(\.|-|$)|(^|/)scratch[-/]|"
                      r"(^|/)(core|a\.out)$|\.DS_Store$)")
DATED = re.compile(r"(^|[-_/])20\d\d-\d\d-\d\d([-_.]|$)")
LEFTOVER_ALLOWED = ("tests/", "vendor/", "docs/records/")  # records keep their evidence


def check_leftovers(report, files):
    for path in files:
        if path.startswith(LEFTOVER_ALLOWED):
            continue
        if LEFTOVER.search(path):
            report.add("leftovers", path, "looks like a log, backup or scratch file")
        elif DATED.search(path) and path.endswith(".md") and not path.startswith(("docs/records/", "docs/research/")):
            report.add("leftovers", path, "dated document outside docs/records/: move it there or make it current")


LOCAL_CACHES = re.compile(r"(^|/)(\.DS_Store|__pycache__/|\.ruff_cache/|\.pytest_cache/|node_modules/|\.venv/)$")


def check_local(report):
    """Ignored files in this working tree outside build/: what a fresh agent trips over."""
    for line in git("status", "--porcelain", "--ignored", "--", ".").splitlines():
        code, path = line[:2], line[3:]
        if code != "!!" or path.startswith(("build/", "target/")) or LOCAL_CACHES.search(path):
            continue
        full = ROOT / path
        size = sum(f.stat().st_size for f in full.rglob("*") if f.is_file()) if full.is_dir() else full.stat().st_size
        report.add("local", path, f"ignored, {size / 1048576:.1f} MiB: move it out of the checkout or delete it")


# ---------------------------------------------------------------- todos

# A marker is one of the words, then optionally a date or owner in parentheses, then a colon.
TODO = re.compile(r"\b(TODO|FIXME|XXX|HACK)(?:\(([^)]*)\))?:")
TODO_DIRS = ("compiler/", "runtime/", "library/", "tools/", "scripts/", "build-support/", "bootstrap/", "os/",
             "install/", "minyar", "Makefile", "docs/")


def check_todos(report, corpus):
    for path, body in sorted(corpus.text.items()):
        if not path.startswith(TODO_DIRS) or path.startswith("docs/research/"):
            continue
        prose = path.endswith(".md")
        for number, line in enumerate(body.splitlines(), 1):
            if prose:
                line = CODE_SPAN.sub("", line)  # a doc may quote a marker
            for match in TODO.finditer(line):
                when = match.group(2) or ""
                if re.fullmatch(r"\d{4}-\d\d-\d\d", when):
                    due = datetime.date.fromisoformat(when)
                    if due < TODAY:
                        report.add("todos", f"{path}:{number}", f"{match.group(1)} past its date {when}")
                else:
                    report.add("todos", f"{path}:{number}", f"undated {match.group(1)}: give it a date or an issue")


# ---------------------------------------------------------------- checks

RESULT = re.compile(r"^(?:prerequisite )?(\S+): (passed|failed|skipped)\b.*?wall_ms=(\d+).*?timeout=(\w+)")


def check_checks(report, logs, slowest, history):
    report.ensure("checks")
    walls = collections.defaultdict(list)
    outcomes = collections.defaultdict(set)
    for log in logs:
        for line in read(log).splitlines():
            match = RESULT.match(line)
            if match:
                label, outcome, wall, timeout = match.groups()
                outcomes[label].add("timeout" if timeout == "true" else outcome)
                if not line.startswith("prerequisite "):
                    walls[label].append(int(wall))
    rows = []
    if history.exists():
        source = str(history.relative_to(ROOT)) if history.is_relative_to(ROOT) else str(history)
        for line in read(history).splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[1].isdigit():
                rows.append((int(fields[1]), fields[0]))
    else:
        source = f"{len(logs)} log(s)"
        rows = [(sorted(values)[len(values) // 2], label) for label, values in walls.items()]
    rows.sort(reverse=True)
    total = sum(r[0] for r in rows)
    for wall, label in rows[:slowest]:
        share = 100.0 * wall / total if total else 0
        report.add("checks", label, f"slow: {wall / 1000:.0f}s wall, {share:.1f}% of all check time in {source}")
    known = ROOT / "tools" / "ci-known-failures.txt"
    if known.exists():
        for number, line in enumerate(read(known).splitlines(), 1):
            name, _, cause = line.partition("#")
            if name.strip():
                report.add("checks", f"tools/ci-known-failures.txt:{number}",
                           f"{name.strip()} fails in CI: {cause.strip()}")
    for label, seen in sorted(outcomes.items()):
        if "timeout" in seen:
            report.add("checks", label, "timed out (" + ", ".join(sorted(seen)) + " across the logs)")
        elif {"passed", "failed"} <= seen:
            report.add("checks", label, "both passed and failed across the logs: flaky unless the trees differ")


# ---------------------------------------------------------------- deps

def pins():
    """(name, version, upstream git URL, file that pins it)."""
    found = []
    toolchain = read(ROOT / "tools" / "toolchain.sh")
    match = re.search(r"^llvm_version=(\S+)", toolchain, re.M)
    if match:
        found.append(("llvm", match.group(1), "https://github.com/llvm/llvm-project.git", "tools/toolchain.sh"))
    readme = read(ROOT / "vendor" / "README.md")
    for name, pattern, url in (
        ("stb_ds", r"`stb_ds\.h` (\S+)", "https://github.com/nothings/stb.git"),
        ("monocypher", r"Monocypher (\d[\d.]+\d)", "https://github.com/LoupVaillant/Monocypher.git"),
        ("utf8proc", r"utf8proc (\d[\d.]+\d)", "https://github.com/JuliaStrings/utf8proc.git"),
        ("protobuf", r"Protocol Buffers (\d[\d.]+\d)", "https://github.com/protocolbuffers/protobuf.git"),
    ):
        match = re.search(pattern, readme)
        if match:
            found.append((name, match.group(1), url, "vendor/README.md"))
    swift = ROOT / "toolchains" / "native-swift" / "sources.json"
    if swift.exists():
        tag = json.loads(read(swift)).get("tag", "")
        found.append(("swift", tag.replace("swift-", "").replace("-RELEASE", ""),
                      "https://github.com/swiftlang/swift.git", "toolchains/native-swift/sources.json"))
    return found


def version_key(text):
    return tuple(int(part) for part in re.findall(r"\d+", text)[:4])


def latest_tag(url, name):
    try:
        out = subprocess.run(["git", "ls-remote", "--tags", "--refs", url], capture_output=True, text=True,
                             timeout=60).stdout
    except (subprocess.TimeoutExpired, OSError):
        return None
    tags = []
    for line in out.splitlines():
        tag = line.rsplit("/", 1)[-1]
        if re.search(r"(rc|beta|alpha|dev|snapshot|init|DEVELOPMENT)", tag, re.I):
            continue
        if name == "llvm" and not tag.startswith("llvmorg-"):
            continue
        if name == "swift" and not re.fullmatch(r"swift-[\d.]+-RELEASE", tag):
            continue
        if name == "protobuf" and not re.fullmatch(r"v\d+\.\d+(\.\d+)?", tag):
            continue
        if re.search(r"\d", tag):
            tags.append(tag)
    return max(tags, key=version_key) if tags else None


def check_deps(report, online):
    for name, version, url, source in pins():
        log = git("log", "-1", "--format=%cs", "--", source).strip()
        age = (TODAY - datetime.date.fromisoformat(log)).days if log else -1
        message = f"{name} {version} (pinning file last changed {age} days ago)"
        if online:
            latest = latest_tag(url, name)
            if latest and version_key(latest) > version_key(version):
                message += f"; upstream has {latest}"
            elif latest:
                message += "; current"
        report.add("deps", source, message)


# ---------------------------------------------------------------- main

SECTIONS = ("docs", "unused", "size", "leftovers", "local", "todos", "checks", "deps")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sections", nargs="*", help="sections to run (default: all): " + ", ".join(SECTIONS))
    parser.add_argument("--root", help="checkout to inspect (default: the one containing this script)")
    parser.add_argument("--limit", type=int, default=30, help="findings shown per section; 0 shows all")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--online", action="store_true", help="compare pins with upstream tags (git ls-remote)")
    parser.add_argument("--check-log", action="append", default=[], help="check-runner log to scan for flaky checks")
    parser.add_argument("--fail-on", default="", metavar="SECTIONS",
                        help="comma-separated sections whose findings make the exit status 1 (for checks and CI)")
    parser.add_argument("--slowest", type=int, default=10, help="slowest recorded checks to list")
    parser.add_argument("--durations", help="check-in-parallel duration history (default: build/tooling/check-durations)")
    args = parser.parse_args()
    global ROOT, ALLOW_FILE
    if args.root:
        ROOT = Path(args.root).resolve()
        ALLOW_FILE = ROOT / "tools" / "garden-allow.txt"
    unknown = [s for s in args.sections + [f for f in args.fail_on.split(",") if f] if s not in SECTIONS]
    if unknown:
        parser.error("unknown section(s): " + ", ".join(unknown))
    wanted = args.sections or list(SECTIONS)
    report = Report(args.limit if args.limit > 0 else sys.maxsize)
    files = tracked()
    corpus = Corpus(files) if {"unused", "todos"} & set(wanted) else None
    targets = prerequisites = None
    if {"docs", "unused"} & set(wanted):
        targets, prerequisites = make_targets()
    for section in wanted:
        report.ensure(section)
        if section == "docs":
            check_docs(report, files, targets)
        elif section == "unused":
            check_unused(report, files, corpus, targets, prerequisites)
        elif section == "size":
            check_size(report, files)
        elif section == "leftovers":
            check_leftovers(report, files)
        elif section == "local":
            check_local(report)
        elif section == "todos":
            check_todos(report, corpus)
        elif section == "checks":
            check_checks(report, args.check_log, args.slowest,
                         Path(args.durations) if args.durations else ROOT / "build" / "tooling" / "check-durations")
        elif section == "deps":
            check_deps(report, args.online)
    if args.json:
        json.dump({k: [{"where": w, "message": m} for w, m in v] for k, v in report.sections.items()},
                  sys.stdout, indent=1)
        sys.stdout.write("\n")
    else:
        report.render(sys.stdout)
    failing = [name for name in args.fail_on.split(",") if name and report.sections.get(name)]
    if failing:
        sys.stderr.write("garden: findings in " + ", ".join(failing) + " (docs/garden.md says how to fix them)\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
