"""Optional frozen evidence and portable pipe drains for QUIC author tests."""
import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import shutil
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
from clang_helpers import windows_host
from test_evidence import Evidence, terminate_process_tree


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(data):
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


class ProtocolArtifacts:
    def __init__(self, label, requested, *, inputs=(), declared_cases=()):
        self.declared_cases = list(declared_cases)
        self.temporary = None
        self.endpoint_commands = []
        self.fixture_modules = []
        self.report = None
        self.shared_fixtures = []
        self.case_files = {case:{} for case in self.declared_cases}
        self.passed = False
        self.inputs = {str(Path(p).resolve()): digest(p) for p in inputs}
        self.evidence = None
        if requested is None:
            self.temporary = tempfile.TemporaryDirectory(prefix=label + "-")
            self.workspace = Path(self.temporary.name)
            self.path = None
        else:
            requested = Path(requested)
            if not requested.is_absolute() or requested.exists():
                raise ValueError("--artifacts requires a fresh absolute path")
            requested.mkdir(parents=True)
            self.path = requested.resolve()
            self.workspace = self.path / "fixtures"
            self.workspace.mkdir()
            self.evidence = Evidence(label, inputs=inputs)
            self.evidence.path.rmdir()
            self.evidence.path = self.path

    def _recorded_run(self, command, *, timeout, case=None, phase="protocol-case",
                      capture_output=True, text=False, check=False, cwd=None,
                      env=None, input=None):
        command = list(map(str, command))
        directory = str(Path(cwd or Path.cwd()).resolve())
        effective_env = os.environ if env is None else env
        executable = shutil.which(command[0], path=effective_env.get("PATH")) if not os.path.dirname(command[0]) else str((Path(directory)/command[0]).resolve())
        row = {"command":command,"cwd":directory,"timeout":timeout,"phase":phase,"case":case,
               "executable":executable,"executable_sha256":digest(executable) if executable else None,
               "stdout_captured":capture_output,"stderr_captured":capture_output,
               "stdin":{"mode":"input" if input is not None else "eof"},
               "timed_out":False}
        self.evidence.commands.append(row)
        started = time.monotonic()
        data = input.encode("utf-8") if text and input is not None else input
        try:
            with subprocess.Popen(command, cwd=directory, env=env,
                                  stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                                  stdout=subprocess.PIPE if capture_output else None,
                                  stderr=subprocess.PIPE if capture_output else None,
                                  start_new_session=not windows_host()) as process:
                try:
                    out, err = process.communicate(input=data, timeout=timeout)
                except subprocess.TimeoutExpired:
                    row["timed_out"] = True
                    terminate_process_tree(process)
                    out, err = process.communicate(timeout=10)
                row.update(returncode=process.returncode,
                           stdout_base64=base64.b64encode(out or b"").decode("ascii"),
                           stderr_base64=base64.b64encode(err or b"").decode("ascii"))
                if row["timed_out"]:
                    raise subprocess.TimeoutExpired(command, timeout, output=out, stderr=err)
                result = subprocess.CompletedProcess(command,process.returncode,
                    globals()["text"](out) if text and out is not None else out,
                    globals()["text"](err) if text and err is not None else err)
                if check:
                    result.check_returncode()
                return result
        except BaseException as error:
            row["exception"] = type(error).__name__
            raise
        finally:
            row["elapsed_seconds"] = time.monotonic()-started

    def fixture(self, module):
        if self.evidence is None:
            return
        original = module.subprocess
        def run(command, **kwargs):
            return self._recorded_run(command, phase="certificate-fixture", **kwargs)
        def check_output(command, **kwargs):
            return self._recorded_run(command, check=True, phase="certificate-fixture", **kwargs).stdout
        # Only this separately loaded certificate fixture delegates recording.
        module.subprocess = SimpleNamespace(run=run, check_output=check_output)
        self.fixture_modules.append((module, original))

    def certificates_ready(self):
        self.shared_fixtures = sorted(p for p in self.workspace.iterdir() if p.is_file())

    def bind_files(self, case, role, paths):
        self.case_files[case][role] = list(map(Path, paths))

    def run(self, command, *, timeout, case=None, **kwargs):
        if self.evidence is None:
            return subprocess.run(command, timeout=timeout, **kwargs)
        return self._recorded_run(command, timeout=timeout, case=case, **kwargs)

    def endpoint(self, command, stem, *, case, peer_timeout):
        return EndpointProcess(self, command, self.workspace / stem, case, peer_timeout)

    def _persist_commands(self):
        for index, row in enumerate(self.evidence.commands):
            row["status"] = row.get("returncode")
            for stream in ("stdout", "stderr"):
                encoded = row.pop(stream + "_base64", None)
                if encoded is not None:
                    path = self.path / ("command-" + str(index).zfill(3) + "." + stream + ".bin")
                    path.write_bytes(base64.b64decode(encoded))
                    row[stream + "_path"] = str(path)
                    row[stream + "_sha256"] = digest(path)
                    row[stream + "_bytes"] = path.stat().st_size

    def _case_inventory(self):
        def paths(values):
            found = []
            for value in values:
                candidates = value.rglob("*") if value.is_dir() else [value]
                found.extend(p.relative_to(self.path).as_posix() for p in candidates if p.is_file() and not p.is_symlink())
            return sorted(set(found))
        result = []
        for case in self.declared_cases:
            commands = [i for i,row in enumerate(self.evidence.commands) if row.get("case")==case or row.get("phase")=="certificate-fixture"]
            endpoints = [i for i,row in enumerate(self.endpoint_commands) if row.get("case")==case]
            roles = {"certificates":paths(self.shared_fixtures)}
            roles.update({role:paths(values) for role,values in self.case_files[case].items()})
            raw = []
            for row in [self.evidence.commands[i] for i in commands]+[self.endpoint_commands[i] for i in endpoints]:
                raw.extend(Path(row[name+"_path"]) for name in ("stdout","stderr") if name+"_path" in row)
            roles["raw_output"] = paths(raw)
            result.append({"case":case,"command_indices":commands,"endpoint_indices":endpoints,
                           "fixture_workspace":str(self.workspace),"file_roles":roles,
                           "files":sorted(set(p for values in roles.values() for p in values))})
        return result

    def publish(self, report, passed):
        self.report = report
        self.passed = passed
        if self.path is not None:
            self._persist_commands()
            report["artifacts"] = str(self.path)
            report["declared_cases"] = self.declared_cases
            report["case_inventory"] = self._case_inventory()
            (self.path / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            if self.path is not None:
                commands = self.evidence.commands
                self._persist_commands()
                self.evidence.closed = True
                files = {p.relative_to(self.path).as_posix(): digest(p) for p in self.path.rglob("*") if p.is_file() and not p.is_symlink() and p.name != "manifest.json"}
                manifest = {"schema_version":1,"status":"passed" if kind is None and self.passed else "failed",
                    "workspace":str(self.workspace),"inputs":self.inputs,"commands":commands,
                    "endpoint_commands":self.endpoint_commands,"declared_cases":self.declared_cases,"case_inventory":self._case_inventory(),"files":files,
                    "file_bytes":{name:(self.path/name).stat().st_size for name in files}}
                if kind is not None:
                    manifest["exception"] = kind.__name__
                (self.path / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        finally:
            for module, original in self.fixture_modules:
                module.subprocess = original
            if self.temporary is not None:
                self.temporary.cleanup()


class EndpointProcess:
    def __init__(self, owner, command, stem, case, peer_timeout):
        self.owner = owner
        self.paths = {name: Path(str(stem) + "." + name + ".bin") for name in ("stdout", "stderr")}
        self.lines = queue.Queue()
        self.consumed = b""
        self.started = time.monotonic()
        self.stopped = False
        self.row = {"argv":list(map(str, command)),"case":case,"peer_timeout_seconds":peer_timeout,"readiness_timeout_seconds":10,
                    "shutdown_grace_seconds":5,"cwd":str(Path.cwd().resolve()),"timed_out":False,"binary_sha256":digest(command[0]),"stdout_path":str(self.paths["stdout"]),"stderr_path":str(self.paths["stderr"])}
        owner.endpoint_commands.append(self.row)
        self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=not windows_host())
        self.threads = []
        for name in ("stdout", "stderr"):
            thread = threading.Thread(target=self._drain, args=(name, getattr(self.process, name)), daemon=True)
            self.threads.append(thread)
            thread.start()

    def _drain(self, name, pipe):
        pending = b""
        with self.paths[name].open("wb") as output:
            try:
                while True:
                    data = pipe.read1(65536)
                    if not data:
                        break
                    output.write(data)
                    output.flush()
                    if name == "stdout":
                        pending += data
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            self.lines.put(line + b"\n")
                if name == "stdout" and pending:
                    self.lines.put(pending)
            finally:
                pipe.close()
                if name == "stdout":
                    self.lines.put(None)

    def ready_line(self):
        try:
            line = self.lines.get(timeout=10)
        except queue.Empty:
            self.row["readiness_timed_out"] = True
            return ""
        self.consumed = line or b""
        self.row["ready_line_sha256"] = hashlib.sha256(self.consumed).hexdigest()
        return text(self.consumed)

    def stop(self):
        if not self.stopped:
            try:
                self.row["status_before_shutdown"] = self.process.poll()
                self.row["owned_termination_requested"] = self.row["status_before_shutdown"] is None
                if self.row["owned_termination_requested"]:
                    if windows_host():
                        terminate_process_tree(self.process)
                    else:
                        try:
                            os.killpg(self.process.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        terminate_process_tree(self.process)
                        self.process.wait(timeout=5)
            finally:
                for thread in self.threads:
                    thread.join(timeout=5)
                if any(thread.is_alive() for thread in self.threads):
                    raise RuntimeError("owned endpoint pipe drains did not finish")
                self.stopped = True
                self.row.update(status=self.process.returncode, elapsed_seconds=time.monotonic()-self.started)
                for name, path in self.paths.items():
                    self.row[name + "_sha256"] = digest(path)
                    self.row[name + "_bytes"] = path.stat().st_size
        output = self.paths["stdout"].read_bytes()
        # Preserve the previous report's consumed greeting, while the raw
        # file retains every byte including native Windows CRLF endings.
        if output.startswith(self.consumed):
            output = output[len(self.consumed):]
        return text(output), text(self.paths["stderr"].read_bytes())
