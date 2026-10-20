#!/usr/bin/env python3
"""Check real Git diffs, exported inputs and stale-input rejection."""
import errno
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parent.parent / "tools/check-changed.py"


def write_lf(path, contents):
    path.write_bytes(contents.encode("utf-8"))


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
        write_lf(self.root / "tools/toolchain.sh", "printf 'fixture-clang\\n'\n")
        write_lf(self.root / "Makefile",
            "build/tooling/tools/check-commit: tools/fake-checker.py\n"
            "\t@mkdir -p build/tooling/tools\n"
            "\t@cp tools/fake-checker.py $@\n\t@chmod 755 $@\n")
        write_lf(self.root / "tools/fake-checker.py",
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
        write_lf(self.root / "tools/check-changed-entry.py",
            "import pathlib, runpy, subprocess, sys\n"
            "root = pathlib.Path(__file__).resolve().parent.parent\n"
            "checker = str(root / 'build/tooling/tools/check-commit')\n"
            "original_run = subprocess.run; adapted = 0\n"
            "def fixture_run(command, *arguments, **options):\n"
            "    global adapted\n"
            "    if isinstance(command, (list, tuple)) and command and command[0] == checker:\n"
            "        adapted += 1\n"
            "        command = [sys.executable, *command]\n"
            "    return original_run(command, *arguments, **options)\n"
            "subprocess.run = fixture_run\n"
            "try:\n"
            "    runpy.run_path(str(root / 'tools/check-changed.py'), run_name='__main__')\n"
            "finally:\n"
            "    sys.stderr.write('fixture checker adapter calls: ' + str(adapted) + '\\n')\n")
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

    def invoke(self, *arguments, expected=0, environment=None, fixture_adapter=False):
        # Native Windows cannot directly execute the Python text fake checker.
        # The exact fixture path is adapted in a child; production stays unchanged.
        entry = "tools/check-changed-entry.py" if os.name == "nt" or fixture_adapter else "tools/check-changed.py"
        result = self.run_command([sys.executable, entry, *arguments], environment=environment)
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
        renamed = "new name with spaces.txt"
        self.git("mv", "old name.txt", renamed)
        (self.root / "untracked file.min").write_text("untracked\n")
        index = (self.root / ".git/index").read_bytes()
        result = self.invoke("--plan")
        data = json.loads(result.stdout)
        self.assertEqual(set(data["paths"]), {"library/math.min", "library/text.min", "deleted.txt", "old name.txt", renamed, "untracked file.min"})
        self.assertEqual(data["previous"], 'use "math" as math\n')
        self.assertTrue(data["plan"])
        self.assertEqual(data["make_environment"], [])
        self.assertEqual((self.root / ".git/index").read_bytes(), index)
        self.assertEqual((self.root / "library/math.min").read_text(), "unstaged\n")

    @unittest.skipIf(os.name == "nt", "native Windows reserves newline (U+000A) in filenames")
    def test_newline_paths_preserve_nul_delimiting(self):
        renamed = "new name\nwith newline.txt"
        untracked = "untracked\nfile.min"
        self.git("mv", "old name.txt", renamed)
        (self.root / untracked).write_text("untracked\n")
        index = (self.root / ".git/index").read_bytes()
        data = json.loads(self.invoke("--plan").stdout)
        self.assertEqual(set(data["paths"]), {"old name.txt", renamed, untracked})
        self.assertEqual((self.root / ".git/index").read_bytes(), index)
        self.assertEqual((self.root / untracked).read_text(), "untracked\n")

    def test_forced_checker_adapter_preserves_arguments_and_failure(self):
        result = self.invoke("--plan", "--jobs", "3", expected=37, fixture_adapter=True,
                             environment=dict(self.environment, CHECKER_EXIT="37"))
        data = json.loads(result.stdout)
        self.assertEqual(data["--root"], str(self.root.resolve()))
        self.assertEqual(data["--jobs"], "3")
        self.assertTrue(data["plan"])
        self.assertEqual(data["paths"], [])
        self.assertEqual(result.stderr.splitlines().count(b"fixture checker adapter calls: 1"), 1)

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

    def test_source_change_after_path_collection_is_rejected(self):
        spec = importlib.util.spec_from_file_location("check_changed_capture_race", self.root / "tools/check-changed.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_git = module.git
        mutations = []

        def collect_then_change(root, *arguments):
            result = original_git(root, *arguments)
            if arguments[0] == "ls-files":
                # The path list is already collected; no sleep or scheduler race.
                (self.root / "tools/new-helper.min").write_text("new source after selection\n")
                mutations.append(True)
            return result

        inputs = Path(self.temporary.name) / "racing-export"
        inputs.mkdir()
        with mock.patch.dict(os.environ, self.environment, clear=True):
            with mock.patch.object(module, "git", side_effect=collect_then_change):
                with self.assertRaisesRegex(ValueError, "source changed while exporting"):
                    module.capture(self.root, "HEAD", inputs)
        self.assertEqual(mutations, [True], "the mutation must follow exactly one path collection")
        self.assertFalse((inputs / "manifest.json").exists(), "a racing capture must not publish a manifest")
        self.assertFalse((self.root / "build").exists(), "capture must not build the planner")

    def test_deleted_source_is_rejected(self):
        self.export()
        (self.root / "library/math.min").unlink()
        self.rejection("source differs")

    def test_changed_executable_mode_is_rejected(self):
        self.export()
        path = self.root / "library/math.min"
        mode = path.stat().st_mode
        executable = bool(mode & 0o111)
        path.chmod(mode & ~0o111 if executable else mode | 0o111)
        if bool(path.stat().st_mode & 0o111) == executable:
            self.skipTest("this filesystem/Python exposes no executable-bit transition")
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
        link = self.root / "library/external.min"
        try:
            link.symlink_to(external)
        except NotImplementedError as error:
            self.skipTest("real symlink creation is unavailable: " + str(error))
        except OSError as error:
            unsupported = {getattr(errno, name, None) for name in ("ENOSYS", "ENOTSUP", "EOPNOTSUPP")}
            unsupported.discard(None)
            if error.errno in unsupported or (os.name == "nt" and getattr(error, "winerror", None) == 1314):
                self.skipTest("real symlink creation is unsupported or lacks Windows privilege: " + str(error))
            raise
        self.assertTrue(link.is_symlink(), "the fixture must create a genuine symlink, not a copy")
        result = self.invoke("--export", "target/changes", expected=1)
        self.assertIn("source symlinks require explicit checks", result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
