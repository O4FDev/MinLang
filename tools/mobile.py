#!/usr/bin/env python3
"""Build target-isolated UIKit apps and Android NDK core archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("ios-simulator", "ios-device", "android-arm64", "android-x86_64")


class MobileError(Exception):
    pass


def run(command: list[str], *, capture: bool = False) -> str:
    command = [str(word) for word in command]
    print("+ " + shlex.join(command), file=sys.stderr, flush=True)
    try:
        result = subprocess.run(command, cwd=ROOT, check=True, text=True,
                                stdout=subprocess.PIPE if capture else None,
                                timeout=900)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise MobileError(str(error)) from error
    return result.stdout.strip() if capture else ""


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("source", type=Path)
    result.add_argument("--target", choices=TARGETS, required=True)
    result.add_argument("-o", "--output", type=Path)
    result.add_argument("--name", default="Minyar")
    result.add_argument("--identifier", default="org.minyar.hello")
    result.add_argument("--arch", choices=("arm64", "x86_64"))
    result.add_argument("--minimum-ios", default="16.0")
    result.add_argument("--api", type=int, default=28)
    result.add_argument("--ndk", type=Path, help="Android NDK root; defaults to ANDROID_NDK_HOME")
    result.add_argument("--library", type=Path, action="append", default=[])
    result.add_argument("--debug", action="store_true", help="compile target code at O0 (default O2)")
    result.add_argument("--no-bootstrap", action="store_true", help="use already built host compiler and runtime generator output")
    return result


def validate(args: argparse.Namespace) -> None:
    args.source = args.source.resolve()
    if not args.source.is_file():
        raise MobileError(f"cannot read source: {args.source}")
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", args.identifier):
        raise MobileError("bundle identifier needs at least two dot-separated ASCII names")
    if not args.name or any(ord(char) < 32 for char in args.name):
        raise MobileError("application name must be nonempty and contain no control characters")
    if not re.fullmatch(r"\d{1,2}\.\d{1,2}(?:\.\d{1,2})?", args.minimum_ios) or int(args.minimum_ios.split(".")[0]) < 16:
        raise MobileError("the minimum iOS version must be 16.0 or later")
    if args.api < 28 or args.api > 999:
        raise MobileError("Android API must be between 28 and 999; the runtime uses getrandom")
    if args.arch and args.target != "ios-simulator":
        raise MobileError("--arch applies only to ios-simulator; other targets fix their architecture")
    args.library = [path.resolve() for path in args.library]
    for path in args.library:
        if not path.is_dir():
            raise MobileError(f"library directory does not exist: {path}")
    suffix = ".app" if args.target.startswith("ios-") else ".a"
    default = "Minyar.app" if suffix == ".app" else "libminyar-app.a"
    args.output = (args.output or ROOT / "build" / "mobile" / args.target / default).absolute()
    if args.output.suffix != suffix:
        raise MobileError(f"{args.target} output must end in {suffix}")
    if args.output.is_symlink():
        raise MobileError("refusing to replace a symbolic-link output")
    destination = args.output.resolve()
    if destination == args.source or destination in args.source.parents:
        raise MobileError("the output must not contain or replace the source")
    if suffix == ".app" and args.output.exists() and not (args.output / "minyar-build.json").is_file():
        raise MobileError("refusing to replace an application not built by this tool")
    if suffix == ".a":
        args.metadata = args.output.with_suffix(".a.json")
        if args.metadata.is_symlink() or args.metadata.resolve() == args.source:
            raise MobileError("the archive metadata must not link to or replace the source")
        if args.metadata.exists():
            try:
                prior = json.loads(args.metadata.read_text())
            except (OSError, ValueError) as error:
                raise MobileError("refusing to replace unrelated archive metadata") from error
            if not isinstance(prior, dict) or prior.get("schema") != 1 or prior.get("target") != args.target:
                raise MobileError("refusing to replace unrelated archive metadata")


def apple_tools(args: argparse.Namespace) -> dict:
    if platform.system() != "Darwin":
        raise MobileError("iOS targets require macOS and a full Xcode installation")
    simulator = args.target == "ios-simulator"
    sdk_name = "iphonesimulator" if simulator else "iphoneos"
    sdk = run(["xcrun", "--sdk", sdk_name, "--show-sdk-path"], capture=True)
    if not Path(sdk).is_dir():
        raise MobileError(f"Xcode SDK does not exist: {sdk}")
    clang = run(["sh", str(ROOT / "tools" / "toolchain.sh"), "default-clang"], capture=True)
    arch = (args.arch or ("arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64")) if simulator else "arm64"
    triple = f"{arch}-apple-ios{args.minimum_ios}" + ("-simulator" if simulator else "")
    linker = run(["xcrun", "--sdk", sdk_name, "--find", "ld"], capture=True)
    return {"clang": clang, "triple": triple, "sdk": sdk,
            "flags": ["-target", triple, "-isysroot", sdk], "linker": linker}


def android_tools(args: argparse.Namespace) -> dict:
    requested = args.ndk or os.environ.get("ANDROID_NDK_HOME")
    if not requested:
        raise MobileError("Android targets need --ndk PATH or ANDROID_NDK_HOME pointing to an installed NDK")
    ndk = Path(requested).expanduser().resolve()
    system = {"Darwin": "darwin-x86_64", "Linux": "linux-x86_64"}.get(platform.system())
    if not system:
        raise MobileError("the mobile builder currently supports macOS and Linux hosts")
    binary = ndk / "toolchains" / "llvm" / "prebuilt" / system / "bin"
    arch = "aarch64" if args.target == "android-arm64" else "x86_64"
    triple = f"{arch}-linux-android{args.api}"
    clang, archive = binary / (triple + "-clang"), binary / "llvm-ar"
    for tool in (clang, archive):
        if not tool.is_file() or not os.access(tool, os.X_OK):
            raise MobileError(f"Android NDK tool is missing or not executable: {tool}")
    return {"clang": str(clang), "archive": str(archive), "triple": triple,
            "sdk": str(ndk), "flags": ["-fPIC"]}


def inspect_ir(llvm: str, target: str) -> set[str]:
    libraries = set(re.findall(r"^; minyar-native-library: ([A-Za-z0-9_]+)$", llvm, re.MULTILINE))
    allowed = {"runtime", "callbackruntime"}
    if target.startswith("ios-"):
        allowed.add("mobileios")
    unsupported = libraries - allowed
    if unsupported:
        raise MobileError("native libraries need a mobile provider: " + ", ".join(sorted(unsupported)))
    if "; minyar-thread-runtime: 1" in llvm:
        raise MobileError("managed thread entries are not yet supported by the mobile host")
    if "; minyar-machine: " in llvm:
        raise MobileError("raw machine intrinsics are not supported by the mobile host")
    if "; minyar-c-layout: " in llvm or "; minyar-c-value: " in llvm:
        raise MobileError("C-layout adapters are not yet supported by the mobile builder")
    if target.startswith("ios-") and "mobileios" not in libraries:
        raise MobileError("a UIKit application must call mobile.run or ui-ios.run")
    if len(re.findall(r"^define i32 @main\(", llvm, re.MULTILINE)) != 1:
        raise MobileError("the mobile host requires one generated Minyar entry point")
    return libraries


def publish_app(staged: Path, output: Path) -> None:
    backup = staged.parent / "previous.app"
    if output.exists():
        output.rename(backup)
    try:
        staged.rename(output)
    except OSError:
        if backup.exists():
            backup.rename(output)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def build(args: argparse.Namespace) -> Path:
    validate(args)
    tools = apple_tools(args) if args.target.startswith("ios-") else android_tools(args)
    if not args.no_bootstrap:
        run(["make", "-j2", "build/minyarc", "build/testing/cycle-runtime.c"])
    compiler = ROOT / "build" / "minyarc"
    engine = ROOT / "build" / "testing" / "cycle-runtime.c"
    if not compiler.is_file() or not engine.is_file():
        raise MobileError("build the host tools first: make -j2 build/minyarc build/testing/cycle-runtime.c")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".minyar-mobile-", dir=args.output.parent) as temporary:
        directory = Path(temporary)
        ir = directory / "program.ll"
        command = [str(compiler), str(args.source), str(ir), "--bounded-owners", "32"]
        for library in args.library + [ROOT / "library"]:
            command += ["--library", str(library)]
        run(command)
        llvm = ir.read_text()
        libraries = inspect_ir(llvm, args.target)
        runtime = directory / "runtime.c"
        runtime.write_text('#define MINYAR_SYSTEM_HEAP 1\n#define MINYAR_RC_POLL_BUDGET 32\n'
                           f'#include "{engine.as_posix()}"\n#include "minyar_stack_frames.h"\n')
        optimization = "-O0" if args.debug else "-O2"
        flags = [tools["clang"], *tools["flags"], optimization, "-g", "-Wno-override-module"]
        includes = ["-iquote", str(ROOT / "runtime")]
        objects = []
        for source, name, extra in [(ir, "program.o", []), (runtime, "runtime.o", ["-std=c11", *includes])]:
            output = directory / name
            run([*flags, *extra, "-c", str(source), "-o", str(output)])
            objects.append(str(output))
        metadata = {"schema": 1, "target": args.target, "triple": tools["triple"],
                    "sdk": tools["sdk"], "target_compiler": tools["clang"], "optimization": optimization,
                    "source": str(args.source), "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
                    "ir_sha256": hashlib.sha256(ir.read_bytes()).hexdigest(),
                    "runtime_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
                    "native_libraries": sorted(libraries)}
        if args.target.startswith("ios-"):
            native = directory / "mobileios.o"
            run([*flags, *includes, "-fobjc-arc", "-c", str(ROOT / "runtime" / "native" / "mobileios.m"), "-o", str(native)])
            staged = directory / "application.app"
            staged.mkdir()
            executable = staged / "MinyarApplication"
            run([*flags, f'-fuse-ld={tools["linker"]}', *objects, str(native), "-framework", "UIKit",
                 "-framework", "Foundation", "-framework", "CoreFoundation", "-lobjc", "-lm", "-o", str(executable)])
            info = {"CFBundleIdentifier": args.identifier, "CFBundleName": args.name,
                    "CFBundleDisplayName": args.name, "CFBundleExecutable": executable.name,
                    "CFBundlePackageType": "APPL", "CFBundleVersion": "1", "CFBundleShortVersionString": "1.0",
                    "MinimumOSVersion": args.minimum_ios, "LSRequiresIPhoneOS": True,
                    "CFBundleSupportedPlatforms": ["iPhoneSimulator" if args.target == "ios-simulator" else "iPhoneOS"],
                    "UIDeviceFamily": [1, 2], "UILaunchScreen": {},
                    "UISupportedInterfaceOrientations": ["UIInterfaceOrientationPortrait", "UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"]}
            (staged / "Info.plist").write_bytes(plistlib.dumps(info))
            (staged / "minyar-build.json").write_text(json.dumps(metadata, indent=2) + "\n")
            if args.target == "ios-simulator":
                run(["codesign", "--force", "--sign", "-", "--timestamp=none", str(staged)])
            publish_app(staged, args.output)
        else:
            # Keep generated LLVM intact and bind its entry locally in the JNI
            # library. An atomic guard rejects repeated or concurrent startup.
            wrapper = directory / "entry.c"
            wrapper.write_text('#include <stdatomic.h>\n'
                               'extern int main(int, char **) __attribute__((visibility("hidden")));\n'
                               'int minyar_mobile_entry(void) {\n'
                               '    static atomic_flag started = ATOMIC_FLAG_INIT;\n'
                               '    static char name[] = "Minyar";\n'
                               '    static char *arguments[] = {name, 0};\n'
                               '    if (atomic_flag_test_and_set_explicit(&started, memory_order_relaxed)) return -1;\n'
                               '    return main(1, arguments);\n}\n')
            entry = directory / "entry.o"
            run([*flags, "-std=c11", "-c", str(wrapper), "-o", str(entry)])
            archive = directory / "application.a"
            run([tools["archive"], "rcs", str(archive), *objects, str(entry)])
            metadata_file = directory / "application.a.json"
            metadata_file.write_text(json.dumps(metadata, indent=2) + "\n")
            archive.replace(args.output)
            metadata_file.replace(args.metadata)
    return args.output


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        output = build(args)
    except (MobileError, OSError) as error:
        print(f"mobile: {error}", file=sys.stderr)
        return 1
    print(f"built {output}")
    if args.target == "ios-device":
        print("Device bundle is unsigned. Add a matching provisioning profile and sign before installation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
