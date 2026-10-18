#!/usr/bin/env python3
"""Local signed release fixtures; no network beyond loopback, no global install."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import select
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading

if not __debug__:
    raise SystemExit("installer checks require Python assertions; remove -O")


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *arguments):
        pass


def run(arguments, *, environment=None, directory=None, expected=None, input=None):
    result = subprocess.run([str(value) for value in arguments], env=environment, cwd=directory, input=input, text=True, capture_output=True, timeout=45)
    if expected is None:
        assert result.returncode == 0, (arguments, result.stdout, result.stderr)
    else:
        assert result.returncode != 0 and expected in result.stderr, (arguments, expected, result.stdout, result.stderr)
    return result.stdout + result.stderr


def archive(root, installer, version, *, broken=False, unsafe=None):
    operating_system = "macos" if platform.system() == "Darwin" else "linux"
    architecture = "arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64"
    name = f"minyar-{version}-{operating_system}-{architecture}"
    stage = root / name
    (stage / "install").mkdir(parents=True)
    shutil.copyfile(installer / "install.sh", stage / "install/install.sh")
    shutil.copyfile(installer / "manager.sh", stage / "install/manager.sh")
    (stage / "minyar").write_text("#!/bin/sh\n" + ("exit 9\n" if broken else f"printf 'Minyar {version}\\n'\n"))
    (stage / "minyar").chmod(0o755)
    (stage / "distribution.version").write_text(version + "\n")
    (stage / "distribution.arch").write_text(architecture + "\n")
    (stage / "alias").symlink_to("minyar")
    output = root / f"{name}.tar.gz"
    with tarfile.open(output, "w:gz") as target:
        target.add(stage, arcname=name)
        if unsafe == "path":
            item = tarfile.TarInfo(f"{name}/../ESCAPED")
            item.size = 6
            target.addfile(item, io.BytesIO(b"unsafe"))
        elif unsafe == "link":
            item = tarfile.TarInfo(f"{name}/escape")
            item.type = tarfile.SYMTYPE
            item.linkname = "../../ESCAPED"
            target.addfile(item)
    return output


def main():
    installer = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "install"
    with tempfile.TemporaryDirectory(prefix="minyar installer ") as temporary:
        root = Path(temporary)
        public = root / "public"
        public.mkdir()
        registry = None
        server = None
        if len(sys.argv) > 2:
            (public / "index.json").write_text(json.dumps({"schema": 1, "checksum_root": hashlib.sha256(b"minyar-checksums-v1\n").hexdigest(), "packages": []}))
            registry = subprocess.Popen([str(Path(sys.argv[2]).resolve()), "serve", str(public), "0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(public)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
        try:
            if registry:
                ready, _, _ = select.select([registry.stdout], [], [], 20)
                assert ready, "registry server did not announce readiness"
                line = registry.stdout.readline().strip()
                assert line.startswith("Registry listening at http://127.0.0.1:"), line
                url = line.removeprefix("Registry listening at ")
            else:
                url = f"http://127.0.0.1:{server.server_port}"
            key = root / "test-signing-key"
            run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", key])
            home = root / "home with spaces and 'quotes'"
            environment = os.environ.copy()
            for name in ("MINYAR_HOME", "MINYAR_TOOLCHAIN", "MINYAR_TOOLCHAIN_ACTIVE", "MINYAR_TRUSTED_KEY", "MINYAR_DIST_URL", "MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS"):
                environment.pop(name, None)
            environment.update(MINYAR_HOME=str(home))

            def prepare(version, **options):
                artifact = archive(root, installer, version, **options)
                run([sys.executable, installer / "prepare-release.py", "--version", version, "--archive", artifact, "--public-key", key.with_suffix(".pub"), "--signing-key", key, "--server", url, "--output", public, "--latest"])
                return artifact

            prepare("1.0.0")
            # Exercise the actual one-line installation shape against loopback.
            output = run(["bash", "-o", "pipefail", "-c", 'curl -q -fsSL "$1/install" | sh', "minyar", url], environment=environment)
            assert "Ed25519 signature + SHA-256" in output and "Minyar is ready." in output
            command = home / "bin/minyar"
            path_command = next(line.strip() for line in output.splitlines() if line.strip().startswith("export PATH="))
            assert str(command) in run(["sh", "-c", path_command + "\ncommand -v minyar"], environment=environment)
            assert "Minyar 1.0.0" in run([command, "--version"], environment=environment)
            assert "1.0.0 (default)" in run([command, "toolchain", "list"], environment=environment)
            source_launcher = installer.parent / "minyar"
            assert "1.0.0 (default)" in run([source_launcher, "toolchain", "current"], environment=environment)
            extra_home = root / "explicit home"
            extra_output = run(["sh", public / "install", "--home", extra_home], environment=environment)
            assert "Minyar is ready." in extra_output and (extra_home / "bin/minyar").exists()
            if platform.system() == "Darwin":
                missing_sdk_home = root / "missing sdk"
                run(["sh", public / "install"], environment=dict(environment, MINYAR_HOME=str(missing_sdk_home), SDKROOT=str(root / "no sdk")), expected="Apple SDK is unavailable")
                assert not missing_sdk_home.exists()
            prepare("2.0.0")
            run([command, "toolchain", "install", "2.0.0"], environment=environment)
            assert (home / "default").read_text() == "1.0.0\n"
            project = root / "a project"
            (project / "nested").mkdir(parents=True)
            pin = project / "minyar-toolchain"
            pin.write_text("2.0.0\n")
            assert "Minyar 2.0.0" in run([command, "--version"], environment=environment, directory=project / "nested")
            assert str(pin) in run([command, "toolchain", "current"], environment=environment, directory=project / "nested")
            assert "Minyar 1.0.0" in run([command, "--version"], environment=dict(environment, MINYAR_TOOLCHAIN="1.0.0"), directory=project)
            pin.write_text("9.9.9\n")
            run([command, "--version"], environment=environment, directory=project, expected="run minyar toolchain install 9.9.9")
            pin.write_text("../../escape\n")
            run([command, "--version"], environment=environment, directory=project, expected="must contain one toolchain version")
            pin.write_text("1.0.0\n")
            run([command, "self", "update"], environment=environment, directory=project)
            assert (home / "default").read_text() == "2.0.0\n"
            assert "Minyar 1.0.0" in run([command, "--version"], environment=environment, directory=project)
            run([command, "toolchain", "default", "1.0.0"], environment=environment)
            assert (home / "default").read_text() == "1.0.0\n"
            # A nested Minyar invocation may inherit the selected-toolchain marker.
            assert "Minyar 1.0.0" in run([command, "--version"], environment=dict(environment, MINYAR_TOOLCHAIN_ACTIVE="1.0.0"))

            generated = public / "install"
            checksum = public / "releases/2.0.0/SHA256SUMS"
            original = checksum.read_bytes()
            checksum.write_bytes(original + b"tampered\n")
            rejected_home = root / "bad-signature"
            run(["sh", generated, "--version", "2.0.0"], environment=dict(environment, MINYAR_HOME=str(rejected_home)), expected="signature verification failed")
            assert not rejected_home.exists()
            checksum.write_bytes(original)
            artifact = next((public / "releases/2.0.0").glob("*.tar.gz"))
            content = artifact.read_bytes()
            artifact.write_bytes(content + b"tampered")
            run(["sh", generated, "--version", "2.0.0"], environment=dict(environment, MINYAR_HOME=str(rejected_home)), expected="checksum mismatch")
            assert not rejected_home.exists()
            artifact.write_bytes(content)
            prepare("3.0.0", unsafe="path")
            run(["sh", generated, "--version", "3.0.0"], environment=dict(environment, MINYAR_HOME=str(rejected_home)), expected="unsafe paths")
            assert not rejected_home.exists() and not (root / "ESCAPED").exists()
            prepare("3.1.0", unsafe="link")
            run(["sh", generated, "--version", "3.1.0"], environment=dict(environment, MINYAR_HOME=str(rejected_home)), expected="unsupported links")
            prepare("4.0.0", broken=True)
            run([command, "toolchain", "install", "4.0.0"], environment=environment, expected="could not start")
            assert not (home / "toolchains/4.0.0").exists()
            assert "Minyar 1.0.0" in run([command, "--version"], environment=environment)
            assert not (home / ".install-lock").exists()
            unrelated = root / "unrelated"
            (unrelated / "bin").mkdir(parents=True)
            (unrelated / "bin/minyar").write_text("keep me\n")
            run(["sh", generated, "--version", "2.0.0"], environment=dict(environment, MINYAR_HOME=str(unrelated)), expected="unrelated command")
            assert (unrelated / "bin/minyar").read_text() == "keep me\n"
            outside = root / "outside-marker"
            outside.write_text("keep me\n")
            marker_home = root / "symlink marker"
            marker_home.mkdir()
            (marker_home / ".minyar-home").symlink_to(outside)
            run(["sh", generated, "--version", "2.0.0"], environment=dict(environment, MINYAR_HOME=str(marker_home)), expected="unrelated installation marker")
            assert outside.read_text() == "keep me\n"
            print("Installer: signed curl install, checksums, versions, pins, update, failure preservation and unsafe archives passed")
        finally:
            if registry:
                registry.terminate()
                registry.wait(timeout=10)
            else:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    main()
