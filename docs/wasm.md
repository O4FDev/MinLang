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
programs, ending with the lantern gallery. Each step explains one idea,
offers an editable challenge, a hint and an output goal. Progress records
observed matching outputs on this device; it is not a proof of learning.
Save .wasm downloads the actual compiled program. Drafts and tour progress
are stored on the current browser when local storage is available.

The language-guide library contains every Minyar code block from
[docs/language.md](language.md), with its heading and original source line.
Search by topic or source text. Standalone blocks run unchanged; excerpts
that need surrounding declarations, test mode or native host APIs retain
their source and explain what is missing.
Run stays unavailable for an unchanged contextual excerpt. You can edit
one into a complete program and run your visible edit. No hidden scaffold
or source rewrite is added. Provenance distinguishes an original example
from an edited draft. The catalog generator checks every block and source
hash; new or changed blocks require an explicit classification and output
oracle before the site builds. Each build generates its catalog from the
current guide, keeping source locations current after documentation edits.

Programs can contain up to 16 source files, with 64 KiB of combined UTF-8
source. Add a file such as `geometry.min`, then use the file buttons to edit
it. Run always starts at the entry shown above the editor, normally
`main.min`. Switching the displayed file does not change the entry. Imports
resolve relative to their importing file; an unused file is not checked.
A diagnostic selects its source file and range, including preserved CRLF
and bare-CR source. Remove file keeps one undo; the entry cannot be removed.
Project drafts retain all files and the selected file across reloads.
The guide’s local-module excerpt offers Add geometry.min. This explicit action
adds a visible companion with public Point and answer declarations; the guide
entry stays unchanged. Both files can be inspected, edited and shared.

File names are relative `.min` paths of at most 256 UTF-8 bytes, using forward
slashes. Nested folders, spaces and Unicode are supported. Dot and parent
segments, control characters, duplicate/file-directory collisions and the
reserved `library/` root are rejected. Over-budget edits stay visible but
cannot be compiled, saved or shared until the source fits again.

Share code creates a link containing the complete project in its URL
fragment. It makes no upload or server request. Query parameters and old
fragments are omitted. The link appears in a selectable field and is copied
when clipboard access is available. Anyone with the link can read the
source; it is not encrypted. All project files share a 64 KiB UTF-8 source
limit. Links use an uncompressed versioned encoding and carry a checksum to
detect damaged links. Single-file links use the original v1 format; projects
use v2 with a canonical binary file list. Old source-only links still open.
Some messaging apps impose shorter URL limits.

Opening a shared link takes precedence over the displayed draft and never
starts a compiler check or execution. Review it, then choose Run code.
The prior local draft is kept until you explicitly edit the shared program
or choose another example. Invalid or unsupported links leave the current
program intact with an explanation. Browser back/forward navigation opens
the corresponding source; edits made while a link is decoding are retained.

Compilation has two stages, both in the browser: the wasm build of Minyar's
self-hosted compiler emits LLVM, then the bundled YoWASP LLVM/Clang toolchain
links it with a prebuilt Minyar runtime. Live checking runs only the
frontend. Each compiler and user execution gets a fresh WASI instance and
in-memory files. Project sources exist only in the compiler filesystem; a
user program starts with an empty filesystem. Files disappear after each
execution; no host filesystem
or network is exposed to a program. The bundled portable modules are
`maybe`, `errors`, `text`, `math`, `io`, `process`, `random` and `json`.

The frontend has a 512 MiB linear-memory ceiling and programs have a 256 MiB
ceiling. Source and captured output are each limited to 64 KiB. Virtual-file
growth is capped at 16 MiB per execution, with at most 256 open/create/link
operations, with paths limited to 4 KiB before UTF-8 decoding. File growth
is checked before JavaScript allocation, including sparse writes. Preparation
and compilation have a two-minute limit; execution has a
ten-second limit. Stop and timeouts discard the worker and its state.

The toolchain is large: about 79 MB uncompressed. Its two main LLVM assets
compress to about 23.2 MB with gzip. Browser packaging keeps only the seven
WASI link resources needed by the IR pipeline; the full native sysroot is
preserved. The generated `resources-transform.json` records every input and
output hash. A recent browser supporting
WebAssembly exceptions is required for compiler diagnostic recovery.
Compilation and execution are tested in Chromium. This is an initial
browser target; these focused checks do not establish full native-suite
conformance or performance parity.

## Verification

```sh
make check-wasm
make prepare-playground-tests
make check-playground
# Focused browser checks while working on a feature:
make check-playground-sharing
make check-playground-learning
make check-playground-projects
```

`check-wasm` executes real O0/O2 WASI programs, including every unmodified
fixture in the native language conformance index, checks cycle cleanup and
failed-output preservation, runs every tour through the wasm frontend and
browser LLVM backend, compares native/wasm frontend LLVM, and checks
diagnostic recovery and resource limits. `check-playground` also drives
Chromium through the editor, worker, cancellation, drafts, private fragment
links, all six challenge solutions, the full guide picker and its contextual
Run guards. Project checks exercise relative and Unicode imports, changed
dependency cache identity, full-project links/drafts, file-aware diagnostic
selection, source budgets and fresh execution filesystems. Every standalone
guide block also executes through the real
browser frontend/backend with independently reviewed stdout and exit status.
Evidence is retained under `build/wasm-evidence`. The separate WebAssembly
CI workflow builds and tests the site and uploads it as a static artifact.

The browser LLVM distribution is independently pinned from the native LLVM
toolchain: npm package `@yowasp/clang@22.0.0-git20542-10` reports LLVM 22.1.0.
See [third-party notices](../playground/THIRD_PARTY.md) for exact archives,
hashes, source snapshots and licenses. Update those together when changing
the browser toolchain.

See the [WASI hello-world comparison](research/wasm-comparison.md) for
reproducible size, build time, startup and linear-memory measurements against
Go, Rust and Zig. Minyar produced the smallest module in that experiment;
Rust started faster and reserved less linear memory. The raw samples,
toolchain hashes and exact flags are retained, and the results apply to
those hello-world programs rather than general language performance.
