#!/usr/bin/env python3
"""Real delegated-controller acceptance tests; explicitly invoked on Linux only.

Each run keeps private caller/request/guardian/manager/client artifacts. These
tests never turn absent delegation into a skip or a successful unbounded run.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = None
MIB = 1048576


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.evidence = Path(tempfile.mkdtemp(prefix="case-", dir=OPTIONS.evidence_root))

    def argv(self, command, wall=10, memory=64 * MIB):
        return ["zsh", str(ROOT / "scripts/with-limits.sh"), sys.executable,
                str(ROOT / "tools/test-memory-budget.py"), "--profile", "aggregate-v1",
                "--memory-bytes", str(memory), "--wall-seconds", str(wall),
                "--helper", OPTIONS.helper, "--evidence-root", str(self.evidence), "--", *command]

    def sidecars(self):
        directories = list(self.evidence.glob("run-*"))
        self.assertEqual(len(directories), 1)
        return {name: json.loads((directories[0] / (name + ".json")).read_bytes())
                for name in ("caller", "guardian", "manager", "client")}

    def settled(self, command, expected=0, kind="target-exit", wall=10, memory=64 * MIB,
                input=b"", env=None, preexec_fn=None):
        result = subprocess.run(self.argv(command, wall, memory), input=input, capture_output=True,
                                timeout=wall + 65, env=env, preexec_fn=preexec_fn)
        (self.evidence / "stdout").write_bytes(result.stdout)
        (self.evidence / "stderr").write_bytes(result.stderr)
        self.assertEqual(result.returncode, expected, result.stderr.decode(errors="replace"))
        records = self.sidecars()
        client, guardian = records["client"], records["guardian"]
        self.assertTrue(client["complete"], client)
        self.assertEqual(client["kind"], kind)
        self.assertTrue(guardian["complete"], guardian)
        self.assertTrue(guardian["admission"]["controls_verified"])
        self.assertEqual(guardian["admission"]["memory_max"], str(memory))
        self.assertEqual(guardian["admission"]["memory_swap_max"], "0")
        self.assertEqual(guardian["admission"]["memory_oom_group"], "1")
        self.assertTrue(guardian["cleanup"]["populated_zero"])
        self.assertTrue(guardian["cleanup"]["job_removed"])
        self.assertTrue(guardian["cleanup"]["owned_children_drained"])
        self.assertFalse(Path("/sys/fs/cgroup" + guardian["unit_cgroup"]).exists())
        return result, records

    def test_01_exact_launch_and_limits(self):
        literal = ["", "a b", "apostrophe'", "$HOME%value", "back\\slash", "line\nbreak"]
        environment = dict(os.environ, MINYAR_MEMORY_LITERAL="a b'$%\\\n", MINYAR_MEMORY_EMPTY="")
        environment.pop("MINYAR_MEMORY_ABSENT", None)
        command = [OPTIONS.fixture, "inspect", "--env", "MINYAR_MEMORY_LITERAL", "--env",
                   "MINYAR_MEMORY_EMPTY", "--env", "MINYAR_MEMORY_ABSENT", "--", *literal]
        result, records = self.settled(command, input=b"in\x00\xff\n", env=environment)
        line, sentinel = result.stdout.split(b"\n", 1)
        self.assertEqual(sentinel, b"out\x00\xff\n")
        self.assertEqual(result.stderr, b"err\x00\xff\n")
        inspect = json.loads(line)
        self.assertEqual(inspect["argv_hex"], [os.fsencode(arg).hex() for arg in command])
        self.assertEqual(inspect["cwd_hex"], os.getcwdb().hex())
        self.assertEqual(inspect["stdin_hex"], b"in\x00\xff\n".hex())
        self.assertEqual([item["value_hex"] for item in inspect["environment"]],
                         [os.fsencode(environment["MINYAR_MEMORY_LITERAL"]).hex(), "", None])
        self.assertEqual(sorted(item["fd"] for item in inspect["open_fds"]), [0, 1, 2])
        self.assertEqual(inspect["nice"], records["caller"]["nice"])
        self.assertEqual(int(inspect["umask_octal"], 8), records["caller"]["umask"])
        for observed, captured in zip(inspect["rlimits"], records["caller"]["rlimits"], strict=True):
            def normalized(value):
                return None if value == "infinity" else str(value)
            self.assertEqual(normalized(observed["hard"]), captured["hard"])
            self.assertEqual(normalized(observed["soft"]),
                             captured["hard"] if captured["id"] == resource.RLIMIT_AS else captured["soft"])
        self.assertEqual(records["caller"]["rlimits"][resource.RLIMIT_AS]["soft"], str(768 * MIB))

    def test_02_exit_codes_are_literal(self):
        for code in (0, 37, 124, 125, 137):
            with self.subTest(code=code):
                self.setUp()
                _, records = self.settled(["/bin/sh", "-c", "exit " + str(code)], expected=code)
                self.assertEqual(records["guardian"]["leader"]["exit_code"], code)
                self.assertFalse(records["guardian"]["causes"]["target_wall"])

    def test_03_raw_signal(self):
        _, records = self.settled([OPTIONS.fixture, "abrt"], expected=134, kind="target-signal")
        self.assertEqual(records["guardian"]["leader"]["signal"], signal.SIGABRT)
        self.assertIsNone(records["guardian"]["leader"]["exit_code"])

    def test_04_exec_failure(self):
        _, records = self.settled(["/does-not-exist/minyar"], expected=125, kind="target-exec-error")
        self.assertEqual(records["guardian"]["leader"]["preexec_errno"], 2)

    def test_05_sparse_reservation(self):
        self.settled([OPTIONS.fixture, "sparse", "2147483648"])

    def test_06_under_budget_touch(self):
        _, records = self.settled([OPTIONS.fixture, "touch", str(48 * MIB), "100"])
        self.assertEqual(records["client"]["memory_events_delta"]["oom"], 0)

    def assert_oom(self, command):
        _, records = self.settled(command, expected=125, kind="memory-oom")
        events = records["client"]["memory_events_delta"]
        self.assertGreater(events["oom"], 0)
        self.assertGreater(events["oom_kill"], 0)
        self.assertGreater(events["max"], 0)
        self.assertEqual(records["guardian"]["leader"]["signal"], signal.SIGKILL)

    def test_07_touched_overrun(self):
        self.assert_oom([OPTIONS.fixture, "touch", str(96 * MIB), "100"])

    def test_08_aggregate_descendants(self):
        self.assert_oom([OPTIONS.fixture, "aggregate", str(48 * MIB), "1000"])

    def test_09_term_handled_deadline(self):
        _, records = self.settled([OPTIONS.fixture, "term", "handled", "15000"], expected=124,
                                 kind="target-wall-timeout", wall=1)
        self.assertEqual(records["guardian"]["leader"]["exit_code"], 0)
        self.assertTrue(records["guardian"]["causes"]["term_sent"])
        self.assertFalse(records["guardian"]["causes"]["grace_expired"])

    def test_10_term_ignored_deadline(self):
        _, records = self.settled([OPTIONS.fixture, "term", "ignore", "15000"], expected=124,
                                 kind="target-wall-timeout", wall=1)
        self.assertEqual(records["guardian"]["leader"]["signal"], signal.SIGKILL)
        self.assertTrue(records["guardian"]["causes"]["grace_expired"])

    def event(self, process, wanted):
        # One absolute readiness deadline; no short-wait or sleep polling loop.
        deadline = time.monotonic() + 15
        data = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                left = deadline - time.monotonic()
                self.assertGreater(left, 0, "fixture readiness deadline")
                self.assertTrue(selector.select(left), "fixture readiness timeout")
                chunk = os.read(process.stdout.fileno(), 65536)
                self.assertTrue(chunk, "fixture exited before readiness")
                data.extend(chunk)
                while b"\n" in data:
                    line, _, rest = data.partition(b"\n")
                    data = bytearray(rest)
                    record = json.loads(line)
                    if record["event"] == wanted:
                        return record

    def orphan_start(self, wall=10, hold_ms=15000, lifetime=False):
        receipt = self.evidence / "detached.json"
        mode = "orphan-hold" if lifetime else "orphan"
        process = subprocess.Popen(self.argv([OPTIONS.fixture, mode, str(receipt), str(hold_ms)], wall=wall),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop_process, process)
        ready = self.event(process, "orphan-awaiting-stdin-G")
        child = json.loads(receipt.read_bytes())
        self.assertEqual(child["pid"], ready["grandchild_pid"])
        pidfd = os.pidfd_open(child["pid"])
        self.addCleanup(os.close, pidfd)
        return process, ready, child, pidfd

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=25)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def assert_dead(self, pidfd, timeout=15):
        with selectors.DefaultSelector() as selector:
            selector.register(pidfd, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout), "detached descendant survived cleanup")

    def guardian_pidfd(self, ready):
        status = Path(f"/proc/{ready['leader_pid']}/stat").read_bytes().rsplit(b")", 1)[1].split()
        self.guardian_pid = int(status[1])
        fd = os.pidfd_open(self.guardian_pid)
        self.addCleanup(os.close, fd)
        return fd

    def stop_guardian(self, ready):
        fd = self.guardian_pidfd(ready)
        signal.pidfd_send_signal(fd, signal.SIGSTOP)
        # SIGSTOP is delivered asynchronously and the guardian is not our child, so
        # waitid cannot observe the stop; read /proc until it shows T or the deadline passes.
        deadline = time.monotonic() + 5
        while True:
            state = Path(f"/proc/{self.guardian_pid}/stat").read_bytes().rsplit(b")", 1)[1].split()[0]
            if state == b"T" or time.monotonic() >= deadline:
                break
            time.sleep(0.001)
        self.assertEqual(state, b"T", "stopped-guardian precondition was not established")
        return fd

    def manager_pidfd(self, process):
        children = Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split()
        self.assertEqual(len(children), 1, "client must own exactly its manager CLI")
        fd = os.pidfd_open(int(children[0]))
        self.addCleanup(os.close, fd)
        self.assertEqual(Path(f"/proc/{children[0]}/exe").resolve().name, "systemd-run")
        return fd

    def assert_manager_cleanup(self, child):
        directory = next(self.evidence.glob("run-*"))
        manager = json.loads((directory / "manager.json").read_bytes())
        self.assertEqual(manager["cleanup"]["errno"], 0)
        self.assertTrue(manager["cleanup"]["populated_zero"])
        self.assertTrue(manager["cleanup"]["job_removed"])
        unit_path = bytes.fromhex(child["cgroup_hex"]).decode().rsplit("/", 1)[0]
        self.assertFalse(Path("/sys/fs/cgroup" + unit_path).exists())

    def test_11_normal_exit_cleans_detached(self):
        process, _, _, pidfd = self.orphan_start()
        process.stdin.write(b"G")
        process.stdin.flush()
        process.communicate(timeout=25)
        self.assertEqual(process.returncode, 0)
        self.assert_dead(pidfd)
        self.assertTrue(self.sidecars()["client"]["complete"])

    def test_12_client_death_cleans_detached(self):
        process, _, child, pidfd = self.orphan_start(hold_ms=60000, lifetime=True)
        manager = self.manager_pidfd(process)
        # communicate closes its stdin. Retain a writer so neither EOF nor the
        # fixture's 60s fallback can impersonate supervisor lifetime cleanup.
        writer = os.dup(process.stdin.fileno())
        self.addCleanup(os.close, writer)
        process.kill()
        process.communicate(timeout=25)
        self.assert_dead(pidfd)
        self.assert_dead(manager)
        self.assert_manager_cleanup(child)
        directory = next(self.evidence.glob("run-*"))
        guardian = json.loads((directory / "guardian.json").read_bytes())
        self.assertTrue(guardian["causes"]["client_dead"])
        self.assertTrue(guardian["complete"])
        # Guardian/manager survive their client. No complete client result can exist.
        self.assertFalse(any(self.evidence.glob("run-*/client.json")))

    def test_13_guardian_death_cleans_detached(self):
        process, ready, child, pidfd = self.orphan_start(hold_ms=60000, lifetime=True)
        signal.pidfd_send_signal(self.guardian_pidfd(ready), signal.SIGKILL)
        process.communicate(timeout=30)
        self.assertEqual(process.returncode, 125)
        self.assert_dead(pidfd)
        directory = next(self.evidence.glob("run-*"))
        self.assertFalse(json.loads((directory / "client.json").read_bytes())["complete"])
        self.assert_manager_cleanup(child)

    def test_14_both_owners_die_manager_cleans(self):
        process, ready, child, pidfd = self.orphan_start(hold_ms=60000, lifetime=True)
        manager = self.manager_pidfd(process)
        writer = os.dup(process.stdin.fileno())
        self.addCleanup(os.close, writer)
        # A stopped guardian cannot react to client death and clean the job
        # before this test kills it. The independent manager must do teardown.
        guardian = self.stop_guardian(ready)
        process.kill()
        signal.pidfd_send_signal(guardian, signal.SIGKILL)
        process.communicate(timeout=30)
        self.assert_dead(pidfd)
        self.assert_dead(manager)
        self.assertFalse(any(self.evidence.glob("run-*/client.json")))
        self.assert_manager_cleanup(child)

    def test_15_manager_runtime_cleans_wedged_guardian(self):
        process, ready, _, pidfd = self.orphan_start(wall=1, hold_ms=60000)
        self.stop_guardian(ready)
        # Leader exits while guardian is stopped; detached child outlives the
        # real manager runtime lease (23s), so its own 60s fallback cannot pass.
        process.stdin.write(b"G")
        process.stdin.flush()
        process.communicate(timeout=45)
        self.assertEqual(process.returncode, 125)
        self.assert_dead(pidfd)
        directory = next(self.evidence.glob("run-*"))
        manager = json.loads((directory / "manager.json").read_bytes())
        self.assertEqual(manager["service_result"], "timeout")
        client = json.loads((directory / "client.json").read_bytes())
        self.assertEqual(client["kind"], "manager-timeout")

    def test_16_finite_hard_as_preserved(self):
        def finite_as():
            resource.setrlimit(resource.RLIMIT_AS, (768 * MIB, 1536 * MIB))
        result, records = self.settled([OPTIONS.fixture, "inspect", "--"], preexec_fn=finite_as)
        inspect = json.loads(result.stdout.split(b"\n", 1)[0])
        self.assertEqual(inspect["rlimits"][resource.RLIMIT_AS]["soft"], 1536 * MIB)
        self.assertEqual(inspect["rlimits"][resource.RLIMIT_AS]["hard"], 1536 * MIB)
        self.assertEqual(records["caller"]["rlimits"][resource.RLIMIT_AS]["hard"], str(1536 * MIB))

    def test_17_unavailable_bus_never_executes(self):
        marker = self.evidence / "payload-marker"
        environment = dict(os.environ, DBUS_SESSION_BUS_ADDRESS="unix:path=/does-not-exist/minyar-bus")
        result = subprocess.run(self.argv(["/usr/bin/touch", str(marker)]), input=b"", capture_output=True,
                                env=environment, timeout=30)
        self.assertEqual(result.returncode, 125)
        self.assertFalse(marker.exists())
        directory = next(self.evidence.glob("run-*"))
        self.assertFalse(json.loads((directory / "client.json").read_bytes())["complete"])

    def test_18_default_virtual_cap_unchanged(self):
        result = subprocess.run(["zsh", str(ROOT / "scripts/with-limits.sh"), OPTIONS.fixture,
                                 "inspect", "--"], input=b"", capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        inspect = json.loads(result.stdout.split(b"\n", 1)[0])
        self.assertEqual(inspect["rlimits"][resource.RLIMIT_AS]["soft"], 768 * MIB)
        self.assertEqual(inspect["rlimits"][resource.RLIMIT_CPU]["soft"], 240)
        self.assertFalse(list(self.evidence.glob("run-*")))

    def test_19_concurrent_job_survives_other_job_oom(self):
        first_root = self.evidence
        process = subprocess.Popen(self.argv([OPTIONS.fixture, "term", "ignore", "15000"]),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop_process, process)
        ready = self.event(process, "term-ignore-ready")
        first_pidfd = os.pidfd_open(ready["pid"])
        self.addCleanup(os.close, first_pidfd)
        self.setUp()
        self.assert_oom([OPTIONS.fixture, "aggregate", str(48 * MIB), "1000"])
        with selectors.DefaultSelector() as selector:
            selector.register(first_pidfd, selectors.EVENT_READ)
            self.assertFalse(selector.select(0), "other job's OOM killed the control job")
        process.terminate()
        process.communicate(timeout=25)
        self.assertEqual(process.returncode, 143)
        self.evidence = first_root
        records = self.sidecars()
        self.assertTrue(records["client"]["complete"])
        self.assertEqual(records["client"]["kind"], "client-cancelled")
        self.assertEqual(records["client"]["memory_events_delta"]["oom"], 0)

    def test_20_restrictive_umask_and_affinity(self):
        def restricted_state():
            os.umask(0o777)
            os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
        _, records = self.settled(["/bin/true"], preexec_fn=restricted_state)
        self.assertEqual(records["caller"]["umask"], 0o777)
        self.assertEqual(len(records["caller"]["affinity"]), 1)
        directory = next(self.evidence.glob("run-*"))
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        for name in ("request.bin", "caller.json", "guardian.json", "manager.json", "client.json"):
            self.assertEqual((directory / name).stat().st_mode & 0o777, 0o600)


def main():
    global OPTIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--evidence-root", required=True)
    OPTIONS, remaining = parser.parse_known_args()
    OPTIONS.helper, OPTIONS.fixture = map(os.path.realpath, (OPTIONS.helper, OPTIONS.fixture))
    Path(OPTIONS.evidence_root).mkdir(parents=True, exist_ok=True)
    # Signal fixtures must not create a potentially huge inherited core file.
    _, hard = resource.getrlimit(resource.RLIMIT_CORE)
    resource.setrlimit(resource.RLIMIT_CORE, (0, hard))
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)


if __name__ == "__main__":
    main()
