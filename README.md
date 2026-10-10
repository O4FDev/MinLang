# Minyar

A small, statically typed language that compiles to native code through LLVM.

## Get started

Requires Clang, a C compiler, Make, Python 3.9+, zsh, and system C development
headers. The compiler and runtime build on first use.

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
Large ownership graphs are reclaimed in budgeted batches, with no tracing
collector and no required memory-management syntax. The default cleanup budget
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

## Native macOS apps

Build the AppKit notes example, with native text editing, menus and file dialogs:

```sh
./minyar --app --bundle-id org.example.notes examples/macos/main.min -o "build/Minyar Notes.app"
open "build/Minyar Notes.app"
```

The `macos` package provides windows, layout, styling, controls and an event loop
directly in Minyar, and the `http` and `json` packages talk to web services. See
the [macOS guide](docs/macos.md) for APIs, ownership, packaging (including
`--icon` and `--resources`), and the Swift-to-AppKit ABI investigation.

An experimental native SwiftUI compiler frontend is also available. First build
the pinned compiler using the [native frontend guide](docs/native-frontend.md), then:

```sh
./minyar --backend native --release --app examples/swiftui/main.min -o "build/Minyar Native SwiftUI.app"
open "build/Minyar Native SwiftUI.app"
```

It parses original `.min` files inside a compiler fork and reuses Swift's semantic
analysis, optimizer, and ABI without generating intermediary Swift source or
adding a Minyar UI runtime. Native acceptance tests cover
SwiftUI scenes, macros, module imports, and a differential LLVM comparison.
It is **not full Minyar/Swift parity**. The older `--backend swift` source prototype
remains available with the installed Xcode compiler. See the
[SwiftUI compiler guide](docs/swiftui.md) for tested features, code-generation
comparison, language differences and the remaining frontend work.

For an app split into plain `.min` files, use `app.min` at the project root and
pass the directory. Components are available automatically across the app;
optional `.mac.min` files replace shared implementations for macOS:

```sh
./minyar --backend native --release examples/native-counter -o "build/Project Counter.app"
open "build/Project Counter.app"
```

## Native Linux desktop apps

The native frontend also has an experimental GTK 4/libadwaita target. Build the
compiler inside Fedora using the [Linux desktop guide](docs/linux-desktop.md), then:

```sh
./minyar --backend native --release --pkg-config libadwaita-1 \
  examples/native-editor -o build/minyar-editor
./build/minyar-editor
```

The editor shares `app.min` and its document model with macOS, selecting
`PlatformApplication.linux.min` or `PlatformApplication.mac.min` for the native
UI. Linux SDK calls use the system C ABI. Shared declarative UI syntax, ergonomic
ownership-aware bindings, Flatpak packaging and Mac-to-Linux cross-compilation
remain unfinished.

## Documentation

- [Language guide](docs/language.md) and [syntax review](docs/syntax-review.md)
- [Architecture and coding standards](docs/architecture.md)
- [Native toolchains and LLVM audit](docs/toolchain.md)
- [October language hardening review](docs/hardening-report.md)
- [Modules](docs/modules.md) and [incremental builds](docs/incremental-builds.md)
- [Examples](examples/)
- [Runtime ownership](docs/runtime-memory.md) and [runtime profiles](docs/bounded-runtime-contract.md)
- [Performance testing](docs/performance.md)
- [Testing strategy](docs/testing.md)
- [Linux testing](experiments/linux/README.md)

## A note from the developer 

Hey, Luke here - I made this language as a small joke to a friend as a poke for using PHP and Laravel, I'm trying to get it into an acceptable state for them and me to use in a few projects for funsies and it's also helping me to do some learning and security research, also to push the limits of what AI agents are capable of doing. I've got some really super fun things planned so feel free to drop an issue if you have any ideas or feedback!
