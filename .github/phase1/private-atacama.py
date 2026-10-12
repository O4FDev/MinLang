"""Run the frozen private downstream through the current public launcher.

Only encrypted evidence leaves the private workspace. This is CI orchestration,
not a replacement for the owning Makefile or any native qualification oracle.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

SECRET = "MINYAR_PHASE1_ATACAMA_AGE_KEY"
STAGES = {"input", "source", "make", "evidence", "qualification"}


class PrivateRun:
    def __init__(self):
        os.umask(0o077)
        self.status_fd = os.dup(1)
        os.set_inheritable(self.status_fd, False)
        self.workspace = Path(tempfile.mkdtemp(prefix="minyar-atacama-private-",
                                              dir=os.environ["RUNNER_TEMP"]))
        self.workspace.chmod(0o700)
        log = os.open(self.workspace / "helper.log", os.O_WRONLY | os.O_CREAT, 0o600)
        os.dup2(log, 1)
        os.dup2(log, 2)
        os.close(log)
        # No child, including age, receives the identity in its environment.
        self.identity = os.environ.pop(SECRET, "")
        allowed = {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
                   "SDKROOT", "DEVELOPER_DIR", "MACOSX_DEPLOYMENT_TARGET"}
        self.env = {k: v for k, v in os.environ.items() if k in allowed}
        self.env["GITHUB_ACTIONS"] = "true"
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.active = None
        self.receipt = {"commands": [], "python": sys.version, "result": 1}
        self.sha = ""

    def status(self, stage, passed):
        assert stage in STAGES
        value = {"stage": stage, "status": "passed" if passed else "failed",
                 "sha": self.sha if re.fullmatch(r"[0-9a-f]{40}", self.sha) else ""}
        os.write(self.status_fd, (json.dumps(value, sort_keys=True) + "\n").encode())

    def close_group(self, pid):
        # Close our own process group, including descendants that outlive Make.
        def stopped():
            # Darwin can return EPERM for a group containing only orphaned
            # zombies. Verify states; never treat a live group's EPERM as closed.
            state = subprocess.run(["ps", "-g", str(pid), "-o", "stat="],
                                   env=self.env, stdout=subprocess.PIPE,
                                   close_fds=True, timeout=2)
            states = state.stdout.split()
            return not states or all(s.startswith(b"Z") for s in states)

        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError:
            if stopped():
                return
            raise
        if self.active and self.active.pid == pid:
            try:
                self.active.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
        time.sleep(0.05)
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            if not stopped():
                raise

    def run(self, argv, *, cwd=None, output=None, required=True):
        record = {"argv": [str(x) for x in argv], "cwd": str(cwd or self.workspace)}
        self.receipt["commands"].append(record)
        print(json.dumps(record), flush=True)
        started = time.monotonic()
        child = subprocess.Popen(argv, cwd=cwd or self.workspace, env=self.env,
                                 stdout=subprocess.PIPE if output else None,
                                 close_fds=True, start_new_session=True)
        self.active = child
        record["pid"] = child.pid
        try:
            data, _ = child.communicate()
            record["returncode"] = child.returncode
            record["seconds"] = time.monotonic() - started
            if argv[0] == "make":
                self.receipt["make_result"] = child.returncode if child.returncode >= 0 else 128 - child.returncode
                self.receipt["result"] = self.receipt["make_result"]
            if output:
                Path(output).write_bytes(data)
            if required and child.returncode:
                raise RuntimeError("private command failed")
            return child.returncode
        finally:
            self.close_group(child.pid)
            child.wait()
            self.active = None

    def interrupted(self, signum, frame):
        self.receipt["signal"] = signum
        raise InterruptedError("qualification interrupted")

    def snapshot(self, source, bindings):
        actual = []
        for entry in bindings:
            path = source / entry["path"]
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("source type changed")
            actual.append({"path": entry["path"], "mode": stat.S_IMODE(info.st_mode),
                           "bytes": info.st_size, "sha256": digest(path)})
        if actual != bindings:
            raise ValueError("source bytes or modes changed")
        return actual

    def extract(self, archive, source, count):
        bindings = []
        with tarfile.open(archive, "r:") as tf:
            members = tf.getmembers()
            seen = set()
            for member in members:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or not path.parts or ".." in path.parts
                        or ".git" in path.parts or member.name in seen
                        or not (member.isdir() or member.isfile()) or member.mode & ~0o777):
                    raise ValueError("unsafe private archive")
                seen.add(member.name)
            if sum(m.isfile() for m in members) != count:
                raise ValueError("private file count mismatch")
            for member in members:
                path = source / member.name
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(member) as src, path.open("xb") as dest:
                    shutil.copyfileobj(src, dest)
                path.chmod(member.mode)
                bindings.append({"path": member.name, "mode": member.mode,
                                 "bytes": member.size, "sha256": digest(path)})
        self.snapshot(source, bindings)
        return bindings

    def qualify(self, args, meta):
        if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
            raise ValueError("invalid candidate SHA")
        self.sha = args.sha
        if (Path(args.input).stat().st_size != meta["ciphertext_bytes"]
                or digest(args.input) != meta["ciphertext_sha256"]):
            raise ValueError("ciphertext binding mismatch")
        if not self.identity:
            raise ValueError("required private input key missing")
        key = self.workspace / "identity.txt"
        zipped = self.workspace / "input.tar.gz"
        try:
            key.write_text(self.identity)
            key.chmod(0o600)
            self.identity = ""
            self.run(["age", "--decrypt", "--identity", str(key),
                      "--output", str(zipped), str(Path(args.input).resolve())])
        finally:
            self.identity = ""
            key.unlink(missing_ok=True)
        expected_size = meta["source_archive_bytes"]
        if not 0 < expected_size <= 64 * 1024 * 1024:
            raise ValueError("invalid private archive size")
        archive = self.workspace / "input.tar"
        with gzip.open(zipped, "rb") as src:
            data = src.read(expected_size + 1)
        if len(data) != expected_size or hashlib.sha256(data).hexdigest() != meta["source_archive_sha256"]:
            raise ValueError("original archive binding mismatch")
        archive.write_bytes(data)
        source = self.workspace / "downstream"
        source.mkdir(mode=0o700)
        bindings = self.extract(archive, source, meta["source_files"])
        (self.workspace / "private-source-bindings.json").write_text(json.dumps(bindings, indent=2))
        self.receipt["input"] = meta
        self.status("input", True)

        candidate = self.workspace / "candidate"
        self.run(["git", "clone", "--no-hardlinks", "--no-checkout",
                  str(Path(args.repository).resolve()), str(candidate)])
        candidate.chmod(0o700)
        self.run(["git", "checkout", "--detach", args.sha], cwd=candidate)
        head = self.workspace / "candidate-head.txt"
        tree = self.workspace / "candidate-tree.txt"
        clean = self.workspace / "candidate-before.txt"
        self.run(["git", "rev-parse", "HEAD"], cwd=candidate, output=head)
        self.run(["git", "rev-parse", "HEAD^{tree}"], cwd=candidate, output=tree)
        self.run(["git", "status", "--porcelain"], cwd=candidate, output=clean)
        if head.read_text().strip() != args.sha or clean.read_bytes():
            raise ValueError("candidate source mismatch or dirty checkout")
        self.receipt["candidate"] = {"commit": args.sha, "tree": tree.read_text().strip(),
                                     "clean_before": True}
        self.status("source", True)
        # Actual native tools and ordinary bootstrap/link output remain private.
        for argv in (["age", "--version"], ["clang", "--version"],
                     ["xcrun", "--show-sdk-path"]):
            self.run(argv, required=False)
        result = self.run(["make", "MINYAR=" + str(candidate / "minyar"),
                           "MINYAR_PYTHON=" + sys.executable, "check", "test", "all"],
                          cwd=source, required=False)
        self.receipt["result"] = result if result >= 0 else 128 - result
        self.snapshot(source, bindings)
        after = self.workspace / "candidate-after.txt"
        self.run(["git", "status", "--porcelain"], cwd=candidate, output=after)
        if after.read_bytes():
            raise ValueError("candidate changed during qualification")
        self.receipt["candidate"]["clean_after"] = True
        artifacts = []
        for label, root in (("candidate-build", candidate / "build"), ("downstream-build", source / "build")):
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_symlink() or not path.is_file():
                    continue
                artifacts.append({"path": label + "/" + str(path.relative_to(root)),
                                  "bytes": path.stat().st_size, "sha256": digest(path),
                                  "mode": stat.S_IMODE(path.stat().st_mode)})
                with path.open("rb") as src:
                    magic = src.read(4)
                if magic in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
                    self.run(["otool", "-hv", str(path)])
                    self.run(["otool", "-L", str(path)])
        self.receipt["native_artifacts"] = artifacts
        self.status("make", result == 0)
        return self.receipt["result"]

    def encrypt(self, meta, output):
        # The identity is never needed for evidence encryption or included in it.
        (self.workspace / "identity.txt").unlink(missing_ok=True)
        self.identity = ""
        (self.workspace / "receipt.json").write_text(json.dumps(self.receipt, indent=2))
        evidence = self.workspace / "evidence.tar.gz"
        with tarfile.open(evidence, "w:gz") as tf:
            for path in sorted(self.workspace.iterdir()):
                if path.name in {"evidence.tar.gz", "evidence.age", "input.tar", "input.tar.gz", "identity.txt"}:
                    continue
                if path.name == "candidate":
                    # Public source need not be duplicated; retain actual native
                    # compiler/runtime stamps, objects and private program output.
                    if (path / "build").exists():
                        tf.add(path / "build", arcname="candidate-build")
                else:
                    tf.add(path, arcname=path.name)
        cipher = self.workspace / "evidence.age"
        self.run(["age", "--encrypt", "--recipient", meta["public_recipient"],
                  "--output", str(cipher), str(evidence)])
        if not cipher.is_file() or not cipher.stat().st_size:
            raise ValueError("evidence encryption produced no ciphertext")
        os.replace(cipher, output)
        self.status("evidence", True)


def digest(path):
    with open(path, "rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def main():
    # Redirect before parsing arguments, loading metadata, decoding or exceptions.
    private = PrivateRun()
    result, meta, output = 1, None, None
    try:
        parser = argparse.ArgumentParser()
        for name in ("repository", "sha", "input", "metadata", "evidence"):
            parser.add_argument("--" + name, required=True)
        args = parser.parse_args()
        output = Path(args.evidence).resolve()
        output.unlink(missing_ok=True)  # Never upload a stale artifact on failure.
        meta = json.loads(Path(args.metadata).read_text())
        if not re.fullmatch(r"age1[0-9a-z]+", meta["public_recipient"]):
            raise ValueError("invalid evidence recipient")
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, private.interrupted)
        result = private.qualify(args, meta)
    except BaseException as exc:
        private.receipt["failure_type"] = type(exc).__name__
        private.receipt["failure"] = str(exc)
        private.status("qualification", False)
        result = private.receipt["result"] or 1
        if isinstance(exc, InterruptedError) and not private.receipt.get("make_result"):
            result = 128 + private.receipt.get("signal", signal.SIGTERM)
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, signal.SIG_IGN)
        if private.active:
            private.close_group(private.active.pid)
        private.receipt["result"] = result
        try:
            if meta is None or output is None:
                raise ValueError("no validated evidence destination")
            private.encrypt(meta, output)
        except BaseException:
            private.status("evidence", False)
            result = result or 1
        private.status("qualification", result == 0)
        shutil.rmtree(private.workspace)
        os.close(private.status_fd)
    return result


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:
        # Initialization/cleanup failure still cannot print private exceptions.
        os.write(1, b'{"stage":"qualification","status":"failed","sha":""}\n')
        code = 1
    raise SystemExit(code)
