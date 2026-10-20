#!/usr/bin/env python3
"""Target selection, SDK isolation, provider rejection and output safety."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("minyar_mobile", ROOT / "tools/mobile.py")
mobile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mobile)
ENTRY = "define i32 @main(i32 %argc, ptr %argv) uwtable {\n  ret i32 0\n}\n"


class MobileTools(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="minyar-mobile-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "hello.min"
        self.source.write_text("print(42)\n")

    def args(self, *extra):
        return mobile.parser().parse_args([str(self.source), "--target", "ios-simulator", *extra])

    def test_validated_target_defaults(self):
        args = self.args()
        mobile.validate(args)
        self.assertEqual(args.output, ROOT / "build/mobile/ios-simulator/Minyar.app")

    def test_reject_bad_metadata_and_target_options(self):
        for options in (("--identifier", "bad\nname"), ("--name", "bad\tname"),
                        ("--minimum-ios", "15.0"), ("--minimum-ios", "16.0 -bad"),
                        ("--api", "27"), ("-o", str(self.directory / "bad.zip")),
                        ("--library", str(self.directory / "absent"))):
            with self.subTest(options=options), self.assertRaises(mobile.MobileError):
                mobile.validate(self.args(*options))

    def test_reject_output_containing_source(self):
        output = self.directory / "Source.app"
        output.mkdir()
        source = output / "main.min"
        source.write_text("print(42)\n")
        args = self.args("-o", str(output))
        args.source = source
        with self.assertRaisesRegex(mobile.MobileError, "contain or replace"):
            mobile.validate(args)
        self.assertTrue(source.exists())

    def test_reject_foreign_app_and_symlink(self):
        foreign = self.directory / "Other.app"
        foreign.mkdir()
        with self.assertRaisesRegex(mobile.MobileError, "not built by this tool"):
            mobile.validate(self.args("-o", str(foreign)))
        link = self.directory / "Link.app"
        link.symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(mobile.MobileError, "symbolic-link"):
            mobile.validate(self.args("-o", str(link)))

    def test_provider_selection_fails_closed(self):
        ios = ENTRY + "; minyar-native-library: mobileios\n"
        self.assertEqual(mobile.inspect_ir(ios, "ios-simulator"), {"mobileios"})
        self.assertEqual(mobile.inspect_ir(ENTRY, "android-arm64"), set())
        for target, text in (("ios-simulator", ENTRY), ("android-arm64", ios),
                             ("android-arm64", ENTRY + "; minyar-native-library: macos\n"),
                             ("android-arm64", ENTRY + "; minyar-thread-runtime: 1\n"),
                             ("android-arm64", ENTRY + "; minyar-machine: syscall\n"),
                             ("android-arm64", ENTRY + "; minyar-c-layout: 1|8|8\n"),
                             ("android-arm64", ENTRY * 2)):
            with self.subTest(target=target, text=text), self.assertRaises(mobile.MobileError):
                mobile.inspect_ir(text, target)

    def test_feature_markers_inside_text_are_ordinary_text(self):
        for marker in ("; minyar-thread-runtime: 1", "; minyar-machine: syscall",
                       "; minyar-c-layout: 1|8|8", "; minyar-c-value: example"):
            literal = f'@message = private constant [{len(marker) + 1} x i8] c"{marker}\\00"\n'
            self.assertEqual(mobile.inspect_ir(ENTRY + literal, "android-arm64"), set())

    def test_archive_metadata_cannot_truncate_source_or_unrelated_file(self):
        output = self.directory / "library.a"
        sidecar = output.with_suffix(".a.json")
        sidecar.symlink_to(self.source)
        args = self.args("--target", "android-arm64", "-o", str(output))
        with self.assertRaisesRegex(mobile.MobileError, "metadata must not link"):
            mobile.validate(args)
        self.assertEqual(self.source.read_text(), "print(42)\n")
        sidecar.unlink()
        sidecar.write_text("unrelated file")
        with self.assertRaisesRegex(mobile.MobileError, "unrelated archive metadata"):
            mobile.validate(args)

    def test_archive_output_cannot_replace_a_directory(self):
        output = self.directory / "important.a"
        output.mkdir()
        (output / "data").write_text("preserve me")
        args = self.args("--target", "android-arm64", "-o", str(output))
        with self.assertRaisesRegex(mobile.MobileError, "regular file"):
            mobile.validate(args)
        self.assertEqual((output / "data").read_text(), "preserve me")

    def test_apple_sdk_and_triple_are_explicit(self):
        commands = []
        def run(command, **_):
            commands.append(command)
            if "--show-sdk-path" in command:
                return str(self.directory)
            if "--find" in command:
                return "/xcode/ld"
            return "/pinned/clang"
        with patch.object(mobile.platform, "system", return_value="Darwin"), patch.object(mobile, "run", side_effect=run):
            args = self.args("--arch", "arm64")
            tools = mobile.apple_tools(args)
        self.assertEqual(tools["triple"], "arm64-apple-ios16.0-simulator")
        self.assertEqual(tools["flags"], ["-target", tools["triple"], "-isysroot", str(self.directory)])
        self.assertIn("iphonesimulator", commands[0])
        self.assertEqual(tools["linker"], "/xcode/ld")

    def test_missing_android_ndk_is_actionable(self):
        args = self.args()
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(mobile.MobileError, "ANDROID_NDK_HOME"):
            mobile.android_tools(args)

    def test_android_toolchain_is_separate_from_host_clang(self):
        binary = self.directory / "toolchains/llvm/prebuilt/linux-x86_64/bin"
        binary.mkdir(parents=True)
        for name in ("aarch64-linux-android28-clang", "llvm-ar"):
            tool = binary / name
            tool.touch(mode=0o755)
        args = self.args()
        args.target = "android-arm64"
        args.ndk = self.directory
        with patch.object(mobile.platform, "system", return_value="Linux"):
            tools = mobile.android_tools(args)
        self.assertEqual(tools["clang"], str(binary / "aarch64-linux-android28-clang"))
        self.assertEqual(tools["flags"], ["-fPIC"])

    def test_publication_replaces_only_after_successful_build(self):
        output = self.directory / "App.app"
        output.mkdir()
        (output / "old").write_text("old")
        staging = self.directory / "staging"
        staging.mkdir()
        staged = staging / "new.app"
        staged.mkdir()
        (staged / "new").write_text("new")
        mobile.publish_app(staged, output)
        self.assertEqual((output / "new").read_text(), "new")
        self.assertFalse((staging / "previous.app").exists())

    def test_archive_and_metadata_roll_back_together(self):
        output, sidecar = self.directory / "old.a", self.directory / "old.a.json"
        archive, metadata = self.directory / "new.a", self.directory / "new.a.json"
        for path, value in ((output, "old archive"), (sidecar, "old metadata"),
                            (archive, "new archive"), (metadata, "new metadata")):
            path.write_text(value)
        rename = Path.rename
        def fail_metadata(path, destination):
            if path == metadata:
                raise OSError("injected metadata publication failure")
            return rename(path, destination)
        with patch.object(Path, "rename", fail_metadata), self.assertRaises(OSError):
            mobile.publish_archive(archive, metadata, output, sidecar)
        self.assertEqual(output.read_text(), "old archive")
        self.assertEqual(sidecar.read_text(), "old metadata")


if __name__ == "__main__":
    unittest.main()
