#!/usr/bin/env python3
"""Feed working-tree changes to the existing Minyar commit-check policy."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


def git_environment(root):
    environment = os.environ.copy()
    names = subprocess.run(["git", "rev-parse", "--local-env-vars"], cwd=root,
                           capture_output=True, check=True).stdout.decode().split()
    for name in names + ["GIT_PREFIX"]:
        environment.pop(name, None)
    return environment


def git(root, *arguments):
    result = subprocess.run(["git", "-C", str(root), *arguments], env=git_environment(root),
                            capture_output=True, check=True)
    return result.stdout


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    """Match the source copied to a build box; ignore generated build outputs."""
    entries = {}

    def visit(directory):
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            if relative in (".git", "build", "target") or path.name == "__pycache__" or path.suffix == ".pyc":
                continue
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"source symlinks require explicit checks: {relative}")
            elif stat.S_ISDIR(mode):
                visit(path)
            elif stat.S_ISREG(mode):
                hasher = hashlib.sha256()
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        hasher.update(chunk)
                entries[relative] = ["file", bool(mode & 0o111), hasher.hexdigest()]
            else:
                raise ValueError(f"unsupported source file: {relative}")

    visit(root)
    return entries


def capture(root, base, destination):
    # Resolve before writing anything. A bad base must never become an empty diff.
    tree = git(root, "rev-parse", "--verify", "--end-of-options", base + "^{tree}").decode().strip()
    changed = git(root, "diff", "--name-only", "--no-renames", "-z", tree, "--")
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    paths = sorted(set((changed + untracked).split(b"\0")) - {b""})
    # These directories are generated and intentionally absent from validation.
    if any(path.split(b"/", 1)[0] in (b"build", b"target") for path in paths):
        raise ValueError("changed source under build/ or target/ cannot be exported; move it to a source directory")
    before = inventory(root)
    previous = destination / "previous"
    previous.mkdir(parents=True)
    (previous / "library").mkdir()
    # Extract only regular Minyar module files. Git export-ignore attributes must
    # not hide an old import edge, so use the tree itself rather than git archive.
    listing = git(root, "ls-tree", "-rz", tree, "--", "library")
    objects = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        header, name = entry.split(b"\t", 1)
        mode, kind, object_id = header.split()
        if kind != b"blob" or not name.endswith(b".min"):
            continue
        if mode not in (b"100644", b"100755"):
            raise ValueError(f"unsupported previous module mode: {os.fsdecode(name)}")
        objects.append((name, object_id))
    if objects:
        contents = subprocess.run(
            ["git", "-C", str(root), "cat-file", "--batch"],
            env=git_environment(root),
            input=b"".join(object_id + b"\n" for _, object_id in objects),
            capture_output=True, check=True,
        ).stdout
        stream = io.BytesIO(contents)
        for name, object_id in objects:
            actual, kind, size = stream.readline().split()
            if actual != object_id or kind != b"blob":
                raise ValueError("could not read previous library module")
            data = stream.read(int(size))
            if len(data) != int(size) or stream.read(1) != b"\n":
                raise ValueError("incomplete previous library module")
            path = previous / os.fsdecode(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    changes = b"".join(path + b"\0" for path in paths)
    (destination / "changed-paths").write_bytes(changes)
    if inventory(root) != before:
        raise ValueError("source changed while exporting; export again")
    manifest = {"schema": 1, "base_tree": tree, "source": before,
                "changes_sha256": digest(changes), "previous": inventory(previous)}
    (destination / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    return len(paths)


def validate(root, inputs):
    manifest = json.loads((inputs / "manifest.json").read_text())
    if manifest.get("schema") != 1:
        raise ValueError("unsupported changed-check manifest schema")
    if inventory(root) != manifest["source"]:
        raise ValueError("source differs from the exported changes; run check-changed-export again")
    if digest((inputs / "changed-paths").read_bytes()) != manifest["changes_sha256"]:
        raise ValueError("exported changed paths were modified; export again")
    if inventory(inputs / "previous") != manifest["previous"]:
        raise ValueError("exported previous modules were modified; export again")


def check(root, inputs, plan, jobs):
    validate(root, inputs)
    environment = git_environment(root)
    # A recursive make must not inherit the parent's jobserver or target list.
    for name in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEFILES", "GNUMAKEFLAGS",
                 "MINYAR_TEST_COMPILER", "MINYAR_TEST_MODULE_COMPILER", "MINYAR_TEST_RUNTIME", "MINYAR_TEST_LINK_FLAGS"):
        environment.pop(name, None)
    environment.setdefault("MINYAR_INTERACTIVE_BOOTSTRAP", "1")
    environment["MINYAR_TEST_CLANG"] = environment.get("LLVM_CC") or subprocess.run(
        ["sh", "tools/toolchain.sh", "default-clang"], cwd=root, env=environment,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run(["make", "--no-print-directory", "-s", "build/tooling/tools/check-commit"],
                   cwd=root, env=environment, check=True)
    command = [str(root / "build/tooling/tools/check-commit"), "--root", str(root),
               "--previous", str(inputs / "previous"), "--changes", str(inputs / "changed-paths"),
               "--rules", str(root / "build-support/commit-checks.mk"), "--jobs", str(jobs)]
    if plan:
        command.append("--plan")
    result = subprocess.run(command, cwd=root, env=environment)
    validate(root, inputs)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.environ.get("CHECK_CHANGED_BASE", "HEAD"), help="compare current source with this Git tree (default HEAD)")
    parser.add_argument("--input", default=os.environ.get("CHECK_CHANGED_INPUT"), help="use exported inputs on a build box without Git")
    parser.add_argument("--export", dest="export", help="capture inputs without building; destination must be under target/")
    parser.add_argument("--plan", action="store_true", help="print selected checks without running them (builds the planner)")
    parser.add_argument("--jobs", type=int, default=2, choices=range(1, 17))
    arguments = parser.parse_args()
    if arguments.input and arguments.export:
        parser.error("--input and --export are mutually exclusive")
    root = Path(__file__).resolve().parent.parent
    try:
        if arguments.export:
            destination = Path(arguments.export).resolve()
            if root / "target" not in destination.parents:
                raise ValueError("export destination must be a new directory under target/")
            # Refuse to delete or reuse arbitrary user files; publish a new capture.
            destination.mkdir(parents=True, exist_ok=False)
            count = capture(root, arguments.base, destination)
            print(f"Exported {count} changed paths to {destination}")
            return 0
        if arguments.input:
            return check(root, Path(arguments.input).resolve(), arguments.plan, arguments.jobs)
        with tempfile.TemporaryDirectory(prefix="minyar changed checks ") as temporary:
            inputs = Path(temporary)
            capture(root, arguments.base, inputs)
            return check(root, inputs, arguments.plan, arguments.jobs)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None)
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace").strip()
        print(f"check-changed: {detail or error}", file=sys.stderr)
        return getattr(error, "returncode", 1) or 1


if __name__ == "__main__":
    sys.exit(main())
