#!/usr/bin/env python3
"""Provenance and incomplete-review fault injection for peer inventory tooling."""

import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "peer_sources", ROOT / "scripts/peer-research-sources.py"
)
SOURCES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCES)


class PeerSourcesHarness(unittest.TestCase):
    def setUp(self):
        self.peer = {"language": "example", "repository": "owner/repository",
                     "commit": "a" * 40}
        self.file = {"path": "tests/test.src", "sha256": "b" * 64,
                     "bytes": 10, "status": "retrieved_not_reviewed"}

    def test_moving_reference_cannot_be_called_pinned(self):
        for value in ("main", "v1.0", "abc", "a" * 39):
            with self.subTest(commit=value):
                self.peer["commit"] = value
                with self.assertRaisesRegex(ValueError, "commit"):
                    SOURCES.validate_entry(self.peer, self.file)

    def test_cache_paths_cannot_escape_the_peer_directory(self):
        for value in ("../test.src", "/test.src", "tests/../../test.src", "",
                      "C:/test.src", "tests\\..\\..\\test.src"):
            with self.subTest(path=value):
                self.file["path"] = value
                with self.assertRaisesRegex(ValueError, "path"):
                    SOURCES.validate_entry(self.peer, self.file)

    def test_peer_namespace_cannot_escape_the_cache(self):
        for value in ("../peer", "/peer", "C:/peer", "peer\\child"):
            with self.subTest(language=value):
                self.peer["language"] = value
                with self.assertRaisesRegex(ValueError, "language"):
                    SOURCES.validate_entry(self.peer, self.file)

    def test_unread_file_cannot_be_reported_as_reviewed(self):
        self.file["status"] = "source_read_and_semantically_reviewed"
        for units in (None, [], [{"id": "test", "disposition": "compatible_adaptation"}]):
            with self.subTest(units=units):
                self.file["review_units"] = units
                with self.assertRaisesRegex(ValueError, "review"):
                    SOURCES.validate_entry(self.peer, self.file)

    def test_retrieval_bounds_and_checksums_are_required(self):
        for key, value in (("bytes", 1000001), ("bytes", -1), ("sha256", "bad")):
            with self.subTest(key=key, value=value):
                changed = copy.deepcopy(self.file)
                changed[key] = value
                with self.assertRaises(ValueError):
                    SOURCES.validate_entry(self.peer, changed)

    def test_valid_pending_entry_stays_pending(self):
        SOURCES.validate_entry(self.peer, self.file)
        self.assertEqual(self.file["status"], "retrieved_not_reviewed")

    def test_render_retains_the_actual_inventory_scope(self):
        peer = {**self.peer, "tag": "v1", "license_url": "https://example.com/license",
                "license_identification": "example license",
                "files": [{**self.file, "url": "https://example.com/source", "lines": 1}]}
        scope = "Complete immediate example directory; no repository-wide review claim."
        rendered = SOURCES.render({"peers": [peer], "scope": scope})
        self.assertIn(scope, rendered)
        self.assertNotIn("32 files", rendered)
        self.assertNotIn("four per peer", rendered)
        self.assertEqual(peer["files"][0]["status"], "retrieved_not_reviewed")


if __name__ == "__main__":
    unittest.main()
