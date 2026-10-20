#!/usr/bin/env python3
"""Check the actual seed-study evidence boundary with independent fake processes.

Install beside osdev-seeds.py in tests/. Run on Boat; no LLVM, Minyar compiler,
production runtime, privileged I/O or QEMU is required. No child uses a shell.
"""

import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tests/osdev-seeds.py"
SPEC = importlib.util.spec_from_file_location("_osdev_seeds_evidence", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load seed study: " + str(SOURCE))
SEEDS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SEEDS
SPEC.loader.exec_module(SEEDS)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="osdev seed evidence ' , ")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.tree = self.work / "source tree"
        self.tree.mkdir()
        self.source = self.tree / "case.min"
        self.source.write_text("function main(): Integer { return 0 }\n")
        self.compiler = self.executable("compiler fake", "raise SystemExit(0)\n")
        self.study = SEEDS.Study(SimpleNamespace(
            compiler=str(self.compiler), runtime=str(self.work / "unused-runtime.o"),
            clang=str(self.compiler), output=self.work / "evidence", no_qemu=True,
            keep_trees=True,
        ))
        self.study.out.mkdir()

    def executable(self, name, body):
        path = self.work / name
        path.write_text("#!" + sys.executable + "\n" + body)
        path.chmod(0o755)
        return path

    def compiler_body(self, body):
        self.compiler.write_text("#!" + sys.executable + "\n"
                                 "import os, signal, sys\nfrom pathlib import Path\n"
                                 "source, output = map(Path, sys.argv[1:3])\n" + body)

    def compile(self):
        return self.study.minyar_compile(self.tree, "case.min", False)

    def last_event(self):
        self.assertTrue(self.study.log, "the failure must retain its command evidence")
        return self.study.log[-1]

    def test_normal_process_retains_non_timeout_event(self):
        child = self.executable("success child", 'print("ordinary output")\n')
        status, stdout, stderr = self.study.run("normal-child", [child])
        self.assertEqual((status, stdout, stderr), (0, "ordinary output\n", ""))
        self.assertIs(self.last_event()["timed_out"], False)

    def test_real_timeout_is_invalid_study(self):
        child = self.executable("blocked child", 'import signal\nprint("before timeout", flush=True)\nsignal.pause()\n')
        with self.assertRaises(SEEDS.StudyFailure):
            self.study.run("actual-timeout", [child], timeout=2)
        event = self.last_event()
        self.assertEqual(event["label"], "actual-timeout")
        self.assertEqual(event["status"], 124)
        self.assertIs(event["timed_out"], True)
        # Deterministic bytes/None coverage below separately checks partial text;
        # an overloaded host may time out before this child starts writing.
        self.assertIsInstance(event["stdout"], str)
        self.assertIsInstance(event["stderr"], str)

    def test_timeout_partial_bytes_and_none_are_normalized(self):
        for stdout, stderr in ((b"partial output\n", b"partial error\xff\n"), (None, None)):
            with self.subTest(stdout=stdout, stderr=stderr):
                self.study.log.clear()
                process = mock.Mock()
                process.pid = 987654321
                process.returncode = -signal.SIGKILL
                process.poll.return_value = process.returncode
                process.communicate.side_effect = [
                    subprocess.TimeoutExpired(["fake"], 1, output=stdout, stderr=stderr),
                    (stdout, stderr),
                ]
                with mock.patch.object(SEEDS.subprocess, "Popen", return_value=process), \
                     mock.patch.object(SEEDS.os, "killpg") as kill_group:
                    with self.assertRaises(SEEDS.StudyFailure):
                        self.study.run("synthetic-timeout", ["fake"], timeout=1)
                kill_group.assert_called_once_with(process.pid, signal.SIGKILL)
                event = self.last_event()
                self.assertIs(event["timed_out"], True)
                self.assertEqual(event["status"], 124)
                self.assertEqual(event["stdout"], "partial output\n" if stdout else "")
                self.assertIn("partial error\ufffd\n" if stderr else "", event["stderr"])
                self.assertIsInstance(event["stderr"], str)

    def test_explicit_timeout_status_is_invalid_study(self):
        child = self.executable("timeout status child", "raise SystemExit(124)\n")
        with self.assertRaises(SEEDS.StudyFailure):
            self.study.run("reserved-timeout-status", [child])
        self.assertEqual(self.last_event()["status"], 124)
        self.assertIs(self.last_event()["timed_out"], True)

    def test_successful_compiler_requires_fresh_nonempty_llvm(self):
        for mode in ("fresh", "missing", "empty", "stale"):
            with self.subTest(mode=mode):
                output = self.tree / "out.ll"
                output.unlink(missing_ok=True)
                if mode == "stale":
                    output.write_text("define i32 @old() { ret i32 0 }\n")
                body = "raise SystemExit(0)\n"
                if mode == "fresh":
                    body = 'output.write_text("define i32 @main() { ret i32 0 }\\n")\n'
                elif mode == "empty":
                    body = 'output.write_text("")\n'
                self.compiler_body(body)
                if mode == "fresh":
                    passed, detail = self.compile()
                    self.assertTrue(passed, detail)
                    self.assertTrue(output.read_text())
                else:
                    with self.assertRaises(SEEDS.StudyFailure):
                        self.compile()

    def test_semantic_compiler_rejection_is_accepted(self):
        self.compiler_body('print(f"{source}:3:5: error: DMA ownership: binding already moved", file=sys.stderr)\n'
                           'raise SystemExit(1)\n')
        passed, detail = self.compile()
        self.assertFalse(passed, detail)
        self.assertFalse((self.tree / "out.ll").exists())
        self.assertIs(self.last_event()["timed_out"], False)

    def test_compiler_faults_cannot_establish_source_rejection(self):
        cases = {
            "status2": 'print(f"{source}:3:5: error: DMA ownership: binding already moved", file=sys.stderr)\nraise SystemExit(2)\n',
            "garbage": 'print("a source rejection supposedly happened", file=sys.stderr)\nraise SystemExit(1)\n',
            "no-location": 'print("error: DMA ownership: binding already moved", file=sys.stderr)\nraise SystemExit(1)\n',
            "no-error": 'print(f"{source}:3:5: DMA ownership: binding already moved", file=sys.stderr)\nraise SystemExit(1)\n',
            "emitted-llvm": 'output.write_text("define i32 @stale() { ret i32 0 }\\n")\nprint(f"{source}:3:5: error: DMA ownership: binding already moved", file=sys.stderr)\nraise SystemExit(1)\n',
            "llvm-error": 'print(f"{source}:3:5: error: DMA ownership: binding already moved\\nLLVM ERROR: instruction selection failed", file=sys.stderr)\nraise SystemExit(1)\n',
            "internal-error": 'print(f"{source}:3:5: error: internal compiler error: DMA ownership", file=sys.stderr)\nraise SystemExit(1)\n',
            "traceback": 'print(f"{source}:3:5: error: DMA ownership: binding already moved\\nTraceback (most recent call last):", file=sys.stderr)\nraise SystemExit(1)\n',
            "sanitizer": 'print(f"{source}:3:5: error: DMA ownership: binding already moved\\nERROR: AddressSanitizer: heap-buffer-overflow", file=sys.stderr)\nraise SystemExit(1)\n',
            "ubsan": 'print(f"{source}:3:5: error: DMA ownership: binding already moved\\nruntime error: signed integer overflow", file=sys.stderr)\nraise SystemExit(1)\n',
            "signal": 'import resource\nresource.setrlimit(resource.RLIMIT_CORE, (0, 0))\nos.kill(os.getpid(), signal.SIGSEGV)\n',
        }
        for name, body in cases.items():
            with self.subTest(name=name):
                (self.tree / "out.ll").unlink(missing_ok=True)
                self.compiler_body(body)
                with self.assertRaises(SEEDS.StudyFailure):
                    self.compile()
                self.assertIs(self.last_event()["timed_out"], False)

    def test_build_failures_are_invalid_study(self):
        self.study.require_build("valid-link", 0, "")
        for status in (1, 2, -signal.SIGSEGV, 124):
            with self.subTest(status=status):
                with self.assertRaises(SEEDS.StudyFailure):
                    self.study.require_build("fixture-link", status, "fixture failed")

    def test_host_sanitizer_failure_remains_execution_evidence(self):
        for diagnostic in ("ERROR: AddressSanitizer: heap-buffer-overflow", "runtime error: signed integer overflow"):
            with self.subTest(diagnostic=diagnostic):
                child = self.executable("sanitizer child", "import sys\nprint(" + repr(diagnostic) + ", file=sys.stderr)\nraise SystemExit(1)\n")
                status, stdout, stderr = self.study.run("host-execution", [child])
                self.assertEqual(status, 1)
                self.assertEqual(stdout, "")
                self.assertIn(diagnostic, stderr)
                self.assertIs(self.last_event()["timed_out"], False)

    def test_ladder_requires_the_expected_minyar_diagnostic_family(self):
        source = self.tree / "os/tests/rtc-kernel.min"
        source.parent.mkdir(parents=True)
        source.write_text("function main(): Integer { return 0 }\n")
        # Bypass expensive checkout copying, while exercising the real compiler
        # validation and the real ladder's seed-specific evidence check.
        self.study.tree = lambda name, edit: self.tree
        for message, accepted in (
                ("register field 'afternoon' overlaps 'value'", True),
                ("unknown module 'missing-fixture'", False)):
            with self.subTest(message=message):
                self.compiler_body('print(str(source) + ":3:5: error: " + ' + repr(message) + ', file=sys.stderr)\n'
                                   'raise SystemExit(1)\n')
                if accepted:
                    outcome, evidence, warned = self.study.ladder("field-width", "minyar", "rtc", None)
                    self.assertEqual(outcome, "compile")
                    self.assertFalse(warned)
                else:
                    with self.assertRaises(SEEDS.StudyFailure):
                        self.study.ladder("field-width", "minyar", "rtc", None)

    def rtc_events(self):
        return [dict(stage=stage, status=0, timed_out=False) for stage in (
            "runtime-build", "decode-compile", "decode-link-O0", "decode-run-O0",
            "decode-link-O2", "decode-run-O2", "reader-compile", "reader-link-O0",
            "reader-run-O0", "reader-link-O2", "reader-run-O2",
        )]

    def invoke_rtc_events(self, events, status=1, stderr="RTC oracle FAILED: run failed"):
        artifacts = self.study.out / "oracle-artifacts" / self.tree.name
        artifacts.mkdir(parents=True, exist_ok=True)
        evidence = artifacts / "events.json"
        evidence.unlink(missing_ok=True)

        def fake_child(label, command, **options):
            self.assertIn("--artifacts", command)
            self.assertEqual(Path(command[command.index("--artifacts") + 1]), artifacts)
            if events is not None:
                evidence.write_text(events if isinstance(events, str) else json.dumps(events))
            return status, "", stderr

        with mock.patch.object(self.study, "run", side_effect=fake_child):
            return self.study.minyar_rtc_host(self.tree)

    def test_nested_rtc_semantic_run_and_output_failures_are_detection(self):
        for status in (0, 1):
            with self.subTest(run_status=status):
                events = self.rtc_events()[:4]
                events[-1]["status"] = status
                message = ("RTC oracle FAILED: decode O0: output/diagnostic mismatch" if status == 0
                           else "RTC oracle FAILED: decode-run-O0 failed with status 1")
                passed, detail = self.invoke_rtc_events(events, stderr=message)
                self.assertFalse(passed, detail)
        passed, detail = self.invoke_rtc_events(self.rtc_events(), status=0, stderr="")
        self.assertTrue(passed, detail)

    def test_nested_rtc_tracebacks_cannot_count_as_detection(self):
        for run_status in (0, 1):
            with self.subTest(run_status=run_status):
                events = self.rtc_events()[:4]
                events[-1]["status"] = run_status
                message = ("Traceback (most recent call last):\n"
                           "  raise CheckFailure('output/diagnostic mismatch')\n"
                           "NameError: failure while reporting the oracle result\n")
                with self.assertRaises(SEEDS.StudyFailure):
                    self.invoke_rtc_events(events, stderr=message)

    def test_nested_rtc_zero_status_mismatch_needs_oracle_report(self):
        events = self.rtc_events()[:4]
        with self.assertRaises(SEEDS.StudyFailure):
            self.invoke_rtc_events(events, stderr="unrelated output/diagnostic mismatch")
        passed, detail = self.invoke_rtc_events(
            events, stderr="RTC oracle artifacts: /fixture\nRTC oracle FAILED: decode O0: output/diagnostic mismatch\n")
        self.assertFalse(passed, detail)

    def test_nested_rtc_runtime_sanitizer_failure_remains_detection(self):
        events = self.rtc_events()[:4]
        events[-1]["status"] = 1
        message = ("RTC oracle FAILED: decode-run-O0 failed with status 1\n"
                   "ERROR: AddressSanitizer: heap-buffer-overflow\n")
        passed, detail = self.invoke_rtc_events(events, stderr=message)
        self.assertFalse(passed, detail)
        self.assertIn("AddressSanitizer", "\n".join(detail))

    def test_nested_rtc_build_failures_and_timeouts_invalidate(self):
        for index, timed_out in ((0, False), (1, False), (2, False), (3, True)):
            with self.subTest(index=index, timed_out=timed_out):
                events = self.rtc_events()[:index + 1]
                events[-1].update(status=124 if timed_out else 1, timed_out=timed_out)
                with self.assertRaises(SEEDS.StudyFailure):
                    self.invoke_rtc_events(events)

    def test_nested_rtc_incomplete_or_inconsistent_events_invalidate(self):
        cases = [
            (None, 1, "missing evidence"),
            ("not JSON", 1, "malformed evidence"),
            ([], 1, "empty evidence"),
            ([17], 1, "invalid event"),
            ([dict(stage="decode-run-O0", status=None, timed_out=False)], 1, "missing status"),
            ([dict(stage="decode-run-O0", status="1", timed_out=False)], 1, "non-integer status"),
            (self.rtc_events()[:3], 1, "output/diagnostic mismatch"),
            (self.rtc_events()[:1], 0, ""),
            ([dict(stage="bogus-run-x", status=1, timed_out=False)], 1, "run failure"),
            ([dict(stage="decode-run-O0", status=0, timed_out=False)] * 4, 0, ""),
            ([event for event in self.rtc_events() if "-run-" in event["stage"]], 0, ""),
        ]
        bad_success = self.rtc_events()
        bad_success[-1]["status"] = 1
        cases.append((bad_success, 0, ""))
        runtime_failure = self.rtc_events()[:4]
        runtime_failure[-1]["status"] = 1
        cases.append((runtime_failure, 2, "output/diagnostic mismatch"))
        for events, status, message in cases:
            with self.subTest(events=events, status=status, message=message):
                with self.assertRaises(SEEDS.StudyFailure):
                    self.invoke_rtc_events(events, status, message)

    def c_fixture(self, name):
        tree = self.work / name
        tree.mkdir()
        source = tree / SEEDS.C_RTC
        source.parent.mkdir(parents=True)
        source.write_text("int main(void) { return 0; }\n")
        return tree

    def c_compiler_body(self, body):
        self.compiler.write_text("#!" + sys.executable + "\n"
                                 "import os, signal, sys\nfrom pathlib import Path\n"
                                 "output = Path(sys.argv[sys.argv.index('-o') + 1])\n"
                                 "source = next(Path(a) for a in sys.argv[1:] if a.endswith('.c'))\n" + body)

    def test_c_initial_width_rejection_is_the_only_accepted_failure(self):
        tree = self.c_fixture("wrong-port-width-c")
        diagnostic = 'print(f"{source}:144:23: error: invalid operand for instruction", file=sys.stderr)\n'
        self.c_compiler_body(diagnostic + "raise SystemExit(1)\n")
        passed, detail, warned = self.study.c_compile(tree, "rtc")
        self.assertFalse(passed, detail)
        self.assertFalse(warned)
        other = self.c_fixture("unrelated-mutant-c")
        with self.assertRaises(SEEDS.StudyFailure):
            self.study.c_compile(other, "rtc")

    def test_c_compiler_infrastructure_cannot_hide_behind_width_error(self):
        tree = self.c_fixture("wrong-port-width-c")
        diagnostic = 'print(f"{source}:144:23: error: invalid operand for instruction", file=sys.stderr)\n'
        cases = {
            "missing-header": 'print(f"{source}:1:1: fatal error: missing.h file not found", file=sys.stderr)\nraise SystemExit(1)\n',
            "status2": diagnostic + "raise SystemExit(2)\n",
            "llvm-error": diagnostic + 'print("LLVM ERROR: backend crash", file=sys.stderr)\nraise SystemExit(1)\n',
            "sanitizer": diagnostic + 'print("ERROR: AddressSanitizer: heap-buffer-overflow", file=sys.stderr)\nraise SystemExit(1)\n',
            "ubsan": diagnostic + 'print("runtime error: signed integer overflow", file=sys.stderr)\nraise SystemExit(1)\n',
            "emitted-artifact": diagnostic + 'output.write_text("stale object")\nraise SystemExit(1)\n',
        }
        for name, body in cases.items():
            with self.subTest(name=name):
                (tree / "rtc.o").unlink(missing_ok=True)
                self.c_compiler_body(body)
                with self.assertRaises(SEEDS.StudyFailure):
                    self.study.c_compile(tree, "rtc")

    def test_c_compiler_success_needs_fresh_artifact(self):
        tree = self.c_fixture("baseline-rtc-c")
        artifact = tree / "rtc.o"
        for mode in ("fresh", "missing", "empty", "stale"):
            with self.subTest(mode=mode):
                artifact.unlink(missing_ok=True)
                if mode == "stale":
                    artifact.write_text("stale executable")
                body = 'output.write_text("fresh executable")\n' if mode == "fresh" else "raise SystemExit(0)\n"
                if mode == "empty":
                    body = 'output.write_text("")\n'
                self.c_compiler_body(body)
                if mode == "fresh":
                    passed, detail, warned = self.study.c_compile(tree, "rtc")
                    self.assertTrue(passed, detail)
                    self.assertFalse(warned)
                else:
                    with self.assertRaises(SEEDS.StudyFailure):
                        self.study.c_compile(tree, "rtc")

    def test_later_host_link_and_build_errors_invalidate(self):
        empty_oracle = SimpleNamespace(decode_cases=lambda: [], read_cases=lambda: [])
        for method in ("minyar_dma_host", "c_dma_host", "c_rtc_host"):
            with self.subTest(method=method):
                with mock.patch.object(SEEDS, "load_oracle", return_value=empty_oracle), \
                     mock.patch.object(self.study, "run", return_value=(1, "", "linker failed")) as child:
                    with self.assertRaises(SEEDS.StudyFailure):
                        getattr(self.study, method)(self.tree)
                    self.assertEqual(child.call_count, 1)

    def test_c_dma_sanitizer_execution_remains_host_detection(self):
        with mock.patch.object(self.study, "run", side_effect=[
                (0, "", ""), (1, "", "ERROR: AddressSanitizer: heap-buffer-overflow\n")]):
            passed, detail = self.study.c_dma_host(self.tree)
        self.assertFalse(passed)
        self.assertIn("AddressSanitizer", "\n".join(detail))

    def test_dma_success_marker_cannot_hide_runtime_diagnostics(self):
        for method, marker in (("minyar_dma_host", "MINYAR ENTROPY HOST PASS\n"),
                               ("c_dma_host", "C ENTROPY HOST PASS\n")):
            with self.subTest(method=method):
                with mock.patch.object(self.study, "run", side_effect=[
                        (0, "", ""), (0, marker, "runtime error: signed integer overflow\n")]):
                    passed, detail = getattr(self.study, method)(self.tree)
                self.assertFalse(passed, detail)

    def qemu_fixture(self, name):
        tree = self.work / name
        (tree / "os").mkdir(parents=True)
        (tree / "os/Makefile").write_text("# fake kernel build\n")
        base = self.work / "baseline qemu"
        built = base / "build/os/x86_64"
        built.mkdir(parents=True, exist_ok=True)
        for filename in ("mbr.bin", "loader.bin", "config.txt"):
            (built / filename).write_text("fixture\n")
        self.study.base_qemu_tree = base
        self.study.prepare_c_support = mock.Mock(return_value=dict(
            objects=[base / "runtime.o", base / "freestanding.o", base / "entry.o"],
            resource=base / "include",
        ))
        return tree

    def test_qemu_build_failures_are_never_guest_detection(self):
        for method, phases in (("minyar_qemu", ("minyar-os-build",)),
                               ("c_qemu", ("c-guest-compile", "c-guest-link", "c-guest-image"))):
            for phase in phases:
                with self.subTest(method=method, phase=phase):
                    tree = self.qemu_fixture(method + "-" + phase)
                    labels = []

                    def fake_child(label, command, **options):
                        labels.append(label)
                        return (1, "", "build failure") if label.endswith("/" + phase) else (0, "", "")

                    with mock.patch.object(self.study, "run", side_effect=fake_child):
                        with self.assertRaises(SEEDS.StudyFailure):
                            getattr(self.study, method)(tree)
                    self.assertTrue(labels[-1].endswith("/" + phase))

    def test_qemu_requires_guest_serial_evidence_on_failure(self):
        for method in ("minyar_qemu", "c_qemu"):
            for mode in ("no-serial", "stderr-only", "guest-stop", "bad-status"):
                with self.subTest(method=method, mode=mode):
                    tree = self.qemu_fixture(method + "-" + mode)
                    serial = tree / ("serial.log" if method == "minyar_qemu" else "c-serial.log")

                    def fake_child(label, command, **options):
                        if label.endswith("/minyar-qemu") or label.endswith("/c-qemu"):
                            text = "OSDEV RTC START\nMinyar stopped: fixture guest failure\n"
                            if mode in ("guest-stop", "bad-status"):
                                serial.write_text(text)
                            return (2 if mode == "bad-status" else 1), "", text if mode == "stderr-only" else "QEMU failed"
                        return 0, "", ""

                    with mock.patch.object(self.study, "run", side_effect=fake_child):
                        if mode == "guest-stop":
                            passed, detail = getattr(self.study, method)(tree)
                            self.assertFalse(passed, detail)
                            self.assertIn("fixture guest failure", "\n".join(detail))
                        else:
                            with self.assertRaises(SEEDS.StudyFailure):
                                getattr(self.study, method)(tree)

    def test_qemu_serial_validator_must_fail_semantically(self):
        serial = self.tree / "serial.log"
        serial.write_text("OSDEV RTC START\nOSDEV RTC 2009 8 7 4 2 0\nOSDEV RTC PASS\n")
        cases = (
            (0, "RTC serial calendar/marker passed (+1s); guest exit is verified separately\n", "", True),
            (1, "", "RTC oracle FAILED: RTC serial calendar is -542882000s from fixed base; required 0..10s\n", False),
        )
        for status, stdout, stderr, expected in cases:
            with self.subTest(status=status, stderr=stderr):
                with mock.patch.object(self.study, "run", return_value=(status, stdout, stderr)):
                    passed, detail = self.study.qemu_log_valid(self.tree, serial)
                self.assertEqual(passed, expected, detail)
        for status, message in ((1, "Traceback (most recent call last): validator crashed"),
                                (2, "python3: cannot open validator script"),
                                (1, "RTC oracle FAILED: missing kernel file"),
                                (1, "RTC oracle FAILED: RTC serial calendar is -542882000s from fixed base; required 0..10s\nTraceback (most recent call last): validator crashed")):
            with self.subTest(status=status, message=message):
                with mock.patch.object(self.study, "run", return_value=(status, "", message)):
                    with self.assertRaises(SEEDS.StudyFailure):
                        self.study.qemu_log_valid(self.tree, serial)


class ReadOnlySeedTests(unittest.TestCase):
    def test_paired_read_only_write_keeps_original_selector_last(self):
        matches = [seed for seed in SEEDS.SEEDS if seed.name == "read-only-register-write"]
        self.assertEqual(len(matches), 1)
        seed = matches[0]
        self.assertEqual(seed.driver, "rtc")
        self.assertIsNotNone(seed.minyar)
        self.assertIsNotNone(seed.c)
        self.assertEqual(seed.minyar.path, "os/arch/x86_64/rtc.min")
        self.assertEqual([line.strip() for line in seed.minyar.new.splitlines() if line.strip()], [
            "device.out8(selector, 13)", "device.out8(data, 0)", "device.out8(selector, index)",
        ])
        self.assertEqual(seed.minyar.old.strip(), "device.out8(selector, index)")
        self.assertEqual(seed.minyar.new.count(seed.minyar.old.strip()), 1)
        self.assertEqual(seed.c.path, "tests/osdev-seeds/c/rtc.c")
        operations = [line.strip() for line in seed.c.new.splitlines() if line.strip()]
        self.assertEqual(len(operations), 3)
        self.assertEqual(operations[-1], seed.c.old.strip())
        self.assertEqual(seed.c.new.count("outb %0, %1"), 3)
        self.assertRegex(operations[0], r'"a"\(\(uint8_t\)13\).*"Nd"\(\(uint16_t\)0x70\)')
        self.assertRegex(operations[1], r'"a"\(\(uint8_t\)0\).*"Nd"\(\(uint16_t\)0x71\)')
        self.assertIn('"a"(register_index)', operations[-1])
        self.assertEqual(SEEDS.EXPECTED[seed.name], ("undetected", "undetected"))
        for edit in (seed.minyar, seed.c):
            with self.subTest(path=edit.path):
                original = (ROOT / edit.path).read_text()
                self.assertEqual(original.count(edit.old), 1)
                changed = original.replace(edit.old, edit.new)
                self.assertIn(edit.new, changed)
                self.assertNotEqual(original, changed)


if __name__ == "__main__":
    unittest.main()
