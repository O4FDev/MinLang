#!/usr/bin/env python3
"""Exercise the public project CLI's compiler diagnostic transport."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if not __debug__:
    raise SystemExit("diagnostic checks require Python assertions; remove -O")

binary = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="minyar project diagnostics '") as temporary:
    root = Path(temporary)
    project = root / "project"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "Minyar.toml").write_text('[package]\nname = "diagnostic-probe"\nversion = "0.1.0"\n')
    (project / "src/main.min").write_text('print("ready")\n')
    compiler = root / "compiler"
    compiler.mkdir()
    launcher = compiler / "minyar"
    launcher.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['MINYAR_FIXTURE_ARGUMENTS'], 'a') as output:
    output.write(json.dumps(args) + '\\n')
mode = os.environ['MINYAR_FIXTURE_COMPILER_MODE']
if mode != 'entry':
    if '--list-tests' in args:
        if mode == 'module-build':
            print('0\\t"an embedded test"')
            sys.exit(0)
        if mode == 'legacy': sys.exit(0)
    elif '--test-mode' not in args and not any('/tests/' in item for item in args):
        sys.exit(0)
if '--error-format' in args and args[args.index('--error-format') + 1] == 'json':
    sys.stderr.write(os.environ['MINYAR_FIXTURE_DIAGNOSTIC'])
else:
    sys.stderr.write('text compiler fixture failure\\n')
sys.exit(7)
''')
    launcher.chmod(0o755)
    arguments = root / "arguments.jsonl"
    diagnostic = {"version": 1, "severity": "error", "message": "fixture · compiler rejection", "file": str(project / "src/main.min"),
                  "line": 1, "column": 1, "endLine": 1, "endColumn": 6, "sourceLine": 'print("ready")', "label": "fixture", "help": []}
    encoded = json.dumps(diagnostic, ensure_ascii=False, separators=(",", ":")) + "\n"
    environment = dict(os.environ, MINYAR_PROJECT_DIR=str(compiler), MINYAR_HOME=str(root / "home"),
                       MINYAR_FIXTURE_ARGUMENTS=str(arguments), MINYAR_FIXTURE_DIAGNOSTIC=encoded)

    def invoke(command, *options, mode="entry"):
        arguments.unlink(missing_ok=True)
        result = subprocess.run([str(binary), command, "--manifest-path", str(project), *options], cwd=root,
                                env=dict(environment, MINYAR_FIXTURE_COMPILER_MODE=mode), text=True, capture_output=True, timeout=30)
        calls = [json.loads(line) for line in arguments.read_text().splitlines()] if arguments.exists() else []
        return result, calls

    for command in ("build", "run", "check", "test", "install"):
        for profile in ([], ["--release"]):
            result, calls = invoke(command, "--error-format", "json", *profile)
            assert result.returncode == 7 and result.stderr == encoded, (command, profile, result.stdout, result.stderr)
            assert len(calls) == 1 and calls[0][calls[0].index("--error-format") + 1] == "json", calls
    for mode in ("module-discovery", "module-build", "legacy"):
        if mode == "legacy":
            (project / "tests/failure.min").write_text('print("legacy")\n')
        result, calls = invoke("test", "--error-format", "json", mode=mode)
        assert result.returncode == 7 and result.stderr == encoded, (mode, result.stdout, result.stderr)
        assert len(calls) >= 2 and all(call[call.index("--error-format") + 1] == "json" for call in calls), calls
        (project / "tests/failure.min").unlink(missing_ok=True)
    for options, message in [(["--error-format"], "requires a value"), (["--error-format", "xml"], "text or json"),
                             (["--error-format", "json", "--error-format", "text"], "duplicate option")]:
        result, calls = invoke("check", *options)
        assert result.returncode != 0 and message in result.stderr and not calls, (options, result.stderr)
    result, calls = invoke("tree", "--error-format", "json")
    assert result.returncode != 0 and "not supported by tree" in result.stderr and not calls
    result, calls = invoke("check", "--error-format", "text")
    assert result.returncode == 7 and result.stderr == "text compiler fixture failure\n"
    result, calls = invoke("check")
    assert result.returncode == 7 and result.stderr == "text compiler fixture failure\n" and "--error-format" not in calls[0]
print("Project diagnostics: all compile routes, module discovery/build, legacy tests, exact JSON stderr/status and option validation passed")
