#!/usr/bin/env python3
"""Assemble an offline static site from checked-in UI and pinned tools."""
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
OUTPUT = BUILD / "playground"
PORTABLE_MODULES = ("maybe", "errors", "text", "math", "io", "process", "random", "json")


def main():
    # Assemble from an empty tree so removed source/vendor assets cannot ship.
    SITE = Path(tempfile.mkdtemp(prefix=".playground-", dir=BUILD))
    for source in (ROOT / "playground").iterdir():
        if source.is_file() and not source.name.startswith("test-package"):
            shutil.copy2(source, SITE / source.name)
        elif source.name == "licenses":
            shutil.copytree(source, SITE / source.name, dirs_exist_ok=True)
    for name in ("clang", "wasi"):
        shutil.copytree(BUILD / "wasm" / name / "package", SITE / "vendor" / name, dirs_exist_ok=True)
    for name in ("compiler.wasm", "runtime.o", "dependencies.json"):
        shutil.copy2(BUILD / "wasm" / name, SITE / name)
    shutil.copy2(ROOT / "tools/wasm-target.mjs", SITE / "target.mjs")
    library = {f"{name}.min": (ROOT / "library" / f"{name}.min").read_text() for name in PORTABLE_MODULES}
    (SITE / "library.json").write_text(json.dumps(library, ensure_ascii=False) + "\n")
    files = {str(path.relative_to(SITE)): path.stat().st_size for path in SITE.rglob("*") if path.is_file() and path.name != "build.json"}
    (SITE / "build.json").write_text(json.dumps({"bytes": sum(files.values()), "files": files}, indent=2) + "\n")
    (SITE / ".built").touch()
    previous = BUILD / ".playground-previous"
    if previous.exists():
        shutil.rmtree(previous)
    if OUTPUT.exists():
        OUTPUT.rename(previous)
    SITE.rename(OUTPUT)
    if previous.exists():
        shutil.rmtree(previous)
    print(f"Built {OUTPUT}: {len(files)} files, {sum(files.values()):,} bytes")


if __name__ == "__main__":
    main()
