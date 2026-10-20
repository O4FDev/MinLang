#!/usr/bin/env python3
"""Assemble an offline static site from checked-in UI and pinned tools."""
import json
import importlib.util
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
    # The browser only compiles LLVM IR and links a prebuilt runtime. Preserve
    # the full source package/sysroot for native C builds, and derive a small
    # browser-only archive with pinned, byte-identical link resources.
    specification = importlib.util.spec_from_file_location("minyar_wasm_resources", ROOT / "tools/trim-wasm-resources.py")
    resources = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(resources)
    resources.trim_resources(BUILD / "wasm/clang/package/gen/llvm-resources.tar",
                             SITE / "vendor/clang/gen/llvm-resources.tar",
                             SITE / "resources-transform.json")
    backend_paths = sorted((SITE / "vendor/clang/gen").glob("llvm.core*.wasm"))
    backend_paths.append(SITE / "vendor/clang/gen/llvm-resources.tar")
    backend_files = {str(path.relative_to(SITE)): path.stat().st_size for path in backend_paths}
    (SITE / "backend.json").write_text(json.dumps({
        "schemaVersion": 1, "totalBytes": sum(backend_files.values()), "files": backend_files,
    }, indent=2) + "\n")
    for name in ("compiler.wasm", "runtime.o", "dependencies.json"):
        shutil.copy2(BUILD / "wasm" / name, SITE / name)
    shutil.copy2(BUILD / "wasm/language-examples.json", SITE / "language-examples.json")
    shutil.copy2(ROOT / "tools/wasm-target.mjs", SITE / "target.mjs")
    library = {f"{name}.min": (ROOT / "library" / f"{name}.min").read_text() for name in PORTABLE_MODULES}
    (SITE / "library.json").write_text(json.dumps(library, ensure_ascii=False) + "\n")
    files = {str(path.relative_to(SITE)): path.stat().st_size for path in SITE.rglob("*") if path.is_file() and path.name != "build.json"}
    (SITE / "build.json").write_text(json.dumps({"bytes": sum(files.values()), "files": files}, indent=2) + "\n")
    (SITE / ".built").touch()
    # Temporary paths start private. The finished artifact must be readable
    # by a static server running as a different user, regardless of umask.
    for path in SITE.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    SITE.chmod(0o755)
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
