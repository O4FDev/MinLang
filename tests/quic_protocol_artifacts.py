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
        self.endpoints = []
        self.fixture_modules = []
        self.report = None
        self.shared_fixtures = []
        self.case_files = {case:{} for case in self.declared_cases}
        self.passed = False
        self.finalization_errors = []
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
                receipt = row.get("lifecycle",{}).get("receipt",{})
                raw.extend(Path(receipt[name+"_path"]) for name in ("stdout","stderr") if name+"_path" in receipt)
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
        cleanup_failure = None
        manifest = None
        def secondary(stage,error):
            nonlocal cleanup_failure
            row = {"stage":stage,"exception":type(error).__name__,"message":str(error)}
            self.finalization_errors.append(row)
            self.passed = False
            if value is not None:
                if hasattr(value,"add_note"):
                    value.add_note("protocol artifact finalization failed: "+json.dumps(row,sort_keys=True))
            elif cleanup_failure is None:
                cleanup_failure = error
        for endpoint in self.endpoints:
            if not endpoint.stopped:
                try:
                    endpoint.stop(primary=value)
                except BaseException as error:
                    secondary("endpoint-cleanup",error)
        if self.path is not None:
            try:
                self._persist_commands()
            except BaseException as error:
                secondary("command-retention",error)
            self.evidence.closed = True
            files = {}
            unhashed = []
            try:
                candidates = sorted(self.path.rglob("*"))
                for path in candidates:
                    if not path.is_file() or path.is_symlink() or path.name=="manifest.json":
                        continue
                    name = path.relative_to(self.path).as_posix()
                    try:
                        files[name] = digest(path)
                    except BaseException as error:
                        unhashed.append(name)
                        secondary("file-retention:"+name,error)
                inventory = self._case_inventory()
            except BaseException as error:
                inventory = []
                secondary("file-inventory",error)
            manifest = {"schema_version":1,"status":"passed" if kind is None and
                        cleanup_failure is None and self.passed and not unhashed else "failed",
                        "workspace":str(self.workspace),"inputs":self.inputs,
                        "commands":self.evidence.commands,"endpoint_commands":self.endpoint_commands,
                        "declared_cases":self.declared_cases,"case_inventory":inventory,"files":files,
                        "file_bytes":{},"finalization_errors":self.finalization_errors,
                        "unhashed_files":unhashed}
            for name in files:
                try:
                    manifest["file_bytes"][name]=(self.path/name).stat().st_size
                except BaseException as error:
                    secondary("file-size:"+name,error)
                    manifest["status"]="failed"
            if kind is not None:
                manifest["exception"]=kind.__name__
        for module,original in self.fixture_modules:
            try:
                module.subprocess=original
            except BaseException as error:
                secondary("fixture-restoration",error)
        if self.temporary is not None:
            try:
                self.temporary.cleanup()
            except BaseException as error:
                secondary("temporary-cleanup",error)
        if manifest is not None:
            if self.finalization_errors:
                manifest["status"]="failed"
            try:
                (self.path/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
            except BaseException as error:
                secondary("manifest-retention",error)
        if value is None and cleanup_failure is not None:
            raise cleanup_failure


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
        self.threads = []
        self.drain_errors = []
        for path in self.paths.values():
            path.write_bytes(b"")
        self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=not windows_host())
        owner.endpoints.append(self)
        self.row["pid"] = self.process.pid
        try:
            for name in ("stdout", "stderr"):
                thread = threading.Thread(target=self._drain, args=(name, getattr(self.process, name)), daemon=True)
                self.threads.append((name, thread))
                thread.start()
        except BaseException as error:
            self.row["startup_exception"] = type(error).__name__
            self.stop(primary=error)
            raise

    def _drain(self, name, pipe):
        pending = b""
        with self.paths[name].open("ab") as output:
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
            except BaseException as error:
                self.drain_errors.append({"stage":name+"-drain","exception":type(error).__name__,"message":str(error)})
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

    def _windows_stop(self):
        native_pid = self.process.pid if os.name == "nt" else int(
            Path("/proc/"+str(self.process.pid)+"/winpid").read_text().strip())
        if native_pid <= 0:
            raise ValueError("invalid owned native process identity")
        command = ["taskkill.exe", "-F", "-T", "-PID", str(native_pid)]
        receipt = {"pid":self.process.pid,"native_pid":native_pid,
                   "pid_source":"popen" if os.name == "nt" else "proc-winpid",
                   "python_os_name":os.name,"argv":command,"timeout_seconds":10,"attempted":True}
        self.row["lifecycle"]["receipt"] = receipt
        result = subprocess.run(command, capture_output=True, timeout=10)
        receipt["status"] = result.returncode
        for name, data in (("stdout",result.stdout),("stderr",result.stderr)):
            path = Path(str(self.paths[name])+".termination.bin")
            path.write_bytes(data)
            receipt[name+"_path"] = str(path)
            receipt[name+"_sha256"] = digest(path)
            receipt[name+"_bytes"] = len(data)
        if result.returncode:
            raise RuntimeError("owned native tree termination failed")
        # This exact prediction fails closed on an unsupported native mapping;
        # taskkill success alone never makes an arbitrary target status healthy.
        # Native/MSYS execution is required before claiming platform coverage.

    def stop(self, *, primary=None):
        try:
            return self._stop(primary=primary)
        except BaseException as error:
            # Retention failures can occur after the process has already been
            # stopped. They must fail the ledger without replacing the caller's
            # original startup/readiness exception.
            lifecycle = self.row.setdefault("lifecycle",{})
            errors = lifecycle.setdefault("cleanup_errors",[])
            errors.append({"stage":"cleanup-or-retention","exception":type(error).__name__,"message":str(error)})
            lifecycle["passed"] = False
            lifecycle.setdefault("cleanup_complete",self.stopped)
            self.owner.passed = False
            if primary is None:
                raise
            self.row["primary_exception"] = type(primary).__name__
            if hasattr(primary,"add_note"):
                primary.add_note("owned endpoint secondary failure: "+type(error).__name__+": "+str(error))
            return "", ""

    def _stop(self, *, primary=None):
        if not self.stopped:
            errors = []
            prior = self.process.poll()
            requested = prior is None
            self.row.update(status_before_shutdown=prior, owned_termination_requested=requested)
            lifecycle = {"healthy_before_shutdown":prior is None or prior == 0,
                         "termination_strategy":"already-exited","expected_final_status":0,
                         "escalated":False,"cleanup_errors":errors,"receipt":{}}
            self.row["lifecycle"] = lifecycle
            def failure(stage, error):
                errors.append({"stage":stage,"exception":type(error).__name__,"message":str(error)})
            def signal_group(signum):
                pgid = os.getpgid(self.process.pid)
                if pgid != self.process.pid:
                    raise RuntimeError("endpoint no longer owns its process group")
                receipt = lifecycle["receipt"]
                receipt.update(pid=self.process.pid,pgid=pgid,attempted=True,signal=int(signum),
                               grace_seconds=5,wait_timed_out=False,result="pending")
                os.killpg(pgid, signum)
                receipt["result"] = "sent"
            if requested:
                try:
                    if windows_host():
                        lifecycle.update(termination_strategy="windows-taskkill-tree",expected_final_status=1)
                        self._windows_stop()
                    else:
                        lifecycle.update(termination_strategy="posix-sigterm",expected_final_status=-int(signal.SIGTERM))
                        signal_group(signal.SIGTERM)
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        lifecycle["receipt"]["wait_timed_out"] = True
                        raise
                except BaseException as error:
                    if not isinstance(error, subprocess.TimeoutExpired):
                        failure("termination",error)
                    if self.process.poll() is None:
                        lifecycle["escalated"] = True
                        try:
                            if windows_host():
                                self._windows_stop()
                            else:
                                previous = dict(lifecycle["receipt"])
                                lifecycle.update(termination_strategy="posix-sigkill-after-grace",expected_final_status=-int(signal.SIGKILL))
                                signal_group(signal.SIGKILL)
                                lifecycle["receipt"]["previous"] = previous
                            self.process.wait(timeout=5)
                        except BaseException as cleanup_error:
                            failure("forced-termination",cleanup_error)
            for name, thread in self.threads:
                if thread.ident is not None:
                    try:
                        thread.join(timeout=5)
                        if thread.is_alive():
                            raise RuntimeError("owned endpoint pipe drain did not finish")
                    except BaseException as error:
                        failure(name+"-join",error)
                elif self.process.poll() is not None:
                    # A failed Thread.start leaves this pipe solely owned here.
                    try:
                        pipe = getattr(self.process,name)
                        with self.paths[name].open("ab") as output:
                            output.write(pipe.read())
                        pipe.close()
                    except BaseException as error:
                        failure(name+"-unstarted-drain",error)
            # A first start failure can leave the other stream without a Thread.
            names = {name for name,_ in self.threads}
            for name in set(self.paths)-names:
                pipe = getattr(self.process,name)
                if self.process.poll() is not None:
                    try:
                        with self.paths[name].open("ab") as output:
                            output.write(pipe.read())
                        pipe.close()
                    except BaseException as error:
                        failure(name+"-unstarted-drain",error)
            errors.extend(self.drain_errors)
            complete = self.process.poll() is not None and all(
                thread.ident is None or not thread.is_alive() for _,thread in self.threads
            ) and all(getattr(self.process,name).closed for name in self.paths)
            self.stopped = complete
            self.row.update(status=self.process.returncode, elapsed_seconds=time.monotonic()-self.started)
            for name,path in self.paths.items():
                self.row[name+"_sha256"] = digest(path)
                self.row[name+"_bytes"] = path.stat().st_size
            lifecycle.update(cleanup_complete=complete,passed=lifecycle["healthy_before_shutdown"] and
                             complete and not errors and self.process.returncode == lifecycle["expected_final_status"])
        if not self.row["lifecycle"]["passed"]:
            error = RuntimeError("owned endpoint lifecycle failed: "+json.dumps(self.row["lifecycle"],sort_keys=True))
            if primary is None:
                raise error
            if hasattr(primary,"add_note"):
                primary.add_note(str(error))
            self.row["primary_exception"] = type(primary).__name__
        output = self.paths["stdout"].read_bytes()
        if output.startswith(self.consumed):
            output = output[len(self.consumed):]
        return text(output), text(self.paths["stderr"].read_bytes())
