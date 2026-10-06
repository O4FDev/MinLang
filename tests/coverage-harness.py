#!/usr/bin/env python3
"""Verify coverage counts keep instrumented runtime headers in the denominator."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("minyar_coverage", Path(__file__).resolve().parents[1] / "scripts/coverage.py")
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class CoverageHarness(unittest.TestCase):
    def test_coverage_compiler_runtime_uses_selected_clang_and_arena_source(self):
        with mock.patch.object(coverage, "run") as run:
            coverage.build_compiler_runtime(Path("isolated-runtime.o"), clang="chosen clang", env={})
        command = run.call_args.args[0]
        self.assertEqual(command[0], "chosen clang")
        self.assertIn("-DMINYAR_COMPILER_ARENA=1", command)
        self.assertIn(str(coverage.ROOT / "runtime/minyar_runtime.c"), command)
        self.assertNotIn(str(coverage.ROOT / "build/minyar-compiler-runtime.ll"), command)

    def test_tool_versions_are_recorded_and_mismatches_fail_before_instrumentation(self):
        tools = {"clang": "chosen clang", "opt": "chosen opt",
                 "llvm_cov": "chosen cov", "profdata": "chosen profdata"}
        def version(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "LLVM version 22.1.5\n", "")
        with mock.patch.object(coverage, "run", side_effect=version):
            identities = coverage.toolchain_identity(tools, {})
        self.assertEqual(identities["clang"]["path"], "chosen clang")
        self.assertEqual(identities["opt"]["major"], 22)
        def mismatch(command, **kwargs):
            major = 17 if command[0] == "chosen cov" else 22
            return subprocess.CompletedProcess(command, 0, f"LLVM version {major}.0.0\n", "")
        with mock.patch.object(coverage, "run", side_effect=mismatch):
            with self.assertRaisesRegex(ValueError, "matching LLVM"):
                coverage.toolchain_identity(tools, {})

    def test_pre_inlining_instrumentation_uses_the_selected_backend_target(self):
        for triple in ("arm64-apple-darwin25.0.0", "x86_64-unknown-linux-gnu"):
            with self.subTest(triple=triple):
                commands = []
                def run(command, **kwargs):
                    commands.append(command)
                    return subprocess.CompletedProcess(command, 0, triple + "\n", "")
                with mock.patch.object(coverage, "run", side_effect=run):
                    coverage.instrument_compiler_ir(Path("source.ll"), Path("instrumented.ll"),
                        clang="selected clang", opt="selected opt", phase="before-inlining", env={})
                self.assertEqual(commands[0], ["selected clang", "-dumpmachine"])
                self.assertIn("--mtriple=" + triple, commands[1])
                self.assertIn("-passes=sancov-module", commands[1])

    def test_missing_or_invalid_target_metadata_cannot_choose_an_implicit_target(self):
        for triple in ("", "\n", "unknown", "arm64 apple darwin",
                       "arm64-apple-darwin\nx86_64-unknown-linux-gnu"):
            with self.subTest(triple=triple), mock.patch.object(coverage, "run", return_value=
                subprocess.CompletedProcess([], 0, triple, "")) as run:
                with self.assertRaisesRegex(ValueError, "target triple"):
                    coverage.instrument_compiler_ir(Path("source.ll"), Path("instrumented.ll"),
                        clang="selected clang", opt="selected opt", phase="before-inlining", env={})
                self.assertEqual(run.call_count, 1, "opt must not run without a valid target")

    def test_runtime_aggregation_includes_headers_and_excludes_tests(self):
        def file(name, line_count, line_covered, branch_count, branch_covered):
            return {"filename": name, "summary": {
                "lines": {"count": line_count, "covered": line_covered, "percent": 100},
                "branches": {"count": branch_count, "covered": branch_covered, "percent": 100}}}
        exported = {"data": [{"files": [
            file("/project/runtime/minyar_runtime.c", 10, 10, 2, 2),
            file("/project/runtime/minyar_numbers.h", 90, 0, 18, 0),
            file("/project/tests/runtime-unit.c", 200, 200, 50, 50),
            file("/project/runtime-neighbor/foreign.c", 200, 200, 50, 50)]}]}
        totals, files = coverage.aggregate_runtime_coverage(exported, Path("/project/runtime"))
        self.assertEqual(totals["lines"], {"count": 100, "covered": 10, "percent": 10.0})
        self.assertEqual(totals["branches"]["percent"], 10.0)
        self.assertEqual(len(files), 2)

    def test_empty_runtime_mapping_cannot_report_full_coverage(self):
        with self.assertRaises(ValueError):
            coverage.aggregate_runtime_coverage({"data": [{"files": []}]}, Path("/project/runtime"))

    def test_empty_denominator_cannot_report_full_coverage(self):
        with self.assertRaises(ValueError):
            coverage.percentage(0, 0)

    def test_edge_profiles_merge_branches_and_reject_inconsistent_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            first, second = directory / '1.edges', directory / '2.edges'
            first.write_bytes(struct.pack('=Q', 3) + b'\x01\x00\x00')
            second.write_bytes(struct.pack('=Q', 3) + b'\x00\x01\x00')
            self.assertEqual(coverage.compiler_edge_coverage(directory),
                             {'count': 3, 'covered': 2, 'percent': 66.67})
            for malformed in (b'broken', struct.pack('=Q', 0),
                              struct.pack('=Q', 4) + b'\x01\x01\x00\x00',
                              struct.pack('=Q', 3) + b'\x01'):
                with self.subTest(profile=malformed):
                    second.write_bytes(malformed)
                    with self.assertRaises(RuntimeError):
                        coverage.compiler_edge_coverage(directory)

    def test_invalid_threshold_cannot_disable_gate(self):
        for value in ("nan", "inf", "-inf", "-1", "101", "invalid", ""):
            with self.subTest(value=value), mock.patch.dict(coverage.os.environ, {"TEST_FLOOR": value}):
                with self.assertRaises(ValueError):
                    coverage.minimum_coverage("TEST_FLOOR")
        with mock.patch.dict(coverage.os.environ, {"TEST_FLOOR": "79.5"}):
            self.assertEqual(coverage.minimum_coverage("TEST_FLOOR"), 79.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
