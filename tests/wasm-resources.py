#!/usr/bin/env python3
"""Check pinned browser resource derivation without compiling anything."""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = ROOT / "tools" / "trim-wasm-resources.py"
SPEC = importlib.util.spec_from_file_location("trim_wasm_resources", TOOL_PATH)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

# Independent compatibility contract: do not derive expected names from the tool.
EXPECTED_FILES = {
    "lib/wasm32-wasip1/crt1-command.o": b"command\0crt\xff",
    "lib/wasm32-wasip1/crt1-reactor.o": b"reactor\0crt",
    "lib/wasm32-wasip1/crt1.o": b"command\0crt\xff",
    "lib/wasm32-wasip1/libc.a": b"!<arch>\nlibc\0\xff",
    "lib/wasm32-wasip1/libm.a": b"!<arch>\n",
    "lib/wasm32-wasip1/libsetjmp.a": b"!<arch>\nsetjmp",
    "lib/wasm32-unknown-wasip1/libclang_rt.builtins.a": b"!<arch>\nbuiltins",
}
RESOURCE_SOURCE = None


def entry(name, data=b"", kind=tarfile.REGTYPE, *, linkname=""):
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = linkname
    info.size = len(data) if kind == tarfile.REGTYPE else 0
    return info, data


def write_archive(path, entries, *, stamp=123, reverse=False):
    with tarfile.open(path, "w:", format=tarfile.USTAR_FORMAT) as archive:
        for original, data in reversed(entries) if reverse else entries:
            info = copy.copy(original)
            info.uid, info.gid = stamp, stamp + 1
            info.mtime = stamp
            info.mode = 0o777
            info.uname, info.gname = "original-owner", "original-group"
            archive.addfile(info, io.BytesIO(data) if info.isfile() else None)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "source.tar"
        self.destination = self.directory / "browser.tar"
        self.manifest = self.directory / "browser.json"

    def valid_entries(self):
        return [entry(name, data) for name, data in EXPECTED_FILES.items()]

    def trim_fixture(self):
        return TOOL.trim_resources(
            self.source, self.destination, self.manifest,
            expected_source_sha256=file_hash(self.source))

    def rejected(self, entries, expected):
        write_archive(self.source, entries)
        before = self.source.read_bytes()
        self.destination.write_bytes(b"previous archive")
        self.manifest.write_bytes(b"previous manifest")
        with self.assertRaisesRegex((ValueError, tarfile.TarError), expected):
            self.trim_fixture()
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.destination.read_bytes(), b"previous archive")
        self.assertEqual(self.manifest.read_bytes(), b"previous manifest")

    def test_required_files_bytes_hashes_and_normalization(self):
        entries = self.valid_entries() + [entry("include/unused.h", b"excluded")]
        write_archive(self.source, entries)
        before = self.source.read_bytes()
        document = self.trim_fixture()
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.manifest.stat().st_mode & 0o777, 0o644)
        self.assertEqual(document, json.loads(self.manifest.read_bytes()))
        self.assertEqual(document["schema"], "minyar.wasm-resources/1")
        self.assertEqual(document["upstream"]["resource_sha256"], TOOL.RESOURCE_SHA256)
        self.assertEqual(document["source"]["sha256"], file_hash(self.source))
        self.assertEqual(document["source"]["size_bytes"], len(before))
        self.assertFalse(document["source"]["matches_published_pin"])
        self.assertEqual(document["output"]["sha256"], file_hash(self.destination))
        self.assertEqual(document["output"]["size_bytes"], self.destination.stat().st_size)
        expected = {name: hashlib.sha256(data).hexdigest()
                    for name, data in EXPECTED_FILES.items()}
        self.assertEqual({item["name"]: item["sha256"]
                          for item in document["output"]["files"]}, expected)
        raw_archive = self.destination.read_bytes()
        with tarfile.open(self.destination, "r:") as archive:
            actual = {}
            seen = set()
            for member in archive:
                self.assertEqual((member.uid, member.gid, member.mtime), (0, 0, 0))
                self.assertEqual((member.uname, member.gname), ("", ""))
                self.assertEqual(member.pax_headers, {})
                parent = str(Path(member.name).parent)
                if parent != ".":
                    self.assertIn(parent, seen)
                seen.add(member.name)
                if member.isfile():
                    self.assertEqual(member.mode, 0o644)
                    actual[member.name] = archive.extractfile(member).read()
                else:
                    self.assertTrue(member.isdir())
                    self.assertEqual(member.mode, 0o755)
                    # The browser's existing unpacker consumes the raw name,
                    # while Python strips a directory's slash during parsing.
                    raw_name = raw_archive[member.offset:member.offset + 100].split(b"\0", 1)[0]
                    self.assertEqual(raw_name.decode(), member.name)
                    self.assertFalse(raw_name.endswith(b"/"))
            self.assertEqual(actual, EXPECTED_FILES)
            self.assertEqual(seen - actual.keys(), {
                "lib", "lib/wasm32-wasip1", "lib/wasm32-unknown-wasip1"})

    def test_repeat_is_identical_and_has_no_output_paths(self):
        write_archive(self.source, self.valid_entries())
        self.trim_fixture()
        first = self.destination.read_bytes(), self.manifest.read_bytes()
        other_archive, other_manifest = self.directory / "other.tar", self.directory / "other.json"
        TOOL.trim_resources(self.source, other_archive, other_manifest,
                            expected_source_sha256=file_hash(self.source))
        self.assertEqual(first, (other_archive.read_bytes(), other_manifest.read_bytes()))
        self.assertNotIn(str(self.directory).encode(), first[1])

    def test_input_order_and_metadata_do_not_change_output(self):
        write_archive(self.source, self.valid_entries())
        self.trim_fixture()
        first = self.destination.read_bytes()
        write_archive(self.source, self.valid_entries(), stamp=999, reverse=True)
        self.trim_fixture()
        self.assertEqual(first, self.destination.read_bytes())

    def test_unneeded_contents_are_not_extracted(self):
        write_archive(self.source, self.valid_entries() + [
            entry("include/unused.h", b"header"), entry("lib/unused.a", b"archive")])
        extracted = []
        original = tarfile.TarFile.extractfile

        def track(archive, member, *args, **kwargs):
            extracted.append(member.name)
            return original(archive, member, *args, **kwargs)

        with mock.patch.object(tarfile.TarFile, "extractfile", track):
            self.trim_fixture()
        self.assertEqual(set(extracted), set(EXPECTED_FILES))
        self.assertEqual(len(extracted), len(EXPECTED_FILES))

    def test_each_required_file_is_required(self):
        for missing in EXPECTED_FILES:
            with self.subTest(missing=missing):
                entries = [item for item in self.valid_entries() if item[0].name != missing]
                self.rejected(entries, "missing required resources")

    def test_duplicate_required_unknown_and_directory_entries_fail(self):
        for extra in [entry(next(iter(EXPECTED_FILES)), b"duplicate"),
                      entry("unused", b"first"), entry("directory", kind=tarfile.DIRTYPE)]:
            with self.subTest(name=extra[0].name):
                additions = [extra] if extra[0].name in EXPECTED_FILES else [extra, extra]
                self.rejected(self.valid_entries() + additions, "duplicate archive entry")

    def test_unsafe_paths_fail_even_when_not_retained(self):
        for name in ("../escape", "/absolute", "a/../escape", "a/./file",
                     "a//file", "C:/windows", "back\\slash"):
            with self.subTest(name=name):
                self.rejected(self.valid_entries() + [entry(name)], "unsafe archive path")

    def test_links_and_special_files_fail_even_when_not_retained(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE,
                     tarfile.BLKTYPE, tarfile.FIFOTYPE):
            with self.subTest(kind=kind):
                self.rejected(self.valid_entries() + [entry("unused", kind=kind, linkname="lib")],
                              "unsupported archive entry")

    def test_required_directory_and_file_parent_collisions_fail(self):
        name = next(iter(EXPECTED_FILES))
        entries = [item for item in self.valid_entries() if item[0].name != name]
        self.rejected(entries + [entry(name, kind=tarfile.DIRTYPE)],
                      "required resource is not a regular file")
        self.rejected(self.valid_entries() + [entry("lib", b"not a directory")],
                      "archive parent is not a directory")

    def test_default_pin_rejects_untrusted_archive_without_outputs(self):
        write_archive(self.source, self.valid_entries())
        with self.assertRaisesRegex(ValueError, "SHA-256 integrity"):
            TOOL.trim_resources(self.source, self.destination, self.manifest)
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.manifest.exists())

    def test_output_aliases_cannot_clobber_source(self):
        write_archive(self.source, self.valid_entries())
        before = self.source.read_bytes()
        symlink, hardlink = self.directory / "symlink", self.directory / "hardlink"
        symlink.symlink_to(self.source)
        hardlink.hardlink_to(self.source)
        for output, manifest in [(self.source, self.manifest), (symlink, self.manifest),
                                 (hardlink, self.manifest), (self.destination, self.source),
                                 (self.destination, self.destination)]:
            with self.subTest(output=output, manifest=manifest):
                with self.assertRaisesRegex(ValueError, "separate files|hard links"):
                    TOOL.trim_resources(self.source, output, manifest,
                                        expected_source_sha256=file_hash(self.source))
                self.assertEqual(self.source.read_bytes(), before)

    def test_truncated_payload_and_member_limit_fail(self):
        self.source.write_bytes(self._truncated_payload())
        with self.assertRaisesRegex((ValueError, tarfile.TarError), "truncated|unexpected end"):
            self.trim_fixture()
        write_archive(self.source, self.valid_entries())
        with mock.patch.object(TOOL, "MAX_MEMBERS", 2):
            with self.assertRaisesRegex(ValueError, "too many entries"):
                self.trim_fixture()

    def _truncated_payload(self):
        info = tarfile.TarInfo("unneeded")
        info.size = 1024
        return info.tobuf(format=tarfile.USTAR_FORMAT)

    def test_actual_pinned_archive_and_cli(self):
        if RESOURCE_SOURCE is None:
            self.skipTest("pass --source for real pinned archive proof")
        original_hash = file_hash(RESOURCE_SOURCE)
        result = subprocess.run([sys.executable, str(TOOL_PATH), str(RESOURCE_SOURCE),
                                 str(self.destination), str(self.manifest)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(file_hash(RESOURCE_SOURCE), original_hash)
        document = json.loads(self.manifest.read_bytes())
        self.assertTrue(document["source"]["matches_published_pin"])
        self.assertEqual(document["source"]["sha256"], TOOL.RESOURCE_SHA256)
        with tarfile.open(RESOURCE_SOURCE, "r:") as original, \
                tarfile.open(self.destination, "r:") as trimmed:
            actual = {item.name for item in trimmed if item.isfile()}
            self.assertEqual(actual, set(EXPECTED_FILES))
            for name in actual:
                self.assertEqual(original.extractfile(name).read(), trimmed.extractfile(name).read())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", type=Path)
    options, remaining = parser.parse_known_args()
    RESOURCE_SOURCE = options.source
    unittest.main(argv=[sys.argv[0], *remaining])
