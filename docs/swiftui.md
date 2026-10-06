# Native SwiftUI compiler target (experimental)

The goal is a first-class Minyar frontend for Apple's native programming model:
the same concrete SwiftUI types, generic specialization, ownership, concurrency,
and SDK access as Swift, with Minyar's own language design. A control wrapper,
an `AnyView` renderer, or a callback/event serialization layer does not meet that
goal. **Full language and tooling parity has not been achieved.**

This branch contains a working, opt-in native frontend. `--backend native`
passes original `.min` files to a pinned compiler fork, where native parsing feeds
Swift's semantic AST, type checker, macro expansion, SIL pipeline, optimizer, and
LLVM backend. It generates no intermediary Swift source and adds no Minyar UI
runtime. The direct-frontend acceptance suite covers compilation and project builds.

The older `--backend swift` prototype still lowers source and uses the installed
Xcode compiler. It is available without building the custom toolchain. The two
backends share app/module packaging, but have distinct source-processing paths.

For native GTK/libadwaita development with the same frontend and app layout, see
[Linux desktop development](linux-desktop.md). SwiftUI itself remains Apple-only.

## Build and run

Requires macOS, Xcode with Swift 6, and a logged-in desktop for GUI tests.
Verified with the pinned Swift 6.2.4 compiler, macOS SDK 26.2 and an Apple Silicon
macOS 26.0 host. Other SDK/compiler/OS combinations need their own validation.

Build the custom compiler following the [native frontend guide](native-frontend.md).
Then compile and launch the app; compilation alone does not open a window.

```sh
./minyar --backend native --release --app \
  --bundle-id org.example.native-notebook \
  examples/swiftui/main.min -o "build/Minyar Native SwiftUI.app"
open "build/Minyar Native SwiftUI.app"

# Mount a real SwiftUI scene, mutate observable state, then exit.
"build/Minyar Native SwiftUI.app/Contents/MacOS/application" --smoke

make check-native-compiler
```

`--backend native` must be the first option. The default target remains the
portable LLVM compiler (`--backend llvm` is also accepted). The native target
does not build or link the portable Minyar runtime or the AppKit handle package.
It uses native Swift objects, values, ARC and concurrency. Apple's Swift runtime
is expected in the resulting binary, just as it is for a Swift-authored app.

The example uses `App`, scenes, settings, command menus, `NavigationSplitView`,
`List`, concrete generic cards, native text editing, bindings, `@State`,
`@Bindable`, the `@Observable` macro, animation and actor-isolated tasks.

## Plain .min app projects

Use ordinary `.min` files for components and application logic. A project has
an `app.min` entry file at its root; feature folders are optional:

```text
native-counter/
  app.min
  counter/
    Counter.min
    CounterToolbar.min
    CounterToolbar.mac.min
```

Build the [complete example](../examples/native-counter/app.min) by passing its
directory or its `app.min` file. Project mode implies `--app`:

```sh
./minyar --backend native --release examples/native-counter \
  --bundle-id org.minyar.project-counter -o "build/Project Counter.app"
open "build/Project Counter.app"
```

Each directory containing an `app.min` defines a separate app. A repository can
contain sibling or nested apps:

```text
workspace/
  notebook/
    app.min
    Notes.min
    tools/
      preview/
        app.min
        Preview.min
  counter/
    app.min
    Counter.min
```

Build `workspace/notebook`, `workspace/notebook/tools/preview`, or
`workspace/counter` separately. Discovery stops at nested app boundaries, so
the notebook never compiles the preview's sources or entry point. This also
applies to directories with platform-specific app entries. A workspace directory
without its own entry asks you to select an individual app; it does not combine
all apps into one binary or implicitly build them all.

Components and functions are available by name across the app without local
file imports. All selected files form one module; feature folders organize code
without introducing namespaces. Normal access control still applies, and SDK
imports such as `use "SwiftUI"` remain explicit in files that use their APIs.
`app.min` declares the app with the existing `@main ...: App` syntax; the filename
does not synthesize an entry declaration. HTML-like component syntax is not yet
implemented.

For a macOS target, `CounterToolbar.mac.min` replaces `CounterToolbar.min` in
the same folder. Other platform variants are excluded. A shared file is used
when the target has no override. Platform-only files are included only for their
target. Entry files can also have overrides, such as `app.mac.min`; pass the
project directory when there is no shared `app.min`.

Recognized suffixes are `.mac.min`, `.ios.min`, `.windows.min`, `.linux.min`,
`.android.min`, and `.web.min`; ordinary `.swift` files follow the same selection
rule. Selection uses `--target-platform`, whose default is `mac`. **Only macOS
builds are currently supported.** Other target requests fail explicitly; these
filename rules do not provide Windows, web, or iOS backends or cross-compilation
toolchains.

Discovery includes `.min` and `.swift` files recursively within the app boundary, excluding hidden files
and directories, `build`, `dist`, `target`, `node_modules`, `__pycache__`, and
`.app`, `.framework`, and `.bundle` directories. Directory symlinks are not
followed; source-file symlinks inside projects are rejected. Keep unrelated
programs/tests outside the app source directory. A project uses one declaration
namespace, so components need distinct names across feature folders.

Passing explicit files other than a lone `app.min` retains manual source scope;
neighbors are not discovered. Variants are selected only among those supplied
files. Existing `main.min` commands continue to work. Project discovery is
specific to `--backend native`; the portable LLVM backend and the source
prototype retain their existing file handling.

Run `make check-native-project` for SDK-independent selection tests, or
`make check-native-compiler` for those tests plus native compilation/app tests.

Inspect native compiler output:

```sh
./minyar --backend native --release --parse-as-library \
  --emit-sil build/native.sil \
  --emit-ir build/native.ll \
  examples/swiftui/main.min -o build/native-notebook
```

SIL and IR inspection cause additional compiler invocations with the same flags.
The executable is compiled through the compiler's in-memory pipeline. Textual
SIL is not used as a build input: on the tested toolchain, reparsing emitted SIL
for an `@State` view reports `expected get or set in a protocol property` at a
`nonmutating _modify` accessor and crashes. A robust future frontend needs a
compiler integration, not dependence on this textual round-trip. The native
frontend uses that integration; `--emit-swift` is explicitly rejected.

Multiple `.min` files can be passed in one invocation; they share a native
module. With multiple inputs, top-level executable statements belong in
`main.min` (or `main.swift`); alternatively use one `@main` declaration.
Standalone `@main` executables need `--parse-as-library`; app and library modes
select it automatically. Select a module name with `--module-name Name`.
Additional compiler arguments can be supplied one at a time using
`--swift-flag=-I --swift-flag=/path/to/modules` (likewise SDK/target/framework
options). These are passed as individual arguments, never shell commands.
Use compatible arguments: overriding the driver's output mode is unsupported.
The bundle packager is the same as the [AppKit target](macos.md).

## Native libraries and Swift imports

Build public Minyar-native declarations as a native library/module:

```sh
./minyar --backend native --library --release --module-name MinyarWidgets \
  examples/swiftui-library/widgets.min -o build/MinyarWidgets
```

The output directory contains `libMinyarWidgets.dylib`, the binary
`MinyarWidgets.swiftmodule`, its documentation/source information, a public
`.swiftinterface`, a private interface and an ABI descriptor. The compiler uses
library evolution mode. The dylib's install name is `@rpath/libMinyarWidgets.dylib`;
clients supply the library directory as a runtime search path or package it in
their app. App packaging does not automatically embed dependent dylibs yet.

A separately compiled Swift client imports the module normally:

```swift
import SwiftUI
import MinyarWidgets

struct Content: View {
    @State private var count = 0
    var body: some View {
        VStack {
            NativeBadge(value: "A Minyar-authored generic view")
            NativeCounter(count: $count)
        }
    }
}
```

Compile the maintained Swift integration test with:

```sh
xcrun swiftc -swift-version 6 -parse-as-library -O \
  -I build/MinyarWidgets -L build/MinyarWidgets -lMinyarWidgets \
  -Xlinker -rpath -Xlinker "$PWD/build/MinyarWidgets" \
  tests/swiftui-library-client.swift -o build/swiftui-library-client
./build/swiftui-library-client
```

The integration suite also imports only the public textual interface with a
fresh module cache, and imports the module from a second Minyar compilation.
Concrete generic views, opaque body types, associated-type protocol conformances
and `@inlinable` generic functions remain native module declarations. There is
no C export layer or mandatory view erasure. Resilience and cross-module
optimization follow the ordinary native compiler rules; library mode is not a
claim that every public function will be inlined.

`--library` and `--app` are mutually exclusive.
The output is a directory, not a dylib filename. Rebuilds replace its binary and
metadata together after compilation succeeds. The installer refuses unrelated
directories/symlinks and uses a sibling `.minyar-lock`. If installing a new
directory fails, it restores the previous version; if rollback also fails, the
error identifies the preserved backup. Interrupted installation may require
recovering that backup and removing the stale lock once no writer is running.

## Experimental syntax and compatibility boundary

This is not a drop-in backend for existing Minyar programs. Most expression,
type and declaration syntax currently comes from Swift. The frontend recognizes
these Minyar forms:

| Minyar native syntax | Equivalent Swift semantics |
| --- | --- |
| `use "SwiftUI"` | `import SwiftUI` |
| `record Card<T>: View` | `struct Card<T>: View` |
| `function f(x: Int): Int` | `func f(_ x: Int) -> Int` |
| `function f(to x: Int): Int` | `func f(to x: Int) -> Int` |
| `let count = 0` | mutable `var count = 0` |
| `constant count = 0` | immutable `let count = 0` |
| `async constant answer = work()` | Swift `async let` child task |

Native `func`, `struct`, `var`, attributes, generics, protocols, associated types,
enums, classes, actors, extensions, opaque types, key paths and closures can be
written directly. Function return types may use `:` or `->`, including typed
throws such as `throws(Failure): Int`. The older source prototype requires `->`
with typed throws. Record fields require an
explicit `let` or `constant`. Computed properties use `let body: some View { … }`
or native `var body: some View { … }`. Escape keyword identifiers with backticks.

Native types are spelled `Int`, `Int64`, `Double`, `Bool`, `String`, `[T]`, etc.
`Text` is SwiftUI's view, not portable Minyar's text type. No implicit text,
collection, object, error or closure conversions connect these two targets.
Arrays have Swift value semantics; Minyar's portable `List` reference semantics
and runtime intrinsics are not imported. The targets' runtime profile flags
cannot be mixed. Local `use "./file.min"` imports, module aliases, portable
package resolution and incremental build flags are not implemented here.

Native parsing preserves comments, strings, interpolation, escaped identifiers,
and both bare and extended regex literals. Original `.swift` files and imported
module interfaces retain Swift's immutable `let`, including in mixed-language
compilations. SDK member names such as `Binding.constant` remain intact.
Diagnostics, including tested macro errors, display the original Minyar source
and columns. Debugger/editor integration, macro fix-it spelling, and plugin
line/column queries inside changed spellings still need broader work.

The older source prototype requires extended regex (`#/pattern/#`) and can
require escaped SDK keyword names. Its displayed diagnostic columns and snippets
can reflect lowered source. Use `make check-swiftui` to test that separate path.

## Evidence and limits of the performance claim

`tests/swiftui-equivalent.min` and the independently authored
`tests/swiftui-equivalent.swift` create a concrete `NSHostingView<CounterView>`
with `@State`, text and a button, and run a generic integer sum. The differential
test compiles both with identical module, language and optimization settings,
and the same logical source location (so native `#fileID` strings also match).
It compares **all optimized LLVM IR**, excluding only the two lines naming the
IR output file, and checks that the view body and hosting view survive code
generation. It also compares executable output. Matching generated instructions
are stronger evidence for this fixture than a noisy timing comparison.

Other tests execute native generic protocols and associated types, generic enum
payloads, typed throws, closure ownership and weak-reference destruction, and
actor/async child-task behavior in both debug and release builds. A separate
signed app test mounts the full example's SwiftUI scene and updates its model.
Tests verify multi-file compilation, source diagnostics and preservation of an
existing binary when compilation fails.

These checks establish native code equivalence for the fixture and working
integration for the exercised APIs. They do not prove parity for all SwiftUI
APIs, zero regressions on other architectures or toolchains, animation frame
budgets, accessibility correctness, or every interactive control. The frontend
adds no runtime dispatch/boxing/serialization of its own, but the native SwiftUI
framework and the program still perform their ordinary allocations and work.

## Work required for first-class parity

1. **Complete the language design and conformance contract.** Define Minyar syntax and
   semantics for generics and constraints, protocol conformances and associated
   types, opaque/existential types, overloads, result builders, property wrappers,
   key paths, macros, ownership, noncopyable values, actors and effects. The
   native frontend currently supports a small Minyar dialect alongside Swift
   constructs; it does not unify the portable backend's language/runtime.
2. **Maintain the native semantic integration.** The pinned compiler fork now
   parses Minyar inputs directly and preserves native declarations into SILGen.
   Expand parser, source-map, macro, diagnostic, and compiler-entry-point coverage.
   The installed command-line compiler does not offer an external typed-AST input
   contract, so maintaining the fork and its SDK compatibility is necessary.
3. **Import modules without per-control bindings.** Consume Swift module
   interfaces and Clang modules with availability, overloads, conformances,
   macro plugins, library evolution and resilience intact. The experiment
   already delegates imports to the native compiler, so it has no API whitelist;
   that does not mean every imported API has been validated from Minyar syntax.
4. **Prove code-generation parity continuously.** Expand independent differential
   fixtures to every supported language feature and relevant framework family;
   inspect SIL, LLVM, ARC traffic, allocations, specialization, binary size and
   frame-time distributions. Keep concrete generic view types. Reject accidental
   mandatory erasure, thunk layers or conversion allocations in regression tests.
5. **Provide the developer experience.** Native module emission and package
   dependencies, incremental compilation, source maps, LLDB, SourceKit/LSP,
   previews and macro tooling; assets, resources, entitlements, signing,
   notarization and distribution; test Apple Silicon and Intel where supported.
6. **Maintain SDK parity.** Test compiler/SDK releases and new Swift language
   features. Parity is a maintained compatibility contract, not a one-time ABI
   discovery. iOS and other Apple platforms are outside this macOS experiment.

Native module/library emission, public-interface re-import, actual SwiftUI
scenes, macros, ownership/concurrency, and optimized IR comparison now pass through
the direct frontend. The remaining language and developer-tooling work above is
still outstanding. Reproducible builds, patch architecture, and verified coverage
are recorded in [native frontend integration](native-frontend.md).

Compiling straight to LLVM does not bypass these requirements. LLVM does not
invent Swift protocol witnesses, generic metadata, property-wrapper semantics,
actor isolation or SwiftUI's typed view graph for a frontend. Direct Swift ABI
probes successfully constructed `NSHostingView<AnyView>` through clang in this
investigation, but that approach was not adopted as the SwiftUI product target:
it erased the types and introduced the very integration layer this goal excludes.

Primary references: [Swift compiler architecture](https://www.swift.org/documentation/swift-compiler/),
[SIL documentation](https://github.com/swiftlang/swift/blob/main/docs/SIL/SIL.md),
[Swift calling convention](https://github.com/swiftlang/swift/blob/main/docs/ABI/CallingConvention.rst),
[type metadata](https://github.com/swiftlang/swift/blob/main/docs/ABI/TypeMetadata.rst),
[NSHostingView](https://developer.apple.com/documentation/swiftui/nshostingview).
