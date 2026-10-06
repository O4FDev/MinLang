# Native toolchains

`./minyar file.min -o program` optimizes generated code with `-O2` by default.
`--debug` selects `-O0`; `--release` additionally enables LTO across the program
and runtime. Runtime ownership checks remain enabled in all three modes.
`--check` validates language and module semantics without producing a native
program. It can be combined with `--incremental`; native library availability
and linking remain build-time checks.

```sh
./minyar --help
./minyar --version
./minyar --doctor
./minyar --check app.min
```

The version command reports a development source identity and the cached
compiler identity. The doctor actually links opaque-pointer LLVM IR and a
64-bit C translation unit with LTO, rather than reporting readiness from a
version string alone. It also checks Make, a C compiler, zsh, and C headers.
Python 3.9 or newer is required by the launcher helpers.

## Installation

On macOS, install Xcode command-line tools (`xcode-select --install`). Apple
Clang works; Homebrew LLVM is optional. Install `glfw` and `pkg-config` with
Homebrew for graphics programs.

On Debian or Ubuntu:

```sh
sudo apt install clang lld make python3 zsh
sudo apt install libglfw3-dev pkg-config # graphics programs
```

On Windows, the supported development environment is MSYS2 UCRT64:

```sh
pacman -S make diffutils zsh python mingw-w64-ucrt-x86_64-clang \
  mingw-w64-ucrt-x86_64-glfw mingw-w64-ucrt-x86_64-pkgconf
make LIMITED= SANITIZER_LIMITED= COMPILER_LTO_FLAGS= CC=clang LLVM_CC=clang check-portable
```

Use the UCRT64 shell. The ordinary launcher and native renderer target MinGW
Windows executables; incremental module caching currently uses a POSIX driver
with `fork` and `/dev/fd` and is supported on macOS and Linux. Native Windows
without MSYS2 is not a supported bootstrap path.

## Selection, flags, and caches

`MINYAR_CLANG` selects an executable for both the launcher's bootstrap and native
link. The launcher uses that Clang for the C bootstrap too, unless `CC` was
explicitly selected. `LLVM_CC` selects the Make toolchain and is also the launcher's fallback
when `MINYAR_CLANG` is absent. Paths containing spaces are passed as one argument:

```sh
MINYAR_CLANG='/path with spaces/clang' ./minyar --release app.min -o 'my program'
MINYAR_CLANG_FLAGS='-O3 -Wno-override-module' ./minyar app.min
```

`MINYAR_CLANG_FLAGS`, `MINYAR_RUNTIME_FLAGS`, and `MINYAR_NATIVE_FLAGS` use
shell-style quoting to form literal arguments. Quotes can protect spaces;
wildcards and command substitutions are never evaluated. Use forward slashes
for Windows paths in these flag strings. Native flags default to the program
flags; override them when a native package needs a different optimization level.

Make tracks compiler identity and configuration in a toolchain stamp so switching
compilers rebuilds generated artifacts. Graphics objects are content-addressed by
Clang executable/version, compilation flags, source, and runtime headers. They
are published from invocation-owned temporary files. A project-local advisory
lock serializes shared bootstrap builds; program compilation and linking remain
parallel. Old objects remain valid
for concurrent links and disappear with `make clean`. The native cache is a local
build cache, not a distribution or trust boundary.

The launcher rejects unreadable source files before bootstrapping and refuses
source/output aliases, including symlinks and hard links. Native links stage
their result on the output filesystem and publish it with an atomic rename.
A failed or interrupted link preserves the previous complete executable.

Unix links include `libm` after the runtime object. Linux release links prefer a
matching `ld.lld`, avoiding GNU ld's optional LLVMgold plugin, unless a linker
was explicitly selected. The public Linux compiler bootstrap also prefers matching
LLD and defaults to one linker thread, keeping its virtual address reservations
within the existing development limit. Explicit `COMPILER_LTO_FLAGS` are preserved;
callers selecting their own LLD flags can use `-Wl,--threads=1` to stay within that
limit. Explicit thread options in `LLVM_FLAGS` are preserved as well. Apple and
Windows builds do not receive the ELF thread option. Graphics links use macOS frameworks, Linux OpenGL, or
Windows `opengl32`; newer Windows GL entry points are loaded through GLFW after
the context becomes current. [GLFW's context guide](https://www.glfw.org/docs/latest/context_guide.html)
describes the required context and function-loading behavior.

## LLVM audit, 2026-10-02

The latest official stable release verified through the upstream release API is
[LLVM 23.1.2](https://github.com/llvm/llvm-project/releases/tag/llvmorg-23.1.2),
published September 22, 2026. Release-index search results can lag the upstream
release API; LLVM development trunk is not a stable release.

| Toolchain | Evidence in this change |
| --- | --- |
| Apple Clang 17.0.0, macOS ARM64 | Launcher, runtime-cache, native renderer compilation, GL loader, and doctor probes executed locally |
| Ubuntu Clang 18.1.3, Linux ARM64 | Isolated portable suite and real missing-libm regression executed in Docker |
| Upstream Clang 22.1.5, macOS ARM64 | Opaque IR assembly/verification, native and LTO program execution, and native renderer compilation executed locally |
| Upstream Clang/LLVM/lld 23.1.2, Linux ARM64 | Installed from signed official packages; portable suite, release/launcher tests, native renderer, incremental modules, IR verification, and craft release links executed in Docker |
| GCC 13.3.0, Linux ARM64 | Bootstrap maximum-Integer and complete compiler-source checks executed under UBSan after fixing intermediate signed overflow |
| LLVM branches 22 and 23, Linux x86-64 | Hosted CI matrix configured using signed official apt repositories; execution is pending |
| MSYS2 UCRT64, Windows x86-64 | Hosted portable/native-renderer checks configured; no local Windows execution in this change |

The live [official Noble LLVM 23 repository metadata](https://apt.llvm.org/noble/dists/llvm-toolchain-noble-23/main/binary-amd64/Packages)
was checked and offered Clang/LLVM/lld 23.1.2 packages. CI records the installed
version; these are release-branch packages and may receive subsequent fixes.
Local LLVM 22 evidence is retained at `build/toolchain-evidence/llvm22.json`.
Linux snapshot hashes and logs are retained under `build/toolchain-evidence/linux`.
LLVM 23 and GCC evidence is under `build/toolchain-evidence/llvm23`. The separate
initial 60-second AFL++ campaign completed 39,251 executions without crashes or
hangs. The pre-List freeze completed 52,865 executions, and the final List implementation
completed 32,298 executions in another 60-second run, both without crashes or
hangs. These are independent discovery campaigns, not timing comparisons. Final
sources, logs, and findings are under `build/toolchain-evidence/final-list-linux`.

The final compiler (`8519fd17…`) is revalidated after the namespace, native ABI,
and sparse source-position changes. LLVM 22 verifies and LTO-links it, reproduces
the exact self-hosted IR, and passes arithmetic, conversion, and symbol-isolation
tests. LLVM 23's isolated Linux snapshot passes all 61 recorded correctness
checks. Its AFL++ campaign completes 68,364 executions in 60 seconds with no saved
crashes or hangs; native examples and all four game link modes pass. A subsequent
test-only snapshot closes both observed mutation survivors and passes the full
16-mutant and coverage campaigns without changing production sources. Records
are retained under `build/toolchain-evidence/final-linkage-llvm22` and
`build/toolchain-evidence/final-pairs-linux`; the final evidence index is
`build/hardening-evidence/final/summary.json`.

The CI action audit also checked current official releases:
[checkout 7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1),
[setup-python 7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0),
[upload-artifact 7.0.1](https://github.com/actions/upload-artifact/releases/tag/v7.0.1),
[cache 6.1.0](https://github.com/actions/cache/releases/tag/v6.1.0), and
[setup-msys2 2.33.0](https://github.com/msys2/setup-msys2/releases/tag/v2.33.0).
Both workflows pin the release commits, disable checkout credential persistence,
and use read-only repository permissions. Dependabot checks the pins weekly.
Actionlint 1.7.12 validates both workflows locally; executing these hosted jobs
remains separate from local toolchain validation. Python 3.12 in CI is a deliberate
supported interpreter baseline, while local suites also exercise Python 3.14.

Minyar emits textual IR rather than using LLVM's C/C++ API. It already uses
`ptr`, typed loads/stores, and typed GEP element operands, matching LLVM's
[opaque-pointer model](https://llvm.org/docs/OpaquePointers.html). LLVM 17 removed
typed pointers; changes to LLVMBuildLoad/LLVMBuildCall API signatures therefore
do not require an API migration here.

The [LLVM 23 release notes](https://releases.llvm.org/23.1.0/docs/ReleaseNotes.html)
identify two relevant checks. `alwaysinline` no longer overrides target-feature
compatibility, so runtime IR still removes host CPU/feature attributes before
LTO with generic Minyar callers. LLVM 23 also changes floating-point literal
formats and deprecates old bitwise hexadecimal spelling. Minyar's emitted Float
constants use decimal spelling; runtime IR is produced by the selected matching
Clang. Passing assembly/verification and executing Float fixtures are required
before declaring a new LLVM version supported.

Generated IR deliberately leaves the target triple and data layout to Clang;
it is only intended for supported 64-bit native targets. C-generated runtime IR
and native objects must match the same toolchain and target. This does not make
arbitrary cross-compilation or 32-bit object layouts supported.

Checked List reads, scalar writes, and length loads now use small internal
`alwaysinline` LLVM helpers, allowing ordinary builds to optimize those operations
without LTO. C static assertions bind the helpers to the supported 64-bit List
layout. Runtime calls remain on invalid-index and reference-write paths.

Checked arithmetic, shifts, Unicode scalar conversion, Float-to-Integer conversion,
Integer absolute value, and clamping also expose their successful paths to LLVM.
Integer failure entry points are explicitly cold and non-returning. Other helpers
retain returning runtime fallbacks where required by the ABI. Conversion limits
use exactly representable decimal bounds, avoiding the deprecated hexadecimal
IR spelling without weakening NaN, infinity, overflow, or Unicode checks.

The main optimization opportunities remain broader runtime visibility through LTO,
reducing remaining generic container operations, and emitting accurate alias/effect and
function linkage information where language semantics justify it. Adding
`noalias`, `nonnull`, overflow flags, fast-math, or internal linkage without a
proof can miscompile shared references, checked arithmetic, or exported modules.
LLVM 23 alone is not evidence of a performance gain over C++.
