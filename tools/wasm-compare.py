#!/usr/bin/env python3
"""Reproduce a bounded WASIp1 hello-world comparison; no global installs.

Run on a build box, after make playground. --prepare-toolchains downloads only
official SHA256-pinned Linux x86_64 archives. All raw evidence stays in --output.
"""
import argparse
import datetime
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "benchmarks/wasm"
LANGUAGES = ("minyar", "go", "rust", "zig")
EXTENSIONS = dict(zip(LANGUAGES, ("min", "go", "rs", "zig")))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run(argv, *, env=None, timeout=180):
    start = time.perf_counter_ns()
    completed = subprocess.run([str(item) for item in argv], cwd=ROOT,
                               env=env, capture_output=True, timeout=timeout)
    duration = time.perf_counter_ns() - start
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {argv!r}\n"
                           + completed.stderr.decode(errors="replace")
                           + completed.stdout.decode(errors="replace"))
    return completed.stdout, duration


def toolchains(directory, prepare):
    pins = json.loads((SOURCES / "toolchains.json").read_text())
    if prepare:
        directory.mkdir(parents=True, exist_ok=True)
        for pin in pins["archives"]:
            archive = directory / pin["url"].rsplit("/", 1)[1]
            if not archive.exists():
                print(f"Downloading {pin['name']} {pin['version']}", file=sys.stderr, flush=True)
                temporary = archive.with_suffix(".download")
                with urllib.request.urlopen(pin["url"], timeout=120) as source, temporary.open("wb") as out:
                    shutil.copyfileobj(source, out)
                temporary.replace(archive)
            if sha256(archive.read_bytes()) != pin["sha256"]:
                raise RuntimeError(f"official archive failed SHA256: {archive}")
            unpacked = directory / f"unpacked-{pin['name']}-{pin['version']}"
            marker = unpacked / ".complete"
            if not marker.exists():
                shutil.rmtree(unpacked, ignore_errors=True)
                unpacked.mkdir()
                with tarfile.open(archive) as bundle:
                    bundle.extractall(unpacked, filter="data")
                marker.touch()
            if pin["name"] in ("rustc", "rust-std"):
                package = next(item for item in unpacked.iterdir() if item.is_dir())
                component = package / ("rustc" if pin["name"] == "rustc" else "rust-std-wasm32-wasip1")
                shutil.copytree(component, directory / "rust", dirs_exist_ok=True)
    tools = {
        "go": directory / "unpacked-go-1.27.2/go/bin/go",
        "rust": directory / "rust/bin/rustc",
        "zig": directory / "unpacked-zig-0.17.0/zig-x86_64-linux-0.17.0/zig",
    }
    for name, executable in tools.items():
        if not executable.is_file():
            raise RuntimeError(f"missing {name}; run with --prepare-toolchains: {executable}")
    return tools, pins


def leb(data, position):
    value = shift = 0
    while True:
        byte = data[position]
        position += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, position
        shift += 7
        if shift > 63:
            raise ValueError("invalid Wasm integer")


def sections(data):
    if data[:8] != b"\0asm\1\0\0\0":
        raise ValueError("not a WebAssembly 1 module")
    position = 8
    while position < len(data):
        start = position
        kind = data[position]
        size, body = leb(data, position + 1)
        position = body + size
        if position > len(data):
            raise ValueError("truncated Wasm section")
        yield kind, data[start:position], data[body:position]


def strip_custom_metadata(data):
    """Uniformly strip custom metadata, preserving every standard section byte."""
    return data[:8] + b"".join(encoded for kind, encoded, _ in sections(data) if kind)


def memory_limits(data):
    memories = []
    for kind, _, body in sections(data):
        if kind != 5:
            continue
        count, position = leb(body, 0)
        for _ in range(count):
            flags, position = leb(body, position)
            initial, position = leb(body, position)
            maximum = None
            if flags & 1:
                maximum, position = leb(body, position)
            memories.append({"initial_pages": initial, "maximum_pages": maximum,
                             "shared": bool(flags & 2), "memory64": bool(flags & 4)})
    return memories


def stats(values):
    ordered = sorted(values)
    return {"count": len(values), "best": ordered[0], "median": statistics.median(values),
            "p95": ordered[math.ceil(len(ordered) * .95) - 1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/wasm-compare")
    parser.add_argument("--prepare-toolchains", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--revision", default="unknown (bx omits Git metadata)")
    parser.add_argument("--build-samples", type=int, default=7)
    parser.add_argument("--cold-samples", type=int, default=12)
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--samples", type=int, default=200)
    args = parser.parse_args()
    for field, bound in (("build_samples", 30), ("cold_samples", 50), ("warmups", 100), ("samples", 2000)):
        if not 1 <= getattr(args, field) <= bound:
            parser.error(f"{field} must be between 1 and {bound}")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("the pinned toolchains require a Linux x86_64 build box")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tools, pins = toolchains(output / "toolchains", args.prepare_toolchains)
    if args.prepare_only:
        print(json.dumps({name: str(value) for name, value in tools.items()}, indent=2))
        return
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is required")
    clang = os.environ.get("LLVM_CC") or run(["sh", "tools/toolchain.sh", "default-clang"])[0].decode().strip()
    cache = output / "cache"
    work = output / "working"
    artifacts = output / "artifacts"
    # A validation/repeat invocation must not silently inherit the first-use
    # dependency caches from an earlier run. Toolchain archives are retained.
    shutil.rmtree(cache, ignore_errors=True)
    for directory in (cache, work, artifacts):
        directory.mkdir(exist_ok=True)
    sources = {name: SOURCES / f"hello.{extension}" for name, extension in EXTENSIONS.items()}
    oracle = (SOURCES / "expected.txt").read_bytes()
    if oracle != b"Hello, world!\n":
        raise RuntimeError("the independently specified oracle changed")
    environment = os.environ.copy()
    environment.update({"GOTOOLCHAIN": "local", "CGO_ENABLED": "0", "GOOS": "wasip1", "GOARCH": "wasm",
                        "GOROOT": str(tools["go"].parent.parent), "GOFLAGS": "", "RUSTFLAGS": "", "NODE_OPTIONS": "",
                        "GOCACHE": str(cache / "go"), "GOMODCACHE": str(cache / "go-mod"),
                        "ZIG_GLOBAL_CACHE_DIR": str(cache / "zig-global"), "ZIG_LOCAL_CACHE_DIR": str(cache / "zig-local"),
                        "LLVM_CC": clang, "MINYAR_COMPILER": str(ROOT / "build/minyarc"),
                        "MINYAR_WASM_RUNTIME": str(ROOT / "build/wasm/runtime.o"), "WASM_SYSROOT": str(ROOT / "build/wasm/sysroot")})
    evidence = {
        "schema": 1, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_head": args.revision,
        "host": {"platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count(),
                 "affinity": sorted(os.sched_getaffinity(0)),
                 "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), "unknown")},
        "pins": pins, "oracle": {"hex": oracle.hex(), "sha256": sha256(oracle)},
        "source": {name: {"path": str(source.relative_to(ROOT)), "text": source.read_text(), "sha256": sha256(source.read_bytes())} for name, source in sources.items()},
        "versions": {}, "binaries": {}, "builds": [], "cold": [],
        "method": {
            "runtime": "same Node/V8 node:wasi Preview 1 host for every module",
            "release": "Minyar -O2; Go default optimization -s -w; Rust opt-level=3/lto=fat/panic=abort/strip=symbols; Zig ReleaseFast/-fstrip",
            "common_strip": "remove all custom metadata sections after compiler-native stripping; standard sections preserved byte for byte",
            "builds": "first isolated dependency-cache build, then warm dependency-cache builds with a unique trailing source comment to invalidate main-package source caches; output removed each time",
            "prebuilt": "Minyar compiler/runtime/sysroot and Rust target std are prebuilt; Go/Zig first builds may compile standard-library dependencies; installation excluded",
            "cold": "fresh Node process and WebAssembly.compile, OS page cache uncontrolled; not cold disk/network",
            "warm": "precompiled module reused; fresh WASI context/instance each sample, rotated/reversed language order; explicit GC between rounds outside timers",
            "io": "real stdout captured to temporary files; syscall write cost included in start, capture verification excluded",
            "scope": "14-byte hello-world startup only; no claims about general language throughput",
        },
    }
    for name, (program, flags) in {
        "go": (tools["go"], ["version"]), "rust": (tools["rust"], ["--version", "--verbose"]),
        "zig": (tools["zig"], ["version"]), "clang": (clang, ["--version"]), "node": (node, ["--version"]),
    }.items():
        evidence["versions"][name] = {"output": run([program, *flags], env=environment)[0].decode(),
                                      "path": str(program), "sha256": sha256(Path(shutil.which(str(program)) or program).read_bytes())}
    for name, file in (("minyarc", ROOT / "build/minyarc"), ("minyar_runtime", ROOT / "build/wasm/runtime.o")):
        evidence["versions"][name] = {"path": str(file), "sha256": sha256(file.read_bytes())}
    evidence["harness"] = {str(file.relative_to(ROOT)): {"sha256": sha256(file.read_bytes()), "text": file.read_text()}
                            for file in (Path(__file__).resolve(), SOURCES / "run.mjs", ROOT / "tools/wasm-target.mjs")}
    evidence["build_environment"] = {key: environment[key] for key in ("GOTOOLCHAIN", "CGO_ENABLED", "GOOS", "GOARCH", "GOROOT", "GOFLAGS", "RUSTFLAGS", "NODE_OPTIONS", "GOCACHE", "GOMODCACHE", "ZIG_GLOBAL_CACHE_DIR", "ZIG_LOCAL_CACHE_DIR", "LLVM_CC", "MINYAR_COMPILER", "MINYAR_WASM_RUNTIME", "WASM_SYSROOT")}
    evidence_path = output / "results.json"
    write_json(evidence_path, evidence)

    # Round zero records isolated dependency-cache setup. Every later sample
    # changes a source comment so Go cannot merely copy its cached executable.
    for round_ in range(args.build_samples + 1):
        order = list(LANGUAGES[round_ % 4:] + LANGUAGES[:round_ % 4])
        if (round_ // 4) % 2:
            order.reverse()
        for position, name in enumerate(order):
            source = work / f"hello.{EXTENSIONS[name]}"
            source.write_text(sources[name].read_text() + f"\n// benchmark rebuild {round_}\n")
            raw = artifacts / f"{name}.raw.wasm"
            raw.unlink(missing_ok=True)
            commands = {
                "minyar": [node, "tools/wasm-target.mjs", source, raw, "-O2"],
                "go": [tools["go"], "build", "-trimpath", "-ldflags=-s -w -buildid=", "-o", raw, source],
                "rust": [tools["rust"], source, "--edition=2024", "--target=wasm32-wasip1", "-C", "opt-level=3", "-C", "lto=fat", "-C", "codegen-units=1", "-C", "panic=abort", "-C", "strip=symbols", "-C", "debuginfo=0", "-o", raw],
                "zig": [tools["zig"], "build-exe", source, "-target", "wasm32-wasi", "-O", "ReleaseFast", "-fstrip", f"-femit-bin={raw}"],
            }
            _, duration = run(commands[name], env=environment, timeout=240)
            original = raw.read_bytes()
            delivered = strip_custom_metadata(original)
            if [encoded for kind, encoded, _ in sections(original) if kind] != [encoded for kind, encoded, _ in sections(delivered) if kind]:
                raise RuntimeError("metadata stripping changed executable sections")
            binary = artifacts / f"{name}.wasm"
            binary.write_bytes(delivered)
            compressed = gzip.compress(delivered, compresslevel=9, mtime=0)
            binary.with_suffix(".wasm.gz").write_bytes(compressed)
            evidence["builds"].append({"name": name, "round": round_, "position": position,
                                       "dependency_cache_first_use": round_ == 0, "source_sha256": sha256(source.read_bytes()),
                                       "argv": [str(item) for item in commands[name]], "wall_ns": duration,
                                       "binary_sha256": sha256(delivered)})
            evidence["binaries"][name] = {"path": str(binary), "compiler_output_bytes": len(original),
                                          "bytes": len(delivered), "gzip9_bytes": len(compressed),
                                          "sha256": sha256(delivered), "gzip_sha256": sha256(compressed),
                                          "declared_memory": memory_limits(delivered)}
            write_json(evidence_path, evidence)
            print(f"build {round_} {name}: {duration / 1e6:.1f} ms, {len(delivered)} bytes", file=sys.stderr, flush=True)

    def engine(configuration, destination):
        config = output / "runner-config.json"
        write_json(config, configuration)
        encoded, duration = run([node, "--no-warnings", "--expose-gc", SOURCES / "run.mjs", config], env=environment, timeout=180)
        value = json.loads(encoded)
        write_json(destination, value)
        return value, duration

    for round_ in range(args.cold_samples):
        order = list(LANGUAGES[round_ % 4:] + LANGUAGES[:round_ % 4])
        if (round_ // 4) % 2:
            order.reverse()
        for position, name in enumerate(order):
            value, duration = engine({"oracle": str(SOURCES / "expected.txt"), "warmups": 0, "samples": 1,
                                      "modules": {name: evidence["binaries"][name]["path"]}}, output / f"cold-{round_}-{name}.json")
            value.update({"name": name, "round": round_, "position": position, "process_wall_ns": duration})
            evidence["cold"].append(value)
        write_json(evidence_path, evidence)
    warm, _ = engine({"oracle": str(SOURCES / "expected.txt"), "warmups": args.warmups, "samples": args.samples,
                      "modules": {name: evidence["binaries"][name]["path"] for name in LANGUAGES}}, output / "warm.json")
    evidence["warm"] = warm
    summary = {}
    for name in LANGUAGES:
        builds = [item["wall_ns"] for item in evidence["builds"] if item["name"] == name and item["round"] > 0]
        cold = [item for item in evidence["cold"] if item["name"] == name]
        samples = [item for item in warm["samples"] if item["name"] == name]
        summary[name] = {"build_warm_ns": stats(builds), "cold_process_ns": stats([item["process_wall_ns"] for item in cold]),
                         "cold_load_ns": stats([item["modules"][name]["load_ns"] for item in cold]),
                         "cold_compile_ns": stats([item["modules"][name]["compile_ns"] for item in cold]),
                         "warm_initial_pages": stats([item["initial_memory_pages"] for item in samples]),
                         "warm_peak_pages": stats([item["peak_memory_pages"] for item in samples])}
        for phase in ("setup_ns", "instantiate_ns", "run_ns", "ready_module_total_ns"):
            summary[name]["cold_" + phase] = stats([item["samples"][0][phase] for item in cold])
            summary[name]["warm_" + phase] = stats([item[phase] for item in samples])
    evidence["summary"] = summary
    write_json(evidence_path, evidence)
    print(json.dumps({"results": str(evidence_path), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
