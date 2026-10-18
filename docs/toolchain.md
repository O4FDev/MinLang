# Native toolchain setup

These are **source-build** instructions. The [macOS binary distribution](macos-distribution.md)
bundles the pinned LLVM compiler, linker, and prebuilt Minyar tools, so users of
that distribution only need Apple's macOS SDK. Its installer checks the SDK and
opens Apple's Command Line Tools installer when it is missing.

Minyar's LLVM backend requires **LLVM 23.1.2**, a 64-bit target, Make, zsh,
and the operating system's C development headers and libraries. Both ordinary
and release builds check the exact compiler version. Linux release builds also
need matching LLD. The project CLI currently runs on macOS and Linux.

The commands below follow the toolchain selections in
[`CI`](../.github/workflows/ci.yml). Run the verification commands from the
Minyar checkout before `make install`.

## macOS on Apple silicon

Install Apple's command-line tools if they are not already installed:

```sh
xcode-select --install
```

After that installation completes, check `xcrun --show-sdk-path`. The launcher
discovers this SDK automatically. Apple's bundled Clang alone does not satisfy
the pinned LLVM version.

Download the same LLVM archive and verify the same SHA-256 used by CI. This
recipe is for `arm64` Macs; it deliberately refuses an existing destination:

```sh
test "$(uname -m)" = arm64
minyar_llvm_dir="$HOME/.cache/minyar/toolchains/llvm-23.1.2"
minyar_download_dir="$(mktemp -d)"
minyar_archive="$minyar_download_dir/LLVM-23.1.2-macOS-ARM64.tar.xz"
curl --fail --location --retry 3 \
  'https://github.com/llvm/llvm-project/releases/download/llvmorg-23.1.2/LLVM-23.1.2-macOS-ARM64.tar.xz' \
  -o "$minyar_archive" &&
printf '%s  %s\n' \
  'd7c26fc6177e42842e2d1ffaad31aec057c56a924392b1a23d830abe2c5d53b1' \
  "$minyar_archive" | shasum -a 256 --check
```

Only after the checksum succeeds, extract it:

```sh
mkdir -p "$(dirname "$minyar_llvm_dir")"
mkdir "$minyar_llvm_dir" &&
tar -xJf "$minyar_archive" -C "$minyar_llvm_dir" --strip-components=1
export MINYAR_CLANG="$minyar_llvm_dir/bin/clang"
export LLVM_CC="$MINYAR_CLANG"
./minyar --doctor
```

The cache location above is discovered automatically on later invocations.
For Intel Macs, select a matching LLVM 23.1.2 installation for that architecture
using the variables below; the ARM64 archive is not an Intel installation.

## Ubuntu 24.04

Install the native build prerequisites and add the LLVM 23 package repository,
as the Linux CI job does:

```sh
sudo apt-get update &&
sudo apt-get install -y build-essential zsh curl ca-certificates gnupg
minyar_key="$(mktemp)"
curl --fail --location 'https://apt.llvm.org/llvm-snapshot.gpg.key' -o "$minyar_key" &&
sudo gpg --batch --yes --dearmor \
  -o '/usr/share/keyrings/minyar-llvm.gpg' "$minyar_key"
printf '%s\n' \
  'deb [signed-by=/usr/share/keyrings/minyar-llvm.gpg] https://apt.llvm.org/noble/ llvm-toolchain-noble-23 main' |
  sudo tee '/etc/apt/sources.list.d/minyar-llvm.list'
sudo apt-get update &&
sudo apt-get install -y clang-23 llvm-23 lld-23 libclang-rt-23-dev
export MINYAR_CLANG='/usr/lib/llvm-23/bin/clang'
export LLVM_CC="$MINYAR_CLANG"
./minyar --doctor
```

The LLVM repository can advance within its release branch. Installing packages
named `*-23` alone does not establish the required patch version: `--doctor`
must report 23.1.2 and pass its link checks. If the repository supplies a different
patch, use a matching 23.1.2 installation or package snapshot and point both
variables at it. Other distributions need their equivalent C development,
Make, zsh, and matching Clang/LLD packages.

## Compiler selection and verification

For an LLVM installation elsewhere:

```sh
export MINYAR_CLANG='/absolute/path/to/llvm-23.1.2/bin/clang'
export LLVM_CC="$MINYAR_CLANG"
./minyar --doctor
```

`MINYAR_CLANG` selects the launcher/link driver; `LLVM_CC` selects Make's LLVM
compiler. Set both when using a custom installation. An explicitly set `CC`
also affects native C bootstrap compilation. With no override, the tools check
`$HOME/.cache/minyar/toolchains/llvm-23.1.2/bin/clang`, then `clang` on macOS or
`clang-23` elsewhere. On macOS, an explicit `SDKROOT` overrides SDK discovery.

`--doctor` checks prerequisites, C headers, 64-bit code generation, opaque LLVM
IR, and an actual LTO link. A working `clang --version` by itself is insufficient.
After it passes:

```sh
make install
export PATH="$HOME/.local/bin:$PATH"
minyar new hello
cd hello
minyar run
minyar test
```

Add the PATH setting to your shell configuration for future terminals.
Use `make install PREFIX="/another/prefix"` to choose another toolchain location.
See the [CLI guide](cli.md) for project dependencies and executable installation.

Optional packages have additional prerequisites: `graphics` uses GLFW,
while the native Swift/GTK backends use separate compiler/SDK installations.
The basic hello project does not require those optional backends.
