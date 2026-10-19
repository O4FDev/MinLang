#!/usr/bin/env python3
"""Offline package/index integration and the real Minyar loopback HTTP server."""
import hashlib
import http.client
import http.server
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading

if not __debug__:
    raise SystemExit("registry checks require Python assertions; remove -O")


def run(arguments, env, cwd, expected=None):
    result = subprocess.run([str(value) for value in arguments], env=env, cwd=cwd, text=True, capture_output=True, timeout=120)
    if expected is None:
        assert result.returncode == 0, (arguments, result.stdout, result.stderr)
    else:
        assert result.returncode != 0 and expected in result.stderr, (arguments, expected, result.stdout, result.stderr)
    return result.stdout


def sums(entries):
    return "minyar-checksums-v1\n" + "".join(f"{e['repository']} {e['version']} {e['commit']} {e['checksum']}\n" for e in sorted(entries, key=lambda e: e["repository"] + "@" + e["version"]))


def write_index(path, value):
    value["checksum_root"] = hashlib.sha256(sums(value["packages"]).encode()).hexdigest()
    path.write_text(json.dumps(value))


def check_credential_isolation(launcher, env, root, application):
    authorizations = []

    class Denied(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            authorizations.append(self.headers.get("Authorization"))
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="private fixture"')
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *arguments):
            pass

    private_home = root / "user home with credentials"
    private_home.mkdir()
    netrc = private_home / ".netrc"
    netrc.write_text("machine 127.0.0.1 login fixture password fake-test-password\n")
    netrc.chmod(0o600)
    asked = root / "askpass-ran"
    askpass = root / "askpass"
    askpass.write_text("#!/bin/sh\ntouch " + shlex.quote(str(asked)) + "\nprintf 'fixture\\n'\n")
    askpass.chmod(0o755)
    manifest = (application / "Minyar.toml").read_bytes()
    lock = (application / "Minyar.lock").read_bytes()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Denied)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    problems = []
    try:
        for authority in ("127.0.0.1", "localhost"):
            authorizations.clear()
            asked.unlink(missing_ok=True)
            isolated = {k: v for k, v in env.items() if k not in ("MINYAR_GIT_MIRROR", "MINYAR_REGISTRY") and not k.lower().endswith("_proxy")}
            isolated.update(HOME=str(private_home), SSH_ASKPASS=str(askpass), NO_PROXY="*", MINYAR_TEST_AUTH_URL=f"http://{authority}:{server.server_port}/noauth.git")
            run([launcher, "add", "github.com/Fixtures/noauth"], isolated, application, "Git could not read this package")
            assert authorizations, "the private Git HTTP fixture must receive a request"
            if any(authorizations):
                problems.append("Git consulted the invoking user's .netrc")
            if asked.exists():
                problems.append("Git executed the invoking user's password helper")
            assert (application / "Minyar.toml").read_bytes() == manifest and (application / "Minyar.lock").read_bytes() == lock
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    assert not problems, "; ".join(problems)


def main():
    launcher, registry_cli, project_root = map(lambda value: Path(value).resolve(), sys.argv[1:4])
    with tempfile.TemporaryDirectory(prefix="minyar registry ' ") as temporary:
        root = Path(temporary)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k not in ("MINYAR_HOME", "MINYAR_REGISTRY", "MINYAR_GIT_MIRROR", "MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS")}
        env.update(MINYAR_HOME=str(root / "home"), MINYAR_PROJECT_DIR=str(project_root), GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
        package = root / "lumen"
        (package / "src").mkdir(parents=True)
        (package / "Minyar.toml").write_text('[package]\nname = "lumen"\nversion = "0.1.0"\nkind = "lib"\n')
        (package / "src/lumen.min").write_text("public function answer(): Integer { return 42 }\n")
        (package / ".gitignore").write_text("/target/\n")
        (package / "raw").mkdir()
        for number in range(1000):
            (package / f"raw/{number:04}.dat").write_bytes(bytes([0, 255, number % 256]) + b"\nraw Git bytes\r\n")
        (package / "raw/empty.dat").write_bytes(b"")
        (package / "raw/quote' $(touch SHOULD_NOT_EXIST) `echo data` ☀.dat").write_bytes(b"no trailing newline")
        (package / ".gitattributes").write_text("raw/* export-ignore filter=never-run\nsubstitution.dat export-subst\n")
        (package / "substitution.dat").write_text("$Format:%H$\n")

        def git(*arguments):
            return run(["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=Minyar tests", "-c", "user.email=tests@example.invalid", "-C", package, *arguments], env, root)

        git("init", "--quiet", "--initial-branch=main")
        git("add", ".")
        git("commit", "--quiet", "-m", "feat(package): add a registry fixture")
        git("tag", "v0.1.0")
        head = git("rev-parse", "HEAD").strip()
        git("config", "filter.never-run.smudge", "touch " + shlex.quote(str(root / "filter-ran")) + "; cat")
        real_git = shutil.which("git", path=env.get("PATH"))
        assert real_git
        git_log = root / "git-calls.jsonl"
        git_log.write_text("")
        wrappers = root / "bin"
        wrappers.mkdir()
        wrapper = wrappers / "git"
        wrapper.write_text(f"""#!{sys.executable}
import json, os, sys
with open(os.environ['MINYAR_TEST_GIT_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
# The authentication fixture uses real Git HTTP entirely on loopback.
arguments = [os.environ['MINYAR_TEST_AUTH_URL'] if value == 'https://github.com/Fixtures/noauth.git' else value for value in sys.argv[1:]]
os.execv(os.environ['MINYAR_TEST_REAL_GIT'], [os.environ['MINYAR_TEST_REAL_GIT'], *arguments])
""")
        wrapper.chmod(0o755)
        env.update(PATH=str(wrappers) + os.pathsep + env.get("PATH", "/usr/bin:/bin"), MINYAR_TEST_GIT_LOG=str(git_log), MINYAR_TEST_REAL_GIT=real_git)

        def blob_calls():
            return [json.loads(line) for line in git_log.read_text().splitlines() if '"cat-file"' in line]

        arguments = [launcher, "publish", "github.com/O4FDev/lumen", "--description", "Light, in a small library."]
        record_text = run(arguments, env, package)
        calls = blob_calls()
        assert len(calls) == 1 and calls[0][-2:] == ["cat-file", "--batch"], f"publish must read all 1000+ blobs in one Git batch, got {len(calls)} processes"
        assert record_text == run([*arguments, "--dry-run"], env, package)
        record = json.loads(record_text)
        assert record["commit"] == head and record["version"] == "0.1.0"
        names = [name for name in git("ls-tree", "-r", "-z", "--name-only", "HEAD").split("\0") if name]
        material = "minyar-source-v1\n" + "".join(hashlib.sha256((package / name).read_bytes()).hexdigest() + " " + json.dumps(name, ensure_ascii=False, separators=(",", ":")) + "\n" for name in sorted(names))
        assert record["checksum"] == hashlib.sha256(material.encode()).hexdigest()
        assert git("rev-parse", "HEAD").strip() == head and git("status", "--porcelain") == ""
        (package / "src/lumen.min").write_text("// uncommitted\n")
        run(arguments, env, package, "uncommitted files")
        git("restore", "src/lumen.min")
        records = root / "records"
        records.mkdir()
        (records / "lumen.json").write_text(record_text)
        public = root / "public"
        run([launcher, "registry", "build", records, public], env, root)
        index_path = public / "index.json"
        initial = index_path.read_bytes()
        index = json.loads(initial)
        assert (public / "checksums.txt").read_text() == sums([record])
        assert index["checksum_root"] == hashlib.sha256(sums([record]).encode()).hexdigest()
        run([registry_cli, "build", records, public], env, root)
        assert index_path.read_bytes() == initial
        altered = dict(record, checksum="0" * 64)
        (records / "lumen.json").write_text(json.dumps(altered))
        run([registry_cli, "build", records, public], env, root, "immutable")
        assert index_path.read_bytes() == initial
        (records / "lumen.json").write_text(record_text)
        assert "lumen" in run([launcher, "search", "light", "--registry", public], env, root)
        assert record["checksum"] in run([launcher, "info", "lumen", "--registry", public], env, root)
        run([launcher, "info", "absent", "--registry", public], env, root, "package not found")
        ambiguous = dict(record, repository="github.com/Another/lumen")
        write_index(index_path, dict(index, packages=[record, ambiguous]))
        run([launcher, "info", "lumen", "--registry", public], env, root, "more than one package")
        assert record["commit"] in run([launcher, "info", record["repository"], "--registry", public], env, root)
        many = [dict(record, name=f"light{number}", repository=f"github.com/Fixtures/light{number}") for number in range(1000)]
        write_index(index_path, dict(index, packages=many))
        assert "light999" in run([launcher, "search", "light999", "--registry", public], env, root)
        index_path.write_bytes(initial)
        for unsafe_url in ("http://example.invalid", "http://127.0.0.1:12@example.invalid", "http://localhost:1@elsewhere.invalid"):
            run([launcher, "search", "--registry", unsafe_url], env, root, "loopback")
        mirror = root / "mirror/github.com/O4FDev/lumen.git"
        mirror.parent.mkdir(parents=True)
        run(["git", "clone", "--bare", "--quiet", package, mirror], env, root)
        env.update(MINYAR_GIT_MIRROR=str(root / "mirror"), MINYAR_REGISTRY=str(public))
        application = root / "consumer"
        run([launcher, "new", application], env, root)
        before_fetch = len(blob_calls())
        run([launcher, "add", "github.com/O4FDev/lumen"], env, application)
        fetched = blob_calls()[before_fetch:]
        assert len(fetched) == 1 and fetched[0][-2:] == ["cat-file", "--batch"], "a Git install reads every blob in one batch"
        assert not (root / "SHOULD_NOT_EXIST").exists() and not (package / "SHOULD_NOT_EXIST").exists() and not (application / "SHOULD_NOT_EXIST").exists()
        assert not (root / "filter-ran").exists(), "exports never execute Git filters"
        (application / "src/main.min").write_text('use "lumen" as lumen\nprint(lumen.answer())\n')
        assert "42\n" in run([launcher, "run", "--locked", "--offline"], env, application)
        index["packages"] = [altered]
        write_index(index_path, index)
        run([launcher, "tree", "--locked", "--offline"], env, application, "registry checksum mismatch")
        index_path.write_bytes(initial)
        (public / "install").write_text("# local installer fixture\n")
        (public / "latest").write_text("0.1.0\n")
        (public / "latest.sig").write_bytes(b"signature fixture\n")
        outside = root / "not-public"
        outside.write_text("private")
        (public / "releases").mkdir()
        (public / "releases/escape").symlink_to(outside)
        server = subprocess.Popen([str(launcher), "registry", "serve", str(public), "0"], env=env, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([server.stdout], [], [], 20)
            assert ready, "server did not announce readiness"
            line = server.stdout.readline()
            assert line.startswith("Registry listening at http://127.0.0.1:"), line
            port = int(line.strip().rsplit(":", 1)[1])

            def request(method, path):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                connection.request(method, path)
                response = connection.getresponse()
                body = response.read()
                result = response.status, dict(response.getheaders()), body
                connection.close()
                return result

            status, headers, body = request("GET", "/index.json")
            assert status == 200 and body == initial and headers["x-content-type-options"] == "nosniff"
            assert request("HEAD", "/checksums.txt")[2] == b""
            assert request("GET", "/install")[0] == 200
            assert request("GET", "/latest")[2] == b"0.1.0\n"
            assert request("GET", "/latest.sig")[2] == b"signature fixture\n"
            for path in ("/../not-public", "/releases/escape", "/%2e%2e/not-public", "/.git/config"):
                assert request("GET", path)[0] == 404, path
            assert request("POST", "/index.json")[0] == 405
            url = f"http://127.0.0.1:{port}"
            assert "lumen" in run([launcher, "search", "--registry", url], env, root)
            index = json.loads(initial)
            index["packages"] = [altered]
            write_index(index_path, index)
            run([launcher, "search", "--registry", url], env, root, "already witnessed release")
            index_path.write_bytes(initial)
        finally:
            server.terminate()
            server.wait(timeout=10)
        assert "lumen" in run([launcher, "search", "--registry", url, "--offline"], env, root)
        check_credential_isolation(launcher, env, root, application)
        print("Registry: dry runs, batched raw blobs, immutable sums, Git verification, discovery, HTTP, offline witness, paths and credential isolation passed")


if __name__ == "__main__":
    main()
