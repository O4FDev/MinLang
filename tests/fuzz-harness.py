#!/usr/bin/env python3
"""Fault injection for the semantic fuzz oracle and candidate selection."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("minyar_fuzz", Path(__file__).with_name("fuzz.py"))
fuzz = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fuzz)


class FuzzHarness(unittest.TestCase):
    def test_environment_selects_candidate_compiler_and_runtime(self):
        with patch.dict(os.environ, MINYAR_TEST_COMPILER="/candidate/compiler", MINYAR_TEST_RUNTIME="/candidate/runtime.o"):
            candidate = importlib.util.module_from_spec(SPEC)
            SPEC.loader.exec_module(candidate)
        self.assertEqual(candidate.DEFAULT_COMPILER, Path("/candidate/compiler"))
        self.assertEqual(candidate.RUNTIME, Path("/candidate/runtime.o"))

    def test_correct_stdout_does_not_hide_runtime_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            expected = f"{fuzz.expression(fuzz.random.Random(42))[1]}\n"
            outcomes = [subprocess.CompletedProcess([], 0, "", ""),
                        subprocess.CompletedProcess([], 0, "", ""),
                        subprocess.CompletedProcess([], 0, expected, "runtime warning\n")]
            with patch.object(fuzz, "run", side_effect=outcomes):
                with self.assertRaises(AssertionError):
                    fuzz.check_expression_batch(Path("compiler"), "clang", 1, Path(directory), 42)

    def test_rejecting_corpus_requires_error_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "tests/fuzz-regressions"
            corpus.mkdir(parents=True)
            (corpus / "invalid.min").write_text('print("unterminated')
            with patch.object(fuzz, "ROOT", root), patch.object(fuzz, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                with self.assertRaises(AssertionError):
                    fuzz.check_regression_corpus(Path("compiler"), root)

    def test_rejecting_corpus_rejects_unexpected_positive_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "tests/fuzz-regressions"
            corpus.mkdir(parents=True)
            (corpus / "invalid.min").write_text('print("unterminated')
            with patch.object(fuzz, "ROOT", root), patch.object(fuzz, "run", return_value=subprocess.CompletedProcess([], 37, "", "")):
                with self.assertRaises(AssertionError):
                    fuzz.check_regression_corpus(Path("compiler"), root)

    def test_regression_corpus_cannot_be_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(fuzz, "ROOT", root):
                with self.assertRaises(AssertionError):
                    fuzz.check_regression_corpus(Path("compiler"), root)

    def test_sanitizer_failure_is_not_a_user_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "tests/fuzz-regressions"
            corpus.mkdir(parents=True)
            (corpus / "invalid.min").write_text("invalid")
            result = subprocess.CompletedProcess([], 1, "", "AddressSanitizer: heap-use-after-free")
            with patch.object(fuzz, "ROOT", root), patch.object(fuzz, "run", return_value=result):
                with self.assertRaises(AssertionError):
                    fuzz.check_regression_corpus(Path("compiler"), root)

    def test_every_seed_requires_an_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "tests/fuzz-corpus"
            (corpus / "inputs").mkdir(parents=True)
            (corpus / "inputs/unlisted.min").write_text("print(1)")
            (corpus / "seeds.json").write_text("{}")
            with patch.object(fuzz, "ROOT", root):
                with self.assertRaises(AssertionError):
                    fuzz.check_seed_corpus(Path("compiler"), "clang", root)

    def test_failure_retains_source_and_machine_readable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compiler = root / "compiler"
            runtime = root / "runtime.o"
            compiler.write_bytes(b"candidate")
            runtime.write_bytes(b"runtime")

            def fail(_compiler, _clang, _cases, temporary, _seed):
                (temporary / "repro.min").write_text("print(1)\n")
                raise AssertionError("deliberate oracle failure")

            with (patch.object(sys, "argv", ["fuzz.py", "--compiler", str(compiler), "--cases", "1", "--output-dir", str(root / "evidence")]),
                  patch.object(fuzz, "RUNTIME", runtime), patch.object(fuzz, "check_expression_batch", side_effect=fail),
                  contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO())):
                self.assertEqual(fuzz.main(), 1)
            report_path, = (root / "evidence").glob("campaign-*/results.json")
            report = json.loads(report_path.read_text())
            self.assertEqual(report["status"], "failed")
            self.assertIn("deliberate oracle failure", report["failure"])
            self.assertTrue(report_path.with_name("repro.min").exists())
            self.assertEqual(report["compiler"], str(compiler.resolve()))

    def test_invalid_utf8_output_is_reported_without_losing_evidence(self):
        result = fuzz.run([sys.executable, "-c", "import sys; sys.stderr.buffer.write(bytes([255]))"])
        self.assertEqual(result.stderr, "\\xff")
        self.assertEqual(fuzz.COMMANDS[-1]["stderr"], "\\xff")

    @unittest.skipIf(os.name == "nt", "POSIX process group assertion")
    def test_timeout_terminates_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "orphan-wrote-file"
            child = "import time; from pathlib import Path; time.sleep(.5); Path(" + repr(str(marker)) + ").write_text('orphan')"
            parent = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', " + repr(child) + "]); time.sleep(10)"
            with self.assertRaises(subprocess.TimeoutExpired):
                fuzz.run([sys.executable, "-c", parent], timeout=.1)
            time.sleep(.7)
            self.assertFalse(marker.exists())
            self.assertTrue(fuzz.COMMANDS[-1]["timed_out"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
