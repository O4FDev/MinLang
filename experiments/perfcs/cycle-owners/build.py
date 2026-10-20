#!/usr/bin/env python3
"""Prepare this isolated study ON bx only, from a complete frozen product build.

python3 .perfcs/cycle-owner-study/build.py --products-manifest build/PRODUCTS/manifest.json
No live runtime fallback, no LLVM regeneration, no LTO, no shipping accounting.
Every build and ownership run is bounded and retained; new output directories only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
FROZEN_HEAD = "7b36666d800fa02619a360327faec220e1dfab8d"
FROZEN_HEADERS = {
    "minyar_rc.h": "73e3c1e4d94a5ea878dfcd0754b30e27175cab738673bbf8598bb4980f598533",
    "minyar_cycle_rc.h": "a49b87abc80e56355e9ff1c1b0404154b0bf7377ecdbb2c603e13b2ddeaad353",
    "minyar_bounded_rc.h": "922ec6fa0ededc3ad90cbc19f55c8f8dfd6cde7ddd097184f13da176a26bfb64",
    "minyar_cycle_bounded_rc.h": "a6862524df41054c949f46764f320031c078f35eb3644380aeef6ece86944fad",
}
BEGIN = "            /* Sole owner queue:"
END = "            /* End sole owner queue batching. */\n"
FLAGS = ["-O2", "-g", "-fPIC", "-fno-omit-frame-pointer", "-Wno-override-module"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def save(path, value):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    pending.replace(path)


def cycle_source(source):
    # Exact frozen product cycle transformation; source identity is also hashed.
    for old, new in (("minyar_rc.h", "minyar_cycle_rc.h"),
                     ("minyar_collections.h", "minyar_cycle_collections.h")):
        before, after = '#include "' + old + '"', '#include "' + new + '"'
        require(source.count(before) == 1, "cycle include must occur once: " + old)
        source = source.replace(before, after)
    return ('#define MINYAR_SORT_GRAPH 1\n#define MINYAR_MAP_CYCLE_RUNTIME 1\n'
            '#if defined(__GNUC__) || defined(__clang__)\n'
            '#define MINYAR_NOINLINE __attribute__((noinline))\n#else\n'
            '#define MINYAR_NOINLINE\n#endif\n' + source +
            '\n#include "minyar_callbacks.h"\n')


class Builder:
    def __init__(self, args):
        self.args = args
        self.out = args.output.resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        (self.out / "logs").mkdir()
        self.manifest = {"schema": 1, "status": "building", "commands": [],
                         "checks": [], "workloads": [], "runtime_accounting": {},
                         "frozen_gate_head": FROZEN_HEAD,
                         "flags": FLAGS, "method": "same native O2 workload object; separate O2 runtime links; no LTO",
                         "scope": "activated cycle owner batching native microstudy only; no product speedup inference"}
        self.checkpoint()

    def checkpoint(self):
        save(self.out / "manifest.json", self.manifest)

    def run(self, argv, label, timeout=600):
        argv = list(map(str, argv))
        stem = self.out / "logs" / (f"{len(self.manifest['commands']):04d}-" + label)
        row = {"argv": argv, "timeout_seconds": timeout,
               "stdout": str(stem) + ".stdout", "stderr": str(stem) + ".stderr"}
        self.manifest["commands"].append(row)
        self.checkpoint()
        print("STUDY_BUILD", label, flush=True)
        began = time.monotonic()
        try:
            result = subprocess.run(argv, capture_output=True, timeout=timeout)
            stdout, stderr, status = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, status = error.stdout or b"", error.stderr or b"", 124
        Path(row["stdout"]).write_bytes(stdout)
        Path(row["stderr"]).write_bytes(stderr)
        row.update({"exit": status, "wall_seconds": time.monotonic() - began,
                    "stdout_sha256": digest(row["stdout"]), "stderr_sha256": digest(row["stderr"])})
        self.checkpoint()
        require(status == 0, "command failed; logs retained: " + str(stem))
        return stdout, stderr

    def object(self, source, target, extra=()):
        self.run([self.clang, *FLAGS, *extra, "-c", source, "-o", target], target.stem)
        return target

    def build(self):
        source_manifest_path = self.args.products_manifest.resolve()
        product = json.loads(source_manifest_path.read_text())
        require(product["status"] == "ready", "product build must be complete")
        require({work["kind"] for work in product["workloads"]} >= {"js", "jsmn", "safelibs"},
                "a focused partial product build is not the required complete frozen input")
        require(product["flags"] == FLAGS, "frozen product O2 flags changed")
        require(product["profiles"].get("default") == ["--bounded-owners", "32"],
                "frozen product default profile changed")
        shipping_js = [work for work in product["workloads"]
                       if work["kind"] == "js" and work["profile"] == "default"]
        require(len(shipping_js) == 1 and
                shipping_js[0]["runtime_accounting"].get("candidate") is False,
                "require the final shipping-accounting-disabled product snapshot")
        for name, expected in product["immutable_files"].items():
            require(Path(name).is_file() and digest(name) == expected,
                    "frozen product artifact changed: " + name)
        self.clang = str(Path(product["clang"]["path"]).resolve())
        require(digest(self.clang) == product["clang"]["sha256"], "frozen clang changed")
        self.manifest["clang"] = product["clang"]
        source_runtime = source_manifest_path.parent / "candidate-runtime"
        source_hashes = {}
        for path in sorted(source_runtime.rglob("*")):
            if not path.is_file():
                continue
            expected = product["immutable_files"].get(str(path))
            require(expected is not None and digest(path) == expected,
                    "candidate runtime file absent from frozen product identity: " + str(path))
            source_hashes[str(path.relative_to(source_runtime))] = expected
        require(len(source_hashes) > 15, "missing frozen candidate runtime tree")
        for name, expected in FROZEN_HEADERS.items():
            require(source_hashes.get(name) == expected, "candidate is not frozen 7b: " + name)
        self.manifest["product_input"] = {
            "manifest": str(source_manifest_path), "manifest_sha256": digest(source_manifest_path),
            "runtime": str(source_runtime), "runtime_sha256": source_hashes,
            "shipping_default_js_runtime": shipping_js[0]["runtime_objects"]["candidate"],
        }
        # Copy recipes and counter implementation before producing any objects.
        for name in ("build.py", "measure.py", "workload.c", "runtime-helpers.inc"):
            shutil.copy2(HERE / name, self.out / name)
        shutil.copy2(product["counter_runner"], self.out / "frames-instructions.py")
        require(digest(self.out / "frames-instructions.py") == product["immutable_files"].get(product["counter_runner"]),
                "counter runner is not frozen by the complete product manifest")
        self.manifest.update({"counter_runner": str(self.out / "frames-instructions.py"),
                              "measurement_script": str(self.out / "measure.py")})
        for role in ("baseline", "candidate"):
            tree = self.out / (role + "-runtime")
            shutil.copytree(source_runtime, tree)
            require({str(path.relative_to(tree)): digest(path) for path in tree.rglob("*") if path.is_file()} == source_hashes,
                    "runtime snapshot copy differs: " + role)
        header = self.out / "baseline-runtime/minyar_cycle_bounded_rc.h"
        source = header.read_text()
        require(source.count(BEGIN) == 1 and source.count(END) == 1, "batch markers are not unique")
        begin, end = source.index(BEGIN), source.index(END) + len(END)
        require(begin < end and source.count("rc_pending_count <= pending") == 2,
                "frozen V2 owner batching body changed")
        (self.out / "removed-batching.c.fragment").write_text(source[begin:end])
        header.write_text(source[:begin] + source[end:])
        differences = [name for name in source_hashes
                       if digest(self.out / "baseline-runtime" / name) != source_hashes[name]]
        require(differences == ["minyar_cycle_bounded_rc.h"], "runtime ablation touched another file")
        self.manifest["runtime_ablation"] = {
            "baseline": "cache-only frozen 7b; exact marked cycle owner batching block removed",
            "candidate": "complete product frozen 7b candidate, byte-identical runtime tree",
            "changed_files": differences, "removed_block_sha256": digest(self.out / "removed-batching.c.fragment"),
        }
        common_object = self.object(self.out / "workload.c", self.out / "workload.o", ["-std=c11"])
        binaries = {}
        for role in ("baseline", "candidate"):
            tree = self.out / (role + "-runtime")
            engine = cycle_source((tree / "minyar_runtime.c").read_text())
            for ownership in (False, True):
                label = role + ("-ownership" if ownership else "-shipping")
                wrapper = self.out / (label + "-runtime.c")
                prefix = '#define MINYAR_RC_TESTING 1\n' if ownership else ''
                prefix += '#define MINYAR_SYSTEM_HEAP 1\n#define MINYAR_RC_POLL_BUDGET 32\n'
                wrapper.write_text(prefix + engine + '\n#include "minyar_stack_frames.h"\n' +
                                   (self.out / "runtime-helpers.inc").read_text())
                runtime_object = self.object(wrapper, self.out / (label + "-runtime.o"),
                                             ["-std=c11", "-fvisibility=hidden", "-iquote", tree])
                binary = self.out / label
                self.run([self.clang, *FLAGS, common_object, runtime_object, "-lm", "-pthread", "-ldl", "-o", binary], label + "-link")
                binaries[(role, ownership)] = binary
                self.manifest["runtime_accounting"][str(runtime_object)] = {
                    "role": role, "enabled": ownership, "measured": not ownership,
                    "purpose": "unmeasured same-native-object ownership proof" if ownership else "shipping accounting disabled",
                    "wrapper": str(wrapper), "wrapper_sha256": digest(wrapper),
                    "object_sha256": digest(runtime_object),
                    "flags": [*FLAGS, "-std=c11", "-fvisibility=hidden", "-iquote", str(tree)],
                }
                self.checkpoint()
        for active in ("inactive", "active"):
            for owner in ("frame", "chunk"):
                for role in ("baseline", "candidate"):
                    outputs = []
                    for ownership in (False, True):
                        stdout, stderr = self.run([binaries[(role, ownership)], active, owner, "32"],
                                                  role + "-" + active + "-" + owner + ("-proof" if ownership else "-check"), timeout=60)
                        require(not stderr and stdout == b"32640\n", "32-frame independent checksum/diagnostic oracle failed")
                        outputs.append(stdout)
                    require(outputs[0] == outputs[1], "shipping and ownership stdout differ")
                    self.manifest["checks"].append({"role": role, "activation": active, "owner": owner,
                        "iterations": 32, "stdout": outputs[0].decode(), "exact_stdout_equal": True,
                        "shared_object_sha256": digest(common_object), "instrumented_check_measured": False})
                count = 8 * self.args.iterations
                self.manifest["workloads"].append({
                    "id": "owners-" + active + "-" + owner, "kind": "native", "profile": "default",
                    "activation": active, "owner": owner, "units": self.args.iterations, "owners": count,
                    "expected_stdout": str(count * (count - 1) // 2) + "\n",
                    "roles": {role: [str(binaries[(role, False)]), active, owner, str(self.args.iterations)]
                              for role in ("baseline", "candidate")},
                    "shared_object": str(common_object), "shared_object_sha256": digest(common_object),
                    "runtime_accounting": {"baseline": False, "candidate": False},
                })
        self.manifest["immutable_files"] = {str(path): digest(path) for path in sorted(self.out.rglob("*"))
            if path.is_file() and "logs" not in path.relative_to(self.out).parts
            and path.name not in ("manifest.json", "manifest.json.pending")}
        self.manifest["status"] = "ready"
        self.checkpoint()
        print("CYCLE_OWNER_STUDY_READY", self.out / "manifest.json", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/perfcs-cycle-owner-study"))
    parser.add_argument("--iterations", type=int, default=200000)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("build and run only through bx perfcs on Linux x86_64")
    require(1 <= args.iterations <= 10000000, "iterations must be in 1..10000000")
    builder = None
    try:
        builder = Builder(args)
        builder.build()
    except BaseException as error:
        if builder is not None:
            builder.manifest.update({"status": "failed", "error": repr(error)})
            builder.checkpoint()
        raise


if __name__ == "__main__":
    main()
