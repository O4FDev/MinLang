#!/usr/bin/env python3
"""Remote-only paired byte/List codegen study; no timing acceptance bound.

Example ON bx codegen, from the compiler checkout:
python3 experiments/codegen/byte-access-study.py \
  --baseline build/codegen-baseline/minyarc --candidate build/minyarc
Optional: --thinlto --perf /path/to/perf --perf-sudo
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--clang", help="defaults to tools/toolchain.sh default-clang")
    parser.add_argument("--output", type=Path, default=ROOT / "build/codegen-byte-access")
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--elements", type=int, default=65536)
    parser.add_argument("--repeats", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--thinlto", action="store_true")
    parser.add_argument("--perf", type=Path)
    parser.add_argument("--perf-sudo", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("run only on the Linux bx host; no laptop builds or tests")
    if args.samples < 7 or not 0 <= args.elements <= 16777216 or not 1 <= args.repeats <= 1073741824 or args.timeout <= 0:
        parser.error("require samples >= 7, bounded elements/repeats and positive timeout")
    if args.perf_sudo and not args.perf:
        parser.error("--perf-sudo requires --perf")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)  # Never overwrite prior evidence.
    commands: list[dict] = []

    def run(command: list[str], name: str) -> str:
        command = [str(word) for word in command]
        record = {"command": command, "cwd": str(ROOT), "name": name}
        commands.append(record)
        save(output / "commands.json", commands)
        print("+ " + shlex.join(command), flush=True)
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=args.timeout)
        except subprocess.TimeoutExpired as error:
            record["timed_out"] = True
            for field in ("stdout", "stderr"):
                value = getattr(error, field) or ""
                (output / (name + "." + field)).write_text(value.decode(errors="replace") if isinstance(value, bytes) else value)
            save(output / "commands.json", commands)
            raise
        record["status"] = result.returncode
        (output / (name + ".stdout")).write_text(result.stdout)
        (output / (name + ".stderr")).write_text(result.stderr)
        save(output / "commands.json", commands)
        if result.returncode:
            raise RuntimeError(f"{name}: exit {result.returncode}; see retained stderr")
        return result.stdout

    report: dict = {"schema": 1, "status": "preparing", "platform": os.uname().sysname + " " + os.uname().machine,
        "samples": args.samples, "elements": args.elements, "repeats": args.repeats, "observations": [],
        "scope": "kernel CPU/wall; setup, one internal warmup, complete storage validation and ownership drain excluded",
        "perf_scope": "optional whole executable, INCLUDING setup/validation/teardown; not kernel-only counters",
        "limitations": ["shared-host scheduling and caches uncontrolled", "compiler/runtime private ABI",
            "small synthetic kernels; no complete-library or unsafe-C equivalence claim", "no timing acceptance threshold",
            "checked C has no restrict; both paths use identical bounded nonnegative data", "one retained process warmup observation plus one untimed kernel call per process"]}
    save(output / "results.json", report)
    try:
        clang = args.clang or run(["sh", "tools/toolchain.sh", "default-clang"], "select-clang").strip()
        report["clang"] = {"path": clang, "version": run([clang, "--version"], "clang-version")}
        report["host"] = run(["uname", "-a"], "host").strip()
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            (output / "cpuinfo.txt").write_text(cpuinfo.read_text())
        # Freeze every measured source and executable before collecting samples.
        source = output / "byte-access.min"
        driver = output / "byte-access-driver.c"
        shutil.copy2(HERE / source.name, source)
        shutil.copy2(HERE / driver.name, driver)
        shutil.copy2(ROOT / "tests/llvm_symbols.h", output / "llvm_symbols.h")
        shutil.copy2(Path(__file__).resolve(), output / "byte-access-study.py")
        runtime_tree = output / "runtime-source"
        shutil.copytree(ROOT / "runtime", runtime_tree)
        compilers = {}
        for label, original in (("baseline", args.baseline), ("candidate", args.candidate)):
            frozen = output / (label + "-minyarc")
            shutil.copy2(original.resolve(), frozen)
            compilers[label] = frozen
        report["source_sha256"] = {path.name: digest(path) for path in (source, driver, output / "llvm_symbols.h", output / "byte-access-study.py")}
        report["runtime_sha256"] = {str(path.relative_to(runtime_tree)): digest(path) for path in sorted(runtime_tree.rglob("*")) if path.is_file()}
        report["compiler_sha256"] = {label: digest(path) for label, path in compilers.items()}
        runtime = output / "runtime-wrapper.c"
        runtime.write_text('#define MINYAR_RC_TESTING 1\n#include "runtime-source/minyar_default_runtime.c"\n'
            'void codegen_probe_drain(void) {\n'
            '    while (rc_pending_count) minyar_rc_poll(1024);\n'
            '    if (rc_frames || minyar_call_depth) abort();\n}\n'
            'size_t codegen_probe_live(void) { return rc_object_count; }\n')
        report["runtime_wrapper_sha256"] = digest(runtime)
        llvm_paths = {}
        for label, compiler in compilers.items():
            raw = output / (label + ".raw.ll")
            run([compiler, source, raw, "--library", ROOT / "library"], "compile-" + label)
            text = raw.read_text()
            if len(re.findall(r"(?m)^define i32 @main\(", text)) != 1 or text.count("@main(") != 1:
                raise ValueError("expected exactly one generated unused main")
            for name in ("codegenByteSum", "codegenByteCopy", "codegenIntegerListSum"):
                if not re.search(r"(?m)^define i64 @\.minyar\.fn\." + name + r"\(", text):
                    raise ValueError("missing direct generated symbol: " + name)
            llvm = output / (label + ".ll")
            llvm.write_text(text.replace("@main(", "@codegen_unused_main("))
            llvm_paths[label] = llvm
        binaries = {}
        modes = ("separate-o2", "thinlto") if args.thinlto else ("separate-o2",)
        for mode in modes:
            flags = ["-O2", "-g", "-fno-omit-frame-pointer"]
            if mode == "thinlto":
                flags += ["-flto=thin"]
            runtime_input = runtime
            if mode == "thinlto":
                # Match the public launcher's target-attribute normalization.
                raw_runtime = output / "runtime.raw.ll"
                run([clang, *flags, "-S", "-emit-llvm", runtime, "-o", raw_runtime], "emit-runtime")
                runtime_input = output / "runtime.ll"
                runtime_input.write_text(re.sub(r'"(?:target-cpu|target-features|tune-cpu)"="[^"]*" ?', "", raw_runtime.read_text()))
            runtime_object = output / (mode + "-runtime.o")
            driver_object = output / (mode + "-driver.o")
            run([clang, *flags, "-Wno-override-module", "-c", runtime_input, "-o", runtime_object], mode + "-runtime")
            run([clang, *flags, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", output, "-c", driver, "-o", driver_object], mode + "-driver")
            for label, llvm in llvm_paths.items():
                generated = output / (mode + "-" + label + ".o")
                binary = output / (mode + "-" + label)
                run([clang, *flags, "-Wno-override-module", "-c", llvm, "-o", generated], mode + "-" + label + "-object")
                linker = ["-fuse-ld=lld", "-Wl,--threads=1"] if mode == "thinlto" else []
                run([clang, *flags, *linker, generated, driver_object, runtime_object, "-lm", "-pthread", "-ldl", "-o", binary], mode + "-" + label + "-link")
                binaries[(mode, label)] = binary
        report["artifact_sha256"] = {path.name: digest(path) for path in sorted(output.iterdir()) if path.suffix in (".ll", ".o") or path in binaries.values()}
        report["status"] = "measuring"
        save(output / "results.json", report)
        for mode in modes:
            for kernel in ("sum", "copy", "list-sum"):
                order = [("baseline", "c"), ("baseline", "minyar"), ("candidate", "minyar"), ("candidate", "c")]
                checksums = set()
                for sample in range(args.samples + 1):
                    for label, implementation in (order if sample % 2 == 0 else list(reversed(order))):
                        binary = binaries[(mode, label)]
                        if digest(binary) != report["artifact_sha256"][binary.name]:
                            raise ValueError("binary changed during measurement")
                        name = f"{mode}-{kernel}-{sample}-{label}-{implementation}"
                        command = [str(binary), implementation, kernel, str(args.elements), str(args.repeats)]
                        perf_output = output / (name + ".perf")
                        if args.perf:
                            command = (["sudo", "-n"] if args.perf_sudo else []) + [str(args.perf.resolve()), "stat", "-x", ",", "-e", "cycles:u,instructions:u", "-o", str(perf_output), "--", *command]
                        observation = json.loads(run(command, name))
                        checksums.add(observation["checksum"])
                        row = {"mode": mode, "kernel": kernel, "sample": sample, "warmup": sample == 0,
                               "compiler": label, "implementation": implementation, **observation}
                        if args.perf:
                            row["perf_raw"] = perf_output.read_text()
                        report["observations"].append(row)
                        save(output / "results.json", report)
                expected = args.elements * args.repeats if kernel == "copy" else sum((i * 17 + 13) & 255 for i in range(args.elements)) * args.repeats
                if checksums != {expected}:
                    raise ValueError(f"{kernel}: independent checksum mismatch")
        report["medians"] = []
        for mode in modes:
            for kernel in ("sum", "copy", "list-sum"):
                for label in compilers:
                    rows = [row for row in report["observations"] if not row["warmup"] and row["mode"] == mode and row["kernel"] == kernel and row["compiler"] == label]
                    medians = {impl: {metric: statistics.median(row[metric] for row in rows if row["implementation"] == impl) for metric in ("cpu_ns", "wall_ns")} for impl in ("c", "minyar")}
                    report["medians"].append({"mode": mode, "kernel": kernel, "compiler": label, "median_ns": medians,
                        "minyar_over_c_cpu": medians["minyar"]["cpu_ns"] / medians["c"]["cpu_ns"]})
        report["status"] = "complete"
        save(output / "results.json", report)
        print(json.dumps(report["medians"], indent=2))
        return 0
    except Exception as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        save(output / "results.json", report)
        print(report["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
