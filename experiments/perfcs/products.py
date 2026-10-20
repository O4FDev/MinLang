#!/usr/bin/env python3
"""Build frozen same-LLVM/runtime-only product pairs ON bx perfcs, never macOS.

python3 experiments/perfcs/products.py --compiler build/minyarc
sudo -n python3 build/perfcs-products/measure-products.py --manifest build/perfcs-products/manifest.json
New output directories only. This is a focused O2 runtime experiment, not full
product qualification, sanitizer coverage, or a comparison of compiler changes.
Measured JS/jsmn runtimes disable ownership accounting; separate instrumented
links prove cleanup. Safelibs retains accounting required by its frozen API.
"""
from __future__ import annotations

import argparse
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PROFILES = {"default": ["--bounded-owners", "32"], "eager": ["--scope-owners"]}
MODES = {"default": [], "strict": ["-DJSMN_STRICT=1"],
         "links": ["-DJSMN_PARENT_LINKS=1"],
         "strict_links": ["-DJSMN_STRICT=1", "-DJSMN_PARENT_LINKS=1"]}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    pending.replace(path)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def copy_tree(source, target):
    require(source.is_dir(), "missing frozen input: " + str(source))
    shutil.copytree(source, target, symlinks=True,
                    ignore=shutil.ignore_patterns("build", ".git", "__pycache__", "*.pyc"))


def cycle_source(source):
    # Exact tools/test-runtime.min cycleSource transformation, with its guards.
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


def native_library(clang, name, override):
    if override:
        path = Path(override).resolve()
    else:
        soname = ctypes.util.find_library(name)
        require(soname, "missing native library " + name + "; supply --lib" + name)
        found = subprocess.check_output([clang, "-print-file-name=" + soname], text=True).strip()
        path = Path(found)
        if not path.is_file():
            choices = [Path(base) / soname for base in
                       ("/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/lib")]
            path = next((item for item in choices if item.is_file()), path)
        path = path.resolve()
    require(path.is_file(), "cannot locate native library: " + str(path))
    return path


class Builder:
    def __init__(self, args):
        self.args = args
        self.out = args.output.resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        (self.out / "logs").mkdir()
        self.manifest = {"schema": 1, "status": "building", "commands": [], "workloads": [],
                         "checks": [], "runtime_accounting": {},
                         "profiles": {p: PROFILES[p] for p in args.profiles},
                         "method": "same generated LLVM/object and native objects within each profile; separate O2 runtime objects; no LTO",
                         "ownership_checks": "separate instrumented JS/jsmn links drain and assert normal-exit ownership; measured JS/jsmn accounting disabled; frozen safelibs live-object API requires instrumented measurements",
                         "qualification": "focused frozen product checks only; no claim of full product qualification, O0, sanitizer or product-HEAD coverage"}
        self.clang = args.clang if args.clang else self.run(
            ["sh", "tools/toolchain.sh", "default-clang"], "select-clang", cwd=ROOT).strip()
        self.clang = shutil.which(self.clang) or self.clang
        self.clang = str(Path(self.clang).resolve())
        self.flags = ["-O2", "-g", "-fPIC", "-fno-omit-frame-pointer", "-Wno-override-module"]

    def checkpoint(self):
        save(self.out / "manifest.json", self.manifest)

    def run(self, command, label, timeout=600, cwd=None):
        command = list(map(str, command))
        index = len(self.manifest["commands"])
        stem = self.out / "logs" / (f"{index:04d}-" + label)
        row = {"argv": command, "cwd": str(cwd or ROOT), "timeout_seconds": timeout,
               "stdout_path": str(stem) + ".stdout", "stderr_path": str(stem) + ".stderr"}
        self.manifest["commands"].append(row)
        self.checkpoint()
        print("BUILD", label, flush=True)
        began = time.monotonic()
        try:
            result = subprocess.run(command, cwd=cwd or ROOT, capture_output=True, timeout=timeout)
            stdout, stderr, status = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, status = error.stdout or b"", error.stderr or b"", 124
        Path(row["stdout_path"]).write_bytes(stdout)
        Path(row["stderr_path"]).write_bytes(stderr)
        row.update({"exit": status, "wall_seconds": time.monotonic() - began,
                    "stdout_sha256": digest(row["stdout_path"]), "stderr_sha256": digest(row["stderr_path"])})
        self.checkpoint()
        require(status == 0, f"{label}: exit {status}; raw logs retained at {stem}")
        return stdout.decode()

    def object(self, source, target, extra=()):
        self.run([self.clang, *self.flags, *extra, "-c", source, "-o", target], target.stem)
        return target

    def link(self, objects, target, extra=()):
        self.run([self.clang, *self.flags, *objects, *extra, "-o", target], target.name)
        return target

    def llvm(self, source, stem, profile):
        raw = stem.with_suffix(".raw.ll")
        self.run([self.compiler, source, raw, "--library", self.library, *PROFILES[profile]], stem.name + "-emit")
        return raw

    def runtime(self, role, profile, kind, ownership=False):
        tree = self.out / (role + "-runtime")
        target = self.out / (kind + "-" + profile + "-" + role +
                             ("-ownership-runtime.o" if ownership else "-runtime.o"))
        wrapper = target.with_suffix(".c")
        accounting = ownership or kind == "safelibs"
        prefix = '#define MINYAR_RC_TESTING 1\n' if accounting else ''
        if profile == "default":
            prefix += '#define MINYAR_SYSTEM_HEAP 1\n#define MINYAR_RC_POLL_BUDGET 32\n'
        if kind == "js":
            engine = cycle_source((tree / "minyar_runtime.c").read_text())
            content = prefix + engine + '\n#include "minyar_stack_frames.h"\n'
        elif kind == "safelibs":
            old = (self.inputs / "safelibs/native/runtime.c").read_text()
            require(old.count('#include "minyar_runtime.c"') == 1, "unexpected safelibs wrapper")
            content = prefix + old + '\n#include "minyar_stack_frames.h"\n'
        else:
            old = (self.inputs / "c2min/recipes/jsmn/runtime.c.in").read_text()
            require(old.count('#include "minyar_default_runtime.c"') == 1, "unexpected jsmn wrapper")
            content = prefix + old.replace('#include "minyar_default_runtime.c"',
                '#include "minyar_runtime.c"\n#include "minyar_stack_frames.h"')
            # The frozen C adapter polls after releasing both copied buffers.
            # Ordinary eager release has already drained all aggregate debt.
            # Supply that adapter ABI for both accounting variants/roles.
            content += ('\n#ifndef MINYAR_BOUNDED_RC\n'
                        'size_t minyar_rc_poll(size_t budget) { (void)budget; return 0; }\n'
                        '#endif\n')
        if ownership:
            content += '''
/* Test-only cleanup oracle. Never part of a measured JS/jsmn runtime. */
#ifndef MINYAR_COMPILER_ARENA
#include <assert.h>
__attribute__((destructor)) static void perfcs_check_ownership(void) {
    assert(rc_frames == NULL && rc_scopes == NULL);
#ifdef MINYAR_BOUNDED_RC
    while (rc_pending_count) assert(minyar_rc_poll(MINYAR_RC_POLL_BUDGET) > 0);
#else
    minyar_rc_release(NULL);
#endif
    assert(rc_frames == NULL && rc_scopes == NULL);
    assert(rc_pending_count == 0);
    assert(rc_object_count == rc_immortal_object_count);
}
#endif
'''
        wrapper.write_text(content)
        self.object(wrapper, target, ["-std=c11", "-fvisibility=hidden", "-iquote", str(tree)])
        self.manifest["runtime_accounting"][str(target)] = {
            "role": role, "profile": profile, "kind": kind,
            "enabled": accounting, "ownership_check": ownership,
            "purpose": ("unmeasured instrumented ownership proof" if ownership else
                        "instrumented frozen safelibs live-object API" if kind == "safelibs" else
                        "shipping runtime with ownership accounting disabled"),
            "wrapper": str(wrapper), "wrapper_sha256": digest(wrapper),
            "object_sha256": digest(target),
            "compile_flags": [*self.flags, "-std=c11", "-fvisibility=hidden", "-iquote", str(tree)],
            "eager_poll_compatibility": kind == "jsmn" and profile == "eager",
        }
        self.checkpoint()
        return target

    def workload(self, identity, kind, profile, roles, **extra):
        self.manifest["workloads"].append({"id": identity, "kind": kind, "profile": profile,
                                            "roles": {key: list(map(str, value)) for key, value in roles.items()}, **extra})
        self.checkpoint()

    def js(self):
        source = self.inputs / "js/bench/create-probe.min"
        require("let count = 20" in source.read_text(), "JS probe no longer has 20 realms")
        # Same native objects in both links. They cover files/system imports if
        # the frozen module graph includes unused exported methods as well.
        natives = [self.object(self.out / "baseline-runtime/native" / (name + ".c"),
                              self.out / ("js-native-" + name + ".o"), ["-std=c11"])
                   for name in ("files", "system")]
        for profile in self.args.profiles:
            raw = self.llvm(source, self.out / ("js-" + profile), profile)
            obj = self.object(raw, self.out / ("js-" + profile + ".o"))
            roles, runtime_objects, expected_output = {}, {}, None
            for role in ("baseline", "candidate"):
                runtime = self.runtime(role, profile, "js")
                binary = self.link([obj, *natives, runtime], self.out / ("js-" + profile + "-" + role),
                                   ["-lm", "-pthread", "-ldl"])
                ownership_runtime = self.runtime(role, profile, "js", ownership=True)
                proof = self.link([obj, *natives, ownership_runtime],
                                  self.out / ("js-" + profile + "-" + role + "-ownership"),
                                  ["-lm", "-pthread", "-ldl"])
                output = self.run([binary], binary.name + "-shipping-check", timeout=180)
                checked_output = self.run([proof], proof.name + "-check", timeout=180)
                require(re.fullmatch(r"[0-9]+\n", output) is not None and int(output) > 0,
                        "JS ownership proof needs the frozen live checksum")
                require(checked_output == output, "JS ownership runtime changed exact stdout: " + role + "/" + profile)
                if expected_output is not None:
                    require(output == expected_output, "JS baseline/candidate exact stdout differs: " + profile)
                expected_output = output
                self.manifest["checks"].append({
                    "kind": "js-ownership", "profile": profile, "role": role, "measured": False,
                    "shipping_binary": str(binary), "ownership_binary": str(proof),
                    "runtime_accounting": {"shipping": False, "ownership": True},
                    "runtime_objects": {"shipping": str(runtime), "ownership": str(ownership_runtime)},
                    "stdout_sha256": hashlib.sha256(output.encode()).hexdigest(),
                    "ownership_stdout_sha256": hashlib.sha256(checked_output.encode()).hexdigest(),
                    "exact_stdout_equal": True, "shared_object_sha256": digest(obj),
                    "shared_native_objects": {str(path): digest(path) for path in natives},
                })
                self.checkpoint()
                roles[role] = [binary]
                runtime_objects[role] = str(runtime)
            self.workload("js-create-" + profile, "js", profile, roles, units=20,
                          llvm_sha256=digest(raw), shared_object_sha256=digest(obj),
                          runtime_accounting={role: False for role in roles}, runtime_objects=runtime_objects,
                          accounting_note="shipping accounting-disabled runtimes; separate same-object ownership proof")

    def safelibs(self):
        product = self.inputs / "safelibs"
        fixture_root = self.inputs / "safelibs-tools/fixtures"
        fixture_manifest = json.loads((fixture_root / "manifest.json").read_text())["workloads"]
        refs = {name: native_library(self.clang, lib, getattr(self.args, option))
                for name, lib, option in (("zlib", "z", "libz"), ("png", "png16", "libpng"),
                                          ("jpeg", "turbojpeg", "libjpeg"))}
        self.manifest["native_references"] = {name: {"path": str(path), "sha256": digest(path)} for name, path in refs.items()}
        worker = self.link([self.inputs / "safelibs-tools/benchmark.c"], self.out / "safelibs-worker", ["-ldl"])
        native = [self.object(product / "native" / (name + ".c"), self.out / ("safelibs-" + name + ".o"),
                              ["-std=c11", "-fvisibility=default"]) for name in ("bridge", "turbo")]
        for profile in self.args.profiles:
            raw = self.llvm(product / "src/entry.min", self.out / ("safelibs-" + profile), profile)
            llvm = self.out / ("safelibs-" + profile + ".ll")
            self.run([sys.executable, product / "scripts/prepare-llvm.py", raw, llvm], "safelibs-prepare-" + profile)
            obj = self.object(llvm, self.out / ("safelibs-" + profile + ".o"))
            libraries, runtime_objects = {}, {}
            for role in ("baseline", "candidate"):
                runtime = self.runtime(role, profile, "safelibs")
                library = self.out / ("safelibs-" + profile + "-" + role + ".so")
                self.link([obj, *native, runtime], library,
                          ["-shared", "-Wl,--no-undefined", "-Wl,--version-script=" + str(product / "native/exports.map"),
                           "-Wl,-Bsymbolic", "-pthread", "-lm", "-ldl"])
                libraries[role] = library
                runtime_objects[role] = str(runtime)
            for codec, iterations in (("zlib", 64), ("png", 32), ("jpeg", 16)):
                fixture = fixture_root / (codec + "-large.bin")
                expected = fixture_root / (codec + "-large.raw")
                require(fixture.is_file() and expected.is_file(), "missing frozen codec fixture " + codec)
                frozen = fixture_manifest[codec + "-large"]
                require(digest(fixture) == frozen["fixture_sha256"] and digest(expected) == frozen["expected_sha256"], "frozen codec fixture identity changed: " + codec)
                width, height = frozen["width"], frozen["height"]
                common = ["--zlib", refs["zlib"], "--png", refs["png"], "--jpeg", refs["jpeg"],
                          "--codec", codec, "--impl", "candidate", "--iterations", iterations,
                          "--fixture", fixture, "--expected", expected, "--width", width, "--height", height]
                roles = {role: [worker, "--candidate", library, *common] for role, library in libraries.items()}
                self.workload("safelibs-" + codec + "-" + profile, "safelibs", profile, roles,
                              units=iterations, codec=codec, libraries={key: str(value) for key, value in libraries.items()},
                              fixture=str(fixture), expected=str(expected), width=width, height=height,
                              llvm_sha256=digest(llvm), shared_object_sha256=digest(obj),
                              runtime_accounting={role: True for role in libraries}, runtime_objects=runtime_objects,
                              accounting_note="instrumented measurement required by frozen safelibs_runtime_live API")

    def jsmn(self):
        product = self.inputs / "c2min"
        header = product / "vendor/jsmn/jsmn.h"
        pins = re.findall(r'^JSMN_SHA = "([0-9a-f]{64})"$', (product / "tools/c2min.py").read_text(), re.M)
        require(len(pins) == 1 and digest(header) == pins[0], "frozen jsmn upstream pin mismatch")
        self.manifest["jsmn_recipe"] = "frozen reviewed v1; direct recipe extraction, not requalification of the migration system"
        include = ["-std=c11", "-I", str(product / "vendor/jsmn")]
        references, adapter = {}, {}
        for mode, defines in MODES.items():
            adapter[mode] = self.object(product / "recipes/jsmn/adapter.c", self.out / ("jsmn-adapter-" + mode + ".o"), [*include, *defines])
            reference = self.link([product / "vendor/jsmn/test/tests.c"], self.out / ("jsmn-reference-upstream-" + mode), [*include, *defines])
            references[mode] = self.run([reference], "jsmn-reference-check-" + mode, timeout=180)
        client = self.object(product / "tests/benchmark.c", self.out / "jsmn-benchmark.o", include)
        cclient = self.object(product / "tests/benchmark.c", self.out / "jsmn-reference-benchmark.o", [*include, "-DC2MIN_REFERENCE=1"])
        reference_bench = self.link([cclient], self.out / "jsmn-reference-benchmark", ["-lm", "-pthread"])
        for profile in self.args.profiles:
            raw = self.llvm(product / "recipes/jsmn/tokenizer.min", self.out / ("jsmn-" + profile), profile)
            llvm = self.out / ("jsmn-" + profile + ".ll")
            text = raw.read_text()
            entries = re.findall(r'^define i64 @([^ (]*c2minJsmn)\(ptr [^,]*, ptr [^,]*, i64 [^)]*\)', text, re.M)
            require(len(entries) == 1, "expected one c2minJsmn entry, got " + repr(entries))
            text = text.replace("@" + entries[0] + "(", "@.minyar.fn.c2minJsmn(")
            require(text.count("define i32 @main(") == 1, "expected one jsmn main")
            text = re.sub(r'@main(?=[\s,(])', "@c2min_unused_main", text)
            llvm.write_text(text)
            obj = self.object(llvm, self.out / ("jsmn-" + profile + ".o"))
            binaries, runtime_objects = {}, {}
            for role in ("baseline", "candidate"):
                runtime = self.runtime(role, profile, "jsmn")
                ownership_runtime = self.runtime(role, profile, "jsmn", ownership=True)
                for mode, defines in MODES.items():
                    objects = [obj, ownership_runtime, adapter[mode]]
                    for label, source, extra in (
                        ("upstream", product / "vendor/jsmn/test/tests.c", ["-DJSMN_HEADER=1"]),
                        ("compatibility", product / "tests/compatibility.c", []),
                        ("threads", product / "tests/threads.c", ["-DJSMN_HEADER=1"])):
                        binary = self.link([source, *objects], self.out / ("jsmn-" + profile + "-" + role + "-" + mode + "-" + label),
                                           [*include, *defines, *extra, "-lm", "-pthread"])
                        output = self.run([binary], binary.name + "-check", timeout=180)
                        if label == "upstream":
                            require(output == references[mode], "jsmn upstream output differs from C")
                        self.manifest["checks"].append({"kind": "jsmn-" + label, "profile": profile,
                                                        "role": role, "mode": mode, "measured": False,
                                                        "runtime_accounting": True,
                                                        "runtime_object": str(ownership_runtime),
                                                        "shared_object_sha256": digest(obj),
                                                        "shared_adapter_sha256": digest(adapter[mode]),
                                                        "stdout_sha256": hashlib.sha256(output.encode()).hexdigest()})
                        self.checkpoint()
                binaries[role] = self.link([client, obj, runtime, adapter["default"]], self.out / ("jsmn-" + profile + "-" + role + "-benchmark"), ["-lm", "-pthread"])
                runtime_objects[role] = str(runtime)
            for count, repeats in ((16, 200000), (1024, 2000), (16384, 200)):
                roles = {role: [binary, count, repeats] for role, binary in binaries.items()}
                roles["reference"] = [reference_bench, count, repeats]
                self.workload("jsmn-" + str(count) + "-" + profile, "jsmn", profile, roles,
                              count=count, units=repeats, llvm_sha256=digest(llvm), shared_object_sha256=digest(obj),
                              runtime_accounting={role: False for role in roles}, runtime_objects=runtime_objects,
                              accounting_note="shipping accounting-disabled benchmarks; separate instrumented upstream/compatibility/thread checks")

    def build(self):
        require(platform.system() == "Linux" and platform.machine() == "x86_64", "build only on Linux x86_64 bx perfcs")
        self.inputs = self.out / "inputs"
        self.inputs.mkdir()
        names = {"js": ["js"], "safelibs": ["safelibs", "safelibs-tools"], "jsmn": ["c2min"]}
        for name in sorted({name for work in self.args.workloads for name in names[work]}):
            copy_tree(self.args.input_root / name, self.inputs / name)
        for role, source in (("baseline", self.args.baseline_runtime), ("candidate", self.args.candidate_runtime)):
            copy_tree(source, self.out / (role + "-runtime"))
        self.library = self.out / "library"
        copy_tree(self.args.library, self.library)
        self.compiler = self.out / "minyarc"
        shutil.copy2(self.args.compiler.resolve(), self.compiler)
        shutil.copy2(ROOT / "experiments/memory/frames-instructions.py", self.out / "frames-instructions.py")
        shutil.copy2(Path(__file__).with_name("measure-products.py"), self.out / "measure-products.py")
        shutil.copy2(Path(__file__), self.out / "products.py")
        shutil.copy2(ROOT / "tools/test-runtime.min", self.out / "cycle-transform.min")
        self.manifest.update({"host": {"kernel": platform.release(), "machine": platform.machine()},
                              "clang": {"path": self.clang, "sha256": digest(self.clang),
                                        "version": self.run([self.clang, "--version"], "clang-version")},
                              "flags": self.flags, "compiler_sha256": digest(self.compiler),
                              "counter_runner": str(self.out / "frames-instructions.py"),
                              "measurement_script": str(self.out / "measure-products.py")})
        for work in self.args.workloads:
            getattr(self, work)()
        self.manifest["immutable_files"] = {str(path): digest(path) for path in sorted(self.out.rglob("*"))
            if path.is_file() and "logs" not in path.relative_to(self.out).parts
            and path not in (self.out / "manifest.json", self.out / "manifest.json.pending")}
        self.manifest["status"] = "ready"
        self.checkpoint()
        print("PRODUCTS_READY", self.out / "manifest.json", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/perfcs-products")
    parser.add_argument("--compiler", type=Path, default=ROOT / "build/minyarc")
    parser.add_argument("--input-root", type=Path, default=ROOT / ".perfcs",
                        help="frozen js/safelibs/safelibs-tools/c2min source snapshots")
    parser.add_argument("--library", type=Path, default=ROOT / "library")
    parser.add_argument("--baseline-runtime", type=Path, default=ROOT / ".perfcs/baseline-runtime")
    parser.add_argument("--candidate-runtime", type=Path, default=ROOT / "runtime")
    parser.add_argument("--clang")
    parser.add_argument("--workloads", nargs="+", choices=["js", "safelibs", "jsmn"], default=["js", "safelibs", "jsmn"])
    parser.add_argument("--profiles", nargs="+", choices=list(PROFILES), default=list(PROFILES))
    parser.add_argument("--libz")
    parser.add_argument("--libpng")
    parser.add_argument("--libjpeg")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("build only through bx perfcs on Linux x86_64")
    require(len(set(args.workloads)) == len(args.workloads) and len(set(args.profiles)) == len(args.profiles), "duplicate workload/profile selection")
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
