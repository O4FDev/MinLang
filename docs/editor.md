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

Checking is synchronous and bounded to 30 seconds and 512 reachable source
files. Messages have a 16 MiB limit. Unsupported requests receive a JSON-RPC
error; unknown notifications are ignored. Rename, workspace symbols and
tree-sitter integration are future work. The server does not claim complete
implementation of every optional LSP 3.17 feature.

The [VS Code extension skeleton](../editors/vscode/README.md) includes highlighting,
language configuration and a stdio client. Any other LSP client can launch the
same server. `make check-minyar-lsp` runs source-index/position tests and a real
stdio client that exercises diagnostics, UTF-16 edits and navigation.
