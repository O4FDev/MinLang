#!/usr/bin/env python3
"""Selector-only tests; run on BX. No compiler, guest or CPU probe is executed."""

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("osdev_runtime_selector", ROOT / "tools/osdev-runtime.py")
selector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(selector)


class RuntimeSelection(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="osdev-runtime-test-")
        self.root = Path(self.temporary.name)
        (self.root / "runtime/freestanding").mkdir(parents=True)
        self.wrapper = (
            "/* actual wrapper before engine */\n"
            "#define MINYAR_FREESTANDING 1\n"
            "#define MINYAR_SYSTEM_HEAP 1\n"
            '#include "callback-domain.h"\n'
            '#include "../minyar_runtime.c"\n'
            '#include "../minyar_stack_frames.h"\n'
            "/* actual wrapper after engine */\n"
        )
        self.engine = (
            "/* actual common engine */\n"
            '#include "minyar_rc.h"\n'
            "/* code between ownership and collections */\n"
            '#include "minyar_collections.h"\n'
        )
        self.write_wrapper(self.wrapper)
        self.write_engine(self.engine)

    def tearDown(self):
        self.temporary.cleanup()

    def write_wrapper(self, source):
        (self.root / "runtime/freestanding/runtime.c").write_bytes(source.encode("utf-8"))

    def write_engine(self, source):
        (self.root / "runtime/minyar_runtime.c").write_bytes(source.encode("utf-8"))

    def assert_cycle(self, source):
        selected, output = selector.render(self.root, source)
        self.assertEqual(selected, "cycle")
        before, after = self.wrapper.split(selector.WRAPPER_INCLUDE)
        self.assertTrue(output.startswith(selector.INITIALIZE_PREFIX + before))
        self.assertTrue(output.endswith(after + selector.INITIALIZE_SUFFIX))
        self.assertNotIn(selector.WRAPPER_INCLUDE, output)
        self.assertNotIn('#include "minyar_rc.h"', output)
        self.assertNotIn('#include "minyar_collections.h"', output)
        self.assertEqual(output.count('#include "minyar_cycle_rc.h"'), 1)
        self.assertEqual(output.count('#include "minyar_cycle_collections.h"'), 1)
        self.assertEqual(output.count('#include "minyar_callbacks.h"'), 1)
        self.assertIn(selector.CYCLE_PREFIX, output)
        self.assertEqual(output.count("#define MINYAR_SORT_GRAPH 1\n"), 1)
        self.assertEqual(output.count("#define MINYAR_MAP_CYCLE_RUNTIME 1\n"), 1)
        self.assertIn("#define MINYAR_NOINLINE __attribute__((noinline))\n", output)
        self.assertIn('#include "callback-domain.h"', output)
        return output

    def test_ordinary_preserves_wrapper(self):
        selected, output = selector.render(self.root, "define i32 @main() { ret i32 0 }\n")
        self.assertEqual(selected, "ordinary")
        self.assertEqual(output, self.wrapper)

    def test_crlf_wrapper_preserved(self):
        self.wrapper = self.wrapper.replace("\n", "\r\n")
        self.write_wrapper(self.wrapper)
        self.assertEqual(selector.render(self.root, ""), ("ordinary", self.wrapper))
        self.assert_cycle("; minyar-cycle-runtime: 1\n")

    def test_selected_initialization_binds_domain_first(self):
        output = self.assert_cycle("; minyar-callback-runtime: 1\n")
        self.assertTrue(output.startswith(
            "#define minyar_initialize_arguments minyar_freestanding_initialize_arguments\n"))
        body = output[output.rindex("#undef minyar_initialize_arguments"):]
        self.assertIn("void minyar_initialize_arguments(int count, char **values)", body)
        self.assertLess(body.index("(void)minyar_callback_domain();"),
                        body.index("minyar_freestanding_initialize_arguments(count, values);"))
        ordinary = selector.render(self.root, "")[1]
        self.assertNotIn(selector.INITIALIZE_PREFIX, ordinary)
        self.assertNotIn(selector.INITIALIZE_SUFFIX, ordinary)

    def test_each_authoritative_marker_selects_cycle(self):
        for marker in (
            "; minyar-cycle-runtime: 1",
            "; minyar-callback-runtime: 1",
            "; minyar-native-library: runtime",
            "; minyar-native-library: callbackruntime",
        ):
            with self.subTest(marker=marker):
                self.assert_cycle(marker + "\n")

    def test_native_library_strip_and_crlf(self):
        self.assert_cycle("; minyar-native-library: runtime \t\r\n")
        self.assert_cycle("; minyar-callback-runtime: 1\r\n")

    def test_combined_markers_transform_only_once(self):
        self.assert_cycle("\n".join((
            "; minyar-cycle-runtime: 1", "; minyar-callback-runtime: 1",
            "; minyar-native-library: runtime", "; minyar-native-library: callbackruntime",
        )))

    def test_non_authoritative_mentions_do_not_select(self):
        program = (
            '@text = private constant [25 x i8] c"; minyar-cycle-runtime: 1"\n'
            "; not a marker: minyar-callback-runtime: 1\n"
            "; minyar-native-library: runtime_extra\n"
            "; minyar-native-library: io\n"
            "; minyar-parallel: unused.arch.helper\n"
            "; ordinary text\u2028; minyar-cycle-runtime: 1\n"
        )
        self.assertEqual(selector.render(self.root, program), ("ordinary", self.wrapper))

    def test_data_parallel_retains_supported_bare_profile(self):
        marker = "; minyar-data-parallel-runtime: 1\n"
        self.assertEqual(selector.render(self.root, marker), ("ordinary", self.wrapper))
        self.assert_cycle(marker + "; minyar-callback-runtime: 1\n")

    def test_managed_thread_profiles_reject(self):
        for prefix in ("", "; minyar-cycle-runtime: 1\n", "; minyar-data-parallel-runtime: 1\n"):
            with self.subTest(prefix=prefix):
                with self.assertRaisesRegex(ValueError, "managed thread.*unsupported.*freestanding"):
                    selector.render(self.root, prefix + "; minyar-thread-runtime: 1\n")

    def test_exactly_one_common_include_required(self):
        for before, _ in selector.ENGINE_INCLUDES:
            for count in (0, 2):
                with self.subTest(include=before, count=count):
                    self.write_engine(self.engine.replace(before, (before + "\n") * count))
                    with self.assertRaisesRegex(ValueError, "exactly one"):
                        selector.render(self.root, "; minyar-cycle-runtime: 1\n")

    def test_exactly_one_wrapper_include_required(self):
        for count in (0, 2):
            with self.subTest(count=count):
                self.write_wrapper(self.wrapper.replace(selector.WRAPPER_INCLUDE,
                                                        (selector.WRAPPER_INCLUDE + "\n") * count))
                for program in ("", "; minyar-callback-runtime: 1\n"):
                    with self.assertRaisesRegex(ValueError, "freestanding wrapper.*exactly one"):
                        selector.render(self.root, program)

    def test_kernel_and_loader_selection_are_independent(self):
        kernel = self.root / "kernel.ll"
        loader = self.root / "loader.ll"
        kernel.write_text("; minyar-callback-runtime: 1\n", encoding="utf-8")
        loader.write_text("define i32 @main() { ret i32 0 }\n", encoding="utf-8")
        kernel_output = self.root / "out/kernel-runtime.c"
        loader_output = self.root / "out/loader-runtime.c"
        self.assertEqual(selector.publish(kernel, self.root, kernel_output), "cycle")
        self.assertEqual(selector.publish(loader, self.root, loader_output), "ordinary")
        self.assertIn('#include "minyar_cycle_rc.h"', kernel_output.read_text())
        self.assertEqual(loader_output.read_text(), self.wrapper)

    def test_rejected_selection_keeps_previous_output(self):
        program = self.root / "program.ll"
        program.write_text("; minyar-thread-runtime: 1\n", encoding="utf-8")
        output = self.root / "runtime-output.c"
        output.write_text("retained previous output", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            status = selector.main(["--program", str(program), "--root", str(self.root),
                                    "--output", str(output)])
        self.assertEqual(status, 2)
        self.assertEqual(output.read_text(), "retained previous output")

    def test_cannot_overwrite_inputs(self):
        program = self.root / "program.ll"
        program.write_text("", encoding="utf-8")
        for output in (program, self.root / "runtime/minyar_runtime.c",
                       self.root / "runtime/freestanding/runtime.c"):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ValueError, "must not overwrite"):
                    selector.publish(program, self.root, output)

    def test_actual_wrapper_and_shared_transform_preserved(self):
        actual = (ROOT / "runtime/freestanding/runtime.c").read_bytes().decode("utf-8")
        common = (ROOT / "runtime/minyar_runtime.c").read_bytes().decode("utf-8")
        self.assertEqual(selector.render(ROOT, ""), ("ordinary", actual))
        before, after = actual.split(selector.WRAPPER_INCLUDE)
        selected, output = selector.render(ROOT, "; minyar-cycle-runtime: 1\n")
        self.assertEqual(selected, "cycle")
        self.assertEqual(output, selector.INITIALIZE_PREFIX + before +
                         selector.cycle_engine(common) + after + selector.INITIALIZE_SUFFIX)
        # This is text-only: callback-domain.h and actual per-CPU instructions
        # remain part of the wrapper; the test never compiles or invokes them.


if __name__ == "__main__":
    unittest.main()
