#!/usr/bin/env python3
"""Batch the maintained safelibs fixtures with balanced same-process A/B controls.

Run ON bx, from the compiler checkout; this script never compiles anything:
python3 experiments/codegen/safelibs-study.py \
  --product .codegen-bench/safelibs \
  --baseline build/codegen-safelibs/codegen-baseline/libsafelibs.so \
  --candidate build/codegen-safelibs/codegen-inline/libsafelibs.so \
  --output build/codegen-safelibs-batched-first

Requires the product's Pillow/libz/libpng/TurboJPEG reference dependencies.
There is no timing acceptance threshold. Output directories must be new.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import time
import zlib


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def batch(function, calls: int):
    # The maintained wrapper's allocation/copy/guards/owner assertions are
    # inside timing. Validate full final output and hash it after timing.
    last = None
    cpu_start, wall_start = time.thread_time_ns(), time.perf_counter_ns()
    for _ in range(calls):
        last = function()
    wall = time.perf_counter_ns() - wall_start
    cpu = time.thread_time_ns() - cpu_start
    return last, {"calls": calls, "cpu_ns": cpu, "wall_ns": wall,
                  "cpu_ns_per_call": cpu / calls, "wall_ns_per_call": wall / calls}


def result_summary(codec: str, value, native: bool) -> dict:
    if codec == "zlib":
        status, pixels, consumed = value
        return {"status": status, "bytes": len(pixels), "consumed": consumed,
                "output_sha256": hashlib.sha256(pixels).hexdigest()}
    if native:
        width, height, pixels = value
        status = 0
    else:
        status, width, height, pixels = value
    return {"status": status, "width": width, "height": height, "bytes": len(pixels),
            "output_sha256": hashlib.sha256(pixels).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-label", default="baseline")
    parser.add_argument("--candidate-label", default="inline")
    parser.add_argument("--baseline-compiler", type=Path)
    parser.add_argument("--candidate-compiler", type=Path)
    parser.add_argument("--provenance", type=Path, help="optional caller-supplied JSON build identities/flags")
    parser.add_argument("--samples", type=int, default=15, help="at least 15 and a multiple of 3 for positional balance")
    parser.add_argument("--batch-calls", type=int, default=128)
    parser.add_argument("--min-batch-ms", type=float, default=25,
                        help="choose common calls from fastest warmup CPU; 0 disables adjustment")
    parser.add_argument("--max-batch-calls", type=int, default=4096)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("run only on Linux bx; no laptop measurements")
    if args.samples < 15 or args.samples % 3 or args.batch_calls < 1 or args.max_batch_calls < args.batch_calls or not math.isfinite(args.min_batch_ms) or args.min_batch_ms < 0:
        parser.error("require samples >=15 divisible by3, bounded positive calls and finite nonnegative min-batch-ms")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema": 1, "status": "preparing", "command": sys.argv,
        "labels": {"baseline": args.baseline_label, "candidate": args.candidate_label, "native": "incumbent"},
        "method": {"process": "same process, both isolated RTLD_LOCAL candidate DSOs and native references",
            "clock": "thread_time_ns CPU and perf_counter_ns wall; no process startup in either interval",
            "scope": "complete maintained ctypes API calls including allocations/copies/guards/live-object assertion; Python batch loop included",
            "validation": "exact baseline=candidate outside timing; zlib/PNG independent oracle exact; gray-valued RGB JPEG native maximum channel error2, opaque alpha",
            "order": "successive groups of3 use all rotations of forward then reverse profiles, giving equal position counts",
            "warmup": "one retained initial batch per profile/codec; measured batch calls may increase equally for all profiles from fastest warmup CPU",
            "samples": args.samples, "initial_batch_calls": args.batch_calls, "target_batch_ms": args.min_batch_ms,
            "max_batch_calls": args.max_batch_calls, "acceptance": "correctness only; no timing bound"},
        "limitations": ["small maintained synthetic warm-cache workloads, not broad codec throughput",
            "shared-host CPU load, cache and frequency are uncontrolled",
            "wrappers retain their existing per-call safety checks; complete output checked for final call in each batch",
            "baseline and candidate source/build provenance beyond DSO hashes must be supplied by caller",
            "native wrappers differ from candidate API wrappers as documented by maintained benchmark",
            "native library versions/loaded-file hashes reported where available; no perf counters in this study"],
        "warmups": [], "observations": [], "orders": [], "workloads": {}, "summaries": []}
    save(output / "results.json", report)
    try:
        from PIL import Image, __version__ as pillow_version, features

        product = args.product.resolve()
        source = product / "tests/check.py"
        frozen_source = output / "safelibs-check.py"
        shutil.copy2(source, frozen_source)
        shutil.copy2(Path(__file__).resolve(), output / "safelibs-study.py")
        spec = importlib.util.spec_from_file_location("codegen_safelibs_check", frozen_source)
        require(spec is not None and spec.loader is not None, "cannot import frozen product tests/check.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        metadata = {"python": sys.version, "platform": platform.platform(), "uname": list(platform.uname()),
            "cpu_count": os.cpu_count(), "cpu": module.cpu_description(), "pillow": pillow_version,
            "pillow_jpeg": features.version_codec("jpg"), "python_zlib": zlib.ZLIB_RUNTIME_VERSION,
            "product": str(product), "check_source_sha256": digest(frozen_source),
            "study_sha256": digest(output / "safelibs-study.py"),
            "environment": {name: os.environ.get(name) for name in
                ("SAFELIBS_BUILD_OPTIONS", "MINYAR_CLANG_FLAGS", "MINYAR_NATIVE_FLAGS", "MINYAR_RUNTIME_FLAGS",
                 "MINYAR_MEMORY_PROFILE", "MINYAR_PARALLEL_THREADS", "OMP_NUM_THREADS", "BX_SLOT", "BX_TIMEOUT")},
            "source_sha256": {}}
        report["metadata"] = metadata
        for directory in ("src", "native", "scripts", "tests"):
            for path in sorted((product / directory).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    metadata["source_sha256"][str(path.relative_to(product))] = digest(path)
        if (product / "Makefile").is_file():
            metadata["source_sha256"]["Makefile"] = digest(product / "Makefile")
        if args.provenance:
            shutil.copy2(args.provenance.resolve(), output / "caller-provenance.json")
            metadata["caller_provenance"] = json.loads((output / "caller-provenance.json").read_text())
        metadata["compilers"] = {label: {"path": str(path.resolve()), "sha256": digest(path.resolve())} if path else None
            for label, path in (("baseline", args.baseline_compiler), ("candidate", args.candidate_compiler))}
        safe, library_info = {}, {}
        for label, path in (("baseline", args.baseline), ("candidate", args.candidate)):
            original = path.resolve()
            frozen = output / (label + "-libsafelibs.so")
            shutil.copy2(original, frozen)
            safe[label] = module.Safelibs(frozen)
            library_info[label] = {"original": str(original), "measured": str(frozen), "sha256": digest(frozen),
                                   "version": safe[label].library.safelibs_version().decode()}
        metadata["libraries"] = library_info
        zpath = ctypes.util.find_library("z")
        ppath = ctypes.util.find_library("png16") or ctypes.util.find_library("png")
        jpath = ctypes.util.find_library("turbojpeg")
        require(bool(zpath and ppath and jpath), "native libz/libpng/TurboJPEG required; no Pillow fallback")
        zlibrary = ctypes.CDLL(zpath, mode=ctypes.RTLD_LOCAL)
        plibrary = ctypes.CDLL(ppath, mode=ctypes.RTLD_LOCAL)
        jlibrary = ctypes.CDLL(jpath, mode=ctypes.RTLD_LOCAL)
        native_zlib = module.Inflater(zlibrary)
        native_png = module.PngReference(plibrary)
        native_jpeg = module.JpegReference(jlibrary)
        zlibrary.zlibVersion.argtypes, zlibrary.zlibVersion.restype = (), ctypes.c_char_p
        plibrary.png_get_libpng_ver.argtypes, plibrary.png_get_libpng_ver.restype = (ctypes.c_void_p,), ctypes.c_char_p
        metadata["native"] = {"zlib": zpath, "png": ppath, "turbojpeg": jpath,
            "zlib_version": zlibrary.zlibVersion().decode(), "png_version": plibrary.png_get_libpng_ver(None).decode(),
            "jpeg_flags": "RGBA=7, FASTUPSAMPLE=256, ACCURATEDCT=4096; maintained JpegReference"}
        maps = Path("/proc/self/maps")
        if maps.exists():
            mapped = maps.read_text()
            (output / "loaded-libraries.txt").write_text(mapped)
            loaded_paths = {Path(line.split()[-1]) for line in mapped.splitlines() if "/" in line and line.split()[-1].startswith("/")}
            metadata["native"]["mapped_file_sha256"] = {str(path): digest(path) for path in sorted(loaded_paths)
                if path.is_file() and any(name in path.name for name in ("libz.so", "libpng", "libturbojpeg", "libjpeg"))}
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            (output / "cpuinfo.txt").write_text(cpuinfo.read_text())

        # Exactly the maintained benchmark's generation parameters and bytes.
        payload = (b"Minyar safe library benchmark: finite repeated text and binary.\n" + bytes(range(256))) * 192
        stream = zlib.compress(payload)
        png, expected_png = module.png_fixture(width=64, height=64, fixed_filter=1)
        image = Image.new("RGB", (64, 64))
        image.putdata([((x * 7 + y * 3) % 256,) * 3 for y in range(64) for x in range(64)])
        encoded = io.BytesIO()
        image.save(encoded, "JPEG", quality=85, subsampling=0)
        jpeg = encoded.getvalue()
        inputs = {"zlib": stream, "png": png, "jpeg": jpeg}
        functions = {"zlib": {label: lambda owner=owner: owner.inflate(stream, len(payload)) for label, owner in safe.items()},
                     "png": {label: lambda owner=owner: owner.image("png", png) for label, owner in safe.items()},
                     "jpeg": {label: lambda owner=owner: owner.image("jpeg", jpeg) for label, owner in safe.items()}}
        functions["zlib"]["native"] = lambda: native_zlib.inflate(stream, len(payload))
        functions["png"]["native"] = lambda: native_png.decode(png)
        functions["jpeg"]["native"] = lambda: native_jpeg.decode(jpeg)
        expected_outputs = {}
        for codec, data in inputs.items():
            (output / ("fixture." + codec)).write_bytes(data)
            decoded = {label: function() for label, function in functions[codec].items()}
            require(decoded["baseline"] == decoded["candidate"], codec + ": baseline and candidate outputs differ")
            if codec == "zlib":
                require(decoded["baseline"] == decoded["native"] == (0, payload, len(stream)), "zlib exact independent payload/status/consumption mismatch")
                error = 0
            elif codec == "png":
                require(decoded["baseline"] == (0, 64, 64, expected_png) and decoded["native"] == (64, 64, expected_png), "PNG independent generated pixels mismatch")
                error = 0
            else:
                error = module.close_pixels(decoded["baseline"], decoded["native"], 2, "maintained gray-valued RGB JPEG native comparison")
            expected_outputs[codec] = decoded
            report["workloads"][codec] = {"input_bytes": len(data), "input_sha256": hashlib.sha256(data).hexdigest(),
                "decoded_bytes": len(payload) if codec == "zlib" else 64 * 64 * 4, "native_maximum_channel_error": error,
                "jpeg_tolerance_source": "tests/check.py check_jpeg: grayscale/gray-valued RGB tolerance2" if codec == "jpeg" else None,
                "outputs": {label: result_summary(codec, value, label == "native") for label, value in decoded.items()}}
        report["status"] = "measuring"
        save(output / "results.json", report)
        profiles = ["baseline", "candidate", "native"]
        for codec in inputs:
            warmup_cpu = []
            for label in profiles:
                last, observation = batch(functions[codec][label], args.batch_calls)
                require(last == expected_outputs[codec][label], codec + " " + label + ": warmup output changed")
                warmup_cpu.append(observation["cpu_ns"])
                report["warmups"].append({"codec": codec, "profile": label, **observation})
                save(output / "results.json", report)
            requested = args.batch_calls * max(1, math.ceil(args.min_batch_ms * 1e6 / max(1, min(warmup_cpu))))
            calls = min(requested, args.max_batch_calls)
            report["workloads"][codec].update({"measured_batch_calls": calls, "requested_batch_calls": requested,
                                                 "calibration_capped": requested > args.max_batch_calls})
            for sample in range(args.samples):
                direction = profiles if (sample // 3) % 2 == 0 else list(reversed(profiles))
                offset = sample % 3
                order = direction[offset:] + direction[:offset]
                report["orders"].append({"codec": codec, "sample": sample, "profiles": order})
                for position, label in enumerate(order):
                    last, observation = batch(functions[codec][label], calls)
                    require(last == expected_outputs[codec][label], codec + " " + label + ": batch output changed")
                    report["observations"].append({"codec": codec, "profile": label, "sample": sample,
                        "position": position, "output": result_summary(codec, last, label == "native"), **observation})
                    save(output / "results.json", report)
            rows = [row for row in report["observations"] if row["codec"] == codec]
            medians = {label: {metric: statistics.median(row[metric] for row in rows if row["profile"] == label)
                for metric in ("cpu_ns_per_call", "wall_ns_per_call")} for label in profiles}
            paired = []
            for sample in range(args.samples):
                round_rows = {row["profile"]: row for row in rows if row["sample"] == sample}
                paired.append({"sample": sample, "candidate_over_baseline_cpu": round_rows["candidate"]["cpu_ns"] / round_rows["baseline"]["cpu_ns"],
                    "baseline_over_native_cpu": round_rows["baseline"]["cpu_ns"] / round_rows["native"]["cpu_ns"],
                    "candidate_over_native_cpu": round_rows["candidate"]["cpu_ns"] / round_rows["native"]["cpu_ns"]})
            summary = {"codec": codec, "calls_per_batch": calls, "median_ns_per_call": medians, "paired_ratios": paired,
                "candidate_over_baseline_cpu": medians["candidate"]["cpu_ns_per_call"] / medians["baseline"]["cpu_ns_per_call"],
                "baseline_over_native_cpu": medians["baseline"]["cpu_ns_per_call"] / medians["native"]["cpu_ns_per_call"],
                "candidate_over_native_cpu": medians["candidate"]["cpu_ns_per_call"] / medians["native"]["cpu_ns_per_call"]}
            report["summaries"].append(summary)
            save(output / "results.json", report)
            print(json.dumps(summary, indent=2), flush=True)
        for label, owner in safe.items():
            owner.clean()
            require(digest(Path(library_info[label]["measured"])) == library_info[label]["sha256"], label + ": measured DSO changed")
        report["calls"] = {label: owner.calls for label, owner in safe.items()}
        report["status"] = "complete"
        save(output / "results.json", report)
        return 0
    except Exception as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        save(output / "results.json", report)
        print(report["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
