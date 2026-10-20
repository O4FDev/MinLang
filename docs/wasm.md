# WebAssembly and Try Minyar

Minyar can compile to a WASI Preview 1 WebAssembly command. The target uses
the ordinary self-hosted frontend and LLVM backend. Integer stays signed
64-bit, Float stays double precision, and shared records, Lists, Maps, Sets,
choices and callbacks keep their reference semantics.

With the repository's pinned LLVM toolchain, Python 3.10 or newer, and Node
22 or newer:

```sh
make wasm SOURCE=examples/gallery/wasm-lanterns.min OUTPUT=build/lanterns.wasm
```

The first build downloads integrity-pinned WASI tools. Later builds reuse
them. The standalone target driver accepts an optimization level:

```sh
node tools/wasm-target.mjs examples/gallery/wasm-lanterns.min build/lanterns.wasm -O0
node tools/wasm-target.mjs examples/gallery/wasm-lanterns.min build/lanterns.wasm -O2
```

A failed compilation preserves the previous output. A WASI Preview 1 host
can execute the resulting file; the repository's Node runner is one option:

```sh
node --no-warnings tests/wasm-target.mjs --run build/lanterns.wasm
```

The target currently uses eager reclamation, including cyclic managed
graphs. It caps language call depth at 1,024. Native stack-trace metadata is
omitted because its linker-relative addresses and native unwind mechanism
do not apply to this target. Runtime failures retain their messages and
exit status. OS-specific native libraries, managed threads, and arbitrary
native C dependencies need a separate WASI port; this target does not make
those libraries portable. The compiler's existing sequential parallel-loop
backend is available.

## The static playground

```sh
make playground
python3 -m http.server 8000 --directory build/playground
```

Open `http://localhost:8000`. Any static HTTP host can serve the complete
`build/playground` directory. No backend, account, CDN, package manager or
network compiler is needed by a visitor. Keep the `vendor` and `licenses`
directories and third-party notices with the site. Serve JavaScript modules
with a JavaScript MIME type. HTTP compression substantially reduces the
initial transfer.

The editor checks after a short pause and shows the real compiler's JSON
diagnostics, with source positions and suggestions. Clicking an error
selects its range, including after non-BMP Unicode characters. Run compiles
edited source to WebAssembly and executes it in a worker. Cmd/Ctrl+Enter
runs; Stop terminates the worker. A guided tour contains six editable
programs, ending with the lantern gallery. Save .wasm downloads the actual
compiled program. Drafts are stored on the current browser when local
storage is available.

Compilation has two stages, both in the browser: the wasm build of Minyar's
self-hosted compiler emits LLVM, then the bundled YoWASP LLVM/Clang toolchain
links it with a prebuilt Minyar runtime. Live checking runs only the
frontend. Each compiler and user execution gets a fresh WASI instance and
in-memory files. Files disappear after each execution; no host filesystem
or network is exposed to a program. The bundled portable modules are
`maybe`, `errors`, `text`, `math`, `io`, `process`, `random` and `json`.

The frontend has a 512 MiB linear-memory ceiling and programs have a 256 MiB
ceiling. Source and captured output are each limited to 64 KiB. Virtual-file
growth is capped at 16 MiB per execution, with at most 256 open/create/link
operations, with paths limited to 4 KiB before UTF-8 decoding. File growth
is checked before JavaScript allocation, including sparse writes. Preparation
and compilation have a two-minute limit; execution has a
ten-second limit. Stop and timeouts discard the worker and its state.

The initial toolchain is large: about 107 MB uncompressed. Its two main LLVM
assets compress to about 27.1 MB with gzip. A recent browser supporting
WebAssembly exceptions is required for compiler diagnostic recovery.
Compilation and execution are tested in Chromium. This is an initial
browser target; these focused checks do not establish full native-suite
conformance or performance parity.

## Verification

```sh
make check-wasm
make prepare-playground-tests
make check-playground
```

`check-wasm` executes real O0/O2 WASI programs, including every unmodified
fixture in the native language conformance index, checks cycle cleanup and
failed-output preservation, runs every tour through the wasm frontend and
browser LLVM backend, compares native/wasm frontend LLVM, and checks
diagnostic recovery and resource limits. `check-playground` also drives
Chromium through the editor, worker, cancellation and draft workflows.
Evidence is retained under `build/wasm-evidence`. The separate WebAssembly
CI workflow builds and tests the site and uploads it as a static artifact.

The browser LLVM distribution is independently pinned from the native LLVM
toolchain: npm package `@yowasp/clang@22.0.0-git20542-10` reports LLVM 22.1.0.
See [third-party notices](../playground/THIRD_PARTY.md) for exact archives,
hashes, source snapshots and licenses. Update those together when changing
the browser toolchain.
