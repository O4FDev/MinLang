"""Focused project bundling and declarative AppKit integration checks."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(arguments, *, cwd=ROOT, status=0, environment=None, timeout=180):
    result = subprocess.run(
        [str(value) for value in arguments], cwd=cwd, env=environment,
        text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, check=False,
    )
    if result.returncode != status:
        raise AssertionError(f"{arguments}: expected {status}, got {result.returncode}\n{result.stdout}\n{result.stderr}")
    if "Unable to simultaneously satisfy constraints" in result.stderr:
        raise AssertionError(result.stderr)
    return result


def check_cli():
    tool = ROOT / "build/tooling/tools/application-cli"
    result = run([tool, "--help"])
    assert "minyar app" in result.stdout and "--sign IDENTITY" in result.stdout
    for options, message in [
        (["--unknown"], "unknown app option"),
        (["--release", "--release"], "duplicate option"),
        (["--sign"], "requires a value"),
        (["--sign", ""], "requires a value"),
        (["--icon", "--release"], "requires a value"),
        (["--bundle-id", ""], "requires a value"),
        (["unexpected"], "unknown app option"),
    ]:
        assert message in run([tool, *options], status=1).stderr
    if sys.platform != "darwin":
        assert "currently requires macOS" in run([tool], status=1).stderr
        print("Application CLI help, option errors and unsupported-platform diagnostic verified")
        return

    with tempfile.TemporaryDirectory(prefix="minyar app ' é ") as directory:
        project = Path(directory)
        (project / "src").mkdir()
        (project / "src/main.min").write_text('print("A bundled light 🙂")\n', encoding="utf-8")
        (project / "Minyar.toml").write_text('[package]\nname = "little_light"\nversion = "0.1.0"\nkind = "bin"\n', encoding="utf-8")
        resources = project / "resources"
        resources.mkdir()
        (resources / "note.txt").write_text("a resource é", encoding="utf-8")
        launcher = ROOT / "minyar"
        # Use the public launcher, real project builder and real signer.
        run([launcher, "app", "--resources", resources], cwd=project, timeout=600)
        bundle = project / "target/debug/little_light.app"
        info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
        assert info["CFBundleIdentifier"] == "org.minyar.little-light"
        assert (bundle / "Contents/Resources/note.txt").read_text(encoding="utf-8") == "a resource é"
        assert run([bundle / "Contents/MacOS/application"]).stdout == "A bundled light 🙂\n"
        run(["/usr/bin/codesign", "--verify", "--strict", bundle])
        before = {str(path.relative_to(bundle)): path.read_bytes() for path in bundle.rglob("*") if path.is_file()}
        failed = run([launcher, "app", "--sign", "Minyar deliberately missing test certificate"], cwd=project, status=1, timeout=600)
        assert "application packaging failed" in failed.stderr
        after = {str(path.relative_to(bundle)): path.read_bytes() for path in bundle.rglob("*") if path.is_file()}
        assert before == after, "failed signing changed the previous app"
        run([launcher, "app", "--manifest-path", project / "Minyar.toml", "--release", "--bundle-id", "org.minyar.release", "--sign", "-"], timeout=600)
        release = project / "target/release/little_light.app"
        assert plistlib.loads((release / "Contents/Info.plist").read_bytes())["CFBundleIdentifier"] == "org.minyar.release"
        run(["/usr/bin/codesign", "--verify", "--strict", release])
        print("Project app builds, debug/release, resources, Unicode paths, signatures and signing rollback verified")


def check_ui(clang):
    if sys.platform != "darwin":
        print("Declarative AppKit integration skipped: requires macOS with a GUI session")
        return
    os.environ["MINYAR_CLANG"] = clang
    with tempfile.TemporaryDirectory(prefix="minyar-ui-") as directory:
        for profile in ["--debug", "--release"]:
            binary = Path(directory) / ("ui" + profile)
            run([ROOT / "minyar", profile, "--native-source", f"uitest={ROOT / 'tests/ui-macos-events.m'}", ROOT / "tests/ui-macos.min", "-o", binary], timeout=600)
            output = run([binary]).stdout
            assert output == "Declarative AppKit events, Unicode, 200 retained updates, rebuild and closure verified\n"
            for mode, expected in [("invalid", "control keys must be unique"), ("disposed", "has been disposed"), ("multiple", "dispose the current declarative window")]:
                assert expected in run([binary, mode], status=1).stderr
        # Exercise the actual gallery entry and project demo's bounded launch.
        binary = Path(directory) / "harbour"
        run([ROOT / "minyar", ROOT / "examples/gallery/desktop.min", "-o", binary], timeout=600)
        assert run([binary, "--smoke"]).stdout == "Minyar → AppKit 🙂\n42 lights; native editor retained\n"
        print("Declarative AppKit and Harbour gallery verified at debug/release")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["cli", "ui"])
    parser.add_argument("--clang", default="clang")
    arguments = parser.parse_args()
    if arguments.mode == "cli":
        check_cli()
    else:
        check_ui(arguments.clang)
