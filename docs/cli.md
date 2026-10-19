# Developer CLI

The [signed installer and toolchain manager](install.md) install into
`~/.minyar`, keep versions side by side and select project versions from
`minyar-toolchain`. The release host is configurable; no public host is live yet.

The [macOS](macos-distribution.md) and [Linux](linux-distribution.md) binary
distributions supply prebuilt tools and bundled LLVM. They run without Python,
Make, zsh or another LLVM installation. The platform's C SDK remains required:
Apple's SDK on macOS, or the documented development files and runtime libraries
on Linux. The source-build prerequisites below apply to checkout installations.

The project CLI is written in `tools/project-cli.min` and `tools/project.min`.
The `minyar` shell launcher bootstraps it using the existing self-hosted compiler.
Run `make install` once to install `minyar` into `$HOME/.local/bin`. The installer,
also written in Minyar, copies the compiler, standard library, runtime and build
support into `$HOME/.local/lib/minyar`. The installed command works independently
of the source checkout. Use `make install PREFIX=/another/prefix` for a different
location; its `bin` directory must be on `PATH`. Re-running the installer publishes
a new toolchain without modifying the previous installation's files.
Source installations require LLVM **23.1.2**, Make, zsh and system C headers;
follow the [toolchain setup](toolchain.md), then select the pinned Clang with
`MINYAR_CLANG` and `LLVM_CC`. `minyar --doctor`
checks the installation. Project commands currently require macOS or Linux.

Clang installed at `$HOME/.cache/minyar/toolchains/llvm-23.1.2/bin/clang`
is discovered automatically by the launcher, link driver and Make. Explicit
`MINYAR_CLANG` and `LLVM_CC` selections take precedence. The default fallback
is `clang` on macOS and `clang-23` elsewhere; all selections are version checked.
On macOS the launcher and Make discover the Xcode SDK with
`xcrun --show-sdk-path` unless `SDKROOT` has already been set.

```sh
make install                 # once, from the source checkout
export PATH="$HOME/.local/bin:$PATH"
mkdir hello
cd hello
minyar init                  # initialize this directory
minyar run
minyar test
```

Or create a project directory in one step:

```sh
minyar new hello
cd hello
minyar run -- first-argument "argument with spaces"
minyar check
minyar test
minyar build --release
./target/release/hello
```

`new PATH` creates a directory; `init [PATH]` initializes an existing directory.
Both accept `--name NAME` and `--lib`. They refuse to overwrite a manifest or
entry file, and preserve existing `.gitignore` and smoke tests. A binary uses
`src/main.min`; a library named `geometry` uses `src/geometry.min`. Package names
start with a letter or underscore and contain letters, digits, `_` or `-`.

## Manifest and dependencies

`Minyar.toml` uses this deliberately small TOML subset:

```toml
[package]
name = "hello"
version = "0.1.0"
kind = "bin"

[dependencies]
geometry = { path = "../geometry" }
paint = { git = "github.com/O4FDev/paint", rev = "v0.1.0" }
```

Only these sections and keys are accepted. Strings are double quoted, supporting
escaped quotes and backslashes; blank lines, CRLF and `#` comments are accepted.
Versions have three numeric components. Unknown keys, duplicates and unsupported
TOML constructs produce an error rather than being ignored.

`package.kind` is optional and accepts `"bin"` or `"lib"`. Scaffolding writes
it explicitly. Older manifests without it keep source-layout inference:
`src/main.min` means a binary, otherwise `src/<package-name>.min` means a
library. Thus `minyar new main` creates a runnable binary, while
`minyar new main --lib` records `kind = "lib"` to disambiguate the same path.
Other binary packages can also expose a sibling `src/<package-name>.min`
library for dependencies.

```sh
minyar new ../geometry --lib
minyar add geometry --path ../geometry
minyar tree
minyar metadata
minyar remove geometry
```

Import dependencies with `use "geometry" as geometry`. Dependencies must expose
`src/<package-name>.min`; sibling modules use ordinary relative imports. Source
files stay in their original directories. The resolver follows transitive local
dependencies, rejects cycles, mismatched names and conflicting packages, and
passes the resolved source directories to the compiler. All resolved packages
share a single package-name namespace. `add --path` resolves its argument from
the current working directory, then writes a path relative to the package's
manifest directory. This keeps sibling-package trees usable after relocation,
including when `add` was invoked from a nested directory. Handwritten absolute
paths are still accepted; relative paths always resolve from the manifest
directory. `add` and `remove` rewrite the supported manifest fields and remove
comments.

Add Git packages by their repository path. An omitted revision chooses the latest
stable semver tag; a tag, branch or commit can be selected explicitly:

```sh
minyar add github.com/O4FDev/paint
minyar add github.com/O4FDev/paint@v0.1.0
minyar build --locked --offline
```

`Minyar.lock` records the resolved graph, relative local locations, versions and
manifest hashes. Git entries also pin an exact commit and SHA-256 source-tree
checksum. Commit it with your project. `--locked` rejects a missing or stale
lockfile; `--offline` forbids downloads. Cached Git sources are verified on every
resolution, including ordinary builds. Local source files remain editable.

Git packages use HTTPS and a shared cache under `$MINYAR_HOME/packages` or
`~/.minyar/packages`. Compatible semver requirements select the highest requested
minimum within one major version. Packages cannot run install scripts or supply
native implementations. See [packages](packages.md) for the complete resolution,
cache, security and offline testing contract.

## Builds and tests

Commands discover `Minyar.toml` in the current directory or its parents. Supply
`--manifest-path PATH` to select another manifest or package directory.

`build` and `run` use the debug profile (`--debug` in the compiler); `--release`
enables whole-program optimization. Outputs go to `target/debug` or
`target/release`. Module caching is enabled by default in each profile's `.cache`
directory; use `--no-incremental` to disable it. Library builds validate source;
consumers compile reachable library modules into their own executables.

`--error-format json` selects compiler diagnostics as JSON lines on standard
error for `build`, `run`, `check`, `test` and `install`. This includes discovery
and compilation of embedded module tests. Each compiler diagnostic is preserved
with its original exit status. Use `--error-format text` for the human-readable
renderer. Argument, manifest and runtime messages use their command's normal
format.

Debug builds include Minyar source line tables for breakpoints, stepping and
backtraces, including imported modules. On macOS the matching `.dSYM` bundle is
kept beside each executable. This currently supplies function and source-line
information; local-variable/type inspection is not yet implemented. Release
builds omit this debug information.

`check` validates the entry point and top-level `tests/*.min` without linking.
`test` validates the entry point, then compiles and runs each top-level
`tests/*.min` as an independent executable, in sorted filename order. Keep
support modules outside that directory, or in subdirectories. Tests report
failure by exiting nonzero (`fail("message")` is sufficient).

```sh
minyar test smoke                 # filename substring filter
minyar test --release -- --verbose
minyar build --locked
minyar clean
```

Arguments after `--` are passed unchanged to the program or each test. Programs
and tests run from the package root with inherited standard input/output and
environment. `run` propagates the program exit code; test failures are aggregated
and return nonzero. Compiler failures stop the command immediately. A test filter
matching no files is an error; an empty unfiltered test suite is permitted.

`clean` only removes a generated `target` directory bearing Minyar's ownership
marker. Symlinked targets and existing unowned directories are rejected.

## Install executables

```sh
minyar install --release
minyar install --path ../hello --release --root ~/.local
minyar uninstall hello --root ~/.local
```

The installation prefix defaults to `$MINYAR_HOME` or `$HOME/.minyar`. Executables
go in its `bin` directory; add that directory to `PATH`. Existing binaries require
`--force` to replace. `uninstall` only removes binaries marked as installed by
Minyar. Installing a library is rejected.
A package named `minyar` cannot replace or uninstall an installed toolchain's
launcher, even with `--force` or a stale package marker. Choose a separate
`--root` for that package; use `minyar self update` to update a managed toolchain.

Installation defaults to the debug profile, like `build`. On macOS it installs
the matching `.dSYM` beside the executable and records ownership of that bundle.
A forced release installation removes an older Minyar-owned debug bundle;
uninstall also removes owned symbols. Unrelated or symlinked symbol bundles
are rejected rather than overwritten. Use `--release` when debug symbols are
not wanted.

## Existing compiler interface

`minyar [OPTIONS] FILE.min [-o PROGRAM]` is preserved, including experimental
native backends and app packaging. Project commands currently target the LLVM
backend. `minyar --help` describes file compilation; `minyar help` describes
project commands. Repository maintenance still uses Make targets; `minyar test`
is for user projects, not the compiler repository's full test suite.

Editor/LSP integration, a Minyar source formatter and workspaces remain separate
tooling work.

## Package discovery and release records

```sh
minyar search paint --registry ./public
minyar info paint --registry https://YOUR-HOST
minyar publish github.com/O4FDev/paint --dry-run --description "A vector studio."
minyar registry build ./release-records ./public
minyar registry serve ./public 8080
```

`MINYAR_REGISTRY` selects a static package index for discovery and optional Git
release checksum verification. Remote indexes have a verified local cache for
`--offline`; previously witnessed releases cannot change or disappear. There is
no default public registry deployed yet. `publish` emits metadata only and is a
dry run even without the flag. It requires a clean committed library and a version
tag at HEAD. See [the registry guide](registry.md) for records, checksums, local
testing and static hosting.
