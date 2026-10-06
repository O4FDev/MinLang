#!/usr/bin/env python3
"""Reproduce bounded pinned peer source retrieval without inventing review status.

All semantic dispositions in the manifest are authored by a reviewer. Fetching,
checking a hash and rendering a table never promotes a file to reviewed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "research/2026-10-memory/peers.json"
CACHE = ROOT / "build/peer-research/sources"
MAX_BYTES = 1_000_000


def validate_entry(peer: dict, entry: dict) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", peer.get("language", "")):
        raise ValueError("invalid peer language cache namespace")
    if not re.fullmatch(r"[0-9a-f]{40}", peer.get("commit", "")):
        raise ValueError("peer commit must be a full immutable SHA")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", peer.get("repository", "")):
        raise ValueError("invalid repository name")
    path = entry.get("path", "")
    if (not isinstance(path, str) or not path or ":" in path or "\\" in path
            or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):
        raise ValueError("invalid source path")
    if not re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")):
        raise ValueError("source SHA256 is required")
    size = entry.get("bytes")
    if type(size) is not int or not 0 <= size <= MAX_BYTES:
        raise ValueError("source size exceeds bounded retrieval")
    if entry.get("status") == "source_read_and_semantically_reviewed":
        units = entry.get("review_units")
        if not isinstance(units, list) or not units:
            raise ValueError("reviewed source requires individual review units")
        for unit in units:
            if (not unit.get("id") or unit.get("status") != "semantically_reviewed"
                    or not unit.get("disposition") or not unit.get("reason")):
                raise ValueError("incomplete individual semantic review")


def verify_or_fetch(peer: dict, entry: dict, fetch: bool) -> None:
    validate_entry(peer, entry)
    destination = CACHE / peer["language"] / entry["path"]
    if fetch:
        url = (f"https://raw.githubusercontent.com/{peer['repository']}/"
               f"{peer['commit']}/{entry['path']}")
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("download exceeds retrieval bound")
    else:
        data = destination.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("source hash mismatch: " + str(destination))
    if entry.get("check_size", True) and len(data) != entry["bytes"]:
        raise ValueError("source size mismatch: " + str(destination))
    if fetch:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def render(report: dict, manifest_path: Path = MANIFEST) -> str:
    count = sum(len(peer["files"]) for peer in report["peers"])
    scope = report.get("scope", "This is a bounded pinned inventory, not a repository-wide review.")
    argument = ""
    if manifest_path != MANIFEST:
        label = manifest_path.relative_to(ROOT) if manifest_path.is_relative_to(ROOT) else manifest_path
        argument = " --manifest " + shlex.quote(str(label))
    lines = ["# Pinned peer-test semantic review", "",
             f"Pinned source entries: **{count}**. Peers: **{len(report['peers'])}**.", "",
             scope, "", "`peers-inventory.json` retains additional",
             "directory-discovered pending paths, including explicitly capped LLVM/Lean",
             "listings. Source retrieval, reading, semantic disposition and validation",
             "are recorded separately. Upstream sources and licenses are cached only in",
             "`build/peer-research/sources`; new Minyar tests are original adaptations.", "",
             "Reproduce retrieval with `python3 scripts/peer-research-sources.py" + argument + " --fetch`.",
             "Verify caches and regenerate this table with `python3 scripts/peer-research-sources.py" + argument + "`.",
             "Run adaptations with `python3 tests/peer-research-semantics.py` (O0 and O2).", ""]
    for peer in report["peers"]:
        lines += [f"## {peer['language'].title()}: {peer['tag']}", "",
                  f"Pinned commit `{peer['commit']}`. [License]({peer['license_url']}): "
                  + peer["license_identification"] + ".", ""]
        for file in peer["files"]:
            lines += [f"### [{file['path']}]({file['url']})", "",
                      f"SHA256 `{file['sha256']}`; {file['lines']} lines. Status: "
                      + file["status"] + ".", ""]
            if not file.get("review_units"):
                lines += ["Pending individual source reading and semantic review.", ""]
                continue
            lines += ["| Individual upstream unit | Disposition | Semantic mapping and evidence |",
                      "| --- | --- | --- |"]
            for unit in file["review_units"]:
                detail = unit["reason"]
                if unit.get("minyar_test"):
                    detail += " Test: `" + unit["minyar_test"].split(".")[-1] + "`; " + unit["validation"] + "."
                label = unit["id"]
                if unit.get("source_line"):
                    label = f"[{label}]({file['url']}#L{unit['source_line']})"
                row = [label, unit["disposition"], detail]
                lines.append("| " + " | ".join(value.replace("|", "\\|").replace("\n", " ")
                                             for value in row) + " |")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    report = json.loads(manifest.read_text())
    count = 0
    for peer in report["peers"]:
        for entry in peer["files"]:
            verify_or_fetch(peer, entry, args.fetch)
            count += 1
        license_entry = {"path": peer["license_path"], "sha256": peer["license_sha256"],
                         "bytes": 0, "check_size": False}
        verify_or_fetch(peer, license_entry, args.fetch)
    manifest.with_suffix(".md").write_text(render(report, manifest))
    print(f"Verified {count} pinned source files and {len(report['peers'])} licenses; no review statuses changed")


if __name__ == "__main__":
    main()
