#!/usr/bin/env python3
"""Peer-generated, virtual-clock RFC 9002 handshake PTO regressions."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from clang_helpers import windows_host
from test_evidence import Evidence

ROOT = Path(__file__).resolve().parents[1]
MODES = ("initial", "handshake", "handshake-ack", "application",
         "confirmed", "close", "drain", "retry", "blocked-probe", "application-ack", "shared", "shared-late", "idle-send", "idle-pto", "initial-burst", "server-credit", "server-paired")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preserve_observations(manifest, evidence, save, failed):
    """Persist raw observations before successful workspace cleanup."""
    manifest["raw_command_records"] = {
        "schema_version": 2,
        "workspace": str(evidence.path),
        "inputs": evidence.inputs,
        "controls": evidence.controls,
        "tool_identity_fields": ["executable", "size", "mtime_ns", "inode"],
        "tool_hashes": [{"identity": list(identity), "sha256": fingerprint}
                        for identity, fingerprint in sorted(evidence.tool_hashes.items())],
        "commands": evidence.commands,
    }
    manifest["raw_command_records_retained"] = True
    manifest["raw_evidence"] = str(evidence.path)
    manifest["raw_workspace_retained"] = None
    save()
    try:
        evidence.close(failed=failed)
    finally:
        manifest["raw_workspace_retained"] = evidence.path.is_dir()
        save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--optimization", choices=("0", "1", "2"), default="0")
    parser.add_argument("--mode", action="append", choices=MODES)
    parser.add_argument("--library", type=Path)
    options = parser.parse_args()
    output = options.artifacts.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ["MINYAR_TEST_EVIDENCE"] = str(output)
    os.environ["MAKEFLAGS"] = "-j1"
    library = (options.library or ROOT / "library").resolve()
    flags = "-O" + options.optimization + " -Wno-override-module"
    if options.sanitize:
        flags += " -g -fsanitize=address,undefined -fno-omit-frame-pointer"
    env = dict(os.environ)
    for name in ("MINYAR_CLANG_FLAGS", "MINYAR_NATIVE_FLAGS", "MINYAR_RUNTIME_FLAGS"):
        env[name] = flags
    if options.sanitize:
        env["ASAN_OPTIONS"] = "detect_leaks=" + ("1" if sys.platform.startswith("linux") else "0")
        env["UBSAN_OPTIONS"] = "halt_on_error=1"
    inputs = [ROOT / "tests/quic-pto.min", ROOT / "tests/quic-pto.py",
              ROOT / "tests/tls-local.py", ROOT / "tests/test_evidence.py",
              ROOT / "tests/clang_helpers.py", ROOT / "minyar"]
    for base in ("library", "runtime", "compiler", "tools"):
        inputs += [p for p in (ROOT / base).rglob("*")
                   if p.is_file() and p.suffix in (".min", ".c", ".h", ".py", ".sh")]
    if library != ROOT / "library":
        inputs += [p for p in library.rglob("*") if p.is_file()]
    manifest = {"optimization": options.optimization, "sanitize": options.sanitize,
                "sources": {str(p): digest(p) for p in inputs}, "cases": [], "state": "running"}
    def save():
        (output / "results.json").write_text(json.dumps(manifest, indent=2) + "\n")
    save()
    evidence = Evidence("quic-pto", inputs=inputs,
                        controls={"modes": options.mode or MODES, "flags": flags, "library": str(library)})
    failed = True
    try:
        version = evidence.run(["openssl", "version"], cwd=ROOT, timeout=10, phase="openssl-version")
        if version.returncode:
            raise AssertionError("OpenSSL unavailable")
        spec = importlib.util.spec_from_file_location("pto_tls_fixtures", ROOT / "tests/tls-local.py")
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        directory = output / "certificates"
        directory.mkdir(mode=0o700)
        ca = fixtures.Certificates(directory)
        ca.root("root"); ca.leaf("server", "root"); ca.leaf("client", "root", usage="clientAuth")
        manifest["certificate_hashes"] = {p.name: digest(p) for p in directory.iterdir() if p.is_file()}
        binary = output / ("quic-pto.exe" if windows_host() else "quic-pto")
        command = [str(ROOT / "minyar"), "--library", str(library)]
        if library != ROOT / "library":
            command += ["--library", str(ROOT / "library")]
        command += [str(ROOT / "tests/quic-pto.min"), "-o", str(binary)]
        if os.name == "nt":
            bash = shutil.which("bash")
            if not bash:
                raise AssertionError("native Windows launcher requires Bash")
            command.insert(0, bash)
        result = evidence.run(command, cwd=ROOT, env=env, timeout=240, phase="compile")
        manifest["compiler_status"] = result.returncode
        save()
        if result.returncode:
            raise AssertionError(("compile", result.returncode, result.stdout[-2000:], result.stderr[-2000:]))
        manifest["binary_sha256"] = digest(binary)
        arguments = [str(ca.path("root", "der")), str(ca.path("server", "der")),
                     str(ca.path("server", "pk8")), str(ca.path("client", "der")), str(ca.path("client", "pk8"))]
        passed = True
        for mode in options.mode or MODES:
            result = evidence.run([str(binary), *arguments, mode], cwd=ROOT, env=env, timeout=120,
                                  phase="runtime-" + mode)
            expected = ("QUIC PTO " + mode + " passed\n").encode()
            normalized = result.stdout.replace(b"\r\n", b"\n") if windows_host() else result.stdout
            ok = result.returncode == 0 and normalized == expected and result.stderr == b""
            manifest["cases"].append({"mode": mode, "status": result.returncode, "passed": ok,
                                      "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                                      "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()})
            print(json.dumps(manifest["cases"][-1]), flush=True)
            passed = passed and ok
            save()
        failed = not passed
        manifest["state"] = "failed" if failed else "passed"
        return 1 if failed else 0
    except BaseException as error:
        manifest["state"] = "failed"
        manifest["error"] = repr(error)
        raise
    finally:
        manifest["source_after_mismatches"] = [name for name, value in manifest["sources"].items()
                                               if not Path(name).is_file() or digest(name) != value]
        if manifest["source_after_mismatches"]:
            manifest["state"] = "failed"
            failed = True
        preserve_observations(manifest, evidence, save, failed)
        if manifest["source_after_mismatches"]:
            raise AssertionError(("source changed during verification", manifest["source_after_mismatches"]))


if __name__ == "__main__":
    sys.exit(main())
