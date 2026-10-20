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

On x86-64 Ubuntu, install the same checksum-pinned LLVM archive used by CI:

```sh
test "$(uname -m)" = x86_64
sudo apt-get update &&
sudo apt-get install -y build-essential make zsh curl ca-certificates zstd libxml2 libtinfo6
minyar_llvm_dir="$HOME/.cache/minyar/toolchains/llvm-23.1.2"
minyar_download_dir="$(mktemp -d)"
minyar_archive="$minyar_download_dir/LLVM-23.1.2-Linux-X64.tar.zst"
curl --fail --location --retry 3 \
  'https://github.com/llvm/llvm-project/releases/download/llvmorg-23.1.2/LLVM-23.1.2-Linux-X64.tar.zst' \
  -o "$minyar_archive" &&
printf '%s  %s\n' \
  '6382de1c1a210ce5a5cc49d18bc8444d137742e7cbf9b19f4ae602bb1ab52534' \
  "$minyar_archive" | sha256sum --check
```

Only after the checksum succeeds, extract into a new directory:

```sh
mkdir -p "$(dirname "$minyar_llvm_dir")"
mkdir "$minyar_llvm_dir" &&
tar --zstd -xf "$minyar_archive" -C "$minyar_llvm_dir" --strip-components=1
export MINYAR_CLANG="$minyar_llvm_dir/bin/clang"
export LLVM_CC="$MINYAR_CLANG"
./minyar --doctor
```

LLVM package repositories can advance within a release branch. Packages named
`*-23` alone do not establish the required patch version: `--doctor` must report
23.1.2 and pass its link checks. ARM64 Linux needs a matching native toolchain;
the X64 archive is not an ARM64 installation. Other distributions need their
equivalent C development, Make and zsh packages.

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

## Compiler ThinLTO cache on Linux

Source builds and first-use bootstrap cache compiler ThinLTO backend objects
when selecting ELF lld automatically. The default directory is
`build/thinlto-cache`; `make clean` removes it. Ordinary program links do not
use this compiler cache. Configure Make or bootstrap through these variables:

```sh
make COMPILER_LTO_CACHE_DIR='/scratch/minyar compiler cache'
COMPILER_LTO_CACHE_DIR='/scratch/minyar compiler cache' ./minyar hello.min
make COMPILER_LTO_CACHE_DIR=  # disable caching while keeping ThinLTO
```

`COMPILER_LTO_CACHE_POLICY` defaults to
`cache_size=10%:cache_size_bytes=1g:cache_size_files=10000:prune_after=168h:prune_interval=0s`.
LLD applies the 10% available-space, 1 GiB and 10,000-file limits together,
expires entries unused for a week, and scans after every link. These are
post-link pruning limits; a link can temporarily exceed them. A shared directory
shares its limits across builds. An override uses LLVM's colon-separated policy
syntax; setting a limit to zero disables that limit.

Explicit `COMPILER_LTO_FLAGS`, including an empty value, are preserved exactly
and bypass automatic cache options. A linker selected through `LLVM_FLAGS`
also receives no automatic cache options. Darwin and Windows do not receive
automatic compiler caching. To configure another linker, supply its own options
explicitly. Paths containing spaces, apostrophes or commas are supported.

LLVM derives cache keys from the LLVM version, input modules, imports/exports
and code generation configuration. Deleting the cache is safe; the next link
rebuilds its objects. See LLVM's [ThinLTO cache and pruning options](https://clang.llvm.org/docs/ThinLTO.html#incremental)
and [cache key implementation](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.2/llvm/lib/LTO/LTO.cpp).
