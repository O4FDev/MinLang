#!/usr/bin/env python3
"""Exercise OS workflow failure handling without LLVM, a compiler or QEMU."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "tools/osdev.py"
SPEC = importlib.util.spec_from_file_location("osdev", DRIVER)
OSDEV = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OSDEV)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="osdev workflow ' , ")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.root = self.work / "checkout"
        (self.root / "os").mkdir(parents=True)
        (self.root / "os/Makefile").write_text("# fake build contract\n")
        (self.root / "os/kernel").mkdir()
        (self.root / "os/kernel/main.min").write_text("// desktop fixture\n")
        self.output = self.root / "build/os/x86_64"
        self.output.mkdir(parents=True)
        for name in ("kernel.elf", "minyar-os.img"):
            (self.output / name).write_text("fixture\n")
        self.bin = self.work / "tools"
        self.bin.mkdir()
        self.env = dict(os.environ, OSDEV_FAKE_MODE="success", OSDEV_FAKE_BUILD="success",
                        OSDEV_QEMU_TRACE=str(self.work / "qemu.json"),
                        OSDEV_BUILD_TRACE=str(self.work / "make.json"))
        self.qemu = self.executable("qemu fake", '''
import json, os, signal, sys
from pathlib import Path
Path(os.environ["OSDEV_QEMU_TRACE"]).write_text(json.dumps(sys.argv[1:]))
mode = os.environ["OSDEV_FAKE_MODE"]
status = 0 if "-M" in sys.argv else 1
if mode == "bad-status": status = 0
if mode == "stderr-marker":
    print("kernel checks passed", file=sys.stderr, flush=True)
elif mode != "missing":
    os.write(1, b"kernel checks ")
    os.write(1, b"passed\\r\\n")
if mode == "panic": print("PANIC: broken invariant", flush=True)
if mode == "guest-failure": print("[minyar exited with status 1]", flush=True)
if mode == "exception": print("Minyar OS processor exception 0e rip 0000000000100040", flush=True)
if mode == "runtime-success": print("[minyar exited with status 0]", flush=True)
if mode in ("hang", "closed-hang"):
    if mode == "closed-hang": os.close(1)
    signal.pause()
if mode == "chatty-hang":
    while True:
        os.write(1, b"still running\\n" * 4096)
sys.exit(status)
''')
        self.make = self.executable("make fake", '''
import json, os, signal, sys
from pathlib import Path
Path(os.environ["OSDEV_BUILD_TRACE"]).write_text(json.dumps(sys.argv[1:]))
if os.environ["OSDEV_FAKE_BUILD"] == "hang": signal.pause()
sys.exit(9 if os.environ["OSDEV_FAKE_BUILD"] == "fail" else 0)
''')
        for name in ("clang", "ld.lld", "llvm-objcopy"):
            self.executable(name, "pass\n")
        self.log = self.work / "serial log.txt"

    def executable(self, name, body):
        path = self.bin / name
        path.write_text("#!" + sys.executable + "\n" + body)
        path.chmod(0o755)
        return path

    def invoke(self, action="test", *extra, mode="success", build="success", expected=0, no_build=True):
        command = [sys.executable, str(DRIVER), action, "--root", str(self.root),
                   "--log", str(self.log), "--qemu", str(self.qemu), "--make", str(self.make),
                   "--llvm-bin", str(self.bin)]
        if action == "test":
            command += ["--expect", "kernel checks passed", "--timeout", "0.3"]
        if no_build:
            command.append("--no-build")
        command += list(extra)
        env = dict(self.env, OSDEV_FAKE_MODE=mode, OSDEV_FAKE_BUILD=build)
        result = subprocess.run(command, env=env, capture_output=True, timeout=12)
        self.assertEqual(result.returncode, expected, result.stdout.decode() + result.stderr.decode())
        return result

    def test_finite_x86_guest_and_serial_line(self):
        result = self.invoke()
        self.assertIn(b"test passed", result.stderr)
        self.assertEqual(self.log.read_bytes(), b"kernel checks passed\r\n")
        command = json.loads((self.work / "qemu.json").read_text())
        self.assertIn("isa-debug-exit,iobase=0xf4,iosize=0x04", command)
        self.assertIn("-no-reboot", command)
        self.assertIn("-monitor", command)
        self.assertIn("snapshot=on", command[command.index("-drive") + 1])
        self.assertIn("' ,, ", command[command.index("-drive") + 1])

    def test_finite_arm_guest(self):
        arm = self.root / "build/os/arm64"
        arm.mkdir()
        for name in ("kernel.elf", "minyar-os.img"):
            (arm / name).write_text("fixture")
        self.invoke("test", "--arch", "arm64")
        command = json.loads((self.work / "qemu.json").read_text())
        self.assertEqual(command[command.index("-M") + 1], "virt,gic-version=3")
        self.assertIn(str(arm / "kernel.elf"), command)
        self.assertIn("virtio-rng-pci,disable-legacy=on", command)

    def test_missing_marker_rejects_stale_serial_log(self):
        self.log.write_text("kernel checks passed\n")
        self.invoke(mode="missing", expected=1)
        self.assertEqual(self.log.read_bytes(), b"")

    def test_success_marker_does_not_hide_failure(self):
        for mode in ("panic", "exception", "guest-failure", "bad-status"):
            with self.subTest(mode=mode):
                self.invoke(mode=mode, expected=1)

    def test_host_diagnostics_are_not_guest_evidence(self):
        self.invoke(mode="stderr-marker", expected=1)
        self.assertEqual(self.log.read_bytes(), b"")

    def test_run_does_not_translate_qemu_failure_to_success(self):
        self.invoke("run", mode="missing", expected=1)
        self.invoke("run", mode="runtime-success")

    def test_deadline_after_marker_is_failure(self):
        for mode in ("hang", "closed-hang"):
            with self.subTest(mode=mode):
                result = self.invoke(mode=mode, expected=124)
                self.assertIn(b"timed out", result.stderr)
                self.assertIn(b"kernel checks passed", self.log.read_bytes())

    def test_continuous_serial_output_cannot_extend_deadline(self):
        command = [sys.executable, str(DRIVER), "test", "--root", str(self.root),
                   "--log", str(self.log), "--qemu", str(self.qemu), "--no-build",
                   "--expect", "kernel checks passed", "--timeout", "0.1"]
        # Discard the terminal copy while retaining the real serial log, so a
        # continuously writing guest cannot exhaust the test runner's memory.
        result = subprocess.run(command, env=dict(self.env, OSDEV_FAKE_MODE="chatty-hang"),
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, 124, result.stderr.decode())
        self.assertIn(b"timed out", result.stderr)
        self.assertGreater(self.log.stat().st_size, 65536)

    def test_exact_line_not_substring(self):
        self.invoke("test", "--expect", "checks passed", expected=1)

    def test_make_reuses_build_and_forces_changed_source(self):
        source = self.work / "test kernel.min"
        source.write_text('print("kernel checks passed")\n')
        self.invoke("test", "--kernel-source", str(source), no_build=False)
        command = json.loads((self.work / "make.json").read_text())
        self.assertIn("ARCH=x86_64", command)
        self.assertIn(f"LLVM_BIN={self.bin}", command)
        self.assertEqual(command[command.index("-W") + 1], str(source))
        self.assertIn(f"KERNEL_SOURCE={source}", command)
        self.assertEqual(command[-1], "all")
        # Returning to the default kernel must also invalidate the old test.
        self.invoke(no_build=False)
        command = json.loads((self.work / "make.json").read_text())
        self.assertIn(f"KERNEL_SOURCE={self.root / 'os/kernel/main.min'}", command)
        self.assertIn("-W", command)

    def test_existing_image_cannot_claim_a_new_kernel_source(self):
        self.invoke("test", "--kernel-source", str(self.root / "os/kernel/main.min"), expected=2)
        self.assertFalse((self.work / "qemu.json").exists())

    def test_build_failure_and_timeout_never_boot(self):
        for mode, status in (("fail", 9), ("hang", 124)):
            with self.subTest(mode=mode):
                self.invoke("test", "--build-timeout", "0.1", build=mode, expected=status, no_build=False)
                self.assertFalse((self.work / "qemu.json").exists())

    def test_missing_tools_and_artifacts_are_diagnosed(self):
        result = self.invoke("test", "--qemu", str(self.work / "no qemu"), expected=2)
        self.assertIn(b"missing executable", result.stderr)
        (self.output / "kernel.elf").unlink()
        result = self.invoke(expected=2)
        self.assertIn(b"kernel.elf", result.stderr)

    def test_build_tools_checked_before_build(self):
        (self.bin / "llvm-objcopy").unlink()
        result = self.invoke(no_build=False, expected=2)
        self.assertIn(b"llvm-objcopy", result.stderr)
        self.assertFalse((self.work / "make.json").exists())

    def test_debug_is_stopped_and_loopback_only(self):
        self.invoke("debug", "--gdb-port", "9123", mode="runtime-success")
        command = json.loads((self.work / "qemu.json").read_text())
        self.assertIn("-S", command)
        self.assertEqual(command[command.index("-gdb") + 1], "tcp:127.0.0.1:9123")

    def test_dry_run_has_no_tool_or_log_side_effects(self):
        self.invoke("test", "--dry-run", "--qemu", "/missing/qemu", no_build=False)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.work / "make.json").exists())
        self.assertFalse((self.work / "qemu.json").exists())

    def test_log_cannot_destroy_artifacts(self):
        self.invoke("test", "--log", str(self.output / "kernel.elf"), expected=2)
        alias = self.work / "kernel hard link"
        os.link(self.output / "kernel.elf", alias)
        self.invoke("test", "--log", str(alias), expected=2)
        self.assertEqual((self.output / "kernel.elf").read_text(), "fixture\n")

    def test_invalid_deadlines_are_rejected(self):
        for value in ("0", "-1", "nan", "inf"):
            with self.subTest(value=value):
                self.invoke("test", "--timeout", value, expected=2)

    def test_instruction_log_extracts_code_not_fault_registers(self):
        source = "Minyar OS processor exception 0e error 0 rip 0000000000100040 rsp 0000abcd cr2 00000bad\n"
        source += "Minyar stopped: synchronous exception (vector 0) at 0x40080040, ESR 0x123, FAR 0x456\n"
        self.assertEqual(OSDEV.instruction_addresses(source), ["0000000000100040", "0x40080040"])

    def test_symbolization_uses_exact_elf_and_address(self):
        trace = self.work / "symbolizer.json"
        symbolizer = self.executable("llvm-symbolizer", f'''
import json, sys
from pathlib import Path
Path({str(trace)!r}).write_text(json.dumps(sys.argv[1:]))
print("kernel_main\\n??:0:0\\n")
''')
        self.log.write_text("Minyar OS processor exception 0e rip 0000000000100040 rsp 00001234\n")
        command = [sys.executable, str(DRIVER), "symbolize", "--root", str(self.root),
                   "--log", str(self.log), "--symbolizer", str(symbolizer)]
        result = subprocess.run(command, capture_output=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"kernel_main", result.stdout)
        argv = json.loads(trace.read_text())
        self.assertIn("--obj=" + str(self.output / "kernel.elf"), argv)
        self.assertEqual(argv[-1], "0x0000000000100040")
        self.assertNotIn("00001234", argv)

    def test_addr2line_dry_run_and_invalid_addresses(self):
        base = [sys.executable, str(DRIVER), "symbolize", "--root", str(self.root)]
        result = subprocess.run(base + ["--symbolizer", "addr2line", "--dry-run", "0x100040"],
                                capture_output=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn("-e", shlex.split(result.stderr.decode().splitlines()[0][2:]))
        for addresses in ([], ["0xinvalid"]):
            result = subprocess.run(base + addresses, capture_output=True, timeout=12)
            self.assertEqual(result.returncode, 2, result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
