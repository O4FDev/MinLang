#!/usr/bin/env python3
"""Exercise the shipped archive with a fresh HOME and no developer tools on PATH."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from distribution_probes import lsp_roundtrip, project_diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distribution", type=Path, required=True, help="extracted distribution directory")
    args = parser.parse_args()
    distribution = args.distribution.resolve()
    metadata = json.loads((distribution / "distribution.json").read_text())
    for path, expected in metadata["files"].items():
        actual = hashlib.sha256((distribution / path).read_bytes()).hexdigest()
        assert actual == expected, f"release file checksum mismatch: {path}"
    for frontend in (distribution / "tools").glob("*-cli.min"):
        assert (distribution / "build/tooling/tools" / frontend.stem).is_file(), f"release is missing {frontend.stem}"
    print("Release manifest verified", flush=True)
    with tempfile.TemporaryDirectory(prefix="minyar clean install '") as temporary:
        work = Path(temporary)
        home = work / "home"
        home.mkdir()
        prefix = home / "prefix with spaces and ' quote"
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "SHELL": "/bin/zsh", "TMPDIR": str(work), "LC_ALL": "C"}
        # A developer SDK remains an explicit platform prerequisite. Nothing
        # else is inherited (no LLVM cache, Homebrew, CC, compiler flags or PATH).
        if os.environ.get("SDKROOT"):
            env["SDKROOT"] = os.environ["SDKROOT"]

        def run(*command, cwd=work, expected=0, environment=env):
            result = subprocess.run([str(arg) for arg in command], cwd=cwd, env=environment,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            if result.returncode != expected:
                raise AssertionError(f"{command}: exit {result.returncode}, expected {expected}\n{result.stdout}")
            assert "argument unused during compilation: '--ld-path=" not in result.stdout, result.stdout
            return result.stdout

        # Missing SDK must be diagnosed before the native tools or shell files
        # are touched; --check never launches Apple's installation dialog.
        missing_sdk = dict(env, SDKROOT=str(work / "no SDK"), DEVELOPER_DIR=str(work / "no Xcode"))
        message = run("/bin/sh", distribution / "install.sh", "--check", environment=missing_sdk, expected=2)
        assert "Apple macOS SDK" in message
        assert not (home / ".zshrc").exists()
        print("Missing-SDK diagnostics passed", flush=True)
        # The archive itself can be placed anywhere, and can be read-only.
        before = {str(path.relative_to(distribution)): path.stat().st_mtime_ns for path in distribution.rglob("*")}
        run("/bin/sh", distribution / "install.sh", "--prefix", prefix)
        command = prefix / "bin/minyar"
        run(command, "--doctor")
        run(command, "new", work / "hello")
        project = work / "hello"
        if (distribution / "tools/lsp-cli.min").is_file():
            lsp_roundtrip(command, project, env)
        assert "Hello, world!" in run(command, "run", cwd=project)
        run(command, "test", cwd=project)
        run(command, "run", "--release", cwd=project)
        if "--error-format" in (distribution / "minyar").read_text():
            project_diagnostics(command, project, env)
        if (distribution / "tools/module-tests.min").is_file():
            module = project / "src/invariant.min"
            module.write_text('function answer(): Integer { return 42 }\nprint("application statement must stay excluded")\ntest "archive invariant" {\n    expect(answer() == 42)\n    print("archive module test passed")\n}\n')
            for options in ([], ["--release"]):
                report = run(command, "test", *options, cwd=project)
                assert "archive module test passed" in report and "archive invariant" in report
                assert "application statement must stay excluded" not in report
            module.unlink()
        if (distribution / "tools/format-cli.min").is_file():
            source = project / "src/main.min"
            source.write_text('function greet(){print("Hello, world!")}\ngreet()\n')
            expected = 'function greet() {\n    print("Hello, world!")\n}\ngreet()\n'
            assert run(command, "fmt", "--stdout", source) == expected
            run(command, "fmt", source)
            assert source.read_text() == expected
            run(command, "fmt", "--check", source)
            assert "Hello, world!" in run(command, "run", cwd=project)
        print("Fresh-home installation and debug/release project workflows passed", flush=True)
        assert (project / "target/debug/hello.dSYM").is_dir(), "debug symbols must survive staging cleanup"
        (project / "src/main.min").write_text('use "system" as system\nprint(system.processId() > 0)\n')
        assert "true" in run(command, "run", cwd=project)
        assert "true" in run(command, "run", "--release", cwd=project)
        source = project / "src/main.min"
        for profile in ("eager", "fixed", "lazy", "system"):
            run(command, "--memory-profile", profile, source, "-o", work / profile)
            assert "true" in run(work / profile)
        (project / "src/main.min").write_text('use "macos" as macos\nmacos.initialize("Install check")\n')
        # Compile/package an actual AppKit program without opening a window.
        run(command, "--app", source, "-o", work / "Install Check.app")
        assert (work / "Install Check.app/Contents/Info.plist").is_file()
        print("Native providers, memory profiles and AppKit packaging passed", flush=True)
        profile = (home / ".zshrc").read_text()
        assert "Minyar PATH" in profile
        assert run("/bin/zsh", "-ic", "command -v minyar").strip().endswith("/bin/minyar")
        # Reinstallation must be idempotent; an unrelated command is protected.
        run("/bin/sh", distribution / "install.sh", "--prefix", prefix)
        assert (home / ".zshrc").read_text() == profile
        unrelated = home / "unrelated"
        (unrelated / "bin").mkdir(parents=True)
        (unrelated / "bin/minyar").write_text("#!/bin/sh\necho unrelated\n")
        refused = run(distribution / "build/tooling/tools/install-cli", "--source", distribution,
                      "--prefix", unrelated, expected=1)
        assert "unrelated command" in refused
        assert "unrelated" in (unrelated / "bin/minyar").read_text()
        after = {str(path.relative_to(distribution)): path.stat().st_mtime_ns for path in distribution.rglob("*")}
        assert before == after, "running the release must never write into the distribution"
        # Delete both the archive source and the old installed version. Only the
        # new installation and its own bundled LLVM may supply the toolchain.
        versions = sorted((prefix / "lib/minyar/versions").iterdir(), key=lambda path: path.stat().st_mtime_ns)
        assert len(versions) == 2
        for directory, _, _ in os.walk(versions[0]):
            Path(directory).chmod(0o700)
        shutil.rmtree(versions[0])
        hidden = distribution.with_name(distribution.name + ".hidden")
        distribution_mode = distribution.stat().st_mode
        # macOS requires write permission on the directory being renamed too.
        distribution.chmod(distribution_mode | 0o200)
        distribution.rename(hidden)
        try:
            shutil.rmtree(project / "target")
            shutil.rmtree(home / "Library/Caches/minyar", ignore_errors=True)
            (project / "src/main.min").write_text('use "system" as system\nprint("standalone")\nprint(system.processId() > 0)\n')
            assert "standalone" in run(command, "run", cwd=project)
            run(command, "run", "--release", cwd=project)
            run(command, "test", cwd=project)
        finally:
            hidden.rename(distribution)
            distribution.chmod(distribution_mode)
    print("macOS distribution: clean install, SDK diagnostics, debug/release, native providers, memory profiles, app packaging, PATH, upgrades and relocation passed")


if __name__ == "__main__":
    main()
