# macOS binary distributions

Minyar can be packaged with its exact LLVM **23.1.2** compiler, LLD linker,
debug-symbol tool, compiler headers, standard library and prebuilt Minyar tools.
Users do not need Homebrew, Python, Make, Git, or an existing LLVM installation.
The installed toolchain never rebuilds itself. Generated files go into
`~/Library/Caches/minyar` (or `$XDG_CACHE_HOME/minyar`); `MINYAR_CACHE_DIR`
can override this. The distribution itself can be read-only.

## Supported platform contract

The binary distribution targets **macOS 14.0 and newer**, with separate native
`arm64` (Apple silicon) and `x86_64` (Intel) archives. Architecture and OS checks
run in shell before any bundled executable, including when Terminal runs under
Rosetta. Unsupported systems receive an explicit error.

The official Apple silicon LLVM archive has a macOS 14.0 deployment target.
Older macOS versions require a separately built and tested LLVM toolchain;
changing a version check cannot make those binaries compatible. The packager
audits every shipped executable and runtime object, rejecting newer OS targets,
the wrong CPU and dynamic dependencies on Homebrew or build-host paths.

Apple's **macOS SDK remains required**, supplied by Xcode or the free Command
Line Tools. The installer checks it before changing the installation. When it
is absent, it opens Apple's installer; finish that installation and rerun
`sh install.sh`. This platform prerequisite is separate from bundled LLVM.
The SDK is not included in the archive. `--check` reports prerequisites without
opening an installation dialog or changing shell configuration.

Optional packages still have their own requirements: GLFW for `graphics`,
and the experimental Swift toolchain for the Swift dialect. Ordinary CLI,
native system/library providers and AppKit builds use the packaged toolchain
and Apple's SDK.

## Install a candidate

Download the matching archive and its checksum from the same trusted release
channel, verify before extracting, then run the installer:

```sh
shasum -a 256 --check minyar-VERSION-macos-arm64.tar.gz.sha256
tar -xzf minyar-VERSION-macos-arm64.tar.gz
cd minyar-VERSION-macos-arm64
sh install.sh
```

Use `macos-x86_64` on Intel. The installer exercises `new`, `run`, `test` and a
release build before publishing the command. It installs into `~/.local`,
preserves old toolchain versions, refuses unrelated commands, and adds its PATH
setup to `.zshrc` or `.bash_profile` without duplicating it on reinstall. Open
a new terminal or run the printed command to update the current shell.

```sh
sh install.sh --prefix "/another/location"
sh install.sh --no-modify-path
minyar new hello
cd hello
minyar run
minyar test
minyar build --release
```

Explicit `MINYAR_CLANG`/`LLVM_CC` overrides still take precedence over bundled
LLVM. Remove stale overrides if `--doctor` reports an unexpected compiler.
`SDKROOT` and `DEVELOPER_DIR` can similarly override Apple's SDK selection.

## Build and qualify a release

Run on a Mac of the target architecture with Python 3.9+, the Apple SDK and a
native LLVM 23.1.2 prefix containing `clang`, `lld`, `dsymutil` and `lib/clang`:

```sh
make package-macos MINYAR_VERSION=0.1.0-rc1 \
  MINYAR_LLVM_ROOT="$HOME/.cache/minyar/toolchains/llvm-23.1.2"
mkdir -p build/release-test
tar -xzf build/releases/minyar-0.1.0-rc1-macos-arm64.tar.gz -C build/release-test
make check-macos-distribution \
  MINYAR_DISTRIBUTION="$PWD/build/release-test/minyar-0.1.0-rc1-macos-arm64"
```

Builds set `MACOSX_DEPLOYMENT_TARGET=14.0`. `--no-build` on the Python packager
can package existing artifacts, but always audits them. Archives include LLVM's
license, a per-file SHA-256 manifest and a sidecar archive checksum. The packager
refuses to overwrite an existing release.

The manual **macOS binary distributions** workflow builds Apple silicon and
Intel candidates. Intel LLVM is built from checksum-pinned upstream source
because that release has no official native Intel archive. Compatibility jobs
install the same archives on macOS 14, 15 and 26 for Apple silicon, and 15 and
26 for Intel. The test uses a fresh HOME, system-only PATH, paths containing
spaces and apostrophes, debug/release builds, native providers, all memory
profiles, app packaging, shell setup, upgrades and removal of source/old copies.
Missing-SDK diagnostics are tested without opening Apple's installer.

**Publication gate:** these are unsigned development candidates. Before public
distribution, sign all executable code with Developer ID, notarize the final
delivery artifact and verify Gatekeeper behavior on a quarantined download on
each supported platform. The existing `scripts/release.min` handles app/DMG
signing; it does not sign CLI toolchain archives. Do not claim a public,
Gatekeeper-approved installer until that CLI delivery/signing work and the
compatibility jobs have passed. No public release is published by this workflow.
