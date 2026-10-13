"""Bounded CI orchestration checks; never compile or qualify a product."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
HELPER = HERE / "private-atacama.py"
BASE_WORKFLOW_SHA = "5f1437b7c0b74592051d775601617fa050e72e80c8b097eb4b748e27b28466a4"
SECRET = "MINYAR_PHASE1_ATACAMA_AGE_KEY"


def run(argv, **kw):
    return subprocess.run(argv, capture_output=True, check=True, timeout=8, **kw)


class Coverage(unittest.TestCase):
    def test_frozen_ciphertext_and_public_metadata_are_byte_bound(self):
        meta = json.loads((HERE / "atacama-input.json").read_text())
        cipher = (HERE / "atacama-085b55736fda.tar.gz.age").read_bytes()
        self.assertEqual(meta["source_files"], 15)
        self.assertEqual(meta["source_commit"], "085b55736fda3f7e583170d7e54c66d4eaaaedb6")
        self.assertEqual(meta["source_archive_sha256"], "c6a384748b935538ed9993159e94272f8dcdf7ec15a9c29cf30e662034416e69")
        self.assertEqual(meta["public_recipient"], "age1d8ycp2hg3trz0kng5nsu70vux9x632fd7qy3wdjlk5cm7lpzgemsl5q6e2")
        self.assertEqual(len(cipher), 249086)
        self.assertEqual(len(cipher), meta["ciphertext_bytes"])
        self.assertEqual(hashlib.sha256(cipher).hexdigest(), "96937f6a37dc15c30506bdb9531747322ff0d77e046d2b1efca0f41dc68ad0da")
        self.assertEqual(hashlib.sha256(cipher).hexdigest(), meta["ciphertext_sha256"])

    def test_existing_jobs_unchanged_and_missing_gates_added(self):
        data = (HERE.parent / "workflows/ci.yml").read_bytes()
        marker = b"\n  macos-phase1-desktop:\n"
        self.assertTrue(marker in data, "missing Phase1 Darwin qualification jobs")
        old, added = data.split(marker, 1)
        self.assertEqual(hashlib.sha256(old).hexdigest(), BASE_WORKFLOW_SHA)
        text = added.decode()
        for target in ("check-macos", "check-http", "check-graphics-render",
                       "check-managed-graphs-profiles", "check-sanitize"):
            self.assertIn(target, text)
        self.assertIn("MINYAR_PHASE1_ATACAMA_AGE_KEY", text)
        self.assertIn("github.repository == 'O4FDev/MinLang'", text)
        self.assertIn("github.ref == 'refs/heads/v2'", text)
        self.assertIn("github.event_name == 'workflow_dispatch'", text)
        self.assertIn("github.event_name == 'push'", text)
        self.assertNotIn("continue-on-error", text)
        self.assertNotIn("if: env.MINYAR_PHASE1_ATACAMA_AGE_KEY", text)
        self.assertIn("path: ${{ runner.temp }}/phase1-atacama-evidence.age", text)


class Privacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HELPER.exists():
            raise AssertionError("private downstream helper is missing")
        cls.age = shutil.which("age")
        cls.keygen = shutil.which("age-keygen")
        if not cls.age or not cls.keygen:
            raise AssertionError("age and age-keygen are required for orchestration checks")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="minyar-ci-fake-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.key = self.root / "fake-key"
        run([self.keygen, "-o", str(self.key)])
        self.recipient = run([self.keygen, "-y", str(self.key)]).stdout.decode().strip()
        self.fake_key = self.key.read_text()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "minyar").write_text("#!/bin/sh\nexit 0\n")
        (self.repo / "minyar").chmod(0o755)
        (self.repo / ".gitignore").write_text("build/\n")
        run(["git", "init", "-q", str(self.repo)])
        run(["git", "-C", str(self.repo), "add", "."])
        run(["git", "-C", str(self.repo), "-c", "user.name=CI test", "-c",
             "user.email=ci@example.invalid", "commit", "-qm", "test(ci): fake source"])
        self.sha = run(["git", "-C", str(self.repo), "rev-parse", "HEAD"]).stdout.decode().strip()
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as tf:
            member = tarfile.TarInfo("Makefile")
            content = b"# synthetic private input\n"
            member.size, member.mode = len(content), 0o644
            tf.addfile(member, io.BytesIO(content))
        self.archive = stream.getvalue()
        zipped = self.root / "input.gz"
        zipped.write_bytes(gzip.compress(self.archive))
        self.cipher = self.root / "input.age"
        run([self.age, "-r", self.recipient, "-o", str(self.cipher), str(zipped)])
        self.metadata = self.root / "metadata.json"
        self.meta = {"source_commit": "a" * 40, "source_tree": "b" * 40,
                     "source_files": 1, "source_archive_bytes": len(self.archive),
                     "source_archive_sha256": hashlib.sha256(self.archive).hexdigest(),
                     "ciphertext_bytes": self.cipher.stat().st_size,
                     "ciphertext_sha256": hashlib.sha256(self.cipher.read_bytes()).hexdigest(),
                     "public_recipient": self.recipient}
        self.metadata.write_text(json.dumps(self.meta))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        make = self.bin / "make"
        make.write_text("#!" + sys.executable + "\n" + '''import json, os, pathlib, subprocess, sys
print("PRIVATE_STDOUT_SENTINEL")
print("PRIVATE_STDERR_SENTINEL", file=sys.stderr)
assert "MINYAR_PHASE1_ATACAMA_AGE_KEY" not in os.environ
for fd in range(3, 32):
    try: os.fstat(fd)
    except OSError: continue
    raise AssertionError("inherited extra fd")
source = pathlib.Path.cwd()
assert not list(source.parent.rglob("identity.txt"))
assert sys.argv[-3:] == ["check", "test", "all"]
candidate = pathlib.Path(next(x.split("=", 1)[1] for x in sys.argv if x.startswith("MINYAR="))).parent
assert candidate.stat().st_mode & 0o077 == 0
(candidate / "build" / "programs").mkdir(parents=True)
(candidate / "build" / "programs" / "private.ll").write_text("PRIVATE_IR_SENTINEL")
subprocess.run([sys.executable, "-c", "import os, sys; assert 'MINYAR_PHASE1_ATACAMA_AGE_KEY' not in os.environ; print('PRIVATE_GRANDCHILD_SENTINEL'); print('PRIVATE_GRANDCHILD_ERROR', file=sys.stderr)"], check=True)
(source / "build").mkdir()
(source / "build" / "make-receipt.json").write_text(json.dumps({"argv": sys.argv, "env": dict(os.environ)}))
raise SystemExit(EXIT_CODE)
'''.replace("EXIT_CODE", "0"))
        make.chmod(0o755)
        self.output = self.root / "evidence.age"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        RUNNER_TEMP=str(self.root), **{SECRET: self.fake_key})

    def invoke(self):
        return subprocess.run([sys.executable, str(HELPER), "--repository", str(self.repo),
                               "--sha", self.sha, "--input", str(self.cipher),
                               "--metadata", str(self.metadata), "--evidence", str(self.output)],
                              env=self.env, capture_output=True, timeout=12)

    def evidence(self):
        decrypted = run([self.age, "-d", "-i", str(self.key), str(self.output)]).stdout
        with tarfile.open(fileobj=io.BytesIO(decrypted), mode="r:gz") as tf:
            names = tf.getnames()
            values = {x.name: tf.extractfile(x).read() for x in tf.getmembers() if x.isfile()}
        self.assertFalse(any("identity.txt" in n for n in names), "identity in evidence")
        self.assertFalse(any(self.fake_key.encode() in x for x in values.values()), "key in evidence")
        self.assertFalse(any(b"AGE-SECRET-KEY-" in x for x in values.values()), "identity in evidence")
        return values

    def assert_private(self, result):
        public = result.stdout + result.stderr
        for sentinel in (b"PRIVATE_", b"AGE-SECRET-KEY", b"Traceback", b"Makefile"):
            self.assertFalse(sentinel in public, "private content in public output")
        for line in result.stdout.splitlines():
            value = json.loads(line)
            self.assertEqual(set(value), {"stage", "status", "sha"})
            self.assertIn(value["stage"], ("input", "source", "make", "evidence", "qualification"))
            self.assertIn(value["status"], ("passed", "failed"))
        self.assertEqual(result.stderr, b"")
        self.assertFalse(list(self.root.glob("minyar-atacama-private-*")), "private workspace not cleaned")

    def test_stdout_stderr_grandchildren_keys_and_fresh_build_are_private(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0)
        self.assert_private(result)
        values = self.evidence()
        joined = b"\n".join(values.values())
        self.assertTrue(b"PRIVATE_GRANDCHILD_SENTINEL" in joined)
        self.assertTrue(b"PRIVATE_STDERR_SENTINEL" in joined)
        self.assertTrue(b"PRIVATE_IR_SENTINEL" in joined)
        self.assertTrue(any(n.endswith("make-receipt.json") for n in values))
        self.assertFalse((self.repo / "build").exists(), "public checkout got private IR")

    def test_failed_make_status_is_not_hidden_by_encryption(self):
        path = self.bin / "make"
        path.write_text(path.read_text().replace("SystemExit(0)", "SystemExit(7)"))
        result = self.invoke()
        self.assertEqual(result.returncode, 7)
        self.assert_private(result)
        self.assertTrue(any(n.endswith("make-receipt.json") for n in self.evidence()))

    def test_wrong_key_missing_key_tampering_and_hash_mismatch_prevent_make(self):
        cases = ("wrong-key", "missing-key", "tampered", "archive-hash", "cipher-hash")
        for case in cases:
            with self.subTest(case=case):
                original_cipher = self.cipher.read_bytes()
                if case == "wrong-key":
                    other = self.root / "other-key"
                    run([self.keygen, "-o", str(other)])
                    self.env[SECRET] = other.read_text()
                elif case == "missing-key":
                    self.env.pop(SECRET)
                elif case == "tampered":
                    self.cipher.write_bytes(original_cipher[:-1] + bytes([original_cipher[-1] ^ 1]))
                    self.meta["ciphertext_sha256"] = hashlib.sha256(self.cipher.read_bytes()).hexdigest()
                elif case == "archive-hash":
                    self.meta["source_archive_sha256"] = "0" * 64
                else:
                    self.meta["ciphertext_sha256"] = "0" * 64
                self.metadata.write_text(json.dumps(self.meta))
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assert_private(result)
                self.assertFalse(any(n.endswith("make-receipt.json") for n in self.evidence()), "Make ran on bad input")
                self.cipher.write_bytes(original_cipher)
                self.meta["ciphertext_sha256"] = hashlib.sha256(original_cipher).hexdigest()
                self.meta["source_archive_sha256"] = hashlib.sha256(self.archive).hexdigest()
                self.env[SECRET] = self.fake_key

    def test_encryption_failure_has_no_plaintext_fallback_or_stale_ciphertext(self):
        wrapper = self.bin / "age"
        wrapper.write_text("#!/bin/sh\ncase \"$1\" in --encrypt) exit 9;; esac\nexec \"" + self.age + "\" \"$@\"\n")
        wrapper.chmod(0o755)
        self.output.write_text("stale ciphertext must not survive")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assert_private(result)
        self.assertFalse(self.output.exists(), "encryption failed open")
        path = self.bin / "make"
        path.write_text(path.read_text().replace("SystemExit(0)", "SystemExit(7)"))
        result = self.invoke()
        self.assertEqual(result.returncode, 7)
        self.assert_private(result)
        self.assertFalse(self.output.exists(), "failed Make gained a plaintext fallback")

    def replace_archive(self, archive):
        self.archive = archive
        zipped = self.root / "replacement.gz"
        zipped.write_bytes(gzip.compress(archive))
        self.cipher.unlink()
        run([self.age, "-r", self.recipient, "-o", str(self.cipher), str(zipped)])
        self.meta.update(source_archive_bytes=len(archive),
                         source_archive_sha256=hashlib.sha256(archive).hexdigest(),
                         ciphertext_bytes=self.cipher.stat().st_size,
                         ciphertext_sha256=hashlib.sha256(self.cipher.read_bytes()).hexdigest())
        self.metadata.write_text(json.dumps(self.meta))

    def test_unsafe_archive_fails_before_make(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as tf:
            member = tarfile.TarInfo("../escape")
            member.size, member.mode = 1, 0o644
            tf.addfile(member, io.BytesIO(b"x"))
        self.replace_archive(stream.getvalue())
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assert_private(result)
        self.assertFalse((self.root / "escape").exists())
        self.assertFalse(any(n.endswith("make-receipt.json") for n in self.evidence()))

    def test_source_mode_change_cannot_pass(self):
        path = self.bin / "make"
        path.write_text(path.read_text().replace("raise SystemExit(0)",
                        "(source / 'Makefile').chmod(0o755)\nraise SystemExit(0)"))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assert_private(result)
        self.evidence()

    def test_cancelled_make_closes_descendants_and_encrypts_failure(self):
        path = self.bin / "make"
        path.write_text(path.read_text().replace("raise SystemExit(0)", '''
import time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(8)"])
(source / "build" / "live-child-pid").write_text(str(child.pid))
time.sleep(8)
'''))
        argv = [sys.executable, str(HELPER), "--repository", str(self.repo),
                "--sha", self.sha, "--input", str(self.cipher),
                "--metadata", str(self.metadata), "--evidence", str(self.output)]
        child = subprocess.Popen(argv, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            pidfiles = []
            while time.monotonic() < deadline:
                pidfiles = list(self.root.glob("minyar-atacama-private-*/downstream/build/live-child-pid"))
                if pidfiles:
                    break
                time.sleep(0.02)
            self.assertTrue(pidfiles, "synthetic Make did not start")
            descendant = int(pidfiles[0].read_text())
            child.send_signal(signal.SIGTERM)
            stdout, stderr = child.communicate(timeout=5)
            result = subprocess.CompletedProcess(argv, child.returncode, stdout, stderr)
            self.assertEqual(result.returncode, 143)
            self.assert_private(result)
            state = subprocess.run(["ps", "-o", "stat=", "-p", str(descendant)], capture_output=True, timeout=2)
            self.assertTrue(not state.stdout.strip() or state.stdout.strip().startswith(b"Z"), "owned descendant survived cancellation")
            self.evidence()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()


if __name__ == "__main__":
    unittest.main()
