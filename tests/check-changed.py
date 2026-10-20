#!/usr/bin/env python3
"""Check real Git diffs, exported inputs and stale-input rejection."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent.parent / "tools/check-changed.py"


class ChangedInputs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="Minyar changed 'inputs' ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source with spaces"
        (self.root / "tools").mkdir(parents=True)
        (self.root / "library").mkdir()
        shutil.copyfile(SCRIPT, self.root / "tools/check-changed.py")
        (self.root / ".gitignore").write_text("/build/\n/target/\n__pycache__/\n*.pyc\n")
        (self.root / "library/math.min").write_text("public function value(): Integer { return 1 }\n")
        (self.root / "library/text.min").write_text('use "math" as math\n')
        (self.root / "deleted.txt").write_text("deleted\n")
        (self.root / "old name.txt").write_text("renamed\n")
        (self.root / "tools/toolchain.sh").write_text("printf 'fixture-clang\\n'\n")
        (self.root / "Makefile").write_text(
            "build/tooling/tools/check-commit: tools/fake-checker.py\n"
            "\t@mkdir -p build/tooling/tools\n"
            "\t@cp tools/fake-checker.py $@\n\t@chmod 755 $@\n")
        (self.root / "tools/fake-checker.py").write_text(
            "#!" + sys.executable + "\n"
            "import json, os, pathlib, sys\n"
            "args = sys.argv[1:]; data = {}\n"
            "for key in ('--root', '--previous', '--changes', '--rules', '--jobs'):\n"
            "    data[key] = args[args.index(key) + 1]\n"
            "data['plan'] = '--plan' in args\n"
            "data['paths'] = pathlib.Path(data['--changes']).read_bytes().decode().split('\\0')[:-1]\n"
            "data['previous'] = (pathlib.Path(data['--previous']) / 'library/text.min').read_text()\n"
            "data['make_environment'] = [key for key in ('MAKEFLAGS', 'MFLAGS', 'MAKELEVEL', 'MAKEFILES', 'GNUMAKEFLAGS') if key in os.environ]\n"
            "data['test_overrides'] = [key for key in ('MINYAR_TEST_COMPILER', 'MINYAR_TEST_MODULE_COMPILER', 'MINYAR_TEST_RUNTIME', 'MINYAR_TEST_LINK_FLAGS') if key in os.environ]\n"
            "data['clang'] = os.environ.get('MINYAR_TEST_CLANG')\n"
            "data['scale'] = os.environ.get('MINYAR_TEST_TIMEOUT_SCALE')\n"
            "print(json.dumps(data))\n"
            "if os.environ.get('CHANGE_DURING_CHECK'):\n"
            "    pathlib.Path('library/math.min').write_text('changed during check')\n"
            "sys.exit(int(os.environ.get('CHECKER_EXIT', '0')))\n")
        self.environment = os.environ.copy()
        for name in list(self.environment):
            if name.startswith("GIT_") or name in ("CHECK_CHANGED_INPUT", "CHECK_CHANGED_BASE", "MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEFILES", "GNUMAKEFLAGS"):
                self.environment.pop(name, None)
        self.environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "-q")
        self.git("config", "user.name", "Changed Inputs")
        self.git("config", "user.email", "changed-inputs@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        self.git("add", ".")
        self.git("commit", "-qm", "initial fixture")

    def run_command(self, command, *, environment=None):
        return subprocess.run([str(part) for part in command], cwd=self.root,
                              env=environment or self.environment, capture_output=True, timeout=60)

    def git(self, *arguments):
        result = self.run_command(["git", *arguments])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def invoke(self, *arguments, expected=0, environment=None):
        result = self.run_command([sys.executable, "tools/check-changed.py", *arguments], environment=environment)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def export(self):
        self.invoke("--export", "target/changes")
        return self.root / "target/changes"

    def rejection(self, text):
        result = self.invoke("--input", "target/changes", "--plan", expected=1)
        self.assertIn(text, result.stderr.decode())
        self.assertFalse((self.root / "build").exists(), "invalid inputs must fail before building")

    def test_staged_unstaged_untracked_deleted_and_renamed_paths(self):
        (self.root / "library/math.min").write_text("staged\n")
        self.git("add", "library/math.min")
        (self.root / "library/math.min").write_text("unstaged\n")
        (self.root / "library/text.min").write_text("removed import\n")
        self.git("rm", "deleted.txt")
        renamed = "new name\nwith newline.txt"
        self.git("mv", "old name.txt", renamed)
        (self.root / "untracked\nfile.min").write_text("untracked\n")
        index = (self.root / ".git/index").read_bytes()
        result = self.invoke("--plan")
        data = json.loads(result.stdout)
        self.assertEqual(set(data["paths"]), {"library/math.min", "library/text.min", "deleted.txt", "old name.txt", renamed, "untracked\nfile.min"})
        self.assertEqual(data["previous"], 'use "math" as math\n')
        self.assertTrue(data["plan"])
        self.assertEqual(data["make_environment"], [])
        self.assertEqual((self.root / ".git/index").read_bytes(), index)
        self.assertEqual((self.root / "library/math.min").read_text(), "unstaged\n")

    def test_explicit_base_includes_committed_work_and_export_ignores_attributes(self):
        base = self.git("rev-parse", "HEAD").decode().strip()
        (self.root / ".gitattributes").write_text("library/text.min export-ignore\n")
        self.git("add", ".gitattributes")
        self.git("commit", "-qm", "archive attributes")
        base = self.git("rev-parse", "HEAD").decode().strip()
        (self.root / "library/math.min").write_text("committed\n")
        self.git("add", "library/math.min")
        self.git("commit", "-qm", "changed module")
        data = json.loads(self.invoke("--base", base, "--plan").stdout)
        self.assertEqual(data["paths"], ["library/math.min"])
        self.assertEqual(data["previous"], 'use "math" as math\n')

    def test_export_runs_without_git_and_reuses_build_outputs(self):
        self.export()
        self.assertFalse((self.root / "build").exists())
        shutil.rmtree(self.root / ".git")
        first = json.loads(self.invoke("--input", "target/changes", "--plan").stdout)
        self.assertEqual(first["paths"], [])
        checker = self.root / "build/tooling/tools/check-commit"
        modified = checker.stat().st_mtime_ns
        (self.root / "target/generated").write_text("generated output")
        self.invoke("--input", "target/changes")
        self.assertEqual(checker.stat().st_mtime_ns, modified)

    def test_invalid_base_is_an_error(self):
        result = self.invoke("--base", "missing-ref", "--plan", expected=128)
        self.assertIn("check-changed:", result.stderr.decode())
        self.assertFalse((self.root / "build").exists())

    def test_stale_content_is_rejected(self):
        self.export()
        (self.root / "library/math.min").write_text("new source\n")
        self.rejection("source differs")

    def test_new_source_is_rejected(self):
        self.export()
        (self.root / "new.min").write_text("new source\n")
        self.rejection("source differs")

    def test_deleted_source_is_rejected(self):
        self.export()
        (self.root / "library/math.min").unlink()
        self.rejection("source differs")

    def test_changed_executable_mode_is_rejected(self):
        self.export()
        path = self.root / "library/math.min"
        path.chmod(path.stat().st_mode | 0o111)
        self.rejection("source differs")

    def test_changed_path_list_is_rejected(self):
        inputs = self.export()
        (inputs / "changed-paths").write_bytes(b"library/math.min\0")
        self.rejection("changed paths were modified")

    def test_changed_previous_module_is_rejected(self):
        inputs = self.export()
        (inputs / "previous/library/text.min").write_text("hidden old import\n")
        self.rejection("previous modules were modified")

    def test_unknown_manifest_schema_is_rejected(self):
        inputs = self.export()
        manifest = json.loads((inputs / "manifest.json").read_text())
        manifest["schema"] = 99
        (inputs / "manifest.json").write_text(json.dumps(manifest))
        self.rejection("unsupported changed-check manifest")

    def test_failure_and_source_changes_during_checks_are_not_passes(self):
        self.export()
        self.invoke("--input", "target/changes", expected=37,
                    environment=dict(self.environment, CHECKER_EXIT="37"))
        result = self.invoke("--input", "target/changes", expected=1,
                             environment=dict(self.environment, CHANGE_DURING_CHECK="1"))
        self.assertIn("source differs", result.stderr.decode())

    def test_foreign_git_environment_does_not_select_another_repository(self):
        foreign = Path(self.temporary.name) / "foreign"
        foreign.mkdir()
        subprocess.run(["git", "init", "-q", str(foreign)], env=self.environment, check=True)
        environment = dict(self.environment, GIT_DIR=str(foreign / ".git"), GIT_WORK_TREE=str(foreign),
                           GIT_INDEX_FILE=str(foreign / ".git/index"))
        (self.root / "library/math.min").write_text("working source\n")
        data = json.loads(self.invoke("--plan", environment=environment).stdout)
        self.assertEqual(data["paths"], ["library/math.min"])

    def test_stale_test_overrides_are_cleared_and_limits_preserved(self):
        environment = dict(self.environment, MINYAR_TEST_COMPILER="/stale/compiler",
                           MINYAR_TEST_MODULE_COMPILER="/stale/module-compiler", MINYAR_TEST_RUNTIME="/stale/runtime",
                           MINYAR_TEST_LINK_FLAGS="-stale", MINYAR_TEST_CLANG="stale-clang", LLVM_CC="chosen-clang",
                           MINYAR_TEST_TIMEOUT_SCALE="3", MAKEFLAGS="--invalid", MFLAGS="--invalid",
                           MAKELEVEL="99", MAKEFILES="missing.mk", GNUMAKEFLAGS="--invalid")
        data = json.loads(self.invoke("--plan", environment=environment).stdout)
        self.assertEqual(data["test_overrides"], [])
        self.assertEqual(data["make_environment"], [])
        self.assertEqual(data["clang"], "chosen-clang")
        self.assertEqual(data["scale"], "3")

    def test_external_source_symlinks_are_rejected(self):
        external = Path(self.temporary.name) / "external.min"
        external.write_text("untracked external source\n")
        (self.root / "library/external.min").symlink_to(external)
        result = self.invoke("--export", "target/changes", expected=1)
        self.assertIn("source symlinks require explicit checks", result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
