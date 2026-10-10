# Native Minyar frontend

The experimental `--backend native` target compiles original `.min` files inside
a locally built compiler fork. It reuses Swift's semantic analysis, SILGen,
optimizer, LLVM backend, and ABI. It introduces no Minyar UI runtime or per-view
wrapper. The older `--backend swift` target remains a separate source-lowering
prototype.

**macOS validation status:** the pinned upstream compiler builds and passes all 10
baseline acceptance tests. The patched native compiler builds and passes all
the native acceptance suite, including signed app packaging and execution,
macro diagnostics in original source coordinates, Swift module imports, and
optimized LLVM equality for the comparison fixture. Full language and tooling
parity is not established.

## Build the compiler

The macOS configuration requires Xcode, CMake, Ninja, Git, and Python 3.
For the Linux configuration and GTK SDK, see [Linux desktop development](linux-desktop.md).
It builds locally and does not install into or modify Xcode. On the development
Mac, three jobs fit within 16 GiB RAM. Swift recommends at least 150 GB free for
compiler development; the script's 40 GiB stop threshold is not a guarantee that
a fresh checkout and build will fit.

```sh
/usr/bin/python3 scripts/native-toolchain.py fetch
/usr/bin/python3 scripts/native-toolchain.py baseline --jobs 3
/usr/bin/python3 tests/native-swift/compiler.py \
  --compiler build/native-toolchain/build/Ninja-ReleaseAssert/swift-macosx-$(uname -m)/bin/swiftc \
  --baseline
/usr/bin/python3 scripts/native-toolchain.py native --jobs 3
make check-native-compiler
```

Use `--root /path/to/compiler-workspace` for a different build location. Select
its resulting compiler with `MINYAR_NATIVE_SWIFTC` or `--compiler PATH` when
running the native launcher. Preserve the `swiftc` symlink name: upstream uses
its executable name to select driver versus frontend mode.

The script verifies pinned revisions, locks the build workspace, checks every
patch before applying it, and records patch hashes. Repeated native builds reuse
the patched tree; changed patches require a fresh workspace or explicit manual
reconciliation. A baseline build refuses modified sources. Nothing resets source
checkouts or deletes unrelated files.

The macOS host-only configuration skips replacement standard libraries, SDK overlays,
and their libexec tools. Acceptance tests and the launcher explicitly use
Xcode's installed SDK/runtime resources. Reconfiguration prevents stale CMake
options from accidentally rebuilding a replacement runtime. Linux instead builds
a matching standard library/runtime from the pinned sources.

## Compiler boundary

`toolchains/native-swift/patches/` contains three maintained patches:

- `swift-parser.patch` recognizes `.min` inputs and `main.min`, classifies Minyar
  keywords in the native lexer, parses quoted module imports and colon return
  types, and represents default-unlabelled function parameters in the semantic
  AST. Conditional bindings preserve Minyar mutability in `if`, `guard` and
  `while`, while diagnostics retain original spellings. Original input bytes
  and source locations remain intact.
- `swift-syntax.patch` adds the corresponding per-file syntax dialect to
  SwiftParser. Macro syntax uses canonical Swift spellings in memory, with
  bidirectional mappings back to the original Minyar source.
- `swift-macros.patch` connects those mappings to AST generation, diagnostics,
  macro expansion, conditional compilation, and exported inlinable bodies.
  Existing Swift macros receive compatible syntax; their generated declarations
  retain Swift semantics. Diagnostic rendering uses a separate lossless tree of
  the original bytes, so displayed lines and columns retain Minyar spelling.

Dialect selection follows the actual source buffer. Imported `.swiftinterface`
files, ordinary `.swift` inputs, and generated macro buffers keep Swift's
immutable `let`. Minyar's mutable `let` applies only to original `.min` inputs.
The launcher passes those inputs directly to the compiler without calling the
prototype's source lowerer or creating intermediary Swift source files.

The shared semantic pipeline matters for opaque result types, generics,
protocol witnesses, result builders, property wrappers, Observation, ownership,
concurrency, and SwiftUI's concrete view types. These mechanisms are handled by
the compiler that already implements Swift's runtime contracts. Textual SIL is
not used as an interchange boundary: reparsing a SwiftUI SIL probe failed on a
synthesized accessor in the installed compiler.

The initial dialect supplies `function`, `record`, `constant`, mutable `let`,
quoted `use`, and colon return annotations, alongside native Swift constructs.
This does not yet unify the full language or runtime behavior of Minyar's
existing LLVM backend with this frontend.

## Verification

`tests/native-swift/compiler.py` passes original Minyar files to the compiler.
Its optional `--baseline` flag uses the older source prototype solely to
establish an upstream control. The acceptance cases cover:

- Debug/release execution, generics, typed errors, noncopyable values, parameter
  packs, ARC/weak references, closures, actors, and actual Observation updates.
- Multiple source files, mixed Swift/Minyar inputs, and isolated mutability rules.
- Original-file diagnostic locations and macro diagnostic columns.
- A mounted SwiftUI scene, `@Entry`, `Binding.constant`, and regex execution.
- App packaging through the native launcher, signature verification, and
  preservation of an existing app when compilation fails.
- Plain `.min` project discovery, target-specific replacements, automatic
  within-project visibility, and diagnostics from original selected files.
- Native resilient libraries imported by Swift through both binary modules and
  textual interfaces, using fresh module caches.
- Complete optimized LLVM IR equality for an independent Swift/Minyar SwiftUI
  probe, excluding only module/source filename headers, plus equal execution.

That comparison can establish equal code generation for the tested program. It
cannot establish performance equality for every possible program.

The syntax component suite additionally verifies Unicode, literal contents,
interpolation, multiline-string token positions, escaped names, parameter
labels, invalid imports, and source mappings in both directions. Run it in a
workspace whose fetched sources are still pristine:

```sh
/usr/bin/python3 scripts/native-toolchain.py fetch --root build/syntax-sources
/usr/bin/python3 scripts/native-syntax-check.py --root build/syntax-sources
```

It creates a separate patched copy identified by the patch hash. All changed
C++ files have also passed syntax/type checking against generated compiler
headers, and the patched AST-generation and macro-evaluation Swift modules
compile against the patched syntax libraries.

## Remaining parity work

The direct compilation milestone is verified. Full parity requires broader language/SDK
conformance and compiler entry-point coverage, SourceKit/editor and debugger
integration, and reproducible toolchain distribution. Macro fix-it replacement
text can still contain Swift spelling; plugin line/column queries inside changed
spellings need additional work. Diagnostic fix-its and expansion views need
broader coverage. The backend remains
experimental and is not the default.

## Pinned upstream sources

The [manifest](../toolchains/native-swift/sources.json) pins Swift, SwiftSyntax,
LLVM/Clang, cmark, and experimental string processing to `swift-6.2.4-RELEASE`.
The compiler revision is `ee343b46aef81c3ac7c5d7960cb35a41a88c5a9b`; SwiftSyntax
is `5a87516fc3dddbd23cb76358eb489915ee86b444`. This upstream release is not a
claim to reproduce Apple's installed `swiftlang-6.2.4.1.4` build byte for byte.
Compiler, macro plugins, and SDK compatibility are checked together.

Sources: [Swift compiler setup guide](https://github.com/swiftlang/swift/blob/main/docs/HowToGuides/GettingStarted.md),
[pinned Swift source](https://github.com/swiftlang/swift/tree/ee343b46aef81c3ac7c5d7960cb35a41a88c5a9b),
[pinned SwiftSyntax source](https://github.com/swiftlang/swift-syntax/tree/5a87516fc3dddbd23cb76358eb489915ee86b444).
