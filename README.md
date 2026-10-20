# Minyar

A small, statically typed language that compiles to native code through LLVM.

## Get started

For macOS 14 and newer, the [binary distribution](docs/macos-distribution.md)
bundles LLVM and the prebuilt Minyar tools. Its installer checks the Apple SDK
and sets up the command. Release candidates can be built locally or with the
manual macOS distribution workflow; they are not yet signed public releases.

The [signed installer and toolchain manager](docs/install.md) keep versions
side by side in `~/.minyar`, with per-project pins and verified updates. The
release directory can be tested locally; a public release host is not live yet.

Building from source requires LLVM 23.1.3, a C compiler, Make, zsh, and system
C development headers. Follow the [toolchain setup](docs/toolchain.md).
The source checkout builds the compiler, runtime and link driver on first use.

The [project CLI](docs/cli.md), written in Minyar, manages packages,
[verified Git and local dependencies](docs/packages.md), builds, tests, and
installed executables:

```sh
make install                  # installs to ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"
minyar new hello
cd hello
minyar run
minyar test
minyar build --release
```

Single-file programs also work directly:

```sh
./minyar examples/hello.min -o hello
./hello
```

Normal builds optimize generated code. Add `--release` for whole-program
optimization with the runtime, or `--debug` for unoptimized code:

```sh
./minyar --release examples/hello.min -o hello
./minyar --check examples/hello.min
```

`--check` validates the language and imported modules without linking native
dependencies or producing a program. Failed builds preserve the previous
executable, and output paths cannot replace the input source.

`./minyar --help` lists options, `--version` identifies the development sources,
and `--doctor` checks the native toolchain with a real LLVM/LTO link. See
[native toolchains](docs/toolchain.md) for platform setup and compiler selection.

Programs use automatic, system-backed incremental reference counting by default.
Large ownership graphs are reclaimed in budgeted batches without required
memory-management syntax. Cycle-capable record and List components automatically
use a traced runtime; unrelated acyclic components retain reference counting.
The default cleanup budget
is 32 work units. Allocator calls, I/O and total operation time remain outside
that bound; this is not a hard-latency guarantee.

`--memory-profile fixed` and `--memory-profile lazy` select optional finite pools.
`--cleanup-budget` accepts 1–1024; `--heap-bytes` selects a power-of-two pool
capacity. `--memory-profile eager` explicitly selects immediate cleanup, which
can cause graph-sized release pauses. See [runtime profiles](docs/bounded-runtime-contract.md).

Run the full local suite with `make check`, the cross-platform per-commit gate
with `make check-portable`, or `make check-smoke` for a quick check. Coverage,
systematic mutation scoring, and AFL++ campaigns are available through
`make check-coverage`, `make check-mutation-score`, and
`make check-fuzz-coverage`.

## Minyarcraft

[`examples/craft`](examples/craft/) is a Minecraft-style block-building game
written in Minyar: generated terrain with caves, ores, trees and water, a
day/night cycle with torch lighting, and saving.

```sh
./minyar --release examples/craft/main.min -o craft
./craft          # or ./craft --new for a fresh world
```

Mouse to look, WASD to move, Space to jump, Shift to sprint, F to fly, left
click to break, right click to place, middle click to pick a block, 1-9 or
the scroll wheel to choose, T to speed up time, and Escape to pause. It uses
the standard `graphics` package, which needs GLFW (`brew install glfw` on
macOS). Programs never write or link C themselves.

## Minyar OS

[`os/`](os/) is an operating system written in Minyar for x86-64 PCs and 64-bit
Arm, from one source tree: a Minyar kernel with its own drivers, TrueType
renderer, TCP/IP stack and an agent desktop. On x86-64 a 512-byte boot record
hands over to a Minyar boot loader; on Arm, QEMU loads the kernel directly and
it runs under Apple's hypervisor at native speed on an Arm Mac.

```sh
make -C os run              # x86-64; needs `brew install llvm lld qemu`
make -C os run ARCH=arm64   # 64-bit Arm
```

The `machine` package and `--freestanding` builds that make it possible are
described in freestanding programs.

## Native macOS apps

Build the AppKit notes example, with native text editing, menus and file dialogs:

```sh
./minyar --app --bundle-id org.example.notes examples/macos/main.min -o "build/Minyar Notes.app"
open "build/Minyar Notes.app"
```

The `macos` package provides windows, layout, styling, controls and an event loop
directly in Minyar, and the `http` and `json` packages talk to web services. See
the macOS guide for APIs, ownership, packaging (including
`--icon` and `--resources`), and the Swift-to-AppKit ABI investigation.

An experimental Swift dialect with a native SwiftUI compiler frontend is also available. First build
the pinned compiler using the native frontend guide, then:

```sh
./minyar --experimental-swift --release --app examples/swiftui/main.min -o "build/Minyar Native SwiftUI.app"
open "build/Minyar Native SwiftUI.app"
```

It parses original `.min` files inside a compiler fork and reuses Swift's semantic
analysis, optimizer, and ABI without generating intermediary Swift source or
adding a Minyar UI runtime. Native acceptance tests cover
SwiftUI scenes, macros, module imports, and a differential LLVM comparison.
It uses Swift value semantics and is **outside the main Minyar language contract**.
It is available through an explicit experimental command rather than a backend
selection. The older `--experimental-swift-source` source prototype
remains available with the installed Xcode compiler. See the
SwiftUI compiler guide for tested features, code-generation
comparison, language differences and the remaining frontend work.

For an app split into plain `.min` files, use `app.min` at the project root and
pass the directory. Components are available automatically across the app;
optional `.mac.min` files replace shared implementations for macOS:

```sh
./minyar --experimental-swift --release examples/native-counter -o "build/Project Counter.app"
open "build/Project Counter.app"
```

## Native Linux desktop apps

The native frontend also has an experimental GTK 4/libadwaita target. Build the
compiler inside Fedora using the Linux desktop guide, then:

```sh
./minyar --experimental-swift --release --pkg-config libadwaita-1 \
  examples/native-editor -o build/minyar-editor
./build/minyar-editor
```

The editor shares `app.min` and its document model with macOS, selecting
`PlatformApplication.linux.min` or `PlatformApplication.mac.min` for the native
UI. Linux SDK calls use the system C ABI. Shared declarative UI syntax, ergonomic
ownership-aware bindings, Flatpak packaging and Mac-to-Linux cross-compilation
remain unfinished.

## Documentation

- [Minyar for people who have never programmed](docs/book/README.md)
- [Minyar for Rust](docs/from-rust.md), [C++](docs/from-cpp.md) and [Swift programmers](docs/from-swift.md)
- [Language guide](docs/language.md)
- [Installation and toolchain versions](docs/install.md)
- [Project CLI](docs/cli.md), [packages](docs/packages.md) and [hosting an index](docs/registry.md)
- [Modules](docs/modules.md) and [incremental builds](docs/incremental-builds.md)
- [Minyar OS](os/README.md)
- [Examples](examples/)
- [Runtime ownership](docs/runtime-memory.md) and [runtime profiles](docs/bounded-runtime-contract.md)
- [Performance testing](docs/performance.md)
- [Testing strategy](docs/testing.md)
- [Linux testing](experiments/linux/README.md)

## A note from the developer 

Hey, Luke here - I made this language as a small joke to a friend as a poke for using PHP and Laravel, I'm trying to get it into an acceptable state for them and me to use in a few projects for funsies and it's also helping me to do some learning and security research, also to push the limits of what AI agents are capable of doing. I've got some really super fun things planned so feel free to drop an issue if you have any ideas or feedback!
