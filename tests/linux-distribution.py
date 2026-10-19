#!/usr/bin/env python3
"""Qualify a native Linux release through its real signed installer."""
import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading

if not __debug__:
    raise SystemExit("distribution checks require Python assertions; remove -O")


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *arguments):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distribution", type=Path, required=True)
    parser.add_argument("--archive", type=Path, help="deliver this original packager archive instead of repacking the verified directory")
    parser.add_argument("--paint", type=Path, help="also run exact offline external gallery checks")
    parser.add_argument("--require-no-system-llvm", action="store_true", help="fail if this qualification host has Clang or LLD installed")
    args = parser.parse_args()
    assert platform.system() == "Linux", "run on the native target Linux host"
    if args.require_no_system_llvm:
        for name in ("clang", "clang-23", "ld.lld", "lld"):
            assert shutil.which(name) is None, f"qualification host has system {name}"
        assert not Path("/usr/lib/llvm-23").exists(), "qualification host has system LLVM"
    distribution = args.distribution.resolve()
    metadata = json.loads((distribution / "distribution.json").read_text())
    assert metadata["platform"] == "linux" and metadata["llvm"] == "23.1.2"
    for path, expected in metadata["files"].items():
        assert hashlib.sha256((distribution / path).read_bytes()).hexdigest() == expected, f"release checksum mismatch: {path}"
    print("Release file manifest verified", flush=True)
    checkout = Path(__file__).resolve().parent.parent
    before = {str(path.relative_to(distribution)): path.stat().st_mtime_ns for path in distribution.rglob("*")}
    with tempfile.TemporaryDirectory(prefix="minyar Linux archive '") as temporary:
        work = Path(temporary)
        home = work / "fresh home"
        home.mkdir()
        blocked = work / "unavailable build tools"
        blocked.mkdir()
        marker = work / "unexpected build tool"
        for name in ("make", "gmake", "python", "python3", "zsh"):
            (blocked / name).write_text('#!/bin/sh\nprintf "%s\\n" "$0" >> "$MINYAR_UNEXPECTED_TOOL"\nexit 93\n')
            (blocked / name).chmod(0o755)
        environment = {"HOME": str(home), "PATH": f"{blocked}:/usr/bin:/bin:/usr/sbin:/sbin",
                       "TMPDIR": str(work), "LC_ALL": "C", "MINYAR_UNEXPECTED_TOOL": str(marker)}

        def run(*command, cwd=work, env=environment, expected=0):
            result = subprocess.run([str(value) for value in command], cwd=cwd, env=env,
                                    text=True, capture_output=True, timeout=600)
            if result.returncode != expected:
                raise AssertionError(f"{command}: exit {result.returncode}, expected {expected}\n{result.stdout}{result.stderr}")
            print(result.stdout + result.stderr, end="", flush=True)
            return result.stdout + result.stderr

        # Platform errors must precede any executable from an incompatible archive.
        contract = work / "platform contract"
        contract.mkdir()
        (contract / "distribution.arch").write_text("wrong-cpu\n")
        (contract / "distribution.libc").write_text("2.39\n")
        assert "download the" in run("sh", distribution / "tools/linux-platform.sh", contract, expected=1)
        (contract / "distribution.arch").write_text(metadata["arch"] + "\n")
        (contract / "distribution.libc").write_text("9999.0\n")
        assert "requires glibc 9999.0" in run("sh", distribution / "tools/linux-platform.sh", contract, expected=1)
        (contract / "distribution.libc").write_text("invalid\n")
        assert "requires glibc" in run("sh", distribution / "tools/linux-platform.sh", contract, expected=1)
        print("CPU and glibc startup diagnostics passed", flush=True)
        public = work / "public"
        public.mkdir()
        artifact = args.archive.resolve() if args.archive else work / (distribution.name + ".tar.gz")
        if not args.archive:
            with tarfile.open(artifact, "w:gz") as archive:
                archive.add(distribution, arcname=distribution.name)
        key = work / "ephemeral-release-key"
        run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", key)
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(public)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            version = metadata["version"]
            run(sys.executable, distribution / "install/prepare-release.py", "--archive", artifact,
                "--version", version, "--public-key", key.with_suffix(".pub"), "--signing-key", key,
                "--server", url, "--output", public, "--latest")
            run("bash", "-o", "pipefail", "-c", 'curl -q -fsSL "$1/install" | sh', "minyar", url)
            command = home / ".minyar/bin/minyar"
            assert f"Minyar {version} (Linux" in run(command, "--version")
            assert "Ready:" in run(command, "--doctor")
            private_libraries = sorted((home / ".minyar/toolchains" / version / "toolchain/lib").glob("libLLVM.so.*"))
            if private_libraries:
                library = private_libraries[0]
                hidden_library = library.with_name(library.name + ".missing")
                library.rename(hidden_library)
                try:
                    assert "bundled LLVM cannot start" in run(command, "--version", expected=1)
                finally:
                    hidden_library.rename(library)
            project = work / "hello project"
            run(command, "new", project, "--name", "hello")
            for options in ([], ["--release"]):
                assert "Hello, world!" in run(command, "run", *options, cwd=project)
                run(command, "test", *options, cwd=project)
            (project / "src/main.min").write_text('use "system" as system\nprint(system.processId() > 0)\n')
            for options in ([], ["--release"]):
                assert "true" in run(command, "run", *options, cwd=project)
            for profile in ("eager", "fixed", "lazy", "system"):
                binary = work / profile
                run(command, "--memory-profile", profile, project / "src/main.min", "-o", binary)
                assert "true" in run(binary)
            (project / "minyar-toolchain").write_text(version + "\n")
            assert "minyar-toolchain" in run(command, "toolchain", "current", cwd=project)
            run(command, "self", "update", cwd=project)
            installed = home / ".minyar"
            relocated = work / "relocated prefix"
            installed.rename(relocated)
            relocated_environment = dict(environment, MINYAR_HOME=str(relocated))
            command = relocated / "bin/minyar"
            shutil.rmtree(project / "target")
            shutil.rmtree(home / ".cache/minyar", ignore_errors=True)
            hidden = distribution.with_name(distribution.name + ".qualification-hidden")
            distribution.rename(hidden)
            try:
                for options in ([], ["--release"]):
                    assert "true" in run(command, "run", *options, cwd=project, env=relocated_environment)
                if args.paint:
                    fixed = relocated / "toolchains" / version / "minyar"
                    run(sys.executable, checkout / "tests/paint-package.py", fixed, args.paint.resolve(),
                        checkout / "examples/gallery/paint", env=relocated_environment)
            finally:
                hidden.rename(distribution)
            assert not marker.exists(), marker.read_text() if marker.exists() else ""
            for name in (".profile", ".bashrc", ".bash_profile", ".zshrc"):
                assert not (home / name).exists(), f"installer edited {name}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    after = {str(path.relative_to(distribution)): path.stat().st_mtime_ns for path in distribution.rglob("*")}
    assert before == after, "runtime commands changed the distribution"
    print("Linux distribution: signed bootstrap, clean HOME, no build tools, doctor, debug/release, native providers, memory profiles, pins, update and relocation passed", flush=True)


if __name__ == "__main__":
    main()
