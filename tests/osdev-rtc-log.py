#!/usr/bin/env python3
"""Strict serial-oracle regression tests; run with Python3 on BX only.

Imports the actual RTC test harness and invokes only qemu_log. No compiler,
runtime, guest, RTC implementation, or privileged I/O is loaded or executed.
Serial validation remains separate from the parent's QEMU exit-status proof.
"""

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest


# Importing the actual dataclasses needs a registered module. Avoid writing
# __pycache__ into the source checkout, including when this file is discovered.
sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().with_name("osdev-rtc.py")
SPEC = importlib.util.spec_from_file_location("_osdev_rtc_serial_oracle", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load actual RTC serial oracle: " + str(SOURCE))
RTC = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RTC
SPEC.loader.exec_module(RTC)

BASE = "2026-10-20T12:34:56"
START = "OSDEV RTC START"
CALENDAR = "OSDEV RTC 2026 10 20 12 34 57"
PASS = "OSDEV RTC PASS"
EXIT = "[minyar exited with status 0]"
VALID = (START, CALENDAR, PASS, EXIT)
MARKERS = "exactly one exact OSDEV RTC START and OSDEV RTC PASS"


class SerialOracleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="minyar-rtc-log-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "serial.log"

    def invoke(self, lines, base=BASE):
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            RTC.qemu_log(self.path, base)
        return output.getvalue()

    def reject(self, lines, message, base=BASE):
        with self.assertRaisesRegex(RTC.CheckFailure, message):
            self.invoke(lines, base)

    def test_actual_start_calendar_pass_log(self):
        self.assertEqual(
            self.invoke(VALID),
            "RTC serial calendar/marker passed (+1s); guest exit is verified separately\n",
        )

    def test_inclusive_zero_and_ten_second_boundaries(self):
        for row, elapsed in (("OSDEV RTC 2026 10 20 12 34 56", 0),
                             ("OSDEV RTC 2026 10 20 12 35 6", 10)):
            with self.subTest(elapsed=elapsed):
                self.assertIn(f"(+{elapsed}s)", self.invoke((START, row, PASS)))

    def test_calendar_rollover_within_tolerance(self):
        output = self.invoke((START, "OSDEV RTC 2027 1 1 0 0 1", PASS),
                             "2026-12-31T23:59:59")
        self.assertIn("(+2s)", output)

    def test_unrelated_boot_output_and_no_exit_claim(self):
        output = self.invoke(("loader ready", "", START, CALENDAR, PASS, "boot complete"))
        self.assertIn("guest exit is verified separately", output)

    def test_duplicate_calendar(self):
        self.reject((START, CALENDAR, CALENDAR, PASS), "exactly one RTC calendar")

    def test_missing_calendar(self):
        self.reject((START, PASS, EXIT), "exactly one RTC calendar")

    def test_malformed_calendar(self):
        for row in ("OSDEV RTC 2026 10 20 12 34", "OSDEV RTC 2026 10 20 12 34 57 0",
                    "OSDEV RTC 2026 10 20 12 34 nope", "OSDEV RTC 2026 10 20 12 34 +57",
                    "OSDEV RTC 2026 10 20 12 34 57.0", "OSDEV RTC 2026 10 20 12 34 57 "):
            with self.subTest(row=row):
                self.reject((START, row, PASS), "malformed RTC calendar")

    def test_invalid_calendar(self):
        for row in ("OSDEV RTC 2026 2 30 12 34 57", "OSDEV RTC 2026 10 20 12 34 60",
                    "OSDEV RTC 0 10 20 12 34 57"):
            with self.subTest(row=row):
                self.reject((START, row, PASS), "invalid RTC serial calendar")

    def test_duplicate_start(self):
        self.reject((START, START, CALENDAR, PASS), MARKERS)

    def test_missing_start(self):
        self.reject((CALENDAR, PASS, EXIT), MARKERS)

    def test_malformed_start(self):
        for marker in ("OSDEV RTC START ", " OSDEV RTC START", "OSDEV RTC STARTED"):
            with self.subTest(marker=marker):
                self.reject((marker, CALENDAR, PASS), MARKERS)

    def test_duplicate_pass(self):
        self.reject((START, CALENDAR, PASS, PASS), MARKERS)

    def test_missing_pass(self):
        self.reject((START, CALENDAR, EXIT), MARKERS)

    def test_malformed_pass(self):
        for marker in ("OSDEV RTC PASS ", " OSDEV RTC PASS", "OSDEV RTC PASSED"):
            with self.subTest(marker=marker):
                self.reject((START, CALENDAR, marker), MARKERS)

    def test_marker_order(self):
        for rows in ((CALENDAR, START, PASS), (START, PASS, CALENDAR),
                     (PASS, CALENDAR, START)):
            with self.subTest(rows=rows):
                self.reject(rows, "START, calendar, PASS in that order")

    def test_calendar_before_fixed_base(self):
        self.reject((START, "OSDEV RTC 2026 10 20 12 34 55", PASS), "required 0..10s")

    def test_calendar_after_tolerance(self):
        self.reject((START, "OSDEV RTC 2026 10 20 12 35 7", PASS), "required 0..10s")

    def test_invalid_base_format(self):
        for base in ("2026-10-20 12:34:56", "2026-10-20T12:34:56Z", "", "2026-1-20T12:34:56"):
            with self.subTest(base=base):
                self.reject(VALID, "must use YYYY-MM-DDTHH:MM:SS", base)

    def test_invalid_base_calendar(self):
        for base in ("2026-02-30T12:34:56", "2026-10-20T24:34:56", "2026-10-20T12:34:60"):
            with self.subTest(base=base):
                self.reject(VALID, "invalid RTC base", base)

    def test_base_outside_frozen_window(self):
        for base in ("1999-12-31T23:59:59", "2100-01-01T00:00:00"):
            with self.subTest(base=base):
                self.reject(VALID, "outside the frozen 2000..2099 year window", base)

    def test_error_after_pass(self):
        for line in ("ERROR late fault", "errors detected", "FAIL", "failed", "failure",
                     "kernel panic", "fatal", "assertion", "AddressSanitizer: fault",
                     "UndefinedBehaviorSanitizer: fault", "LeakSanitizer: fault", "Minyar stopped: fault"):
            with self.subTest(line=line):
                self.reject((*VALID, line), "error in guest log")

    def test_extra_rtc_garbage(self):
        for line in ("OSDEV RTC garbage", "OSDEV RTC START extra", "OSDEV RTC PASS extra",
                     "OSDEV RTC ", "OSDEV RTC 2026 10 20 12 34 58"):
            with self.subTest(line=line):
                self.reject((*VALID, line), "exactly one RTC calendar")

    def test_invalid_utf8(self):
        self.path.write_bytes(b"OSDEV RTC START\n\xff\nOSDEV RTC PASS\n")
        with self.assertRaises(UnicodeError):
            RTC.qemu_log(self.path, BASE)

    def test_empty_log(self):
        self.reject((), MARKERS)


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("run RTC serial-oracle tests on the BX Linux worker")
    unittest.main()
