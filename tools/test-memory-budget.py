#!/usr/bin/env python3
"""SOURCE DRAFT: explicit Linux/systemd255 aggregate test budget, unqualified.

No automatic activation or fallback. Cooperating same-UID tests only. The native
helper, not this manager-spawned client, owns target wait status and accounting.
The request contains the exact environment and is intentionally retained private.
"""
import argparse
import array
import hashlib
import json
import os
import re
import secrets
import selectors
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time

NAMES = ("CPU", "FSIZE", "DATA", "STACK", "CORE", "RSS", "NPROC", "NOFILE",
         "MEMLOCK", "AS", "LOCKS", "SIGPENDING", "MSGQUEUE", "NICE", "RTPRIO", "RTTIME")
MAX_REQUEST, MAX_VECTOR = 16 * 1024 * 1024, 65536
SETUP_MS, GRACE_MS, CLEANUP_MS, STOP_MS, MARGIN_MS = 10000, 2000, 5000, 10000, 5000
SAFE = re.compile(r"/[A-Za-z0-9/._-]+\Z", re.ASCII)
U64_MAX = (1 << 64) - 1


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe_path(path):
    require(isinstance(path, str) and SAFE.fullmatch(path) and len(path) < 1024,
            "control paths require absolute ASCII letters, digits, / . _ -")
    require(all(p not in (".", "..") for p in path.split("/")), "noncanonical control path")
    return path


def start_ticks(pid):
    with open(f"/proc/{pid}/stat", "rb") as stream:
        text = stream.read(4097)
    require(len(text) <= 4096 and b")" in text, "invalid process identity")
    return int(text.rsplit(b")", 1)[1].split()[19])


def private_write(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_json(directory, name, value):
    temporary = os.path.join(directory, f".{name}.{os.getpid()}.tmp")
    private_write(temporary, (json.dumps(value, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii"))
    os.replace(temporary, os.path.join(directory, name))


def snapshot(helper):
    captured = subprocess.run([helper, "--capture"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, close_fds=True, timeout=10, check=False)
    require(captured.returncode == 0 and len(captured.stdout) <= 2097152, "native caller capture failed")
    data = json.loads(captured.stdout)
    require(data.get("schema") == 1 and data.get("client_pid") == os.getpid(), "capture client mismatch")
    require(str(start_ticks(os.getpid())) == data.get("client_start_ticks"), "capture PID reused")
    require(data.get("uid") == os.getuid() == os.geteuid() != 0 and
            data.get("gid") == os.getgid() == os.getegid(), "ordinary equal real/effective IDs required")
    require(type(data.get("nice")) is int and -20 <= data["nice"] <= 19, "invalid nice snapshot")
    require(type(data.get("umask")) is int and 0 <= data["umask"] <= 0o777, "invalid umask snapshot")
    limits = data.get("rlimits")
    require(isinstance(limits, list) and len(limits) == 16, "native 16-limit ABI required")
    for index, entry in enumerate(limits):
        require(entry.get("id") == index and entry.get("name") == NAMES[index], "limit ABI mismatch")
        for key in ("soft", "hard"):
            value = entry.get(key)
            require(value is None or (isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value)
                                      and int(value) < U64_MAX), "invalid native limit value")
        require(entry["hard"] is None or (entry["soft"] is not None and
                int(entry["soft"]) <= int(entry["hard"])), "invalid limit pair")
    size, cpus = data.get("affinity_mask_bytes"), data.get("affinity")
    require(type(size) is int and 1 <= size <= 8192 and isinstance(cpus, list) and cpus,
            "invalid CPU affinity snapshot")
    require(all(type(cpu) is int and 0 <= cpu < size * 8 for cpu in cpus) and
            cpus == sorted(set(cpus)), "invalid CPU affinity vector")
    groups = data.get("supplementary_groups")
    require(isinstance(groups, list) and len(groups) <= 65536 and
            all(type(gid) is int and 0 <= gid <= 0xffffffff for gid in groups) and
            groups == sorted(set(groups)), "invalid supplementary-group set")
    return data, captured.stdout


def request_bytes(data, memory, wall, nonce, unit, state, control_socket, command, environment, cwd):
    fields = [b"MYMEM001"]

    def number(value):
        fields.append(struct.pack("<Q", value))

    def string(value):
        value = os.fsencode(value)
        require(b"\0" not in value, "NUL in request string")
        number(len(value))
        fields.append(value)

    for value in (1, memory, wall, SETUP_MS, GRACE_MS, CLEANUP_MS, data["client_pid"],
                  int(data["client_start_ticks"]), data["nice"] & U64_MAX, data["umask"],
                  data["uid"], data["gid"], 16):
        number(value)
    for entry in data["rlimits"]:
        number((1 if entry["soft"] is None else 0) | (2 if entry["hard"] is None else 0))
        number(0 if entry["soft"] is None else int(entry["soft"]))
        number(0 if entry["hard"] is None else int(entry["hard"]))
    mask = bytearray(data["affinity_mask_bytes"])
    for cpu in data["affinity"]:
        mask[cpu // 8] |= 1 << (cpu % 8)
    number(len(mask))
    fields.append(bytes(mask))
    number(len(data["supplementary_groups"]))
    for gid in data["supplementary_groups"]:
        number(gid)
    executable = command[0] if command[0].startswith(b"/") else cwd + b"/" + command[0]
    require(b"/" in command[0], "command requires an explicit path; PATH search is disabled")
    for value in (nonce, unit, state, control_socket, cwd, executable):
        string(value)
    for vector in (command, environment):
        require(len(vector) <= MAX_VECTOR, "request vector too large")
        number(len(vector))
        for value in vector:
            string(value)
    require(sum(map(len, fields)) <= MAX_REQUEST, "request exceeds 16 MiB")
    return b"".join(fields)


def manager_properties(data, helper, request, wall_ms):
    lease_ms = SETUP_MS + wall_ms + GRACE_MS + CLEANUP_MS + MARGIN_MS
    result = ["Delegate=memory", "DelegateSubgroup=control", "ExitType=main", "RemainAfterExit=no",
              "Restart=no", "KillMode=control-group", "KillSignal=SIGTERM", "FinalKillSignal=SIGKILL",
              "SendSIGKILL=yes", "TimeoutStopSec=10s", "OOMPolicy=continue",
              f"RuntimeMaxSec={lease_ms}ms", f"Nice={data['nice']}", f"UMask={data['umask']:04o}",
              "CPUAffinity=" + " ".join(map(str, data["affinity"])),
              f"ExecStopPost={helper} --unit-result {request}"]
    for entry in data["rlimits"]:
        def value(raw):
            if raw is None:
                return "infinity"
            return raw + ("us" if entry["name"] == "RTTIME" else "")
        result.append(f"Limit{entry['name']}={value(entry['soft'])}:{value(entry['hard'])}")
    return result, lease_ms


def load_sidecar(directory, name, nonce, unit):
    fd = os.open(os.path.join(directory, name), os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= 2097152, "unsafe sidecar")
        value = json.loads(stream.read(2097153))
    require(value.get("schema") == 1 and value.get("nonce") == nonce and value.get("unit") == unit,
            "sidecar identity mismatch")
    return value


def counter_delta(before, after):
    def parse(text):
        return {line.split()[0]: int(line.split()[1]) for line in text.splitlines()}
    first, last = parse(before), parse(after)
    require(all(key in last and last[key] >= value for key, value in first.items()), "memory counters regressed")
    require(all(key in first for key in ("max", "oom", "oom_kill")), "memory counters missing")
    return {key: last[key] - value for key, value in first.items()}


def classify(guardian, manager, captured, unit, manager_returncode, local):
    leader, causes, cleanup = guardian["leader"], guardian["causes"], guardian["cleanup"]
    local["observed_causes"] = causes
    local["leader_status"] = {key: leader[key] for key in
                              ("known", "raw_wait_status", "exit_code", "signal", "preexec_errno", "preexec_phase")}
    local["manager_status"] = {key: manager[key] for key in ("service_result", "exit_code", "exit_status")}
    memory = guardian["memory"]
    delta = counter_delta(memory["events_before"], memory["events_after"])
    local["memory_events_delta"] = delta
    oom = causes["oom_observed"] or any(delta.get(key, 0) for key in ("oom", "oom_kill", "oom_group_kill"))
    mc = manager["cleanup"]
    require(guardian.get("complete") is True and guardian["failure_errno"] == 0 and
            cleanup["errno"] == 0 and cleanup["kill_errno"] == 0 and
            all(cleanup[key] is True for key in ("owned_children_drained", "populated_zero", "job_removed")) and
            (not cleanup["controller_changed"] or cleanup["controller_restored"]), "incomplete guardian cleanup")
    require(mc["errno"] == 0 and mc["populated_zero"] is True and mc["job_removed"] is True and
            (not mc["controller_restore_needed"] or mc["controller_restored"]), "incomplete manager cleanup")
    require(leader["known"] is True and leader["limits_verified"] is True and leader["pipe_closed"] is True,
            "missing leader/exec-boundary evidence")
    require(leader["nice"] == captured["nice"] and leader["umask"] == captured["umask"] and
            leader["affinity_verified"] is True and leader["affinity"] == captured["affinity"],
            "child scheduling/mask state differs")
    require(leader["groups_verified"] is True and
            leader["supplementary_groups"] == captured["supplementary_groups"], "child group set differs")
    expected = [{"id": e["id"], "soft": e["hard"] if e["id"] == 9 else e["soft"], "hard": e["hard"]}
                for e in captured["rlimits"]]
    require(leader["limits"] == expected and guardian["admission"]["controls_verified"] is True,
            "admitted child limits differ")
    root = guardian["unit_cgroup"]
    require(isinstance(root, str) and root.startswith(f"/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/")
            and root.endswith("/" + unit) and "/../" not in root, "invalid unit cgroup evidence")
    require(not os.path.exists("/sys/fs/cgroup" + root), "manager left unit cgroup behind")
    if local["outer_timeout"]:
        return "client-outer-timeout", 125
    if manager["service_result"] == "timeout":
        return "manager-timeout", 125
    if oom:
        return "memory-oom", leader["exit_code"] if leader["exit_code"] else 125
    if leader["preexec_errno"]:
        return "target-exec-error", 125
    if local["cancel_signal"] or causes["cancel_request"]:
        return "client-cancelled", 128 + (local["cancel_signal"] or signal.SIGTERM)
    if causes["target_wall"]:
        return "target-wall-timeout", 124
    require(not causes["client_dead"] and not causes["socket_eof"] and not causes["supervisor_signal"],
            "unexpected supervisor/client termination")
    code = leader["exit_code"]
    # Metadata owns the workload result. Ordinary 37/124/137 is never inferred
    # to be infrastructure/timeout merely from the manager command's exit code.
    require(manager["service_result"] in ("success", "exit-code") and
            manager["exit_code"] == "exited" and manager["exit_status"] in ("0", str(code)) and
            manager_returncode in (0, code), "manager result contradicts complete leader evidence")
    if code is not None:
        require(type(code) is int and 0 <= code <= 255, "invalid target exit status")
        return "target-exit", code
    require(type(leader["signal"]) is int and 1 <= leader["signal"] < signal.NSIG, "invalid target signal")
    return "target-signal", 128 + leader["signal"]


def supervise(listener, unit, helper, request, captured, wall_ms, streams, directory, local):
    properties, lease_ms = manager_properties(captured, helper, request, wall_ms)
    argv = ["systemd-run", "--user", "--wait", "--pipe", "--quiet", "--collect",
            "--service-type=exec", "--expand-environment=no", "--unit=" + unit]
    for value in properties:
        argv += ["--property=" + value]
    argv += [helper, "--unit-main", request]
    local["manager_argv"] = argv
    selector = selectors.DefaultSelector()
    wake_read, wake_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    old_handlers, old_wakeup = {}, signal.set_wakeup_fd(wake_write)
    pending = []

    def interrupted(number, _frame):
        pending.append(number)

    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        old_handlers[number] = signal.signal(number, interrupted)
    process = connection = None
    manager_fd = guardian_fd = -1
    started = time.monotonic()
    startup_end = started + SETUP_MS / 1000
    outer_end = started + (SETUP_MS + lease_ms + STOP_MS + MARGIN_MS) / 1000
    hello, acknowledged, done, sent_cancel, stopped = bytearray(), False, False, False, False
    logs = []

    def stop_unit():
        nonlocal stopped
        if stopped:
            return
        stopped = True
        local["stop_requested"] = True
        try:
            result = subprocess.run(["systemctl", "--user", "stop", unit], stdin=subprocess.DEVNULL,
                                    stdout=logs[0], stderr=logs[1], close_fds=True,
                                    timeout=(STOP_MS + CLEANUP_MS) / 1000, check=False)
            local["stop_returncode"] = result.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            local["stop_error"] = type(error).__name__

    def settle_cli():
        try:
            local["manager_returncode"] = process.wait(timeout=(STOP_MS + MARGIN_MS) / 1000)
        except subprocess.TimeoutExpired:
            # Unit cancellation was requested first. Killing this direct child
            # only reaps a stuck CLI; it is never substituted for unit cleanup.
            local["manager_cli_killed"] = True
            process.kill()
            try:
                local["manager_returncode"] = process.wait(timeout=MARGIN_MS / 1000)
            except subprocess.TimeoutExpired:
                local["manager_wait_incomplete"] = True

    try:
        for name in ("manager.stdout", "manager.stderr"):
            fd = os.open(os.path.join(directory, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
            os.fchmod(fd, 0o600)
            logs.append(os.fdopen(fd, "wb", buffering=0))
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=logs[0], stderr=logs[1],
                                   close_fds=True, start_new_session=True)
        local["manager_pid"] = process.pid
        manager_fd = os.pidfd_open(process.pid, 0)
        selector.register(manager_fd, selectors.EVENT_READ, "manager")
        selector.register(listener, selectors.EVENT_READ, "listener")
        selector.register(wake_read, selectors.EVENT_READ, "signal")
        while True:
            now = time.monotonic()
            if pending:
                local["cancel_signal"] = pending[0]
            if local["cancel_signal"] and connection is not None and acknowledged and not sent_cancel:
                connection.sendall(b"C")
                sent_cancel = True
            if now >= outer_end:
                local["outer_timeout"] = True
                stop_unit()
                break
            if not acknowledged and now >= startup_end:
                raise TimeoutError("native admission handshake deadline")
            deadline = outer_end if acknowledged else min(outer_end, startup_end)
            for key, _mask in selector.select(max(0, deadline - now)):
                if key.data == "signal":
                    try:
                        os.read(wake_read, 4096)
                    except BlockingIOError:
                        pass
                elif key.data == "manager":
                    local["manager_returncode"] = process.wait()
                    if not os.path.exists(os.path.join(directory, "manager.json")):
                        local["manager_cli_exited_before_sidecar"] = True
                        stop_unit()
                    return local["manager_returncode"]
                elif key.data == "listener":
                    require(connection is None, "unexpected second native connection")
                    connection, _address = listener.accept()
                    connection.setblocking(False)
                    pid, uid, gid = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    require(uid == captured["uid"] and gid == captured["gid"], "native peer credentials differ")
                    local["guardian_pid"] = pid
                    selector.unregister(listener)
                    selector.register(connection, selectors.EVENT_READ, "control")
                elif key.data == "guardian":
                    selector.unregister(guardian_fd)
                    os.close(guardian_fd)
                    guardian_fd = -1
                    local["guardian_exited"] = True
                    # systemd completes whole-unit stop and ExecStopPost; wait
                    # for the CLI pidfd rather than treating MainPID death as done.
                elif key.data == "control":
                    chunk = connection.recv(4096)
                    if not chunk:
                        selector.unregister(connection)
                        local["guardian_socket_closed"] = True
                        continue
                    if not acknowledged and len(hello) < 56:
                        needed = 56 - len(hello)
                        hello.extend(chunk[:needed])
                        chunk = chunk[needed:]
                        if len(hello) == 56:
                            magic, pid, ticks, nonce = struct.unpack("<8sQQ32s", hello)
                            require(magic == b"MYHEL001" and pid == local["guardian_pid"] and
                                    nonce == local["nonce"].encode("ascii") and start_ticks(pid) == ticks,
                                    "native identity handshake failed")
                            guardian_fd = os.pidfd_open(pid, 0)
                            require(start_ticks(pid) == ticks, "native identity changed")
                            selector.register(guardian_fd, selectors.EVENT_READ, "guardian")
                            connection.settimeout(max(0.001, startup_end - time.monotonic()))
                            message = b"MYFDS001" + nonce
                            count = connection.sendmsg([message], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", streams))])
                            require(count > 0, "descriptor handoff failed")
                            connection.sendall(message[count:])
                            connection.setblocking(False)
                    for byte in chunk:
                        if byte == ord("R") and not acknowledged and len(hello) == 56:
                            acknowledged = True
                            local["native_handshake"] = True
                        elif byte == ord("D") and acknowledged and not done:
                            done = True
                            local["native_done"] = True
                        else:
                            raise ValueError("unexpected native control message")
        settle_cli()
        return local.get("manager_returncode")
    except BaseException:
        if process is not None:
            stop_unit()
            settle_cli()
        raise
    finally:
        signal.set_wakeup_fd(old_wakeup)
        for number, handler in old_handlers.items():
            signal.signal(number, handler)
        selector.close()
        if connection is not None:
            connection.close()
        for fd in (wake_read, wake_write, manager_fd, guardian_fd):
            if fd >= 0:
                os.close(fd)
        for stream in logs:
            stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=["aggregate-v1"])
    parser.add_argument("--memory-bytes", required=True, type=int)
    parser.add_argument("--wall-seconds", required=True, type=int)
    parser.add_argument("--helper", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    require(sys.platform == "linux" and hasattr(os, "pidfd_open") and hasattr(os, "environb"),
            "Linux Python with pidfd_open and byte environments required")
    require(command and command[0], "target command required")
    require(0 < args.memory_bytes <= (1 << 63) - 1 and args.memory_bytes % os.sysconf("SC_PAGE_SIZE") == 0,
            "memory bytes must be positive and page aligned")
    require(0 < args.wall_seconds <= 604800, "wall seconds outside 1..604800")
    helper = safe_path(os.path.realpath(args.helper))
    require(os.path.isfile(helper) and os.access(helper, os.X_OK), "native helper is not executable")
    root = safe_path(os.path.realpath(args.evidence_root))
    require(os.path.isdir(root) and os.stat(root).st_uid == os.getuid(), "evidence root must exist and be caller owned")
    runtime = safe_path(os.path.realpath(os.environ["XDG_RUNTIME_DIR"]))
    runtime_stat = os.stat(runtime)
    require(stat.S_ISDIR(runtime_stat.st_mode) and runtime_stat.st_uid == os.getuid() and
            stat.S_IMODE(runtime_stat.st_mode) == 0o700, "private XDG_RUNTIME_DIR required")
    captured, raw_capture = snapshot(helper)  # Before manager launch or any caller-state changes.
    nonce = secrets.token_hex(16)
    unit = "minyar-test-mem-" + nonce + ".service"
    directory = safe_path(os.path.join(root, "run-" + nonce))
    os.mkdir(directory, 0o700)
    os.chmod(directory, 0o700)
    require(stat.S_IMODE(os.stat(directory).st_mode) == 0o700, "caller umask prevented private state directory")
    local = {"schema": 1, "profile": args.profile, "nonce": nonce, "unit": unit, "source_draft": True,
             "cancel_signal": 0, "outer_timeout": False, "native_handshake": False,
             "capture_sha256": hashlib.sha256(raw_capture).hexdigest(), "evidence_directory": directory}
    connection_dir = listener = None
    streams = []
    code = 125
    try:
        private_write(os.path.join(directory, "caller.json"), raw_capture)
        with open(helper, "rb") as source:
            local["helper_sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
        connection_dir = safe_path(tempfile.mkdtemp(prefix="minyar-mem-", dir=runtime))
        os.chmod(connection_dir, 0o700)
        control_socket = safe_path(os.path.join(connection_dir, "control"))
        require(len(os.fsencode(control_socket)) < 108, "Unix control socket path too long")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        listener.bind(control_socket)
        os.chmod(control_socket, 0o600)
        listener.listen(1)
        listener.setblocking(False)
        payload = request_bytes(captured, args.memory_bytes, args.wall_seconds * 1000, nonce, unit,
                                directory, control_socket, list(map(os.fsencode, command)),
                                [key + b"=" + value for key, value in os.environb.items()], os.getcwdb())
        request = os.path.join(directory, "request.bin")
        private_write(request, payload)
        local["request_sha256"] = hashlib.sha256(payload).hexdigest()
        local["request_bytes"] = len(payload)
        for fd in (0, 1, 2):
            streams.append(os.dup(fd))
        manager_code = supervise(listener, unit, helper, request, captured, args.wall_seconds * 1000,
                                 streams, directory, local)
        manager = load_sidecar(directory, "manager.json", nonce, unit)
        local["manager_status"] = {key: manager[key] for key in ("service_result", "exit_code", "exit_status")}
        guardian = load_sidecar(directory, "guardian.json", nonce, unit)
        local["kind"], code = classify(guardian, manager, captured, unit, manager_code, local)
        local["complete"] = True
    except BaseException as error:
        local["kind"] = "infrastructure-error"
        if local["outer_timeout"]:
            local["kind"] = "client-outer-timeout"
        elif local.get("manager_status", {}).get("service_result") == "timeout":
            local["kind"] = "manager-timeout"
        elif local.get("observed_causes", {}).get("oom_observed") or \
                local.get("manager_status", {}).get("service_result") == "oom-kill":
            local["kind"] = "memory-oom"
        elif local["cancel_signal"]:
            local["kind"] = "client-cancelled"
        local["complete"] = False
        local.setdefault("leader_status", {"known": False, "raw_wait_status": None,
                                           "exit_code": None, "signal": None})
        local["error_type"] = type(error).__name__
        # Never include target environment or literal argument bytes in errors.
        local["error"] = str(error) if isinstance(error, (ValueError, TimeoutError)) else "see native/manager evidence"
    finally:
        for fd in streams:
            os.close(fd)
        if listener is not None:
            listener.close()
        if connection_dir is not None:
            try:
                os.unlink(os.path.join(connection_dir, "control"))
            except OSError as error:
                if not isinstance(error, FileNotFoundError):
                    local["socket_cleanup_errno"] = error.errno
                    local["complete"] = False
                    code = 125
            try:
                os.rmdir(connection_dir)
            except OSError as error:
                if not isinstance(error, FileNotFoundError):
                    local["socket_directory_cleanup_errno"] = error.errno
                    local["complete"] = False
                    code = 125
        local["exit_code"] = code
        atomic_json(directory, "client.json", local)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("aggregate-v1 setup failed: " + type(error).__name__, file=sys.stderr)
        sys.exit(125)
