#!/usr/bin/env python3
"""Interactive bootstrap scheduling preserves the development resource caps.

Taskpolicy is replaced only in disposable script copies so these tests inspect
arguments and inherited limits without changing the host's scheduling policy.
The public launcher test uses fake build/compiler tools; the separate cold
bootstrap gate provides real toolchain, caching, release and spaced-path checks.
"""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ZSH = shutil.which("zsh")


@unittest.skipUnless(ZSH and os.name != "nt", "POSIX launcher and zsh limits required")
class BootstrapScheduling(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="minyar bootstrap policy ")
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.log = self.work / "policy.json"
        policy = self.work / "fake taskpolicy"
        policy.write_text("#!" + sys.executable + "\n" + """import json,os,sys
from pathlib import Path
args=sys.argv[1:]
if os.environ.get('POLICY_NO_MEMORY') == '1' and '-m' in args:
    sys.exit(64)
Path(os.environ['POLICY_LOG']).write_text(json.dumps(args))
while args and args[0].startswith('-'):
    option=args.pop(0)
    if option in ('-m','-c'): args.pop(0)
os.execvp(args[0],args)
""")
        policy.chmod(0o755)
        self.wrappers = {}
        for name in ("with-limits.sh", "with-sanitizer-limits.sh"):
            wrapper = self.work / name
            wrapper.write_text((ROOT / "scripts" / name).read_text().replace(
                "/usr/sbin/taskpolicy", shlex.quote(str(policy))))
            self.wrappers[name] = wrapper
        self.environment = dict(os.environ, POLICY_LOG=str(self.log))
        self.environment.pop("MINYAR_INTERACTIVE_BOOTSTRAP", None)
        self.payload = self.work / "payload with spaces.py"
        self.payload.write_text("import json,os,resource\nprint(json.dumps({"
                                "'cpu':resource.getrlimit(resource.RLIMIT_CPU),"
                                "'file':resource.getrlimit(resource.RLIMIT_FSIZE),"
                                "'priority':os.getpriority(os.PRIO_PROCESS,0)}))\n")

    def invoke(self, name, **environment):
        result = subprocess.run([ZSH, str(self.wrappers[name]), sys.executable,
                                 str(self.payload)], env=dict(self.environment, **environment),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.log.read_text()), json.loads(result.stdout)

    def test_bulk_checks_keep_background_policy(self):
        for name in self.wrappers:
            with self.subTest(wrapper=name):
                args, limits = self.invoke(name)
                self.assertEqual(args[:5], ["-b", "-c", "background", "-m", "768"])
                self.assertIn("15", args)
                self.assertEqual(limits["cpu"][0], 240)

    def test_interactive_bootstrap_uses_normal_qos_with_the_same_caps(self):
        for name in self.wrappers:
            with self.subTest(wrapper=name):
                args, limits = self.invoke(name, MINYAR_INTERACTIVE_BOOTSTRAP="1")
                self.assertEqual(args[:2], ["-m", "768"])
                self.assertNotIn("-b", args)
                self.assertNotIn("background", args)
                self.assertEqual(limits["cpu"][0], 240)
                self.assertLessEqual(limits["file"][0], 262144 * 1024)
                self.assertGreaterEqual(limits["priority"], 15)

    def test_foreground_context_retains_custom_caps(self):
        for name in self.wrappers:
            with self.subTest(wrapper=name):
                args, limits = self.invoke(name, MINYAR_INTERACTIVE_BOOTSTRAP="1",
                    MINYAR_MAX_CPU_SECONDS="17", MINYAR_MAX_MEMORY_MIB="96",
                    MINYAR_MAX_FILE_BLOCKS="19", MINYAR_NICE_PRIORITY="0")
                self.assertEqual(args[:2], ["-m", "96"])
                self.assertEqual(limits["cpu"][0], 17)
                self.assertLessEqual(limits["file"][0], 19 * 1024)

    def test_context_cannot_raise_an_inherited_hard_cpu_cap(self):
        for name in self.wrappers:
            with self.subTest(wrapper=name):
                command = [ZSH, "-c", 'ulimit -SH -t 2; exec "$@"', "nested",
                           ZSH, str(self.wrappers[name]), sys.executable, str(self.payload)]
                result = subprocess.run(command,
                    env=dict(self.environment, MINYAR_INTERACTIVE_BOOTSTRAP="1"),
                    capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.log.exists(), "policy must not run after a cap failure")

    def test_older_taskpolicy_keeps_scheduling_cpu_and_file_limits(self):
        for name in self.wrappers:
            for interactive in ('0', '1'):
                with self.subTest(wrapper=name, interactive=interactive):
                    args, limits = self.invoke(name, POLICY_NO_MEMORY='1',
                                              MINYAR_INTERACTIVE_BOOTSTRAP=interactive)
                    self.assertNotIn('-m', args)
                    self.assertEqual('-b' in args, interactive == '0')
                    self.assertEqual(limits['cpu'][0], 240)
                    self.assertLessEqual(limits['file'][0], 262144 * 1024)
                    self.assertGreaterEqual(limits['priority'], 15)

    def test_public_launcher_scopes_context_to_bootstrap(self):
        project = self.work / "project with spaces"
        (project / "tools").mkdir(parents=True)
        (project / "build").mkdir()
        shutil.copy2(ROOT / "minyar", project / "minyar")
        compiler = project / "build/minyarc"
        compiler.write_text("#!" + sys.executable + "\nimport pathlib,sys\n"
                            "pathlib.Path(sys.argv[2]).write_text('; mock IR\\n')\n")
        compiler.chmod(0o755)
        (project / "tools/clang-driver.py").write_text("""import json,os,sys
from pathlib import Path
with Path(os.environ['POLICY_LOG']).open('a') as stream:
    stream.write(json.dumps({'command':sys.argv[1],
      'context':os.environ.get('MINYAR_INTERACTIVE_BOOTSTRAP')})+'\\n')
if sys.argv[1]=='link': Path(sys.argv[5]).write_text('fake output')
""")
        source = project / "source with spaces.min"
        source.write_text("print(42)\n")
        for options in (("--check",), ("--release", "--memory-profile", "eager")):
            with self.subTest(options=options):
                self.log.unlink(missing_ok=True)
                result = subprocess.run([str(project / "minyar"), *options, str(source)],
                    cwd=self.work, env=self.environment, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = [json.loads(line) for line in self.log.read_text().splitlines()]
                self.assertEqual(rows[0], {"command": "build", "context": "1"})
                self.assertTrue(all(row["context"] is None for row in rows[1:]),
                                "bootstrap context must not leak into program linking")


if __name__ == "__main__":
    unittest.main()
