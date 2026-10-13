#!/usr/bin/env python3
"""Wire-visible ACK scheduling adversaries with monotonic virtual clocks."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--mode", type=int, action="append", choices=range(50))
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--library", type=Path)
    parser.add_argument("--optimization", choices=("0", "2", "both"), default="both")
    options = parser.parse_args()
    directory = options.artifacts or Path(tempfile.mkdtemp(prefix="minyar-quic-ack-"))
    directory.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("ack_tls_fixtures", ROOT / "tests/tls-local.py")
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    ca = fixtures.Certificates(directory)
    ca.root("root")
    ca.leaf("server", "root")
    ca.leaf("client", "root", usage="clientAuth")
    paths = [ROOT / "tests/quic-ack.min", Path(__file__), ROOT / "tests/tls-local.py", ROOT / "minyar"]
    for base in ("library", "runtime", "compiler", "tools"):
        paths += [p for p in (ROOT / base).rglob("*") if p.is_file() and p.suffix in (".min", ".c", ".h", ".py", ".sh")]
    before = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    manifest = {"sources": before, "sanitize": options.sanitize, "commands": [], "cases": [], "passed": False}
    target = directory / "manifest.json"
    def save():
        target.write_text(json.dumps(manifest, indent=2) + "\n")
    save()
    library = (options.library or ROOT / "library").resolve()
    if library != ROOT / "library":
        manifest["override_sources"] = {str(p): digest(p) for p in library.rglob("*") if p.is_file()}
    opts = ("0", "2") if options.optimization == "both" else (options.optimization,)
    for opt in opts:
        flags = f"-O{opt} -Wno-override-module"
        if options.sanitize:
            flags += " -g -fsanitize=address,undefined -fno-omit-frame-pointer"
        env = os.environ.copy()
        for name in ("MINYAR_CLANG_FLAGS", "MINYAR_NATIVE_FLAGS", "MINYAR_RUNTIME_FLAGS"):
            env[name] = flags
        env["MAKEFLAGS"] = "-j1"
        env["ASAN_OPTIONS"] = "detect_leaks=1" if sys.platform.startswith("linux") else "detect_leaks=0"
        env["UBSAN_OPTIONS"] = "halt_on_error=1"
        binary = directory / f"ack-O{opt}.exe"
        command = [str(ROOT / "minyar"), "--library", str(library)]
        if library != ROOT / "library":
            command += ["--library", str(ROOT / "library")]
        command += [str(ROOT / "tests/quic-ack.min"), "-o", str(binary)]
        if os.name == "nt":
            shell = shutil.which("bash")
            if not shell:
                raise RuntimeError("native Windows ACK fixtures require Bash")
            command.insert(0, shell)
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
        prefix = directory / f"compile-O{opt}"
        prefix.with_suffix(".stdout").write_bytes(result.stdout)
        prefix.with_suffix(".stderr").write_bytes(result.stderr)
        row = {"argv": command, "status": result.returncode, "seconds": time.monotonic() - started,
               "flags": flags, "stdout_sha256": digest(prefix.with_suffix(".stdout")), "stderr_sha256": digest(prefix.with_suffix(".stderr"))}
        manifest["commands"].append(row)
        save()
        if result.returncode:
            print("ACK compiler failed", opt, result.returncode, result.stderr.decode(errors="replace")[-3000:])
            return 1
        row["binary_sha256"] = digest(binary)
        for mode in options.mode or range(50):
            command = [str(binary), *[str(ca.path(name, suffix)) for name, suffix in (
                ("root", "der"), ("server", "der"), ("server", "pk8"), ("client", "der"), ("client", "pk8"))], str(mode)]
            started = time.monotonic()
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=30)
            prefix = directory / f"O{opt}-case-{mode}"
            prefix.with_suffix(".stdout").write_bytes(result.stdout)
            prefix.with_suffix(".stderr").write_bytes(result.stderr)
            expected = f"ACK case {mode}\n".encode()
            output = result.stdout.replace(b"\r\n", b"\n") if os.name == "nt" or sys.platform.startswith(("cygwin", "msys")) else result.stdout
            passed = result.returncode == 0 and output == expected and not result.stderr
            manifest["cases"].append({"optimization": opt, "mode": mode, "argv": command, "status": result.returncode,
                "passed": passed, "seconds": time.monotonic() - started, "stdout_sha256": digest(prefix.with_suffix(".stdout")),
                "stderr_sha256": digest(prefix.with_suffix(".stderr"))})
            save()
            print("ACK", opt, mode, result.returncode, "PASS" if passed else "FAIL", flush=True)
    manifest["source_after"] = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    manifest["passed"] = all(row["passed"] for row in manifest["cases"]) and manifest["source_after"] == before
    save()
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
