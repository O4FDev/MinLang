# Minyar in an editor

Run `minyar lsp --stdio` to start the language server. It speaks JSON-RPC over
standard input and output using the [LSP 3.17 framing and lifecycle](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/).
Build messages and errors go to standard error. A cold source checkout builds
the server on first use; installed toolchains should include its executable.
The current server uses the macOS and Linux host services.

The server supplies:

- Live compiler diagnostics when a document opens, changes or saves, with
  versioned clearing when errors are fixed or a document closes.
- Hover with declaration signatures, annotated or directly inferred types,
  and leading `///` documentation.
- Definitions across local modules and configured package source directories.
- References and rename for resolved declarations, parameters, locals, import
  aliases, record fields and methods, including callers in unopened files.
- Inlay type hints for unannotated bindings with complete scalar literal values.
- Quick fixes for the compiler's unambiguous `did you mean` name suggestions.
- Completion for visible names, fields, methods, module exports, choice cases
  and common built-in collection/Text operations.
- Document symbols and canonical document formatting through `minyar fmt`.

Text synchronization accepts full replacements and incremental edits. Positions
use UTF-16 code units, including non-BMP characters. The server keeps unsaved
buffers in memory. Compiler checking uses a private snapshot of the reachable
import graph, including other open buffers; it never rewrites user source files.
When a dependency changes, other open documents are checked again. Closed disk
modules are refreshed when used. Source locations are mapped back from the
private files to the user's document URIs.

```sh
minyar lsp --stdio
minyar lsp --compiler /path/to/minyarc --library /path/to/package/src
```

Additional `--library` directories and `initialize.initializationOptions.libraryPaths`
are searched before the standard library. Relative initialization paths resolve
from the workspace root. The workspace's `src` directory and local dependency
paths in an existing `Minyar.lock` are discovered automatically. When the
toolchain includes the project CLI, locked offline metadata supplies verified
Git cache paths too. The server does not fetch packages or change lockfiles;
pass package source directories through `libraryPaths` when metadata is not
available or the lockfile needs updating.

Compiler `--error-format json` diagnostics use the same message and source span
as the command line. The server accepts the diagnostic agent's NDJSON schema
and translates its one-based Unicode scalar columns into LSP's zero-based UTF-16
ranges. A legacy compiler is detected once and its text diagnostics remain
usable; errors that lack a source span use the start of the file. The compiler
is the authority on language validity. The source index supports incomplete
buffers, while semantic navigation currently follows declarations, annotations,
direct literals, factory return types and dotted names. It does not yet resolve
every generic instantiation or arbitrary receiver expression into a checked type.
For a complex initializer with operators or chained calls, an explicit type
annotation helps the editor navigate the resulting value.

References search project `.min` files, open buffers and their reachable imports.
Hidden directories, `build`, `target`, `node_modules` and `vendor` are excluded
from directory discovery. The scan stops at 512 sources, 4,096 directories or
32,768 entries. References can be partial at those limits; rename refuses a
truncated search. Closed sources are reread and open sources use their current
buffer contents. Edits carry buffer versions when the client supports versioned
workspace edits. The server returns edits for the editor to apply.

Rename checks overlapping declarations and name capture. Names shared across
value, type, function or import namespaces are declined because the index cannot
distinguish every use. Shadowed callback factories likewise do not supply an
inferred receiver type. It accepts ASCII
identifier names and declines unsupported bindings, choice cases, interpolated
references and unresolved expressions that could make an edit incomplete.
References currently omit interpolation bodies. These restrictions preserve a
small, useful rename surface until compiler-resolved symbol metadata is available.
Inlay hints likewise omit inferred expressions whose type is not certain from
the source index; an expression beginning with `1` is not necessarily an Integer.

Quick fixes use the current compiler diagnostic's exact identifier range and
suggested replacement. Old diagnostics or arbitrary help prose do not become
edits. They require the client's `codeActionLiteralSupport` capability; other
clients continue to receive diagnostics. Prepare-rename is advertised only when
the client declares `rename.prepareSupport`.

Checking is synchronous and bounded to 30 seconds and 512 reachable source
files. Messages have a 16 MiB limit. Unsupported requests receive a JSON-RPC
error; unknown notifications are ignored. Workspace symbols and tree-sitter
integration are future work. The server does not claim complete
implementation of every optional LSP 3.17 feature.

The [Cursor and VS Code extension](../editors/vscode/README.md) includes highlighting,
language configuration, a stdio client and local VSIX installation instructions.
Any other LSP client can launch the
same server. `make check-minyar-lsp` runs source-index/position tests and a real
stdio client that exercises diagnostics, UTF-16 edits, navigation and refactoring.
The [lighthouse gallery](../examples/gallery/lighthouse-editor.min) is a small
source file for trying hover docs, field navigation, rename and literal hints.
