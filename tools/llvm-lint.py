#!/usr/bin/env python3
"""Run LLVM's IR verifier and Lint pass over the IR the compiler emits.

  tools/llvm-lint.py [--work DIR] [--keep] PROGRAM.min...

Each program is compiled as `./minyar --release` compiles it, linked with the
release runtime IR (so every call into the runtime is checked against the C
definition it reaches), and checked twice: as emitted and after the O2
pipeline. A Lint report of undefined behaviour, or a verifier error, fails the
check. Lint sees what we claim to LLVM: call-site and definition signatures and
ABI attributes (zeroext, signext), alignment against the data layout, loads
and stores through null or undef pointers, and unreachable code that the
optimizer proved reachable. These are the claims a wrong attribute turns into
a miscompile, so they are checked on every program rather than reviewed by eye.

LLVM tools come from MINYAR_LLVM_BIN, else from the directory of the pinned
Clang (tools/toolchain.sh toolchain). The compiler is build/minyarc and the
runtime build/minyar-default-runtime-release.ll unless MINYAR_COMPILER and
MINYAR_LINT_RUNTIME name others.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

MISALIGNED = "Undefined behavior: Memory reference address is misaligned"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def llvm_bin():
    chosen = os.environ.get("MINYAR_LLVM_BIN")
    if chosen:
        return chosen
    clang = subprocess.run(["sh", os.path.join(ROOT, "tools/toolchain.sh"), "toolchain"],
                           check=True, capture_output=True, text=True).stdout.strip()
    return os.path.dirname(os.path.realpath(clang))


def run(command):
    return subprocess.run(command, capture_output=True, text=True)


def findings(stderr):
    """Lint and verifier reports: a message line followed by indented IR lines."""
    reports = []
    current = None
    for line in stderr.splitlines():
        if line.startswith("Undefined behavior:") or "input module is broken" in line or line.startswith("Broken module"):
            current = [line]
            reports.append(current)
        elif current is not None and line.startswith("  "):
            current.append(line)
        else:
            current = None
    return reports


def harmless_extension(report):
    """A call site that extends a narrow integer argument the C definition does not ask to be extended.

    Minyar's IR is target-independent, so a Boolean argument to C is always passed `i1 zeroext`: Darwin's and the
    x86-64 System V C ABIs require the caller to extend it, AAPCS64 (Linux on ARM) does not, and Clang marks the
    definition accordingly. Extending when the callee does not rely on it is harmless; the opposite (the definition
    relies on an extension the call site does not promise) is the real error and is still reported."""
    match = re.match(r"Undefined behavior: ABI attribute (zeroext|signext) not present on both function and call-site", report[0])
    if not match or len(report) < 2:
        return False
    call = re.search(r"@[^(\s]+\((.*)\)", report[1])
    if not call:
        return False
    arguments = call.group(1)
    narrow = len(re.findall(r"\bi(?:1|8|16) ", arguments))
    extended = len(re.findall(r"\bi(?:1|8|16) (?:noundef )?" + match.group(1) + r"\b", arguments))
    return narrow > 0 and narrow == extended


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("programs", nargs="+")
    options = parser.parse_args()
    tools = llvm_bin()
    opt, link = os.path.join(tools, "opt"), os.path.join(tools, "llvm-link")
    for tool in (opt, link):
        if not os.access(tool, os.X_OK):
            sys.exit(f"llvm-lint: {tool} is missing; set MINYAR_LLVM_BIN to the LLVM 23 bin directory")
    compiler = os.environ.get("MINYAR_COMPILER", os.path.join(ROOT, "build/minyarc"))
    runtime = os.environ.get("MINYAR_LINT_RUNTIME", os.path.join(ROOT, "build/minyar-default-runtime-release.ll"))
    work = options.work or tempfile.mkdtemp(prefix="minyar-llvm-lint-")
    os.makedirs(work, exist_ok=True)
    libraries = ["--library", os.path.join(ROOT, "library")]
    if sys.platform == "darwin":
        libraries = ["--library", os.path.join(ROOT, "library/platform/macos")] + libraries
    failed = 0
    seen = set()
    for index, program in enumerate(options.programs):
        stem = f"{index}-{os.path.splitext(os.path.basename(program))[0]}"
        emitted = os.path.join(work, stem + ".ll")
        linked = os.path.join(work, stem + ".linked.bc")
        compiled = run([compiler, program, emitted, "--release", "--scope-owners", "--bounded-owners", "32"] + libraries)
        if compiled.returncode:
            print(f"FAIL {program}: does not compile\n{compiled.stderr}")
            failed += 1
            continue
        joined = run([link, emitted, runtime, "-o", linked])
        if joined.returncode:
            print(f"FAIL {program}: llvm-link\n{joined.stderr}")
            failed += 1
            continue
        reports = []
        for label, passes in (("emitted", "verify,lint"), ("O2", "default<O2>,verify,lint")):
            checked = run([opt, "-passes=" + passes, "-disable-output", linked])
            for report in findings(checked.stderr):
                # After O2 every alignment is LLVM's own: InstCombine raises accesses to a global without an
                # explicit alignment up to the target's preferred alignment (16 for globals of 16 bytes or more),
                # which code generation also gives the global, while Lint measures them against the ABI
                # alignment. Our own alignment claims are the emitted ones, checked above.
                if label == "O2" and report[0] == MISALIGNED:
                    continue
                if harmless_extension(report):
                    continue
                reports.append((label, report))
            if checked.returncode:
                reports.append((label, [f"opt exited with {checked.returncode}", checked.stderr[-2000:]]))
        for label, report in reports:
            key = (label, "\n".join(report))
            first = key not in seen
            seen.add(key)
            print(f"FAIL {program} ({label}): " + ("\n".join(report) if first else report[0] + " (as above)"))
        if reports:
            failed += 1
        else:
            print(f"ok   {program}")
    if not options.keep and not options.work:
        shutil.rmtree(work, ignore_errors=True)
    print(f"llvm-lint: {len(options.programs) - failed} of {len(options.programs)} programs clean")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
